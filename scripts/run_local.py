#!/usr/bin/env python3
"""Local CLI harness for CP-01/CP-02/CP-03 verification.

Usage:
    python scripts/run_local.py --task "your task description"
    python scripts/run_local.py --task "delete config file" --auto-approve
    python scripts/run_local.py --task "flaky task" --max-retries 3
    python scripts/run_local.py --metrics   # show MOR/PRR metrics

Flags:
    --auto-approve    Auto-approve APPROVAL_REQUIRED tasks (no CLI prompt)
    --max-retries N   Max execution retry attempts (default: 3)
    --metrics         Print current MOR/PRR metrics and exit

Set ANTHROPIC_API_KEY to use the real Anthropic API; omit for stub mode.
"""

import argparse
import json
import sys
from pathlib import Path

# ─── sys.path setup ──────────────────────────────────────────────────────────
_ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(_ROOT / "packages"))
sys.path.insert(0, str(_ROOT / "apps" / "executor-gateway"))
sys.path.insert(0, str(_ROOT / "apps" / "takumi-core" / "orchestration"))
sys.path.insert(0, str(_ROOT / "apps" / "takumi-core" / "policy"))
sys.path.insert(0, str(_ROOT / "apps" / "takumi-core" / "state"))
sys.path.insert(0, str(_ROOT / "apps" / "takumi-core" / "metrics"))
sys.path.insert(0, str(_ROOT / "apps" / "hermes-bridge"))
# ─────────────────────────────────────────────────────────────────────────────

from job_runner import JobRunner   # noqa: E402
from mor_prr import get_metrics    # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Takumi Autonomy — Local Job Runner (CP-01/CP-02/CP-03)"
    )
    parser.add_argument("--task", help="Task description to execute")
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
    parser.add_argument(
        "--metrics",
        action="store_true",
        default=False,
        help="Print current MOR/PRR metrics and exit",
    )
    args = parser.parse_args()

    if args.metrics:
        m = get_metrics()
        print("=== MOR / PRR Metrics ===")
        print(json.dumps(m, indent=2, ensure_ascii=False))
        sys.exit(0)

    if not args.task:
        parser.error("--task is required (or use --metrics)")

    print("=== Takumi Autonomy — run_local ===")
    print(f"Task:         {args.task}")
    print(f"Auto-approve: {args.auto_approve}")
    print(f"Max retries:  {args.max_retries}")
    print()

    runner = JobRunner(auto_approve=args.auto_approve, max_retries=args.max_retries)
    job, report_path = runner.run(args.task)

    with open(report_path, encoding="utf-8") as f:
        report = json.load(f)

    print()
    print("=== Report Contents ===")
    print(json.dumps(report, indent=2, ensure_ascii=False))

    print()
    print("=== MOR / PRR (cumulative) ===")
    print(json.dumps(get_metrics(), indent=2, ensure_ascii=False))

    sys.exit(0 if job.status.value == "done" else 1)


if __name__ == "__main__":
    main()
