from datetime import datetime

# These imports resolve once run_local.py has set up sys.path:
#   packages/          → schemas.*, utils.*
#   apps/executor-gateway/ → workspace_manager, agent_sdk_executor
from schemas.task import Task, Job, JobStatus
from schemas.execution_result import ExecutionResult
from utils.ids import generate_job_id
from workspace_manager import create_workspace, save_report
from agent_sdk_executor import AgentSdkExecutor


class JobRunner:
    """Orchestrates the full job lifecycle for CP-01.

    Flow: create job → create workspace → execute → save report
    Guarantees: report is always saved, even on unexpected failure.
    """

    def __init__(self, executor=None):
        self.executor = executor or AgentSdkExecutor()

    def run(self, task_description: str) -> tuple:
        """Run a task end-to-end.

        Returns:
            (Job, report_path: str)
        """
        # 1. Issue job ID and create Job (PENDING)
        job_id = generate_job_id()
        task = Task(description=task_description)
        job = Job(job_id=job_id, task=task)
        print(f"[{job_id}] Job created  status=PENDING")

        # 2. Create isolated workspace (1 job = 1 workspace)
        workspace_path = create_workspace(job_id)
        job.workspace_path = workspace_path
        print(f"[{job_id}] Workspace    {workspace_path}")

        # 3. Transition to RUNNING
        job.status = JobStatus.RUNNING
        job.started_at = datetime.utcnow()
        print(f"[{job_id}] Executing…")

        # 4. Execute (exactly once)
        result: ExecutionResult = None
        try:
            result = self.executor.run(job)
            if result.success:
                job.status = JobStatus.DONE
                print(f"[{job_id}] Execution    success")
            else:
                job.status = JobStatus.FAILED
                job.error = result.error
                print(f"[{job_id}] Execution    FAILED  {result.error}")
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error = str(exc)
            result = ExecutionResult(job_id=job_id, success=False, error=str(exc))
            print(f"[{job_id}] Unexpected error: {exc}")
        finally:
            job.completed_at = datetime.utcnow()

        # 5. Save report (always — CP pass condition)
        report_path = save_report(job, result)
        print(f"[{job_id}] Report saved {report_path}")

        return job, report_path
