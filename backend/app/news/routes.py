"""API подсистемы «Новости» (ТЗ §10.9).

Фронтенду достаточно одного запроса к своему API — вместо публичных
CORS-прокси и разбора XML в браузере (§10.1).

Правовое (§10.10): отдаём только заголовок, короткую выдержку и ссылку на
оригинал; полные тексты не републикуются, источник указан у каждого материала.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Query

from app.cache.cache import cache
from app.core.config import settings
from app.core.logging import get_logger
from app.news.collector import collect
from app.news.models import Article, NewsFeed, NewsSource
from app.news.sources import DEFAULT_SOURCES, enabled_sources

log = get_logger("news.routes")
router = APIRouter(prefix="/api/news", tags=["news"])

CACHE_KEY = "news:feed"


@router.get("/sources", response_model=list[NewsSource])
async def news_sources() -> list[NewsSource]:
    """Список источников для фильтров (API-02)."""
    return DEFAULT_SOURCES


@router.get("", response_model=NewsFeed)
async def news_feed(
    sources: str | None = Query(default=None, description="id источников через запятую"),
    limit: int = Query(default=0, ge=0, le=200),
    refresh: bool = Query(default=False, description="обойти кэш"),
) -> NewsFeed:
    """Лента новостей (API-01).

    Кэшируется целиком: опрос источников идёт по расписанию TTL, а не на
    каждый запрос пользователя — это и вежливо к источникам (SC-01/SC-02),
    и быстро для клиента.
    """
    active = enabled_sources()
    payload = None if refresh else await cache.get_json(CACHE_KEY)

    if payload is None:
        articles, failed = await collect(active)
        feed = NewsFeed(
            items=articles[: settings.news_limit],
            sources=DEFAULT_SOURCES,
            fetched_at=datetime.now(timezone.utc),
            failed_sources=failed,
            error=None if articles else "Источники новостей недоступны",
        )
        # Пустую выдачу не кэшируем надолго — иначе разовый сбой сети
        # «залипнет» на весь TTL.
        await cache.set_json(CACHE_KEY, feed.model_dump(),
                             ttl=settings.news_ttl_s if articles else 60)
    else:
        feed = NewsFeed(**payload)

    # Фильтрация по источникам — поверх кэша, без повторного опроса.
    if sources:
        wanted = {s.strip() for s in sources.split(",") if s.strip()}
        feed = feed.model_copy(update={
            "items": [a for a in feed.items if a.source_id in wanted]
        })
    if limit:
        feed = feed.model_copy(update={"items": feed.items[:limit]})
    return feed
