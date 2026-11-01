#!/usr/bin/env python3
"""One starter per NJSIAA weight class → data/varsity_assignments.json.

Assigned weight class is stored independently of weights a wrestler has wrestled.

Seed (2025-26): reuse varsity.py appearance logic — for each NJSIAA class pick the
wrestler with the most varsity dual appearances at that weight (fallback: most
season bouts / wins among roster rows whose TW roster weight matches).

Coach Jotform submissions override the seed via ingest_jotform_submission().
Also writes data/jotform_roster_options.json for populating Jotform dropdowns.

Do not create the Jotform yet — schema + stub only.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from prestige import NJSIAA_WEIGHT_CLASSES, build_prestige_index
from varsity import build_varsity

EST = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parent

WEIGHT_STRS = [str(w) for w in NJSIAA_WEIGHT_CLASSES]


def now_est() -> str:
    t = datetime.now(EST)
    s = t.strftime("%Y-%m-%dT%H:%M:%S%z")
    return s[:-2] + ":" + s[-2:]


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text())


def _slug(name: str, wid: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (name or "wrestler").lower()).strip("-")
    return f"{base}-{wid[-6:]}" if wid else base


def seed_assignments_from_appearances(
    wrestling_data: Dict[str, Any],
    appearances: Dict[str, Any],
    overrides: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """Map weight → wrestler row using most appearances per weight (one per class)."""
    varsity_doc = build_varsity(wrestling_data, appearances, overrides)
    roster = wrestling_data.get("roster") or []
    by_id = {str(w.get("wrestler_id")): w for w in roster if w.get("wrestler_id")}

    # Count appearances per (wrestler, weight) from dual bouts when present
    bouts = [
        b
        for b in (appearances.get("bouts") or [])
        if (b.get("level") or "Varsity").lower() == "varsity"
    ]
    pair_counts: Dict[tuple, int] = defaultdict(int)
    if bouts:
        for b in bouts:
            wid = str(b.get("wrestler_id") or "")
            wt = str(b.get("weight") or "").strip()
            if wid and wt:
                pair_counts[(wid, wt)] += 1

    # Fallback: season_record_proxy wrestlers keyed by their roster/TW weight
    proxy_by_weight: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for w in varsity_doc.get("wrestlers") or []:
        wt = str(w.get("weight") or "").strip()
        if wt:
            proxy_by_weight[wt].append(w)

    chosen: Dict[str, Dict[str, Any]] = {}
    used_ids: set = set()

    for wt in WEIGHT_STRS:
        candidates: List[tuple] = []  # (score, wins, name, row)
        if pair_counts:
            for (wid, wtw), n in pair_counts.items():
                if wtw != wt or wid in used_ids:
                    continue
                base = by_id.get(wid) or {}
                row = {
                    "wrestler_id": wid,
                    "name": base.get("name"),
                    "grade": base.get("grade"),
                    "wins": base.get("wins") or 0,
                    "losses": base.get("losses") or 0,
                    "photo": base.get("photo"),
                }
                candidates.append((n, row["wins"], row.get("name") or "", row))
        if not candidates:
            for w in proxy_by_weight.get(wt) or []:
                wid = str(w.get("wrestler_id"))
                if wid in used_ids:
                    continue
                # Prefer higher bout total, then wins
                score = w.get("varsity_bouts") or ((w.get("wins") or 0) + (w.get("losses") or 0))
                candidates.append((score, w.get("wins") or 0, w.get("name") or "", {
                    "wrestler_id": wid,
                    "name": w.get("name"),
                    "grade": w.get("grade"),
                    "wins": w.get("wins") or 0,
                    "losses": w.get("losses") or 0,
                    "photo": (by_id.get(wid) or {}).get("photo"),
                }))
        if not candidates:
            continue
        candidates.sort(key=lambda t: (-t[0], -t[1], t[2]))
        _score, _wins, _name, row = candidates[0]
        used_ids.add(row["wrestler_id"])
        chosen[wt] = {
            **row,
            "assigned_weight": wt,
            "source": "auto_seed",
        }
    return chosen


def apply_jotform_override_map(
    assignments: Dict[str, Dict[str, Any]],
    override_by_weight: Dict[str, Dict[str, Any]],
    roster_by_id: Dict[str, Dict[str, Any]],
    roster_by_name: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Merge coach weight→wrestler overrides (from Jotform or hand edit)."""
    out = dict(assignments)
    for wt, payload in (override_by_weight or {}).items():
        wt = str(wt)
        if wt not in WEIGHT_STRS:
            continue
        wid = str(payload.get("wrestler_id") or "").strip()
        name = (payload.get("name") or "").strip()
        base = None
        if wid and wid in roster_by_id:
            base = roster_by_id[wid]
        elif name:
            key = name.lower()
            base = roster_by_name.get(key)
            if not base:
                # fuzzy: last name
                for n, w in roster_by_name.items():
                    if n.endswith(key.split()[-1]) and key.split()[0][:1] == n.split()[0][:1]:
                        base = w
                        break
        if not base:
            # clear slot if explicitly null
            if payload.get("clear"):
                out.pop(wt, None)
            continue
        out[wt] = {
            "wrestler_id": str(base.get("wrestler_id")),
            "name": base.get("name"),
            "grade": base.get("grade"),
            "wins": base.get("wins") or 0,
            "losses": base.get("losses") or 0,
            "photo": base.get("photo"),
            "assigned_weight": wt,
            "source": "jotform" if payload.get("from_jotform") else "coach_override",
        }
    # Ensure uniqueness: if same wrestler in two weights via override, keep override weights
    # and drop earlier auto_seed duplicates
    seen = {}
    for wt in list(out.keys()):
        wid = out[wt]["wrestler_id"]
        if wid in seen and out[wt].get("source") == "auto_seed":
            del out[wt]
            continue
        if wid in seen and out[seen[wid]].get("source") == "auto_seed" and out[wt].get("source") != "auto_seed":
            del out[seen[wid]]
        seen[wid] = wt
    return out


def ingest_jotform_submission(
    submission: Dict[str, Any],
    roster: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Convert one Jotform submission JSON into weight→wrestler override map.

    Expected shape (planned form — not created yet)::

        {
          "submissionID": "…",
          "created_at": "…",
          "answers": {
            "106": {"name": "Daniel Fitzpatrick", "wrestler_id": "35217300132"},
            "113": "Matt Hart",
            …
            "285": {"name": "Collin McHugh"}
          }
        }

    Field names may also be ``weight_106`` / ``wt_106``. Answers may be plain
    name strings or objects with name / wrestler_id. Empty / "Vacant" clears.
    """
    roster_by_id = {str(w["wrestler_id"]): w for w in roster if w.get("wrestler_id")}
    roster_by_name = {(w.get("name") or "").lower(): w for w in roster}

    answers = submission.get("answers") or submission.get("content") or submission
    if not isinstance(answers, dict):
        raise ValueError("Jotform submission missing answers object")

    override: Dict[str, Dict[str, Any]] = {}
    for key, raw in answers.items():
        m = re.search(r"(106|113|120|126|132|138|144|150|157|165|175|190|215|285)", str(key))
        if not m:
            continue
        wt = m.group(1)
        if raw is None or raw == "" or str(raw).strip().lower() in {"vacant", "none", "n/a", "-"}:
            override[wt] = {"clear": True, "from_jotform": True}
            continue
        if isinstance(raw, dict):
            override[wt] = {
                "wrestler_id": raw.get("wrestler_id") or raw.get("id"),
                "name": raw.get("name") or raw.get("text") or raw.get("answer"),
                "from_jotform": True,
            }
        else:
            override[wt] = {"name": str(raw).strip(), "from_jotform": True}
    # Validate names resolve (do not raise — leave unresolved out)
    return apply_jotform_override_map({}, override, roster_by_id, roster_by_name)


def build_jotform_options(roster: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Active roster list for Jotform dropdown population."""
    options = []
    for w in sorted(roster, key=lambda x: ((x.get("last_name") or x.get("name") or ""), x.get("name") or "")):
        wid = str(w.get("wrestler_id") or "")
        name = w.get("name") or ""
        if not wid or not name:
            continue
        options.append({
            "wrestler_id": wid,
            "name": name,
            "grade": w.get("grade"),
            "roster_weight": w.get("weight"),
            "label": f"{name} ({w.get('grade') or '?'})",
        })
    return {
        "schema_version": 1,
        "updated_at": now_est(),
        "weight_classes": WEIGHT_STRS,
        "options": options,
        "jotform_note": (
            "Rebuild this file on every roster scrape. Point each weight-class dropdown "
            "at options[].label (store wrestler_id in a hidden field or parse from submission)."
        ),
    }


def build_varsity_assignments(
    wrestling_data: Dict[str, Any],
    appearances: Dict[str, Any],
    overrides: Dict[str, Any],
    awards_doc: Dict[str, Any],
    jotform_overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    roster = wrestling_data.get("roster") or []
    roster_by_id = {str(w["wrestler_id"]): w for w in roster if w.get("wrestler_id")}
    roster_by_name = {(w.get("name") or "").lower(): w for w in roster}
    season = (wrestling_data.get("metadata") or {}).get("season") or "2025-2026"

    seeded = seed_assignments_from_appearances(wrestling_data, appearances, overrides)

    # Hand / Jotform weight map in varsity_overrides.starters already {weight: id}
    starter_map = {
        str(wt): {"wrestler_id": str(wid), "from_jotform": False}
        for wt, wid in (overrides.get("starters") or {}).items()
    }
    if jotform_overrides:
        # jotform_overrides may be full assignment doc or {weight: {...}}
        raw = jotform_overrides.get("by_weight") if "by_weight" in jotform_overrides else jotform_overrides
        for wt, payload in (raw or {}).items():
            if isinstance(payload, dict):
                starter_map[str(wt)] = {**payload, "from_jotform": payload.get("from_jotform", True)}
            else:
                starter_map[str(wt)] = {"wrestler_id": str(payload), "from_jotform": True}

    assignments = apply_jotform_override_map(seeded, starter_map, roster_by_id, roster_by_name)

    prestige = build_prestige_index(roster, awards_doc, season)
    prest_by_id = prestige.get("wrestlers") or {}

    slots = []
    for wt in WEIGHT_STRS:
        row = assignments.get(wt)
        if not row:
            slots.append({
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
            })
            continue
        wid = row["wrestler_id"]
        p = prest_by_id.get(wid) or {}
        slots.append({
            "assigned_weight": wt,
            "vacant": False,
            "wrestler_id": wid,
            "name": row.get("name"),
            "grade": row.get("grade"),
            "wins": row.get("wins") or 0,
            "losses": row.get("losses") or 0,
            "photo": row.get("photo"),
            "player_page": f"players/{_slug(row.get('name') or '', wid)}.html",
            "prestige_points": p.get("prestige_points") or 0,
            "prestige": {
                "points": p.get("prestige_points") or 0,
                "advancement": p.get("advancement"),
                "season": p.get("season"),
                "inferred": p.get("inferred", False),
            } if p.get("has_prestige") else None,
            "source": row.get("source"),
        })

    return {
        "schema_version": 1,
        "season": season,
        "updated_at": now_est(),
        "weight_classes": WEIGHT_STRS,
        "derivation": "one_per_njsiaa_weight",
        "derivation_note": (
            "One wrestler per NJSIAA weight class. Auto-seeded from most varsity dual "
            "appearances at that weight (fallback: season record proxy by roster weight). "
            "Assigned class is independent of weights wrestled. Coach Jotform / "
            "varsity_overrides.starters override the seed. Prestige = career-best prior "
            "NJSIAA placement (not current season)."
        ),
        "counts": {
            "filled": sum(1 for s in slots if not s.get("vacant")),
            "vacant": sum(1 for s in slots if s.get("vacant")),
            "weight_classes": len(WEIGHT_STRS),
            "full_roster": len(roster),
        },
        "slots": slots,
    }


def main():
    wd = load_json(ROOT / "data" / "wrestling_data.json", {})
    appearances = load_json(ROOT / "data" / "dual_appearances.json", {"bouts": []})
    overrides = load_json(ROOT / "data" / "varsity_overrides.json", {})
    awards = load_json(ROOT / "data" / "awards.json", {"awards": []})
    jot = load_json(ROOT / "data" / "varsity_jotform_overrides.json", {})

    doc = build_varsity_assignments(wd, appearances, overrides, awards, jot or None)
    out = ROOT / "data" / "varsity_assignments.json"
    out.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"Wrote {out} — {doc['counts']['filled']} filled / {doc['counts']['vacant']} vacant")

    opts = build_jotform_options(wd.get("roster") or [])
    opts_path = ROOT / "data" / "jotform_roster_options.json"
    opts_path.write_text(json.dumps(opts, indent=2) + "\n")
    print(f"Wrote {opts_path} — {len(opts['options'])} options")

    # Prestige index for player pages
    season = (wd.get("metadata") or {}).get("season")
    prest = build_prestige_index(wd.get("roster") or [], awards, season)
    (ROOT / "data" / "prestige.json").write_text(json.dumps(prest, indent=2) + "\n")


if __name__ == "__main__":
    main()
