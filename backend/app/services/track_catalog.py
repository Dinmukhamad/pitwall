"""Каталог реальных контуров трасс — запасной источник геометрии (ТЗ §2.3, R-05).

Основной способ построения контура — трассировка `x,y` из OpenF1 `/location` за
один круг (метод 1, точнее под конкретную сессию). Каталог включается, когда
данных `/location` нет или их слишком мало (нет сессии, начало эфира, шумный
сигнал).

Данные каталога подтягиваются скриптом `scripts/fetch_circuits.py` и в
репозитории не хранятся. Если файла нет — каталог считается пустым, и приложение
работает как раньше.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from app.core.logging import get_logger

log = get_logger("track_catalog")

CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "circuits.json"


def _norm(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]", "", value.lower())


@lru_cache(maxsize=1)
def _catalog() -> dict:
    if not CATALOG_PATH.exists():
        log.info("Каталог трасс не найден (%s) — запасная геометрия отключена", CATALOG_PATH)
        return {}
    try:
        data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        circuits = data.get("circuits", {})
        log.info("Каталог трасс: %d контуров", len(circuits))
        return circuits
    except Exception as exc:  # noqa: BLE001
        log.warning("Каталог трасс не прочитан (%s)", exc)
        return {}


def available() -> bool:
    return bool(_catalog())


def find(*hints: str | None) -> dict | None:
    """Подобрать трассу по подсказкам из сессии.

    Ожидаемые подсказки: ``circuit_short_name``, ``location``, ``country_name``.
    Сначала пробуем точное совпадение по нормализованному имени/локации, затем
    вхождение подстроки — так «Spa-Francorchamps» находит «Spa Francorchamps».
    """
    circuits = _catalog()
    if not circuits:
        return None

    keys = [_norm(h) for h in hints if h]
    if not keys:
        return None

    # 1) точное совпадение
    for key in keys:
        for c in circuits.values():
            if key and key in (_norm(c.get("location")), _norm(c.get("name"))):
                return c

    # 2) вхождение подстроки (в обе стороны)
    for key in keys:
        if len(key) < 4:
            continue
        for c in circuits.values():
            loc, name = _norm(c.get("location")), _norm(c.get("name"))
            if key in loc or loc in key or key in name:
                return c
    return None


def by_id(circuit_id: str) -> dict | None:
    """Трасса по идентификатору каталога (например `hu-1986`)."""
    return _catalog().get(circuit_id)


def attribution() -> str:
    if not CATALOG_PATH.exists():
        return ""
    try:
        return json.loads(CATALOG_PATH.read_text(encoding="utf-8")).get("attribution", "")
    except Exception:  # noqa: BLE001
        return ""
