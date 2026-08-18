"""Async SQLAlchemy engine + session, wired to Postgres.

Persistence is *optional*: if ``PITWALL_DATABASE_URL`` is unset or the DB is
unreachable, ``db.enabled`` stays False and every consumer skips it gracefully.
The app still serves all endpoints straight from source + cache. This keeps the
architecture "Postgres-ready" without making the DB a hard boot dependency.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("db")


class Base(DeclarativeBase):
    pass


class Database:
    def __init__(self) -> None:
        self.engine: AsyncEngine | None = None
        self.sessionmaker: async_sessionmaker[AsyncSession] | None = None
        self.enabled = False

    async def startup(self) -> None:
        if not settings.database_url:
            log.info("DB: disabled (no PITWALL_DATABASE_URL set)")
            return
        try:
            self.engine = create_async_engine(
                settings.database_url, pool_pre_ping=True, future=True
            )
            self.sessionmaker = async_sessionmaker(self.engine, expire_on_commit=False)
            # Import models so metadata is populated, then create tables.
            from app.db import models  # noqa: F401

            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            self.enabled = True
            log.info("DB: connected, schema ready")
        except Exception as exc:  # noqa: BLE001 — degrade, never crash
            log.warning("DB: unavailable (%s); running without persistence", exc)
            self.engine = None
            self.enabled = False

    async def shutdown(self) -> None:
        if self.engine is not None:
            await self.engine.dispose()


db = Database()
