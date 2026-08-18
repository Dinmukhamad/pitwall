"""End-to-end smoke tests against the bundled fixture session."""
from __future__ import annotations

import os

os.environ.setdefault("PITWALL_DATA_SOURCE", "fixture")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

SK = 9011          # Гран-при Венгрии, 11-й этап сезона-2026


def test_health():
    with TestClient(app) as c:
        r = c.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["data_source"] == "fixture"   # демо-режим
        assert body["races_available"] == 22       # весь календарь-2026


def test_all_season_races_are_selectable():
    """В выборе гонки должен быть весь сезон, а не один демо-заезд."""
    with TestClient(app) as c:
        sessions = c.get("/api/sessions").json()

    assert len(sessions) == 22, "в списке не весь календарь сезона"
    assert all(s["year"] == 2026 for s in sessions)
    # Этапы идут по возрастанию даты — как в календаре.
    dates = [s["date_start"] for s in sessions]
    assert dates == sorted(dates)
    # Ключи уникальны, иначе выбор гонки схлопнется.
    assert len({s["session_key"] for s in sessions}) == 22
    names = {s["circuit"] for s in sessions}
    assert {"Monte-Carlo", "Budapest", "Silverstone", "Monza"} <= names


def test_sessions_and_drivers():
    with TestClient(app) as c:
        sessions = c.get("/api/sessions").json()
        assert any(s["session_key"] == SK for s in sessions)
        drivers = c.get(f"/api/sessions/{SK}/drivers").json()
        # Полный грид сезона-2026, а не усечённая выборка.
        assert len(drivers) == 22
        assert all("team_colour" in d for d in drivers)
        acronyms = {d["name_acronym"] for d in drivers}
        assert {"NOR", "VER", "LEC", "HAM", "ALO", "PER"} <= acronyms
        # По две машины в каждой из 11 команд сезона-2026.
        teams = [d["team_name"] for d in drivers]
        assert len(set(teams)) == 11
        assert all(teams.count(t) == 2 for t in set(teams))
        # Дебютанты сезона на месте.
        assert {"Audi", "Cadillac"} <= set(teams)
        # Номера уникальны — иначе таблица и карта разъедутся.
        numbers = [d["driver_number"] for d in drivers]
        assert len(set(numbers)) == len(numbers)


def test_bounds_and_frame():
    with TestClient(app) as c:
        bounds = c.get(f"/api/sessions/{SK}/bounds").json()
        assert "start" in bounds and "end" in bounds
        frame = c.get(f"/api/sessions/{SK}/frame", params={"offset": 120}).json()
        assert frame["timing"], "timing tower should not be empty"
        assert frame["positions"], "car positions should not be empty"
        # positions sorted, every row has a driver
        assert frame["timing"][0]["position"] in (1, None)
        assert frame["flag"] in (
            "GREEN", "YELLOW", "DOUBLE_YELLOW", "SC", "VSC", "RED", "CHEQUERED", "UNKNOWN",
        )
        assert frame["weather"] is not None


def test_track_geometry():
    with TestClient(app) as c:
        track = c.get(f"/api/sessions/{SK}/track").json()
        assert len(track["points"]) > 50
        assert "minx" in track["bounds"]


def test_track_is_a_closed_realistic_loop():
    """Контур должен быть замкнутым кольцом правдоподобной длины.

    Ловит регресс, при котором геометрия выродилась бы в прямую/обрывок:
    начало и конец рядом, а периметр — в диапазоне реальных трасс F1.
    """
    import math

    with TestClient(app) as c:
        pts = c.get(f"/api/sessions/{SK}/track").json()["points"]

    per = sum(
        math.dist((pts[i]["x"], pts[i]["y"]), (pts[i - 1]["x"], pts[i - 1]["y"]))
        for i in range(1, len(pts))
    )
    gap = math.dist((pts[0]["x"], pts[0]["y"]), (pts[-1]["x"], pts[-1]["y"]))

    assert 3_000 < per < 8_000, f"неправдоподобная длина круга: {per:.0f} м"
    assert gap < per * 0.05, "контур не замкнут"


def test_frame_covers_every_driver():
    """В таблице и на карте должны быть все 22 машины, а позиции — уникальны."""
    with TestClient(app) as c:
        frame = c.get(f"/api/sessions/{SK}/frame", params={"offset": 200}).json()

    assert len(frame["timing"]) == 22
    assert len(frame["positions"]) == 22
    places = [r["position"] for r in frame["timing"]]
    assert sorted(places) == list(range(1, 23)), "позиции дублируются или пропущены"


def test_telemetry_active_driver():
    with TestClient(app) as c:
        tel = c.get(f"/api/sessions/{SK}/telemetry",
                    params={"driver": 1, "offset": 120, "window": 30}).json()
        assert tel["driver_number"] == 1
        assert tel["current"] is not None
        assert len(tel["samples"]) > 5


def test_tyres():
    with TestClient(app) as c:
        tyres = c.get(f"/api/sessions/{SK}/tyres").json()
        assert len(tyres) == 22
        assert all(t["stints"] for t in tyres)


def test_api_responses_are_not_cacheable():
    """Данные тайминга не должны кэшироваться браузером.

    Регресс, который это ловит: после деплоя экран показывает смесь старых
    (постоянный URL, отдан из кэша) и новых (`/frame?offset=…`) данных.
    """
    with TestClient(app) as c:
        for url in (f"/api/sessions/{SK}/drivers", f"/api/sessions/{SK}/track",
                    f"/api/sessions/{SK}/tyres", "/api/health"):
            cc = c.get(url).headers.get("cache-control", "")
            assert "no-store" in cc, f"{url} кэшируется: {cc!r}"

        # Статика обязана сверяться с сервером, иначе остаётся старый интерфейс.
        assert "no-cache" in c.get("/").headers.get("cache-control", "")


def test_news_skeleton():
    with TestClient(app) as c:
        assert c.get("/api/news/sources").json()
        assert c.get("/api/news", params={"lang": "ru"}).json()["items"] == []


def test_each_round_runs_on_its_own_circuit():
    """Разные этапы — разные трассы, а не один контур на весь сезон."""
    import math

    with TestClient(app) as c:
        lengths = {}
        for sk, name in ((9006, "Монако"), (9010, "Спа"), (9013, "Монца")):
            pts = c.get(f"/api/sessions/{sk}/track").json()["points"]
            lengths[name] = sum(
                math.dist((pts[i]["x"], pts[i]["y"]), (pts[i - 1]["x"], pts[i - 1]["y"]))
                for i in range(1, len(pts))
            )

    # Монако заметно короче Спа — если контуры совпали, тест это поймает.
    assert lengths["Монако"] < lengths["Монца"] < lengths["Спа"]
    assert len(set(round(v) for v in lengths.values())) == 3
