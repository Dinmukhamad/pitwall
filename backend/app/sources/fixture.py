"""Offline fixture adapter.

Serves a bundled sample session from JSON files that mimic OpenF1's raw wire
shape, so the entire product runs end-to-end with zero network access. Flip
``PITWALL_DATA_SOURCE=openf1`` to switch to live data — nothing else changes.

The fixture files live in ``app/sources/fixtures/`` and are produced by
``scripts/generate_fixture.py``.
"""
from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from app.core.logging import get_logger
from app.sources.base import DataSource, RawList

log = get_logger("sources.fixture")

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _parse_dt(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


@lru_cache(maxsize=32)
def _load(name: str) -> tuple:
    path = FIXTURE_DIR / f"{name}.json"
    if not path.exists():
        return tuple()
    with path.open(encoding="utf-8") as fh:
        return tuple(json.load(fh))


def _filter_time(rows: RawList, date_gte, date_lte, key: str = "date") -> RawList:
    if date_gte is None and date_lte is None:
        return list(rows)
    out = []
    for row in rows:
        ts = _parse_dt(row.get(key))
        if ts is None:
            continue
        if date_gte and ts < date_gte:
            continue
        if date_lte and ts > date_lte:
            continue
        out.append(row)
    return out


class FixtureSource(DataSource):
    name = "fixture"

    async def startup(self) -> None:
        sessions = _load("sessions")
        log.info("Fixture source ready — %d session(s) from %s",
                 len(sessions), FIXTURE_DIR)

    def _rows(self, name: str, session_key: int | None = None) -> RawList:
        rows = list(_load(name))
        if session_key is not None:
            rows = [r for r in rows if r.get("session_key") == session_key]
        return rows

    # -- catalog ------------------------------------------------------------
    async def get_sessions(self, *, year=None, country=None, session_name=None) -> RawList:
        rows = self._rows("sessions")
        if year is not None:
            rows = [r for r in rows if r.get("year") == year]
        if country is not None:
            rows = [r for r in rows if r.get("country_name") == country]
        if session_name is not None:
            rows = [r for r in rows if r.get("session_name") == session_name]
        return rows

    async def get_meetings(self, *, year=None) -> RawList:
        rows = self._rows("meetings")
        if year is not None:
            rows = [r for r in rows if r.get("year") == year]
        return rows

    # -- per-session --------------------------------------------------------
    async def get_drivers(self, session_key: int) -> RawList:
        return self._rows("drivers", session_key)

    async def get_position(self, session_key, *, date_gte=None, date_lte=None) -> RawList:
        return _filter_time(self._rows("position", session_key), date_gte, date_lte)

    async def get_intervals(self, session_key, *, date_gte=None, date_lte=None) -> RawList:
        return _filter_time(self._rows("intervals", session_key), date_gte, date_lte)

    async def get_location(self, session_key, *, driver_number=None, date_gte=None, date_lte=None) -> RawList:
        rows = self._rows("location", session_key)
        if driver_number is not None:
            rows = [r for r in rows if r.get("driver_number") == driver_number]
        return _filter_time(rows, date_gte, date_lte)

    async def get_car_data(self, session_key, *, driver_number=None, date_gte=None, date_lte=None) -> RawList:
        rows = self._rows("car_data", session_key)
        if driver_number is not None:
            rows = [r for r in rows if r.get("driver_number") == driver_number]
        return _filter_time(rows, date_gte, date_lte)

    async def get_laps(self, session_key, *, driver_number=None) -> RawList:
        rows = self._rows("laps", session_key)
        if driver_number is not None:
            rows = [r for r in rows if r.get("driver_number") == driver_number]
        return rows

    async def get_stints(self, session_key: int) -> RawList:
        return self._rows("stints", session_key)

    async def get_pit(self, session_key: int) -> RawList:
        return self._rows("pit", session_key)

    async def get_weather(self, session_key, *, date_gte=None, date_lte=None) -> RawList:
        return _filter_time(self._rows("weather", session_key), date_gte, date_lte)

    async def get_race_control(self, session_key: int) -> RawList:
        return self._rows("race_control", session_key)
