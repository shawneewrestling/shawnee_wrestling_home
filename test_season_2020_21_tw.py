#!/usr/bin/env python3
"""2020-21 archive duals must match Trackwrestling capture (coaching 5-7)."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SEASON = ROOT / "data" / "seasons" / "2020-21"
CSV_PATH = SEASON / "tw_schedule.csv"
TW_FALLBACK = Path("/workspace/shawnee/tw_capture/2020-21/schedule.csv")


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
    assert len(tw) == 12, len(tw)

    results = json.loads((SEASON / "results.json").read_text(encoding="utf-8"))
    schedule = json.loads((SEASON / "schedule.json").read_text(encoding="utf-8"))
    standings = json.loads((SEASON / "standings.json").read_text(encoding="utf-8"))
    meta = json.loads((SEASON / "meta.json").read_text(encoding="utf-8"))
    index = json.loads((ROOT / "data" / "seasons" / "index.json").read_text(encoding="utf-8"))

    rows = results.get("rows") or []
    assert len(rows) == 12, len(rows)
    assert results.get("shawnee_dual_record") == "5-7"
    assert meta.get("coaching_mismatch") is None
    assert meta.get("coaching_history_record") == "5-7"
    assert meta.get("dual_record") == "5-7"
    assert not any(m.get("season") == "2020-21" for m in (index.get("coaching_mismatches") or []))

    pf = pa = 0
    w = l = 0
    for i, (tw_row, r) in enumerate(zip(tw, rows)):
        assert r["date_iso"] == tw_row["date"].strip(), (i, r, tw_row)
        assert int(r["score_shawnee"]) == int(tw_row["shawnee"])
        assert int(r["score_opp"]) == int(tw_row["opp"])
        assert r["result"] == tw_row["result"].strip().upper()
        # Location detail omitted when unknown
        assert not r.get("home_away"), r
        assert not r.get("location"), r
        assert not r.get("location_display"), r
        sh, opp = int(r["score_shawnee"]), int(r["score_opp"])
        pf += sh
        pa += opp
        if r["result"] == "W":
            w += 1
        elif r["result"] == "L":
            l += 1
        assert r.get("cumulative_record") == f"{w}-{l}"

    assert pf == 422 and pa == 457, (pf, pa)
    assert f"{w}-{l}" == "5-7"
    assert results["summary"]["pf"] == 422
    assert results["summary"]["pa"] == 457
    assert schedule["pf"] == 422 and schedule["pa"] == 457
    assert schedule["dual_record"] == "5-7"
    assert schedule.get("home_record") in (None, "")
    assert schedule.get("away_record") in (None, "")

    duals = [e for e in schedule["schedule"] if e.get("event_kind") == "D"]
    tournaments = [e for e in schedule["schedule"] if e.get("event_kind") == "T"]
    assert len(duals) == 12
    assert len(tournaments) == 2
    names = {t.get("event_name") for t in tournaments}
    assert "NJSIAA Region South" in names
    assert "NJSIAA State Championships" in names
    # tournaments not on Results
    assert all(r.get("event_kind") != "T" for r in rows)

    shawnee = None
    for div in standings.get("divisions") or []:
        for team in div.get("teams") or []:
            if team.get("is_shawnee"):
                shawnee = team
                break
    assert shawnee, "Shawnee standings line missing"
    assert shawnee["overall_record"] == "5-7"
    assert shawnee["pf"] == 422 and shawnee["pa"] == 457
    assert abs(float(shawnee["overall_pct"]) - (5 / 12)) < 0.001
    assert shawnee.get("home_record") in (None, "")
    assert shawnee.get("away_record") in (None, "")
    assert shawnee.get("division_record") in (None, "")

    print(f"OK 2020-21 TW duals=12 record=5-7 PF={pf} PA={pa} coaching_mismatch=cleared")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        raise
