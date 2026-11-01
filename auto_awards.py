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

from datetime import datetime
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

EST = ZoneInfo("America/New_York")


def now_est() -> str:
    t = datetime.now(EST)
    s = t.strftime("%Y-%m-%dT%H:%M:%S%z")
    return s[:-2] + ":" + s[-2:]


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
        "awards": historical + derived,
        "seed_count": len(historical),
        "derived_2025_26_count": len(derived),
    }
