"""Модели раздела «Сезон» (ТЗ §2.2 — экраны вне живой гонки).

Нормализованный контракт: схема Ergast/Jolpica остаётся в адаптере, фронтенд
работает с этими моделями.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RaceEvent(BaseModel):
    round: int
    name: str
    circuit: str | None = None
    country: str | None = None
    locality: str | None = None
    date: datetime | None = None
    is_past: bool = False
    is_next: bool = False


class DriverStanding(BaseModel):
    position: int
    code: str                      # акроним (VER, HAM…)
    full_name: str | None = None
    team_name: str | None = None
    team_colour: str = "8A9099"     # hex без '#'
    points: float = 0.0
    wins: int = 0


class ConstructorStanding(BaseModel):
    position: int
    name: str
    team_colour: str = "8A9099"
    points: float = 0.0
    wins: int = 0


class RaceResultRow(BaseModel):
    position: int | None = None     # None — сход (в Ergast positionText = R/D/…)
    position_text: str = ""         # «1», «R», «DNF» — как отдал источник
    driver_code: str = "UNK"
    driver_name: str | None = None
    driver_number: int | None = None
    team_name: str | None = None
    team_colour: str = "8A9099"
    grid: int | None = None
    laps: int | None = None
    status: str | None = None       # «Finished», «+1 Lap», «Engine»…
    time: str | None = None         # время победителя или отставание
    points: float = 0.0
    fastest_lap: str | None = None
    is_fastest_lap: bool = False    # быстрейший круг гонки


class RaceResult(BaseModel):
    season: str = ""
    round: int = 0
    name: str = ""
    circuit: str | None = None
    country: str | None = None
    locality: str | None = None
    date: datetime | None = None
    rows: list[RaceResultRow] = Field(default_factory=list)
    error: str | None = None


class SeasonOverview(BaseModel):
    season: str
    races_total: int = 0
    races_done: int = 0
    next_race: RaceEvent | None = None
    days_to_next: int | None = None
    calendar: list[RaceEvent] = Field(default_factory=list)
    drivers: list[DriverStanding] = Field(default_factory=list)
    constructors: list[ConstructorStanding] = Field(default_factory=list)
    # Заполняется, когда источник недоступен: фронтенд показывает состояние
    # ошибки с кнопкой повтора вместо выдуманных цифр.
    error: str | None = None
