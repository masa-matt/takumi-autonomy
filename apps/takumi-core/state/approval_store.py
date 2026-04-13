import json
from pathlib import Path
from typing import Optional

from schemas.approval_request import ApprovalRequest

_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
_APPROVALS_DIR = _PROJECT_ROOT / "runtime" / "approvals"


def save(request: ApprovalRequest) -> str:
    """Persist approval record to runtime/approvals/{job_id}.json.

    Returns the saved file path.
    """
    _APPROVALS_DIR.mkdir(parents=True, exist_ok=True)
    path = _APPROVALS_DIR / f"{request.job_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(request.to_dict(), f, indent=2, ensure_ascii=False)
    return str(path)


def load(job_id: str) -> Optional[dict]:
    """Load approval record for a job. Returns None if not found."""
    path = _APPROVALS_DIR / f"{job_id}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)
