"""Persistence models.

Deliberately small for the skeleton: we persist the *session catalog* (so the
picker works without re-hitting the source) and *materialized replay frames*
(so an already-computed replay can be replayed again cheaply — replay data is
immutable, TZ DR-04). High-frequency raw streams are NOT stored row-per-sample
here; the aggregator (Variant B, future) would own that.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class CachedSession(Base):
    __tablename__ = "cached_sessions"

    session_key: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    meeting_key: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    circuit: Mapped[str | None] = mapped_column(String(160), nullable=True)
    session_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    date_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class ReplayFrame(Base):
    """A materialized normalized frame at a given offset for a session."""
    __tablename__ = "replay_frames"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_key: Mapped[int] = mapped_column(BigInteger, index=True)
    offset_ms: Mapped[int] = mapped_column(BigInteger)  # ms from session start
    payload: Mapped[dict] = mapped_column(JSON)

    __table_args__ = (
        UniqueConstraint("session_key", "offset_ms", name="uq_frame_session_offset"),
        Index("ix_frame_session_offset", "session_key", "offset_ms"),
    )
