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
    # Текст, который издание САМО синдицировало в RSS (content:encoded или
    # description). Показывается во встроенной читалке. Страница издания при
    # этом не скачивается: републикация чужой статьи запрещена (ТЗ L-01).
    body: list[str] = []          # абзацы, уже очищенные от HTML
    full_text: bool = False       # True, если лента отдала статью, а не анонс
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
