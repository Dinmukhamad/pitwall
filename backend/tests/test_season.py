"""Разбор ответов Jolpica-F1 (схема Ergast) — без сети, на образцах."""
from __future__ import annotations

import os
from datetime import datetime, timezone

os.environ.setdefault("PITWALL_DATA_SOURCE", "fixture")

from app.season.jolpica import (  # noqa: E402
    assemble, parse_constructor_standings, parse_driver_standings,
)
from app.season.teams import team_colour  # noqa: E402

NOW = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)

CALENDAR = {"MRData": {"RaceTable": {"season": "2024", "Races": [
    {"round": "1", "raceName": "Bahrain Grand Prix", "date": "2024-03-02", "time": "15:00:00Z",
     "Circuit": {"circuitName": "Bahrain International Circuit",
                 "Location": {"locality": "Sakhir", "country": "Bahrain"}}},
    {"round": "2", "raceName": "Monaco Grand Prix", "date": "2024-05-26", "time": "13:00:00Z",
     "Circuit": {"circuitName": "Circuit de Monaco",
                 "Location": {"locality": "Monte-Carlo", "country": "Monaco"}}},
    {"round": "3", "raceName": "Canadian Grand Prix", "date": "2024-06-09", "time": "18:00:00Z",
     "Circuit": {"circuitName": "Circuit Gilles Villeneuve",
                 "Location": {"locality": "Montreal", "country": "Canada"}}},
    {"round": "4", "raceName": "Spanish Grand Prix", "date": "2024-06-23", "time": "13:00:00Z",
     "Circuit": {"circuitName": "Circuit de Barcelona-Catalunya",
                 "Location": {"locality": "Montmeló", "country": "Spain"}}},
]}}}

DRIVERS = {"MRData": {"StandingsTable": {"StandingsLists": [{"DriverStandings": [
    {"position": "1", "points": "169", "wins": "5",
     "Driver": {"code": "VER", "givenName": "Max", "familyName": "Verstappen"},
     "Constructors": [{"constructorId": "red_bull", "name": "Red Bull"}]},
    {"position": "2", "points": "113", "wins": "1",
     "Driver": {"code": "LEC", "givenName": "Charles", "familyName": "Leclerc"},
     "Constructors": [{"constructorId": "ferrari", "name": "Ferrari"}]},
    {"position": "3", "points": "83", "wins": "0",
     # без кода — акроним должен вывестись из фамилии
     "Driver": {"givenName": "Oscar", "familyName": "Piastri"},
     "Constructors": [{"constructorId": "mclaren", "name": "McLaren"}]},
]}]}}}

CONSTRUCTORS = {"MRData": {"StandingsTable": {"StandingsLists": [{"ConstructorStandings": [
    {"position": "1", "points": "276", "wins": "6",
     "Constructor": {"constructorId": "red_bull", "name": "Red Bull"}},
    {"position": "2", "points": "212", "wins": "1",
     "Constructor": {"constructorId": "ferrari", "name": "Ferrari"}},
]}]}}}


def test_calendar_splits_past_and_next():
    o = assemble(CALENDAR, DRIVERS, CONSTRUCTORS, NOW)
    assert o.season == "2024"
    assert o.races_total == 4
    # Бахрейн и Монако позади, Канада — следующая.
    assert o.races_done == 2
    assert o.next_race is not None
    assert o.next_race.round == 3
    assert o.next_race.name == "Canadian Grand Prix"
    assert sum(1 for e in o.calendar if e.is_next) == 1
    assert o.days_to_next is not None and 7 <= o.days_to_next <= 9


def test_standings_parsed_with_team_colours():
    drivers = parse_driver_standings(DRIVERS)
    assert [d.code for d in drivers] == ["VER", "LEC", "PIA"]   # PIA выведен из фамилии
    assert drivers[0].points == 169.0 and drivers[0].wins == 5
    assert drivers[0].full_name == "Max Verstappen"
    assert drivers[0].team_colour == "3671C6"                    # Red Bull

    teams = parse_constructor_standings(CONSTRUCTORS)
    assert [t.name for t in teams] == ["Red Bull", "Ferrari"]
    assert teams[1].team_colour == "E8002D"


def test_team_colour_fallbacks():
    assert team_colour("mclaren", None) == "FF8000"
    assert team_colour(None, "Scuderia Ferrari") == "E8002D"     # по названию
    assert team_colour("unknown_team", "Nonexistent") == "8A9099"  # нейтральный


def test_empty_payloads_do_not_crash():
    o = assemble({}, {}, {}, NOW)
    assert o.races_total == 0 and o.drivers == [] and o.constructors == []
    assert o.next_race is None


def test_season_finished_has_no_next_race():
    """Когда все этапы позади, следующей гонки нет — а не 'первая по кругу'."""
    later = datetime(2025, 1, 1, tzinfo=timezone.utc)
    o = assemble(CALENDAR, DRIVERS, CONSTRUCTORS, later)
    assert o.races_done == o.races_total == 4
    assert o.next_race is None and o.days_to_next is None
