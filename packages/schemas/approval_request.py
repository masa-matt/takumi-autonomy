from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class DangerLevel(Enum):
    AUTO_ALLOW = "auto_allow"
    APPROVAL_REQUIRED = "approval_required"
    DENY = "deny"


class ApprovalStatus(Enum):
    PENDING = "pending"
    AUTO_APPROVED = "auto_approved"   # danger_level=AUTO_ALLOW
    APPROVED = "approved"             # human or --auto-approve flag
    DENIED = "denied"                 # human denial or DENY policy


@dataclass
class ApprovalRequest:
    job_id: str
    task_description: str
    danger_level: DangerLevel
    reason: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None  # "policy_auto_allow" | "policy_deny" | "auto" | "human"

    @property
    def is_allowed(self) -> bool:
        return self.status in (ApprovalStatus.AUTO_APPROVED, ApprovalStatus.APPROVED)

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "task_description": self.task_description,
            "danger_level": self.danger_level.value,
            "reason": self.reason,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by": self.resolved_by,
        }
