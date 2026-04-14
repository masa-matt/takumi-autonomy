from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class SkillStatus(Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    DEPRECATED = "deprecated"


@dataclass
class Skill:
    skill_id: str
    name: str
    description: str
    trigger_keywords: list
    source_job_id: str
    source_task: str
    procedure_summary: Optional[str]
    status: SkillStatus = SkillStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = None
    use_count: int = 0

    def to_dict(self) -> dict:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "trigger_keywords": self.trigger_keywords,
            "source_job_id": self.source_job_id,
            "source_task": self.source_task,
            "procedure_summary": self.procedure_summary,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "use_count": self.use_count,
        }


@dataclass
class SkillResult:
    created: bool
    skill_id: Optional[str] = None
    skip_reason: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "created": self.created,
            "skill_id": self.skill_id,
            "skip_reason": self.skip_reason,
        }
