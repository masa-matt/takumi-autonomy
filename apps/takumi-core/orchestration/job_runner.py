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
from skill_api import search_skills, create_skill_draft, increment_use_count
from mor_prr import (
    record_job_start, record_search, record_write,
    record_skill_create, record_skill_reference,
)


class JobRunner:
    """Orchestrates the full job lifecycle (CP-01 + CP-02 + CP-03 + CP-04).

    Flow:
      1.  Issue job ID + record job start (metrics)
      2.  Recall: session_search + skill_search before any decision (Recall First)
      3.  Classify danger level + evaluate approval
      4.  Save approval record
      5.  If denied → save report (no memory/skill write), return
      6.  Create workspace
      7.  Execute with retry loop (up to max_retries)
      8.  Save memory (write_memory with save/no-save rules)
      9.  Optionally create skill draft (if create_skill=True)
      10. Save report with recall + save + skill audit trail
    """

    def __init__(
        self,
        executor=None,
        auto_approve: bool = False,
        max_retries: int = 3,
        create_skill: bool = False,
    ):
        self.executor = executor or AgentSdkExecutor()
        self.policy = ApprovalPolicy(auto_approve=auto_approve)
        self.max_retries = max_retries
        self.create_skill = create_skill

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

        # ── 2. Recall First (memory entries + approved skills) ─────────────────
        record_search()
        search_result = search_sessions(task_description)
        skill_hits = search_skills(task_description)

        # Increment use_count for referenced skills
        for sh in skill_hits:
            increment_use_count(sh["skill_id"])
            record_skill_reference()

        recall_summary = {
            "called": True,
            "hits_count": len(search_result.hits),
            "total_searched": search_result.total_searched,
            "top_hit_task": search_result.hits[0].task if search_result.hits else None,
            "skill_hits": [
                {"skill_id": s["skill_id"], "name": s["name"], "score": s["score"]}
                for s in skill_hits
            ],
        }
        hit_parts = []
        if search_result.hits:
            hit_parts.append(f"{len(search_result.hits)} memory hit(s)")
        if skill_hits:
            hit_parts.append(f"{len(skill_hits)} skill hit(s)")
        recall_label = ", ".join(hit_parts) if hit_parts else f"no past sessions ({search_result.total_searched} searched)"
        print(f"[{job_id}] Recall         {recall_label}")

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
            report_path = save_report(
                job, result=None,
                stop_reason=approval.reason,
                recall=recall_summary,
                save={"called": False, "saved": False, "skip_reason": "job denied by policy"},
                skill={"called": False, "created": False, "skip_reason": "job denied by policy"},
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

        # ── 8. Optionally create skill draft ──────────────────────────────────
        skill_result_obj = None
        if self.create_skill:
            skill_result_obj = create_skill_draft(job, result)
            record_skill_create(skill_result_obj.created)
            if skill_result_obj.created:
                print(f"[{job_id}] Skill draft    {skill_result_obj.skill_id}")
            else:
                print(f"[{job_id}] Skill skip     {skill_result_obj.skip_reason}")

        # ── 9. Save report ────────────────────────────────────────────────────
        report_path = save_report(
            job, result,
            stop_reason=retry_state.stop_reason,
            recall=recall_summary,
            save=save_result_obj.to_dict(),
            skill=skill_result_obj.to_dict() if skill_result_obj else {"called": False, "created": False, "skip_reason": "not requested"},
        )
        print(f"[{job_id}] Report saved   {report_path}")

        return job, report_path
