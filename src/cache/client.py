"""Redis cache client — get/set with JSON serialization."""

import json
from typing import Any

import redis.asyncio as aioredis
import structlog

from src.config import settings

log = structlog.get_logger()


class CacheClient:
    def __init__(self) -> None:
        self._redis: aioredis.Redis = aioredis.from_url(
            settings.redis_url, decode_responses=True
        )

    async def get(self, key: str) -> Any | None:
        raw = await self._redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        ttl = ttl or settings.redis_ttl_seconds
        await self._redis.set(key, json.dumps(value, default=str), ex=ttl)

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)

    async def close(self) -> None:
        await self._redis.aclose()
