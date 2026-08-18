"""End-to-end smoke tests against the bundled fixture session."""
from __future__ import annotations

import os

os.environ.setdefault("PITWALL_DATA_SOURCE", "fixture")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

SK = 9999


def test_health():
    with TestClient(app) as c:
        r = c.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["data_source"] == "fixture"


def test_sessions_and_drivers():
    with TestClient(app) as c:
        sessions = c.get("/api/sessions").json()
        assert any(s["session_key"] == SK for s in sessions)
        drivers = c.get(f"/api/sessions/{SK}/drivers").json()
        # Полный грид, а не усечённая выборка.
        assert len(drivers) == 20
        assert all("team_colour" in d for d in drivers)
        acronyms = {d["name_acronym"] for d in drivers}
        assert {"VER", "HAM", "LEC", "NOR", "ALO", "TSU"} <= acronyms
        # По две машины в каждой из 10 команд.
        teams = [d["team_name"] for d in drivers]
        assert len(set(teams)) == 10
        assert all(teams.count(t) == 2 for t in set(teams))


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

    assert 2_000 < per < 8_000, f"неправдоподобная длина круга: {per:.0f} м"
    assert gap < per * 0.05, "контур не замкнут"


def test_frame_covers_every_driver():
    """В таблице и на карте должны быть все 20 машин, а позиции — уникальны."""
    with TestClient(app) as c:
        frame = c.get(f"/api/sessions/{SK}/frame", params={"offset": 200}).json()

    assert len(frame["timing"]) == 20
    assert len(frame["positions"]) == 20
    places = [r["position"] for r in frame["timing"]]
    assert sorted(places) == list(range(1, 21)), "позиции дублируются или пропущены"


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
        assert len(tyres) == 20
        assert all(t["stints"] for t in tyres)


def test_news_skeleton():
    with TestClient(app) as c:
        assert c.get("/api/news/sources").json()
        assert c.get("/api/news", params={"lang": "ru"}).json()["items"] == []
