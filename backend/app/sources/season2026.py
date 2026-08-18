"""Календарь сезона-2026 и состав команд — справочные данные демо-режима.

Названия этапов, страны, трассы и даты — настоящие. Дистанции и опорные времена
круга взяты близкими к реальным, чтобы длительность заезда и цифры на экране
выглядели правдоподобно.

Сами позиции, телеметрия и результаты в демо СЧИТАЮТСЯ МОДЕЛЬЮ (см.
`simulated.py`) — это имитация для работы без сети, а не запись гонки.
Настоящие данные включаются переменной PITWALL_DATA_SOURCE=openf1.
"""
from __future__ import annotations

from datetime import datetime, timezone

# round, название, страна, город, id трассы в каталоге, дата (UTC), кругов, опорный круг (с)
CALENDAR: list[tuple[int, str, str, str, str, datetime, int, float]] = [
    (1,  "Australian Grand Prix",   "Australia",   "Melbourne",   "au-1953",
     datetime(2026, 3, 8,  5, 0, tzinfo=timezone.utc), 58, 80.0),
    (2,  "Chinese Grand Prix",      "China",       "Shanghai",    "cn-2004",
     datetime(2026, 3, 15, 7, 0, tzinfo=timezone.utc), 56, 95.0),
    (3,  "Japanese Grand Prix",     "Japan",       "Suzuka",      "jp-1962",
     datetime(2026, 3, 29, 5, 0, tzinfo=timezone.utc), 53, 92.0),
    (4,  "Miami Grand Prix",        "USA",         "Miami",       "us-2022",
     datetime(2026, 5, 3,  20, 0, tzinfo=timezone.utc), 57, 90.0),
    (5,  "Canadian Grand Prix",     "Canada",      "Montreal",    "ca-1978",
     datetime(2026, 5, 24, 18, 0, tzinfo=timezone.utc), 70, 75.0),
    (6,  "Monaco Grand Prix",       "Monaco",      "Monte-Carlo", "mc-1929",
     datetime(2026, 6, 7,  13, 0, tzinfo=timezone.utc), 78, 73.0),
    (7,  "Spanish Grand Prix",      "Spain",       "Barcelona",   "es-1991",
     datetime(2026, 6, 14, 13, 0, tzinfo=timezone.utc), 66, 76.0),
    (8,  "Austrian Grand Prix",     "Austria",     "Spielberg",   "at-1969",
     datetime(2026, 6, 28, 13, 0, tzinfo=timezone.utc), 71, 68.0),
    (9,  "British Grand Prix",      "UK",          "Silverstone", "gb-1948",
     datetime(2026, 7, 5,  14, 0, tzinfo=timezone.utc), 52, 88.0),
    (10, "Belgian Grand Prix",      "Belgium",     "Spa",         "be-1925",
     datetime(2026, 7, 19, 13, 0, tzinfo=timezone.utc), 44, 106.0),
    (11, "Hungarian Grand Prix",    "Hungary",     "Budapest",    "hu-1986",
     datetime(2026, 7, 26, 13, 0, tzinfo=timezone.utc), 70, 78.0),
    (12, "Dutch Grand Prix",        "Netherlands", "Zandvoort",   "nl-1948",
     datetime(2026, 8, 23, 13, 0, tzinfo=timezone.utc), 72, 72.0),
    (13, "Italian Grand Prix",      "Italy",       "Monza",       "it-1922",
     datetime(2026, 9, 6,  13, 0, tzinfo=timezone.utc), 53, 82.0),
    (14, "Madrid Grand Prix",       "Spain",       "Madrid",      "es-2026",
     datetime(2026, 9, 13, 13, 0, tzinfo=timezone.utc), 57, 92.0),
    (15, "Azerbaijan Grand Prix",   "Azerbaijan",  "Baku",        "az-2016",
     datetime(2026, 9, 26, 11, 0, tzinfo=timezone.utc), 51, 104.0),
    (16, "Singapore Grand Prix",    "Singapore",   "Singapore",   "sg-2008",
     datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc), 62, 95.0),
    (17, "United States Grand Prix", "USA",        "Austin",      "us-2012",
     datetime(2026, 10, 25, 19, 0, tzinfo=timezone.utc), 56, 97.0),
    (18, "Mexico City Grand Prix",  "Mexico",      "Mexico City", "mx-1962",
     datetime(2026, 11, 1, 20, 0, tzinfo=timezone.utc), 71, 79.0),
    (19, "Sao Paulo Grand Prix",    "Brazil",      "Sao Paulo",   "br-1940",
     datetime(2026, 11, 8, 17, 0, tzinfo=timezone.utc), 71, 72.0),
    (20, "Las Vegas Grand Prix",    "USA",         "Las Vegas",   "us-2023",
     datetime(2026, 11, 21, 4, 0, tzinfo=timezone.utc), 50, 95.0),
    (21, "Qatar Grand Prix",        "Qatar",       "Lusail",      "qa-2004",
     datetime(2026, 11, 29, 15, 0, tzinfo=timezone.utc), 57, 85.0),
    (22, "Abu Dhabi Grand Prix",    "UAE",         "Yas Marina",  "ae-2009",
     datetime(2026, 12, 6, 13, 0, tzinfo=timezone.utc), 58, 86.0),
]

SESSION_KEY_BASE = 9000          # session_key = SESSION_KEY_BASE + round
MEETING_KEY_BASE = 1900


def session_key(round_no: int) -> int:
    return SESSION_KEY_BASE + round_no


def round_of(sk: int) -> int | None:
    r = sk - SESSION_KEY_BASE
    return r if 1 <= r <= len(CALENDAR) else None


def event(round_no: int) -> tuple | None:
    for row in CALENDAR:
        if row[0] == round_no:
            return row
    return None


# --- Грид сезона-2026: номер, акроним, имя, команда, цвет (формат OpenF1) ---
# 11 команд, 22 машины. Норрис под первым номером как действующий чемпион,
# Audi (на месте Sauber) и Cadillac — дебютанты сезона.
DRIVERS: list[tuple[int, str, str, str, str]] = [
    (1,  "NOR", "Lando Norris",       "McLaren",         "FF8000"),
    (81, "PIA", "Oscar Piastri",      "McLaren",         "FF8000"),
    (3,  "VER", "Max Verstappen",     "Red Bull Racing", "3671C6"),
    (6,  "HAD", "Isack Hadjar",       "Red Bull Racing", "3671C6"),
    (16, "LEC", "Charles Leclerc",    "Ferrari",         "E8002D"),
    (44, "HAM", "Lewis Hamilton",     "Ferrari",         "E8002D"),
    (63, "RUS", "George Russell",     "Mercedes",        "27F4D2"),
    (12, "ANT", "Kimi Antonelli",     "Mercedes",        "27F4D2"),
    (55, "SAI", "Carlos Sainz",       "Williams",        "64C4FF"),
    (23, "ALB", "Alexander Albon",    "Williams",        "64C4FF"),
    (30, "LAW", "Liam Lawson",        "Racing Bulls",    "6692FF"),
    (41, "LIN", "Arvid Lindblad",     "Racing Bulls",    "6692FF"),
    (14, "ALO", "Fernando Alonso",    "Aston Martin",    "229971"),
    (18, "STR", "Lance Stroll",       "Aston Martin",    "229971"),
    (27, "HUL", "Nico Hulkenberg",    "Audi",            "BB0A30"),
    (5,  "BOR", "Gabriel Bortoleto",  "Audi",            "BB0A30"),
    (10, "GAS", "Pierre Gasly",       "Alpine",          "0093CC"),
    (43, "COL", "Franco Colapinto",   "Alpine",          "0093CC"),
    (31, "OCO", "Esteban Ocon",       "Haas F1 Team",    "B6BABD"),
    (87, "BEA", "Oliver Bearman",     "Haas F1 Team",    "B6BABD"),
    (11, "PER", "Sergio Perez",       "Cadillac",        "C9A24B"),
    (77, "BOT", "Valtteri Bottas",    "Cadillac",        "C9A24B"),
]
