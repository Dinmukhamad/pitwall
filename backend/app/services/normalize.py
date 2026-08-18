"""Pure functions mapping OpenF1 raw records -> domain models.

No I/O here — trivially unit-testable, and the single place vendor field names
turn into our vocabulary.
"""
from __future__ import annotations

from datetime import datetime

from app.domain.models import Compound, Driver, FlagState

# --- primitives -----------------------------------------------------------

def parse_dt(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def drs_open(code) -> bool:
    """Map OpenF1's integer ``drs`` code to open/closed (FR-23).

    Per OpenF1 docs the codes are roughly:
        0, 1      -> off
        2, 3      -> off (unknown/standby variants)
        8         -> eligible (detected, not yet activated)
        10,12,14  -> on / active
    We treat only the active codes as "open".
    """
    try:
        return int(code) in (10, 12, 14)
    except (TypeError, ValueError):
        return False


_COMPOUNDS = {
    "SOFT": "SOFT", "MEDIUM": "MEDIUM", "HARD": "HARD",
    "INTERMEDIATE": "INTERMEDIATE", "WET": "WET",
    # tolerate short/alt spellings
    "S": "SOFT", "M": "MEDIUM", "H": "HARD", "I": "INTERMEDIATE", "W": "WET",
}


def norm_compound(value) -> Compound:
    if not value:
        return "UNKNOWN"
    return _COMPOUNDS.get(str(value).strip().upper(), "UNKNOWN")


_FLAGS = {
    "GREEN": "GREEN", "YELLOW": "YELLOW", "DOUBLE YELLOW": "DOUBLE_YELLOW",
    "RED": "RED", "CHEQUERED": "CHEQUERED",
}


def norm_flag_from_race_control(rows: list[dict], upto: datetime) -> FlagState:
    """Derive a single overall flag state from race_control messages <= upto."""
    current: FlagState = "GREEN"
    relevant = sorted(
        (r for r in rows if (parse_dt(r.get("date")) or datetime.min.replace(tzinfo=upto.tzinfo)) <= upto),
        key=lambda r: parse_dt(r.get("date")) or upto,
    )
    for r in relevant:
        cat = str(r.get("category", "")).lower()
        flag = str(r.get("flag", "")).upper()
        msg = str(r.get("message", "")).upper()
        if "SAFETY CAR" in msg or r.get("category") == "SafetyCar":
            current = "VSC" if "VIRTUAL" in msg else "SC"
        elif flag == "CHEQUERED":
            current = "CHEQUERED"
        elif flag == "RED":
            current = "RED"
        elif flag in ("GREEN", "CLEAR"):
            current = "GREEN"
        elif flag in _FLAGS and cat == "flag":
            current = _FLAGS[flag]  # type: ignore[assignment]
    return current


def norm_driver(raw: dict) -> Driver:
    return Driver(
        driver_number=raw.get("driver_number"),
        name_acronym=raw.get("name_acronym") or "UNK",
        full_name=raw.get("full_name") or raw.get("broadcast_name"),
        team_name=raw.get("team_name"),
        team_colour=(raw.get("team_colour") or "888888").lstrip("#"),
    )


def latest_per_driver(rows: list[dict], upto: datetime | None = None,
                      date_key: str = "date") -> dict[int, dict]:
    """Newest record per driver_number, optionally not later than ``upto``."""
    best: dict[int, tuple[datetime, dict]] = {}
    for r in rows:
        num = r.get("driver_number")
        if num is None:
            continue
        ts = parse_dt(r.get(date_key))
        if ts is None:
            continue
        if upto is not None and ts > upto:
            continue
        cur = best.get(num)
        if cur is None or ts >= cur[0]:
            best[num] = (ts, r)
    return {num: rec for num, (_, rec) in best.items()}
