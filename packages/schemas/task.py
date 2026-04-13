from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Task:
    description: str
    context: dict = field(default_factory=dict)


@dataclass
class Job:
    job_id: str
    task: Task
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    workspace_path: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "task": {
                "description": self.task.description,
                "context": self.task.context,
            },
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "workspace_path": self.workspace_path,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
        }
