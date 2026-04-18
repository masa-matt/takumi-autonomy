"""takumi.core.executor_adapter — executor バックエンドの抽象化

TAKUMI_EXECUTOR 環境変数で実行バックエンドを切り替える。
  claude-code  Claude Code CLI（定額プラン・OAuth）
  api          Anthropic API（ANTHROPIC_API_KEY 必要）
  （未設定）    API key があれば api、なければスタブ
"""

import json
import logging
import os
import subprocess
from pathlib import Path

log = logging.getLogger("takumi-v2")


def execute(job, workspace) -> str:
    """job を実行して結果文字列を返す。バックエンドは TAKUMI_EXECUTOR で選択。"""
    executor = os.environ.get("TAKUMI_EXECUTOR", "").lower()

    if executor == "claude-code":
        return _execute_claude_code(job, workspace)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        return _execute_api(job, api_key)

    return f"[STUB] タスクを受け付けました: {job.task}"


# ── Claude Code ───────────────────────────────────────────────────────────────

def _execute_claude_code(job, workspace) -> str:
    from takumi.discord.job_runner import _build_workspace_prompt
    prompt = _build_workspace_prompt(job.task, workspace)

    try:
        result = subprocess.run(
            [
                "claude", "-p", prompt,
                "--output-format", "json",
                "--add-dir", str(workspace.path),
                "--dangerously-skip-permissions",
            ],
            cwd=str(workspace.path),
            capture_output=True,
            text=True,
            timeout=300,
        )
    except FileNotFoundError:
        raise RuntimeError("claude CLI が見つかりません。")
    except subprocess.TimeoutExpired:
        raise RuntimeError("タスクがタイムアウトしました（300秒）。")

    if result.returncode != 0:
        raise RuntimeError(f"claude CLI エラー: {result.stderr[:500]}")

    try:
        data = json.loads(result.stdout)
        text = data.get("result") or data.get("content") or result.stdout.strip()
    except (json.JSONDecodeError, AttributeError):
        text = result.stdout.strip() or "(no output)"

    result_md = workspace.output / "result.md"
    if result_md.exists():
        md = result_md.read_text(encoding="utf-8").strip()
        if md:
            return md

    return text


# ── Anthropic API ─────────────────────────────────────────────────────────────

def _execute_api(job, api_key: str) -> str:
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
