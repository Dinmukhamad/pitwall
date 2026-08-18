"""Реестр источников новостей (ТЗ §10.3).

Русскоязычные ленты как в прототипе. Google Новости — широкий агрегатор,
покрывающий множество сайтов сразу (NS-02).

Список конфигурируемый: добавить источник = добавить строку.
"""
from __future__ import annotations

from app.news.models import NewsSource

DEFAULT_SOURCES: list[NewsSource] = [
    NewsSource(
        id="google_news_ru",
        name="Google Новости",
        url=("https://news.google.com/rss/search?"
             "q=%D0%A4%D0%BE%D1%80%D0%BC%D1%83%D0%BB%D0%B0%201%20OR%20%22Formula%201%22"
             "&hl=ru&gl=RU&ceid=RU:ru"),
        lang="ru",
        colour="4C8BF5",
    ),
    NewsSource(id="f1news_ru", name="F1News.ru", url="https://www.f1news.ru/export/news.xml",
               lang="ru", colour="E10600"),
    NewsSource(id="championat", name="Championat", url="https://www.championat.com/rss/auto/",
               lang="ru", colour="F5A623"),
    # Англоязычные — выключены по умолчанию: без переводчика (ТЗ §10.6) лента
    # получилась бы смешанной по языку. Включаются флагом enabled.
    NewsSource(id="motorsport", name="Motorsport.com",
               url="https://www.motorsport.com/rss/f1/news/", lang="en",
               colour="00D2BE", enabled=False),
    NewsSource(id="autosport", name="Autosport", url="https://www.autosport.com/rss/feed/f1",
               lang="en", colour="FF8000", enabled=False),
    NewsSource(id="racefans", name="RaceFans", url="https://www.racefans.net/feed/", lang="en",
               colour="B98BFF", enabled=False),
]


def enabled_sources() -> list[NewsSource]:
    return [s for s in DEFAULT_SOURCES if s.enabled]


def by_id(source_id: str) -> NewsSource | None:
    return next((s for s in DEFAULT_SOURCES if s.id == source_id), None)
