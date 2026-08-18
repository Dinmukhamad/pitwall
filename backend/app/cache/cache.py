"""Cache abstraction: Redis when configured & reachable, else in-process LRU.

The rest of the app calls ``cache.get_json`` / ``cache.set_json`` and never
cares which backend is live. This lets the product satisfy TZ §5 (cache
immutable replay data, throttle API load) without *requiring* Redis to boot —
important for local dev and the sandbox.
"""
from __future__ import annotations

import json
import time
from collections import OrderedDict
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("cache")


class _MemoryLRU:
    def __init__(self, capacity: int = 512) -> None:
        self._data: OrderedDict[str, tuple[float, str]] = OrderedDict()
        self._cap = capacity

    def get(self, key: str) -> str | None:
        item = self._data.get(key)
        if item is None:
            return None
        expires, value = item
        if expires and expires < time.monotonic():
            self._data.pop(key, None)
            return None
        self._data.move_to_end(key)
        return value

    def set(self, key: str, value: str, ttl: int) -> None:
        expires = time.monotonic() + ttl if ttl else 0.0
        self._data[key] = (expires, value)
        self._data.move_to_end(key)
        while len(self._data) > self._cap:
            self._data.popitem(last=False)


class Cache:
    def __init__(self) -> None:
        self._redis = None
        self._mem = _MemoryLRU()
        self.backend = "memory"

    async def startup(self) -> None:
        if not settings.redis_url:
            log.info("Cache: in-memory (no PITWALL_REDIS_URL set)")
            return
        try:
            import redis.asyncio as aioredis  # lazy import

            self._redis = aioredis.from_url(
                settings.redis_url, encoding="utf-8", decode_responses=True
            )
            await self._redis.ping()
            self.backend = "redis"
            log.info("Cache: Redis at %s", settings.redis_url)
        except Exception as exc:  # noqa: BLE001 — degrade, never crash
            log.warning("Cache: Redis unavailable (%s); using in-memory", exc)
            self._redis = None

    async def shutdown(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()

    async def get_json(self, key: str) -> Any | None:
        try:
            raw = await self._redis.get(key) if self._redis else self._mem.get(key)
        except Exception as exc:  # noqa: BLE001
            log.warning("Cache get failed (%s); memory fallback", exc)
            raw = self._mem.get(key)
        return json.loads(raw) if raw else None

    async def set_json(self, key: str, value: Any, ttl: int | None = None) -> None:
        ttl = settings.cache_ttl_s if ttl is None else ttl
        raw = json.dumps(value, default=str)
        try:
            if self._redis:
                await self._redis.set(key, raw, ex=ttl or None)
            else:
                self._mem.set(key, raw, ttl)
        except Exception as exc:  # noqa: BLE001
            log.warning("Cache set failed (%s); memory fallback", exc)
            self._mem.set(key, raw, ttl)


cache = Cache()
