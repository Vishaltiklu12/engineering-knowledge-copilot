from types import SimpleNamespace

import pytest

from app.core.exceptions import RateLimitExceededError
from app.services.rate_limit import InMemoryRateLimitBackend, RateLimiterService


class FakeRequest:
    def __init__(self, host: str = "127.0.0.1") -> None:
        self.headers: dict[str, str] = {}
        self.client = SimpleNamespace(host=host)
        self.state = SimpleNamespace()


def test_rate_limiter_blocks_requests_over_limit_and_resets() -> None:
    now = [1000.0]
    backend = InMemoryRateLimitBackend(time_provider=lambda: now[0])
    service = RateLimiterService(backend=backend)
    request = FakeRequest()

    first = service.enforce_request_limit(request, scope="query", limit=2, window_seconds=60)
    second = service.enforce_request_limit(request, scope="query", limit=2, window_seconds=60)

    assert first.allowed is True
    assert first.remaining == 1
    assert second.allowed is True
    assert second.remaining == 0

    with pytest.raises(RateLimitExceededError):
        service.enforce_request_limit(request, scope="query", limit=2, window_seconds=60)

    now[0] += 61
    reset = service.enforce_request_limit(request, scope="query", limit=2, window_seconds=60)
    assert reset.allowed is True
    assert reset.remaining == 1
