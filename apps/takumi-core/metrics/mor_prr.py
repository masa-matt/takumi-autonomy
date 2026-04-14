"""MOR / PRR / PCR metrics tracker.

Persists running counters to runtime/memory/metrics.json.

MOR (Memory Operation Rate)    = memory_write_saves / total_jobs
PRR (Past Reference Rate)      = session_search_calls / total_jobs
PCR (Proceduralization Rate)   = skill_creates / total_jobs
"""

import json
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
_METRICS_FILE = _PROJECT_ROOT / "runtime" / "memory" / "metrics.json"

_DEFAULTS: dict = {
    "total_jobs": 0,
    "session_search_calls": 0,
    "memory_write_calls": 0,
    "memory_write_saves": 0,
    "memory_write_skips": 0,
    "skill_creates": 0,
    "skill_approvals": 0,
    "skill_references": 0,
}


def _load() -> dict:
    if _METRICS_FILE.exists():
        data = json.loads(_METRICS_FILE.read_text(encoding="utf-8"))
        # Back-fill any keys added after initial creation
        for k, v in _DEFAULTS.items():
            data.setdefault(k, v)
        return data
    return dict(_DEFAULTS)


def _persist(metrics: dict) -> None:
    _METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _METRICS_FILE.write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def record_job_start() -> None:
    m = _load()
    m["total_jobs"] += 1
    _persist(m)


def record_search() -> None:
    m = _load()
    m["session_search_calls"] += 1
    _persist(m)


def record_write(saved: bool) -> None:
    m = _load()
    m["memory_write_calls"] += 1
    if saved:
        m["memory_write_saves"] += 1
    else:
        m["memory_write_skips"] += 1
    _persist(m)


def record_skill_create(created: bool) -> None:
    if not created:
        return
    m = _load()
    m["skill_creates"] += 1
    _persist(m)


def record_skill_approve() -> None:
    m = _load()
    m["skill_approvals"] += 1
    _persist(m)


def record_skill_reference() -> None:
    m = _load()
    m["skill_references"] += 1
    _persist(m)


def get_metrics() -> dict:
    m = _load()
    total = m["total_jobs"] or 1  # avoid div-by-zero on first run
    return {
        **m,
        "MOR": round(m["memory_write_saves"] / total, 3),
        "PRR": round(m["session_search_calls"] / total, 3),
        "PCR": round(m["skill_creates"] / total, 3),
    }
