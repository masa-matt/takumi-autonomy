"""ClaudeCodeExecutor — drop-in replacement for AgentSdkExecutor.

Uses the `claude` CLI (Claude Code) to execute tasks via:
    claude -p "<task>" --output-format json

Falls back to stub mode when the `claude` binary is not found so that the
full pipeline remains testable without a Claude Code installation.

Swap in from run_local.py:
    runner = JobRunner(executor=ClaudeCodeExecutor(), ...)
"""

import json
import shutil
import subprocess
from pathlib import Path

from base import Executor


class ClaudeCodeExecutor(Executor):
    """Executor backed by the Claude Code CLI (`claude -p`).

    When the `claude` binary is available:
      - runs `claude -p "<task>" --output-format json` inside job.workspace_path
      - parses JSON result from stdout

    When not available (or CLAUDE_CODE_STUB=1):
      - returns a stub ExecutionResult so the pipeline can run in CI/offline

    The interface is identical to AgentSdkExecutor.
    """

    def __init__(self, stub: bool = False):
        self._force_stub = stub
        self._cli_path = shutil.which("claude")

    def run(self, job) -> object:
        if self._force_stub or self._cli_path is None:
            return self._run_stub(job)
        return self._run_real(job)

    def _run_real(self, job) -> object:
        from schemas.execution_result import ExecutionResult

        workspace = Path(job.workspace_path) if job.workspace_path else Path(".")

        cmd = [
            self._cli_path,
            "-p", job.task.description,
            "--output-format", "json",
        ]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(workspace),
                timeout=300,          # 5-minute hard timeout per job
            )
        except subprocess.TimeoutExpired:
            return self._error_result(job, "claude CLI timed out (300s)", mode="claude_code_cli")
        except Exception as exc:
            return self._error_result(job, f"subprocess error: {exc}", mode="claude_code_cli")

        if proc.returncode != 0:
            stderr_snippet = proc.stderr[:500] if proc.stderr else "(no stderr)"
            return self._error_result(
                job,
                f"claude CLI exited {proc.returncode}: {stderr_snippet}",
                mode="claude_code_cli",
            )

        # Parse JSON output
        try:
            data = json.loads(proc.stdout)
            # Claude Code JSON output schema: {result: str, ...} or {error: str}
            if "error" in data:
                return self._error_result(job, data["error"], mode="claude_code_cli")

            output = data.get("result") or data.get("content") or proc.stdout

            return ExecutionResult(
                job_id=job.job_id,
                success=True,
                output=str(output),
                metadata={
                    "mode": "claude_code_cli",
                    "cli_path": self._cli_path,
                    "return_code": proc.returncode,
                },
            )
        except json.JSONDecodeError:
            # Non-JSON output is treated as plain text success
            return ExecutionResult(
                job_id=job.job_id,
                success=True,
                output=proc.stdout,
                metadata={
                    "mode": "claude_code_cli",
                    "cli_path": self._cli_path,
                    "note": "stdout was not JSON — captured as plain text",
                },
            )

    def _run_stub(self, job) -> object:
        from schemas.execution_result import ExecutionResult

        reason = (
            "forced stub mode" if self._force_stub
            else "`claude` CLI not found — install Claude Code or set CLAUDE_CODE_STUB=1"
        )
        return ExecutionResult(
            job_id=job.job_id,
            success=True,
            output=f"[STUB] ClaudeCodeExecutor: {job.task.description}",
            metadata={
                "mode": "claude_code_stub",
                "note": reason,
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
        # Stateless for now — subprocess already exited before this is called
        pass
