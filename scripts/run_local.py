#!/usr/bin/env python3
"""Local CLI harness for CP-01 through CP-05 verification.

Usage:
    python scripts/run_local.py --task "description"
    python scripts/run_local.py --task "description" --skill        # create skill draft after run
    python scripts/run_local.py --task "description" --auto-approve
    python scripts/run_local.py --task "description" --max-retries 2
    python scripts/run_local.py --task "description" --executor claude-code  # use Claude Code CLI
    python scripts/run_local.py --skill-review                      # review pending skill drafts
    python scripts/run_local.py --metrics                           # show MOR/PRR/PCR

Executor options:
    --executor agent-sdk    (default) Anthropic API direct — requires ANTHROPIC_API_KEY
    --executor claude-code  Claude Code CLI — requires `claude` binary and auth
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

from job_runner import JobRunner          # noqa: E402
from mor_prr import get_metrics           # noqa: E402
from skill_api import list_skills, approve_skill, reject_skill  # noqa: E402


def _build_executor(executor_name: str):
    """Return an Executor instance for the given name."""
    if executor_name == "claude-code":
        from claude_code_executor import ClaudeCodeExecutor
        return ClaudeCodeExecutor()
    # Default: agent-sdk
    from agent_sdk_executor import AgentSdkExecutor
    return AgentSdkExecutor()


def cmd_run(args) -> int:
    executor_label = args.executor or "agent-sdk"
    print("=== Takumi Autonomy — run_local ===")
    print(f"Task:         {args.task}")
    print(f"Executor:     {executor_label}")
    print(f"Auto-approve: {args.auto_approve}")
    print(f"Max retries:  {args.max_retries}")
    print(f"Create skill: {args.skill}")
    print()

    runner = JobRunner(
        executor=_build_executor(executor_label),
        auto_approve=args.auto_approve,
        max_retries=args.max_retries,
        create_skill=args.skill,
    )
    job, report_path = runner.run(args.task)

    with open(report_path, encoding="utf-8") as f:
        report = json.load(f)

    print()
    print("=== Report Contents ===")
    print(json.dumps(report, indent=2, ensure_ascii=False))

    print()
    print("=== MOR / PRR / PCR (cumulative) ===")
    print(json.dumps(get_metrics(), indent=2, ensure_ascii=False))

    return 0 if job.status.value == "done" else 1


def cmd_skill_review() -> int:
    """Interactive CLI review of pending skill drafts."""
    drafts = list_skills(status_filter="draft")
    if not drafts:
        print("No pending skill drafts.")
        return 0

    print(f"=== Skill Review — {len(drafts)} pending draft(s) ===\n")
    approved = rejected = 0

    for skill in drafts:
        print(f"Skill ID:  {skill['skill_id']}")
        print(f"Name:      {skill['name']}")
        print(f"Source:    {skill['source_task']}")
        print(f"Keywords:  {', '.join(skill['trigger_keywords'])}")
        print(f"Summary:   {(skill.get('procedure_summary') or '')[:120]}…")
        print(f"Created:   {skill['created_at']}")
        print()

        answer = input("  [a]pprove / [r]eject / [s]kip? ").strip().lower()
        if answer == "a":
            approve_skill(skill["skill_id"])
            from mor_prr import record_skill_approve
            record_skill_approve()
            print(f"  ✓ Approved: {skill['skill_id']}\n")
            approved += 1
        elif answer == "r":
            reject_skill(skill["skill_id"])
            print(f"  ✗ Rejected: {skill['skill_id']}\n")
            rejected += 1
        else:
            print(f"  — Skipped\n")

    print(f"Review done — approved={approved} rejected={rejected}")
    return 0


def cmd_metrics() -> int:
    m = get_metrics()
    print("=== MOR / PRR / PCR Metrics ===")
    print(json.dumps(m, indent=2, ensure_ascii=False))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Takumi Autonomy — Local Job Runner (CP-01 through CP-04)"
    )
    parser.add_argument("--task", help="Task description to execute")
    parser.add_argument(
        "--executor",
        choices=["agent-sdk", "claude-code"],
        default="agent-sdk",
        help="Executor backend: agent-sdk (default) or claude-code",
    )
    parser.add_argument("--auto-approve", action="store_true", default=False,
                        help="Auto-approve APPROVAL_REQUIRED tasks")
    parser.add_argument("--max-retries", type=int, default=3, metavar="N",
                        help="Max execution retry attempts (default: 3)")
    parser.add_argument("--skill", action="store_true", default=False,
                        help="Create a skill draft after successful execution")
    parser.add_argument("--skill-review", action="store_true", default=False,
                        help="Interactively review and approve pending skill drafts")
    parser.add_argument("--metrics", action="store_true", default=False,
                        help="Print current MOR/PRR/PCR metrics and exit")
    args = parser.parse_args()

    if args.metrics:
        sys.exit(cmd_metrics())
    elif args.skill_review:
        sys.exit(cmd_skill_review())
    elif args.task:
        sys.exit(cmd_run(args))
    else:
        parser.error("Provide --task, --skill-review, or --metrics")


if __name__ == "__main__":
    main()
