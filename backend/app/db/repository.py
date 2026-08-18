"""Optional persistence helpers for the session catalog.

All methods no-op (return None / []) when the DB is disabled, so callers can use
them unconditionally.
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.logging import get_logger
from app.db.database import db
from app.db.models import CachedSession

log = get_logger("db.repo")


async def upsert_sessions(rows: list[dict]) -> None:
    if not db.enabled or not db.sessionmaker:
        return
    try:
        async with db.sessionmaker() as s:
            for r in rows:
                sk = r.get("session_key")
                if sk is None:
                    continue
                obj = await s.get(CachedSession, sk)
                if obj is None:
                    obj = CachedSession(session_key=sk)
                    s.add(obj)
                obj.meeting_key = r.get("meeting_key")
                obj.year = r.get("year")
                obj.country = r.get("country")
                obj.circuit = r.get("circuit")
                obj.session_name = r.get("session_name")
                obj.payload = r
            await s.commit()
    except Exception as exc:  # noqa: BLE001
        log.warning("upsert_sessions skipped (%s)", exc)


async def list_sessions() -> list[dict]:
    if not db.enabled or not db.sessionmaker:
        return []
    try:
        async with db.sessionmaker() as s:
            res = await s.execute(select(CachedSession))
            return [row.payload for row in res.scalars().all()]
    except Exception as exc:  # noqa: BLE001
        log.warning("list_sessions skipped (%s)", exc)
        return []
