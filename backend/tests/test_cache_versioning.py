"""Кэш не должен переживать смену версии сборки.

Регресс, который это ловит (наблюдался в проде): Redis живёт дольше контейнера,
поэтому после деплоя новый код читал старый закэшированный список пилотов и
геометрию, а свежие данные приходили только по новым ключам — на экране
получалась смесь старых и новых данных.
"""
from __future__ import annotations

import os

os.environ.setdefault("PITWALL_DATA_SOURCE", "fixture")

import pytest  # noqa: E402

from app.cache.cache import Cache  # noqa: E402
from app.core.config import settings  # noqa: E402


@pytest.mark.asyncio
async def test_key_includes_cache_version():
    cache = Cache()
    key = cache._k("drivers:9999")
    assert settings.cache_version in key
    assert key.endswith("drivers:9999")


@pytest.mark.asyncio
async def test_value_from_previous_build_is_not_reused():
    cache = Cache()
    await cache.startup()

    original = settings.cache_version
    try:
        # Сборка A записала данные…
        settings.cache_version = "build-A"
        await cache.set_json("drivers:9999", [{"driver_number": 1}], ttl=60)
        assert await cache.get_json("drivers:9999") is not None

        # …после деплоя сборка B их не видит.
        settings.cache_version = "build-B"
        assert await cache.get_json("drivers:9999") is None

        # А своё пишет и читает нормально.
        await cache.set_json("drivers:9999", [{"driver_number": 2}], ttl=60)
        assert (await cache.get_json("drivers:9999"))[0]["driver_number"] == 2
    finally:
        settings.cache_version = original
        await cache.shutdown()
