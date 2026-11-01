#!/usr/bin/env python3
"""
Career stats model for Shawnee Wrestling.

baseline: Jeff-supplied prior-years rows (empty until 2026-27 upload)
events: append-only seasonal contributions keyed by source_event_id
rollup: career_X = baseline_X + sum(events for wrestler)

Dedupe: UNIQUE(wrestler_id, source_event_id). Re-running the same season
aggregate replaces that season's event rather than double-counting.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

EST = ZoneInfo("America/New_York")


def now_est() -> str:
    t = datetime.now(EST)
    s = t.strftime("%Y-%m-%dT%H:%M:%S%z")
    return s[:-2] + ":" + s[-2:]


EMPTY = {
    "schema_version": 1,
    "baseline": [],
    "baseline_note": (
        "Empty by design. At the start of 2026-27, Jeff uploads prior-years "
        "career data; then each season appends events with source_event_id dedupe."
    ),
    "events": [],
    "rollups": [],
}


def load_career(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return json.loads(json.dumps(EMPTY))
    return json.loads(path.read_text())


def save_career(path: Path, doc: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n")


def apply_season_aggregate(doc: Dict[str, Any], season_data: Dict[str, Any]) -> Dict[str, Any]:
    meta = season_data.get("metadata") or {}
    season = meta.get("season") or "unknown"
    season_id = str(meta.get("season_id") or "unknown")
    source_event_id = f"season:{season_id}:aggregate"

    wrestlers = []
    for w in season_data.get("roster") or season_data.get("stats") or []:
        wrestlers.append({
            "wrestler_id": w.get("wrestler_id"),
            "name": w.get("name"),
            "wins": w.get("wins") or 0,
            "losses": w.get("losses") or 0,
            "pins": w.get("pins"),
        })

    event = {
        "source_event_id": source_event_id,
        "season": season,
        "season_id": season_id,
        "kind": "season_aggregate",
        "applied_at": now_est(),
        "wrestlers": wrestlers,
    }

    events = [e for e in (doc.get("events") or []) if e.get("source_event_id") != source_event_id]
    events.append(event)
    doc["events"] = events
    doc["rollups"] = compute_rollups(doc.get("baseline") or [], events)
    doc["updated_at"] = now_est()
    return doc


def compute_rollups(baseline: List[Dict], events: List[Dict]) -> List[Dict]:
    """Sum baseline + all events per wrestler_id (or name fallback)."""
    by_id: Dict[str, Dict[str, Any]] = {}

    def key_for(row: Dict) -> str:
        return str(row.get("wrestler_id") or row.get("name") or "")

    for b in baseline:
        k = key_for(b)
        if not k:
            continue
        by_id[k] = {
            "wrestler_id": b.get("wrestler_id"),
            "name": b.get("name"),
            "career_wins": int(b.get("career_wins") or b.get("wins") or 0),
            "career_losses": int(b.get("career_losses") or b.get("losses") or 0),
            "career_pins": b.get("career_pins") if b.get("career_pins") is not None else b.get("pins"),
            "sources": ["baseline"],
        }

    for ev in events:
        for w in ev.get("wrestlers") or []:
            k = key_for(w)
            if not k:
                continue
            row = by_id.setdefault(k, {
                "wrestler_id": w.get("wrestler_id"),
                "name": w.get("name"),
                "career_wins": 0,
                "career_losses": 0,
                "career_pins": None,
                "sources": [],
            })
            row["career_wins"] += int(w.get("wins") or 0)
            row["career_losses"] += int(w.get("losses") or 0)
            if w.get("pins") is not None:
                row["career_pins"] = (row["career_pins"] or 0) + int(w["pins"])
            row["name"] = row.get("name") or w.get("name")
            sid = ev.get("source_event_id")
            if sid and sid not in row["sources"]:
                row["sources"].append(sid)

    return sorted(by_id.values(), key=lambda r: (-(r["career_wins"]), r.get("name") or ""))


def ingest_baseline(doc: Dict[str, Any], rows: List[Dict]) -> Dict[str, Any]:
    """Replace baseline with Jeff upload; recompute rollups."""
    doc["baseline"] = rows
    doc["baseline_note"] = f"Loaded {len(rows)} baseline rows at {now_est()}"
    doc["rollups"] = compute_rollups(rows, doc.get("events") or [])
    doc["updated_at"] = now_est()
    return doc
