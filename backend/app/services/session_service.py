"""Orchestration: source calls + cache + normalization -> domain objects.

This is the layer the API routers talk to. It owns the data-loading discipline
from TZ §5:
  * time-windowed queries for position/intervals/location (DR-01),
  * per-driver car_data only for the active driver (DR-03),
  * downsampling of map + telemetry samples (DR-02),
  * caching of small/immutable per-session datasets (DR-04).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.models import (
    CarPosition, Driver, DriverStints, Frame, SessionInfo, Stint,
    TelemetrySample, TelemetryWindow, TimeBounds, TimingRow, TrackGeometry, TrackPoint,
    WeatherSnapshot,
)
from app.cache.cache import cache
from app.services import normalize as N
from app.sources.factory import get_source

log = get_logger("service")


def _ensure_aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class SessionService:
    # ---- catalog ---------------------------------------------------------
    async def list_sessions(self, year: int | None = None) -> list[SessionInfo]:
        key = f"sessions:{year}"
        cached = await cache.get_json(key)
        if cached is None:
            rows = await get_source().get_sessions(year=year, session_name="Race")
            if not rows:  # fixture may not filter by name; fall back
                rows = await get_source().get_sessions(year=year)
            cached = rows
            await cache.set_json(key, rows, ttl=settings.cache_ttl_static_s)
        return [self._session_info(r) for r in cached]

    async def get_session_info(self, session_key: int) -> SessionInfo | None:
        for s in await self.list_sessions():
            if s.session_key == session_key:
                s.total_laps = await self._total_laps(session_key)
                return s
        # not in default list — query directly
        rows = await get_source().get_sessions()
        for r in rows:
            if r.get("session_key") == session_key:
                info = self._session_info(r)
                info.total_laps = await self._total_laps(session_key)
                return info
        return None

    def _session_info(self, r: dict) -> SessionInfo:
        return SessionInfo(
            session_key=r.get("session_key"),
            meeting_key=r.get("meeting_key"),
            year=r.get("year"),
            country=r.get("country_name") or r.get("country"),
            circuit=r.get("circuit_short_name") or r.get("location"),
            session_name=r.get("session_name"),
            session_type=r.get("session_type"),
            date_start=N.parse_dt(r.get("date_start")),
            date_end=N.parse_dt(r.get("date_end")),
        )

    # ---- small per-session datasets (cached) -----------------------------
    async def _drivers_raw(self, session_key: int) -> list[dict]:
        key = f"drivers:{session_key}"
        cached = await cache.get_json(key)
        if cached is None:
            cached = await get_source().get_drivers(session_key)
            await cache.set_json(key, cached, ttl=settings.cache_ttl_static_s)
        return cached

    async def get_drivers(self, session_key: int) -> list[Driver]:
        return [N.norm_driver(r) for r in await self._drivers_raw(session_key)]

    async def _cached(self, session_key: int, name: str, fetch) -> list[dict]:
        key = f"{name}:{session_key}"
        cached = await cache.get_json(key)
        if cached is None:
            cached = await fetch()
            await cache.set_json(key, cached, ttl=settings.cache_ttl_static_s)
        return cached

    async def _laps(self, sk):    return await self._cached(sk, "laps", lambda: get_source().get_laps(sk))
    async def _stints(self, sk):  return await self._cached(sk, "stints", lambda: get_source().get_stints(sk))
    async def _pit(self, sk):     return await self._cached(sk, "pit", lambda: get_source().get_pit(sk))
    async def _weather(self, sk): return await self._cached(sk, "weather", lambda: get_source().get_weather(sk))
    async def _rc(self, sk):      return await self._cached(sk, "rc", lambda: get_source().get_race_control(sk))

    async def _total_laps(self, session_key: int) -> int | None:
        laps = await self._laps(session_key)
        nums = [l.get("lap_number") for l in laps if l.get("lap_number")]
        return max(nums) if nums else None

    # ---- time bounds -----------------------------------------------------
    async def get_bounds(self, session_key: int) -> TimeBounds | None:
        info = await self.get_session_info(session_key)
        if info and info.date_start and info.date_end:
            return TimeBounds(session_key=session_key, start=info.date_start, end=info.date_end)
        pos = await get_source().get_position(session_key)
        dts = [N.parse_dt(p.get("date")) for p in pos]
        dts = [d for d in dts if d]
        if not dts:
            return None
        return TimeBounds(session_key=session_key, start=min(dts), end=max(dts))

    # ---- the replay/live frame ------------------------------------------
    async def build_frame(self, session_key: int, t: datetime) -> Frame:
        t = _ensure_aware(t)
        src = get_source()
        window_start = t - timedelta(seconds=5)

        position = await src.get_position(session_key, date_gte=window_start, date_lte=t)
        intervals = await src.get_intervals(session_key, date_gte=window_start, date_lte=t)
        location = await src.get_location(session_key, date_gte=window_start, date_lte=t)

        drivers = {d.get("driver_number"): d for d in await self._drivers_raw(session_key)}
        laps = await self._laps(session_key)
        stints = await self._stints(session_key)
        pit = await self._pit(session_key)
        weather_rows = await self._weather(session_key)
        rc = await self._rc(session_key)

        pos_by = N.latest_per_driver(position, upto=t)
        int_by = N.latest_per_driver(intervals, upto=t)
        loc_by = N.latest_per_driver(location, upto=t)

        # Lap bookkeeping per driver.
        completed, current_lap, last_lap, best_lap = self._lap_stats(laps, t)
        overall_fastest = min((b for b in best_lap.values() if b), default=None)

        rows: list[TimingRow] = []
        for num, draw in drivers.items():
            p = pos_by.get(num, {})
            iv = int_by.get(num, {})
            interval = iv.get("interval")
            gap = iv.get("gap_to_leader")
            cl = current_lap.get(num)
            compound, tyre_age = self._tyre_at_lap(stints, num, cl)
            ll = last_lap.get(num)
            bl = best_lap.get(num)
            rows.append(TimingRow(
                driver_number=num,
                position=p.get("position"),
                interval=interval,
                gap_to_leader=gap,
                last_lap=ll,
                best_lap=bl,
                lap_number=cl,
                compound=N.norm_compound(compound),
                tyre_age=tyre_age,
                # DRS is available within 1s of the car ahead (glossary def).
                drs=bool(interval is not None and 0 < interval < 1.0),
                in_pit=self._in_pit(pit, num, t),
                is_fastest_lap=bool(bl and overall_fastest and abs(bl - overall_fastest) < 1e-6),
                is_personal_best=bool(ll and bl and abs(ll - bl) < 1e-6),
            ))
        rows.sort(key=lambda r: (r.position is None, r.position or 999))

        positions = [
            CarPosition(driver_number=num, x=float(l.get("x", 0)), y=float(l.get("y", 0)))
            for num, l in loc_by.items() if l.get("x") is not None
        ]

        return Frame(
            t=t,
            lap=max([v for v in current_lap.values() if v], default=None),
            total_laps=await self._total_laps(session_key),
            flag=N.norm_flag_from_race_control(rc, t),
            timing=rows,
            positions=positions,
            weather=self._weather_at(weather_rows, t),
        )

    # ---- telemetry (active driver only, DR-03) --------------------------
    async def build_telemetry(self, session_key: int, driver_number: int,
                              t: datetime, window_s: int | None = None) -> TelemetryWindow:
        t = _ensure_aware(t)
        window_s = window_s or settings.telemetry_window_s
        start = t - timedelta(seconds=window_s)
        raw = await get_source().get_car_data(
            session_key, driver_number=driver_number, date_gte=start, date_lte=t
        )
        raw = [r for r in raw if N.parse_dt(r.get("date"))]
        raw.sort(key=lambda r: N.parse_dt(r.get("date")))
        # Downsample to a glass-readable density (DR-02): cap ~120 points.
        raw = self._downsample(raw, cap=120)

        samples = [
            TelemetrySample(
                t=N.parse_dt(r.get("date")),
                speed=r.get("speed"), throttle=r.get("throttle"), brake=r.get("brake"),
                n_gear=r.get("n_gear"), rpm=r.get("rpm"), drs=N.drs_open(r.get("drs")),
            )
            for r in raw
        ]
        current = samples[-1] if samples else None
        laps = await self._laps(session_key)
        stints = await self._stints(session_key)
        _, current_lap, _, _ = self._lap_stats(laps, t)
        compound, tyre_age = self._tyre_at_lap(stints, driver_number, current_lap.get(driver_number))
        return TelemetryWindow(
            driver_number=driver_number, current=current, samples=samples,
            compound=N.norm_compound(compound), tyre_age=tyre_age,
        )

    # ---- track geometry --------------------------------------------------
    async def build_track(self, session_key: int) -> TrackGeometry:
        key = f"track:{session_key}"
        cached = await cache.get_json(key)
        if cached is not None:
            return TrackGeometry(**cached)

        drivers = await self._drivers_raw(session_key)
        laps = await self._laps(session_key)
        # pick a driver and one representative lap
        chosen = drivers[0]["driver_number"] if drivers else None
        pts: list[TrackPoint] = []
        if chosen is not None:
            dl = [l for l in laps if l.get("driver_number") == chosen and l.get("lap_duration")]
            loc = await get_source().get_location(session_key, driver_number=chosen)
            loc = [l for l in loc if l.get("x") is not None]
            loc.sort(key=lambda l: N.parse_dt(l.get("date")) or datetime.min.replace(tzinfo=timezone.utc))
            if dl and loc:
                start = N.parse_dt(dl[0].get("date_start")) or N.parse_dt(loc[0].get("date"))
                end = start + timedelta(seconds=dl[0]["lap_duration"] * 1.02)
                loc = [l for l in loc if start <= (N.parse_dt(l.get("date")) or start) <= end] or loc
            raw_pts = [(float(l["x"]), float(l["y"])) for l in loc]
            raw_pts = self._smooth(raw_pts)               # R-05 smoothing
            raw_pts = self._downsample_xy(raw_pts, cap=240)
            pts = [TrackPoint(x=x, y=y) for x, y in raw_pts]

        xs = [p.x for p in pts] or [0]
        ys = [p.y for p in pts] or [0]
        geom = TrackGeometry(
            session_key=session_key, points=pts,
            start_finish=pts[0] if pts else None, drs_zones=[],
            bounds={"minx": min(xs), "maxx": max(xs), "miny": min(ys), "maxy": max(ys)},
        )
        await cache.set_json(key, geom.model_dump(), ttl=settings.cache_ttl_static_s)
        return geom

    # ---- tyres -----------------------------------------------------------
    async def build_tyres(self, session_key: int) -> list[DriverStints]:
        stints = await self._stints(session_key)
        by: dict[int, list[Stint]] = {}
        for s in stints:
            num = s.get("driver_number")
            if num is None:
                continue
            by.setdefault(num, []).append(Stint(
                compound=N.norm_compound(s.get("compound")),
                lap_start=s.get("lap_start"), lap_end=s.get("lap_end"),
                tyre_age_at_start=s.get("tyre_age_at_start"),
            ))
        out = []
        for num, sts in by.items():
            sts.sort(key=lambda x: (x.lap_start or 0))
            out.append(DriverStints(driver_number=num, stints=sts))
        return out

    # ================= internal helpers ==================================
    def _lap_stats(self, laps: list[dict], t: datetime):
        completed: dict[int, int] = {}
        current_lap: dict[int, int] = {}
        last_lap: dict[int, float] = {}
        best_lap: dict[int, float] = {}
        for l in laps:
            num = l.get("driver_number")
            ln = l.get("lap_number")
            dur = l.get("lap_duration")
            ds = N.parse_dt(l.get("date_start"))
            if num is None or ln is None or ds is None:
                continue
            if ds <= t:
                current_lap[num] = max(current_lap.get(num, 0), ln)
            if dur and ds + timedelta(seconds=dur) <= t:
                completed[num] = max(completed.get(num, 0), ln)
                if ln >= completed.get(num, 0):
                    last_lap[num] = dur
                best_lap[num] = min(best_lap.get(num, 1e9), dur)
        best_lap = {k: v for k, v in best_lap.items() if v < 1e9}
        return completed, current_lap, last_lap, best_lap

    def _tyre_at_lap(self, stints: list[dict], num: int, lap: int | None):
        if lap is None:
            lap = 1
        for s in stints:
            if s.get("driver_number") != num:
                continue
            ls, le = s.get("lap_start"), s.get("lap_end")
            if ls is None or le is None:
                continue
            if ls <= lap <= le:
                age0 = s.get("tyre_age_at_start") or 0
                return s.get("compound"), age0 + (lap - ls)
        return None, None

    def _in_pit(self, pit: list[dict], num: int, t: datetime) -> bool:
        for p in pit:
            if p.get("driver_number") != num:
                continue
            d = N.parse_dt(p.get("date"))
            if d is None:
                continue
            dur = p.get("pit_duration") or 25
            if d <= t <= d + timedelta(seconds=dur + 8):  # include the lane in/out
                return True
        return False

    def _weather_at(self, rows: list[dict], t: datetime) -> WeatherSnapshot | None:
        best = None
        best_dt = None
        for r in rows:
            d = N.parse_dt(r.get("date"))
            if d is None or d > t:
                continue
            if best_dt is None or d >= best_dt:
                best, best_dt = r, d
        if best is None and rows:
            best = rows[0]
        if best is None:
            return None
        return WeatherSnapshot(
            air_temperature=best.get("air_temperature"),
            track_temperature=best.get("track_temperature"),
            humidity=best.get("humidity"),
            wind_speed=best.get("wind_speed"),
            wind_direction=best.get("wind_direction"),
            rainfall=best.get("rainfall"),
        )

    @staticmethod
    def _downsample(rows: list, cap: int) -> list:
        if len(rows) <= cap:
            return rows
        step = len(rows) / cap
        return [rows[int(i * step)] for i in range(cap)]

    @staticmethod
    def _downsample_xy(pts: list[tuple[float, float]], cap: int) -> list[tuple[float, float]]:
        if len(pts) <= cap:
            return pts
        step = len(pts) / cap
        return [pts[int(i * step)] for i in range(cap)]

    @staticmethod
    def _smooth(pts: list[tuple[float, float]], window: int = 5) -> list[tuple[float, float]]:
        if len(pts) < window:
            return pts
        out = []
        half = window // 2
        n = len(pts)
        for i in range(n):
            xs = [pts[(i + k) % n][0] for k in range(-half, half + 1)]
            ys = [pts[(i + k) % n][1] for k in range(-half, half + 1)]
            out.append((sum(xs) / len(xs), sum(ys) / len(ys)))
        return out


service = SessionService()
