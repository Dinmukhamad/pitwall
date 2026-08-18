"""Конвейер новостей: разбор RSS/Atom, нормализация, дедупликация — без сети."""
from __future__ import annotations

import os

os.environ.setdefault("PITWALL_DATA_SOURCE", "fixture")

from app.news.collector import (  # noqa: E402
    canonical_url, deduplicate, normalize_title, parse_feed, strip_html,
)
from app.news.models import NewsSource  # noqa: E402

SRC = NewsSource(id="test", name="Тестовая лента", url="http://example.com/rss", lang="ru")
GOOGLE = NewsSource(id="gn", name="Google Новости", url="http://news.google.com/rss", lang="ru")

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
<channel>
  <title>Тест</title>
  <item>
    <title>Ферстаппен выиграл Гран-при Монако</title>
    <link>https://example.com/news/1?utm_source=rss&amp;utm_medium=feed</link>
    <description>&lt;p&gt;Гонщик &lt;b&gt;Red Bull&lt;/b&gt; финишировал первым.&lt;/p&gt;
      &lt;img src="https://example.com/a.jpg"&gt;</description>
    <pubDate>Sun, 26 May 2024 15:30:00 +0000</pubDate>
  </item>
  <item>
    <title>Леклер стал вторым</title>
    <link>https://example.com/news/2</link>
    <description>Пилот Ferrari поднялся на подиум.</description>
    <pubDate>Sun, 26 May 2024 16:00:00 +0000</pubDate>
    <enclosure url="https://example.com/b.jpg" type="image/jpeg" length="1000"/>
  </item>
  <item>
    <title>Без ссылки — должен быть отброшен</title>
    <description>нет link</description>
  </item>
</channel></rss>"""

ATOM = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom тест</title>
  <entry>
    <title>Норрис на поуле</title>
    <link href="https://example.org/a1"/>
    <summary>Квалификация завершилась сенсацией.</summary>
    <updated>2024-05-25T14:00:00Z</updated>
  </entry>
</feed>"""

GOOGLE_RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>Ферстаппен выиграл гонку - Спорт-Экспресс</title>
    <link>https://news.google.com/articles/xyz</link>
    <description>текст</description>
    <pubDate>Mon, 27 May 2024 08:00:00 +0000</pubDate>
    <source url="https://sport-express.ru">Спорт-Экспресс</source>
  </item>
</channel></rss>"""


def test_rss_parsed_into_schema():
    items = parse_feed(RSS, SRC)
    # Запись без ссылки не попадает в ленту.
    assert len(items) == 2
    first = items[0]
    assert first.title == "Ферстаппен выиграл Гран-при Монако"
    # HTML вычищен, картинка вытащена из тела описания.
    assert "<" not in (first.excerpt or "") and "Red Bull" in first.excerpt
    assert first.image_url == "https://example.com/a.jpg"
    assert first.published_at is not None and first.published_at.year == 2024
    assert first.source_id == "test"
    # enclosure как источник картинки
    assert items[1].image_url == "https://example.com/b.jpg"


def test_atom_parsed():
    items = parse_feed(ATOM, SRC)
    assert len(items) == 1 and items[0].title == "Норрис на поуле"
    assert items[0].url == "https://example.org/a1"


def test_google_news_source_extracted_from_title():
    """У Google News издание указано суффиксом заголовка — переносим в source."""
    items = parse_feed(GOOGLE_RSS, GOOGLE)
    assert len(items) == 1
    assert items[0].source == "Спорт-Экспресс"
    assert items[0].title == "Ферстаппен выиграл гонку"   # суффикс убран


def test_canonical_url_strips_tracking():
    assert canonical_url("https://E.com/News/1/?utm_source=x&id=7&fbclid=z") == \
        "https://e.com/News/1?id=7"


def test_dedup_by_url_and_title():
    a = parse_feed(RSS, SRC)[0]
    same_url = a.model_copy(update={"id": "other"})
    same_title = a.model_copy(update={
        "id": "x", "url": "https://other.com/p",
        # другой регистр и пунктуация — тот же материал
        "title": "ФЕРСТАППЕН ВЫИГРАЛ ГРАН-ПРИ МОНАКО!!!",
    })
    unique = a.model_copy(update={"id": "y", "url": "https://other.com/q",
                                  "title": "Совсем другая новость"})
    out = deduplicate([a, same_url, same_title, unique])
    assert len(out) == 2
    assert {x.title for x in out} == {a.title, "Совсем другая новость"}


def test_normalize_title_handles_yo_and_punctuation():
    assert normalize_title("Гонщик «Ф1» — всё!") == normalize_title("гонщик ф1 все")


def test_strip_html():
    assert strip_html("<p>Привет  <b>мир</b></p>") == "Привет мир"
    assert strip_html(None) == ""


def test_broken_feed_yields_nothing_but_does_not_raise():
    assert parse_feed("не xml вовсе", SRC) == []
    assert parse_feed("", SRC) == []
