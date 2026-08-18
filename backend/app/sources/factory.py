"""Source selection — one place decides which adapter is live."""
from __future__ import annotations

from app.core.config import settings
from app.sources.base import DataSource
from app.sources.simulated import SimulatedSource
from app.sources.openf1 import OpenF1Source

_INSTANCE: DataSource | None = None


def build_source() -> DataSource:
    if settings.data_source == "openf1":
        return OpenF1Source()
    # «fixture» исторически означает демо-режим; теперь это симулятор
    # всего календаря, а не один заранее сгенерированный заезд.
    return SimulatedSource()


def get_source() -> DataSource:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = build_source()
    return _INSTANCE


def set_source(source: DataSource) -> None:
    """Used by the app lifespan / tests to inject a started instance."""
    global _INSTANCE
    _INSTANCE = source
