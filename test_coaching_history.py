#!/usr/bin/env python3
"""Assert coaching history totals, win%, and sectional flags.

  python test_coaching_history.py
  python test_coaching_history.py --rebuild
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from coaching_history import (  # noqa: E402
    EXPECTED_COACH_CAREER,
    EXPECTED_TEAM,
    JEFF_SECTIONAL_SEASONS,
    OUT_PATH,
    build,
    win_pct,
    write,
)


def approx(a: float, b: float, tol: float = 1e-6) -> bool:
    return abs(a - b) <= tol


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true")
    args = ap.parse_args()

    doc = write() if args.rebuild or not OUT_PATH.exists() else build()
    if args.rebuild or not OUT_PATH.exists():
        pass
    else:
        # Prefer recomputed build for assertions; refresh file if stale
        on_disk = json.loads(OUT_PATH.read_text())
        if on_disk.get("team_all_time") != doc.get("team_all_time"):
            write(doc)

    errors: list[str] = []

    tw, tl, tt = doc["team_all_time"]["w"], doc["team_all_time"]["l"], doc["team_all_time"]["t"]
    if (tw, tl, tt) != EXPECTED_TEAM:
        errors.append(f"team all-time {(tw, tl, tt)} != {EXPECTED_TEAM}")

    # 1971-72 win% sample from source sheet
    s7172 = next(s for s in doc["seasons"] if s["season"] == "1971-72")
    if not approx(s7172["win_pct"], 100 * 8 / 14):
        errors.append(f"1971-72 win% {s7172['win_pct']} != {100 * 8 / 14}")

    for name, (w, l, t, pct) in EXPECTED_COACH_CAREER.items():
        c = next((x for x in doc["coaches"] if x["name"] == name), None)
        if not c:
            errors.append(f"missing coach {name}")
            continue
        if (c["w"], c["l"], c["t"]) != (w, l, t):
            errors.append(f"{name} record {(c['w'], c['l'], c['t'])} != {(w, l, t)}")
        if not approx(c["win_pct"], pct, tol=0.02):  # allow hundredths display drift
            errors.append(f"{name} win% {c['win_pct']} != {pct}")
        # Source-sheet rounded career %
        rounded = {
            "Bill Neal": 70.31,
            "Roger Pullen": 64.11,
            "Ron Jensen": 60.26,
            "Tom Mann": 42.86,
        }
        if name in rounded and round(c["win_pct"], 2) != rounded[name]:
            errors.append(f"{name} rounded win% {round(c['win_pct'], 2)} != {rounded[name]}")

    # Sectional
    sect = {s["season"] for s in doc["seasons"] if s["championships"]["sectional"]}
    if sect != set(JEFF_SECTIONAL_SEASONS):
        errors.append(f"sectional seasons {sorted(sect)} != {sorted(JEFF_SECTIONAL_SEASONS)}")
    packer = next(c for c in doc["coaches"] if c["name"] == "Kyle Packer")
    if packer["titles"]["sectional"] != 2:
        errors.append(f"Packer sectional count {packer['titles']['sectional']} != 2")

    # 2024-25 correction + 2025-26 ledger
    s2425 = next(s for s in doc["seasons"] if s["season"] == "2024-25")
    if (s2425["w"], s2425["l"], s2425["t"]) != (12, 14, 0):
        errors.append(f"2024-25 {(s2425['w'], s2425['l'], s2425['t'])} != (12,14,0)")
    s2526 = next(s for s in doc["seasons"] if s["season"] == "2025-26")
    if (s2526["w"], s2526["l"], s2526["t"]) != (12, 15, 0):
        errors.append(f"2025-26 {(s2526['w'], s2526['l'], s2526['t'])} != (12,15,0)")

    v = doc["validation"]
    if not v.get("team_matches_expected"):
        errors.append("validation.team_matches_expected is false")
    if not v.get("sectional_agrees_with_awards"):
        errors.append(
            f"Sectional disagrees with awards.json: awards={v.get('sectional_from_awards')} jeff={v.get('jeff_sectional_seasons')}"
        )
    if v.get("results_ledger_2025_26") and str(v["results_ledger_2025_26"]).startswith("mismatch"):
        errors.append(str(v["results_ledger_2025_26"]))

    # Cumulative integrity: last season team cum == all-time
    last = doc["seasons"][-1]
    if last["team_cumulative"]["record"] != doc["team_all_time"]["record"]:
        errors.append("last season team_cumulative != team_all_time")

    # Recompute win% from scratch for every row
    tw = tl = tt = 0
    cc: dict = {}
    for s in doc["seasons"]:
        tw += s["w"]
        tl += s["l"]
        tt += s["t"]
        c = cc.setdefault(s["coach"], {"w": 0, "l": 0, "t": 0})
        c["w"] += s["w"]
        c["l"] += s["l"]
        c["t"] += s["t"]
        exp = win_pct(s["w"], s["l"], s["t"])
        if not approx(s["win_pct"], exp or 0.0):
            errors.append(f"{s['season']} win% stored {s['win_pct']} != {exp}")
        if s["team_cumulative"]["w"] != tw or s["coach_cumulative"]["w"] != c["w"]:
            errors.append(f"{s['season']} cumulative drift")

    if errors:
        print("FAIL", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        for m in v.get("awards_cross_check") or []:
            print(f"  NOTE {m}", file=sys.stderr)
        return 1

    print(
        f"OK team={doc['team_all_time']['record']} "
        f"packer={packer['record']} sectional={sorted(sect)} "
        f"cross_check_notes={len(v.get('awards_cross_check') or [])}"
    )
    for m in v.get("awards_cross_check") or []:
        print(f"NOTE: {m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
