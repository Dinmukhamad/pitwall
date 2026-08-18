"""Цвета команд по constructorId (Ergast/Jolpica).

Держим отдельно от логики: список меняется каждый сезон (переименования команд,
новые участники), и это единственное место, куда нужно вносить правку.
"""
from __future__ import annotations

TEAM_COLOURS: dict[str, str] = {
    "red_bull": "3671C6",
    "ferrari": "E8002D",
    "mclaren": "FF8000",
    "mercedes": "27F4D2",
    "aston_martin": "229971",
    "alpine": "0093CC",
    "williams": "64C4FF",
    "rb": "6692FF",
    "alphatauri": "6692FF",
    "racing_bulls": "6692FF",
    "sauber": "52E252",
    "kick_sauber": "52E252",
    "audi": "BB0A30",
    "haas": "B6BABD",
    "cadillac": "C9A24B",
}
NEUTRAL = "8A9099"


def team_colour(constructor_id: str | None, name: str | None = None) -> str:
    """Цвет по id, иначе — попытка угадать по названию, иначе нейтральный."""
    if constructor_id:
        hit = TEAM_COLOURS.get(constructor_id.strip().lower())
        if hit:
            return hit
    if name:
        low = name.lower()
        for key, colour in TEAM_COLOURS.items():
            if key.replace("_", " ") in low:
                return colour
    return NEUTRAL
