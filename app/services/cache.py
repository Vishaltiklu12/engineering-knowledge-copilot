import json
import logging
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class CacheService:
    def __init__(self) -> None:
        settings = get_settings()
        self.client = Redis.from_url(settings.redis_url, decode_responses=True)
        self.ttl_seconds = settings.query_cache_ttl_seconds

    def get_json(self, key: str) -> dict[str, Any] | None:
        try:
            value = self.client.get(key)
        except RedisError as exc:
            logger.warning("Redis get failed: %s", exc)
            return None
        return json.loads(value) if value else None

    def set_json(self, key: str, value: dict[str, Any]) -> None:
        try:
            self.client.setex(key, self.ttl_seconds, json.dumps(value, default=str))
        except RedisError as exc:
            logger.warning("Redis set failed: %s", exc)
