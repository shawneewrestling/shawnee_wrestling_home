#!/usr/bin/env python3
"""Season Configuration — site-v2 (Trackwrestling is the sole schedule source).

IDs live in data/seasons/<YYYY-YY>/config.json. This module loads them and keeps
module-level CURRENT_* aliases for older scripts (scraper_hybrid, update_site_data).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parent
SEASONS_DIR = ROOT / "data" / "seasons"

CURRENT_SEASON = "2026-27"
GB_ID = "36"

_FALLBACK = {
    "2023-24": {"team_id": "424308143", "season_id": "170451138", "gb_id": "36"},
    "2024-25": {"team_id": "1441922147", "season_id": "842514138", "gb_id": "36"},
    "2025-26": {"team_id": "768996150", "season_id": "1560212138", "gb_id": "36"},
    "2026-27": {"team_id": "1912611150", "season_id": "95515140", "gb_id": "36"},
}


def _read_config(season: str) -> Optional[Dict[str, Any]]:
    path = SEASONS_DIR / season / "config.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _long(season: str) -> str:
    if len(season) == 7 and season[4] == "-":
        a, b = season[:4], season[5:]
        return f"{a}-20{b}" if len(b) == 2 else f"{a}-{b}"
    return season


def load_season(season: str) -> Dict[str, Any]:
    cfg = _read_config(season) or {}
    fb = _FALLBACK.get(season, {})
    season_id = str(cfg.get("season_id") or fb.get("season_id") or "")
    team_id = str(cfg.get("team_id") or fb.get("team_id") or "")
    gb_id = str(cfg.get("gb_id") or fb.get("gb_id") or GB_ID)
    if not season_id:
        raise KeyError(f"No season_id for {season} — run: python tw_pull.py ids --season {season}")
    return {
        "season": season,
        "season_long": cfg.get("season_long") or _long(season),
        "season_id": season_id,
        "team_id": team_id,
        "gb_id": gb_id,
        "gb_name": cfg.get("gb_name") or "New Jersey State Interscholastic Athletic Association",
        "school": cfg.get("school") or "Shawnee",
        "school_search": cfg.get("school_search") or ["Shawnee", "Medford"],
        "path": str(SEASONS_DIR / season / "config.json"),
        "raw": cfg,
    }


def list_seasons() -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    discovered = {p.parent.name for p in SEASONS_DIR.glob("*/config.json")}
    for key in sorted(set(_FALLBACK) | discovered):
        try:
            out[key] = load_season(key)
        except KeyError:
            continue
    return out


def save_season_config(season: str, **fields: Any) -> Path:
    path = SEASONS_DIR / season / "config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    cfg = _read_config(season) or {}
    cfg.update({k: v for k, v in fields.items() if v is not None})
    cfg.setdefault("season", season)
    cfg.setdefault("season_long", _long(season))
    cfg.setdefault("school", "Shawnee")
    cfg.setdefault("school_search", ["Shawnee", "Medford"])
    cfg.setdefault("gb_id", GB_ID)
    path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    return path


_cfg = load_season(CURRENT_SEASON)
TEAM_ID = _cfg["team_id"]
SEASON_ID = _cfg["season_id"]
GB_ID = _cfg["gb_id"]

SEASONS = {
    k: {"team_id": v["team_id"], "season_id": v["season_id"], "gb_id": v["gb_id"]}
    for k, v in list_seasons().items()
}
