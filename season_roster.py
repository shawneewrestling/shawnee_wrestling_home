#!/usr/bin/env python3
"""Season kickoff roster hygiene.

When a new season starts:
  - Drop anyone who was a Senior in a concluded prior season (graduates)
  - Rematch returners onto the new Trackwrestling roster (new wrestler_ids)
  - Prefer TW grade / W-L for the new season (0-0 in preseason)
  - If TW still shows last year's grade, advance Fr→So→Jr→Sr
  - Keep graduate photos and player cards as alumni history

Used by update_site_data.py and as a standalone repair:
  python season_roster.py
  python season_roster.py --prior-season 2025-26
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
from zoneinfo import ZoneInfo

EST = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parent
SEASONS_DIR = ROOT / "data" / "seasons"

GRADE_ORDER = ["Fr.", "So.", "Jr.", "Sr."]
GRADE_ALIASES = {
    "fr": "Fr.",
    "fr.": "Fr.",
    "freshman": "Fr.",
    "9": "Fr.",
    "so": "So.",
    "so.": "So.",
    "sophomore": "So.",
    "10": "So.",
    "jr": "Jr.",
    "jr.": "Jr.",
    "junior": "Jr.",
    "11": "Jr.",
    "sr": "Sr.",
    "sr.": "Sr.",
    "senior": "Sr.",
    "12": "Sr.",
}


def now_est() -> str:
    t = datetime.now(EST)
    s = t.strftime("%Y-%m-%dT%H:%M:%S%z")
    return s[:-2] + ":" + s[-2:]


def name_key(name: str) -> str:
    s = re.sub(r"[`'\"]", "", (name or "").lower())
    s = re.sub(r"\(.*?\)", " ", s)
    parts = re.findall(r"[a-z]+", s)
    if len(parts) >= 2:
        return parts[0] + parts[-1]
    return "".join(parts)


def normalize_grade(grade: Optional[str]) -> Optional[str]:
    if grade is None:
        return None
    raw = str(grade).strip()
    if not raw:
        return None
    return GRADE_ALIASES.get(raw.lower(), raw if raw in GRADE_ORDER else raw)


def advance_grade(grade: Optional[str]) -> Optional[str]:
    g = normalize_grade(grade)
    if g is None:
        return None
    if g not in GRADE_ORDER:
        return g
    idx = GRADE_ORDER.index(g)
    if idx >= len(GRADE_ORDER) - 1:
        return "Sr."  # already senior — caller should have filtered graduates
    return GRADE_ORDER[idx + 1]


def season_short(label: str) -> str:
    """2026-2027 / 2026-27 → 2026-27."""
    s = (label or "").strip()
    m = re.match(r"^(\d{4})-(\d{2,4})$", s)
    if not m:
        return s
    a, b = m.group(1), m.group(2)
    if len(b) == 4:
        b = b[-2:]
    return f"{a}-{b}"


def season_long(label: str) -> str:
    """2026-27 → 2026-2027."""
    s = season_short(label)
    m = re.match(r"^(\d{4})-(\d{2})$", s)
    if not m:
        return label
    return f"{m.group(1)}-20{m.group(2)}"


def prior_season_of(season: str) -> str:
    s = season_short(season)
    m = re.match(r"^(\d{4})-(\d{2})$", s)
    if not m:
        raise ValueError(f"Cannot derive prior season from {season!r}")
    start = int(m.group(1))
    return f"{start - 1}-{str(start)[-2:]}"


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _roster_from_season_dir(season: str) -> List[Dict[str, Any]]:
    """Prefer archived final, then season wrestling_data, then roster.json."""
    short = season_short(season)
    base = SEASONS_DIR / short
    for name in (
        "wrestling_data_final.json",
        "wrestling_data.json",
        "tw_pull/wrestling_data.json",
        "roster.json",
        "tw_pull/roster.json",
    ):
        path = base / name
        if not path.exists():
            continue
        doc = load_json(path, {})
        if isinstance(doc, list):
            return doc
        if isinstance(doc, dict):
            if isinstance(doc.get("roster"), list):
                return doc["roster"]
            if isinstance(doc.get("wrestlers"), list):
                return doc["wrestlers"]
    return []


def seniors_from_roster(roster: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for row in roster:
        g = normalize_grade(row.get("grade") or row.get("class"))
        if g == "Sr.":
            out.append(row)
    return out


def graduate_name_keys(prior_season: str) -> Set[str]:
    roster = _roster_from_season_dir(prior_season)
    keys = {name_key(r.get("name") or "") for r in seniors_from_roster(roster)}
    return {k for k in keys if k}


def photo_by_name_key(root: Path = ROOT) -> Dict[str, str]:
    """Map name_key → relative photo path from assets/img/roster and known JSON."""
    out: Dict[str, str] = {}
    photo_dir = root / "assets" / "img" / "roster"
    if photo_dir.exists():
        for p in photo_dir.iterdir():
            if not p.is_file():
                continue
            if p.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                continue
            # strip optional wp- prefix for matching
            stem = p.stem
            if stem.startswith("wp-"):
                stem = stem[3:]
            key = name_key(stem.replace("-", " "))
            if key:
                out.setdefault(key, f"assets/img/roster/{p.name}")

    for rel in (
        "data/home_roster.json",
        "data/varsity_assignments.json",
        "data/players_index.json",
        "data/wrestling_data.json",
    ):
        doc = load_json(root / rel, {}) or {}
        rows: List[Dict[str, Any]] = []
        if isinstance(doc.get("wrestlers"), list):
            rows.extend(doc["wrestlers"])
        if isinstance(doc.get("slots"), list):
            rows.extend(doc["slots"])
        if isinstance(doc.get("roster"), list):
            rows.extend(doc["roster"])
        for row in rows:
            photo = row.get("photo")
            nm = row.get("name")
            if photo and nm:
                out.setdefault(name_key(nm), photo)
    return out


def index_roster_by_name(roster: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    by: Dict[str, Dict[str, Any]] = {}
    for row in roster:
        key = name_key(row.get("name") or "")
        if key:
            by[key] = row
    return by



def load_prior_home_varsity(
    root: Path,
    prior_season: str,
    fallback_home: Dict[str, Any],
    fallback_va: Dict[str, Any],
    current_season: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Prefer archived prior-season home/varsity so re-runs do not double-advance grades.

    If on-disk home/varsity already claim the *current* season, they are polluted
    kickoff output — do not treat them as prior cards.
    """
    short = season_short(prior_season)
    base = SEASONS_DIR / short
    home = None
    va = None
    for name in ("home_roster_final.json", "home_roster.json"):
        p = base / name
        if p.exists():
            home = load_json(p, {})
            break
    for name in ("varsity_assignments_final.json", "varsity_assignments.json"):
        p = base / name
        if p.exists():
            va = load_json(p, {})
            break
    cur_s = season_short(current_season)
    # Fallbacks only if they still look like the prior season
    if home is None:
        fb_s = season_short(str((fallback_home or {}).get("season") or ""))
        if fb_s and fb_s != cur_s:
            home = fallback_home
    if va is None:
        fb_s = season_short(str((fallback_va or {}).get("season") or ""))
        if fb_s and fb_s != cur_s:
            va = fallback_va
    return home or {}, va or {}


def filter_graduates(
    roster: List[Dict[str, Any]],
    graduate_keys: Set[str],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    kept: List[Dict[str, Any]] = []
    removed: List[str] = []
    for row in roster:
        nm = row.get("name") or ""
        key = name_key(nm)
        if key and key in graduate_keys:
            removed.append(nm)
            continue
        kept.append(row)
    return kept, removed


def maybe_advance_grade(tw_grade: Optional[str], prior_grade: Optional[str]) -> Optional[str]:
    """Prefer TW grade; if TW still shows prior-season grade, advance one year."""
    tw = normalize_grade(tw_grade)
    prior = normalize_grade(prior_grade)
    if tw and prior and tw == prior and prior in GRADE_ORDER and prior != "Sr.":
        return advance_grade(prior)
    if tw:
        return tw
    if prior and prior != "Sr.":
        return advance_grade(prior)
    return tw or prior


def sanitize_current_roster(
    roster: List[Dict[str, Any]],
    *,
    graduate_keys: Set[str],
    prior_by_name: Optional[Dict[str, Dict[str, Any]]] = None,
    force_zero_record: bool = False,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Drop graduates TW may have rolled forward; fix stuck grades; optional 0-0."""
    prior_by_name = prior_by_name or {}
    cleaned, removed = filter_graduates(roster, graduate_keys)
    grade_fixes = 0
    record_fixes = 0
    out: List[Dict[str, Any]] = []
    for row in cleaned:
        r = dict(row)
        key = name_key(r.get("name") or "")
        prior = prior_by_name.get(key) or {}
        new_grade = maybe_advance_grade(r.get("grade"), prior.get("grade"))
        if new_grade and new_grade != normalize_grade(r.get("grade")):
            grade_fixes += 1
        if new_grade:
            r["grade"] = new_grade
        if force_zero_record or (
            (r.get("wins") or 0) == 0 and (r.get("losses") or 0) == 0
        ):
            # Always normalize None → 0; force_zero_record clears leftover prior W-L
            if force_zero_record and ((r.get("wins") or 0) or (r.get("losses") or 0)):
                record_fixes += 1
            if force_zero_record:
                r["wins"] = 0
                r["losses"] = 0
            else:
                r["wins"] = int(r.get("wins") or 0)
                r["losses"] = int(r.get("losses") or 0)
        out.append(r)
    report = {
        "removed_graduates": removed,
        "grade_fixes": grade_fixes,
        "record_fixes": record_fixes,
        "roster_count": len(out),
    }
    return out, report


def _slug(name: str, wid: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (name or "wrestler").lower()).strip("-")
    return f"{base}-{wid[-6:]}" if wid else base


def build_home_and_varsity_from_prior(
    *,
    current_roster: List[Dict[str, Any]],
    current_season: str,
    prior_home: Dict[str, Any],
    prior_varsity: Dict[str, Any],
    graduate_keys: Set[str],
    career_by_key: Optional[Dict[str, Dict[str, Any]]] = None,
    photos: Optional[Dict[str, str]] = None,
    prior_by_name: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
    """Rebuild home_roster + varsity_assignments for the new season.

    Starts from prior varsity starter slots (or prior home cards), drops graduates,
    rematches returners onto the current TW roster, uses TW grade/W-L, keeps photos
    and provisional assigned weights until the coach sets new starters.
    """
    career_by_key = career_by_key or {}
    photos = photos or photo_by_name_key()
    prior_by_name = prior_by_name or {}
    by_name = index_roster_by_name(current_roster)
    season_l = season_long(current_season)
    season_s = season_short(current_season)

    # Prefer prior varsity slots (14 weights); fall back to home wrestlers list
    prior_slots = list(prior_varsity.get("slots") or [])
    if not prior_slots:
        for w in prior_home.get("wrestlers") or []:
            prior_slots.append(
                {
                    "assigned_weight": w.get("display_weight") or w.get("assigned_weight"),
                    "name": w.get("name"),
                    "grade": w.get("grade"),
                    "wins": w.get("wins"),
                    "losses": w.get("losses"),
                    "photo": w.get("photo"),
                    "wrestler_id": w.get("wrestler_id"),
                    "weights_wrestled": w.get("weights_wrestled") or [],
                    "vacant": False,
                }
            )

    removed: List[str] = []
    new_slots: List[Dict[str, Any]] = []
    home_cards: List[Dict[str, Any]] = []

    # Ensure we cover all NJSIAA weights in order when prior had them
    from prestige import NJSIAA_WEIGHT_CLASSES

    weight_order = [str(w) for w in NJSIAA_WEIGHT_CLASSES]
    slot_by_wt = {
        str(s.get("assigned_weight")): s
        for s in prior_slots
        if s.get("assigned_weight") is not None
    }

    for wt in weight_order:
        prev = slot_by_wt.get(wt) or {}
        nm = (prev.get("name") or "").strip()
        if not nm or prev.get("vacant"):
            new_slots.append(
                {
                    "assigned_weight": wt,
                    "vacant": True,
                    "wrestler_id": None,
                    "name": None,
                    "grade": None,
                    "wins": None,
                    "losses": None,
                    "photo": None,
                    "player_page": None,
                    "prestige_points": 0,
                    "prestige": None,
                    "source": None,
                }
            )
            continue

        key = name_key(nm)
        if key in graduate_keys:
            removed.append(nm)
            new_slots.append(
                {
                    "assigned_weight": wt,
                    "vacant": True,
                    "wrestler_id": None,
                    "name": None,
                    "grade": None,
                    "wins": None,
                    "losses": None,
                    "photo": None,
                    "player_page": None,
                    "prestige_points": 0,
                    "prestige": None,
                    "source": "vacated_graduate",
                }
            )
            continue

        tw = by_name.get(key)
        if not tw:
            # Returner missing from TW — leave vacant rather than show a ghost
            removed.append(f"{nm} (not on TW {season_s})")
            new_slots.append(
                {
                    "assigned_weight": wt,
                    "vacant": True,
                    "wrestler_id": None,
                    "name": None,
                    "grade": None,
                    "wins": None,
                    "losses": None,
                    "photo": None,
                    "player_page": None,
                    "prestige_points": 0,
                    "prestige": None,
                    "source": "vacated_missing_tw",
                }
            )
            continue

        wid = str(tw.get("wrestler_id") or "")
        prior_row = prior_by_name.get(key) or {}
        # Grade from prior *season roster*, not the (possibly already advanced) slot
        grade = maybe_advance_grade(tw.get("grade"), prior_row.get("grade") or prev.get("grade"))
        wins = int(tw.get("wins") or 0)
        losses = int(tw.get("losses") or 0)
        photo = tw.get("photo") or prev.get("photo") or photos.get(key)
        career = career_by_key.get(key) or {}
        # Prefer career_records totals; season W-L is current (0-0)
        show_career = bool(career.get("show_career")) or (
            int(career.get("seasons_on_record") or 0) > 1
        )
        weights = list(tw.get("weights_wrestled") or prev.get("weights_wrestled") or [])
        if tw.get("weight") and str(tw.get("weight")) not in weights:
            weights = [str(tw["weight"])] + weights if not weights else weights

        page = f"players/{_slug(tw.get('name') or nm, wid)}.html"
        slot = {
            "assigned_weight": wt,
            "vacant": False,
            "wrestler_id": wid,
            "name": tw.get("name") or nm,
            "grade": grade,
            "wins": wins,
            "losses": losses,
            "photo": photo,
            "player_page": page,
            "prestige_points": prev.get("prestige_points") or 0,
            "prestige": prev.get("prestige"),
            "source": "kickoff_returner",
            "show_career": show_career,
            "career_wins": career.get("career_wins"),
            "career_losses": career.get("career_losses"),
            "seasons_on_record": career.get("seasons_on_record") or 0,
            "weights_wrestled": weights,
        }
        new_slots.append(slot)
        home_cards.append(
            {
                "name": slot["name"],
                "wrestler_id": wid,
                "display_weight": wt,
                "assigned_weight": wt,
                "grade": grade,
                "wins": wins,
                "losses": losses,
                "photo": photo,
                "player_page": page,
                "weights_wrestled": weights,
                "matched": bool(photo),
                "show_career": show_career,
                "career_wins": career.get("career_wins"),
                "career_losses": career.get("career_losses"),
                "seasons_on_record": career.get("seasons_on_record") or 0,
            }
        )

    home_doc = {
        "schema_version": 1,
        "season": season_l,
        "updated_at": now_est(),
        "source_note": (
            f"Kickoff home cards: prior varsity starters rematched to {season_s} TW roster; "
            "graduates removed; grades/W-L from TW (preseason 0-0). "
            "Provisional weights until coach sets 2026-27 starters."
        ),
        "counts": {
            "starters": len(home_cards),
            "with_photo": sum(1 for c in home_cards if c.get("photo")),
            "weight_classes": len(weight_order),
            "vacant": sum(1 for s in new_slots if s.get("vacant")),
        },
        "wrestlers": home_cards,
        "removed_graduates": sorted({n for n in removed if "(not on TW" not in n}),
        "prior_season_cards": season_short(prior_home.get("season") or prior_varsity.get("season") or ""),
    }

    varsity_doc = {
        "schema_version": 1,
        "season": season_l,
        "updated_at": now_est(),
        "weight_classes": weight_order,
        "derivation": "kickoff_from_prior_minus_graduates",
        "derivation_note": (
            "Preseason kickoff: prior-season one-per-weight starters rematched to the new "
            "TW roster by name. Seniors from the concluded season are vacated. Grades and "
            "W-L come from TW (0-0 until duals). Coach Jotform / varsity_overrides.starters "
            "override once set."
        ),
        "counts": {
            "filled": sum(1 for s in new_slots if not s.get("vacant")),
            "vacant": sum(1 for s in new_slots if s.get("vacant")),
            "weight_classes": len(weight_order),
            "full_roster": len(current_roster),
        },
        "slots": new_slots,
        "removed_graduates": home_doc["removed_graduates"],
    }
    return home_doc, varsity_doc, removed


def career_index(path: Path) -> Dict[str, Dict[str, Any]]:
    doc = load_json(path, {}) or {}
    out: Dict[str, Dict[str, Any]] = {}
    for row in doc.get("wrestlers") or []:
        key = name_key(row.get("name") or "") or row.get("name_key") or ""
        if not key:
            continue
        out[key] = {
            "show_career": bool(row.get("show_career"))
            or int(row.get("seasons_on_record") or 0) > 1,
            "career_wins": row.get("career_wins"),
            "career_losses": row.get("career_losses"),
            "seasons_on_record": row.get("seasons_on_record") or 0,
            "name": row.get("name"),
            "wrestler_id": row.get("wrestler_id"),
            "prior_wins": row.get("prior_wins"),
            "prior_losses": row.get("prior_losses"),
        }
    return out


def recent_graduates_for_alumni(
    prior_season: str,
    current_roster: List[Dict[str, Any]],
    *,
    career_by_key: Dict[str, Dict[str, Any]],
    photos: Dict[str, str],
    prior_players: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Build alumni rows for seniors from the concluded season who are off the new roster."""
    current_keys = {name_key(r.get("name") or "") for r in current_roster}
    seniors = seniors_from_roster(_roster_from_season_dir(prior_season))
    prior_pi = {
        name_key(r.get("name") or ""): r for r in (prior_players or []) if r.get("name")
    }
    alumni: List[Dict[str, Any]] = []
    for row in seniors:
        nm = row.get("name") or ""
        key = name_key(nm)
        if not key or key in current_keys:
            continue
        career = career_by_key.get(key) or {}
        prior = prior_pi.get(key) or {}
        wid = str(row.get("wrestler_id") or prior.get("wrestler_id") or "")
        photo = prior.get("photo") or photos.get(key) or row.get("photo")
        alumni.append(
            {
                "wrestler_id": wid,
                "name": nm,
                "grade": "Alumni",
                "weight": row.get("weight") or prior.get("roster_weight"),
                "wins": 0,
                "losses": 0,
                "photo": photo,
                "alumni": True,
                "status": "alumni",
                "graduated_after": season_short(prior_season),
                "career_weights": list(
                    prior.get("weights_wrestled") or row.get("weights_wrestled") or []
                ),
                "weights_by_season": prior.get("weights_by_season") or {},
                "show_career": career.get("show_career"),
                "career_wins": career.get("career_wins"),
                "career_losses": career.get("career_losses"),
                "seasons_on_record": career.get("seasons_on_record") or 0,
            }
        )
    return alumni


def apply_kickoff_roster_hygiene(
    *,
    root: Path = ROOT,
    current_season: Optional[str] = None,
    prior_season: Optional[str] = None,
    force_zero_record: bool = True,
    write: bool = True,
) -> Dict[str, Any]:
    wd_path = root / "data" / "wrestling_data.json"
    wd = load_json(wd_path, {})
    meta = wd.get("metadata") or {}
    cur = season_short(
        current_season
        or meta.get("season_short")
        or meta.get("season")
        or "2026-27"
    )
    prior = season_short(prior_season or prior_season_of(cur))

    graduate_keys = graduate_name_keys(prior)
    prior_roster = _roster_from_season_dir(prior)
    prior_by_name = index_roster_by_name(prior_roster)

    roster_in = list(wd.get("roster") or [])
    roster_out, sanitize_report = sanitize_current_roster(
        roster_in,
        graduate_keys=graduate_keys,
        prior_by_name=prior_by_name,
        force_zero_record=force_zero_record
        or (meta.get("season_status") == "preseason")
        or (meta.get("mode") == "preseason"),
    )
    wd["roster"] = roster_out
    if "metadata" in wd:
        wd["metadata"]["roster_count"] = len(roster_out)

    career_by = career_index(root / "data" / "career_records.json")
    # Also fold career.json if present
    for k, v in career_index(root / "data" / "career.json").items():
        career_by.setdefault(k, v)

    photos = photo_by_name_key(root)
    # Attach photos onto current roster by name when TW has none
    for row in roster_out:
        if not row.get("photo"):
            p = photos.get(name_key(row.get("name") or ""))
            if p:
                row["photo"] = p

    disk_home = load_json(root / "data" / "home_roster.json", {}) or {}
    disk_va = load_json(root / "data" / "varsity_assignments.json", {}) or {}
    prior_home, prior_va = load_prior_home_varsity(
        root, prior, disk_home, disk_va, cur
    )
    if not (prior_home.get("wrestlers") or prior_va.get("slots")):
        # Last resort: scrub whatever is on disk (first kickoff before archive exists)
        prior_home, prior_va = disk_home, disk_va
    home_doc, varsity_doc, removed = build_home_and_varsity_from_prior(
        current_roster=roster_out,
        current_season=cur,
        prior_home=prior_home,
        prior_varsity=prior_va,
        graduate_keys=graduate_keys,
        career_by_key=career_by,
        photos=photos,
        prior_by_name=prior_by_name,
    )

    prior_pi = (load_json(root / "data" / "players_index.json", {}) or {}).get(
        "wrestlers"
    ) or []
    alumni_rows = recent_graduates_for_alumni(
        prior,
        roster_out,
        career_by_key=career_by,
        photos=photos,
        prior_players=prior_pi,
    )

    report = {
        "current_season": cur,
        "prior_season": prior,
        "graduate_keys": sorted(graduate_keys),
        "graduates_removed_from_home": home_doc.get("removed_graduates") or [],
        "sanitize": sanitize_report,
        "home_starters": home_doc["counts"]["starters"],
        "home_vacant": home_doc["counts"]["vacant"],
        "roster_count": len(roster_out),
        "alumni_from_prior_seniors": [a["name"] for a in alumni_rows],
        "removed_detail": removed,
    }

    if write:
        wd_path.write_text(json.dumps(wd, indent=2) + "\n", encoding="utf-8")
        (root / "wrestling_data.json").write_text(
            json.dumps(wd, indent=2) + "\n", encoding="utf-8"
        )
        (root / "data" / "home_roster.json").write_text(
            json.dumps(home_doc, indent=2) + "\n", encoding="utf-8"
        )
        (root / "data" / "varsity_assignments.json").write_text(
            json.dumps(varsity_doc, indent=2) + "\n", encoding="utf-8"
        )
        # Persist alumni payload for players_build to consume
        alum_path = root / "data" / "recent_graduates.json"
        alum_doc = {
            "schema_version": 1,
            "graduated_after": prior,
            "current_season": cur,
            "updated_at": now_est(),
            "count": len(alumni_rows),
            "wrestlers": alumni_rows,
        }
        alum_path.write_text(json.dumps(alum_doc, indent=2) + "\n", encoding="utf-8")
        (root / "data" / "kickoff_roster_hygiene.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )

    report["home_doc"] = home_doc
    report["varsity_doc"] = varsity_doc
    report["alumni_rows"] = alumni_rows
    report["wrestling_data"] = wd
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prior-season", default=None)
    ap.add_argument("--current-season", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--keep-records",
        action="store_true",
        help="Do not force W-L to 0-0 (default forces zero in preseason)",
    )
    args = ap.parse_args()
    report = apply_kickoff_roster_hygiene(
        current_season=args.current_season,
        prior_season=args.prior_season,
        force_zero_record=not args.keep_records,
        write=not args.dry_run,
    )
    # Don't dump huge docs to stdout
    slim = {k: v for k, v in report.items() if k not in {"home_doc", "varsity_doc", "alumni_rows", "wrestling_data"}}
    print(json.dumps(slim, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
