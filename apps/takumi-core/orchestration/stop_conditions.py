from dataclasses import dataclass
from typing import Optional


@dataclass
class RetryState:
    """Tracks retry attempts for a single job.

    Usage:
        state = RetryState(job_id="job-...", max_retries=3)
        while state.can_retry():
            result = executor.run(job)
            if result.success:
                break
            state.record_failure(result.error)
        stop_reason = state.stop_reason  # None if succeeded
    """

    job_id: str
    max_retries: int = 3
    attempt: int = 0
    stop_reason: Optional[str] = None

    def can_retry(self) -> bool:
        """Returns True if another attempt is allowed."""
        return self.attempt < self.max_retries and self.stop_reason is None

    def record_attempt(self) -> None:
        self.attempt += 1

    def record_failure(self, error: str) -> None:
        """Call after a failed attempt. Sets stop_reason when limit is reached."""
        if self.attempt >= self.max_retries:
            self.stop_reason = (
                f"Stopped after {self.attempt} attempt(s): {error}"
            )

    @property
    def exhausted(self) -> bool:
        return self.stop_reason is not None
