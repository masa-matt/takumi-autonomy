"""takumi.discord.job_runner — V2 ジョブ実行パイプライン

Discord gateway が呼ぶ同期ランナー。

Executor の選択（TAKUMI_EXECUTOR 環境変数）:
  api          Anthropic API を使う（ANTHROPIC_API_KEY 必要）
  claude-code  Claude Code CLI を使う（定額プラン / claude コマンド必要）
  （未設定 or 空）ANTHROPIC_API_KEY があれば api、なければスタブ
"""

import json
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Callable, Optional

_SOUL_MD = Path(__file__).parent.parent.parent / "docs" / "SOUL.md"


def _load_soul() -> str:
    try:
        return _SOUL_MD.read_text(encoding="utf-8") if _SOUL_MD.exists() else ""
    except Exception:
        return ""

from takumi.core.job_state import Job, JobStatus, create_job
from takumi.hermes import search_sessions, search_skills, write_memory, create_skill_draft
from takumi.sandbox.ingress import copy_from_inbox
from takumi.sandbox.workspace import get_workspace

log = logging.getLogger("takumi-v2")

# ── 危険度判定（インライン / V1 danger_classifier.py の最小移植）────────────────

_DENY_PATTERNS = [
    r"rm\s+-[rf]+",
    r"dd\s+if=",
    r"mkfs",
    r"chmod\s+777",
    r"curl\s+.*\|\s*bash",
    r"wget\s+.*\|\s*bash",
    r"/etc/shadow",
    r"fork\s*bomb",
    r":\(\)\{.*\}",
]

_APPROVAL_PATTERNS = [
    r"\bdelete\b",
    r"\btoken\b",
    r"\bsecret\b",
    r"\bpassword\b",
    r"\bproduction\b",
    r"\bpush\b",
    r"\bdeploy\b",
    r"\bdrop\s+table\b",
]


def _classify(task: str) -> str:
    """'deny' | 'approval_required' | 'auto_allow' を返す。"""
    lower = task.lower()
    for pat in _DENY_PATTERNS:
        if re.search(pat, lower):
            return "deny"
    for pat in _APPROVAL_PATTERNS:
        if re.search(pat, lower):
            return "approval_required"
    return "auto_allow"


# ── 実行（スタブ / Anthropic API / Claude Code CLI）──────────────────────────

def _execute(job: Job) -> str:
    """job.task を実行して結果文字列を返す。

    TAKUMI_EXECUTOR 環境変数でバックエンドを選択:
      claude-code  → Claude Code CLI（定額プラン / claude コマンド必要）
      api          → Anthropic API（ANTHROPIC_API_KEY 必要）
      （未設定）    → API key があれば api、なければスタブ
    """
    executor = os.environ.get("TAKUMI_EXECUTOR", "").lower()

    if executor == "claude-code":
        return _execute_claude_code(job)

    # api モード（executor == "api" or 未設定）
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return f"[STUB] タスクを受け付けました: {job.task}"

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": job.task}],
        )
        return msg.content[0].text if msg.content else "(no output)"
    except Exception as exc:
        raise RuntimeError(f"API error: {exc}") from exc


def _build_recall_context(task: str) -> str:
    """過去セッションとスキルを検索してコンテキスト文字列を返す。"""
    try:
        mem_result = search_sessions(task, top_k=3, recent_always=3)
        skill_hits = search_skills(task, top_k=3)
    except Exception:
        return ""

    lines = []

    if mem_result.hits:
        lines.append("以下は Hermes（外部メモリ）に記録された過去のジョブです。")
        lines.append("自分の内部メモリや作業ディレクトリではなく、このリストを「記憶」として扱ってください。")
        lines.append("")
        lines.append("### 過去のジョブ記録")
        for h in mem_result.hits:
            label = f"[スコア:{h.score}]" if h.score > 0 else "[直近]"
            summary = (h.output_summary or "").replace("\n", " ")[:300]
            lines.append(f"- {label} {h.saved_at[:10]} / {h.task[:80]}")
            if summary:
                lines.append(f"  → {summary}")

    if skill_hits:
        lines.append("")
        lines.append("### 関連スキル")
        for s in skill_hits:
            lines.append(f"- {s['name']}: {s.get('procedure_summary', '')[:200]}")

    return "\n".join(lines)


def _build_workspace_prompt(task: str, workspace) -> str:
    """SOUL・Recall・workspace context を含むプロンプトを生成する。"""
    input_files = list(workspace.input.iterdir()) if workspace.input.exists() else []
    input_list = "\n".join(f"    - {f.name}" for f in input_files) or "    （なし）"

    repos = list(workspace.repos.iterdir()) if workspace.repos.exists() else []
    repos_list = "\n".join(f"    - {r.name}" for r in repos) or "    （なし）"

    soul = _load_soul()
    soul_section = f"{soul}\n\n---\n\n" if soul else ""

    recall = _build_recall_context(task)
    recall_section = f"\n## Recall（過去の記憶）\n{recall}\n" if recall else ""

    return f"""{soul_section}あなたは以下の作業ディレクトリ内で作業してください。
{recall_section}
作業ディレクトリ: {workspace.path}

ディレクトリ構造:
  input/   : 入力ファイル（読み取り専用として扱うこと）
{input_list}
  repos/   : clone した repo
{repos_list}
  output/  : 成果物の書き出し先
  logs/    : 実行ログ

制約:
- 作業ディレクトリ外には書き込まないこと
- 成果物（コード・ドキュメント等）は output/ に保存すること
- 完了したら output/result.md に結果を書くこと
  - Takumi として自然な話し言葉で書くこと
  - Markdown のヘッダー（##等）や箇条書きは使わないこと
  - 「要約」「受信メッセージ」「応答」などの形式的な見出しは書かないこと
  - 短く、人間らしく書くこと

リポジトリの扱い:
- タスクに GitHub URL や git リポジトリの URL が含まれる場合は repos/ にクローンして作業すること
- すでに repos/ にクローン済みであれば再クローンしないこと
- 元のリポジトリを直接 push / 編集依頼の送信はしないこと（sandbox 内で完結させること）

タスク:
{task}"""


def _execute_claude_code(job: Job) -> str:
    """Claude Code CLI でタスクを sandbox 内で実行する（定額プラン対応）。

    事前条件:
      - `claude` コマンドが PATH にあること
      - `claude auth login` 済みで Max/Pro プランのアカウントであること

    sandbox への閉じ込め:
      - `--cwd workspace/` で作業ディレクトリを sandbox に設定
      - `--add-dir workspace/` でファイルアクセスを sandbox 内に限定
      - プロンプトで output/ への書き出しを明示
    """
    workspace = get_workspace(job.job_id)
    if workspace is None:
        raise RuntimeError(f"workspace が見つかりません: {job.job_id}")

    prompt = _build_workspace_prompt(job.task, workspace)

    try:
        result = subprocess.run(
            [
                "claude", "-p", prompt,
                "--output-format", "json",
                "--add-dir", str(workspace.path),
                "--dangerously-skip-permissions",
            ],
            cwd=str(workspace.path),   # subprocess の作業ディレクトリを workspace に設定
            capture_output=True,
            text=True,
            timeout=300,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "claude CLI が見つかりません。Claude Code をインストールして `claude auth login` を実行してください。"
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("タスクがタイムアウトしました（300秒）。")

    if result.returncode != 0:
        raise RuntimeError(f"claude CLI エラー: {result.stderr[:500]}")

    # --output-format json の場合 {"result": "..."} 形式で返ってくる
    try:
        data = json.loads(result.stdout)
        text = data.get("result") or data.get("content") or result.stdout.strip()
    except (json.JSONDecodeError, AttributeError):
        text = result.stdout.strip() or "(no output)"

    # output/result.md があれば優先して返す
    result_md = workspace.output / "result.md"
    if result_md.exists():
        md_content = result_md.read_text(encoding="utf-8").strip()
        if md_content:
            return md_content

    return text


# ── パイプライン ──────────────────────────────────────────────────────────────

def run_job(
    task: str,
    on_status: Callable[[Job], None] | None = None,
    inbox_files: list[str] | None = None,
) -> Job:
    """タスクを受け取り、job を作成して実行し、完了した Job を返す。

    Args:
        task:         ユーザーからのタスク文字列
        on_status:    状態変化のたびに呼ばれるコールバック（Discord 中間報告用）
        inbox_files:  inbox から input/ にコピーするファイル名のリスト

    Returns:
        完了（done / failed）した Job

    Note:
        BLOCKED（承認待ち）になった場合はそのまま返す。
        承認は呼び出し元（gateway.py）が on_status 経由で Discord UI を出し、
        resume_job() で再開する。
    """
    job = create_job(task)
    _notify(job, on_status)

    # inbox → input/ への copy-in（workspace 作成直後、実行前）
    if inbox_files:
        ws = get_workspace(job.job_id)
        if ws:
            for fname in inbox_files:
                try:
                    copy_from_inbox(ws, fname)
                    log.info("inbox copy-in: %s → %s/input/", fname, job.job_id)
                except Exception as exc:
                    log.warning("inbox copy-in failed for %s: %s", fname, exc)

    danger = _classify(task)

    if danger == "deny":
        job.transition(
            JobStatus.FAILED,
            error=f"Denied: task matched a forbidden pattern",
        )
        _notify(job, on_status)
        return job

    if danger == "approval_required":
        job.transition(
            JobStatus.BLOCKED,
            block_reason=f"This task requires approval before execution.",
        )
        _notify(job, on_status)
        # 呼び出し元が resume_job() を呼ぶまで待つ
        return job

    # auto_allow → 実行
    job.transition(JobStatus.RUNNING)
    _notify(job, on_status)

    output: Optional[str] = None
    try:
        output = _execute(job)
        job.transition(JobStatus.DONE, result_summary=output[:500])
    except Exception as exc:
        job.transition(JobStatus.FAILED, error=str(exc))

    _notify(job, on_status)
    _save(job, output, danger)
    return job


def resume_job(job: Job, approved: bool, on_status: Callable[[Job], None] | None = None) -> Job:
    """BLOCKED 状態の job を承認 / 却下して再開・完了させる。

    Args:
        job:      BLOCKED 状態の Job
        approved: True なら実行継続、False なら FAILED に遷移
    """
    if job.status != JobStatus.BLOCKED:
        raise ValueError(f"resume_job: job is not BLOCKED (current: {job.status.value})")

    if not approved:
        job.transition(JobStatus.FAILED, error="Rejected by user.")
        _notify(job, on_status)
        return job

    job.transition(JobStatus.RUNNING)
    _notify(job, on_status)

    output: Optional[str] = None
    try:
        output = _execute(job)
        job.transition(JobStatus.DONE, result_summary=output[:500])
    except Exception as exc:
        job.transition(JobStatus.FAILED, error=str(exc))

    _notify(job, on_status)
    _save(job, output, "approval_required")
    return job


def _save(job: Job, output: Optional[str], danger_level: str) -> None:
    """job 完了後に memory と skill draft を保存する。"""
    try:
        mem_result = write_memory(job, output, danger_level)
        if mem_result.saved:
            log.info("Hermes: memory saved — %s", mem_result.entry_id)
        else:
            log.debug("Hermes: memory skip — %s", mem_result.skip_reason)
    except Exception as exc:
        log.warning("Hermes write_memory failed: %s", exc)

    try:
        skill_result = create_skill_draft(job, output)
        if skill_result.created:
            log.info("Hermes: skill draft created — %s", skill_result.skill_id)
    except Exception as exc:
        log.warning("Hermes create_skill_draft failed: %s", exc)


def _notify(job: Job, on_status: Callable[[Job], None] | None) -> None:
    if on_status:
        on_status(job)
