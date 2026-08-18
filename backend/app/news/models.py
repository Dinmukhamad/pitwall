"""Normalized news article schema (TZ §10.4)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class NewsSource(BaseModel):
    id: str
    name: str
    url: str
    lang: str = "en"
    enabled: bool = True


class Article(BaseModel):
    id: str
    source: str
    source_url: str | None = None
    title: str
    url: str                      # canonical
    excerpt: str | None = None
    image_url: str | None = None
    published_at: datetime | None = None
    lang: str = "en"
    category: str | None = None
    title_ru: str | None = None
    excerpt_ru: str | None = None


class NewsPage(BaseModel):
    items: list[Article] = []
    next_cursor: str | None = None
