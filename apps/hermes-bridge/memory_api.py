"""Hermes Bridge — memory_write

File-based implementation for PoC.
Writes memory entries to runtime/memory/entries/ after applying save/no-save rules.
"""

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from schemas.memory_entry import MemoryEntry, SaveResult

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_ENTRIES_DIR = _PROJECT_ROOT / "runtime" / "memory" / "entries"

# Output content with these patterns is never saved (sensitive data guard)
_SENSITIVE_PATTERNS = [
    r"\btoken\b",
    r"\bpassword\b",
    r"\bsecret\b",
    r"\bapi.?key\b",
    r"\bcredential",
    r"\bprivate.?key\b",
    r"\bssh.?key\b",
]


# ─── Save / No-Save Rules ─────────────────────────────────────────────────────

def should_save(job, result, approval=None) -> tuple[bool, Optional[str]]:
    """Determine whether to write a memory entry for this job.

    Rules:
      NO-SAVE: job was denied by policy (nothing ran, nothing to learn)
      NO-SAVE: no execution result exists
      NO-SAVE: output contains sensitive patterns
      SAVE:    everything else (success or informative failure)

    Returns:
        (save: bool, skip_reason: str | None)
    """
    # Denied by danger policy — skip
    if (
        approval is not None
        and hasattr(approval, "resolved_by")
        and approval.resolved_by == "policy_deny"
    ):
        return False, "job denied by policy"

    # No result produced
    if result is None:
        return False, "no execution result"

    # Sensitive content guard
    output = result.output or ""
    for pattern in _SENSITIVE_PATTERNS:
        if re.search(pattern, output, re.IGNORECASE):
            return False, f"output matches sensitive pattern: {pattern!r}"

    return True, None


def write_memory(job, result, approval=None) -> SaveResult:
    """Write a memory entry if save rules allow it.

    Returns SaveResult with saved=True and entry_id, or saved=False and skip_reason.
    """
    _ENTRIES_DIR.mkdir(parents=True, exist_ok=True)

    saveable, skip_reason = should_save(job, result, approval)
    if not saveable:
        return SaveResult(saved=False, skip_reason=skip_reason)

    entry_id = f"mem-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
    output_summary = (result.output or "")[:500] if result and result.output else None
    danger_level = (
        approval.danger_level.value if approval and hasattr(approval, "danger_level") else "auto_allow"
    )

    entry = MemoryEntry(
        entry_id=entry_id,
        job_id=job.job_id,
        task=job.task.description,
        status=job.status.value,
        output_summary=output_summary,
        danger_level=danger_level,
        tags=[job.status.value, danger_level],
    )

    path = _ENTRIES_DIR / f"{entry_id}.json"
    path.write_text(
        json.dumps(entry.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )

    return SaveResult(saved=True, entry_id=entry_id)
