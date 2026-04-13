#!/usr/bin/env python3
"""Local CLI harness for CP-01 verification.

Usage:
    python scripts/run_local.py --task "your task description"

This runs the full Task → Job → Workspace → Executor → Report pipeline
without requiring Discord. Set ANTHROPIC_API_KEY to use the real API;
omit it to run in stub mode.
"""

import argparse
import json
import sys
from pathlib import Path

# ─── sys.path setup ──────────────────────────────────────────────────────────
# Must happen before any project imports.
_ROOT = Path(__file__).parent.parent

# Shared schemas and utils (packages/schemas/, packages/utils/)
sys.path.insert(0, str(_ROOT / "packages"))

# Executor gateway modules (base, workspace_manager, agent_sdk_executor, execution_result)
sys.path.insert(0, str(_ROOT / "apps" / "executor-gateway"))

# Takumi-core orchestration (job_runner)
sys.path.insert(0, str(_ROOT / "apps" / "takumi-core" / "orchestration"))
# ─────────────────────────────────────────────────────────────────────────────

from job_runner import JobRunner  # noqa: E402 (import after sys.path setup)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Takumi Autonomy — Local Job Runner (CP-01 verification)"
    )
    parser.add_argument("--task", required=True, help="Task description to execute")
    args = parser.parse_args()

    print("=== Takumi Autonomy — run_local ===")
    print(f"Task: {args.task}")
    print()

    runner = JobRunner()
    job, report_path = runner.run(args.task)

    print()
    print("=== CP-01 Pass Condition Checks ===")
    print(f"  [{'✓' if job.job_id else '✗'}] job id issued:       {job.job_id}")
    print(f"  [{'✓' if job.workspace_path else '✗'}] workspace created:   {job.workspace_path}")
    print(f"  [{'✓' if Path(report_path).exists() else '✗'}] report saved:        {report_path}")
    print(f"  [{'✓' if job.status.value in ('done', 'failed') else '✗'}] executor ran once:   status={job.status.value}")

    print()
    print("=== Report Contents ===")
    with open(report_path, encoding="utf-8") as f:
        report = json.load(f)
    print(json.dumps(report, indent=2, ensure_ascii=False))

    sys.exit(0 if job.status.value == "done" else 1)


if __name__ == "__main__":
    main()
