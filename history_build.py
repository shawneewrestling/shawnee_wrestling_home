#!/usr/bin/env python3
"""Build data/history artifacts for past seasons (roster, stats, bouts).

Roster starters prefer dual bout lineups when data/history/<season>_bouts.json
has Shawnee bouts; otherwise season_record_proxy (TW roster weight + most wins).

Bout grids require browser EventMatches HTML (getEventMatchesJSP is null
server-side). When captures land under tw_capture/<season>/event_*.html or
--event-capture-dir, re-run to populate *_bouts.json.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from tournament_results import (
    build_event_results,
    extract_init_datagrid,
    parse_bout_row,
    wrestler_cards,
)

ROOT = Path(__file__).resolve().parent
HISTORY = ROOT / "data" / "history"
SEASONS = ROOT / "data" / "seasons"
DRYRUN = Path("/workspace/shawnee/dryrun")
TW_CAPTURE = Path("/workspace/shawnee/tw_capture")
TW_EVENT_PAGES = Path("/workspace/shawnee/tw_event_pages")
EST = ZoneInfo("America/New_York")

NJSIAA_WEIGHTS = [
    "106", "113", "120", "126", "132", "138", "144",
    "150", "157", "165", "175", "190", "215", "285",
]


def _now() -> str:
    t = datetime.now(EST)
    s = t.strftime("%Y-%m-%dT%H:%M:%S%z")
    return s[:-2] + ":" + s[-2:]


def short_to_label(short: str) -> str:
    a, _ = short.split("-")
    return f"{int(a)}-{int(a) + 1} Season"


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text())


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def norm_name(n: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (n or "").lower())


def bout_score_or_time(b: Dict[str, Any]) -> Optional[str]:
    """TW-style score or fall clock for blurbs."""
    if b.get("score"):
        return str(b["score"])
    wt = str(b.get("win_type") or "")
    fall = b.get("fall_seconds")
    if fall not in (None, "", 0, "0"):
        try:
            secs = int(fall)
            return f"{secs // 60}:{secs % 60:02d}"
        except (TypeError, ValueError):
            pass
    s1, s2 = b.get("score_w1"), b.get("score_w2")
    if s1 not in (None, "") and s2 not in (None, ""):
        try:
            return f"{int(s1)}-{int(s2)}"
        except (TypeError, ValueError):
            return f"{s1}-{s2}"
    if re.search(r"forfeit", wt, re.I):
        return "Forfeit"
    if re.search(r"\bbye\b", wt, re.I):
        return "Bye"
    return None


def tw_blurb(b: Dict[str, Any]) -> str:
    """Trackwrestling-style one-line blurb."""
    weight = b.get("weight") or "—"
    win_type = b.get("win_type") or ""
    score = bout_score_or_time(b) or ""
    winner = b.get("winner_name") or b.get("winner") or "—"
    wteam = b.get("winner_team") or "—"
    loser = b.get("loser_name") or b.get("loser") or "—"
    lteam = b.get("loser_team") or "—"
    # Prefer explicit winner/loser; else derive from Shawnee-centric fields
    if not b.get("winner_name") and b.get("result") in ("W", "L"):
        us = b.get("shawnee_wrestler") or "—"
        opp = b.get("opponent_wrestler") or "—"
        oteam = b.get("opponent_team") or "—"
        if b.get("result") == "W":
            winner, wteam, loser, lteam = us, "Shawnee", opp, oteam
        else:
            winner, wteam, loser, lteam = opp, oteam, us, "Shawnee"
    paren = ""
    if re.search(r"forfeit", win_type, re.I) or score == "Forfeit":
        paren = "(For.)"
    elif re.search(r"\bbye\b", win_type, re.I) or score == "Bye":
        paren = "(Bye)"
    elif re.search(r"tech", win_type, re.I):
        paren = f"(TF {score})" if score and not re.match(r"^\d+:\d{2}$", score) else (f"(TF {score})" if score else "(TF)")
    elif re.search(r"fall", win_type, re.I):
        clock = score if score and re.search(r"\d+:\d{2}", score) else score
        if clock and re.search(r"Fall\s+", str(clock), re.I):
            clock = re.sub(r"(?i)Fall\s+", "", str(clock)).strip()
        paren = f"(Fall {clock})" if clock else "(Fall)"
    elif re.search(r"maj", win_type, re.I):
        paren = f"(MD {score})" if score else "(MD)"
    elif re.search(r"dec|SV|sud", win_type, re.I) or re.match(r"^\d+\s*-\s*\d+$", str(score or "")):
        paren = f"(Dec {score})" if score else "(Dec)"
    elif score:
        paren = f"({score})"
    return f"{weight}: {winner} ({wteam}) over {loser} ({lteam}) {paren}".strip()


def enrich_bout_for_history(b: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a parsed bout into history blurb fields."""
    out = dict(b)
    # Ensure winner/loser name+team
    if not out.get("winner_name"):
        if out.get("result") == "W":
            out["winner_name"] = out.get("shawnee_wrestler")
            out["winner_team"] = "Shawnee"
            out["loser_name"] = out.get("opponent_wrestler")
            out["loser_team"] = out.get("opponent_team")
        elif out.get("result") == "L":
            out["winner_name"] = out.get("opponent_wrestler")
            out["winner_team"] = out.get("opponent_team")
            out["loser_name"] = out.get("shawnee_wrestler")
            out["loser_team"] = "Shawnee"
    out["score_or_time"] = bout_score_or_time(out)
    out["blurb"] = tw_blurb(out)
    return out


def find_event_captures(season: str, event_dir: Optional[Path]) -> Dict[str, Path]:
    """Map event_id -> HTML capture path."""
    found: Dict[str, Path] = {}
    dirs = []
    if event_dir:
        dirs.append(event_dir)
    dirs.append(TW_CAPTURE / season)
    # Only use shared tw_event_pages for the season that produced them (2025-26)
    if season == "2025-26":
        dirs.append(TW_EVENT_PAGES)
    eid_re = re.compile(r"(?:event_)?(\d{6,})(?:_|\.|$)")
    for d in dirs:
        if not d or not d.exists():
            continue
        for p in d.glob("*.html"):
            m = eid_re.search(p.name)
            if not m:
                # also try reading event_id from content later
                text = p.read_text(errors="ignore")[:2000]
                m2 = re.search(r"eventId[=:](\d+)", text)
                if m2:
                    found.setdefault(m2.group(1), p)
                continue
            found.setdefault(m.group(1), p)
    return found


def build_bouts_from_captures(
    season: str,
    checklist: Optional[Dict[str, Any]] = None,
    event_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    captures = find_event_captures(season, event_dir)
    events_out: Dict[str, Any] = {}
    all_blurbs: List[Dict[str, Any]] = []
    checklist = checklist or load_json(DRYRUN / season / "capture_checklist.json", {}) or {}
    checklist_events = {str(e["event_id"]): e for e in (checklist.get("events") or [])}

    # Prefer checklist event ids; also include any extra captures found
    eids = list(checklist_events.keys()) or list(captures.keys())
    for eid in sorted(set(list(captures.keys()) + eids), key=lambda x: (0 if x in captures else 1, x)):
        meta = checklist_events.get(eid, {})
        path = captures.get(eid)
        entry: Dict[str, Any] = {
            "event_id": eid,
            "event_name": meta.get("event_name"),
            "date_iso": meta.get("date_iso"),
            "capture_url": meta.get("url"),
            "available": False,
            "bout_count": 0,
            "shawnee_bout_count": 0,
            "wrestlers": [],
            "bouts": [],
            "blurbs": [],
        }
        if path and path.exists():
            try:
                built = build_event_results(eid, path)
                raw_bouts = built.get("bouts") or []
                enriched = [enrich_bout_for_history(b) for b in raw_bouts]
                # Also enrich wrestler card bouts
                wrestlers = []
                for w in built.get("wrestlers") or []:
                    wb = dict(w)
                    wb["bouts"] = [enrich_bout_for_history(b) for b in (w.get("bouts") or [])]
                    wrestlers.append(wb)
                entry.update({
                    "available": len(enriched) > 0,
                    "bout_count": built.get("bout_count") or len(enriched),
                    "shawnee_bout_count": built.get("shawnee_bout_count") or sum(
                        1 for b in enriched if b.get("shawnee_wrestler")
                    ),
                    "opponents": built.get("opponents") or [],
                    "dual_scores": built.get("dual_scores") or {},
                    "wrestlers": wrestlers,
                    "bouts": enriched,
                    "blurbs": [
                        {
                            "weight": b.get("weight"),
                            "winner": b.get("winner_name"),
                            "winner_team": b.get("winner_team"),
                            "loser": b.get("loser_name"),
                            "loser_team": b.get("loser_team"),
                            "win_type": b.get("win_type"),
                            "score_or_time": b.get("score_or_time"),
                            "blurb": b.get("blurb"),
                            "result": b.get("result"),
                            "opponent_team": b.get("opponent_team"),
                            "shawnee_wrestler": b.get("shawnee_wrestler"),
                        }
                        for b in enriched
                        if b.get("shawnee_wrestler")
                    ],
                    "source_file": path.name,
                })
                all_blurbs.extend(entry["blurbs"])
            except Exception as exc:  # noqa: BLE001
                entry["error"] = str(exc)
        events_out[eid] = entry

    available_events = sum(1 for e in events_out.values() if e.get("available"))
    return {
        "schema_version": 1,
        "season": season,
        "title": short_to_label(season),
        "generated_at": _now(),
        "available": available_events > 0,
        "event_count": len(events_out),
        "events_with_bouts": available_events,
        "blurb_count": len(all_blurbs),
        "note": (
            None
            if available_events
            else (
                "No EventMatches HTML captures for this season. "
                "TW getEventMatchesJSP returns null without a browser session. "
                "Capture checklist URLs are under events[].capture_url."
            )
        ),
        "events": events_out,
    }


def build_bouts_from_tournament_results(season: str) -> Optional[Dict[str, Any]]:
    """Convert data/tournament_results.json (current-season captures) into history bouts."""
    if season != "2025-26":
        return None
    tr = load_json(ROOT / "data" / "tournament_results.json")
    if not tr:
        return None
    events_out: Dict[str, Any] = {}
    blurbs_all: List[Dict[str, Any]] = []
    for eid, built in tr.items():
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
        events_out[eid] = {
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
        blurbs_all.extend(event_blurbs)
    return {
        "schema_version": 1,
        "season": season,
        "title": short_to_label(season),
        "generated_at": _now(),
        "available": len(blurbs_all) > 0,
        "event_count": len(events_out),
        "events_with_bouts": sum(1 for e in events_out.values() if e.get("available")),
        "blurb_count": len(blurbs_all),
        "note": "Built from data/tournament_results.json (EventMatches captures).",
        "events": events_out,
    }


def primary_weight_from_sheet(weights: str) -> Optional[str]:
    if not weights:
        return None
    parts = re.split(r"[\/,|; ]+", str(weights).strip())
    for p in parts:
        p = p.strip()
        if p.isdigit():
            return p
    return None


def build_roster(season: str, bouts_doc: Dict[str, Any]) -> Dict[str, Any]:
    """Varsity slots for historical Roster season dropdown."""
    players_index = load_json(ROOT / "data" / "players_index.json", {"wrestlers": []})
    by_name = {norm_name(w["name"]): w for w in players_index.get("wrestlers") or [] if w.get("name")}
    site_wp = load_json(ROOT / "data" / "site_roster_wp.json", {"wrestlers": []})
    home = load_json(ROOT / "data" / "home_roster.json", {"wrestlers": []})
    photo_by = {}
    for w in (site_wp.get("wrestlers") or []):
        if w.get("photo_url") and w.get("name"):
            photo_by[norm_name(w["name"])] = w["photo_url"]
    for w in (home.get("wrestlers") or []):
        if w.get("photo") and w.get("name"):
            photo_by[norm_name(w["name"])] = w["photo"]
    for w in players_index.get("wrestlers") or []:
        if w.get("photo") and w.get("name"):
            photo_by.setdefault(norm_name(w["name"]), w["photo"])

    # TW roster from dryrun if present
    dry = load_json(DRYRUN / season / "wrestling_data.json") or load_json(DRYRUN / season / "roster.json")
    tw_roster: List[Dict[str, Any]] = []
    if dry:
        tw_roster = dry.get("roster") or (dry if isinstance(dry, list) else [])

    # Season stats for W-L + sheet weights
    stats = load_json(SEASONS / season / "stats.json") or load_json(HISTORY / f"{season}_stats.json")
    stats_by = {}
    if stats:
        for w in stats.get("wrestlers") or []:
            stats_by[norm_name(w["name"])] = w

    # Count dual lineup appearances from bouts when available
    appearance: Dict[Tuple[str, str], int] = defaultdict(int)
    wins_at: Dict[Tuple[str, str], int] = defaultdict(int)
    if bouts_doc and bouts_doc.get("available"):
        for ev in (bouts_doc.get("events") or {}).values():
            for b in ev.get("bouts") or []:
                name = b.get("shawnee_wrestler")
                wt = str(b.get("weight") or "")
                if not name or wt not in NJSIAA_WEIGHTS:
                    continue
                key = (norm_name(name), wt)
                appearance[key] += 1
                if b.get("result") == "W":
                    wins_at[key] += 1

    method = "dual_bouts" if appearance else "season_record_proxy"
    # Candidate pool: TW roster preferred; else stats names
    candidates: List[Dict[str, Any]] = []
    if tw_roster:
        for w in tw_roster:
            name = w.get("name")
            if not name:
                continue
            st = stats_by.get(norm_name(name), {})
            weight = str(w.get("weight") or primary_weight_from_sheet(st.get("weights") or "") or "")
            wins = int(w.get("wins") if w.get("wins") is not None else st.get("win") or 0)
            losses = int(w.get("losses") if w.get("losses") is not None else st.get("loss") or 0)
            if wins + losses < 1 and method == "season_record_proxy":
                continue
            candidates.append({
                "wrestler_id": w.get("wrestler_id"),
                "name": name,
                "grade": w.get("grade"),
                "weight": weight,
                "wins": wins,
                "losses": losses,
            })
    else:
        for key, st in stats_by.items():
            weight = primary_weight_from_sheet(st.get("weights") or "") or ""
            wins = int(st.get("win") or 0)
            losses = int(st.get("loss") or 0)
            if wins + losses < 1:
                continue
            candidates.append({
                "wrestler_id": None,
                "name": st.get("name"),
                "grade": None,
                "weight": weight,
                "wins": wins,
                "losses": losses,
            })

    # Pick starter per weight
    slots = []
    used = set()
    for wt in NJSIAA_WEIGHTS:
        best = None
        best_score = (-1, -1, -1)  # appearances, wins_at, season wins
        for c in candidates:
            nk = norm_name(c["name"])
            if nk in used:
                continue
            if method == "dual_bouts":
                apps = appearance.get((nk, wt), 0)
                if apps <= 0:
                    continue
                score = (apps, wins_at.get((nk, wt), 0), c["wins"])
            else:
                if str(c.get("weight") or "") != wt:
                    continue
                score = (c["wins"] + c["losses"], c["wins"], 0)
            if score > best_score:
                best_score = score
                best = c
        if not best:
            slots.append({"assigned_weight": wt, "vacant": True})
            continue
        used.add(norm_name(best["name"]))
        idx = by_name.get(norm_name(best["name"]), {})
        photo = photo_by.get(norm_name(best["name"])) or idx.get("photo")
        # Historical grade: TW grade after season end means Sr. -> treat as that season's grade
        grade = best.get("grade") or idx.get("grade")
        if grade and str(grade).lower() in ("alumni",):
            # Prefer TW grade from dryrun when available
            grade = best.get("grade") or "—"
        slots.append({
            "assigned_weight": wt,
            "vacant": False,
            "wrestler_id": best.get("wrestler_id") or idx.get("wrestler_id"),
            "name": best["name"],
            "grade": grade,
            "wins": best["wins"],
            "losses": best["losses"],
            "photo": photo,
            "player_page": idx.get("player_page"),
            "prestige_points": idx.get("prestige_points") or 0,
            "source": method,
            "show_career": bool(idx.get("show_career")),
            "career_wins": idx.get("career_wins"),
            "career_losses": idx.get("career_losses"),
            "seasons_on_record": idx.get("seasons_on_record") or 0,
            "weights_wrestled": (idx.get("weights_by_season") or {}).get(season)
                or idx.get("career_weights")
                or ([best["weight"]] if best.get("weight") else []),
        })

    filled = sum(1 for s in slots if not s.get("vacant"))
    return {
        "schema_version": 1,
        "season": season,
        "title": short_to_label(season),
        "updated_at": _now(),
        "weight_classes": list(NJSIAA_WEIGHTS),
        "derivation": method,
        "derivation_note": (
            "Most dual appearances per NJSIAA weight from TW EventMatches captures."
            if method == "dual_bouts"
            else (
                "No TW dual lineup captures for this season; "
                "starter = most wins among wrestlers whose TW roster weight matches the class."
            )
        ),
        "counts": {
            "filled": filled,
            "vacant": len(NJSIAA_WEIGHTS) - filled,
            "weight_classes": len(NJSIAA_WEIGHTS),
            "full_roster": len(candidates),
        },
        "slots": slots,
    }


def build_stats(season: str) -> Dict[str, Any]:
    """Full W/L breakdown for Stats season dropdown."""
    existing = load_json(SEASONS / season / "stats.json")
    dry = load_json(DRYRUN / season / "wrestling_data.json") or {}
    grade_by = {
        norm_name(w["name"]): w.get("grade")
        for w in (dry.get("roster") or [])
        if w.get("name")
    }
    players_index = load_json(ROOT / "data" / "players_index.json", {"wrestlers": []})
    page_by = {
        norm_name(w["name"]): w.get("player_page")
        for w in (players_index.get("wrestlers") or [])
        if w.get("name") and w.get("player_page")
    }
    wrestlers = []
    if existing:
        for w in existing.get("wrestlers") or []:
            row = dict(w)
            nk = norm_name(w.get("name") or "")
            row["grade"] = grade_by.get(nk) or row.get("grade")
            row["player_page"] = page_by.get(nk)
            # Normalize keys for the UI
            row.setdefault("wins", row.get("win") or 0)
            row.setdefault("losses", row.get("loss") or 0)
            row.setdefault("pins", row.get("w_fall"))
            row.setdefault("weight", primary_weight_from_sheet(row.get("weights") or "") or "—")
            wrestlers.append(row)
    else:
        # Fall back to TW roster only (W-L, no breakdown)
        for w in dry.get("roster") or []:
            wins = int(w.get("wins") or 0)
            losses = int(w.get("losses") or 0)
            if wins + losses < 1:
                continue
            nk = norm_name(w.get("name") or "")
            wrestlers.append({
                "name": w.get("name"),
                "weight": w.get("weight") or "—",
                "weights": w.get("weight"),
                "grade": w.get("grade"),
                "win": wins,
                "loss": losses,
                "wins": wins,
                "losses": losses,
                "pins": w.get("pins"),
                "w_fall": w.get("pins"),
                "player_page": page_by.get(nk),
            })
    wrestlers.sort(key=lambda r: (-int(r.get("wins") or 0), int(r.get("losses") or 0), r.get("name") or ""))
    return {
        "schema_version": 1,
        "season": season,
        "title": short_to_label(season),
        "generated_at": _now(),
        "source": (existing or {}).get("source") or ("tw_roster" if dry else None),
        "has_breakdown": bool(existing),
        "count": len(wrestlers),
        "wrestlers": wrestlers,
    }


def update_history_index(seasons_built: List[str], bout_status: Dict[str, bool]) -> Dict[str, Any]:
    index = load_json(HISTORY / "index.json", {"seasons": []}) or {"seasons": []}
    by_id = {s["id"]: s for s in index.get("seasons") or []}
    for sid in seasons_built:
        entry = by_id.get(sid, {"id": sid})
        entry.update({
            "id": sid,
            "label": short_to_label(sid),
            "roster": (HISTORY / f"{sid}_roster.json").exists(),
            "stats": (HISTORY / f"{sid}_stats.json").exists(),
            "bouts": bool(bout_status.get(sid)),
            "roster_path": f"data/history/{sid}_roster.json",
            "stats_path": f"data/history/{sid}_stats.json",
            "bouts_path": f"data/history/{sid}_bouts.json",
        })
        by_id[sid] = entry
    # Also mark 2025-26 if present
    seasons_sorted = sorted(by_id.keys(), reverse=True)
    out = {
        "default": "2025-26",
        "generated_at": _now(),
        "seasons": [by_id[s] for s in seasons_sorted],
        "bouts_summary": {
            "with_bouts": sorted([s for s, ok in bout_status.items() if ok], reverse=True),
            "without_bouts": sorted([s for s, ok in bout_status.items() if not ok], reverse=True),
        },
    }
    write_json(HISTORY / "index.json", out)
    return out


def build_season(season: str, event_dir: Optional[Path] = None) -> Dict[str, Any]:
    checklist = load_json(DRYRUN / season / "capture_checklist.json")
    bouts = build_bouts_from_captures(season, checklist, event_dir)
    # Overlay 2025-26 tournament_results if captures empty but live TR exists
    if season == "2025-26" and not bouts.get("available"):
        alt = build_bouts_from_tournament_results(season)
        if alt and alt.get("available"):
            bouts = alt
    elif season == "2025-26" and bouts.get("available"):
        pass
    elif season == "2025-26":
        alt = build_bouts_from_tournament_results(season)
        if alt:
            bouts = alt

    write_json(HISTORY / f"{season}_bouts.json", bouts)
    stats = build_stats(season)
    write_json(HISTORY / f"{season}_stats.json", stats)
    # Also keep seasons/<season>/stats.json in sync when we have sheet stats
    if stats.get("has_breakdown") and not (SEASONS / season / "stats.json").exists():
        write_json(SEASONS / season / "stats.json", {
            "schema_version": stats["schema_version"],
            "season": season,
            "count": stats["count"],
            "wrestlers": [
                {k: v for k, v in w.items() if k not in ("wins", "losses", "pins", "grade", "player_page", "weight")}
                | {"name": w["name"], "weights": w.get("weights"), "win": w.get("win"), "loss": w.get("loss")}
                for w in stats["wrestlers"]
            ],
            "updated_at": _now(),
        })
    roster = build_roster(season, bouts)
    write_json(HISTORY / f"{season}_roster.json", roster)
    return {
        "season": season,
        "bouts_available": bool(bouts.get("available")),
        "events_with_bouts": bouts.get("events_with_bouts"),
        "blurb_count": bouts.get("blurb_count"),
        "roster_filled": roster["counts"]["filled"],
        "roster_method": roster["derivation"],
        "stats_count": stats["count"],
        "stats_breakdown": stats["has_breakdown"],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", action="append", dest="seasons", help="Season short id (repeatable)")
    ap.add_argument("--event-capture-dir", type=Path, default=None)
    ap.add_argument("--also-current-bouts", action="store_true", help="Also export 2025-26 bouts from tournament_results")
    args = ap.parse_args()
    seasons = args.seasons or ["2024-25"]
    if args.also_current_bouts and "2025-26" not in seasons:
        seasons = list(seasons) + ["2025-26"]
    summaries = []
    bout_status: Dict[str, bool] = {}
    for s in seasons:
        summary = build_season(s, args.event_capture_dir)
        summaries.append(summary)
        bout_status[s] = bool(summary["bouts_available"])
    # Scan existing history bout files for summary
    for p in HISTORY.glob("*_bouts.json"):
        sid = p.name.replace("_bouts.json", "")
        if sid not in bout_status:
            doc = load_json(p, {})
            bout_status[sid] = bool(doc.get("available"))
    index = update_history_index(seasons, bout_status)
    print(json.dumps({"summaries": summaries, "bouts_summary": index["bouts_summary"]}, indent=2))


if __name__ == "__main__":
    main()
