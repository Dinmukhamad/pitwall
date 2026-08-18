"""Нормализованная схема новостей (ТЗ §10.4)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class NewsSource(BaseModel):
    id: str
    name: str
    url: str
    lang: str = "ru"
    colour: str = "8A9099"   # hex без '#'
    enabled: bool = True


class Article(BaseModel):
    id: str                       # хэш канонической ссылки
    source: str                   # отображаемое имя (может быть изданием из Google News)
    source_id: str                # id ленты, по которой фильтруем
    title: str
    url: str
    excerpt: str | None = None
    image_url: str | None = None
    published_at: datetime | None = None
    lang: str = "ru"


class NewsFeed(BaseModel):
    items: list[Article] = []
    sources: list[NewsSource] = []
    fetched_at: datetime | None = None
    # Ленты, которые не ответили: показываем честно, а не молча укорачиваем список.
    failed_sources: list[str] = []
    error: str | None = None
