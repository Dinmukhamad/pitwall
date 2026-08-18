"""Сервис раздела «Сезон»: источник + кэш + honest-состояние ошибки.

Важно: если Jolpica недоступна, возвращается пустой обзор с заполненным полем
`error`, а не выдуманные цифры — фронтенд показывает состояние ошибки с кнопкой
повтора. Придумывать положение в чемпионате нельзя.
"""
from __future__ import annotations

from app.cache.cache import cache
from app.core.config import settings
from app.core.logging import get_logger
from app.domain.season import SeasonOverview
from app.season.jolpica import JolpicaClient

log = get_logger("season.service")

CACHE_KEY = "season:current"


class SeasonService:
    def __init__(self) -> None:
        self.client = JolpicaClient()

    async def startup(self) -> None:
        await self.client.startup()

    async def shutdown(self) -> None:
        await self.client.shutdown()

    async def get_overview(self, force: bool = False) -> SeasonOverview:
        if not force:
            cached = await cache.get_json(CACHE_KEY)
            if cached is not None:
                return SeasonOverview(**cached)

        try:
            overview = await self.client.fetch_overview()
        except Exception as exc:  # noqa: BLE001 — наружу отдаём состояние, не 500
            log.warning("Jolpica недоступна: %s", exc)
            return SeasonOverview(
                season="",
                error=f"Не удалось получить данные сезона: {type(exc).__name__}",
            )

        await cache.set_json(CACHE_KEY, overview.model_dump(), ttl=settings.season_ttl_s)
        log.info("Сезон %s: %d этапов, %d пилотов, %d команд",
                 overview.season, overview.races_total,
                 len(overview.drivers), len(overview.constructors))
        return overview


season_service = SeasonService()
