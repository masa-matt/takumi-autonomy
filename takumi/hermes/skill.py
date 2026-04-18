"""takumi.hermes.skill — create_skill_draft / search_skills

File-based PoC. Skills stored in runtime/memory/skills/ as JSON.
"""

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from takumi.hermes.models import Skill, SkillResult, SkillStatus

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_SKILLS_DIR = Path(
    os.environ.get("HERMES_SKILLS_DIR", str(_PROJECT_ROOT / "runtime" / "memory" / "skills"))
)

_STOP_WORDS = {"", "the", "a", "an", "to", "in", "of", "for", "and", "or", "is", "it",
               "が", "を", "は", "に", "の", "で", "と", "も", "から", "まで"}


# ── Create ────────────────────────────────────────────────────────────────────

def create_skill_draft(job, output: Optional[str]) -> SkillResult:
    """正常完了した job からスキル草案を作成する。"""
    from takumi.core.job_state import JobStatus
    if job.status != JobStatus.DONE:
        return SkillResult(created=False, skip_reason="job did not succeed")
    if not output:
        return SkillResult(created=False, skip_reason="no output to summarize")

    _SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    skill_id = f"skill-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
    name = _task_to_name(job.task)
    trigger_keywords = _extract_keywords(job.task)

    skill = Skill(
        skill_id=skill_id,
        name=name,
        description=f"Procedure for: {job.task}",
        trigger_keywords=trigger_keywords,
        source_job_id=job.job_id,
        source_task=job.task,
        procedure_summary=output[:1000],
    )

    (_SKILLS_DIR / f"{skill_id}.json").write_text(
        json.dumps(skill.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return SkillResult(created=True, skill_id=skill_id)


# ── Search ────────────────────────────────────────────────────────────────────

def search_skills(query: str, top_k: int = 3) -> list[dict]:
    """承認済みスキルをキーワードマッチで検索する。"""
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    hits = []
    for path in sorted(_SKILLS_DIR.glob("*.json")):
        try:
            skill = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if skill.get("status") != SkillStatus.APPROVED.value:
            continue

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


# ── Internal ──────────────────────────────────────────────────────────────────

def _task_to_name(task: str) -> str:
    words = [w for w in re.split(r"\W+", task.lower()) if w and w not in _STOP_WORDS]
    return "_".join(words[:5])


def _extract_keywords(text: str) -> list[str]:
    tokens = [w for w in re.split(r"\W+", text.lower()) if w and w not in _STOP_WORDS]
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
