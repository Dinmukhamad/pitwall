"""News API (TZ §10.9).

Skeleton stage (N0->N1): the source registry and the normalized contract are
live so the frontend can integrate now. The collector -> normalizer ->
deduplicator -> translator -> store pipeline (§10.2) is stubbed and returns an
empty page with an explicit ``status`` until N1 lands. Wiring it up means
implementing ``collect()`` behind this same contract — no API change.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.news.models import NewsPage, NewsSource
from app.news.sources import enabled_sources

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("/sources", response_model=list[NewsSource])
async def news_sources() -> list[NewsSource]:
    return enabled_sources()


@router.get("", response_model=NewsPage)
async def news_feed(
    lang: str = Query(default="ru"),
    sources: str | None = Query(default=None, description="comma-separated source ids"),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=30, le=100),
) -> NewsPage:
    # TODO(N1): run collector pipeline; for now return an empty, well-formed page.
    return NewsPage(items=[], next_cursor=None)
