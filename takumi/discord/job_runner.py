"""takumi.discord.job_runner — V2 ジョブ実行パイプライン

Discord gateway が呼ぶ同期ランナー。
CP-LV2-02 スコープ: job状態管理 + 危険判定 + 実行(stub/API) + 結果返却

Executor は ANTHROPIC_API_KEY があれば Anthropic API を使い、
なければスタブとして応答する（sandbox 基盤の検証用）。
"""

import logging
import os
import re
from typing import Callable

from takumi.core.job_state import Job, JobStatus, create_job
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


# ── 実行（スタブ / Anthropic API）────────────────────────────────────────────

def _execute(job: Job) -> str:
    """job.task を実行して結果文字列を返す。"""
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

    try:
        result = _execute(job)
        job.transition(JobStatus.DONE, result_summary=result[:500])
    except Exception as exc:
        job.transition(JobStatus.FAILED, error=str(exc))

    _notify(job, on_status)
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

    try:
        result = _execute(job)
        job.transition(JobStatus.DONE, result_summary=result[:500])
    except Exception as exc:
        job.transition(JobStatus.FAILED, error=str(exc))

    _notify(job, on_status)
    return job


def _notify(job: Job, on_status: Callable[[Job], None] | None) -> None:
    if on_status:
        on_status(job)
