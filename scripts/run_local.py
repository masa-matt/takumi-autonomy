#!/usr/bin/env python3
"""Local CLI harness for CP-01/CP-02 verification.

Usage:
    python scripts/run_local.py --task "your task description"
    python scripts/run_local.py --task "delete config file" --auto-approve
    python scripts/run_local.py --task "flaky task" --max-retries 3

Flags:
    --auto-approve    Auto-approve APPROVAL_REQUIRED tasks (no CLI prompt)
    --max-retries N   Max execution retry attempts (default: 3)

Set ANTHROPIC_API_KEY to use the real Anthropic API; omit for stub mode.
"""

import argparse
import json
import sys
from pathlib import Path

# ─── sys.path setup ──────────────────────────────────────────────────────────
# Must happen before any project imports.
_ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(_ROOT / "packages"))
sys.path.insert(0, str(_ROOT / "apps" / "executor-gateway"))
sys.path.insert(0, str(_ROOT / "apps" / "takumi-core" / "orchestration"))
sys.path.insert(0, str(_ROOT / "apps" / "takumi-core" / "policy"))
sys.path.insert(0, str(_ROOT / "apps" / "takumi-core" / "state"))
# ─────────────────────────────────────────────────────────────────────────────

from job_runner import JobRunner  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Takumi Autonomy — Local Job Runner (CP-01/CP-02)"
    )
    parser.add_argument("--task", required=True, help="Task description to execute")
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        default=False,
        help="Auto-approve APPROVAL_REQUIRED tasks without CLI prompt",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        metavar="N",
        help="Max execution retry attempts (default: 3)",
    )
    args = parser.parse_args()

    print("=== Takumi Autonomy — run_local ===")
    print(f"Task:         {args.task}")
    print(f"Auto-approve: {args.auto_approve}")
    print(f"Max retries:  {args.max_retries}")
    print()

    runner = JobRunner(auto_approve=args.auto_approve, max_retries=args.max_retries)
    job, report_path = runner.run(args.task)

    # ── Report ────────────────────────────────────────────────────────────────
    with open(report_path, encoding="utf-8") as f:
        report = json.load(f)

    print()
    print("=== CP-02 Pass Condition Checks ===")
    approval_path = _ROOT / "runtime" / "approvals" / f"{job.job_id}.json"
    has_approval = approval_path.exists()
    has_stop_reason_field = "stop_reason" in report
    stop_reason = report.get("stop_reason")

    print(f"  [{'✓' if has_approval else '✗'}] approval record saved:    {approval_path}")
    print(f"  [{'✓' if has_stop_reason_field else '✗'}] stop_reason in report:    {stop_reason!r}")
    print(f"  [{'✓' if job.status.value in ('done', 'failed') else '✗'}] job reached terminal state: status={job.status.value}")

    print()
    print("=== Report Contents ===")
    print(json.dumps(report, indent=2, ensure_ascii=False))

    sys.exit(0 if job.status.value == "done" else 1)


if __name__ == "__main__":
    main()
