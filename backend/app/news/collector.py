"""Конвейер новостей: Collector → Normalizer → Deduplicator (ТЗ §10.2).

Работает на сервере, поэтому CORS-прокси из прототипа не нужны: у сервера нет
ограничений браузера, а прокси были главной причиной нестабильности (§10.1).

Перевод (§10.6) не подключён: источники по умолчанию русскоязычные. Точка
расширения — `translate()` между нормализацией и дедупликацией.
"""
from __future__ import annotations

import asyncio
import hashlib
import re
from datetime import datetime, timezone
from html import unescape
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import feedparser
import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.news.models import Article, NewsSource

log = get_logger("news.collector")

# utm-и и прочие метки не меняют материал, но ломают дедуп по ссылке (DR-N1).
TRACKING_PARAMS = re.compile(r"^(utm_|fbclid|gclid|yclid|_openstat|ref$|ref_)", re.I)
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
IMG_RE = re.compile(r"""<img[^>]+src=["']([^"']+)""", re.I)


def canonical_url(url: str) -> str:
    """Убрать метки отслеживания и мусор — ключ дедупликации (DR-N1)."""
    if not url:
        return ""
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not TRACKING_PARAMS.match(k)]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path,
                       urlencode(query), ""))


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    return WS_RE.sub(" ", TAG_RE.sub(" ", unescape(value))).strip()


# Границы абзацев: закрывающий </p>, <br>, </div>, заголовки.
PARA_SPLIT_RE = re.compile(r"(?:</p\s*>|<br\s*/?>|</div\s*>|</h[1-6]\s*>)", re.I)
# Служебные хвосты RSS: «Читать далее», ссылки на источник и т.п.
TAIL_RE = re.compile(r"^(читать (далее|полностью)|подробнее|источник|read more)\b", re.I)


def to_paragraphs(html: str | None, min_len: int = 25) -> list[str]:
    """HTML из ленты -> список абзацев чистого текста.

    Теги вырезаются полностью, а не «санируются»: во встроенную читалку
    попадает только текст, поэтому чужой разметке и скриптам взяться неоткуда
    (XSS исключён по построению).
    """
    if not html:
        return []
    parts = PARA_SPLIT_RE.split(html)
    out: list[str] = []
    for part in parts:
        text = strip_html(part)
        if len(text) < min_len or TAIL_RE.match(text):
            continue
        if text not in out:            # ленты часто дублируют лид в теле
            out.append(text)
    return out


def pick_body(entry) -> tuple[list[str], bool]:
    """Достать самый полный текст, который отдала лента.

    `content:encoded` (feedparser кладёт в ``entry.content``) — это полный
    текст, который издание намеренно синдицировало. Если его нет, остаётся
    анонс из ``summary``.
    """
    candidates: list[str] = []
    for item in getattr(entry, "content", []) or []:
        value = item.get("value") if isinstance(item, dict) else getattr(item, "value", None)
        if value:
            candidates.append(value)
    summary = getattr(entry, "summary", "") or ""
    if summary:
        candidates.append(summary)
    if not candidates:
        return [], False

    richest = max(candidates, key=len)
    paragraphs = to_paragraphs(richest)
    if not paragraphs:
        return [], False

    # Признак статьи, а не анонса: несколько абзацев И заметно больше текста,
    # чем в кратком описании. Одного порога по длине мало — короткая заметка
    # в три абзаца это всё-таки статья, а длинный лид — всё ещё анонс.
    total = sum(len(p) for p in paragraphs)
    summary_len = len(strip_html(summary))
    is_full = len(paragraphs) >= 2 and total >= max(240, int(summary_len * 1.5))
    return paragraphs, is_full


def normalize_title(value: str) -> str:
    """Ключ похожести заголовков: одну новость публикуют многие (DR-N2)."""
    low = (value or "").lower().replace("ё", "е")
    return WS_RE.sub(" ", re.sub(r"[^\w\s]", " ", low, flags=re.U)).strip()


def _parse_date(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        value = getattr(entry, key, None)
        if value:
            try:
                return datetime(*value[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
    return None


def _extract_image(entry) -> str | None:
    for link in getattr(entry, "links", []) or []:
        if link.get("rel") == "enclosure" and "image" in (link.get("type") or ""):
            return link.get("href")
    for key in ("media_content", "media_thumbnail"):
        media = getattr(entry, key, None)
        if media and isinstance(media, list) and media[0].get("url"):
            return media[0]["url"]
    raw = getattr(entry, "summary", "") or ""
    hit = IMG_RE.search(raw)
    return hit.group(1) if hit else None


def parse_feed(raw: bytes | str, source: NewsSource) -> list[Article]:
    """RSS/Atom -> список статей единой схемы (ТЗ §10.4)."""
    parsed = feedparser.parse(raw)
    items: list[Article] = []

    for entry in parsed.entries:
        url = canonical_url(getattr(entry, "link", "") or "")
        title = strip_html(getattr(entry, "title", "") or "")
        if not url or not title or not url.startswith(("http://", "https://")):
            continue

        # Google News добавляет « - Издание» в конец заголовка; убираем и
        # используем как настоящее имя источника.
        display_source = source.name
        origin = getattr(entry, "source", None)
        if origin is not None:
            origin_title = (origin.get("title") if isinstance(origin, dict)
                            else getattr(origin, "title", None))
            if origin_title:
                display_source = origin_title.strip()
                suffix = f" - {display_source}"
                if title.endswith(suffix):
                    title = title[: -len(suffix)].strip()

        body, full_text = pick_body(entry)
        excerpt = strip_html(getattr(entry, "summary", "") or "") or (body[0] if body else "")
        items.append(Article(
            id=hashlib.sha1(url.encode()).hexdigest()[:16],
            source=display_source,
            source_id=source.id,
            title=title,
            url=url,
            excerpt=excerpt[:400] or None,
            body=body,
            full_text=full_text,
            image_url=_extract_image(entry),
            published_at=_parse_date(entry),
            lang=source.lang,
        ))
    return items


def deduplicate(items: list[Article]) -> list[Article]:
    """Убрать повторы по ссылке (DR-N1) и по заголовку (DR-N2)."""
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    out: list[Article] = []
    for art in items:
        title_key = normalize_title(art.title)[:80]
        if art.url in seen_urls or (title_key and title_key in seen_titles):
            continue
        seen_urls.add(art.url)
        if title_key:
            seen_titles.add(title_key)
        out.append(art)
    return out


async def fetch_source(client: httpx.AsyncClient, source: NewsSource) -> list[Article]:
    resp = await client.get(source.url)
    resp.raise_for_status()
    return parse_feed(resp.content, source)


async def collect(sources: list[NewsSource]) -> tuple[list[Article], list[str]]:
    """Собрать и нормализовать ленты. Возвращает (статьи, имена сбойных лент).

    Сбой одной ленты не должен ронять выдачу — остальные показываем, а список
    неответивших отдаём наружу, чтобы не делать вид, что это всё, что есть.
    """
    if not sources:
        return [], []

    headers = {
        # Вежливый User-Agent — требование SC-02.
        "User-Agent": "PitWall/1.0 (F1 second screen; RSS reader)",
        "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
    }
    async with httpx.AsyncClient(timeout=settings.news_timeout_s, headers=headers,
                                 follow_redirects=True) as client:
        results = await asyncio.gather(
            *(fetch_source(client, s) for s in sources), return_exceptions=True
        )

    articles: list[Article] = []
    failed: list[str] = []
    for source, result in zip(sources, results):
        if isinstance(result, Exception):
            log.warning("Лента %s недоступна: %s", source.id, result)
            failed.append(source.name)
        else:
            articles.extend(result)

    articles = deduplicate(articles)
    # Свежие сверху; без даты — в конец.
    articles.sort(key=lambda a: a.published_at or datetime.min.replace(tzinfo=timezone.utc),
                  reverse=True)
    return articles, failed
