"""takumi.core.job_state — Job の状態機械

V2 の 5 状態:
    queued   → タスク受付、sandbox 未確保
    running  → 実行中
    blocked  → 承認待ち（危険操作が含まれる場合）
    done     → 正常完了
    failed   → 失敗（retry 上限超過 / 実行エラー）

状態遷移グラフ:
    queued  → running | blocked | failed
    running → done | failed | blocked
    blocked → running | failed      (承認 → running, 却下 → failed)
    done    → (終端)
    failed  → (終端)
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from takumi.sandbox.workspace import JOBS_DIR, create_workspace


# ── Job ID ────────────────────────────────────────────────────────────────────

def generate_job_id() -> str:
    """job-YYYYMMDD-XXXXXXXX 形式の一意 ID を返す。"""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d")
    uid = uuid.uuid4().hex[:8]
    return f"job-{ts}-{uid}"


# ── 状態 ──────────────────────────────────────────────────────────────────────

class JobStatus(Enum):
    QUEUED  = "queued"
    RUNNING = "running"
    BLOCKED = "blocked"
    DONE    = "done"
    FAILED  = "failed"


# 有効な状態遷移
_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.QUEUED:   {JobStatus.RUNNING, JobStatus.BLOCKED, JobStatus.FAILED},
    JobStatus.RUNNING:  {JobStatus.DONE, JobStatus.FAILED, JobStatus.BLOCKED},
    JobStatus.BLOCKED:  {JobStatus.RUNNING, JobStatus.FAILED},
    JobStatus.DONE:     set(),
    JobStatus.FAILED:   set(),
}


# ── Job dataclass ─────────────────────────────────────────────────────────────

@dataclass
class Job:
    job_id:          str
    task:            str
    status:          JobStatus = JobStatus.QUEUED
    workspace_path:  str | None = None
    created_at:      str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at:      str | None = None
    completed_at:    str | None = None
    error:           str | None = None
    block_reason:    str | None = None   # BLOCKED 時の理由
    result_summary:  str | None = None   # DONE 時の要約

    # ── 状態遷移 ──────────────────────────────────────────────────────────────

    def transition(self, new_status: JobStatus, **kwargs) -> None:
        """new_status に遷移する。許可されていない遷移は ValueError。

        kwargs: error / block_reason / result_summary など任意フィールドを同時更新。
        """
        allowed = _TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Invalid transition: {self.status.value} → {new_status.value}"
            )
        self.status = new_status
        now = datetime.now(timezone.utc).isoformat()
        if new_status == JobStatus.RUNNING and self.started_at is None:
            self.started_at = now
        if new_status in (JobStatus.DONE, JobStatus.FAILED):
            self.completed_at = now
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)
        self._persist()

    # ── 永続化 ────────────────────────────────────────────────────────────────

    def _persist(self) -> None:
        """workspace の state/job.json に現在の状態を書き込む。"""
        if not self.workspace_path:
            return
        state_dir = Path(self.workspace_path) / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        with open(state_dir / "job.json", "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    def to_dict(self) -> dict:
        return {
            "job_id":         self.job_id,
            "task":           self.task,
            "status":         self.status.value,
            "workspace_path": self.workspace_path,
            "created_at":     self.created_at,
            "started_at":     self.started_at,
            "completed_at":   self.completed_at,
            "error":          self.error,
            "block_reason":   self.block_reason,
            "result_summary": self.result_summary,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Job":
        data = dict(data)
        data["status"] = JobStatus(data["status"])
        return cls(**data)

    @classmethod
    def load(cls, job_id: str) -> "Job | None":
        """state/job.json から既存 job を読み込む。存在しなければ None。"""
        state_file = JOBS_DIR / job_id / "state" / "job.json"
        if not state_file.exists():
            return None
        with open(state_file, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


# ── ファクトリ ─────────────────────────────────────────────────────────────────

def create_job(task: str) -> Job:
    """新しい job を QUEUED 状態で作成し、workspace を確保して返す。"""
    job_id = generate_job_id()
    ws = create_workspace(job_id)
    job = Job(job_id=job_id, task=task, workspace_path=str(ws.path))
    job._persist()
    return job
