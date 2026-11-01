#!/usr/bin/env python3
"""NJSIAA prestige points from a wrestler's highest CAREER placement.

Source (cite in docs/comments only — never display Trackwrestling IDs on pages):
  https://www.njsiaa.org/sites/default/files/documents/2025-11/wrestling-boys-individual-regs-2025-26.pdf
  NJSIAA 2025-2026 Boys Wrestling Individual Championships — District Pre-Seed Chart
  (Prestige Points / Own Merit column).

Site rule (Jeff 2026-11-01): points come from the wrestler's best placement across
ALL prior seasons on record (career high), not only the immediately prior year.
Current-season placements are excluded. Per-match prestige is out of scope.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
TABLE_PATH = ROOT / "data" / "njsiaa_prestige.json"

# Official NJSIAA boys weight classes (base; post–Jan 1 growth allowance labels 108–287).
# Confirmed against TW 2025-26 Shawnee roster weights and the 14-class chart.
NJSIAA_WEIGHT_CLASSES = [
    106, 113, 120, 126, 132, 138, 144, 150, 157, 165, 175, 190, 215, 285
]


def load_table(path: Path = TABLE_PATH) -> Dict[str, Any]:
    return json.loads(path.read_text())


def _norm_name(name: str) -> str:
    s = (name or "").lower()
    s = s.replace("`", "'")
    s = re.sub(r"\([^)]*\)", " ", s)  # drop nicknames in parens
    s = re.sub(r"[^a-z\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _parse_place(placement: Any) -> Tuple[Optional[int], Optional[str]]:
    """Return (numeric_place, token) from award placement strings."""
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
        return None, token  # WB1 etc.
    if "quarter" in low:
        return None, "quarters"
    if "prelim" in low:
        return None, "prelim"
    if "2v3" in low or "2-v-3" in low:
        return None, "2v3"
    return None, None


def _season_year(season: Any) -> Optional[int]:
    """First year of a season label: '2024', '2023-24', '2024-2025' → int."""
    if season is None:
        return None
    m = re.search(r"(19|20)\d{2}", str(season))
    return int(m.group(0)) if m else None


def _current_season_years(current_season: Optional[str]) -> set:
    """Years that belong to the active season label (exclude from career prestige)."""
    if not current_season:
        return set()
    years = set(re.findall(r"(?:19|20)\d{2}", str(current_season)))
    out = {int(y) for y in years}
    # Also treat bare end-year forms
    y0 = _season_year(current_season)
    if y0:
        out.add(y0)
        out.add(y0 + 1)
    return out


def placement_to_prestige(
    level: str,
    placement: Any,
    table: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Map a single award-like placement to prestige points using the official chart + floors."""
    table = table or load_table()
    level = (level or "").lower().strip()
    place_n, place_tok = _parse_place(placement)

    # Direct chart rows
    for row in table.get("table") or []:
        if row.get("level") != level:
            continue
        rp = row.get("place")
        if isinstance(rp, int) and place_n == rp:
            return {
                "prestige_points": row["prestige_points"],
                "advancement": row["advancement"],
                "level": level,
                "placement": placement,
                "inferred": False,
            }
        if isinstance(rp, str) and place_tok and str(rp).upper() == place_tok.upper():
            return {
                "prestige_points": row["prestige_points"],
                "advancement": row["advancement"],
                "level": level,
                "placement": placement,
                "inferred": False,
            }

    floors = table.get("inferred_floors") or {}
    # Region 1–4 advance to states → WB1 States floor when no explicit state row
    if level == "region" and place_n is not None and 1 <= place_n <= 4:
        f = floors.get("region_qualifier_1_to_4") or {}
        return {
            "prestige_points": f.get("prestige_points", 65),
            "advancement": f.get("advancement", "WB1 in States (inferred)"),
            "level": level,
            "placement": placement,
            "inferred": True,
        }
    # District 1–3 advance to regions → WB1 Regions floor
    if level == "district" and place_n is not None and 1 <= place_n <= 3:
        f = floors.get("district_qualifier_1_to_3") or {}
        return {
            "prestige_points": f.get("prestige_points", 40),
            "advancement": f.get("advancement", "WB1 in Regions (inferred)"),
            "level": level,
            "placement": placement,
            "inferred": True,
        }
    return None


def awards_for_wrestler(
    awards: List[Dict[str, Any]],
    wrestler_name: str,
    wrestler_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    target = _norm_name(wrestler_name)
    if not target:
        return []
    # Build last-name match set for loose matching
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
        if an == target or (last and an.endswith(last) and (
            an.split()[0][:3] == parts[0][:3] if parts else False
        )):
            out.append(a)
            continue
        # exact last + first initial
        if last and an.endswith(" " + last) is False and an.split()[-1] == last:
            if parts and an.split()[0].startswith(parts[0][0]):
                out.append(a)
    return out


def best_career_prestige(
    wrestler_name: str,
    awards: List[Dict[str, Any]],
    current_season: Optional[str] = None,
    table: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Highest prestige across all prior seasons (career), excluding current season."""
    table = table or load_table()
    exclude_years = _current_season_years(current_season)
    best: Optional[Dict[str, Any]] = None
    recognitions: List[Dict[str, Any]] = []

    for a in awards_for_wrestler(awards, wrestler_name):
        sy = _season_year(a.get("season"))
        if sy and sy in exclude_years:
            # still list as recognition but skip for prestige
            recognitions.append({
                "season": a.get("season"),
                "award_name": a.get("award_name"),
                "award_category": a.get("award_category"),
                "placement": a.get("placement"),
                "weight": a.get("weight"),
                "counts_for_prestige": False,
                "reason": "current_season",
            })
            continue
        mapped = placement_to_prestige(a.get("award_category"), a.get("placement"), table)
        rec = {
            "season": a.get("season"),
            "award_name": a.get("award_name"),
            "award_category": a.get("award_category"),
            "placement": a.get("placement"),
            "weight": a.get("weight"),
            "counts_for_prestige": bool(mapped),
            "prestige_points": (mapped or {}).get("prestige_points"),
            "advancement": (mapped or {}).get("advancement"),
            "inferred": (mapped or {}).get("inferred", False),
        }
        recognitions.append(rec)
        if not mapped:
            continue
        if best is None or mapped["prestige_points"] > best["prestige_points"]:
            best = {
                **mapped,
                "season": a.get("season"),
                "award_name": a.get("award_name"),
                "wrestler": a.get("wrestler"),
                "weight": a.get("weight"),
            }

    recognitions.sort(
        key=lambda r: (
            -(_season_year(r.get("season")) or 0),
            str(r.get("award_category") or ""),
        )
    )
    return {
        "prestige_points": (best or {}).get("prestige_points", 0),
        "advancement": (best or {}).get("advancement"),
        "season": (best or {}).get("season"),
        "award_name": (best or {}).get("award_name"),
        "inferred": (best or {}).get("inferred", False),
        "source": "career_best_placement",
        "recognitions": recognitions,
        "has_prestige": bool(best and best.get("prestige_points")),
    }


def build_prestige_index(
    roster: List[Dict[str, Any]],
    awards_doc: Dict[str, Any],
    current_season: Optional[str] = None,
) -> Dict[str, Any]:
    table = load_table()
    awards = awards_doc.get("awards") or []
    by_id: Dict[str, Any] = {}
    for w in roster:
        wid = str(w.get("wrestler_id") or "")
        if not wid:
            continue
        by_id[wid] = {
            "wrestler_id": wid,
            "name": w.get("name"),
            **best_career_prestige(w.get("name") or "", awards, current_season, table),
        }
    return {
        "schema_version": 1,
        "source_url": table.get("source_url"),
        "rule": "career_best_prior_placement",
        "current_season": current_season,
        "wrestlers": by_id,
    }


def main():
    wd = json.loads((ROOT / "data" / "wrestling_data.json").read_text())
    awards = json.loads((ROOT / "data" / "awards.json").read_text())
    season = (wd.get("metadata") or {}).get("season") or "2025-2026"
    doc = build_prestige_index(wd.get("roster") or [], awards, season)
    out = ROOT / "data" / "prestige.json"
    out.write_text(json.dumps(doc, indent=2) + "\n")
    n = sum(1 for v in doc["wrestlers"].values() if v.get("has_prestige"))
    print(f"Wrote {out} — {n} wrestlers with prestige > 0")


if __name__ == "__main__":
    main()
