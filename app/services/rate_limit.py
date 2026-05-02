import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from threading import Lock

from fastapi import Request
from redis import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.core.exceptions import RateLimitExceededError
from app.services.metrics import record_rate_limit_exceeded

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_in_seconds: int


class RateLimitBackend(ABC):
    @abstractmethod
    def increment(self, key: str, window_seconds: int) -> tuple[int, int]:
        raise NotImplementedError


class RedisRateLimitBackend(RateLimitBackend):
    def __init__(self, client: Redis) -> None:
        self.client = client

    def increment(self, key: str, window_seconds: int) -> tuple[int, int]:
        pipeline = self.client.pipeline()
        pipeline.incr(key)
        pipeline.expire(key, window_seconds, nx=True)
        pipeline.ttl(key)
        count, _, ttl_seconds = pipeline.execute()
        reset_in_seconds = window_seconds if ttl_seconds is None or ttl_seconds < 0 else int(ttl_seconds)
        return int(count), reset_in_seconds


class InMemoryRateLimitBackend(RateLimitBackend):
    def __init__(self, time_provider=None) -> None:
        self.time_provider = time_provider or time.time
        self._lock = Lock()
        self._buckets: dict[str, tuple[int, float]] = {}

    def increment(self, key: str, window_seconds: int) -> tuple[int, int]:
        now = float(self.time_provider())
        with self._lock:
            count, expires_at = self._buckets.get(key, (0, now + window_seconds))
            if expires_at <= now:
                count = 0
                expires_at = now + window_seconds

            count += 1
            self._buckets[key] = (count, expires_at)

        reset_in_seconds = max(0, int(expires_at - now))
        return count, reset_in_seconds


_in_memory_backend = InMemoryRateLimitBackend()


class RateLimiterService:
    def __init__(self, backend: RateLimitBackend | None = None) -> None:
        self.backend = backend or self._build_backend()

    def _build_backend(self) -> RateLimitBackend:
        settings = get_settings()
        try:
            client = Redis.from_url(settings.redis_url, decode_responses=True)
            client.ping()
            return RedisRateLimitBackend(client)
        except RedisError as exc:
            logger.warning("Falling back to in-memory rate limiting: %s", exc)
            return _in_memory_backend

    @staticmethod
    def build_key(scope: str, identifier: str) -> str:
        return f"rate_limit:{scope}:{identifier}"

    @staticmethod
    def get_identifier(request: Request) -> str:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        if request.client and request.client.host:
            return request.client.host
        return "anonymous"

    def check(self, *, scope: str, identifier: str, limit: int, window_seconds: int) -> RateLimitResult:
        count, reset_in_seconds = self.backend.increment(
            self.build_key(scope=scope, identifier=identifier),
            window_seconds=window_seconds,
        )
        return RateLimitResult(
            allowed=count <= limit,
            limit=limit,
            remaining=max(0, limit - count),
            reset_in_seconds=reset_in_seconds,
        )

    def enforce_request_limit(self, request: Request, *, scope: str, limit: int, window_seconds: int) -> RateLimitResult:
        result = self.check(
            scope=scope,
            identifier=self.get_identifier(request),
            limit=limit,
            window_seconds=window_seconds,
        )
        request.state.rate_limit = result
        if not result.allowed:
            record_rate_limit_exceeded(scope)
            raise RateLimitExceededError(
                "Rate limit exceeded.",
                details={
                    "scope": scope,
                    "limit": limit,
                    "window_seconds": window_seconds,
                },
                retry_after_seconds=result.reset_in_seconds,
            )
        return result
