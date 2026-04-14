from datetime import datetime

from schemas.task import Task, Job, JobStatus
from schemas.execution_result import ExecutionResult
from utils.ids import generate_job_id
from workspace_manager import create_workspace, save_report
from agent_sdk_executor import AgentSdkExecutor
from approval_policy import ApprovalPolicy
from approval_store import save as save_approval
from stop_conditions import RetryState
from session_search_api import search_sessions
from memory_api import write_memory
from mor_prr import record_job_start, record_search, record_write


class JobRunner:
    """Orchestrates the full job lifecycle (CP-01 + CP-02 + CP-03).

    Flow:
      1.  Issue job ID + record job start (metrics)
      2.  Recall: session_search before any decision (Recall First rule)
      3.  Classify danger level + evaluate approval
      4.  Save approval record
      5.  If denied → save report (no memory write), return
      6.  Create workspace
      7.  Execute with retry loop (up to max_retries)
      8.  Save: write_memory after execution (with save/no-save rules)
      9.  Save report with recall + save audit trail
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
        record_job_start()
        print(f"[{job_id}] Job created    status=PENDING")

        # ── 2. Recall First ───────────────────────────────────────────────────
        record_search()
        search_result = search_sessions(task_description)
        recall_summary = {
            "called": True,
            "hits_count": len(search_result.hits),
            "total_searched": search_result.total_searched,
            "top_hit_task": search_result.hits[0].task if search_result.hits else None,
        }
        if search_result.hits:
            print(f"[{job_id}] Recall         {len(search_result.hits)} hit(s) / {search_result.total_searched} searched")
        else:
            print(f"[{job_id}] Recall         no past sessions ({search_result.total_searched} searched)")

        # ── 3-4. Approval gate ────────────────────────────────────────────────
        print(f"[{job_id}] Classifying…   '{task_description[:60]}'")
        approval = self.policy.evaluate(job_id, task_description)
        save_approval(approval)
        print(f"[{job_id}] Approval       danger={approval.danger_level.value}  status={approval.status.value}")

        if not approval.is_allowed:
            job.status = JobStatus.FAILED
            job.error = approval.reason
            job.started_at = datetime.utcnow()
            job.completed_at = datetime.utcnow()
            save_result_obj = None  # denied jobs are never saved
            report_path = save_report(
                job, result=None,
                stop_reason=approval.reason,
                recall=recall_summary,
                save={"called": False, "saved": False, "skip_reason": "job denied by policy"},
            )
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

        # ── 7. Save memory ────────────────────────────────────────────────────
        save_result_obj = write_memory(job, result, approval=approval)
        record_write(save_result_obj.saved)
        if save_result_obj.saved:
            print(f"[{job_id}] Memory saved   {save_result_obj.entry_id}")
        else:
            print(f"[{job_id}] Memory skip    {save_result_obj.skip_reason}")

        # ── 8. Save report ────────────────────────────────────────────────────
        report_path = save_report(
            job, result,
            stop_reason=retry_state.stop_reason,
            recall=recall_summary,
            save=save_result_obj.to_dict(),
        )
        print(f"[{job_id}] Report saved   {report_path}")

        return job, report_path
