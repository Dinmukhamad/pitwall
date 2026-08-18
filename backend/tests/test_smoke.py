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
        assert len(drivers) == 6
        assert all("team_colour" in d for d in drivers)


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
        assert len(tyres) == 6
        assert all(t["stints"] for t in tyres)


def test_news_skeleton():
    with TestClient(app) as c:
        assert c.get("/api/news/sources").json()
        assert c.get("/api/news", params={"lang": "ru"}).json()["items"] == []
