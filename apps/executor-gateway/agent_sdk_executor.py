import os

from base import Executor


class AgentSdkExecutor(Executor):
    """Executor backed by the Anthropic API (Agent SDK path).

    When ANTHROPIC_API_KEY is set, calls the real API.
    When not set, falls back to stub mode so the pipeline can be tested
    without credentials.

    Future replacement: ClaudeCodeExecutor (Claude Code Team) — same interface.
    """

    def __init__(self):
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")

    def run(self, job) -> object:
        if self.api_key:
            return self._run_real(job)
        return self._run_stub(job)

    def _run_real(self, job) -> object:
        # Import lazily so the package is optional in stub mode
        try:
            import anthropic
        except ImportError:
            return self._error_result(
                job,
                "anthropic package not installed — run: pip install anthropic",
                mode="anthropic_api",
            )

        from schemas.execution_result import ExecutionResult

        try:
            client = anthropic.Anthropic(api_key=self.api_key)
            message = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=1024,
                messages=[{"role": "user", "content": job.task.description}],
            )
            output = message.content[0].text if message.content else ""
            usage = {}
            if hasattr(message, "usage") and message.usage:
                usage = {
                    "input_tokens": message.usage.input_tokens,
                    "output_tokens": message.usage.output_tokens,
                }
            return ExecutionResult(
                job_id=job.job_id,
                success=True,
                output=output,
                metadata={"mode": "anthropic_api", "model": message.model, "usage": usage},
            )
        except Exception as exc:
            return self._error_result(job, str(exc), mode="anthropic_api")

    def _run_stub(self, job) -> object:
        from schemas.execution_result import ExecutionResult

        return ExecutionResult(
            job_id=job.job_id,
            success=True,
            output=f"[STUB] Task received and processed: {job.task.description}",
            metadata={
                "mode": "stub",
                "note": "Set ANTHROPIC_API_KEY env var to enable real API execution",
            },
        )

    def _error_result(self, job, message: str, mode: str) -> object:
        from schemas.execution_result import ExecutionResult

        return ExecutionResult(
            job_id=job.job_id,
            success=False,
            error=message,
            metadata={"mode": mode},
        )

    def stop(self, job_id: str) -> None:
        # Stateless for now; CP-02 will add cancellation support
        pass
