#!/usr/bin/env python3
"""Enrich Shawnee schedule: split multi-team meets into dual rows, attach logos.

Trackwrestling remains the sole schedule source. This module only reshapes
parsed TW events + EventMatches bout grids (via tournament_results) and looks
up logos from data/logos.json / assets/logos.
"""
from __future__ import annotations

import copy
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from school_aliases import lookup_logo, resolve_school, load_logos_map
from tournament_results import (
    attach_tournament_results,
    build_event_results,
    index_captures,
    is_shawnee,
    load_capture,
)

logger = logging.getLogger("schedule_enrich")
ROOT = Path(__file__).resolve().parent

# Event names / kinds that are multi-team dual meets (split into per-opponent rows)
MULTI_DUAL_HINTS = re.compile(
    r"\b(tri|quad|dual tournament|duals?\b|vs\.|w/)",
    re.I,
)

# Known static opponent lists when bout grid missing (fallback from prior research)
KNOWN_SPLIT_OPPONENTS: Dict[str, List[str]] = {
    "8715034132": ["West Deptford", "West Windsor-Plainsboro North"],  # Shawnee Tri
    "8724258132": ["Seneca", "Cherokee", "Lenape"],  # LRHSD Quad
    "8729716132": ["Rancocas Valley", "Camden Catholic"],  # Tri @ Camden Catholic
    "8715056132": ["Collingswood", "Cinnaminson", "Absegami"],  # Quad @ Shawnee
    "8733369132": ["Delran", "Toms River North", "Lacey Township"],  # Quad @ Delran
    "8773919132": ["St. Joseph (Hammonton)", "Pennsauken"],  # St Joes Tri
}



def coalesce_to_base_schedule(schedule: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Undo prior split enrichment so enrich_schedule is idempotent."""
    parents: Dict[str, Dict[str, Any]] = {}
    singles: List[Dict[str, Any]] = []
    for ev in schedule or []:
        if ev.get("split") or ev.get("parent_event_id"):
            eid = str(ev.get("parent_event_id") or ev.get("event_id") or "")
            if not eid or eid in parents:
                continue
            p = copy.deepcopy(ev)
            for k in (
                "opponent", "opponent_slug", "opponent_logo", "opponent_logo_local",
                "logo_source", "score_shawnee", "score_opp", "score_display", "result",
                "split", "split_note", "filter_opponent", "parent_event_id",
                "expandable", "tournament_key", "display_as_event", "multi_meet",
            ):
                p.pop(k, None)
            p["opponent"] = None
            p["score_shawnee"] = None
            p["score_opp"] = None
            p["score_display"] = None
            p["result"] = None
            p["opponent_slug"] = None
            p["opponent_logo"] = None
            p["opponent_logo_local"] = None
            parents[eid] = p
        else:
            # Drop stale expand flags; re-attach below
            s = copy.deepcopy(ev)
            for k in ("expandable", "tournament_key", "display_as_event", "multi_meet", "filter_opponent"):
                s.pop(k, None)
            singles.append(s)
    merged = singles + list(parents.values())
    merged.sort(key=lambda x: (x.get("date_iso") or "", str(x.get("event_id") or "")))
    return merged


def _apply_logo_fields(row: Dict[str, Any], logos_map: Dict[str, Any]) -> None:
    name = row.get("opponent") or ""
    if not name or name in ("0", "-"):
        return
    info = lookup_logo(name, logos_map, make_badge=True)
    if info.get("opponent"):
        row["opponent"] = info["opponent"]
    row["opponent_slug"] = info.get("opponent_slug")
    row["opponent_logo"] = info.get("opponent_logo")
    row["opponent_logo_local"] = info.get("opponent_logo_local")
    if info.get("logo_source"):
        row["logo_source"] = info["logo_source"]


def _clean_standings_note(note: str) -> str:
    if not note:
        return note
    # Remove Trackwrestling / season-id style mentions from user-visible note
    note = re.sub(r"Trackwrestling\s+", "", note, flags=re.I)
    note = re.sub(r"\bTW\b", "schedule source", note)
    note = note.replace(
        "did not expose a bulk Olympic Conference standings Ajax in the 2025-26 replay (TeamStatistics JSPs 404). Standings below list Shawnee dual results vs Olympic Conference / local foes from the schedule source Schedule UI scores.",
        "official Olympic Conference standings were not available in the season archive. Rows below list Shawnee dual results vs Olympic Conference / local foes from schedule scores.",
    )
    # Soften leftover
    note = note.replace("schedule source Schedule UI scores", "schedule scores")
    note = note.replace("schedule source", "the schedule feed")
    return note


def opponents_for_event(ev: Dict[str, Any], results_entry: Optional[Dict[str, Any]]) -> List[str]:
    eid = str(ev.get("event_id") or "")
    if results_entry and results_entry.get("opponents"):
        # Prefer dual_scores keys order (Shawnee-faced), else opponents list
        ds = results_entry.get("dual_scores") or {}
        if ds:
            return list(ds.keys())
        return list(results_entry["opponents"])
    if eid in KNOWN_SPLIT_OPPONENTS:
        return list(KNOWN_SPLIT_OPPONENTS[eid])
    # Parse from event_name heuristics
    name = ev.get("event_name") or ""
    return []


def should_split(ev: Dict[str, Any], results_entry: Optional[Dict[str, Any]]) -> bool:
    """Split multi-team dual meets; keep true tournaments as one expandable listing."""
    kind = (ev.get("event_kind") or "").upper()
    name = ev.get("event_name") or ""
    # Individual tournaments (I) stay as one card
    if kind == "I":
        return False
    # Named NJSIAA team sectionals: keep one row (team dual bracket) — still can expand
    if re.search(r"sectional|njsiaa south group", name, re.I):
        return False
    if results_entry and results_entry.get("dual_scores") and len(results_entry["dual_scores"]) >= 1:
        # Dual-style multi with computed scores
        if kind == "D" or MULTI_DUAL_HINTS.search(name):
            return True
    if kind == "D" and MULTI_DUAL_HINTS.search(name):
        return True
    if eid_known := str(ev.get("event_id") or ""):
        if eid_known in KNOWN_SPLIT_OPPONENTS:
            return True
    return False


def enrich_schedule(data: Dict[str, Any], capture_dir: Path | None = None) -> Dict[str, Any]:
    logos_map = load_logos_map(ROOT / "data" / "logos.json")
    # Ensure tournament_results present
    if "tournament_results" not in data:
        attach_tournament_results(data, capture_dir)
    results = data.get("tournament_results") or {}

    base = coalesce_to_base_schedule(data.get("schedule") or [])
    new_schedule: List[Dict[str, Any]] = []
    split_log: List[Dict[str, Any]] = []

    for ev in base:
        ev = copy.deepcopy(ev)
        eid = str(ev.get("event_id") or "")
        tr = results.get(eid)

        # Attach logos on single-opponent duals
        if ev.get("opponent"):
            _apply_logo_fields(ev, logos_map)

        if should_split(ev, tr):
            opps = opponents_for_event(ev, tr)
            if not opps:
                # Cannot split — keep as event with note
                ev["multi_meet"] = True
                ev["split"] = False
                ev["expandable"] = bool(tr and tr.get("wrestlers"))
                new_schedule.append(ev)
                continue
            parent_name = ev.get("event_name") or "Multi-team dual"
            for opp in opps:
                child = copy.deepcopy(ev)
                child["opponent"] = opp
                child["event_name"] = parent_name
                child["parent_event_id"] = eid
                child["multi_meet"] = True
                child["split"] = True
                child["split_note"] = f"Part of {parent_name}"
                child["home_away"] = ev.get("home_away") or "event"
                # Scores from bout grid when available
                ds = (tr or {}).get("dual_scores") or {}
                # match opponent name flexibly
                score = None
                for k, v in ds.items():
                    slug_a, _ = resolve_school(k)
                    slug_b, _ = resolve_school(opp)
                    if _norm(k) == _norm(opp) or (slug_a and slug_a == slug_b):
                        score = v
                        break
                if score:
                    child["score_shawnee"] = score["shawnee"]
                    child["score_opp"] = score["opp"]
                    child["score_display"] = score["score_display"]
                    child["result"] = score["result"]
                else:
                    child["score_shawnee"] = None
                    child["score_opp"] = None
                    child["score_display"] = None
                    child["result"] = None
                _apply_logo_fields(child, logos_map)
                # Only attach wrestler cards filtered to this opponent on expand
                if tr and tr.get("wrestlers"):
                    child["expandable"] = True
                    child["tournament_key"] = eid
                    child["filter_opponent"] = child["opponent"]
                new_schedule.append(child)
            split_log.append({"event_id": eid, "name": parent_name, "opponents": opps})
        else:
            # Tournaments / single duals
            if tr and tr.get("wrestlers"):
                ev["expandable"] = True
                ev["tournament_key"] = eid
                # For pure tournaments, show event name as primary label
                if (ev.get("event_kind") or "").upper() == "I" or not ev.get("opponent"):
                    ev["display_as_event"] = True
            # Named dual already has score from scraper — keep
            new_schedule.append(ev)

    data["schedule"] = new_schedule
    data.setdefault("enrichment", {})["splits"] = split_log

    # Canonical dual record from ALL dual listings (incl. multi-meet splits).
    # results_ledger owns dual_scores / metadata records / standings rows.
    from results_ledger import build_and_apply, LedgerConsistencyError
    try:
        build_and_apply(data, write=True, strict=False)
    except LedgerConsistencyError as e:
        logger.error("%s", e)

    st = data.get("standings") or {}
    if st.get("note"):
        st["note"] = _clean_standings_note(st["note"])
    data["standings"] = st

    # Scrub metadata sources of raw IDs (keep in config only — already in season_config)
    meta = data.get("metadata") or {}
    # Keep season_id/team_id in JSON for pipeline but UI must not render them.
    # Soften sources wording for any future display:
    sources = meta.get("sources") or {}
    if isinstance(sources, dict):
        for k, v in list(sources.items()):
            if isinstance(v, str) and "Trackwrestling" in v:
                sources[k] = v.replace("Trackwrestling", "Schedule feed").replace("getTeamSchedule + Schedule UI dual scores", "team schedule")
                sources[k] = sources[k].replace("getWrestlers", "roster feed")
        meta["sources"] = sources
    # Prefer user-facing season label
    if meta.get("season") in ("2025-26", "2025-26 Closeout", "2025-26 closeout"):
        meta["season"] = "2025-2026"
    data["metadata"] = meta

    return data


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


# school_aliases doesn't export is_shawnee — ignore unused import quirk
try:
    from tournament_results import is_shawnee  # noqa: F811
except Exception:
    pass


def enrich_file(
    path: Path | None = None,
    capture_dir: Path | None = None,
    write: bool = True,
) -> Dict[str, Any]:
    path = path or (ROOT / "data" / "wrestling_data.json")
    data = json.loads(path.read_text())
    attach_tournament_results(data, capture_dir)
    data = enrich_schedule(data, capture_dir)
    if write:
        path.write_text(json.dumps(data, indent=2) + "\n")
        (ROOT / "wrestling_data.json").write_text(json.dumps(data, indent=2) + "\n")
        # Also dump tournament_results alone for debugging
        tr_path = ROOT / "data" / "tournament_results.json"
        tr_path.write_text(json.dumps(data.get("tournament_results") or {}, indent=2) + "\n")
    return data


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    d = enrich_file()
    print("schedule rows", len(d["schedule"]))
    print("splits", d.get("enrichment", {}).get("splits"))
    print("tournament events", list((d.get("tournament_results") or {}).keys()))
    print("dual record", d.get("dual_scores", {}).get("record"))
