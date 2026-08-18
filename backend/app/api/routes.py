"""HTTP API — a stable, source-agnostic contract for the frontend.

Time handling for replay: the client works in *offset seconds from session
start*. Endpoints accept either an absolute ISO ``t`` or an ``offset`` (seconds);
``offset`` is the normal path for the replay scrubber.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.domain.models import (
    Driver, DriverStints, Frame, SessionInfo, TelemetryWindow, TimeBounds, TrackGeometry,
)
from app.services.session_service import service

router = APIRouter(prefix="/api")


@router.get("/health", tags=["meta"])
async def health() -> dict:
    from app.cache.cache import cache
    from app.db.database import db
    return {
        "status": "ok",
        "data_source": settings.data_source,
        "cache_backend": cache.backend,
        "db_enabled": db.enabled,
    }


@router.get("/sessions", response_model=list[SessionInfo], tags=["catalog"])
async def list_sessions(year: int | None = Query(default=None)) -> list[SessionInfo]:
    return await service.list_sessions(year=year)


@router.get("/sessions/{session_key}", response_model=SessionInfo, tags=["catalog"])
async def get_session(session_key: int) -> SessionInfo:
    info = await service.get_session_info(session_key)
    if info is None:
        raise HTTPException(404, "session not found")
    return info


@router.get("/sessions/{session_key}/drivers", response_model=list[Driver], tags=["catalog"])
async def get_drivers(session_key: int) -> list[Driver]:
    return await service.get_drivers(session_key)


@router.get("/sessions/{session_key}/bounds", response_model=TimeBounds, tags=["replay"])
async def get_bounds(session_key: int) -> TimeBounds:
    b = await service.get_bounds(session_key)
    if b is None:
        raise HTTPException(404, "no time bounds for session")
    return b


async def _resolve_t(session_key: int, t: str | None, offset: float | None) -> datetime:
    if t:
        try:
            return datetime.fromisoformat(t.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(422, f"bad t: {exc}") from exc
    b = await service.get_bounds(session_key)
    if b is None:
        raise HTTPException(404, "unknown session")
    return b.start + timedelta(seconds=offset or 0.0)


@router.get("/sessions/{session_key}/frame", response_model=Frame, tags=["replay"])
async def get_frame(
    session_key: int,
    t: str | None = Query(default=None, description="absolute ISO timestamp"),
    offset: float | None = Query(default=None, description="seconds from session start"),
) -> Frame:
    when = await _resolve_t(session_key, t, offset)
    return await service.build_frame(session_key, when)


@router.get("/sessions/{session_key}/track", response_model=TrackGeometry, tags=["replay"])
async def get_track(session_key: int) -> TrackGeometry:
    return await service.build_track(session_key)


@router.get("/sessions/{session_key}/tyres", response_model=list[DriverStints], tags=["replay"])
async def get_tyres(session_key: int) -> list[DriverStints]:
    return await service.build_tyres(session_key)


@router.get("/sessions/{session_key}/telemetry", response_model=TelemetryWindow, tags=["replay"])
async def get_telemetry(
    session_key: int,
    driver: int = Query(..., description="driver_number of the active driver"),
    t: str | None = Query(default=None),
    offset: float | None = Query(default=None),
    window: int | None = Query(default=None, description="sliding window seconds"),
) -> TelemetryWindow:
    when = await _resolve_t(session_key, t, offset)
    return await service.build_telemetry(session_key, driver, when, window_s=window)
