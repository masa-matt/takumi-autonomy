from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ExecutionResult:
    job_id: str
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    artifacts: list = field(default_factory=list)
    completed_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "artifacts": self.artifacts,
            "completed_at": self.completed_at.isoformat(),
            "metadata": self.metadata,
        }
