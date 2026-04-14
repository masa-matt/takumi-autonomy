"""Hermes Bridge — skill_create / skill_update

File-based implementation for PoC.
Skills are stored in runtime/memory/skills/{skill_id}.json.
"""

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from schemas.skill import Skill, SkillStatus, SkillResult

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_SKILLS_DIR = _PROJECT_ROOT / "runtime" / "memory" / "skills"

_STOP_WORDS = {"", "the", "a", "an", "to", "in", "of", "for", "and", "or", "is", "it"}


# ─── Create ───────────────────────────────────────────────────────────────────

def create_skill_draft(job, result) -> SkillResult:
    """Create a skill draft from a completed successful job.

    Skips if the job did not succeed or produced no output.
    """
    if not result or not result.success:
        return SkillResult(created=False, skip_reason="job did not succeed")
    if not result.output:
        return SkillResult(created=False, skip_reason="no output to summarize")

    _SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    skill_id = f"skill-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
    name = _task_to_name(job.task.description)
    trigger_keywords = _extract_keywords(job.task.description)
    procedure_summary = result.output[:1000]

    skill = Skill(
        skill_id=skill_id,
        name=name,
        description=f"Procedure for: {job.task.description}",
        trigger_keywords=trigger_keywords,
        source_job_id=job.job_id,
        source_task=job.task.description,
        procedure_summary=procedure_summary,
    )

    (_SKILLS_DIR / f"{skill_id}.json").write_text(
        json.dumps(skill.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )

    return SkillResult(created=True, skill_id=skill_id)


# ─── List / Get ───────────────────────────────────────────────────────────────

def list_skills(status_filter: Optional[str] = None) -> list[dict]:
    """Return all skills, optionally filtered by status string."""
    _SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    skills = []
    for path in sorted(_SKILLS_DIR.glob("*.json")):
        try:
            skill = json.loads(path.read_text(encoding="utf-8"))
            if status_filter is None or skill.get("status") == status_filter:
                skills.append(skill)
        except Exception:
            continue
    return skills


def get_skill(skill_id: str) -> Optional[dict]:
    path = _SKILLS_DIR / f"{skill_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# ─── Review ───────────────────────────────────────────────────────────────────

def approve_skill(skill_id: str) -> bool:
    """Approve a draft skill. Returns True on success."""
    path = _SKILLS_DIR / f"{skill_id}.json"
    if not path.exists():
        return False
    skill = json.loads(path.read_text(encoding="utf-8"))
    skill["status"] = SkillStatus.APPROVED.value
    skill["approved_at"] = datetime.utcnow().isoformat()
    path.write_text(json.dumps(skill, indent=2, ensure_ascii=False), encoding="utf-8")
    return True


def reject_skill(skill_id: str) -> bool:
    """Mark a skill as deprecated (soft-delete). Returns True on success."""
    path = _SKILLS_DIR / f"{skill_id}.json"
    if not path.exists():
        return False
    skill = json.loads(path.read_text(encoding="utf-8"))
    skill["status"] = SkillStatus.DEPRECATED.value
    path.write_text(json.dumps(skill, indent=2, ensure_ascii=False), encoding="utf-8")
    return True


# ─── Search ───────────────────────────────────────────────────────────────────

def search_skills(query: str, top_k: int = 3) -> list[dict]:
    """Search approved skills by keyword overlap. Returns top_k hits with score."""
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    hits = []
    for skill in list_skills(status_filter=SkillStatus.APPROVED.value):
        text = " ".join([
            skill.get("name", ""),
            skill.get("description", ""),
            " ".join(skill.get("trigger_keywords", [])),
            skill.get("source_task", ""),
        ])
        text_tokens = _tokenize(text)
        overlap = len(query_tokens & text_tokens)
        if overlap > 0:
            score = round(overlap / len(query_tokens), 3)
            hits.append({**skill, "score": score})

    hits.sort(key=lambda s: s["score"], reverse=True)
    return hits[:top_k]


def increment_use_count(skill_id: str) -> None:
    """Increment the use_count for a referenced skill."""
    path = _SKILLS_DIR / f"{skill_id}.json"
    if not path.exists():
        return
    skill = json.loads(path.read_text(encoding="utf-8"))
    skill["use_count"] = skill.get("use_count", 0) + 1
    path.write_text(json.dumps(skill, indent=2, ensure_ascii=False), encoding="utf-8")


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _task_to_name(task: str) -> str:
    words = [w for w in re.split(r"\W+", task.lower()) if w and w not in _STOP_WORDS]
    return "_".join(words[:5])


def _extract_keywords(text: str) -> list[str]:
    tokens = [w for w in re.split(r"\W+", text.lower()) if w and w not in _STOP_WORDS]
    # deduplicate, keep order, cap at 8
    seen: set[str] = set()
    result = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            result.append(t)
        if len(result) >= 8:
            break
    return result


def _tokenize(text: str) -> set[str]:
    return set(re.split(r"\W+", text.lower())) - _STOP_WORDS
