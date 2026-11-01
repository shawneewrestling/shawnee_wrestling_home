#!/usr/bin/env python3
"""NJSIAA prestige points from a wrestler's highest CAREER placement.

Source (cite in docs/comments only — never display on pages):
  https://www.njsiaa.org/sites/default/files/documents/2025-11/wrestling-boys-individual-regs-2025-26.pdf
  NJSIAA District Pre-Seed Chart — Prestige Points (Own Merit) column.

Site rule (Jeff 2026-11-01):
  - Career-best NJSIAA individual finish (District → Region → State).
  - District 1st–3rd / region 1st–4th are qualifiers: score by how far they
    got in the *next* tournament (never invent a floor).
  - District 3rd + region first-round loss → "2v3 in Regions" (35).
  - Region 7th or 8th → "WB1 in Regions" (40).
  - Never entered districts → 0.
  - If a qualifier's next-tournament depth cannot be determined → unknown
    (do not fabricate). Closed 2025-26 site includes all seasons on record.
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
TABLE_PATH = ROOT / "data" / "njsiaa_prestige.json"
SHEET_DIR = Path("/workspace/shawnee/history/individual_sheet")
TRACKTEST = SHEET_DIR / "TrackTest.csv"
HISTORY_DIR = ROOT / "data" / "history"
TOURNAMENT_RESULTS = ROOT / "data" / "tournament_results.json"
AWARDS_PATH = ROOT / "data" / "awards.json"

# Official NJSIAA boys weight classes
NJSIAA_WEIGHT_CLASSES = [
    106, 113, 120, 126, 132, 138, 144, 150, 157, 165, 175, 190, 215, 285
]

# Sheet Advancement abbreviations → (level, place_token)
ADVANCEMENT_CODES = {
    "s1": ("state", 1),
    "s2": ("state", 2),
    "s3": ("state", 3),
    "s4": ("state", 4),
    "s5": ("state", 5),
    "s6": ("state", 6),
    "s7": ("state", 7),
    "s8": ("state", 8),
    "swb1": ("state", "WB1"),
    "swb2": ("state", "WB2"),
    "swb3": ("state", "WB3"),
    "swb4": ("state", "WB4"),
    # Reached states round of 16 / early champ-bracket exit — chart floor WB1
    "sr16": ("state", "WB1"),
    "r5": ("region", 5),
    "r6": ("region", 6),
    "r7": ("region", 7),
    "r8": ("region", 8),
    "rwb1": ("region", "WB1"),
    "r2v3": ("region", "2v3"),
    "2v3": ("region", "2v3"),
    "d4": ("district", 4),
    "dqf": ("district", "quarters"),
    "d qf": ("district", "quarters"),
    "qd": ("district", "quarters"),
    "dprelim": ("district", "prelim"),
    "dp": ("district", "prelim"),
    "prelim": ("district", "prelim"),
    "np": ("none", None),
    "no postseason": ("none", None),
    "-": ("none", None),
}

# Confirmed from NJSIAA individual season record (Jeff paste). Year label =
# season-ending calendar year → prior season (2023 → 2022-23).
# Only fill gaps; bout/sheet evidence still wins when richer.
NJSIAA_RECORD_OVERRIDES = {
    # 2023 swb1, 2024 S4 Place, 2025 District Qtrs (Qtrs DISAGREES with TW D1 — keep TW)
    ("jordansegal", "2022-23"): ("state", "WB1", "njsiaa_record:2023_swb1"),
}

# 2025-26 NJSIAA event ids in tournament_results / history bouts
NJSIAA_EVENTS_2025_26 = {
    "8978282132": ("district", "2025-26"),
    "8978292132": ("region", "2025-26"),
    "8978305132": ("state", "2025-26"),
}


def load_table(path: Path = TABLE_PATH) -> Dict[str, Any]:
    return json.loads(path.read_text())


def _norm_name(name: str) -> str:
    s = (name or "").lower()
    s = s.replace("`", "'")
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^a-z\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def name_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def _season_year(season: Any) -> Optional[int]:
    if season is None:
        return None
    m = re.search(r"(19|20)\d{2}", str(season))
    return int(m.group(0)) if m else None


def _chart_row(level: str, place: Any, table: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Exact chart lookup (no inferred floors)."""
    level = (level or "").lower().strip()
    place_n = place if isinstance(place, int) else None
    place_tok = None
    if isinstance(place, str):
        place_tok = place.upper() if place.upper().startswith("WB") or place.lower() == "2v3" else place.lower()
        if place_tok == "2V3":
            place_tok = "2v3"
    for row in table.get("table") or []:
        if row.get("level") != level:
            continue
        rp = row.get("place")
        if isinstance(rp, int) and place_n == rp:
            return {
                "prestige_points": row["prestige_points"],
                "advancement": row["advancement"],
                "level": level,
                "placement": place,
                "inferred": False,
            }
        if isinstance(rp, str) and place_tok and str(rp).upper() == str(place_tok).upper():
            return {
                "prestige_points": row["prestige_points"],
                "advancement": row["advancement"],
                "level": level,
                "placement": place,
                "inferred": False,
            }
        if rp is None and level == "none" and place is None:
            return {
                "prestige_points": 0,
                "advancement": row["advancement"],
                "level": "none",
                "placement": None,
                "inferred": False,
            }
    # Region 7/8 → WB1 in Regions (Jeff)
    if level == "region" and place_n in (7, 8):
        for row in table.get("table") or []:
            if row.get("advancement") == "WB1 in Regions":
                return {
                    "prestige_points": row["prestige_points"],
                    "advancement": "WB1 in Regions",
                    "level": "region",
                    "placement": place,
                    "inferred": False,
                }
    return None


def placement_to_prestige(
    level: str,
    placement: Any,
    table: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Map a terminal (non-qualifier-only) placement to chart points."""
    table = table or load_table()
    level = (level or "").lower().strip()
    place_n, place_tok = _parse_place(placement)

    if place_n is not None:
        hit = _chart_row(level, place_n, table)
        if hit:
            hit["placement"] = placement
            return hit
    if place_tok:
        hit = _chart_row(level, place_tok, table)
        if hit:
            hit["placement"] = placement
            return hit
    return None


def _parse_place(placement: Any) -> Tuple[Optional[int], Optional[str]]:
    if placement is None:
        return None, None
    raw = str(placement).strip()
    if not raw:
        return None, None
    low = raw.lower()
    if "national champion" in low or low in {"champ", "champion", "1st", "1", "first"}:
        return 1, "1"
    m = re.match(r"^(\d+)(st|nd|rd|th)?\b", low)
    if m:
        return int(m.group(1)), m.group(1)
    if low.startswith("wb"):
        token = low.replace(" ", "").upper()
        return None, token
    if "quarter" in low:
        return None, "quarters"
    if "prelim" in low:
        return None, "prelim"
    if "2v3" in low or "2-v-3" in low:
        return None, "2v3"
    return None, None


# ---------------------------------------------------------------------------
# Bout / path helpers
# ---------------------------------------------------------------------------

_ROUND_ORDER = [
    "prelim",
    "champ. round 1",
    "champ. round 2",
    "quarterfinals",
    "semifinals",
    "1st place match",
    "3rd place match",
    "5th place match",
    "7th place match",
    "cons. round 1",
    "cons. round 2",
    "cons. round 3",
    "cons. round 4",
    "cons. semis",
]


def _round_label(raw: Optional[str]) -> str:
    s = (raw or "").strip().lower()
    for label in _ROUND_ORDER:
        if label in s:
            return label
    return s


def _shawnee_won_summary(summary: str, wrestler_name: str) -> Optional[bool]:
    """True if Shawnee wrestler won, False if lost, None if unclear."""
    s = summary or ""
    name = wrestler_name
    if f"{name} (Shawnee) received a bye" in s or f"{name} (Shawnee) over" in s:
        return True
    if f"over {name} (Shawnee)" in s:
        return False
    # Last-name fallback for backtick / nickname variants
    parts = _norm_name(name).split()
    if not parts:
        return None
    last = parts[-1]
    first = parts[0]
    low = s.lower()
    if "shawnee" not in low:
        return None
    if "received a bye" in low and first in low:
        return True
    # "First Last (Shawnee) over"
    if re.search(rf"{re.escape(first)}\s+[\w`']*\s*{re.escape(last)}\s*\(shawnee\)\s+over", low):
        return True
    if re.search(rf"over\s+{re.escape(first)}\s+[\w`']*\s*{re.escape(last)}\s*\(shawnee\)", low):
        return False
    return None


def _finish_from_bouts(
    level: str,
    bouts: List[Dict[str, Any]],
    *,
    is_qualifier_from_prior: bool = False,
) -> Tuple[Optional[Any], Optional[str]]:
    """Infer a place/token from bout list for one tournament level.

    Returns (place_or_token, note). place_or_token matches chart place field.
    """
    if not bouts:
        return None, "no_bouts"

    # Explicit placement field on wrestler aggregate
    for b in bouts:
        if b.get("_placement"):
            pn, pt = _parse_place(b["_placement"])
            return (pn if pn is not None else pt), "explicit_placement"

    results = []
    for b in bouts:
        rnd = _round_label(b.get("round"))
        res = b.get("result")
        if res not in ("W", "L"):
            continue
        results.append((rnd, res, b))

    if not results:
        return None, "no_decided_bouts"

    # Place matches
    for rnd, res, _ in results:
        if rnd == "1st place match" and res == "W":
            return 1, "1st_place_match"
        if rnd == "1st place match" and res == "L":
            return 2, "lost_final"
        if rnd == "3rd place match" and res == "W":
            return 3, "3rd_place_match"
        if rnd == "3rd place match" and res == "L":
            return 4, "lost_3rd"
        if rnd == "5th place match" and res == "W":
            return 5, "5th_place_match"
        if rnd == "5th place match" and res == "L":
            return 6, "lost_5th"
        if rnd == "7th place match" and res == "W":
            return 7, "7th_place_match"
        if rnd == "7th place match" and res == "L":
            return 8, "lost_7th"

    # State / region wrestleback depth
    if level == "state":
        max_cons = 0
        won_cons = set()
        for rnd, res, _ in results:
            m = re.match(r"cons\. round (\d+)", rnd)
            if m:
                n = int(m.group(1))
                max_cons = max(max_cons, n)
                if res == "W":
                    won_cons.add(n)
            if rnd == "cons. semis":
                max_cons = max(max_cons, 3)
                if res == "W":
                    won_cons.add(3)
        if max_cons >= 1:
            # Furthest WB round reached
            wb = min(max_cons, 4)
            return f"WB{wb}", f"cons_round_{max_cons}"
        # Made states but only champ-bracket losses
        champ_rounds = [r for r, res, _ in results if r.startswith("champ")]
        if champ_rounds:
            return "WB1", "state_champ_bracket_only"
        return None, "state_unclear"

    if level == "region":
        # Consolation wins → at least WB1; place already handled above
        cons_wins = [r for r, res, _ in results if res == "W" and r.startswith("cons")]
        if cons_wins:
            return "WB1", "region_cons_win"
        # First contested championship loss with no cons wins
        contested = [(r, res) for r, res, b in results if not (
            (b.get("win_type") or "").lower() == "bye" or "bye" in (b.get("round") or "").lower()
        )]
        # Also treat bye-only then loss
        losses = [(r, res) for r, res, _ in results if res == "L"]
        wins_non_bye = [
            (r, res) for r, res, b in results
            if res == "W" and "bye" not in (b.get("win_type") or "").lower()
            and "bye" not in r
        ]
        if losses and not wins_non_bye and not cons_wins:
            # District qualifier early exit → 2v3
            if is_qualifier_from_prior:
                return "2v3", "region_early_exit"
            return "2v3", "region_early_exit"
        if losses and not cons_wins:
            # Won a champ bout then lost, no cons — still early relative to places
            if is_qualifier_from_prior or True:
                # Reached quarters or further without place → WB1 floor not automatic
                deepest_loss = losses[-1][0]
                if deepest_loss in ("champ. round 1", "quarterfinals"):
                    return "2v3", f"region_loss_{deepest_loss}"
                return "WB1", f"region_loss_{deepest_loss}"
        return None, "region_unclear"

    if level == "district":
        # Lost in quarters (after possible CR1) without place match
        rounds_hit = {r for r, _, _ in results}
        losses = {r for r, res, _ in results if res == "L"}
        if "quarterfinals" in losses and "semifinals" not in rounds_hit:
            return "quarters", "district_qf_loss"
        if "champ. round 1" in losses and "quarterfinals" not in rounds_hit:
            return "prelim", "district_cr1_loss"
        if "prelim" in losses:
            return "prelim", "district_prelim_loss"
        # Lost semis + lost 3rd already handled; lost semis without 3rd match?
        if "semifinals" in losses and "3rd place match" not in rounds_hit:
            return 4, "district_semi_loss_no_3rd"
        return None, "district_unclear"

    return None, "unhandled"


def _region_qualifies_for_states(region: Any) -> bool:
    return isinstance(region, int) and 1 <= region <= 4


def _score_path(
    district: Optional[Any],
    region: Optional[Any],
    state: Optional[Any],
    table: Dict[str, Any],
    *,
    district_known_absent: bool = False,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Apply Jeff's qualifier rule. Returns (scored, unknown_reason)."""
    # Region non-qualifiers cannot have a state finish — drop conflicting state
    if state is not None and region is not None and not _region_qualifies_for_states(region):
        state = None
    # State finish is always terminal when present
    if state is not None:
        hit = _chart_row("state", state, table) or placement_to_prestige("state", state, table)
        if hit:
            return hit, None
        return None, f"unmapped_state:{state}"

    if region is not None:
        # Region 1–4 advance to states — need state depth
        if isinstance(region, int) and 1 <= region <= 4:
            return None, f"region_{region}_missing_state"
        hit = _chart_row("region", region, table)
        if hit:
            return hit, None
        return None, f"unmapped_region:{region}"

    if district is not None:
        # District 1–3 advance to regions — need region depth
        if isinstance(district, int) and 1 <= district <= 3:
            return None, f"district_{district}_missing_region"
        hit = _chart_row("district", district, table)
        if hit:
            return hit, None
        return None, f"unmapped_district:{district}"

    if district_known_absent:
        hit = _chart_row("none", None, table)
        return hit, None

    return None, None  # no postseason info (not necessarily unknown)


# ---------------------------------------------------------------------------
# Source loaders → per-wrestler season paths
# ---------------------------------------------------------------------------

def _empty_path() -> Dict[str, Any]:
    return {
        "district": None,
        "region": None,
        "state": None,
        "sources": [],
        "district_known_absent": False,
        "notes": [],
    }


def _paths() -> Dict[str, Dict[str, Dict[str, Any]]]:
    """name_key → season_label → path dict."""
    return defaultdict(lambda: defaultdict(_empty_path))


def _canonical_season(label: str) -> str:
    """Normalize to YYYY-YY when possible."""
    s = (label or "").strip()
    m = re.match(r"^(20\d{2})-(\d{2}|\d{4})$", s)
    if m:
        y = int(m.group(1))
        return f"{y}-{str(y + 1)[-2:]}"
    m = re.match(r"^(19|20)(\d{2})$", s)
    if m:
        y = int(s)
        # Award/sheet calendar year of March tournament → season (y-1)-YY
        return f"{y - 1}-{str(y)[-2:]}"
    return s


def _set_level(path: Dict[str, Any], level: str, place: Any, source: str) -> None:
    if place is None:
        return
    cur = path.get(level)
    # Prefer more specific / better numeric place; tokens overwrite None
    if cur is None:
        path[level] = place
        path["sources"].append(f"{source}:{level}={place}")
        return
    # Numeric places: keep best (lowest number) for champ places; for 5-8 keep as is if already set
    if isinstance(cur, int) and isinstance(place, int):
        # For placement, lower is better at top; but 5th vs 6th both valid — keep better (lower)
        if place < cur:
            path[level] = place
            path["sources"].append(f"{source}:{level}={place}")
        return
    # Don't overwrite numeric with token
    if isinstance(cur, int) and isinstance(place, str):
        return
    if isinstance(cur, str) and isinstance(place, int):
        path[level] = place
        path["sources"].append(f"{source}:{level}={place}")
        return
    if cur != place:
        # Prefer higher WB number / keep first
        if isinstance(cur, str) and isinstance(place, str) and cur.startswith("WB") and place.startswith("WB"):
            if int(place[2:]) > int(cur[2:]):
                path[level] = place
                path["sources"].append(f"{source}:{level}={place}")
        elif cur in ("quarters", "prelim") and isinstance(place, str):
            path[level] = place
            path["sources"].append(f"{source}:{level}={place}")


def load_paths_from_tournament_results(paths: Dict) -> None:
    if not TOURNAMENT_RESULTS.exists():
        return
    tr = json.loads(TOURNAMENT_RESULTS.read_text())
    for eid, meta in NJSIAA_EVENTS_2025_26.items():
        level, season = meta
        ev = tr.get(eid)
        if not ev:
            continue
        for w in ev.get("wrestlers") or []:
            name = w.get("wrestler") or ""
            key = name_key(name)
            if not key:
                continue
            path = paths[key][season]
            place = w.get("placement")
            bouts = []
            for b in w.get("bouts") or []:
                bouts.append({
                    "round": b.get("round"),
                    "result": b.get("result"),
                    "win_type": b.get("win_type"),
                })
            if place:
                pn, pt = _parse_place(place)
                _set_level(path, level, pn if pn is not None else pt, "tournament_results")
            else:
                inferred, note = _finish_from_bouts(
                    level,
                    bouts,
                    is_qualifier_from_prior=(level == "region" and (
                        isinstance(paths[key][season].get("district"), int)
                        and 1 <= paths[key][season]["district"] <= 3
                    )),
                )
                if inferred is not None:
                    _set_level(path, level, inferred, f"tournament_results_bouts:{note}")
                elif note:
                    path["notes"].append(f"{level}:{note}")


def load_paths_from_history_bouts(paths: Dict) -> None:
    for fname, season in (("2025-26_bouts.json", "2025-26"), ("2024-25_bouts.json", "2024-25")):
        fp = HISTORY_DIR / fname
        if not fp.exists():
            continue
        doc = json.loads(fp.read_text())
        for eid, ev in (doc.get("events") or {}).items():
            name = (ev.get("event_name") or "").lower()
            if "njsiaa" not in name:
                continue
            if "district" in name:
                level = "district"
            elif "region" in name:
                level = "region"
            elif "state" in name:
                level = "state"
            else:
                continue
            if not ev.get("available"):
                continue
            for w in ev.get("wrestlers") or []:
                wname = w.get("wrestler") or ""
                key = name_key(wname)
                if not key:
                    continue
                path = paths[key][season]
                if w.get("placement"):
                    pn, pt = _parse_place(w["placement"])
                    _set_level(path, level, pn if pn is not None else pt, f"history_bouts:{fname}")
                    continue
                bouts = [{
                    "round": b.get("round"),
                    "result": b.get("result"),
                    "win_type": b.get("win_type"),
                } for b in (w.get("bouts") or [])]
                dist = path.get("district")
                inferred, note = _finish_from_bouts(
                    level,
                    bouts,
                    is_qualifier_from_prior=(
                        level == "region" and isinstance(dist, int) and 1 <= dist <= 3
                    ),
                )
                if inferred is not None:
                    _set_level(path, level, inferred, f"history_bouts:{note}")


def load_paths_from_tracktest(paths: Dict) -> None:
    if not TRACKTEST.exists():
        return
    # TrackTest covers 2024-25 NJSIAA (dates in Feb/Mar 2025)
    season = "2024-25"
    by: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    with TRACKTEST.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            ev = row.get("Event") or ""
            if not ev.lower().startswith("njsiaa"):
                continue
            if "district" in ev.lower():
                level = "district"
            elif "region" in ev.lower():
                level = "region"
            elif "state" in ev.lower():
                level = "state"
            else:
                continue
            wname = (row.get("Wrestler") or "").split(" - ", 1)[-1].strip()
            key = name_key(wname)
            if not key:
                continue
            summary = row.get("Summary") or ""
            won = _shawnee_won_summary(summary, wname)
            rnd = "?"
            for label in [
                "1st Place Match", "3rd Place Match", "5th Place Match", "7th Place Match",
                "Semifinals", "Quarterfinals", "Champ. Round 1", "Champ. Round 2",
                "Cons. Round 1", "Cons. Round 2", "Cons. Round 3", "Cons. Round 4",
                "Cons. Semis", "Prelim",
            ]:
                if label in summary:
                    rnd = label
                    break
            by[key][level].append({
                "round": rnd,
                "result": "W" if won is True else ("L" if won is False else "?"),
                "win_type": "Bye" if "bye" in summary.lower() else None,
                "summary": summary,
                "_name": wname,
            })

    for key, levels in by.items():
        path = paths[key][season]
        # Prefer a real display name from the first bout row
        for bouts in levels.values():
            for b in bouts:
                if b.get("_name"):
                    path["display_name"] = b["_name"]
                    break
            if path.get("display_name"):
                break
        # District first so region can see qualifier
        for level in ("district", "region", "state"):
            bouts = levels.get(level) or []
            if not bouts:
                continue
            dist = path.get("district")
            inferred, note = _finish_from_bouts(
                level,
                bouts,
                is_qualifier_from_prior=(
                    level == "region" and isinstance(dist, int) and 1 <= dist <= 3
                ),
            )
            if inferred is not None:
                _set_level(path, level, inferred, f"tracktest:{note}")
            elif note:
                path["notes"].append(f"{level}:{note}")


def load_paths_from_advancement(paths: Dict) -> None:
    if not SHEET_DIR.exists():
        return
    for year in range(2015, 2025):
        fp = SHEET_DIR / f"{year}.csv"
        if not fp.exists():
            continue
        season = _canonical_season(str(year))  # calendar year of tournament → prior season label
        with fp.open(newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                adv = (row.get("Advancement") or "").strip()
                if not adv:
                    continue
                # current_sortable sometimes concatenates
                adv_main = adv.split(",")[0].strip()
                code = ADVANCEMENT_CODES.get(adv_main.lower())
                if code is None:
                    # try compact
                    code = ADVANCEMENT_CODES.get(re.sub(r"\s+", "", adv_main.lower()))
                name = (row.get("Name") or "").strip() or f"{row.get('First', '')} {row.get('Last', '')}".strip()
                key = name_key(name)
                if not key or code is None:
                    if key and adv_main.lower() in {"4th region", "region 4th", "r4"}:
                        path = paths[key][season]
                        path["display_name"] = name or path.get("display_name")
                        _set_level(path, "region", 4, f"sheet_advancement:{year}")
                        path["notes"].append("region_4_needs_state")
                    continue
                level, place = code
                path = paths[key][season]
                if name:
                    path["display_name"] = name
                if level == "none":
                    path["district_known_absent"] = True
                    path["sources"].append(f"sheet_advancement:{year}:never")
                    continue
                _set_level(path, level, place, f"sheet_advancement:{year}")

    # current_sortable.csv / current_auto.csv are incomplete stubs (e.g. Sean Bradley
    # wrongly coded "s4"); 2025-26 comes from TW bout captures instead.


def load_paths_from_awards(paths: Dict, awards: List[Dict[str, Any]]) -> None:
    for a in awards:
        cat = (a.get("award_category") or "").lower()
        if cat not in {"state", "region", "district"}:
            continue
        name = a.get("wrestler") or ""
        key = name_key(name)
        if not key:
            continue
        season = _canonical_season(str(a.get("season") or ""))
        if not season:
            continue
        path = paths[key][season]
        pn, pt = _parse_place(a.get("placement"))
        place = pn if pn is not None else pt
        if place is None:
            continue
        _set_level(path, cat, place, f"awards:{a.get('id') or a.get('award_name')}")


def collect_all_paths(
    awards: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    paths = _paths()
    if awards is None:
        if AWARDS_PATH.exists():
            awards = json.loads(AWARDS_PATH.read_text()).get("awards") or []
        else:
            awards = []
    # Order: sheet advancement (historical), awards, tracktest, tournament/history bouts (prefer recent bout detail)
    load_paths_from_advancement(paths)
    load_paths_from_awards(paths, awards)
    load_paths_from_tracktest(paths)
    load_paths_from_history_bouts(paths)
    load_paths_from_tournament_results(paths)
    # Fill gaps from NJSIAA individual-record paste (never overwrite richer data)
    for (key, season), (level, place, note) in NJSIAA_RECORD_OVERRIDES.items():
        path = paths[key][season]
        if path.get(level) is None:
            _set_level(path, level, place, note)
        # State finish makes district/region qualifier path complete for scoring
        if level == "state" and path.get("district") is not None and path.get("region") is None:
            # District champ/2nd/3rd who reached states — region depth implied by state
            pass
    return paths


def score_season_path(
    path: Dict[str, Any],
    table: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    table = table or load_table()
    return _score_path(
        path.get("district"),
        path.get("region"),
        path.get("state"),
        table,
        district_known_absent=bool(path.get("district_known_absent")),
    )


def best_career_from_paths(
    name: str,
    paths_by_season: Dict[str, Dict[str, Any]],
    table: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    table = table or load_table()
    best: Optional[Dict[str, Any]] = None
    recognitions: List[Dict[str, Any]] = []
    unknown_seasons: List[Dict[str, Any]] = []

    for season, path in sorted(paths_by_season.items(), key=lambda x: x[0], reverse=True):
        scored, unk = score_season_path(path, table)
        rec = {
            "season": season,
            "district": path.get("district"),
            "region": path.get("region"),
            "state": path.get("state"),
            "sources": list(path.get("sources") or []),
            "counts_for_prestige": bool(scored and (scored.get("prestige_points") or 0) > 0),
            "prestige_points": (scored or {}).get("prestige_points"),
            "advancement": (scored or {}).get("advancement"),
            "unknown_reason": unk,
        }
        recognitions.append(rec)
        if unk and (path.get("district") is not None or path.get("region") is not None or path.get("state") is not None):
            unknown_seasons.append({
                "season": season,
                "reason": unk,
                "district": path.get("district"),
                "region": path.get("region"),
                "state": path.get("state"),
            })
        if not scored:
            continue
        pts = scored.get("prestige_points") or 0
        if best is None or pts > (best.get("prestige_points") or 0):
            best = {
                **scored,
                "season": season,
                "wrestler": name,
            }

    return {
        "prestige_points": (best or {}).get("prestige_points", 0) or 0,
        "advancement": (best or {}).get("advancement"),
        "season": (best or {}).get("season"),
        "award_name": None,
        "inferred": (best or {}).get("inferred", False),
        "source": "career_best_njsiaa",
        "recognitions": recognitions,
        "has_prestige": bool(best and (best.get("prestige_points") or 0) > 0),
        "unknown_seasons": unknown_seasons,
    }


def awards_for_wrestler(
    awards: List[Dict[str, Any]],
    wrestler_name: str,
    wrestler_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Kept for callers that still filter awards by name."""
    target = _norm_name(wrestler_name)
    if not target:
        return []
    parts = target.split()
    last = parts[-1] if parts else ""
    out = []
    for a in awards:
        cat = (a.get("award_category") or "").lower()
        if cat not in {"state", "region", "district"}:
            continue
        an = _norm_name(a.get("wrestler") or "")
        if not an:
            continue
        if an == target or (last and an.split()[-1] == last and parts and an.split()[0][:3] == parts[0][:3]):
            out.append(a)
    return out


def best_career_prestige(
    wrestler_name: str,
    awards: List[Dict[str, Any]],
    current_season: Optional[str] = None,
    table: Optional[Dict[str, Any]] = None,
    paths_index: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """Highest prestige across all seasons on record (career best).

    ``current_season`` is accepted for API compatibility but no longer excludes
    seasons on the closed 2025-26 site — Jeff: career-best finish.
    """
    table = table or load_table()
    if paths_index is None:
        paths_index = collect_all_paths(awards)
    key = name_key(wrestler_name)
    by_season = paths_index.get(key) or {}
    # Ensure award-only names still get award paths if collect was partial
    if not by_season and awards:
        tmp = _paths()
        load_paths_from_awards(tmp, awards_for_wrestler(awards, wrestler_name))
        by_season = tmp.get(key) or {}
    return best_career_from_paths(wrestler_name, by_season, table)


def build_prestige_index(
    roster: List[Dict[str, Any]],
    awards_doc: Dict[str, Any],
    current_season: Optional[str] = None,
) -> Dict[str, Any]:
    table = load_table()
    awards = awards_doc.get("awards") or []
    paths_index = collect_all_paths(awards)

    by_id: Dict[str, Any] = {}
    unknowns: List[Dict[str, Any]] = []
    seen_unknown_keys = set()

    def _add_unknown(name: str, wid: Optional[str], detail: Dict[str, Any]) -> None:
        key = name_key(name)
        uk = f"{key}:{detail.get('season')}:{detail.get('reason')}"
        if uk in seen_unknown_keys:
            return
        seen_unknown_keys.add(uk)
        unknowns.append({
            "name": name,
            "wrestler_id": wid,
            **detail,
        })

    for w in roster:
        wid = str(w.get("wrestler_id") or "")
        if not wid:
            continue
        name = w.get("name") or ""
        scored = best_career_prestige(name, awards, current_season, table, paths_index)
        by_id[wid] = {
            "wrestler_id": wid,
            "name": name,
            **scored,
        }
        for u in scored.get("unknown_seasons") or []:
            _add_unknown(name, wid, u)

    # Also score notable names from paths not on current roster (alumni)
    roster_keys = {name_key(w.get("name") or "") for w in roster}
    by_name: Dict[str, Any] = {}
    for key, by_season in paths_index.items():
        # pick a display name from sources / first recognition
        display = None
        for w in roster:
            if name_key(w.get("name") or "") == key:
                display = w.get("name")
                break
        if not display:
            for a in awards:
                if name_key(a.get("wrestler") or "") == key:
                    display = a.get("wrestler")
                    break
        if not display:
            for path in by_season.values():
                if path.get("display_name"):
                    display = path["display_name"]
                    break
        if not display:
            display = key
        scored = best_career_from_paths(display, by_season, table)
        by_name[key] = {"name": display, **scored}
        if key not in roster_keys:
            for u in scored.get("unknown_seasons") or []:
                _add_unknown(display, None, u)

    unknowns.sort(key=lambda x: (x.get("name") or "", x.get("season") or ""))

    return {
        "schema_version": 2,
        "source_url": table.get("source_url"),
        "rule": "career_best_njsiaa_finish",
        "current_season": current_season,
        "wrestlers": by_id,
        "by_name": by_name,
        "unknowns": unknowns,
    }


def main():
    wd = json.loads((ROOT / "data" / "wrestling_data.json").read_text())
    awards = json.loads((ROOT / "data" / "awards.json").read_text())
    season = (wd.get("metadata") or {}).get("season") or "2025-2026"
    doc = build_prestige_index(wd.get("roster") or [], awards, season)
    out = ROOT / "data" / "prestige.json"
    out.write_text(json.dumps(doc, indent=2) + "\n")
    n = sum(1 for v in doc["wrestlers"].values() if v.get("has_prestige"))
    print(f"Wrote {out} — {n} roster wrestlers with prestige > 0")
    print(f"Unknowns: {len(doc.get('unknowns') or [])}")
    # Top by prestige across by_name
    ranked = sorted(
        (doc.get("by_name") or {}).values(),
        key=lambda x: (-(x.get("prestige_points") or 0), x.get("name") or ""),
    )
    print("Top 10:")
    for row in ranked[:10]:
        if not row.get("prestige_points"):
            break
        print(f"  {row.get('prestige_points'):3}  {row.get('name')}  ({row.get('advancement')}, {row.get('season')})")
    # Leeland
    lr = (doc.get("by_name") or {}).get(name_key("Leeland Rogers")) or {}
    print(f"Leeland Rogers: {lr.get('prestige_points')} ({lr.get('advancement')}, {lr.get('season')})")


if __name__ == "__main__":
    main()
