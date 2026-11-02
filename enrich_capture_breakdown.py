#!/usr/bin/env python3
"""Apply W/L type + team_points breakdown for a season.

Primary source for 2025-26 incomplete wrestlers:
  tw_capture/<season>/wrestler_matches/<First_Last>.txt
  pipe: date|event|weight|W/L|result_type|score_time|opponent|opponent_team|team_points
  #BYE / #JV / #JV-NORESULT excluded from records, types, win%, and points.
  Points = NET dual scoring on varsity (wins add / losses subtract).

Fallback for wrestlers without a match file: schedule tournament_results
exact TW W-L match (prior behavior).

Tyler Davis: exclude 1/24 Peddie "M. For." loss (TW omits it); keep display 3-13.
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
TW_CAPTURE = ROOT.parent / "tw_capture"

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


def file_stem_for_name(name: str) -> str:
    """Map roster name → wrestler_matches stem."""
    # Oleksandr `Sasha` Yurovskyi → Oleksandr_Sasha_Yurovskyi
    # William (Liam) McSorley → William_Liam_McSorley
    s = name.replace("`", " ").replace("'", " ")
    s = re.sub(r"[()]", " ", s)
    s = re.sub(r"[^A-Za-z0-9]+", "_", s.strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def classify(result_type: str, score_time: str = "") -> str:
    raw = f"{result_type or ''} {score_time or ''}".strip().lower()
    if not raw or raw == "bye" or raw.startswith("bye"):
        return "bye"
    if "inj" in raw or "m. for" in raw or "m for" in raw or "medical" in raw:
        return "inj"
    if "dq" in raw or "disq" in raw:
        return "dq"
    if "tech" in raw or re.search(r"\btf\b", raw):
        return "tech"
    if re.search(r"\bmd\b", raw) or "maj" in raw:
        return "maj"
    if "fall" in raw or "pin" in raw:
        return "fall"
    if "forfeit" in raw or re.search(r"\bff\b", raw) or "fft" in raw:
        return "ff"
    if re.search(r"\bsv\b", raw) or "sudden" in raw:
        return "sv"
    if re.search(r"\btb\b", raw) or "tie break" in raw or "tiebreak" in raw:
        return "tb"
    if "dec" in raw or "decision" in raw:
        # score may carry SV-1 / TB-1
        if re.search(r"\bsv(?:-|\b)", raw) or "sudden" in raw:
            return "sv"
        if re.search(r"\btb(?:-|\b)", raw):
            return "tb"
        return "dec"
    if re.search(r"\d+\s*-\s*\d+", raw):
        if re.search(r"\bsv", raw):
            return "sv"
        if re.search(r"\btb", raw):
            return "tb"
        return "dec"
    return "dec"


def empty_agg() -> Dict[str, Any]:
    a = {k: 0 for k in STAT_KEYS + ["w", "l", "byes", "points", "jv_bouts_skipped", "varsity_bouts"]}
    a["excluded"] = []
    a["source"] = None
    a["_name"] = None
    return a


def parse_match_file(path: Path, wrestler_name: str) -> Dict[str, Any]:
    a = empty_agg()
    a["_name"] = wrestler_name
    a["source"] = f"wrestler_matches/{path.name}"
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#BYE"):
            a["byes"] += 1
            continue
        if line.startswith("#JV-NORESULT"):
            continue

        # Jeff: JV does not count — skip all #JV lines (same as byes / no-results)
        if line.startswith("#JV"):
            a["jv_bouts_skipped"] = a.get("jv_bouts_skipped", 0) + 1
            continue

        parts = line.split("|")
        # JV bye short form: date|event|weight|BYE
        if len(parts) >= 4 and (parts[3].strip().upper() == "BYE" or (
            len(parts) >= 5 and parts[4].strip().upper() == "BYE"
        )):
            a["byes"] += 1
            continue
        if len(parts) < 5:
            continue

        date, event, weight, wl = parts[0], parts[1], parts[2], parts[3].strip().upper()
        result_type = parts[4].strip() if len(parts) > 4 else ""
        score_time = parts[5].strip() if len(parts) > 5 else ""
        opponent = parts[6].strip() if len(parts) > 6 else ""
        opponent_team = parts[7].strip() if len(parts) > 7 else ""

        if result_type.upper() == "BYE" or wl == "BYE":
            a["byes"] += 1
            continue
        if wl not in ("W", "L"):
            continue

        # Tyler Davis: TW omits medical forfeit loss to Xzavier Torres (Peddie) 1/24
        if (
            nk(wrestler_name) == nk("Tyler Davis")
            and "01/24/2026" in date
            and "torres" in opponent.lower()
            and ("m. for" in score_time.lower() or "m. for" in result_type.lower()
                 or "for" in score_time.lower())
        ):
            a["excluded"].append({
                "reason": "TW omits medical forfeit; display record stays TW 3-13",
                "date": date,
                "event": event,
                "result": wl,
                "result_type": result_type,
                "score_time": score_time,
                "opponent": opponent,
                "opponent_team": opponent_team,
            })
            continue

        kind = classify(result_type, score_time)
        if kind == "bye":
            a["byes"] += 1
            continue

        a["varsity_bouts"] += 1

        pts = WIN_PTS.get(kind, 3)
        if wl == "W":
            a["w"] += 1
            field = "w_" + kind
            if field not in a:
                field = "w_dec"
            a[field] += 1
            a["points"] += pts  # net: wins add
        else:
            a["l"] += 1
            field = "l_" + kind
            if field not in a:
                field = "l_dec"
            a[field] += 1
            a["points"] -= pts  # net: losses subtract same dual values
    return a


# --- tournament_results fallback (exact match) ---

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


def classify_tr(win_type: Any, score: Any = None) -> str:
    return classify(str(win_type or ""), str(score or ""))


def aggregate_tournament_results(season: str) -> Dict[str, Dict[str, Any]]:
    sched_path = ROOT / "data" / "seasons" / season / "schedule.json"
    if not sched_path.exists():
        return {}
    sched = json.loads(sched_path.read_text())
    tr = sched.get("tournament_results") or {}
    bout_pts = load_bout_points(season)
    agg: Dict[str, Dict[str, Any]] = {}
    for eid, ev in tr.items():
        for w in ev.get("wrestlers") or []:
            name = w.get("wrestler") or w.get("name")
            if not name:
                continue
            key = nk(name)
            if key not in agg:
                agg[key] = empty_agg()
                agg[key]["_name"] = name
                agg[key]["source"] = "schedule.tournament_results"
            a = agg[key]
            for b in w.get("bouts") or []:
                kind = classify_tr(b.get("win_type"), b.get("score"))
                res = (b.get("result") or "").upper()
                if kind == "bye" or res not in ("W", "L"):
                    if kind == "bye":
                        a["byes"] += 1
                    continue
                a["varsity_bouts"] += 1
                opp = b.get("opponent_wrestler") or b.get("opponent")
                pts = bout_pts.get((key, nk(opp), res))
                dual = float(pts if pts is not None else WIN_PTS.get(kind, 3))
                if res == "W":
                    a["w"] += 1
                    field = "w_" + kind
                    if field not in a:
                        field = "w_dec"
                    a[field] += 1
                    a["points"] += dual
                else:
                    a["l"] += 1
                    field = "l_" + kind
                    if field not in a:
                        field = "l_dec"
                    a[field] += 1
                    a["points"] -= dual
    return agg


def apply_agg_to_wrestler(w: Dict[str, Any], a: Dict[str, Any], *, prior_tw: str) -> Dict[str, Any]:
    for k in STAT_KEYS:
        w[k] = a[k]
    # Displayed record = varsity-only
    w["win"] = a["w"]
    w["loss"] = a["l"]
    w["wins"] = a["w"]
    w["losses"] = a["l"]
    tp = a["points"]
    w["team_points"] = int(tp) if float(tp) == int(tp) else tp
    w["points"] = w["team_points"]
    w["pins"] = a["w_fall"]
    w["has_capture_breakdown"] = True
    w["record_scope"] = "varsity_only"
    entry = {
        "name": w.get("name"),
        "record": f"{a['w']}-{a['l']}",
        "prior_tw_record": prior_tw,
        "team_points": w["team_points"],
        "breakdown": {k: a[k] for k in STAT_KEYS if a[k]},
        "source": a.get("source"),
        "varsity_bouts": a.get("varsity_bouts"),
        "jv_bouts_skipped": a.get("jv_bouts_skipped") or 0,
        "byes_skipped": a.get("byes"),
        "excluded_bouts": a.get("excluded") or [],
    }
    if prior_tw != entry["record"]:
        entry["record_changed_from_tw"] = True
    return entry


def enrich(season: str) -> Dict[str, Any]:
    stats_path = HISTORY / f"{season}_stats.json"
    stats = json.loads(stats_path.read_text())
    matches_dir = TW_CAPTURE / season / "wrestler_matches"
    tr_agg = aggregate_tournament_results(season)

    complete: List[Dict[str, Any]] = []
    incomplete: List[Dict[str, Any]] = []
    no_bouts: List[Dict[str, Any]] = []
    notes: List[Dict[str, Any]] = []

    for w in stats.get("wrestlers") or []:
        name = w.get("name") or ""
        key = nk(name)
        tw_w = int(w.get("win") if w.get("win") is not None else w.get("wins") or 0)
        tw_l = int(w.get("loss") if w.get("loss") is not None else w.get("losses") or 0)
        for k in STAT_KEYS + ["team_points", "points", "has_capture_breakdown"]:
            w.pop(k, None)

        a = None
        match_path = matches_dir / f"{file_stem_for_name(name)}.txt"
        if match_path.exists():
            a = parse_match_file(match_path, name)
        elif key in tr_agg:
            a = tr_agg[key]

        prior_tw = f"{tw_w}-{tw_l}"
        from_match_file = bool(match_path.exists())

        if not a or (a["w"] + a["l"] == 0 and not from_match_file):
            if tw_w + tw_l >= 1:
                no_bouts.append({"name": name, "tw_record": prior_tw})
            continue

        # Match-list path: always publish varsity-only record (even 0-0 after JV strip)
        # TR fallback: require exact match to prior TW (no JV tags in that source)
        if from_match_file or (a["w"] == tw_w and a["l"] == tw_l):
            complete.append(apply_agg_to_wrestler(w, a, prior_tw=prior_tw))
            if a.get("excluded"):
                notes.append({"name": name, "excluded_bouts": a["excluded"]})
        else:
            incomplete.append({
                "name": name,
                "tw_record": prior_tw,
                "captured_record": f"{a['w']}-{a['l']}",
                "byes_skipped": a.get("byes"),
                "delta_w": a["w"] - tw_w,
                "delta_l": a["l"] - tw_l,
                "source": a.get("source"),
                "excluded_bouts": a.get("excluded") or [],
            })

    stats["has_breakdown"] = bool(complete)
    stats["breakdown_source"] = "wrestler_matches+tournament_results_exact_match"
    stats["breakdown_points_convention"] = (
        "standard_dual_scoring_varsity_net"
        " (Fall/FF/DQ/Inj-Def=6, TF=5, MD=4, Dec/SV/TB=3);"
        " records + W/L types + win% + NET points from varsity only;"
        " #JV / #JV-NORESULT / byes excluded"
    )
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
        "notes": notes,
        "summary": {
            "complete": len(complete),
            "incomplete": len(incomplete),
            "no_bouts": len(no_bouts),
            "points_convention": stats["breakdown_points_convention"],
            "rule": (
                "Varsity-only: exclude #JV, #JV-NORESULT, and byes from records, "
                "W/L type breakdown, win%, and points. "
                "Points: NET dual scoring on varsity (wins add, losses subtract Fall/FF/DQ/Inj=6 TF=5 MD=4 Dec/SV/TB=3). "
                "Fallback: tournament_results exact TW W-L match. "
                "Tyler Davis: exclude Peddie 1/24 M. For. loss (display 3-13)."
            ),
            "match_list_dir": str(matches_dir.relative_to(ROOT.parent)) if matches_dir.exists() else None,
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
