"""Data-source abstraction.

Every concrete source (live OpenF1, bundled fixture, a future backend
aggregator) returns *raw OpenF1-shaped* records. Normalization into domain
models happens once, in the service layer — so all sources share it and the
rest of the app never sees vendor specifics.

Query filters mirror OpenF1's query params where they exist:
    session_key, driver_number, date_gte (date>=), date_lte (date<=).
Adapters that read local data apply the same filters in memory.
"""
from __future__ import annotations

import abc
from datetime import datetime

Raw = dict
RawList = list[dict]


class DataSource(abc.ABC):
    """Read-only access to timing/telemetry records for a session."""

    name: str = "base"

    # -- lifecycle ----------------------------------------------------------
    async def startup(self) -> None:  # optional
        ...

    async def shutdown(self) -> None:  # optional
        ...

    # -- catalog ------------------------------------------------------------
    @abc.abstractmethod
    async def get_sessions(
        self,
        *,
        year: int | None = None,
        country: str | None = None,
        session_name: str | None = None,
    ) -> RawList: ...

    @abc.abstractmethod
    async def get_meetings(self, *, year: int | None = None) -> RawList: ...

    # -- per-session --------------------------------------------------------
    @abc.abstractmethod
    async def get_drivers(self, session_key: int) -> RawList: ...

    @abc.abstractmethod
    async def get_position(
        self, session_key: int, *, date_gte: datetime | None = None,
        date_lte: datetime | None = None,
    ) -> RawList: ...

    @abc.abstractmethod
    async def get_intervals(
        self, session_key: int, *, date_gte: datetime | None = None,
        date_lte: datetime | None = None,
    ) -> RawList: ...

    @abc.abstractmethod
    async def get_location(
        self, session_key: int, *, driver_number: int | None = None,
        date_gte: datetime | None = None, date_lte: datetime | None = None,
    ) -> RawList: ...

    @abc.abstractmethod
    async def get_car_data(
        self, session_key: int, *, driver_number: int | None = None,
        date_gte: datetime | None = None, date_lte: datetime | None = None,
    ) -> RawList: ...

    @abc.abstractmethod
    async def get_laps(
        self, session_key: int, *, driver_number: int | None = None,
    ) -> RawList: ...

    @abc.abstractmethod
    async def get_stints(self, session_key: int) -> RawList: ...

    @abc.abstractmethod
    async def get_pit(self, session_key: int) -> RawList: ...

    @abc.abstractmethod
    async def get_weather(
        self, session_key: int, *, date_gte: datetime | None = None,
        date_lte: datetime | None = None,
    ) -> RawList: ...

    @abc.abstractmethod
    async def get_race_control(self, session_key: int) -> RawList: ...
