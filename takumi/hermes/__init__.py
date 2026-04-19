"""takumi.hermes — Recall / Save bridge (file-based PoC)

Public API:
  search_sessions(query, top_k=3)   → SearchResult
  search_skills(query, top_k=3)     → list[dict]
  write_memory(job, output, danger) → SaveResult
  create_skill_draft(job, output)   → SkillResult
"""

from takumi.hermes.memory import search_sessions, write_memory, write_chat_memory
from takumi.hermes.skill import create_skill_draft, search_skills

__all__ = [
    "search_sessions",
    "write_memory",
    "write_chat_memory",
    "create_skill_draft",
    "search_skills",
]
