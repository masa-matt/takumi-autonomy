"""takumi.hermes.models — Hermes data types (no external deps)"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


# ── Memory ────────────────────────────────────────────────────────────────────

@dataclass
class MemoryEntry:
    entry_id: str
    job_id: str
    task: str
    status: str
    output_summary: Optional[str]
    danger_level: str
    saved_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tags: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "job_id": self.job_id,
            "task": self.task,
            "status": self.status,
            "output_summary": self.output_summary,
            "danger_level": self.danger_level,
            "saved_at": self.saved_at,
            "tags": self.tags,
        }


@dataclass
class SearchHit:
    entry_id: str
    job_id: str
    task: str
    output_summary: Optional[str]
    saved_at: str
    score: float

    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "job_id": self.job_id,
            "task": self.task,
            "output_summary": self.output_summary,
            "saved_at": self.saved_at,
            "score": self.score,
        }


@dataclass
class SearchResult:
    query: str
    hits: list
    total_searched: int

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "hits": [h.to_dict() for h in self.hits],
            "total_searched": self.total_searched,
        }


@dataclass
class SaveResult:
    saved: bool
    entry_id: Optional[str] = None
    skip_reason: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "saved": self.saved,
            "entry_id": self.entry_id,
            "skip_reason": self.skip_reason,
        }


# ── Skill ─────────────────────────────────────────────────────────────────────

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
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    approved_at: Optional[str] = None
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
            "created_at": self.created_at,
            "approved_at": self.approved_at,
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
