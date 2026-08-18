"""Live OpenF1 REST adapter.

Thin, defensive wrapper over https://openf1.org. Applies the data-loading
discipline from TZ §5: callers pass time windows and per-driver filters, and
this adapter turns them into OpenF1 query params so we never pull a whole
session's high-frequency streams into memory.

NOTE: OpenF1's field/param names evolve. Keeping them confined to this file is
the whole point of the adapter (R-04).
"""
from __future__ import annotations

import asyncio
from datetime import datetime

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.sources.base import DataSource, RawList

log = get_logger("sources.openf1")


def _iso(dt: datetime) -> str:
    # OpenF1 accepts ISO 8601; normalize to UTC-ish string.
    return dt.isoformat()


class OpenF1Source(DataSource):
    name = "openf1"

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._sem = asyncio.Semaphore(settings.openf1_max_concurrency)

    async def startup(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.openf1_base_url,
            timeout=settings.openf1_timeout_s,
            headers={"Accept": "application/json", "User-Agent": "PitWall/1.0"},
        )
        log.info("OpenF1 source ready (%s)", settings.openf1_base_url)

    async def shutdown(self) -> None:
        if self._client is not None:
            await self._client.aclose()

    async def _get(self, path: str, params: dict) -> RawList:
        assert self._client is not None, "source not started"
        # Drop None params; OpenF1 dislikes empty values.
        clean = {k: v for k, v in params.items() if v is not None}
        async with self._sem:
            r = await self._client.get(path, params=clean)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else [data]

    # -- catalog ------------------------------------------------------------
    async def get_sessions(self, *, year=None, country=None, session_name=None) -> RawList:
        return await self._get("/sessions", {
            "year": year, "country_name": country, "session_name": session_name,
        })

    async def get_meetings(self, *, year=None) -> RawList:
        return await self._get("/meetings", {"year": year})

    # -- per-session --------------------------------------------------------
    async def get_drivers(self, session_key: int) -> RawList:
        return await self._get("/drivers", {"session_key": session_key})

    async def get_position(self, session_key, *, date_gte=None, date_lte=None) -> RawList:
        return await self._get("/position", {
            "session_key": session_key,
            "date>=": _iso(date_gte) if date_gte else None,
            "date<=": _iso(date_lte) if date_lte else None,
        })

    async def get_intervals(self, session_key, *, date_gte=None, date_lte=None) -> RawList:
        return await self._get("/intervals", {
            "session_key": session_key,
            "date>=": _iso(date_gte) if date_gte else None,
            "date<=": _iso(date_lte) if date_lte else None,
        })

    async def get_location(self, session_key, *, driver_number=None, date_gte=None, date_lte=None) -> RawList:
        return await self._get("/location", {
            "session_key": session_key,
            "driver_number": driver_number,
            "date>=": _iso(date_gte) if date_gte else None,
            "date<=": _iso(date_lte) if date_lte else None,
        })

    async def get_car_data(self, session_key, *, driver_number=None, date_gte=None, date_lte=None) -> RawList:
        return await self._get("/car_data", {
            "session_key": session_key,
            "driver_number": driver_number,
            "date>=": _iso(date_gte) if date_gte else None,
            "date<=": _iso(date_lte) if date_lte else None,
        })

    async def get_laps(self, session_key, *, driver_number=None) -> RawList:
        return await self._get("/laps", {
            "session_key": session_key, "driver_number": driver_number,
        })

    async def get_stints(self, session_key: int) -> RawList:
        return await self._get("/stints", {"session_key": session_key})

    async def get_pit(self, session_key: int) -> RawList:
        return await self._get("/pit", {"session_key": session_key})

    async def get_weather(self, session_key, *, date_gte=None, date_lte=None) -> RawList:
        return await self._get("/weather", {
            "session_key": session_key,
            "date>=": _iso(date_gte) if date_gte else None,
            "date<=": _iso(date_lte) if date_lte else None,
        })

    async def get_race_control(self, session_key: int) -> RawList:
        return await self._get("/race_control", {"session_key": session_key})
