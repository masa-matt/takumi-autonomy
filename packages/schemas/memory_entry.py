from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class MemoryEntry:
    entry_id: str
    job_id: str
    task: str
    status: str          # "done" | "failed"
    output_summary: Optional[str]
    danger_level: str    # mirrors DangerLevel.value
    saved_at: datetime = field(default_factory=datetime.utcnow)
    tags: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "job_id": self.job_id,
            "task": self.task,
            "status": self.status,
            "output_summary": self.output_summary,
            "danger_level": self.danger_level,
            "saved_at": self.saved_at.isoformat(),
            "tags": self.tags,
        }


@dataclass
class SearchHit:
    entry_id: str
    job_id: str
    task: str
    output_summary: Optional[str]
    saved_at: str
    score: float   # keyword overlap 0.0–1.0

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
    hits: list     # list[SearchHit]
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
