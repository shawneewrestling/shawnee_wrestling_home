#!/usr/bin/env python3
"""Apply W/L type + team_points breakdown from schedule tournament_results.

Only wrestlers whose captured non-bye W-L exactly matches Trackwrestling season
W-L receive breakdown fields. Writes:
  - data/history/<season>_stats.json (+ seasons mirror)
  - data/history/<season>_breakdown_coverage.json
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
HISTORY = ROOT / "data" / "history"
STAT_KEYS = [
    "w_fall", "w_tech", "w_maj", "w_dec", "w_sv", "w_tb", "w_ff", "w_inj", "w_dq",
    "l_fall", "l_tech", "l_maj", "l_dec", "l_sv", "l_tb", "l_ff", "l_inj", "l_dq",
]
WIN_PTS = {
    "fall": 6, "tech": 5, "maj": 4, "dec": 3, "sv": 3, "tb": 3,
    "ff": 6, "inj": 6, "dq": 6,
}


def nk(n: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9]+", "", (n or "").lower())


def classify(win_type: Any, score: Any = None) -> str:
    raw = " ".join(filter(None, [str(win_type or ""), str(score or "")])).lower()
    if "bye" in raw:
        return "bye"
    if "tech" in raw or re.search(r"\btf\b", raw):
        return "tech"
    if "maj" in raw or re.search(r"\bmd\b", raw):
        return "maj"
    if "fall" in raw or "pin" in raw:
        return "fall"
    if "forfeit" in raw or re.search(r"\bff\b", raw) or "fft" in raw:
        return "ff"
    if "inj" in raw:
        return "inj"
    if "dq" in raw or "disq" in raw:
        return "dq"
    if "sv" in raw or "sudden" in raw:
        return "sv"
    if "tb" in raw or "tie break" in raw or "tiebreak" in raw:
        return "tb"
    if "dec" in raw or "decision" in raw:
        return "dec"
    if re.search(r"\d+\s*-\s*\d+", raw):
        return "dec"
    return "dec"


def load_bout_points(season: str) -> Dict[Tuple[str, str, str], float]:
    path = HISTORY / f"{season}_bouts.json"
    out: Dict[Tuple[str, str, str], float] = {}
    if not path.exists():
        return out
    doc = json.loads(path.read_text())
    for _eid, ev in (doc.get("events") or {}).items():
        for b in ev.get("bouts") or []:
            name = b.get("shawnee_wrestler")
            if not name or b.get("dual_points") is None:
                continue
            key = (
                nk(name),
                nk(b.get("opponent_wrestler") or b.get("opponent")),
                (b.get("result") or "").upper(),
            )
            try:
                out[key] = float(b["dual_points"])
            except (TypeError, ValueError):
                pass
    return out


def aggregate(season: str) -> Dict[str, Dict[str, Any]]:
    sched_path = ROOT / "data" / "seasons" / season / "schedule.json"
    if not sched_path.exists():
        raise SystemExit(f"missing {sched_path}")
    sched = json.loads(sched_path.read_text())
    tr = sched.get("tournament_results") or {}
    bout_pts = load_bout_points(season)
    agg: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {k: 0 for k in STAT_KEYS + ["w", "l", "byes", "points"]}
    )
    events_map: Dict[str, set] = defaultdict(set)
    for eid, ev in tr.items():
        for w in ev.get("wrestlers") or []:
            name = w.get("wrestler") or w.get("name")
            if not name:
                continue
            key = nk(name)
            a = agg[key]
            a["_name"] = name
            for b in w.get("bouts") or []:
                kind = classify(b.get("win_type"), b.get("score"))
                res = (b.get("result") or "").upper()
                if kind == "bye" or res not in ("W", "L"):
                    if kind == "bye":
                        a["byes"] += 1
                    continue
                events_map[key].add(str(eid))
                opp = b.get("opponent_wrestler") or b.get("opponent")
                pts = bout_pts.get((key, nk(opp), res))
                if res == "W":
                    a["w"] += 1
                    field = "w_" + kind
                    if field not in a:
                        field = "w_dec"
                    a[field] += 1
                    a["points"] += float(pts if pts is not None else WIN_PTS.get(kind, 3))
                else:
                    a["l"] += 1
                    field = "l_" + kind
                    if field not in a:
                        field = "l_dec"
                    a[field] += 1
    for key, a in agg.items():
        a["_events"] = sorted(events_map.get(key) or [])
    return agg


def enrich(season: str) -> Dict[str, Any]:
    stats_path = HISTORY / f"{season}_stats.json"
    stats = json.loads(stats_path.read_text())
    agg = aggregate(season)
    complete: List[Dict[str, Any]] = []
    incomplete: List[Dict[str, Any]] = []
    no_bouts: List[Dict[str, Any]] = []
    any_complete = False
    for w in stats.get("wrestlers") or []:
        key = nk(w.get("name"))
        tw_w = int(w.get("win") if w.get("win") is not None else w.get("wins") or 0)
        tw_l = int(w.get("loss") if w.get("loss") is not None else w.get("losses") or 0)
        a = agg.get(key)
        for k in STAT_KEYS + ["team_points", "points", "has_capture_breakdown"]:
            w.pop(k, None)
        if not a or (a["w"] + a["l"] == 0):
            if tw_w + tw_l >= 1:
                no_bouts.append({"name": w.get("name"), "tw_record": f"{tw_w}-{tw_l}"})
            continue
        if a["w"] == tw_w and a["l"] == tw_l:
            any_complete = True
            for k in STAT_KEYS:
                w[k] = a[k]
            tp = a["points"]
            w["team_points"] = int(tp) if float(tp) == int(tp) else tp
            w["points"] = w["team_points"]
            w["pins"] = a["w_fall"]
            w["has_capture_breakdown"] = True
            complete.append({
                "name": w.get("name"),
                "record": f"{tw_w}-{tw_l}",
                "team_points": w["team_points"],
                "breakdown": {k: a[k] for k in STAT_KEYS if a[k]},
            })
        else:
            incomplete.append({
                "name": w.get("name"),
                "tw_record": f"{tw_w}-{tw_l}",
                "captured_record": f"{a['w']}-{a['l']}",
                "byes_skipped": a["byes"],
                "delta_w": a["w"] - tw_w,
                "delta_l": a["l"] - tw_l,
                "events_with_bouts": a.get("_events") or [],
            })
    stats["has_breakdown"] = bool(any_complete)
    stats["breakdown_source"] = "capture_exact_match"
    stats["count"] = len(stats.get("wrestlers") or [])
    out = json.dumps(stats, indent=2, ensure_ascii=False) + "\n"
    stats_path.write_text(out)
    season_mirror = ROOT / "data" / "seasons" / season / "stats.json"
    if season_mirror.parent.exists():
        season_mirror.write_text(out)
    cov = {
        "season": season,
        "complete": complete,
        "incomplete": incomplete,
        "no_bouts": no_bouts,
        "summary": {
            "complete": len(complete),
            "incomplete": len(incomplete),
            "no_bouts": len(no_bouts),
            "rule": (
                "exact TW W-L match to schedule tournament_results non-bye bouts only; "
                "team_points from bout dual_points when known else standard dual scoring by win type"
            ),
            "source": f"data/seasons/{season}/schedule.json#tournament_results",
        },
    }
    cov_path = HISTORY / f"{season}_breakdown_coverage.json"
    cov_path.write_text(json.dumps(cov, indent=2, ensure_ascii=False) + "\n")
    return cov["summary"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", default="2025-26")
    args = ap.parse_args()
    summary = enrich(args.season)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
