"""Цвета команд по constructorId (Ergast/Jolpica).

Нужны только там, где источник не отдаёт цвет сам: в разделе «Сезон» (Jolpica
цветов не присылает) и в демо-режиме. В живом режиме OpenF1 отдаёт
`team_colour` вместе с данными пилота, и этот справочник не используется.

Список меняется каждый сезон — переименования, новые участники. Это
единственное место, куда нужно вносить правку.
"""
from __future__ import annotations

# Сезон-2026: 11 команд. Audi (на базе Sauber) и Cadillac — дебютанты.
TEAM_COLOURS: dict[str, str] = {
    "mclaren": "FF8000",
    "red_bull": "3671C6",
    "ferrari": "E8002D",
    "mercedes": "27F4D2",
    "williams": "64C4FF",
    "rb": "6692FF",              # Racing Bulls, историческое имя id в Ergast
    "racing_bulls": "6692FF",
    "aston_martin": "229971",
    "audi": "BB0A30",            # пришла на место Sauber в 2026
    "alpine": "0093CC",
    "haas": "B6BABD",
    "cadillac": "C9A24B",        # дебютант 2026
    # Прежние идентификаторы — чтобы архивные сезоны не теряли цвета
    "sauber": "52E252",
    "kick_sauber": "52E252",
    "alphatauri": "6692FF",
    "alfa": "900000",
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
