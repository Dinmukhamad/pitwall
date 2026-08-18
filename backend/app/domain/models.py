"""Normalized domain models — the stable contract exposed to the frontend.

These are deliberately decoupled from OpenF1's raw wire schema (which the TZ
flags as unstable, R-04). The source adapters emit raw dicts; the service layer
maps them onto these models. If OpenF1 renames a field, only the adapter changes
— the API contract and the frontend stay put.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Compound = Literal["SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET", "UNKNOWN"]
FlagState = Literal["GREEN", "YELLOW", "DOUBLE_YELLOW", "SC", "VSC", "RED", "CHEQUERED", "UNKNOWN"]


class SessionInfo(BaseModel):
    session_key: int
    meeting_key: int | None = None
    year: int | None = None
    country: str | None = None
    circuit: str | None = None
    session_name: str | None = None       # "Race", "Qualifying", ...
    session_type: str | None = None
    date_start: datetime | None = None
    date_end: datetime | None = None
    total_laps: int | None = None


class Driver(BaseModel):
    driver_number: int
    name_acronym: str = "UNK"
    full_name: str | None = None
    team_name: str | None = None
    team_colour: str = "888888"  # hex without '#', OpenF1 convention


class TimingRow(BaseModel):
    """One row of the Timing Tower at a given instant."""
    driver_number: int
    position: int | None = None
    interval: float | None = None       # gap to car ahead (s)
    gap_to_leader: float | None = None  # gap to leader (s)
    last_lap: float | None = None       # last lap duration (s)
    best_lap: float | None = None       # personal best lap (s)
    lap_number: int | None = None
    compound: Compound = "UNKNOWN"
    tyre_age: int | None = None
    drs: bool = False
    in_pit: bool = False
    is_fastest_lap: bool = False        # holds the overall fastest lap
    is_personal_best: bool = False      # last lap == personal best


class CarPosition(BaseModel):
    driver_number: int
    x: float
    y: float


class Frame(BaseModel):
    """Everything needed to paint the second screen at time ``t``."""
    t: datetime
    lap: int | None = None
    total_laps: int | None = None
    flag: FlagState = "UNKNOWN"
    timing: list[TimingRow] = Field(default_factory=list)
    positions: list[CarPosition] = Field(default_factory=list)
    weather: "WeatherSnapshot | None" = None


class WeatherSnapshot(BaseModel):
    air_temperature: float | None = None
    track_temperature: float | None = None
    humidity: float | None = None
    wind_speed: float | None = None
    wind_direction: float | None = None
    rainfall: float | None = None


class TelemetrySample(BaseModel):
    t: datetime
    speed: float | None = None
    throttle: float | None = None   # 0..100
    brake: float | None = None      # 0..100
    n_gear: int | None = None
    rpm: float | None = None
    drs: bool = False


class TelemetryWindow(BaseModel):
    driver_number: int
    current: TelemetrySample | None = None
    samples: list[TelemetrySample] = Field(default_factory=list)
    compound: Compound = "UNKNOWN"
    tyre_age: int | None = None


class Stint(BaseModel):
    compound: Compound = "UNKNOWN"
    lap_start: int | None = None
    lap_end: int | None = None
    tyre_age_at_start: int | None = None


class DriverStints(BaseModel):
    driver_number: int
    stints: list[Stint] = Field(default_factory=list)


class TrackPoint(BaseModel):
    x: float
    y: float


class DrsZone(BaseModel):
    start: TrackPoint
    end: TrackPoint


class TrackGeometry(BaseModel):
    session_key: int
    points: list[TrackPoint] = Field(default_factory=list)
    start_finish: TrackPoint | None = None
    drs_zones: list[DrsZone] = Field(default_factory=list)
    bounds: dict[str, float] = Field(default_factory=dict)  # minx,maxx,miny,maxy


class TimeBounds(BaseModel):
    session_key: int
    start: datetime
    end: datetime


# Resolve forward reference (Frame -> WeatherSnapshot).
Frame.model_rebuild()
