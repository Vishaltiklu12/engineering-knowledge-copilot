import pytest

from app.services.retry import RetryPolicy, RetryService


def test_retry_service_retries_until_success() -> None:
    attempts = {"count": 0}
    sleep_calls: list[float] = []

    def operation() -> str:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("temporary failure")
        return "ok"

    result = RetryService(sleeper=sleep_calls.append).run(
        operation,
        retryable_exceptions=(RuntimeError,),
        policy=RetryPolicy(attempts=3, delay_seconds=0.1, backoff_multiplier=2.0),
        operation_name="flaky operation",
    )

    assert result == "ok"
    assert attempts["count"] == 3
    assert sleep_calls == [0.1, 0.2]


def test_retry_service_raises_after_last_attempt() -> None:
    attempts = {"count": 0}

    def operation() -> None:
        attempts["count"] += 1
        raise RuntimeError("still failing")

    with pytest.raises(RuntimeError):
        RetryService(sleeper=lambda _: None).run(
            operation,
            retryable_exceptions=(RuntimeError,),
            policy=RetryPolicy(attempts=3, delay_seconds=0.0, backoff_multiplier=2.0),
            operation_name="always failing operation",
        )

    assert attempts["count"] == 3
