from abc import ABC, abstractmethod


class Executor(ABC):
    """Common interface for all executor implementations.

    Current: AgentSdkExecutor (Anthropic API)
    Future:  ClaudeCodeExecutor (Claude Code Team)
    """

    @abstractmethod
    def run(self, job) -> object:
        """Execute the job. Returns ExecutionResult."""

    @abstractmethod
    def stop(self, job_id: str) -> None:
        """Stop a running job."""
