"""Собрать каталог реальных контуров трасс F1 (запасная геометрия, ТЗ §2.3 / R-05).

Источник: открытый набор `bacinger/f1-circuits` (GeoJSON, геометрия построена по
данным OpenStreetMap). Данные НЕ хранятся в репозитории — скрипт скачивает их при
установке/сборке в `app/data/circuits.json` (см. .gitignore). Так мы не
перераспространяем чужой набор и соблюдаем L-02 из ТЗ.

Координаты проецируются из широты/долготы в локальные метры (равнопромежуточная
проекция относительно центра трассы) — проверено на Монако: 3324 м против
заявленных 3337 м.

Запуск:  python scripts/fetch_circuits.py
Сбой скачивания не критичен: приложение и фикстур работают и без каталога.
"""
from __future__ import annotations

import json
import math
import sys
import urllib.request
from pathlib import Path

SOURCE_URL = "https://raw.githubusercontent.com/bacinger/f1-circuits/master/f1-circuits.geojson"
ATTRIBUTION = (
    "Circuit geometry: bacinger/f1-circuits (GeoJSON), derived from OpenStreetMap "
    "(© OpenStreetMap contributors, ODbL)."
)
OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "circuits.json"
EARTH_R = 6371000.0


def project(coords: list[list[float]]) -> tuple[list[list[float]], dict]:
    """[[lon, lat], ...] -> [[x, y], ...] в метрах относительно центра трассы."""
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    lat0 = sum(lats) / len(lats)
    lon0 = sum(lons) / len(lons)
    cos_lat = math.cos(math.radians(lat0))
    pts = [
        [
            round(math.radians(lon - lon0) * EARTH_R * cos_lat, 1),
            round(math.radians(lat - lat0) * EARTH_R, 1),
        ]
        for lon, lat in zip(lons, lats)
    ]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return pts, {"minx": min(xs), "maxx": max(xs), "miny": min(ys), "maxy": max(ys)}


def perimeter(pts: list[list[float]]) -> float:
    total = 0.0
    for i in range(1, len(pts)):
        total += math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])
    total += math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1])
    return total


def main() -> int:
    print(f"Скачиваю {SOURCE_URL} …")
    try:
        with urllib.request.urlopen(SOURCE_URL, timeout=30) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 — не критично для сборки
        print(f"  ! не удалось скачать ({exc}); каталог трасс пропущен", file=sys.stderr)
        return 0

    catalog: dict[str, dict] = {}
    for feat in raw.get("features", []):
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        if geom.get("type") != "LineString":
            continue
        coords = geom.get("coordinates") or []
        if len(coords) < 20:
            continue
        pts, bounds = project(coords)
        cid = props.get("id")
        catalog[cid] = {
            "id": cid,
            "name": props.get("Name"),
            "location": props.get("Location"),
            "length_m": props.get("length"),
            "measured_m": round(perimeter(pts)),
            "points": pts,
            "bounds": bounds,
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps({"attribution": ATTRIBUTION, "source": SOURCE_URL, "circuits": catalog},
                   ensure_ascii=False),
        encoding="utf-8",
    )
    size_kb = OUT.stat().st_size / 1024
    print(f"  сохранено {len(catalog)} трасс → {OUT} ({size_kb:.0f} КБ)")
    print(f"  {ATTRIBUTION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
