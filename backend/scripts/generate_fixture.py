"""Generate a bundled sample session in OpenF1's raw wire shape.

Deterministic (fixed seed) so the fixture is reproducible. Output lands in
``app/sources/fixtures/*.json``. Run:  python scripts/generate_fixture.py
"""
from __future__ import annotations

import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

random.seed(2024)

OUT = Path(__file__).resolve().parent.parent / "app" / "sources" / "fixtures"
OUT.mkdir(parents=True, exist_ok=True)

SESSION_KEY = 9999
MEETING_KEY = 1999
YEAR = 2024
T0 = datetime(2024, 5, 26, 13, 0, 0, tzinfo=timezone.utc)  # race start

LAPS = 6
LAP_TIME = 78.0            # nominal seconds per lap
LOC_HZ = 3.0              # location sample rate
CAR_HZ = 2.0             # car_data sample rate

DRIVERS = [
    # number, acronym, full name, team, colour (hex, no '#')
    (1,  "VER", "Max Verstappen",   "Red Bull Racing", "3671C6"),
    (16, "LEC", "Charles Leclerc",  "Ferrari",         "E80020"),
    (4,  "NOR", "Lando Norris",     "McLaren",         "FF8000"),
    (44, "HAM", "Lewis Hamilton",   "Mercedes",        "27F4D2"),
    (14, "ALO", "Fernando Alonso",  "Aston Martin",    "229971"),
    (81, "PIA", "Oscar Piastri",    "McLaren",         "FF8000"),
]

# --- Track geometry (a closed parametric loop) ---------------------------
A, B = 3000.0, 550.0
C, D = 2100.0, 850.0


def track_xy(theta: float) -> tuple[float, float]:
    x = A * math.cos(theta) + B * math.cos(3 * theta)
    y = C * math.sin(theta) + D * math.sin(2 * theta)
    return x, y


# Precompute arc-length table for distance<->theta mapping.
_STEPS = 2000
_thetas = [2 * math.pi * i / _STEPS for i in range(_STEPS + 1)]
_pts = [track_xy(t) for t in _thetas]
_cum = [0.0]
for i in range(1, len(_pts)):
    dx = _pts[i][0] - _pts[i - 1][0]
    dy = _pts[i][1] - _pts[i - 1][1]
    _cum.append(_cum[-1] + math.hypot(dx, dy))
TRACK_LEN = _cum[-1]

# Local speed factor: slower through tight corners (high curvature).
def _curvature_speed(theta: float) -> float:
    # crude: derivative magnitude -> normalize
    h = 1e-3
    x1, y1 = track_xy(theta - h)
    x2, y2 = track_xy(theta + h)
    d = math.hypot(x2 - x1, y2 - y1) / (2 * h)
    return d


_speeds = [_curvature_speed(t) for t in _thetas]
_smax, _smin = max(_speeds), min(_speeds)


def speed_at(theta: float) -> float:
    theta = theta % (2 * math.pi)
    idx = int(theta / (2 * math.pi) * _STEPS)
    s = _speeds[idx]
    norm = (s - _smin) / (_smax - _smin + 1e-9)   # 0..1
    return 90.0 + norm * 240.0                      # km/h, ~90 (corner) .. 330 (straight)


# DRS zone: enabled while theta in a straight-ish arc.
DRS_LO, DRS_HI = 0.15, 0.75  # in units of full lap (0..1)


def in_drs_zone(lap_frac: float) -> bool:
    return DRS_LO <= (lap_frac % 1.0) <= DRS_HI


def iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "+00:00")


# --- Per-driver pace model ------------------------------------------------
# Slightly different pace + start offset so order evolves and cars spread out.
pace = {}
start_offset = {}
for i, (num, *_rest) in enumerate(DRIVERS):
    pace[num] = 1.0 + (i * 0.006) + random.uniform(-0.002, 0.002)  # >1 = slower
    start_offset[num] = i * 3.2  # grid gap in seconds


def driver_progress(num: int, t: float) -> float:
    """Total distance travelled (in 'laps', float) at race time t seconds."""
    eff_t = max(0.0, t - start_offset[num])
    # small per-lap noise via sine so intervals wobble realistically
    wobble = 0.01 * math.sin(eff_t / 11.0 + num)
    return eff_t / (LAP_TIME * pace[num]) + wobble


def theta_of_progress(prog: float) -> float:
    return 2 * math.pi * (prog % 1.0)


RACE_DUR = LAP_TIME * LAPS * max(pace.values()) + 8

# ---------------------------------------------------------------------------
sessions = [{
    "session_key": SESSION_KEY,
    "meeting_key": MEETING_KEY,
    "location": "Monaco",
    "country_name": "Monaco",
    "circuit_short_name": "Monaco",
    "session_name": "Race",
    "session_type": "Race",
    "year": YEAR,
    "date_start": iso(T0),
    "date_end": iso(T0 + timedelta(seconds=RACE_DUR)),
}]

meetings = [{
    "meeting_key": MEETING_KEY,
    "meeting_name": "Monaco Grand Prix",
    "meeting_official_name": "FORMULA 1 GRAND PRIX DE MONACO 2024 (sample)",
    "country_name": "Monaco",
    "location": "Monte Carlo",
    "year": YEAR,
    "date_start": iso(T0),
}]

drivers = [{
    "session_key": SESSION_KEY,
    "meeting_key": MEETING_KEY,
    "driver_number": num,
    "name_acronym": acr,
    "full_name": full,
    "team_name": team,
    "team_colour": colour,
} for (num, acr, full, team, colour) in DRIVERS]

# --- Sampled streams ------------------------------------------------------
location: list[dict] = []
car_data: list[dict] = []
position: list[dict] = []
intervals: list[dict] = []

loc_dt = 1.0 / LOC_HZ
car_dt = 1.0 / CAR_HZ

# location + car_data
for (num, *_r) in DRIVERS:
    t = 0.0
    while t <= RACE_DUR:
        prog = driver_progress(num, t)
        if prog >= 0:
            theta = theta_of_progress(prog)
            x, y = track_xy(theta)
            location.append({
                "session_key": SESSION_KEY, "driver_number": num,
                "date": iso(T0 + timedelta(seconds=t)),
                "x": round(x, 1), "y": round(y, 1), "z": 0,
            })
        t += loc_dt

    t = 0.0
    while t <= RACE_DUR:
        prog = driver_progress(num, t)
        if prog >= 0:
            theta = theta_of_progress(prog)
            lap_frac = prog % 1.0
            spd = speed_at(theta) + random.uniform(-4, 4)
            spd = max(60.0, spd)
            # throttle/brake from whether accelerating (speed relative to local)
            base = speed_at(theta)
            throttle = 100 if spd >= base - 5 else max(0, int(spd / base * 100))
            brake = 100 if spd < base - 25 else 0
            gear = min(8, max(1, int(spd / 45) + 1))
            rpm = int(6000 + (spd / 330.0) * 6000)
            drs_on = in_drs_zone(lap_frac)
            # OpenF1 drs is an integer code; 8/10/12/14 = enabled variants.
            drs_code = 12 if drs_on else 1
            car_data.append({
                "session_key": SESSION_KEY, "driver_number": num,
                "date": iso(T0 + timedelta(seconds=t)),
                "speed": round(spd), "throttle": throttle, "brake": brake,
                "drs": drs_code, "n_gear": gear, "rpm": rpm,
            })
        t += car_dt

# position + intervals sampled at 1 Hz from progress
t = 0.0
while t <= RACE_DUR:
    progs = {num: driver_progress(num, t) for (num, *_r) in DRIVERS}
    order = sorted(progs.items(), key=lambda kv: kv[1], reverse=True)
    leader_prog = order[0][1]
    dt_stamp = iso(T0 + timedelta(seconds=t))
    prev_prog = None
    for pos, (num, prog) in enumerate(order, start=1):
        position.append({
            "session_key": SESSION_KEY, "driver_number": num,
            "date": dt_stamp, "position": pos,
        })
        # convert distance-gap (in laps) to seconds using nominal pace
        gap_leader = (leader_prog - prog) * LAP_TIME
        interval = 0.0 if prev_prog is None else (prev_prog - prog) * LAP_TIME
        intervals.append({
            "session_key": SESSION_KEY, "driver_number": num, "date": dt_stamp,
            "gap_to_leader": round(gap_leader, 3),
            "interval": round(interval, 3),
        })
        prev_prog = prog
    t += 1.0

# --- Laps -----------------------------------------------------------------
laps: list[dict] = []
for (num, *_r) in DRIVERS:
    for lap_number in range(1, LAPS + 1):
        # time when this driver completes lap boundary
        target = lap_number
        # invert progress ~ linear; approximate start time of the lap
        lap_start_t = start_offset[num] + (lap_number - 1) * LAP_TIME * pace[num]
        dur = LAP_TIME * pace[num] + random.uniform(-1.2, 1.6)
        laps.append({
            "session_key": SESSION_KEY, "driver_number": num,
            "lap_number": lap_number,
            "date_start": iso(T0 + timedelta(seconds=lap_start_t)),
            "lap_duration": round(dur, 3),
            "is_pit_out_lap": False,
        })

# --- Stints (one pit stop mid-race for most) ------------------------------
stints: list[dict] = []
pit: list[dict] = []
for i, (num, *_r) in enumerate(DRIVERS):
    pit_lap = 3 + (i % 2)  # lap 3 or 4
    stints.append({
        "session_key": SESSION_KEY, "driver_number": num, "stint_number": 1,
        "compound": "SOFT" if i % 2 == 0 else "MEDIUM",
        "lap_start": 1, "lap_end": pit_lap, "tyre_age_at_start": 0,
    })
    stints.append({
        "session_key": SESSION_KEY, "driver_number": num, "stint_number": 2,
        "compound": "HARD" if i % 2 == 0 else "MEDIUM",
        "lap_start": pit_lap + 1, "lap_end": LAPS, "tyre_age_at_start": 0,
    })
    pit_t = start_offset[num] + pit_lap * LAP_TIME * pace[num]
    pit.append({
        "session_key": SESSION_KEY, "driver_number": num,
        "date": iso(T0 + timedelta(seconds=pit_t)),
        "pit_duration": round(random.uniform(22, 26), 1),
        "lap_number": pit_lap,
    })

# --- Weather --------------------------------------------------------------
weather: list[dict] = []
for k in range(0, int(RACE_DUR) + 1, 60):
    weather.append({
        "session_key": SESSION_KEY,
        "date": iso(T0 + timedelta(seconds=k)),
        "air_temperature": round(24 + math.sin(k / 300) * 1.5, 1),
        "track_temperature": round(41 + math.sin(k / 250) * 2.0, 1),
        "humidity": round(58 + math.cos(k / 400) * 4, 1),
        "wind_speed": round(2.5 + random.uniform(-0.5, 0.5), 1),
        "wind_direction": int((k * 3) % 360),
        "rainfall": 0,
    })

# --- Race control ---------------------------------------------------------
race_control = [
    {"session_key": SESSION_KEY, "date": iso(T0),
     "category": "Flag", "flag": "GREEN", "message": "GREEN LIGHT - PIT EXIT OPEN"},
    {"session_key": SESSION_KEY, "date": iso(T0 + timedelta(seconds=LAP_TIME * 2)),
     "category": "Flag", "flag": "YELLOW", "scope": "Sector", "sector": 2,
     "message": "YELLOW IN TRACK SECTOR 2"},
    {"session_key": SESSION_KEY, "date": iso(T0 + timedelta(seconds=LAP_TIME * 2 + 25)),
     "category": "Flag", "flag": "CLEAR", "message": "CLEAR IN TRACK SECTOR 2"},
    {"session_key": SESSION_KEY, "date": iso(T0 + timedelta(seconds=RACE_DUR - 2)),
     "category": "Flag", "flag": "CHEQUERED", "message": "CHEQUERED FLAG"},
]

# --- Write ----------------------------------------------------------------
files = {
    "sessions": sessions, "meetings": meetings, "drivers": drivers,
    "location": location, "car_data": car_data, "position": position,
    "intervals": intervals, "laps": laps, "stints": stints, "pit": pit,
    "weather": weather, "race_control": race_control,
}
for name, data in files.items():
    (OUT / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"  {name:12s} {len(data):6d} rows")

print(f"\nTrack length ~ {TRACK_LEN:.0f} units, race ~ {RACE_DUR:.0f}s, "
      f"wrote {len(files)} files to {OUT}")
