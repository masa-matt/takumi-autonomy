from datetime import datetime

from schemas.task import Task, Job, JobStatus
from schemas.execution_result import ExecutionResult
from utils.ids import generate_job_id
from workspace_manager import create_workspace, save_report
from agent_sdk_executor import AgentSdkExecutor
from approval_policy import ApprovalPolicy
from approval_store import save as save_approval
from stop_conditions import RetryState


class JobRunner:
    """Orchestrates the full job lifecycle (CP-01 + CP-02).

    Flow:
      1. Issue job ID
      2. Classify task danger level
      3. Evaluate approval (Auto Allow / Approval Required / Deny)
      4. Save approval record
      5. Create workspace
      6. Execute with retry loop (up to max_retries)
      7. Save report with stop_reason if applicable
    """

    def __init__(self, executor=None, auto_approve: bool = False, max_retries: int = 3):
        self.executor = executor or AgentSdkExecutor()
        self.policy = ApprovalPolicy(auto_approve=auto_approve)
        self.max_retries = max_retries

    def run(self, task_description: str) -> tuple:
        """Run a task end-to-end.

        Returns:
            (Job, report_path: str)
        """
        # ── 1. Issue Job ID ───────────────────────────────────────────────────
        job_id = generate_job_id()
        task = Task(description=task_description)
        job = Job(job_id=job_id, task=task)
        print(f"[{job_id}] Job created    status=PENDING")

        # ── 2-4. Approval gate ────────────────────────────────────────────────
        print(f"[{job_id}] Classifying…   '{task_description[:60]}'")
        approval = self.policy.evaluate(job_id, task_description)
        save_approval(approval)
        print(f"[{job_id}] Approval       danger={approval.danger_level.value}  status={approval.status.value}")

        if not approval.is_allowed:
            job.status = JobStatus.FAILED
            job.error = approval.reason
            job.started_at = datetime.utcnow()
            job.completed_at = datetime.utcnow()
            # No workspace needed for denied jobs
            report_path = save_report(job, result=None, stop_reason=approval.reason)
            print(f"[{job_id}] Report saved   {report_path}")
            return job, report_path

        # ── 5. Create workspace ───────────────────────────────────────────────
        workspace_path = create_workspace(job_id)
        job.workspace_path = workspace_path
        print(f"[{job_id}] Workspace      {workspace_path}")

        # ── 6. Execute with retry loop ────────────────────────────────────────
        job.status = JobStatus.RUNNING
        job.started_at = datetime.utcnow()

        retry_state = RetryState(job_id=job_id, max_retries=self.max_retries)
        result: ExecutionResult = None

        while retry_state.can_retry():
            retry_state.record_attempt()
            attempt_label = (
                f"attempt {retry_state.attempt}/{retry_state.max_retries}"
                if retry_state.max_retries > 1
                else "executing"
            )
            print(f"[{job_id}] {attempt_label}…")

            try:
                result = self.executor.run(job)
            except Exception as exc:
                result = ExecutionResult(job_id=job_id, success=False, error=str(exc))

            if result.success:
                job.status = JobStatus.DONE
                print(f"[{job_id}] Execution      success")
                break
            else:
                print(f"[{job_id}] Execution      FAILED  {result.error}")
                retry_state.record_failure(result.error)

        if not result or not result.success:
            job.status = JobStatus.FAILED
            job.error = result.error if result else "unknown error"

        job.completed_at = datetime.utcnow()

        # ── 7. Save report ────────────────────────────────────────────────────
        report_path = save_report(job, result, stop_reason=retry_state.stop_reason)
        print(f"[{job_id}] Report saved   {report_path}")

        return job, report_path
