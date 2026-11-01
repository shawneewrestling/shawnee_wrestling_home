#!/usr/bin/env python3
"""Unit tests for tw.parsers (no network)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from tw.parsers import (  # noqa: E402
    parse_schedule_rows,
    parse_wrestlers,
    find_shawnee_team,
    build_dual_scores,
    parse_win_types_capture,
    merge_win_types_into_roster,
    parse_placements_capture,
)


def test_parse_schedule_home_and_away_scores():
    rows = [
        # Home dual Cherry Hill West 57-11
        [
            "8715041132", "0", "Cherry Hill  West, NJ @ Shawnee, NJ", "20251217", "1730",
            "20251217", "31", "Y", "1560213138", "N", "", "", "H", "", None, "1",
            "Shawnee", "NJ", "57", "Cherry Hill  West", "NJ", "11",
            "Y", "N", "", "", "", "S", "", "", "", "", "", "", None, "36", "Varsity",
            "768996150,768791150", "", "",
        ],
        # Away dual Northern Burlington — Shawnee loses 29-47
        [
            "8715992132", "0", "Shawnee, NJ @ Northern  Burlington ( Columbus), NJ",
            "20260106", "1800", "20260106", "31", "Y", "1560213138", "N", "", "", "A",
            "", None, "1", "Northern  Burlington ( Columbus)", "NJ", "47", "Shawnee",
            "NJ", "29", "Y", "Y", "", "", "", "S", "", "", "", "", "", "", None, "36",
            "Varsity", "768932150,768996150", "", "",
        ],
        # Tournament — no dual score columns
        [
            "8978282132", "1", "NJSIAA District 28", "20260228", "0900", "20260228",
            "31", "Y", "1560213138", "", "", "", "E", "", "", "", "Shawnee", "NJ",
            "", "", "", "", "N", "", None, None, "", "E", None, None, "", "", None,
            "", "", "", "Varsity", "768996150", "", "",
        ],
    ]
    sched = parse_schedule_rows(rows)
    assert len(sched) == 3
    home = sched[0]
    assert home["home_away"] == "home"
    assert home["opponent"] == "Cherry Hill West" or "Cherry Hill" in home["opponent"]
    assert home["score_shawnee"] == 57 and home["score_opp"] == 11 and home["result"] == "W"
    away = sched[1]
    assert away["home_away"] == "away"
    assert away["score_shawnee"] == 29 and away["score_opp"] == 47 and away["result"] == "L"
    assert "Northern" in (away["opponent"] or "")
    assert sched[2]["home_away"] == "event"
    dual = build_dual_scores(sched)
    assert dual["wins"] == 1 and dual["losses"] == 1
    assert dual["record"] == "1-1"


def test_parse_wrestlers_wl():
    rows = [[
        "35008201132", None, "Jordan", "Segal", "768996150", "Shawnee", "SHAW", "31",
        "x", "126", "14", "Sr.", None, None, None, None, None, "29", "7", "0.8056", "M",
    ]]
    roster = parse_wrestlers(rows)
    assert len(roster) == 1
    assert roster[0]["name"] == "Jordan Segal"
    assert roster[0]["wins"] == 29 and roster[0]["losses"] == 7
    assert roster[0]["pins"] is None


def test_find_shawnee_medford():
    teams = [
        ["1", "Shawnee", "OK", "X", "Other", None, "99", None, None, None, "Y", "1",
         "OTHER", "Shawnee HS", "1 Main", "Shawnee", "74801", "N"],
        ["768996150", "Shawnee", "NJ", "SHAW", "NJSIAA", "NJ District 28", "36",
         "x", "Shawnee", "NJ", "Y", "31", "NJSIAA", "Shawnee High School",
         "600 Tabernacle Road", "Medford", "08055", "Y"],
    ]
    hit = find_shawnee_team(teams, city_hint="Medford")
    assert hit["team_id"] == "768996150"
    assert hit["city"] == "Medford"


def test_win_types_tsv_and_merge():
    text = "Wrestler\tFall\tTech\tMajor\tDec\nJordan Segal\t12\t3\t2\t8\n"
    wt = parse_win_types_capture(text)
    assert wt[0]["name"] == "Jordan Segal"
    assert wt[0]["pins"] == 12 and wt[0]["tech_falls"] == 3
    roster = [{"name": "Jordan Segal", "wins": 29, "losses": 7, "pins": None}]
    merged = merge_win_types_into_roster(roster, wt)
    assert merged[0]["pins"] == 12


def test_win_types_html_table():
    html = """
    <table>
      <tr><th>Wrestler</th><th>Fall</th><th>Tech Fall</th><th>Major</th><th>Decision</th></tr>
      <tr><td>Max Spitznas</td><td>10</td><td>1</td><td>4</td><td>9</td></tr>
    </table>
    """
    wt = parse_win_types_capture(html)
    assert len(wt) == 1
    assert wt[0]["name"] == "Max Spitznas"
    assert wt[0]["pins"] == 10


def test_placements_lines():
    text = "Jordan Segal 126 1st\nMatt Hart — 106 — 3rd place\n"
    rows = parse_placements_capture(text, "district")
    assert any(r["name"] == "Jordan Segal" and r["place"] == 1 for r in rows)
    assert any("Hart" in r["name"] and r["place"] == 3 for r in rows)


def test_season_config_load():
    from season_config import load_season, SEASON_ID, TEAM_ID, CURRENT_SEASON
    cfg = load_season("2025-26")
    assert cfg["season_id"] == "1560212138"
    assert cfg["team_id"] == "768996150"
    # Module aliases track the live/current season (2026-27 after rollover)
    assert CURRENT_SEASON == "2026-27"
    assert SEASON_ID == "95515140"
    assert TEAM_ID == "1912611150"
    cur = load_season("2026-27")
    assert cur["season_id"] == SEASON_ID
    assert cur["team_id"] == TEAM_ID


def main():
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    if failed:
        raise SystemExit(1)
    print(f"OK {len(tests)} tests")


if __name__ == "__main__":
    main()
