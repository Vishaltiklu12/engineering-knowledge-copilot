import logging
import time
from dataclasses import dataclass
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    attempts: int = 3
    delay_seconds: float = 0.25
    backoff_multiplier: float = 2.0

    def __post_init__(self) -> None:
        if self.attempts < 1:
            raise ValueError("Retry attempts must be at least 1.")
        if self.delay_seconds < 0:
            raise ValueError("Retry delay must be non-negative.")
        if self.backoff_multiplier < 1:
            raise ValueError("Backoff multiplier must be at least 1.")


class RetryService:
    def __init__(self, sleeper: Callable[[float], None] | None = None) -> None:
        self._sleeper = sleeper or time.sleep

    def run(
        self,
        operation: Callable[[], T],
        *,
        retryable_exceptions: tuple[type[BaseException], ...],
        policy: RetryPolicy,
        operation_name: str,
    ) -> T:
        delay_seconds = policy.delay_seconds

        for attempt in range(1, policy.attempts + 1):
            try:
                return operation()
            except retryable_exceptions as exc:
                if attempt >= policy.attempts:
                    raise

                logger.warning(
                    "Retrying %s after %s on attempt %s/%s.",
                    operation_name,
                    type(exc).__name__,
                    attempt,
                    policy.attempts,
                )
                if delay_seconds > 0:
                    self._sleeper(delay_seconds)
                delay_seconds *= policy.backoff_multiplier

        raise RuntimeError("Retry loop exited unexpectedly.")
