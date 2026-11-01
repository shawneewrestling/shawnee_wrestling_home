#!/usr/bin/env python3
"""Build data/varsity.json from TW dual appearances + coach overrides.

Auto rule (preferred): wrestled >= 1 Varsity dual bout this season;
weight = most frequent weight wrestled in those bouts.

Fallback (2025-26 closeout): if dual_appearances.bouts is empty, use
season_record_proxy — any wrestler with W+L >= 1 on getWrestlers, weight =
roster weight class.

Overrides in data/varsity_overrides.json always win:
  include[]  force onto varsity (optional weight, starter)
  exclude[]  force off varsity
  weight_overrides {wrestler_id: weight}
  starters {weight: wrestler_id}
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

EST = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parent


def now_est() -> str:
    t = datetime.now(EST)
    s = t.strftime("%Y-%m-%dT%H:%M:%S%z")
    return s[:-2] + ":" + s[-2:]


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text())


def build_varsity(
    wrestling_data: Dict[str, Any],
    appearances: Dict[str, Any],
    overrides: Dict[str, Any],
) -> Dict[str, Any]:
    roster = wrestling_data.get("roster") or []
    by_id = {str(w.get("wrestler_id")): w for w in roster if w.get("wrestler_id")}
    bouts = [b for b in (appearances.get("bouts") or []) if (b.get("level") or "Varsity").lower() == "varsity"]

    auto: Dict[str, Dict[str, Any]] = {}
    method = "dual_bouts"

    if bouts:
        weights: Dict[str, Counter] = defaultdict(Counter)
        counts: Dict[str, int] = defaultdict(int)
        names: Dict[str, str] = {}
        for b in bouts:
            wid = str(b.get("wrestler_id") or "")
            if not wid:
                continue
            counts[wid] += 1
            names[wid] = b.get("name") or names.get(wid) or ""
            wt = str(b.get("weight") or "").strip()
            if wt:
                weights[wid][wt] += 1
        for wid, n in counts.items():
            if n < 1:
                continue
            wt = weights[wid].most_common(1)[0][0] if weights[wid] else (by_id.get(wid) or {}).get("weight")
            base = by_id.get(wid) or {}
            auto[wid] = {
                "wrestler_id": wid,
                "name": names.get(wid) or base.get("name"),
                "weight": wt,
                "grade": base.get("grade"),
                "wins": base.get("wins") or 0,
                "losses": base.get("losses") or 0,
                "varsity_bouts": n,
                "weight_counts": dict(weights[wid]),
                "source": "dual_bouts",
            }
    else:
        method = "season_record_proxy"
        for w in roster:
            wins = w.get("wins") or 0
            losses = w.get("losses") or 0
            if wins + losses < 1:
                continue
            wid = str(w.get("wrestler_id"))
            auto[wid] = {
                "wrestler_id": wid,
                "name": w.get("name"),
                "weight": w.get("weight"),
                "grade": w.get("grade"),
                "wins": wins,
                "losses": losses,
                "varsity_bouts": None,
                "weight_counts": {str(w.get("weight")): 1} if w.get("weight") else {},
                "source": "season_record_proxy",
            }

    # Apply overrides
    exclude_ids = {str(x.get("wrestler_id")) for x in (overrides.get("exclude") or []) if x.get("wrestler_id")}
    for wid in list(auto.keys()):
        if wid in exclude_ids:
            del auto[wid]

    for inc in overrides.get("include") or []:
        wid = str(inc.get("wrestler_id") or "")
        if not wid:
            continue
        base = by_id.get(wid) or {}
        row = auto.get(wid) or {
            "wrestler_id": wid,
            "name": inc.get("name") or base.get("name"),
            "weight": None,
            "grade": base.get("grade"),
            "wins": base.get("wins") or 0,
            "losses": base.get("losses") or 0,
            "varsity_bouts": 0,
            "weight_counts": {},
            "source": "override_include",
        }
        if inc.get("weight"):
            row["weight"] = str(inc["weight"])
        if inc.get("name"):
            row["name"] = inc["name"]
        row["override"] = True
        if inc.get("starter") is not None:
            row["starter"] = bool(inc["starter"])
        auto[wid] = row

    for wid, wt in (overrides.get("weight_overrides") or {}).items():
        if wid in auto and wt:
            auto[wid]["weight"] = str(wt)
            auto[wid]["weight_override"] = True

    starters = overrides.get("starters") or {}
    starter_ids = set()
    for wt, wid in starters.items():
        wid = str(wid)
        starter_ids.add(wid)
        if wid in auto:
            auto[wid]["starter"] = True
            if wt:
                auto[wid]["weight"] = str(wt)

    for wid, row in auto.items():
        if "starter" not in row:
            row["starter"] = wid in starter_ids

    wrestlers = sorted(
        auto.values(),
        key=lambda r: (int(r["weight"]) if str(r.get("weight") or "").isdigit() else 999, r.get("name") or ""),
    )

    return {
        "schema_version": 1,
        "season": (wrestling_data.get("metadata") or {}).get("season"),
        "season_id": (wrestling_data.get("metadata") or {}).get("season_id"),
        "updated_at": now_est(),
        "derivation": method,
        "derivation_note": (
            "Built from Varsity dual bout appearances (most-frequent weight)."
            if method == "dual_bouts"
            else (
                "TW dual bout feed unavailable for 2025-26 replay — proxy: wrestlers with "
                "season W+L >= 1 from getWrestlers; weight = TW roster weight. Coach overrides "
                "in varsity_overrides.json win. Replace dual_appearances.json bouts to switch "
                "to true dual-bout derivation."
            )
        ),
        "counts": {
            "auto": len([w for w in wrestlers if not w.get("override")]),
            "total": len(wrestlers),
            "excluded": len(exclude_ids),
            "full_roster": len(roster),
        },
        "wrestlers": wrestlers,
    }


def main():
    wd = load_json(ROOT / "data" / "wrestling_data.json", {})
    appearances = load_json(ROOT / "data" / "dual_appearances.json", {"bouts": []})
    overrides = load_json(ROOT / "data" / "varsity_overrides.json", {})
    doc = build_varsity(wd, appearances, overrides)
    out = ROOT / "data" / "varsity.json"
    out.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"Wrote {out} — {doc['counts']['total']} varsity ({doc['derivation']})")


if __name__ == "__main__":
    main()
