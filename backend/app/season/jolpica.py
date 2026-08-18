"""Адаптер Jolpica-F1 (преемник Ergast) — календарь и зачёты (ТЗ §2.2).

Схема Ergast вложенная (`MRData.StandingsTable.StandingsLists[0]...`), поэтому
разбор изолирован здесь: наружу уходят только модели из `domain.season`.

Запросы идут с сервера, а не из браузера — никаких CORS-прокси, которые в
прототипе оказались ненадёжными.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.season import (
    ConstructorStanding, DriverStanding, RaceEvent, RaceResult, RaceResultRow,
    SeasonOverview,
)
from app.season.teams import team_colour

log = get_logger("season.jolpica")


def _num(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value, default=0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_calendar(payload: dict, now: datetime) -> tuple[list[RaceEvent], str]:
    """`/current.json` -> список этапов + год сезона."""
    table = (payload or {}).get("MRData", {}).get("RaceTable", {})
    season = str(table.get("season") or "")
    events: list[RaceEvent] = []

    for r in table.get("Races", []) or []:
        circuit = r.get("Circuit", {}) or {}
        location = circuit.get("Location", {}) or {}
        # Время в Ergast отдельным полем; если его нет — считаем концом суток,
        # иначе гонка «сегодня» уже выглядела бы прошедшей.
        raw = f"{r.get('date')}T{r.get('time') or '23:59:59Z'}"
        try:
            when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            when = None
        events.append(RaceEvent(
            round=_int(r.get("round")),
            name=r.get("raceName") or "",
            circuit=circuit.get("circuitName"),
            country=location.get("country"),
            locality=location.get("locality"),
            date=when,
            is_past=bool(when and when < now),
        ))

    events.sort(key=lambda e: e.round)
    nxt = next((e for e in events if not e.is_past), None)
    if nxt is not None:
        nxt.is_next = True
    return events, season


def parse_driver_standings(payload: dict) -> list[DriverStanding]:
    lists = (payload or {}).get("MRData", {}).get("StandingsTable", {}).get("StandingsLists", [])
    rows = (lists[0] if lists else {}).get("DriverStandings", []) or []
    out: list[DriverStanding] = []
    for row in rows:
        drv = row.get("Driver", {}) or {}
        teams = row.get("Constructors") or [{}]
        team = teams[-1] if teams else {}       # последняя = актуальная команда
        family = drv.get("familyName") or ""
        out.append(DriverStanding(
            position=_int(row.get("position")),
            code=drv.get("code") or family[:3].upper() or "UNK",
            full_name=" ".join(x for x in (drv.get("givenName"), family) if x) or None,
            team_name=team.get("name"),
            team_colour=team_colour(team.get("constructorId"), team.get("name")),
            points=_num(row.get("points")),
            wins=_int(row.get("wins")),
        ))
    return out


def parse_constructor_standings(payload: dict) -> list[ConstructorStanding]:
    lists = (payload or {}).get("MRData", {}).get("StandingsTable", {}).get("StandingsLists", [])
    rows = (lists[0] if lists else {}).get("ConstructorStandings", []) or []
    out: list[ConstructorStanding] = []
    for row in rows:
        team = row.get("Constructor", {}) or {}
        out.append(ConstructorStanding(
            position=_int(row.get("position")),
            name=team.get("name") or "—",
            team_colour=team_colour(team.get("constructorId"), team.get("name")),
            points=_num(row.get("points")),
            wins=_int(row.get("wins")),
        ))
    return out


def parse_race_result(payload: dict) -> RaceResult:
    """`/{year}/{round}/results.json` -> протокол одного этапа."""
    table = (payload or {}).get("MRData", {}).get("RaceTable", {})
    races = table.get("Races") or []
    if not races:
        return RaceResult(error="Результаты этапа ещё не опубликованы")

    race = races[0]
    circuit = race.get("Circuit", {}) or {}
    location = circuit.get("Location", {}) or {}
    try:
        when = datetime.fromisoformat(
            f"{race.get('date')}T{race.get('time') or '00:00:00Z'}".replace("Z", "+00:00"))
    except (ValueError, TypeError):
        when = None

    rows: list[RaceResultRow] = []
    for r in race.get("Results", []) or []:
        drv = r.get("Driver", {}) or {}
        team = r.get("Constructor", {}) or {}
        fl = r.get("FastestLap") or {}
        fl_time = (fl.get("Time") or {}).get("time")
        # rank == "1" помечает быстрейший круг гонки (фиолетовый в таблице)
        is_fl = str(fl.get("rank") or "") == "1"

        pos_text = str(r.get("positionText") or r.get("position") or "")
        position = _int(r.get("position"), 0) or None
        # У сошедших positionText — буква; позиция как число смысла не имеет.
        if not pos_text.isdigit():
            position = None

        rows.append(RaceResultRow(
            position=position,
            position_text=pos_text,
            driver_code=drv.get("code") or (drv.get("familyName") or "")[:3].upper() or "UNK",
            driver_name=" ".join(x for x in (drv.get("givenName"), drv.get("familyName")) if x) or None,
            driver_number=_int(r.get("number"), 0) or None,
            team_name=team.get("name"),
            team_colour=team_colour(team.get("constructorId"), team.get("name")),
            grid=_int(r.get("grid"), 0) or None,
            laps=_int(r.get("laps"), 0) or None,
            status=r.get("status"),
            time=(r.get("Time") or {}).get("time"),
            points=_num(r.get("points")),
            fastest_lap=fl_time,
            is_fastest_lap=is_fl,
        ))

    return RaceResult(
        season=str(table.get("season") or race.get("season") or ""),
        round=_int(race.get("round")),
        name=race.get("raceName") or "",
        circuit=circuit.get("circuitName"),
        country=location.get("country"),
        locality=location.get("locality"),
        date=when,
        rows=rows,
    )


def assemble(calendar_payload: dict, drivers_payload: dict,
             constructors_payload: dict, now: datetime) -> SeasonOverview:
    """Собрать обзор сезона из трёх ответов Jolpica."""
    calendar, season = parse_calendar(calendar_payload, now)
    nxt = next((e for e in calendar if e.is_next), None)
    days = None
    if nxt is not None and nxt.date is not None:
        days = max(0, (nxt.date - now + timedelta(seconds=1)).days + 1)

    return SeasonOverview(
        season=season,
        races_total=len(calendar),
        races_done=sum(1 for e in calendar if e.is_past),
        next_race=nxt,
        days_to_next=days,
        calendar=calendar,
        drivers=parse_driver_standings(drivers_payload),
        constructors=parse_constructor_standings(constructors_payload),
    )


class JolpicaClient:
    """HTTP-обёртка. Вынесена отдельно, чтобы разбор тестировался без сети."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def startup(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.jolpica_base_url,
            timeout=settings.jolpica_timeout_s,
            headers={"Accept": "application/json", "User-Agent": "PitWall/1.0"},
            follow_redirects=True,
        )

    async def shutdown(self) -> None:
        if self._client is not None:
            await self._client.aclose()

    async def fetch_overview(self) -> SeasonOverview:
        if self._client is None:
            await self.startup()
        assert self._client is not None

        async def j(path: str) -> dict:
            r = await self._client.get(path)
            r.raise_for_status()
            return r.json()

        # Последовательно, а не Promise.all: у Jolpica есть лимиты, а данные
        # зачётов меняются раз в уик-энд — экономить миллисекунды тут незачем.
        calendar = await j("current.json?limit=100")
        drivers = await j("current/driverStandings.json")
        constructors = await j("current/constructorStandings.json")
        return assemble(calendar, drivers, constructors, datetime.now(timezone.utc))

    async def fetch_race_result(self, round_no: int) -> RaceResult:
        """Протокол одного этапа текущего сезона."""
        if self._client is None:
            await self.startup()
        assert self._client is not None
        # limit=100: в гонке до 22 машин, но запас на дисквалификации и т.п.
        r = await self._client.get(f"current/{round_no}/results.json?limit=100")
        r.raise_for_status()
        return parse_race_result(r.json())
