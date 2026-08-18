"""Сгенерировать демо-сессию в «сыром» формате OpenF1.

Демо-режим нужен, чтобы приложение работало без сети и без ключей: полный грид
сезона-2024 (20 пилотов), реальный контур трассы из каталога (если он собран
скриптом fetch_circuits.py) и правдоподобная динамика гонки.

Это ИМИТАЦИЯ для демонстрации, а не запись реальной гонки: позиции, круги и
телеметрия рассчитываются моделью, а не взяты из архива. Реальные данные
включаются переменной PITWALL_DATA_SOURCE=openf1.

Детерминирован (фиксированный seed). Запуск: python scripts/generate_fixture.py
"""
from __future__ import annotations

import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

random.seed(2024)

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "app" / "sources" / "fixtures"
CATALOG = BASE / "app" / "data" / "circuits.json"
OUT.mkdir(parents=True, exist_ok=True)

SESSION_KEY = 9999
MEETING_KEY = 1999
YEAR = 2024
T0 = datetime(2024, 5, 26, 13, 0, 0, tzinfo=timezone.utc)

# Трасса демо-сессии (ищется в каталоге по этому ключу).
CIRCUIT_ID = "mc-1929"
CIRCUIT_LOCATION = "Monaco"
CIRCUIT_COUNTRY = "Monaco"
CIRCUIT_NAME = "Circuit de Monaco"

LAPS = 8
LAP_TIME = 74.0            # опорное время круга, с
# Частоты подобраны под демо: карта плавная за счёт интерполяции на клиенте,
# а объём данных остаётся приемлемым по памяти на бесплатном хостинге.
LOC_HZ = 2.0               # частота выборки координат
CAR_HZ = 2.0               # частота выборки телеметрии

# --- Реальный грид сезона-2024: номер, акроним, имя, команда, цвет (OpenF1) ---
DRIVERS = [
    (1,  "VER", "Max Verstappen",     "Red Bull Racing", "3671C6"),
    (11, "PER", "Sergio Perez",       "Red Bull Racing", "3671C6"),
    (16, "LEC", "Charles Leclerc",    "Ferrari",         "E8002D"),
    (55, "SAI", "Carlos Sainz",       "Ferrari",         "E8002D"),
    (4,  "NOR", "Lando Norris",       "McLaren",         "FF8000"),
    (81, "PIA", "Oscar Piastri",      "McLaren",         "FF8000"),
    (44, "HAM", "Lewis Hamilton",     "Mercedes",        "27F4D2"),
    (63, "RUS", "George Russell",     "Mercedes",        "27F4D2"),
    (14, "ALO", "Fernando Alonso",    "Aston Martin",    "229971"),
    (18, "STR", "Lance Stroll",       "Aston Martin",    "229971"),
    (10, "GAS", "Pierre Gasly",       "Alpine",          "0093CC"),
    (31, "OCO", "Esteban Ocon",       "Alpine",          "0093CC"),
    (23, "ALB", "Alexander Albon",    "Williams",        "64C4FF"),
    (2,  "SAR", "Logan Sargeant",     "Williams",        "64C4FF"),
    (22, "TSU", "Yuki Tsunoda",       "RB",              "6692FF"),
    (3,  "RIC", "Daniel Ricciardo",   "RB",              "6692FF"),
    (77, "BOT", "Valtteri Bottas",    "Kick Sauber",     "52E252"),
    (24, "ZHO", "Zhou Guanyu",        "Kick Sauber",     "52E252"),
    (27, "HUL", "Nico Hulkenberg",    "Haas F1 Team",    "B6BABD"),
    (20, "MAG", "Kevin Magnussen",    "Haas F1 Team",    "B6BABD"),
]

# ---------------------------------------------------------------------------
# Геометрия трассы: реальный контур из каталога, иначе — синтетическая петля.
# ---------------------------------------------------------------------------
def load_track() -> tuple[list[tuple[float, float]], str]:
    if CATALOG.exists():
        try:
            data = json.loads(CATALOG.read_text(encoding="utf-8"))
            c = data.get("circuits", {}).get(CIRCUIT_ID)
            if c and len(c.get("points", [])) > 30:
                pts = [(float(p[0]), float(p[1])) for p in c["points"]]
                return pts, f"каталог ({c['name']}, {c['measured_m']} м)"
        except Exception as exc:  # noqa: BLE001
            print(f"  ! каталог не прочитан ({exc})")

    # Запасной вариант — параметрическая петля.
    A, B, C, D = 3000.0, 550.0, 2100.0, 850.0
    pts = []
    for i in range(400):
        th = 2 * math.pi * i / 400
        pts.append((A * math.cos(th) + B * math.cos(3 * th),
                    C * math.sin(th) + D * math.sin(2 * th)))
    return pts, "синтетическая петля (каталог не собран)"


TRACK, TRACK_SRC = load_track()

# Замкнутая ломаная + таблица длин дуг: позиция по доле круга -> координаты.
_CUM = [0.0]
for i in range(1, len(TRACK)):
    _CUM.append(_CUM[-1] + math.hypot(TRACK[i][0] - TRACK[i - 1][0],
                                      TRACK[i][1] - TRACK[i - 1][1]))
_CLOSE = math.hypot(TRACK[0][0] - TRACK[-1][0], TRACK[0][1] - TRACK[-1][1])
TRACK_LEN = _CUM[-1] + _CLOSE


def point_at(frac: float) -> tuple[float, float]:
    """Координаты на доле круга frac ∈ [0,1) с линейной интерполяцией."""
    target = (frac % 1.0) * TRACK_LEN
    if target >= _CUM[-1]:                      # замыкающий сегмент
        t = (target - _CUM[-1]) / max(_CLOSE, 1e-9)
        x0, y0 = TRACK[-1]; x1, y1 = TRACK[0]
        return x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
    lo, hi = 0, len(_CUM) - 1
    while lo < hi - 1:                          # двоичный поиск сегмента
        mid = (lo + hi) // 2
        if _CUM[mid] <= target: lo = mid
        else: hi = mid
    seg = max(_CUM[lo + 1] - _CUM[lo], 1e-9)
    t = (target - _CUM[lo]) / seg
    x0, y0 = TRACK[lo]; x1, y1 = TRACK[lo + 1]
    return x0 + (x1 - x0) * t, y0 + (y1 - y0) * t


def local_speed(frac: float) -> float:
    """Скорость по кривизне: в поворотах медленно, на прямых быстро."""
    d = 0.004
    x0, y0 = point_at(frac - d)
    x1, y1 = point_at(frac)
    x2, y2 = point_at(frac + d)
    a1 = math.atan2(y1 - y0, x1 - x0)
    a2 = math.atan2(y2 - y1, x2 - x1)
    turn = abs((a2 - a1 + math.pi) % (2 * math.pi) - math.pi)   # 0=прямая
    straightness = max(0.0, 1.0 - turn / 0.55)
    return 95.0 + straightness * 215.0                            # км/ч


DRS_ZONES = [(0.02, 0.16), (0.55, 0.66)]


def in_drs_zone(frac: float) -> bool:
    f = frac % 1.0
    return any(a <= f <= b for a, b in DRS_ZONES)


def iso(dt: datetime) -> str:
    return dt.isoformat()


# --- Модель гонки -----------------------------------------------------------
# Все машины стартуют одновременно, но с разных слотов решётки (8 м между
# слотами). Дальше поле растягивается за счёт разницы в темпе. Разброс
# «дыхания» темпа нарастает постепенно, иначе на первых секундах порядок
# определялся бы шумом, а не стартовой позицией.
GRID_SLOT_M = 8.0
grid_frac: dict[int, float] = {}
pace: dict[int, float] = {}
for i, (num, *_r) in enumerate(DRIVERS):
    pace[num] = 1.0 + i * 0.0034 + random.uniform(-0.0011, 0.0011)
    grid_frac[num] = i * GRID_SLOT_M / TRACK_LEN


def progress(num: int, t: float) -> float:
    """Пройденная дистанция в кругах (дробное) к моменту t."""
    if t <= 0:
        return -grid_frac[num]
    base = t / (LAP_TIME * pace[num])
    breathing = 0.012 * math.sin(t / 13.0 + num) * min(1.0, t / 90.0)
    return base - grid_frac[num] + breathing


RACE_DUR = LAP_TIME * LAPS * max(pace.values()) + 10

# ---------------------------------------------------------------------------
sessions = [{
    "session_key": SESSION_KEY, "meeting_key": MEETING_KEY,
    "location": CIRCUIT_LOCATION, "country_name": CIRCUIT_COUNTRY,
    "circuit_short_name": CIRCUIT_LOCATION, "circuit_name": CIRCUIT_NAME,
    "session_name": "Race", "session_type": "Race", "year": YEAR,
    "date_start": iso(T0), "date_end": iso(T0 + timedelta(seconds=RACE_DUR)),
}]

meetings = [{
    "meeting_key": MEETING_KEY, "meeting_name": "Monaco Grand Prix (демо)",
    "meeting_official_name": "Pit Wall demo session — имитация, не реальная гонка",
    "country_name": CIRCUIT_COUNTRY, "location": CIRCUIT_LOCATION,
    "year": YEAR, "date_start": iso(T0),
}]

drivers = [{
    "session_key": SESSION_KEY, "meeting_key": MEETING_KEY,
    "driver_number": num, "name_acronym": acr, "full_name": full,
    "team_name": team, "team_colour": colour,
} for (num, acr, full, team, colour) in DRIVERS]

# --- Потоки координат и телеметрии -----------------------------------------
location: list[dict] = []
car_data: list[dict] = []
loc_dt, car_dt = 1.0 / LOC_HZ, 1.0 / CAR_HZ

for (num, *_r) in DRIVERS:
    t = 0.0
    while t <= RACE_DUR:
        pr = progress(num, t)
        if pr >= 0:
            x, y = point_at(pr)
            location.append({
                "session_key": SESSION_KEY, "driver_number": num,
                "date": iso(T0 + timedelta(seconds=t)),
                "x": round(x, 1), "y": round(y, 1), "z": 0,
            })
        t += loc_dt

    t = 0.0
    while t <= RACE_DUR:
        pr = progress(num, t)
        if pr >= 0:
            frac = pr % 1.0
            base = local_speed(frac)
            spd = max(70.0, base + random.uniform(-5, 5))
            throttle = 100 if spd >= base - 6 else max(0, int(spd / base * 100))
            brake = 100 if spd < base - 28 else 0
            gear = min(8, max(1, int(spd / 42) + 1))
            car_data.append({
                "session_key": SESSION_KEY, "driver_number": num,
                "date": iso(T0 + timedelta(seconds=t)),
                "speed": round(spd), "throttle": throttle, "brake": brake,
                "drs": 12 if in_drs_zone(frac) else 1,
                "n_gear": gear, "rpm": int(6000 + (spd / 330.0) * 6200),
            })
        t += car_dt

# --- Позиции и разрывы (1 Гц) ----------------------------------------------
position: list[dict] = []
intervals: list[dict] = []
t = 0.0
while t <= RACE_DUR:
    progs = {num: progress(num, t) for (num, *_r) in DRIVERS}
    order = sorted(progs.items(), key=lambda kv: kv[1], reverse=True)
    leader = order[0][1]
    stamp = iso(T0 + timedelta(seconds=t))
    prev = None
    for pos, (num, pr) in enumerate(order, start=1):
        position.append({"session_key": SESSION_KEY, "driver_number": num,
                         "date": stamp, "position": pos})
        intervals.append({
            "session_key": SESSION_KEY, "driver_number": num, "date": stamp,
            "gap_to_leader": round((leader - pr) * LAP_TIME, 3),
            "interval": 0.0 if prev is None else round((prev - pr) * LAP_TIME, 3),
        })
        prev = pr
    t += 1.0

# --- Круги ------------------------------------------------------------------
laps: list[dict] = []
for (num, *_r) in DRIVERS:
    for lap_number in range(1, LAPS + 1):
        # момент, когда пилот пересекает линию: progress достигает lap_number-1
        lap_start = (lap_number - 1 + grid_frac[num]) * LAP_TIME * pace[num]
        dur = LAP_TIME * pace[num] + random.uniform(-0.9, 1.4)
        laps.append({
            "session_key": SESSION_KEY, "driver_number": num,
            "lap_number": lap_number,
            "date_start": iso(T0 + timedelta(seconds=lap_start)),
            "lap_duration": round(dur, 3),
            "is_pit_out_lap": False,
        })

# --- Стинты и пит-стопы -----------------------------------------------------
stints: list[dict] = []
pit: list[dict] = []
for i, (num, *_r) in enumerate(DRIVERS):
    pit_lap = 5 + (i % 4)
    first, second = ("SOFT", "HARD") if i % 2 == 0 else ("MEDIUM", "HARD")
    stints.append({"session_key": SESSION_KEY, "driver_number": num, "stint_number": 1,
                   "compound": first, "lap_start": 1, "lap_end": pit_lap,
                   "tyre_age_at_start": 0})
    stints.append({"session_key": SESSION_KEY, "driver_number": num, "stint_number": 2,
                   "compound": second, "lap_start": pit_lap + 1, "lap_end": LAPS,
                   "tyre_age_at_start": 0})
    pit.append({
        "session_key": SESSION_KEY, "driver_number": num,
        "date": iso(T0 + timedelta(seconds=(pit_lap + grid_frac[num]) * LAP_TIME * pace[num])),
        "pit_duration": round(random.uniform(21.5, 26.0), 1), "lap_number": pit_lap,
    })

# --- Погода -----------------------------------------------------------------
weather = [{
    "session_key": SESSION_KEY, "date": iso(T0 + timedelta(seconds=k)),
    "air_temperature": round(24 + math.sin(k / 300) * 1.5, 1),
    "track_temperature": round(41 + math.sin(k / 250) * 2.0, 1),
    "humidity": round(58 + math.cos(k / 400) * 4, 1),
    "wind_speed": round(2.5 + random.uniform(-0.5, 0.5), 1),
    "wind_direction": int((k * 3) % 360), "rainfall": 0,
} for k in range(0, int(RACE_DUR) + 1, 60)]

# --- Race control -----------------------------------------------------------
race_control = [
    {"session_key": SESSION_KEY, "date": iso(T0), "category": "Flag",
     "flag": "GREEN", "message": "GREEN LIGHT - PIT EXIT OPEN"},
    {"session_key": SESSION_KEY, "date": iso(T0 + timedelta(seconds=LAP_TIME * 3)),
     "category": "Flag", "flag": "YELLOW", "scope": "Sector", "sector": 2,
     "message": "YELLOW IN TRACK SECTOR 2"},
    {"session_key": SESSION_KEY, "date": iso(T0 + timedelta(seconds=LAP_TIME * 3 + 30)),
     "category": "Flag", "flag": "CLEAR", "message": "CLEAR IN TRACK SECTOR 2"},
    {"session_key": SESSION_KEY, "date": iso(T0 + timedelta(seconds=RACE_DUR - 2)),
     "category": "Flag", "flag": "CHEQUERED", "message": "CHEQUERED FLAG"},
]

# --- Запись -----------------------------------------------------------------
files = {
    "sessions": sessions, "meetings": meetings, "drivers": drivers,
    "location": location, "car_data": car_data, "position": position,
    "intervals": intervals, "laps": laps, "stints": stints, "pit": pit,
    "weather": weather, "race_control": race_control,
}
total = 0
for name, data in files.items():
    (OUT / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    total += len(data)
    print(f"  {name:12s} {len(data):7d}")

print(f"\nТрасса: {TRACK_SRC}; длина круга ~{TRACK_LEN:.0f} м")
print(f"Пилотов: {len(DRIVERS)}, кругов: {LAPS}, длительность ~{RACE_DUR/60:.1f} мин")
print(f"Всего записей: {total} → {OUT}")
