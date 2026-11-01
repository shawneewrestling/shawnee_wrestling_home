#!/usr/bin/env python3
"""Shawnee wrestling coaching history — source seasons + computed rollups.

Season dual records are the source of truth. Win%, team cumulative, coach
cumulative, and coach career win% are computed (never pasted from the sheet).

Championships:
  - League / Districts: from the historic coaching sheet flags
  - Sectional: from data/awards.json Sectional Team Championship years
    (award year N = season ending N, e.g. 2023 → 2022-23), with Packer
    seasons 2021-22 and 2022-23 marked per Jeff.

2024-25 is 12-14-0 (corrected from the sheet's 12-13). 2025-26 is 12-15-0
and must match data/results_ledger.json overall W-L.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
OUT_PATH = ROOT / "data" / "coaching_history.json"
AWARDS_PATH = ROOT / "data" / "awards.json"
LEDGER_PATH = ROOT / "data" / "results_ledger.json"

# Raw seasons: (season, coach, W, L, T, league, districts)
# Sectional is applied separately from awards + Jeff confirmation.
RAW_SEASONS: List[Tuple[str, str, int, int, int, bool, bool]] = [
    ("1970-71", "Bill Neal", 4, 9, 0, False, False),
    ("1971-72", "Bill Neal", 8, 5, 1, False, False),
    ("1972-73", "Bill Neal", 14, 0, 0, True, True),
    ("1973-74", "Bill Neal", 11, 2, 1, True, True),
    ("1974-75", "Bill Neal", 9, 3, 2, False, False),
    ("1975-76", "Bill Neal", 16, 2, 0, False, False),
    ("1976-77", "Bill Neal", 10, 5, 0, False, False),
    ("1977-78", "Bill Neal", 8, 5, 0, False, True),
    ("1978-79", "Bill Neal", 10, 3, 0, False, True),
    ("1979-80", "Roger Pullen", 13, 3, 0, False, False),
    ("1980-81", "Roger Pullen", 7, 9, 0, False, False),
    ("1981-82", "Roger Pullen", 11, 6, 1, False, False),
    ("1982-83", "Roger Pullen", 11, 4, 1, False, True),
    ("1983-84", "Roger Pullen", 8, 4, 0, False, True),
    ("1984-85", "Roger Pullen", 8, 4, 1, False, False),
    ("1985-86", "Roger Pullen", 10, 4, 0, False, True),  # Jeff: 1986 District team title confirmed
    ("1986-87", "Roger Pullen", 10, 5, 0, False, False),
    ("1987-88", "Roger Pullen", 10, 6, 0, False, False),
    ("1988-89", "Roger Pullen", 9, 7, 0, True, False),
    ("1989-90", "Roger Pullen", 10, 6, 1, True, False),
    ("1990-91", "Roger Pullen", 10, 7, 0, False, False),
    ("1991-92", "Roger Pullen", 11, 10, 0, False, False),
    ("1992-93", "Roger Pullen", 11, 3, 0, False, False),
    ("1993-94", "Roger Pullen", 7, 8, 0, False, True),
    ("1994-95", "Roger Pullen", 14, 4, 0, False, False),
    ("1995-96", "Roger Pullen", 12, 3, 0, False, False),
    ("1996-97", "Roger Pullen", 11, 8, 0, False, False),
    ("1997-98", "Roger Pullen", 12, 7, 0, False, False),
    ("1998-99", "Roger Pullen", 14, 5, 0, False, False),
    ("1999-00", "Ron Jensen", 12, 6, 1, False, False),
    ("2000-01", "Ron Jensen", 16, 6, 0, False, False),
    ("2001-02", "Ron Jensen", 9, 11, 0, False, False),
    ("2002-03", "Ron Jensen", 10, 7, 0, False, True),
    ("2003-04", "Tom Mann", 11, 8, 0, False, False),
    ("2004-05", "Tom Mann", 13, 6, 0, False, True),
    ("2005-06", "Tom Mann", 5, 20, 0, False, False),
    ("2006-07", "Tom Mann", 5, 18, 0, False, False),
    ("2007-08", "Tom Mann", 6, 21, 0, False, False),
    ("2008-09", "Tom Mann", 7, 14, 0, False, False),
    ("2009-10", "Tom Mann", 6, 14, 0, False, False),
    ("2010-11", "Tom Mann", 9, 13, 0, False, False),
    ("2011-12", "Tom Mann", 18, 6, 0, True, False),
    ("2012-13", "Tom Mann", 21, 3, 0, True, True),
    ("2013-14", "Tom Mann", 14, 8, 0, False, False),
    ("2014-15", "Tom Mann", 6, 21, 0, False, False),
    ("2015-16", "Tom Mann", 11, 15, 0, False, False),
    ("2016-17", "Tom Mann", 12, 13, 0, False, False),
    ("2017-18", "Tom Mann", 8, 18, 0, False, False),
    ("2018-19", "Tom Mann", 10, 18, 0, False, False),
    ("2019-20", "Kyle Packer", 14, 11, 0, False, False),
    ("2020-21", "Kyle Packer", 5, 7, 0, False, False),
    ("2021-22", "Kyle Packer", 23, 2, 0, False, False),
    ("2022-23", "Kyle Packer", 21, 5, 0, True, False),
    ("2023-24", "Kyle Packer", 15, 10, 0, True, False),
    ("2024-25", "Kyle Packer", 12, 14, 0, False, False),  # corrected from sheet 12-13
    ("2025-26", "Kyle Packer", 12, 15, 0, False, False),
]

# Jeff: Packer sectional titles in these seasons (must agree with awards.json)
JEFF_SECTIONAL_SEASONS = {"2021-22", "2022-23"}

# Optional conference-standings detail (not used for W-L totals)
SEASON_EXTRAS: Dict[str, Dict[str, Any]] = {
    "2024-25": {
        "div_record": "3-2",
        "home_record": "8-6",
        "away_record": "4-8",
        "pf": 925,
        "pa": 946,
        "notes": "Overall corrected to 12-14 from conference standings (sheet had 12-13).",
    },
    "2025-26": {
        "div_record": "2-3",
        "home_record": "8-9",
        "away_record": "4-6",
        "pf": 1032,
        "pa": 907,
        "notes": "Overall must match results_ledger.json (12-15).",
    },
}

EXPECTED_TEAM = (610, 457, 9)
EXPECTED_COACH_CAREER = {
    "Bill Neal": (90, 34, 4, 70.3125),
    "Roger Pullen": (209, 113, 4, 64.11042944785276),  # 209/326
    "Ron Jensen": (47, 30, 1, 60.256410256410255),  # 47/78
    "Tom Mann": (162, 216, 0, 42.857142857142854),  # 162/378
    "Kyle Packer": (102, 64, 0, 61.44578313253012),  # 102/166
}


def win_pct(w: int, l: int, t: int) -> Optional[float]:
    total = w + l + t
    if total <= 0:
        return None
    return 100.0 * w / total


def season_end_year(season: str) -> int:
    """Map '2023-24' → 2024; '1999-00' → 2000."""
    a, b = season.split("-")
    start = int(a)
    end_two = int(b)
    if end_two < 70 and start >= 1970:
        # 1999-00 → 2000, 2019-20 → 2020
        century = (start // 100) * 100
        end = century + end_two
        if end < start:
            end += 100
        return end
    if end_two < 10 and start >= 2000:
        return (start // 100) * 100 + end_two
    # Normal: 1970-71 → 1971, 2024-25 → 2025
    if len(b) == 2:
        century = (start // 100) * 100
        end = century + end_two
        if end < start:
            end += 100
        return end
    return int(b)


def award_year_to_season(year: int) -> str:
    """Award year N (season-ending) → 'YYYY-YY' season label."""
    start = year - 1
    return f"{start}-{str(year)[-2:].zfill(2)}"


def sectional_seasons_from_awards(awards_doc: Dict[str, Any]) -> List[str]:
    years = []
    for a in awards_doc.get("awards") or []:
        if (a.get("award_name") or "") == "Sectional Team Championship":
            try:
                years.append(int(str(a.get("season"))))
            except (TypeError, ValueError):
                continue
    return sorted({award_year_to_season(y) for y in years})


def district_years_from_awards(awards_doc: Dict[str, Any]) -> List[int]:
    years = []
    for a in awards_doc.get("awards") or []:
        if (a.get("award_name") or "") == "District Team Championship":
            try:
                years.append(int(str(a.get("season"))))
            except (TypeError, ValueError):
                continue
    return sorted(set(years))


def league_years_from_awards(awards_doc: Dict[str, Any]) -> List[int]:
    """League / conference team titles in awards (if any)."""
    years = []
    for a in awards_doc.get("awards") or []:
        name = (a.get("award_name") or "").lower()
        if "league" in name or "conference" in name and "team" in name:
            if "sectional" in name:
                continue
            try:
                years.append(int(str(a.get("season"))))
            except (TypeError, ValueError):
                continue
    return sorted(set(years))


def cross_check_awards(
    seasons: List[Dict[str, Any]], awards_doc: Dict[str, Any]
) -> List[str]:
    """Report mismatches; do not change awards."""
    msgs: List[str] = []

    # Districts
    awards_dist = set(district_years_from_awards(awards_doc))
    coach_dist = {season_end_year(s["season"]) for s in seasons if s["championships"]["districts"]}
    only_awards = sorted(awards_dist - coach_dist)
    only_coach = sorted(coach_dist - awards_dist)
    if only_awards:
        msgs.append(
            f"District Team years in awards.json but not flagged in coaching history: {only_awards}"
        )
    if only_coach:
        msgs.append(
            f"District flags in coaching history but missing from awards.json District Team card: {only_coach}"
        )

    # League — awards currently has none under that name
    awards_league = set(league_years_from_awards(awards_doc))
    coach_league = {season_end_year(s["season"]) for s in seasons if s["championships"]["league"]}
    if not awards_league and coach_league:
        msgs.append(
            "awards.json has no League/Conference team championship entries; "
            f"coaching history League flags (end years): {sorted(coach_league)}"
        )
    else:
        only_a = sorted(awards_league - coach_league)
        only_c = sorted(coach_league - awards_league)
        if only_a:
            msgs.append(f"League years in awards but not in coaching history: {only_a}")
        if only_c:
            msgs.append(f"League flags in coaching history missing from awards: {only_c}")

    # Sectional
    awards_sect = set(sectional_seasons_from_awards(awards_doc))
    coach_sect = {s["season"] for s in seasons if s["championships"]["sectional"]}
    jeff = set(JEFF_SECTIONAL_SEASONS)
    if awards_sect != coach_sect:
        msgs.append(
            f"Sectional seasons disagree: awards→{sorted(awards_sect)} coaching→{sorted(coach_sect)}"
        )
    if jeff != awards_sect:
        msgs.append(
            f"Jeff Sectional seasons {sorted(jeff)} vs awards.json Sectional card {sorted(awards_sect)}"
        )
    if jeff != coach_sect:
        msgs.append(
            f"Jeff Sectional seasons {sorted(jeff)} vs coaching flags {sorted(coach_sect)}"
        )

    return msgs


def build(awards_doc: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if awards_doc is None and AWARDS_PATH.exists():
        awards_doc = json.loads(AWARDS_PATH.read_text())
    awards_doc = awards_doc or {"awards": []}

    awards_sect = set(sectional_seasons_from_awards(awards_doc))
    # Prefer intersection of Jeff confirmation + awards; flag both 2021-22 / 2022-23
    sectional = set(JEFF_SECTIONAL_SEASONS) | awards_sect
    # If they agree, sectional == Jeff == awards. If awards has extras, still mark them
    # but cross_check will report. Jeff said mark 2021-22 and 2022-23; awards has those.
    sectional = set(JEFF_SECTIONAL_SEASONS)
    if awards_sect and awards_sect != sectional:
        # Still only mark Jeff's confirmed set in the data; mismatches go to report
        pass

    team_w = team_l = team_t = 0
    coach_cum: Dict[str, Dict[str, int]] = {}
    seasons_out: List[Dict[str, Any]] = []

    for season, coach, w, l, t, league, districts in RAW_SEASONS:
        team_w += w
        team_l += l
        team_t += t
        cc = coach_cum.setdefault(coach, {"w": 0, "l": 0, "t": 0})
        cc["w"] += w
        cc["l"] += l
        cc["t"] += t

        row: Dict[str, Any] = {
            "season": season,
            "season_end_year": season_end_year(season),
            "coach": coach,
            "w": w,
            "l": l,
            "t": t,
            "record": f"{w}-{l}-{t}",
            "win_pct": round(win_pct(w, l, t) or 0.0, 10),
            "team_cumulative": {
                "w": team_w,
                "l": team_l,
                "t": team_t,
                "record": f"{team_w}-{team_l}-{team_t}",
            },
            "coach_cumulative": {
                "w": cc["w"],
                "l": cc["l"],
                "t": cc["t"],
                "record": f"{cc['w']}-{cc['l']}-{cc['t']}",
                "win_pct": round(win_pct(cc["w"], cc["l"], cc["t"]) or 0.0, 10),
            },
            "championships": {
                "league": bool(league),
                "districts": bool(districts),
                "sectional": season in sectional,
            },
        }
        if season in SEASON_EXTRAS:
            row["standings_detail"] = SEASON_EXTRAS[season]
        seasons_out.append(row)

    # Coach summary cards
    coaches: List[Dict[str, Any]] = []
    order: List[str] = []
    for s in seasons_out:
        if s["coach"] not in order:
            order.append(s["coach"])
    for name in order:
        rows = [s for s in seasons_out if s["coach"] == name]
        last = rows[-1]
        cw, cl, ct = last["coach_cumulative"]["w"], last["coach_cumulative"]["l"], last["coach_cumulative"]["t"]
        coaches.append(
            {
                "name": name,
                "first_season": rows[0]["season"],
                "last_season": rows[-1]["season"],
                "seasons": len(rows),
                "w": cw,
                "l": cl,
                "t": ct,
                "record": f"{cw}-{cl}-{ct}",
                "win_pct": round(win_pct(cw, cl, ct) or 0.0, 10),
                "titles": {
                    "league": sum(1 for r in rows if r["championships"]["league"]),
                    "districts": sum(1 for r in rows if r["championships"]["districts"]),
                    "sectional": sum(1 for r in rows if r["championships"]["sectional"]),
                },
            }
        )

    mismatches = cross_check_awards(seasons_out, awards_doc)

    # Ledger check for current season
    ledger_note = None
    if LEDGER_PATH.exists():
        ledger = json.loads(LEDGER_PATH.read_text())
        overall = (ledger.get("summary") or {}).get("overall") or {}
        cur = next(s for s in seasons_out if s["season"] == "2025-26")
        lw, ll = int(overall.get("wins", -1)), int(overall.get("losses", -1))
        if (cur["w"], cur["l"]) != (lw, ll):
            mismatches.append(
                f"2025-26 coaching record {cur['w']}-{cur['l']} != results_ledger overall {lw}-{ll}"
            )
            ledger_note = "mismatch"
        else:
            ledger_note = f"matches results_ledger overall {lw}-{ll}"

    doc = {
        "schema_version": 1,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes": [
            "Win% = W / (W+L+T), computed in code.",
            "2024-25 overall is 12-14-0 (corrected from historic sheet 12-13).",
            "Sectional titles sourced from awards.json Sectional Team Championship + Jeff confirmation (2021-22, 2022-23).",
            "District 1985-86 (Roger Pullen) flagged after Jeff confirmed 1986 District team title (already on awards banner).",
            "Never display Trackwrestling or internal IDs on the page.",
        ],
        "team_all_time": {
            "w": team_w,
            "l": team_l,
            "t": team_t,
            "record": f"{team_w}-{team_l}-{team_t}",
            "win_pct": round(win_pct(team_w, team_l, team_t) or 0.0, 10),
        },
        "coaches": coaches,
        "seasons": seasons_out,
        "validation": {
            "expected_team_all_time": {"w": 610, "l": 457, "t": 9},
            "team_matches_expected": (team_w, team_l, team_t) == EXPECTED_TEAM,
            "awards_cross_check": mismatches,
            "results_ledger_2025_26": ledger_note,
            "sectional_seasons": sorted(sectional),
            "sectional_from_awards": sorted(awards_sect),
            "jeff_sectional_seasons": sorted(JEFF_SECTIONAL_SEASONS),
            "sectional_agrees_with_awards": set(JEFF_SECTIONAL_SEASONS) == awards_sect,
        },
    }
    return doc


def write(doc: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    doc = doc or build()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(doc, indent=2) + "\n")
    return doc


def main() -> int:
    doc = write()
    t = doc["team_all_time"]
    print(f"Wrote {OUT_PATH} team={t['record']} coaches={len(doc['coaches'])} seasons={len(doc['seasons'])}")
    for m in doc["validation"]["awards_cross_check"]:
        print(f"CROSS-CHECK: {m}")
    v = doc["validation"]
    print(f"Sectional awards={v['sectional_from_awards']} jeff={v['jeff_sectional_seasons']} agree={v['sectional_agrees_with_awards']}")
    print(f"Ledger 2025-26: {v['results_ledger_2025_26']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
