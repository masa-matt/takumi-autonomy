import json
from pathlib import Path

# Compute paths relative to this file's location:
# apps/executor-gateway/ → apps/ → project root → runtime/
_PROJECT_ROOT = Path(__file__).parent.parent.parent
WORKSPACES_DIR = _PROJECT_ROOT / "runtime" / "workspaces" / "jobs"
REPORTS_DIR = _PROJECT_ROOT / "runtime" / "reports"


def create_workspace(job_id: str) -> str:
    """Create an isolated workspace directory for a job.

    Creates:
      runtime/workspaces/jobs/{job_id}/artifacts/
      runtime/workspaces/jobs/{job_id}/logs/

    Returns the workspace root path as a string.
    """
    workspace_path = WORKSPACES_DIR / job_id
    (workspace_path / "artifacts").mkdir(parents=True, exist_ok=True)
    (workspace_path / "logs").mkdir(parents=True, exist_ok=True)
    return str(workspace_path)


def save_report(job, result, stop_reason: str = None) -> str:
    """Persist job report to both workspace and runtime/reports/.

    Saves even when result is None (e.g. approval denied before workspace creation).
    stop_reason is set when the job stopped due to retry exhaustion or policy denial.
    Returns the path of the runtime/reports/{job_id}.json file.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    report = {
        "job_id": job.job_id,
        "task": job.task.description,
        "status": job.status.value,
        "stop_reason": stop_reason,
        "workspace_path": job.workspace_path,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "error": job.error,
        "result": result.to_dict() if result is not None else None,
    }

    # 1. Save to runtime/reports/ (global registry)
    report_path = REPORTS_DIR / f"{job.job_id}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # 2. Also save inside the workspace for self-contained auditing
    if job.workspace_path:
        workspace_result = Path(job.workspace_path) / "result.json"
        with open(workspace_result, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

    return str(report_path)
