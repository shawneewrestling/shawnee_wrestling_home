#!/usr/bin/env python3
"""2019-20 archive duals must match Trackwrestling capture (coaching 14-11)."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SEASON = ROOT / "data" / "seasons" / "2019-20"
CSV_PATH = SEASON / "tw_schedule.csv"
TW_FALLBACK = Path("/workspace/shawnee/tw_capture/2019-20/schedule.csv")
TOURN_PATH = SEASON / "tw_tournaments.txt"


def load_tw_duals():
    src = CSV_PATH if CSV_PATH.exists() else TW_FALLBACK
    rows = []
    with src.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(line for line in f if not line.startswith("#")):
            if row.get("date") and row.get("opponent"):
                rows.append(row)
    return rows


def main() -> int:
    tw = load_tw_duals()
    assert len(tw) == 25, len(tw)

    results = json.loads((SEASON / "results.json").read_text(encoding="utf-8"))
    schedule = json.loads((SEASON / "schedule.json").read_text(encoding="utf-8"))
    standings = json.loads((SEASON / "standings.json").read_text(encoding="utf-8"))
    meta = json.loads((SEASON / "meta.json").read_text(encoding="utf-8"))
    index = json.loads((ROOT / "data" / "seasons" / "index.json").read_text(encoding="utf-8"))

    rows = results.get("rows") or []
    assert len(rows) == 25, len(rows)
    assert results.get("shawnee_dual_record") == "14-11"
    assert meta.get("coaching_mismatch") is None
    assert meta.get("coaching_history_record") == "14-11"
    assert meta.get("dual_record") == "14-11"
    assert not any(m.get("season") == "2019-20" for m in (index.get("coaching_mismatches") or []))

    pf = pa = 0
    w = l = 0
    for i, (tw_row, r) in enumerate(zip(tw, rows)):
        assert r["date_iso"] == tw_row["date"].strip(), (i, r["date_iso"], tw_row["date"])
        assert int(r["score_shawnee"]) == int(tw_row["shawnee"])
        assert int(r["score_opp"]) == int(tw_row["opp"])
        assert r["result"] == tw_row["result"].strip().upper()
        event = (tw_row.get("event") or "").strip() or None
        assert r.get("event_name") == event, (r.get("opponent"), r.get("event_name"), event)
        # Quad/tri splits keep event name
        if event:
            assert r.get("event_name")
        sh, opp = int(r["score_shawnee"]), int(r["score_opp"])
        pf += sh
        pa += opp
        if r["result"] == "W":
            w += 1
        elif r["result"] == "L":
            l += 1
        assert r.get("cumulative_record") == f"{w}-{l}"

    assert pf == 1004 and pa == 767, (pf, pa)
    assert f"{w}-{l}" == "14-11"
    assert results["summary"]["pf"] == 1004
    assert results["summary"]["pa"] == 767
    assert schedule["pf"] == 1004 and schedule["pa"] == 767
    assert schedule["dual_record"] == "14-11"
    assert schedule.get("home_record") in (None, "")
    assert schedule.get("away_record") in (None, "")

    duals = [e for e in schedule["schedule"] if e.get("event_kind") == "D"]
    tournaments = [e for e in schedule["schedule"] if e.get("event_kind") == "T"]
    assert len(duals) == 25
    assert len(tournaments) == 10
    # event names preserved on multi-meet duals
    named = [e for e in duals if e.get("event_name")]
    assert len(named) >= 15
    names = {t.get("event_name") for t in tournaments}
    assert "Pine Barrens" in names
    assert "NJSIAA District 25" in names
    assert "NJSIAA Region 7" in names
    assert "NJSIAA State Championships" in names
    assert "Sam Cali Invitational" in names
    # tournaments not on Results
    assert all(r.get("event_kind") != "T" for r in rows)

    # Standings Shawnee line
    shawnee = None
    for div in standings.get("divisions") or []:
        for team in div.get("teams") or []:
            if team.get("is_shawnee"):
                shawnee = team
                break
    assert shawnee, "Shawnee standings line missing"
    assert shawnee["overall_record"] == "14-11"
    assert shawnee["pf"] == 1004 and shawnee["pa"] == 767
    assert abs(float(shawnee["overall_pct"]) - (14 / 25)) < 0.001
    assert shawnee.get("home_record") in (None, "")
    assert shawnee.get("away_record") in (None, "")
    # NJ.com Olympic table existed — keep Div
    assert shawnee.get("division_record") == "3-3"
    assert shawnee.get("division_pct") == 0.5
    # Conference peers still present
    assert len(standings.get("divisions") or []) >= 2

    print(f"OK 2019-20 TW duals=25 record=14-11 PF={pf} PA={pa} coaching_mismatch=cleared div=3-3")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        raise
