#!/usr/bin/env python3
"""
In-season auto-award detection from Trackwrestling season data.

Rules (documented in docs/AUTO_AWARDS.md):
  - Tournament placers (district / region / state) when bout/placement feed exists
  - 100-win career milestones when career rollups available

Note: Season 20+ Wins, Season Win Leaders, and Varsity Dual Record are intentionally
not auto-generated or shown on the awards page.

Returns award row dicts with auto_detected=True for merge into awards.json.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

EST = ZoneInfo("America/New_York")


def now_est() -> str:
    t = datetime.now(EST)
    s = t.strftime("%Y-%m-%dT%H:%M:%S%z")
    return s[:-2] + ":" + s[-2:]



def weight_sort_key(weight: Any) -> int:
    """Ascending weight-class order; HWT / 285 last among known classes."""
    s = str(weight or "").strip().upper()
    if not s:
        return 997
    if s in {"HWT", "HW", "HEAVY", "HEAVYWEIGHT", "HEAVY WEIGHT"}:
        return 285
    m = re.search(r"\d+", s)
    if not m:
        return 998
    n = int(m.group())
    # Treat bare 285 as heavyweight (last)
    return n


def district_region_champ_sort_key(row: Dict[str, Any]) -> tuple:
    return (
        str(row.get("season") or ""),
        weight_sort_key(row.get("weight")),
        str(row.get("wrestler") or ""),
        str(row.get("id") or ""),
    )


def sort_district_region_champions(awards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Year asc, then weight asc within year — District / Region Champions only.

    Other award rows keep their relative positions; champ slots are refilled from
    a globally sorted champ list so automation + seed stay data-driven.
    """
    champ_names = {"District Champions", "Region Champions"}
    by_name = {
        name: sorted(
            [a for a in awards if (a.get("award_name") or "") == name],
            key=district_region_champ_sort_key,
        )
        for name in champ_names
    }
    iters = {name: iter(rows) for name, rows in by_name.items()}
    out: List[Dict[str, Any]] = []
    for a in awards:
        name = a.get("award_name") or ""
        if name in iters:
            out.append(next(iters[name]))
        else:
            out.append(a)
    return out


def detect_season_awards(season_data: Dict[str, Any], placements: List[Dict] | None = None) -> List[Dict]:
    meta = season_data.get("metadata") or {}
    season_label = meta.get("season") or "unknown"
    roster = season_data.get("roster") or season_data.get("stats") or []
    derived: List[Dict] = []




    # Tournament placements — only when feed present
    for p in placements or []:
        # expected: {level: district|region|state, wrestler, weight, placement, wrestler_id?}
        level = (p.get("level") or "").lower()
        name_map = {
            "district": "District Champions" if str(p.get("placement")) in ("1", "1st", "1st Place") else "District Place Winner",
            "region": "Region Champions" if str(p.get("placement")) in ("1", "1st", "1st Place") else "Region Place Winner",
            "state": "State Champions" if str(p.get("placement")) in ("1", "1st", "1st Place") else "State Place Winner",
        }
        award_name = name_map.get(level) or f"{level.title()} Place Winner"
        category = "district" if "district" in level else ("region" if "region" in level else ("state" if "state" in level else "tournament"))
        wid = p.get("wrestler_id") or (p.get("wrestler") or "").lower().replace(" ", "-")
        derived.append({
            "id": f"auto-{season_label}-{level}-{wid}-{p.get('weight')}-{p.get('placement')}",
            "award_name": award_name,
            "award_category": category,
            "season": season_label.split("-")[-1] if category == "district" else season_label,
            "wrestler": p.get("wrestler"),
            "weight": p.get("weight"),
            "placement": p.get("placement"),
            "details": p.get("details") or f"{season_label} {level}",
            "value": None,
            "source": "trackwrestling_tournament_placement",
            "confidence": p.get("confidence") or "medium",
            "auto_detected": True,
        })

    return derived


def merge_awards(seed: List[Dict], derived: List[Dict], seed_source: str = "") -> Dict[str, Any]:
    # Drop prior auto rows from seed just in case
    historical = [a for a in seed if not a.get("auto_detected")]
    return {
        "schema_version": 1,
        "updated_at": now_est(),
        "card_template": {
            "layout": "chevron",
            "title": "top",
            "body": "rows",
            "logo": "shawnee_s_bottom",
            "district_grouping": "by_decade",
        },
        "meta": {
            "njsiaa_placements_2025_26": {
                "status": "unavailable",
                "note": (
                    "District 28 / Region 7 / State bout placements were not recoverable from TW "
                    "in the 2025-26 replay (TeamResults 404; event page scraps empty). Auto-award "
                    "rules for tournament placers are documented in docs/AUTO_AWARDS.md; entries "
                    "will populate once the bout feed or manual Jeff list is available."
                ),
            },
            "seed_source": seed_source or "awards_seed.json",
        },
        "awards": sort_district_region_champions(historical + derived),
        "seed_count": len(historical),
        "derived_2025_26_count": len(derived),
    }
