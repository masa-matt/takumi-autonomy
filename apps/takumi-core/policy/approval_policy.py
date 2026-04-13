from datetime import datetime

from schemas.approval_request import ApprovalRequest, ApprovalStatus, DangerLevel
from danger_classifier import classify


class ApprovalPolicy:
    """Evaluates whether a job is allowed to proceed.

    auto_approve=True:
        APPROVAL_REQUIRED tasks are auto-approved (--auto-approve flag / testing).
    auto_approve=False:
        APPROVAL_REQUIRED tasks prompt for CLI [y/n] input.

    DENY-level tasks are always rejected regardless of auto_approve.
    """

    def __init__(self, auto_approve: bool = False):
        self.auto_approve = auto_approve

    def evaluate(self, job_id: str, task_description: str) -> ApprovalRequest:
        danger_level, reason = classify(task_description)

        request = ApprovalRequest(
            job_id=job_id,
            task_description=task_description,
            danger_level=danger_level,
            reason=reason,
        )

        if danger_level == DangerLevel.AUTO_ALLOW:
            request.status = ApprovalStatus.AUTO_APPROVED
            request.resolved_at = datetime.utcnow()
            request.resolved_by = "policy_auto_allow"

        elif danger_level == DangerLevel.DENY:
            request.status = ApprovalStatus.DENIED
            request.resolved_at = datetime.utcnow()
            request.resolved_by = "policy_deny"
            print(f"  [DENIED] {reason}")

        elif danger_level == DangerLevel.APPROVAL_REQUIRED:
            if self.auto_approve:
                request.status = ApprovalStatus.APPROVED
                request.resolved_at = datetime.utcnow()
                request.resolved_by = "auto"
                print(f"  [AUTO-APPROVED] {reason}")
            else:
                print(f"\n  [APPROVAL REQUIRED] {task_description}")
                print(f"  Reason: {reason}")
                answer = input("  Approve? [y/n]: ").strip().lower()
                if answer == "y":
                    request.status = ApprovalStatus.APPROVED
                    request.resolved_at = datetime.utcnow()
                    request.resolved_by = "human"
                else:
                    request.status = ApprovalStatus.DENIED
                    request.resolved_at = datetime.utcnow()
                    request.resolved_by = "human"

        return request
