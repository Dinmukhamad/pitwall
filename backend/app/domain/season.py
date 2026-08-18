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
