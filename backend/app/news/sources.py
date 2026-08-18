"""Configurable news source registry (TZ §10.3, NS-01/NS-02).

Kept declarative so operators can enable/disable feeds without code changes.
The collector/normalizer/translator pipeline (N1..N3) plugs in on top of this.
"""
from __future__ import annotations

from app.news.models import NewsSource

DEFAULT_SOURCES: list[NewsSource] = [
    NewsSource(id="motorsport", name="Motorsport.com", url="https://www.motorsport.com/rss/f1/news/", lang="en"),
    NewsSource(id="autosport", name="Autosport", url="https://www.autosport.com/rss/feed/f1", lang="en"),
    NewsSource(id="therace", name="The Race", url="https://the-race.com/formula-1/feed/", lang="en"),
    NewsSource(id="planetf1", name="PlanetF1", url="https://www.planetf1.com/feed", lang="en"),
    NewsSource(id="racefans", name="RaceFans", url="https://www.racefans.net/feed/", lang="en"),
    NewsSource(id="bbc", name="BBC F1", url="https://feeds.bbci.co.uk/sport/formula1/rss.xml", lang="en"),
    NewsSource(id="f1news_ru", name="F1News.ru", url="https://www.f1news.ru/export/news.xml", lang="ru"),
    NewsSource(id="championat", name="Championat F1", url="https://www.championat.com/rss/f1/", lang="ru"),
    NewsSource(id="google_news", name="Google News (Formula 1)",
               url="https://news.google.com/rss/search?q=Formula+1&hl=en", lang="en"),
]


def enabled_sources() -> list[NewsSource]:
    return [s for s in DEFAULT_SOURCES if s.enabled]
