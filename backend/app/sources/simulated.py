"""Демо-источник: весь календарь-2026, данные считаются на лету.

Зачем так, а не заранее сгенерированными файлами: заезд на полную дистанцию —
это сотни тысяч записей на этап, а этапов 22. Хранить это невозможно, поэтому
источник вычисляет только то окно, которое запросили. Побочный эффект — в
репозитории нет мегабайт JSON, а в списке гонок доступен весь сезон.

Что здесь настоящее: календарь (названия, страны, даты, дистанции), состав
команд и контуры трасс из каталога. Что имитация: позиции, разрывы, круги и
телеметрия — их считает модель. Настоящие данные гонок — режим `openf1`.
"""
from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from app.core.logging import get_logger
from app.services import track_catalog
from app.sources.base import DataSource, RawList
from app.sources.season2026 import (
    CALENDAR, DRIVERS, MEETING_KEY_BASE, event, round_of,
    session_key as make_session_key,
)

log = get_logger("sources.simulated")

LOC_HZ = 2.0        # частота выборки координат
CAR_HZ = 2.0        # частота выборки телеметрии
ORDER_HZ = 1.0      # частота пересчёта позиций и разрывов
GRID_SLOT_M = 8.0   # расстояние между слотами стартовой решётки
# Плотность запроса без окна ограничиваем, иначе полная дистанция гонки
# превратилась бы в сотни тысяч записей на один вызов.
UNWINDOWED_MAX_SAMPLES = 900


def _iso(dt: datetime) -> str:
    return dt.isoformat()


class RaceSim:
    """Модель одного этапа: геометрия трассы + темп пилотов."""

    def __init__(self, round_no: int) -> None:
        ev = event(round_no)
        if ev is None:
            raise ValueError(f"нет этапа {round_no}")
        (self.round, self.name, self.country, self.locality,
         self.circuit_id, self.start, self.laps, self.lap_time) = ev

        self.points = self._load_track()
        self._build_arc_table()

        # Детерминированно: один и тот же этап всегда даёт одну и ту же гонку.
        rnd = random.Random(2026 * 100 + round_no)
        self.pace: dict[int, float] = {}
        self.grid: dict[int, float] = {}
        for i, (num, *_r) in enumerate(DRIVERS):
            self.pace[num] = 1.0 + i * 0.0032 + rnd.uniform(-0.0010, 0.0010)
            self.grid[num] = i * GRID_SLOT_M / self.track_len
        # Пит-стоп в середине дистанции, у всех в разные круги.
        self.pit_lap: dict[int, int] = {
            num: max(2, int(self.laps * 0.35) + (i % 7) - 3)
            for i, (num, *_r) in enumerate(DRIVERS)
        }
        self.duration = self.lap_time * self.laps * max(self.pace.values()) + 10

    # ---- трасса ----------------------------------------------------------
    def _load_track(self) -> list[tuple[float, float]]:
        hit = track_catalog.by_id(self.circuit_id)
        if hit and len(hit.get("points", [])) > 30:
            return [(float(p[0]), float(p[1])) for p in hit["points"]]
        # Каталог не собран — параметрическая петля, чтобы демо всё же работало.
        log.warning("Контур %s не найден в каталоге, беру синтетический", self.circuit_id)
        a, b, c, d = 900.0, 160.0, 620.0, 250.0
        return [(a * math.cos(t) + b * math.cos(3 * t), c * math.sin(t) + d * math.sin(2 * t))
                for t in (2 * math.pi * i / 400 for i in range(400))]

    def _build_arc_table(self) -> None:
        pts = self.points
        cum = [0.0]
        for i in range(1, len(pts)):
            cum.append(cum[-1] + math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]))
        self._cum = cum
        self._close = math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1])
        self.track_len = cum[-1] + self._close

    def point_at(self, frac: float) -> tuple[float, float]:
        target = (frac % 1.0) * self.track_len
        pts, cum = self.points, self._cum
        if target >= cum[-1]:
            t = (target - cum[-1]) / max(self._close, 1e-9)
            (x0, y0), (x1, y1) = pts[-1], pts[0]
            return x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        lo, hi = 0, len(cum) - 1
        while lo < hi - 1:
            mid = (lo + hi) // 2
            if cum[mid] <= target:
                lo = mid
            else:
                hi = mid
        seg = max(cum[lo + 1] - cum[lo], 1e-9)
        t = (target - cum[lo]) / seg
        (x0, y0), (x1, y1) = pts[lo], pts[lo + 1]
        return x0 + (x1 - x0) * t, y0 + (y1 - y0) * t

    def speed_at(self, frac: float) -> float:
        """Скорость по кривизне: в поворотах медленно, на прямых быстро."""
        d = 0.004
        x0, y0 = self.point_at(frac - d)
        x1, y1 = self.point_at(frac)
        x2, y2 = self.point_at(frac + d)
        turn = abs((math.atan2(y2 - y1, x2 - x1) - math.atan2(y1 - y0, x1 - x0)
                    + math.pi) % (2 * math.pi) - math.pi)
        straightness = max(0.0, 1.0 - turn / 0.55)
        return 95.0 + straightness * 215.0

    # ---- динамика --------------------------------------------------------
    def progress(self, num: int, t: float) -> float:
        """Пройденная дистанция в кругах к секунде t от старта."""
        if t <= 0:
            return -self.grid[num]
        base = t / (self.lap_time * self.pace[num])
        breathing = 0.012 * math.sin(t / 13.0 + num) * min(1.0, t / 90.0)
        return base - self.grid[num] + breathing

    def offsets(self, date_gte: datetime | None, date_lte: datetime | None,
                hz: float) -> list[float]:
        """Секунды от старта, попадающие в запрошенное окно."""
        lo = 0.0 if date_gte is None else (date_gte - self.start).total_seconds()
        hi = self.duration if date_lte is None else (date_lte - self.start).total_seconds()
        lo = max(0.0, lo)
        hi = min(self.duration, hi)
        if hi < lo:
            return []
        step = 1.0 / hz
        count = int((hi - lo) / step) + 1
        if count > UNWINDOWED_MAX_SAMPLES:      # запрос без окна — прореживаем
            step = (hi - lo) / UNWINDOWED_MAX_SAMPLES
            count = UNWINDOWED_MAX_SAMPLES + 1
        return [lo + i * step for i in range(count)]

    def lap_start_offset(self, num: int, lap_number: int) -> float:
        return (lap_number - 1 + self.grid[num]) * self.lap_time * self.pace[num]


@lru_cache(maxsize=8)
def _sim(round_no: int) -> RaceSim:
    """Модели кэшируются: пересчитывать таблицу длин дуг на каждый кадр незачем."""
    return RaceSim(round_no)


class SimulatedSource(DataSource):
    name = "simulated"

    async def startup(self) -> None:
        log.info("Демо-источник готов: %d этапов сезона-2026, %d пилотов",
                 len(CALENDAR), len(DRIVERS))

    # ---- вспомогательное -------------------------------------------------
    @staticmethod
    def _sim_for(sk: int) -> RaceSim | None:
        r = round_of(sk)
        return _sim(r) if r else None

    # ---- каталог ---------------------------------------------------------
    async def get_sessions(self, *, year=None, country=None, session_name=None,
                           session_key=None) -> RawList:
        sk_filter = session_key
        rows = []
        for (rnd, name, ctry, loc, cid, start, laps, lap_t) in CALENDAR:
            sim_key = make_session_key(rnd)
            rows.append({
                "session_key": sim_key,
                "meeting_key": MEETING_KEY_BASE + rnd,
                "location": loc, "country_name": ctry,
                "circuit_short_name": loc, "circuit_name": name,
                "session_name": "Race", "session_type": "Race", "year": 2026,
                "round": rnd,
                "date_start": _iso(start),
                "date_end": _iso(start + timedelta(seconds=_sim(rnd).duration)),
            })
        if sk_filter is not None:
            rows = [r for r in rows if r["session_key"] == sk_filter]
        if year is not None:
            rows = [r for r in rows if r["year"] == year]
        if country is not None:
            rows = [r for r in rows if r["country_name"] == country]
        if session_name is not None:
            rows = [r for r in rows if r["session_name"] == session_name]
        return rows

    async def get_meetings(self, *, year=None) -> RawList:
        return [{
            "meeting_key": MEETING_KEY_BASE + rnd, "meeting_name": f"{name} (демо)",
            "meeting_official_name": "Pit Wall demo — имитация, не запись гонки",
            "country_name": ctry, "location": loc, "year": 2026,
            "date_start": _iso(start),
        } for (rnd, name, ctry, loc, _cid, start, _l, _lt) in CALENDAR]

    # ---- по сессии -------------------------------------------------------
    async def get_drivers(self, session_key: int) -> RawList:
        if self._sim_for(session_key) is None:
            return []
        return [{
            "session_key": session_key, "meeting_key": MEETING_KEY_BASE,
            "driver_number": num, "name_acronym": acr, "full_name": full,
            "team_name": team, "team_colour": colour,
        } for (num, acr, full, team, colour) in DRIVERS]

    async def get_location(self, session_key, *, driver_number=None,
                           date_gte=None, date_lte=None) -> RawList:
        sim = self._sim_for(session_key)
        if sim is None:
            return []
        nums = [driver_number] if driver_number else [d[0] for d in DRIVERS]
        out = []
        for t in sim.offsets(date_gte, date_lte, LOC_HZ):
            stamp = _iso(sim.start + timedelta(seconds=t))
            for num in nums:
                pr = sim.progress(num, t)
                if pr < 0:
                    continue
                x, y = sim.point_at(pr)
                out.append({"session_key": session_key, "driver_number": num,
                            "date": stamp, "x": round(x, 1), "y": round(y, 1), "z": 0})
        return out

    async def get_car_data(self, session_key, *, driver_number=None,
                           date_gte=None, date_lte=None) -> RawList:
        sim = self._sim_for(session_key)
        if sim is None:
            return []
        nums = [driver_number] if driver_number else [d[0] for d in DRIVERS]
        out = []
        for t in sim.offsets(date_gte, date_lte, CAR_HZ):
            stamp = _iso(sim.start + timedelta(seconds=t))
            for num in nums:
                pr = sim.progress(num, t)
                if pr < 0:
                    continue
                frac = pr % 1.0
                base = sim.speed_at(frac)
                # Шум детерминирован: одна и та же секунда даёт то же значение.
                jitter = math.sin(t * 7.3 + num * 1.7) * 4.0
                spd = max(70.0, base + jitter)
                out.append({
                    "session_key": session_key, "driver_number": num, "date": stamp,
                    "speed": round(spd),
                    "throttle": 100 if spd >= base - 6 else max(0, int(spd / base * 100)),
                    "brake": 100 if spd < base - 28 else 0,
                    "drs": 12 if 0.02 <= frac <= 0.16 or 0.55 <= frac <= 0.66 else 1,
                    "n_gear": min(8, max(1, int(spd / 42) + 1)),
                    "rpm": int(6000 + (spd / 330.0) * 6200),
                })
        return out

    async def _order(self, session_key, date_gte, date_lte):
        sim = self._sim_for(session_key)
        if sim is None:
            return [], None
        rows = []
        for t in sim.offsets(date_gte, date_lte, ORDER_HZ):
            progs = {num: sim.progress(num, t) for (num, *_r) in DRIVERS}
            rows.append((t, sorted(progs.items(), key=lambda kv: kv[1], reverse=True)))
        return rows, sim

    async def get_position(self, session_key, *, date_gte=None, date_lte=None) -> RawList:
        rows, sim = await self._order(session_key, date_gte, date_lte)
        out = []
        for t, order in rows:
            stamp = _iso(sim.start + timedelta(seconds=t))
            for pos, (num, _pr) in enumerate(order, start=1):
                out.append({"session_key": session_key, "driver_number": num,
                            "date": stamp, "position": pos})
        return out

    async def get_intervals(self, session_key, *, date_gte=None, date_lte=None) -> RawList:
        rows, sim = await self._order(session_key, date_gte, date_lte)
        out = []
        for t, order in rows:
            stamp = _iso(sim.start + timedelta(seconds=t))
            leader = order[0][1]
            prev = None
            for num, pr in order:
                out.append({
                    "session_key": session_key, "driver_number": num, "date": stamp,
                    "gap_to_leader": round((leader - pr) * sim.lap_time, 3),
                    "interval": 0.0 if prev is None else round((prev - pr) * sim.lap_time, 3),
                })
                prev = pr
        return out

    async def get_laps(self, session_key, *, driver_number=None) -> RawList:
        sim = self._sim_for(session_key)
        if sim is None:
            return []
        nums = [driver_number] if driver_number else [d[0] for d in DRIVERS]
        out = []
        for num in nums:
            for lap in range(1, sim.laps + 1):
                start = sim.lap_start_offset(num, lap)
                dur = sim.lap_time * sim.pace[num] + math.sin(lap * 2.7 + num) * 0.9
                out.append({
                    "session_key": session_key, "driver_number": num, "lap_number": lap,
                    "date_start": _iso(sim.start + timedelta(seconds=start)),
                    "lap_duration": round(dur, 3), "is_pit_out_lap": lap == sim.pit_lap[num] + 1,
                })
        return out

    async def get_stints(self, session_key: int) -> RawList:
        sim = self._sim_for(session_key)
        if sim is None:
            return []
        out = []
        for i, (num, *_r) in enumerate(DRIVERS):
            pit = sim.pit_lap[num]
            first, second = ("SOFT", "HARD") if i % 2 == 0 else ("MEDIUM", "HARD")
            out.append({"session_key": session_key, "driver_number": num, "stint_number": 1,
                        "compound": first, "lap_start": 1, "lap_end": pit,
                        "tyre_age_at_start": 0})
            out.append({"session_key": session_key, "driver_number": num, "stint_number": 2,
                        "compound": second, "lap_start": pit + 1, "lap_end": sim.laps,
                        "tyre_age_at_start": 0})
        return out

    async def get_pit(self, session_key: int) -> RawList:
        sim = self._sim_for(session_key)
        if sim is None:
            return []
        return [{
            "session_key": session_key, "driver_number": num,
            "date": _iso(sim.start + timedelta(
                seconds=sim.lap_start_offset(num, sim.pit_lap[num] + 1))),
            "pit_duration": round(22.0 + (num % 5) * 0.8, 1),
            "lap_number": sim.pit_lap[num],
        } for (num, *_r) in DRIVERS]

    async def get_weather(self, session_key, *, date_gte=None, date_lte=None) -> RawList:
        sim = self._sim_for(session_key)
        if sim is None:
            return []
        return [{
            "session_key": session_key,
            "date": _iso(sim.start + timedelta(seconds=k)),
            "air_temperature": round(23 + math.sin(k / 300 + sim.round) * 2.0, 1),
            "track_temperature": round(38 + math.sin(k / 250 + sim.round) * 3.0, 1),
            "humidity": round(55 + math.cos(k / 400) * 6, 1),
            "wind_speed": round(2.4 + math.sin(k / 500) * 0.8, 1),
            "wind_direction": int((k * 3) % 360), "rainfall": 0,
        } for k in range(0, int(sim.duration) + 1, 60)]

    async def get_race_control(self, session_key: int) -> RawList:
        sim = self._sim_for(session_key)
        if sim is None:
            return []
        return [
            {"session_key": session_key, "date": _iso(sim.start), "category": "Flag",
             "flag": "GREEN", "message": "GREEN LIGHT - PIT EXIT OPEN"},
            {"session_key": session_key,
             "date": _iso(sim.start + timedelta(seconds=sim.lap_time * 3)),
             "category": "Flag", "flag": "YELLOW", "scope": "Sector", "sector": 2,
             "message": "YELLOW IN TRACK SECTOR 2"},
            {"session_key": session_key,
             "date": _iso(sim.start + timedelta(seconds=sim.lap_time * 3 + 30)),
             "category": "Flag", "flag": "CLEAR", "message": "CLEAR IN TRACK SECTOR 2"},
            {"session_key": session_key,
             "date": _iso(sim.start + timedelta(seconds=sim.duration - 2)),
             "category": "Flag", "flag": "CHEQUERED", "message": "CHEQUERED FLAG"},
        ]
