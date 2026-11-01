#!/usr/bin/env python3
"""Merge EventMatches HTML or pipe-format dual .txt captures into wrestling_data
without wiping existing tournament_results. Used for the nine 2025-26 duals that
lack Details bout cards. Pipe format:
  weight|winner|winner_team|loser|loser_team|result_type|score_time
Toms River South dualId 9000836132 is stored under sectional event 9000835132.

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
from tournament_results import build_event_results, index_captures, parse_dual_header_meta

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
    # Deduplicate paths: one capture file may be indexed under dual_id AND parent event id
    # (Toms River South dual 9000836132 inside sectional 9000835132).
    seen_paths: set[str] = set()
    path_to_ids: Dict[str, List[str]] = {}
    for eid, path in idx.items():
        path_to_ids.setdefault(str(path.resolve()), []).append(eid)

    for path_key, eids_for_path in path_to_ids.items():
        path = Path(path_key)
        if path_key in seen_paths:
            continue
        # Choose the schedule-facing event id: prefer one in targets that appears on schedule
        sched_ids = {str(e.get("event_id") or "") for e in schedule}
        candidate_ids = [e for e in eids_for_path if e in targets] or eids_for_path
        if event_ids is not None and not any(e in targets for e in eids_for_path):
            continue
        meta = parse_dual_header_meta(path.read_text(errors="ignore")[:4000])
        dual_id = str(meta.get("dual_id") or "")
        parent_id = str(meta.get("parent_event_id") or "")
        # Prefer parent/schedule event id when dual sits inside a sectional event
        eid = None
        for cand in candidate_ids:
            if cand in sched_ids:
                eid = cand
                break
        if eid is None and parent_id and parent_id in sched_ids:
            eid = parent_id
        if eid is None:
            eid = candidate_ids[0]
        if event_ids is not None and eid not in targets and dual_id not in targets and parent_id not in targets:
            # still allow if any alias is targeted
            if not any(e in targets for e in eids_for_path):
                continue

        seen_paths.add(path_key)
        built = build_event_results(eid, path)
        if built["shawnee_bout_count"] == 0 and built["bout_count"] == 0:
            skipped.append({"event_id": eid, "reason": "no bouts in capture", "file": path.name})
            continue
        # Find matching schedule row for name/date
        ev = next((e for e in schedule if str(e.get("event_id") or "") == eid), None)
        if ev is None and parent_id:
            ev = next((e for e in schedule if str(e.get("event_id") or "") == parent_id), None)
            if ev is not None:
                eid = parent_id
        entry = {
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
        if dual_id and dual_id != eid:
            entry["dual_id"] = dual_id
            entry["dual_note"] = (
                f"Trackwrestling DualMatches dualId={dual_id} inside parent event {eid}"
            )
        tr[eid] = entry
        # Also expose under real dual id when different, so lookups by dualId work
        if dual_id and dual_id != eid:
            alias = dict(entry)
            alias["event_id"] = dual_id
            alias["parent_event_id"] = eid
            tr[dual_id] = alias
        merged.append(eid)
        if dual_id and dual_id != eid:
            merged.append(dual_id)

        # Mark schedule row(s) expandable (single dual — not a multi split)
        for row in schedule:
            rid = str(row.get("event_id") or "")
            pid = str(row.get("parent_event_id") or "")
            if rid not in (eid, dual_id, parent_id) and pid not in (eid, dual_id, parent_id):
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
        print("nothing to merge — place EventMatches HTML or pipe-format event_*.txt into", args.capture_dir)
        return 2
    write_data(data)
    # Refresh history bouts for 2025-26
    try:
        from history_build import (
            HISTORY,
            enrich_bout_for_history,
            update_history_index,
            write_json,
            _now,
            load_json,
        )
        import json as _json
        bouts_path = HISTORY / "2025-26_bouts.json"
        doc = load_json(bouts_path, {
            "schema_version": 1,
            "season": "2025-26",
            "title": "2025-2026 Season",
            "events": {},
        })
        events = doc.setdefault("events", {})
        tr_now = data.get("tournament_results") or {}
        for eid in info["merged_event_ids"]:
            built = tr_now.get(eid)
            if not built:
                continue
            # Dual alias rows (real dualId under sectional parent) stay in TR only
            if built.get("parent_event_id") and str(built.get("event_id")) != str(built.get("parent_event_id")):
                continue
            enriched_wrestlers = []
            event_blurbs = []
            for w in built.get("wrestlers") or []:
                wb = dict(w)
                ebouts = []
                for b in w.get("bouts") or []:
                    bb = enrich_bout_for_history({
                        **b,
                        "shawnee_wrestler": w.get("wrestler"),
                        "weight": b.get("weight") or w.get("weight"),
                    })
                    ebouts.append(bb)
                    event_blurbs.append({
                        "weight": bb.get("weight"),
                        "winner": bb.get("winner_name"),
                        "winner_team": bb.get("winner_team"),
                        "loser": bb.get("loser_name"),
                        "loser_team": bb.get("loser_team"),
                        "win_type": bb.get("win_type"),
                        "score_or_time": bb.get("score_or_time"),
                        "blurb": bb.get("blurb"),
                        "result": bb.get("result"),
                        "opponent_team": bb.get("opponent_team"),
                        "shawnee_wrestler": bb.get("shawnee_wrestler"),
                    })
                wb["bouts"] = ebouts
                enriched_wrestlers.append(wb)
            entry = {
                "event_id": eid,
                "event_name": built.get("event_name"),
                "date_iso": built.get("date_iso"),
                "available": bool(event_blurbs),
                "bout_count": built.get("bout_count") or len(event_blurbs),
                "shawnee_bout_count": len(event_blurbs),
                "opponents": built.get("opponents") or [],
                "dual_scores": built.get("dual_scores") or {},
                "wrestlers": enriched_wrestlers,
                "blurbs": event_blurbs,
                "source_file": built.get("source_file"),
            }
            if built.get("dual_id"):
                entry["dual_id"] = built["dual_id"]
            if built.get("parent_event_id"):
                entry["parent_event_id"] = built["parent_event_id"]
            events[eid] = entry
        doc["generated_at"] = _now()
        doc["event_count"] = len(events)
        doc["events_with_bouts"] = sum(1 for e in events.values() if e.get("available"))
        doc["blurb_count"] = sum(len(e.get("blurbs") or []) for e in events.values())
        doc["available"] = doc["events_with_bouts"] > 0
        write_json(bouts_path, doc)
        bout_status = {}
        for pth in HISTORY.glob("*_bouts.json"):
            sid = pth.name.replace("_bouts.json", "")
            bout_status[sid] = bool(load_json(pth, {}).get("available"))
        update_history_index(["2025-26"], bout_status)
        print("refreshed data/history/2025-26_bouts.json + index")
    except Exception as e:
        logger.warning("history refresh skipped: %s", e)
    print("wrote wrestling_data + tournament_results")
    return 0


if __name__ == "__main__":
    sys.exit(main())
