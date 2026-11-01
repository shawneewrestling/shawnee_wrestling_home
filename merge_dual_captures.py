#!/usr/bin/env python3
"""Merge EventMatches HTML captures for single duals into wrestling_data without
wiping existing tournament_results. Used for the nine 2025-26 duals that lack
Details bout cards.

Usage:
  python merge_dual_captures.py tw_capture/2025-26/missing_duals/
  python merge_dual_captures.py --dry-run tw_capture/2025-26/missing_duals/
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

from school_aliases import lookup_logo, load_logos_map, resolve_school
from tournament_results import build_event_results, index_captures

ROOT = Path(__file__).resolve().parent
logger = logging.getLogger("merge_dual_captures")

DEFAULT_BRIEF = ROOT / "data" / "history" / "2025-26_missing_dual_captures.json"


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def merge_captures(
    capture_dir: Path,
    data: Dict[str, Any],
    event_ids: List[str] | None = None,
) -> Dict[str, Any]:
    idx = index_captures(capture_dir)
    logos_map = load_logos_map(ROOT / "data" / "logos.json")
    tr = dict(data.get("tournament_results") or {})
    schedule = list(data.get("schedule") or [])
    merged: List[str] = []
    skipped: List[Dict[str, str]] = []

    targets = set(event_ids) if event_ids else set(idx.keys())
    # Always consider schedule rows whose event_id is in this capture dir
    for eid, path in idx.items():
        if eid not in targets:
            continue
        built = build_event_results(eid, path)
        if built["shawnee_bout_count"] == 0 and built["bout_count"] == 0:
            skipped.append({"event_id": eid, "reason": "no bouts in capture", "file": path.name})
            continue
        # Find matching schedule row for name/date
        ev = next((e for e in schedule if str(e.get("event_id") or "") == eid), None)
        tr[eid] = {
            "event_id": eid,
            "event_name": (ev or {}).get("event_name") or built.get("event_name"),
            "date_iso": (ev or {}).get("date_iso"),
            "source_file": path.name,
            "opponents": built["opponents"],
            "dual_scores": built["dual_scores"],
            "wrestlers": built["wrestlers"],
            "shawnee_bout_count": built["shawnee_bout_count"],
            "status": "final",
            "completed": True,
        }
        merged.append(eid)

        # Mark schedule row(s) expandable (single dual — not a multi split)
        for row in schedule:
            if str(row.get("event_id") or "") != eid and str(row.get("parent_event_id") or "") != eid:
                continue
            row["expandable"] = True
            row["tournament_key"] = eid
            # Prefer schedule opponent; else first dual_scores / opponents entry
            opp = row.get("opponent") or row.get("filter_opponent")
            if not opp:
                ds = built.get("dual_scores") or {}
                if ds:
                    opp = next(iter(ds.keys()))
                elif built.get("opponents"):
                    opp = built["opponents"][0]
            if opp:
                row["filter_opponent"] = opp
                if not row.get("opponent"):
                    row["opponent"] = opp
                info = lookup_logo(opp, logos_map, make_badge=True)
                if info.get("opponent"):
                    row["opponent"] = info["opponent"]
                    row["filter_opponent"] = info["opponent"]
                row["opponent_slug"] = info.get("opponent_slug")
                row["opponent_logo"] = info.get("opponent_logo")
                row["opponent_logo_local"] = info.get("opponent_logo_local")
            # Apply dual score onto the row when present
            ds = built.get("dual_scores") or {}
            score = None
            for k, v in ds.items():
                slug_a, _ = resolve_school(k)
                slug_b, _ = resolve_school(opp or "")
                if _norm(k) == _norm(opp or "") or (slug_a and slug_a == slug_b):
                    score = v
                    break
            if score is None and len(ds) == 1:
                score = next(iter(ds.values()))
            if score:
                row["score_shawnee"] = score["shawnee"]
                row["score_opp"] = score["opp"]
                row["score_display"] = score["score_display"]
                row["result"] = score["result"]

    data["tournament_results"] = tr
    data["schedule"] = schedule
    data.setdefault("enrichment", {})["merged_dual_captures"] = {
        "merged_event_ids": merged,
        "skipped": skipped,
        "capture_dir": str(capture_dir),
    }
    return data


def write_data(data: Dict[str, Any]) -> None:
    path = ROOT / "data" / "wrestling_data.json"
    path.write_text(json.dumps(data, indent=2) + "\n")
    (ROOT / "wrestling_data.json").write_text(json.dumps(data, indent=2) + "\n")
    tr_path = ROOT / "data" / "tournament_results.json"
    tr_path.write_text(json.dumps(data.get("tournament_results") or {}, indent=2) + "\n")
    # Mirror into seasons pack when present
    season_sched = ROOT / "data" / "seasons" / "2025-26" / "schedule.json"
    if season_sched.exists():
        pack = json.loads(season_sched.read_text())
        if isinstance(pack, dict):
            pack["schedule"] = data["schedule"]
            if "tournament_results" in pack or True:
                pack["tournament_results"] = data.get("tournament_results")
            season_sched.write_text(json.dumps(pack, indent=2) + "\n")
        # also dump stand-alone tournament_results if that file exists
    season_tr = ROOT / "data" / "seasons" / "2025-26" / "tournament_results.json"
    if season_tr.exists() or True:
        season_tr.parent.mkdir(parents=True, exist_ok=True)
        season_tr.write_text(json.dumps(data.get("tournament_results") or {}, indent=2) + "\n")


def main(argv: List[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("capture_dir", type=Path, nargs="?", default=ROOT / "tw_capture" / "2025-26" / "missing_duals")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--brief", type=Path, default=DEFAULT_BRIEF)
    args = ap.parse_args(argv)

    event_ids = None
    if args.brief.exists():
        brief = json.loads(args.brief.read_text())
        event_ids = [str(e["event_id"]) for e in brief.get("events") or []]

    data = json.loads((ROOT / "data" / "wrestling_data.json").read_text())
    before = set((data.get("tournament_results") or {}).keys())
    data = merge_captures(args.capture_dir, data, event_ids=event_ids)
    after = set((data.get("tournament_results") or {}).keys())
    info = data["enrichment"]["merged_dual_captures"]
    print("merged", info["merged_event_ids"])
    print("skipped", info["skipped"])
    print("tr delta", sorted(after - before))
    if args.dry_run:
        print("dry-run: not writing")
        return 0 if info["merged_event_ids"] else 2
    if not info["merged_event_ids"]:
        print("nothing to merge — place EventMatches HTML with initDataGrid into", args.capture_dir)
        return 2
    write_data(data)
    # Refresh history bouts for 2025-26
    try:
        from history_build import build_bouts_for_season, update_index
        build_bouts_for_season("2025-26")
        update_index()
        print("refreshed data/history/2025-26_bouts.json + index")
    except Exception as e:
        logger.warning("history refresh skipped: %s", e)
    print("wrote wrestling_data + tournament_results")
    return 0


if __name__ == "__main__":
    sys.exit(main())
