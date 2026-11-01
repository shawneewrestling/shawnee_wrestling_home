#!/usr/bin/env python3
"""Build data/career_stats.json — one row per wrestler with career totals.

Sources (priority for W-L totals):
  1. Official sheet season CSVs under /workspace/shawnee/history/individual_sheet
     (Past_Years + 2015..2024) plus data/history/2024-25_stats.json and
     2025-26_stats.json / wrestling_data.json
  2. Career_Records_new / Career_Records_old for alumni missing from season tabs
  3. Awards "Career Wins" cards force official career win totals (Dunleavy = 73)
  4. WP career-stats snapshot for grad year when available

Season-by-season rows are stored on each wrestler for player pages; the
Career Stats page itself shows career aggregates only.
"""
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
SHEET = Path("/workspace/shawnee/history/individual_sheet")
HISTORY_EXT = Path("/workspace/shawnee/history")
WP_SNAP = Path("/workspace/shawnee/history/wp_career_stats_snapshot.json")
OUT = ROOT / "data" / "career_stats.json"
EST = ZoneInfo("America/New_York")

WIN_KEYS = [
    "w_fall", "w_tech", "w_maj", "w_dec", "w_sv", "w_tb", "w_ff", "w_inj", "w_dq",
]
LOSS_KEYS = [
    "l_fall", "l_tech", "l_maj", "l_dec", "l_sv", "l_tb", "l_ff", "l_inj", "l_dq",
]
STAT_KEYS = WIN_KEYS + LOSS_KEYS

# Sheet CSV column map
SHEET_MAP = {
    "w_fall": "w- Fall",
    "w_tech": "w- Tech",
    "w_maj": "w- Maj",
    "w_dec": "w- Dec",
    "w_sv": "w-SV",
    "w_tb": "w-TB",
    "w_ff": "w- FF",
    "w_inj": "W- INJ",
    "w_dq": "W-DQ",
    "l_fall": "L- Fall",
    "l_tech": "L-Tech",
    "l_maj": "L-Maj",
    "l_dec": "L- Dec",
    "l_sv": "L-SV",
    "l_tb": "L-TB",
    "l_inj": "L- INJ",
    "l_dq": "L-DQ",
    "l_ff": "L-FF",
}

# Official overrides left as-is until coach confirms (parent chat).
FORCE_CAREER_WINS = {
    "brycedunleavy": 73,
}


def now_est() -> str:
    t = datetime.now(EST)
    s = t.strftime("%Y-%m-%dT%H:%M:%S%z")
    return s[:-2] + ":" + s[-2:]


def norm_name(n: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (n or "").lower())


def to_int(v: Any) -> Optional[int]:
    if v is None or v == "":
        return None
    try:
        return int(float(str(v).replace(",", "").replace("%", "").strip()))
    except (TypeError, ValueError):
        return None


def to_float(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def clean_person_name(name: str) -> Optional[str]:
    nm = (name or "").strip()
    if not nm:
        return None
    low = nm.lower()
    if low in ("total", "totals", "team", "name", "#"):
        return None
    # Known sheet typo
    nm = re.sub(r"(?i)\bHggins\b", "Higgins", nm)
    return nm


def name_from_sheet_row(r: Dict[str, Any]) -> str:
    nm = (r.get("Name") or "").strip()
    if nm and "," in nm:
        last, first = nm.split(",", 1)
        cleaned = clean_person_name(f"{first.strip()} {last.strip()}")
        return cleaned or ""
    if nm:
        return clean_person_name(nm) or ""
    first = (r.get("First") or "").strip()
    last = (r.get("Last") or "").strip()
    if last.lower() == "hggins":
        last = "Higgins"
    return clean_person_name(f"{first} {last}".strip()) or ""


def empty_acc(name: str) -> Dict[str, Any]:
    row = {
        "name": name,
        "name_key": norm_name(name),
        "win": 0,
        "loss": 0,
        "team_points": 0,
        "team_points_known": False,
        "seasons": [],
        "season_rows": [],
        "sources": [],
        "breakdown_known": False,
    }
    for k in STAT_KEYS:
        row[k] = 0
        row[f"_{k}_known"] = False
    return row


def add_stat(acc: Dict[str, Any], key: str, val: Optional[int]) -> None:
    if val is None:
        return
    acc[key] = (acc.get(key) or 0) + int(val)
    acc[f"_{key}_known"] = True
    if key in WIN_KEYS or key in LOSS_KEYS:
        acc["breakdown_known"] = True


def season_sort_key(sid: str) -> Tuple[int, str]:
    m = re.match(r"^(\d{4})", str(sid))
    return (int(m.group(1)) if m else 0, str(sid))


def end_year_of_season(sid: str) -> Optional[int]:
    """'2024-25' -> 2025; '2014-15' -> 2015; Past '2010-11' -> 2011."""
    m = re.match(r"^(\d{4})-(\d{2})$", str(sid))
    if not m:
        return None
    start = int(m.group(1))
    end_yy = int(m.group(2))
    century = (start // 100) * 100
    end = century + end_yy
    if end < start:
        end += 100
    return end


def start_year_of_season(sid: str) -> Optional[int]:
    m = re.match(r"^(\d{4})", str(sid))
    return int(m.group(1)) if m else None


def parse_sheet_row(r: Dict[str, Any], season_id: str) -> Optional[Dict[str, Any]]:
    name = name_from_sheet_row(r)
    if not name:
        return None
    wc = (r.get("Weight Class") or "").strip().lower()
    if wc == "total" or name.lower() in ("total", "totals", "team"):
        return None
    win = to_int(r.get("Win")) or 0
    loss = to_int(r.get("Losses")) or 0
    # Skip empty junk rows
    if win == 0 and loss == 0 and not any(to_int(r.get(SHEET_MAP[k])) for k in STAT_KEYS if SHEET_MAP.get(k)):
        # still keep if name looks real and weight present? skip zero rows
        if not (r.get("Last") or r.get("First") or (r.get("Name") or "").strip()):
            return None
        if win == 0 and loss == 0:
            # include 0-N records (they wrestled)
            pass
    row: Dict[str, Any] = {
        "season": season_id,
        "name": name,
        "win": win,
        "loss": loss,
        "weight": (r.get("Weight Class") or "").strip() or None,
        "team_points": to_float(r.get("Team Points")),
    }
    known = False
    for k, col in SHEET_MAP.items():
        v = to_int(r.get(col))
        row[k] = v
        if v is not None:
            known = True
    row["has_breakdown"] = known
    return row


def ingest_season_row(by: Dict[str, Dict[str, Any]], srow: Dict[str, Any], source: str) -> None:
    name = srow["name"]
    key = norm_name(name)
    if not key:
        return
    acc = by.setdefault(key, empty_acc(name))
    if len(name) > len(acc.get("name") or ""):
        acc["name"] = name
        acc["name_key"] = key

    season = srow["season"]
    # Avoid double-counting the same season from multiple sources
    existing = {r["season"] for r in acc["season_rows"]}
    if season in existing:
        return

    acc["win"] += int(srow.get("win") or 0)
    acc["loss"] += int(srow.get("loss") or 0)
    tp = srow.get("team_points")
    if tp is not None:
        acc["team_points"] += float(tp)
        acc["team_points_known"] = True

    for k in STAT_KEYS:
        add_stat(acc, k, srow.get(k) if srow.get("has_breakdown") else None)

    slim = {
        "season": season,
        "win": int(srow.get("win") or 0),
        "loss": int(srow.get("loss") or 0),
        "weight": srow.get("weight"),
        "team_points": srow.get("team_points"),
        "has_breakdown": bool(srow.get("has_breakdown")),
    }
    for k in STAT_KEYS:
        slim[k] = srow.get(k)
    acc["season_rows"].append(slim)
    acc["seasons"].append(season)
    if source not in acc["sources"]:
        acc["sources"].append(source)


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text())


def load_yearly_sheets(by: Dict[str, Dict[str, Any]]) -> None:
    # 2015.csv = 2014-15 ... 2024.csv = 2023-24
    for end_year in range(2015, 2025):
        path = SHEET / f"{end_year}.csv"
        if not path.exists():
            continue
        season_id = f"{end_year - 1}-{str(end_year)[2:]}"
        with path.open(newline="", encoding="utf-8", errors="replace") as f:
            for r in csv.DictReader(f):
                srow = parse_sheet_row(r, season_id)
                if srow:
                    ingest_season_row(by, srow, f"sheet:{end_year}")


def load_past_years(by: Dict[str, Dict[str, Any]]) -> None:
    path = SHEET / "Past_Years.csv"
    if not path.exists():
        return
    with path.open(newline="", encoding="utf-8", errors="replace") as f:
        for r in csv.DictReader(f):
            # Weight Class holds calendar start year for these rows
            yr = to_int(r.get("Weight Class"))
            if not yr or yr < 1980 or yr > 2020:
                continue
            season_id = f"{yr}-{str(yr + 1)[2:]}"
            # Clear weight-class-as-year so parse doesn't treat it as weight
            r2 = dict(r)
            r2["Weight Class"] = ""
            srow = parse_sheet_row(r2, season_id)
            if srow:
                srow["weight"] = None
                ingest_season_row(by, srow, "sheet:Past_Years")


def load_history_stats(by: Dict[str, Dict[str, Any]], season_id: str, path: Path, source: str) -> None:
    doc = load_json(path, {})
    for w in doc.get("wrestlers") or []:
        name = (w.get("name") or "").strip()
        if not name:
            continue
        has_bd = any(w.get(k) is not None for k in STAT_KEYS)
        # history files use has_breakdown flag; 2025-26 currently false
        if "has_breakdown" in doc:
            has_bd = bool(doc.get("has_breakdown")) and has_bd
        srow = {
            "season": season_id,
            "name": name,
            "win": int(w.get("win") if w.get("win") is not None else (w.get("wins") or 0)),
            "loss": int(w.get("loss") if w.get("loss") is not None else (w.get("losses") or 0)),
            "weight": w.get("weight") or (str(w.get("weights") or "").split("/")[0] or None),
            "team_points": to_float(w.get("team_points")),
            "has_breakdown": has_bd,
        }
        for k in STAT_KEYS:
            srow[k] = to_int(w.get(k)) if has_bd else None
        # If flag says no breakdown, still keep pins as w_fall when present
        if not has_bd and w.get("w_fall") is not None:
            srow["w_fall"] = to_int(w.get("w_fall"))
            srow["has_breakdown"] = False
        elif not has_bd and w.get("pins") is not None:
            srow["w_fall"] = to_int(w.get("pins"))
        ingest_season_row(by, srow, source)


def load_career_records_csv(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    with path.open(newline="", encoding="utf-8", errors="replace") as f:
        for r in csv.DictReader(f):
            # old file uses Last/First; new uses Name
            name = name_from_sheet_row(r)
            if not name:
                first = (r.get("First") or "").strip()
                last = (r.get("Last") or "").strip()
                # fix known typo Hggins -> Higgins
                if last.lower() == "hggins":
                    last = "Higgins"
                name = f"{first} {last}".strip()
            if not name:
                continue
            key = norm_name(name)
            row = {
                "name": name,
                "win": to_int(r.get("Win")),
                "loss": to_int(r.get("Losses")),
                "seasons_count": to_int(r.get("Weight Class") or r.get("Starter")),
                "team_points": to_float(r.get("Team Points")),
                "win_pct": to_float(r.get("Win%") or r.get("win %")),
                "fall_pct": to_float(r.get("Fall%") or r.get("Fall %")),
                "bonus_pct": to_float(r.get("Bonus Pt %") or r.get("Bonus pt %")),
            }
            # Map both new and old column names
            colmap = dict(SHEET_MAP)
            # old file variants
            colmap.update({
                "w_fall": colmap["w_fall"] if r.get(colmap["w_fall"]) not in (None, "") else "w- Fall",
            })
            for k, col in SHEET_MAP.items():
                # try exact, then stripped variants present in old
                v = to_int(r.get(col))
                if v is None and k == "w_tech":
                    v = to_int(r.get("w- Tech") or r.get(""))
                row[k] = v
            # old file blank header sometimes holds w-Tech — already handled via DictReader key ''
            if row.get("w_tech") is None:
                row["w_tech"] = to_int(r.get(""))
            out[key] = row
    return out


def merge_career_record(acc: Dict[str, Any], crec: Dict[str, Any], source: str) -> None:
    """Fill gaps from a career-records row without double-counting season sheets."""
    if not acc["season_rows"]:
        # No season detail — use career record as the totals
        if crec.get("win") is not None:
            acc["win"] = int(crec["win"])
        if crec.get("loss") is not None:
            acc["loss"] = int(crec["loss"])
        if crec.get("team_points") is not None:
            acc["team_points"] = float(crec["team_points"])
            acc["team_points_known"] = True
        for k in STAT_KEYS:
            if crec.get(k) is not None:
                acc[k] = int(crec[k])
                acc[f"_{k}_known"] = True
                acc["breakdown_known"] = True
        if crec.get("seasons_count"):
            acc["seasons_count_hint"] = int(crec["seasons_count"])
        if source not in acc["sources"]:
            acc["sources"].append(source)
        return

    # Have season rows — only fill missing breakdown / team points / pct hints
    if not acc["team_points_known"] and crec.get("team_points") is not None:
        acc["team_points"] = float(crec["team_points"])
        acc["team_points_known"] = True
    if not acc["breakdown_known"]:
        for k in STAT_KEYS:
            if crec.get(k) is not None:
                acc[k] = int(crec[k])
                acc[f"_{k}_known"] = True
                acc["breakdown_known"] = True
    else:
        # Fill individual missing type cols
        for k in STAT_KEYS:
            if not acc.get(f"_{k}_known") and crec.get(k) is not None:
                acc[k] = int(crec[k])
                acc[f"_{k}_known"] = True
    for pct_key in ("win_pct", "fall_pct", "bonus_pct"):
        if crec.get(pct_key) is not None:
            acc[f"sheet_{pct_key}"] = crec[pct_key]
    if source not in acc["sources"]:
        acc["sources"].append(source)


def apply_awards_and_grad(
    by: Dict[str, Dict[str, Any]],
    awards: Dict[str, Any],
    wp_by: Dict[str, Dict[str, Any]],
    players_index: Dict[str, Any],
) -> None:
    # Career Wins cards
    win_awards = {
        norm_name(a.get("wrestler") or ""): a
        for a in (awards.get("awards") or [])
        if (a.get("award_name") or "") == "Career Wins" and a.get("wrestler")
    }
    pins_awards = {
        norm_name(a.get("wrestler") or ""): a
        for a in (awards.get("awards") or [])
        if (a.get("award_name") or "") == "Career Pins" and a.get("wrestler")
    }

    for key, a in win_awards.items():
        name = a["wrestler"]
        acc = by.setdefault(key, empty_acc(name))
        acc["name"] = name
        val = to_int(a.get("value"))
        if val is not None:
            acc["win"] = val
            acc["wins_from_award"] = True
        years = a.get("years_active") or ""
        acc["years_active"] = years
        m = re.match(r"^(\d{4})\s*[-–]\s*(\d{4})$", str(years).strip())
        if m:
            acc["award_start_year"] = int(m.group(1))
            acc["award_end_year"] = int(m.group(2))
            if "awards:Career Wins" not in acc["sources"]:
                acc["sources"].append("awards:Career Wins")

    for key, a in pins_awards.items():
        acc = by.setdefault(key, empty_acc(a["wrestler"]))
        val = to_int(a.get("value"))
        if val is not None and (not acc.get("_w_fall_known") or (acc.get("w_fall") or 0) == 0):
            # Don't overwrite a known non-zero fall total with award if we already summed
            if not acc.get("_w_fall_known") or acc.get("w_fall") == 0:
                acc["w_fall"] = val
                acc["_w_fall_known"] = True
                if "awards:Career Pins" not in acc["sources"]:
                    acc["sources"].append("awards:Career Pins")

    # Explicit forced wins (Dunleavy)
    for key, wins in FORCE_CAREER_WINS.items():
        if key in by:
            by[key]["win"] = wins
            by[key]["wins_from_award"] = True

    # WP snapshot: grad year + fill award-only rows that have no losses
    for key, wp in wp_by.items():
        acc = by.setdefault(key, empty_acc(wp["name"]))
        gy = to_int(wp.get("grad_year"))
        if gy:
            acc["grad_year"] = gy
            acc["grad_year_source"] = "wp_career_stats"
        # If we have no season rows and loss is 0/missing, take WP loss only when > 0
        # or when we have no other loss info
        if not acc["season_rows"]:
            wpl = to_int(wp.get("loss"))
            wpw = to_int(wp.get("win"))
            if acc.get("win") in (0, None) and wpw:
                acc["win"] = wpw
            if acc.get("loss") in (0, None) and wpl:
                acc["loss"] = wpl
            # Win-type cols from WP when we have no breakdown
            if not acc.get("breakdown_known"):
                mapping = [
                    ("w_fall", "w_fall"), ("w_tech", "w_tech"), ("w_maj", "w_maj"),
                    ("w_dec", "w_dec"), ("w_sv", "w_sv"), ("w_tb", "w_tb"),
                    ("w_ff", "w_ff"), ("w_inj", "w_inj"), ("w_dq", "w_dq"),
                ]
                for dst, src in mapping:
                    v = to_int(wp.get(src))
                    if v is not None:
                        acc[dst] = v
                        acc[f"_{dst}_known"] = True
                        if v:
                            acc["breakdown_known"] = True
            if "wp_career_stats" not in acc["sources"]:
                acc["sources"].append("wp_career_stats")

    # Player page links + current grade for grad estimation
    grade_by = {}
    page_by = {}
    for w in (players_index.get("wrestlers") or []):
        key = norm_name(w.get("name") or "")
        if not key:
            continue
        if w.get("player_page"):
            page_by[key] = w["player_page"]
        if w.get("grade"):
            grade_by[key] = w["grade"]
        # also id-based
    for key, acc in by.items():
        acc["player_page"] = page_by.get(key)
        acc["current_grade"] = grade_by.get(key)


def finalize(acc: Dict[str, Any]) -> Dict[str, Any]:
    seasons = sorted(set(acc.get("seasons") or []), key=season_sort_key)
    acc["seasons"] = seasons
    acc["season_rows"] = sorted(acc.get("season_rows") or [], key=lambda r: season_sort_key(r["season"]))
    acc["seasons_count"] = len(seasons) or to_int(acc.get("seasons_count_hint")) or 0

    # seasons label / years
    if acc.get("years_active"):
        acc["seasons_label"] = str(acc["years_active"]).replace("–", "-")
    elif seasons:
        y0 = start_year_of_season(seasons[0])
        y1 = end_year_of_season(seasons[-1])
        if y0 and y1:
            acc["seasons_label"] = f"{y0}-{y1}"
        else:
            acc["seasons_label"] = ", ".join(seasons)
    elif acc.get("award_start_year") and acc.get("award_end_year"):
        acc["seasons_label"] = f"{acc['award_start_year']}-{acc['award_end_year']}"
    else:
        acc["seasons_label"] = None

    # Grad year
    if not acc.get("grad_year"):
        if acc.get("award_end_year"):
            acc["grad_year"] = acc["award_end_year"]
            acc["grad_year_source"] = "awards_years_active"
        else:
            last = seasons[-1] if seasons else None
            end = end_year_of_season(last) if last else None
            grade = (acc.get("current_grade") or "").strip()
            # Alumni / Sr at end of final season
            if end and (
                grade.lower() in ("sr.", "sr", "senior", "alumni")
                or (acc.get("seasons_count") or 0) >= 4
            ):
                # Current seniors in 2025-26 graduate 2026
                if last == "2025-26" and grade.lower() in ("sr.", "sr", "senior"):
                    acc["grad_year"] = 2026
                    acc["grad_year_source"] = "tw_senior"
                elif last != "2025-26" or grade.lower() == "alumni":
                    acc["grad_year"] = end
                    acc["grad_year_source"] = "estimated_final_season"
                else:
                    acc["grad_year"] = None
            else:
                acc["grad_year"] = None

    win = int(acc.get("win") or 0)
    loss = int(acc.get("loss") or 0)
    total = win + loss
    acc["win"] = win
    acc["loss"] = loss

    if total > 0:
        acc["win_pct"] = round(100.0 * win / total, 2)
    else:
        acc["win_pct"] = None

    # Prefer computed pcts; fall back to sheet career pcts
    w_fall = acc["w_fall"] if acc.get("_w_fall_known") else None
    if w_fall is not None and total > 0:
        acc["fall_pct"] = round(100.0 * int(w_fall) / total, 2)
    else:
        acc["fall_pct"] = acc.get("sheet_fall_pct")

    bonus_n = None
    if acc.get("breakdown_known") and total > 0:
        parts = []
        for k in ("w_fall", "w_tech", "w_maj"):
            if acc.get(f"_{k}_known"):
                parts.append(int(acc.get(k) or 0))
        if parts:
            bonus_n = sum(parts)
            acc["bonus_pct"] = round(100.0 * bonus_n / total, 2)
        else:
            acc["bonus_pct"] = acc.get("sheet_bonus_pct")
    else:
        acc["bonus_pct"] = acc.get("sheet_bonus_pct")

    # Null out unknown type fields for the public JSON
    public_stats = {}
    for k in STAT_KEYS:
        if acc.get(f"_{k}_known"):
            public_stats[k] = int(acc.get(k) or 0)
        else:
            public_stats[k] = None

    # pins convenience
    pins = public_stats.get("w_fall")

    tp_out = None
    if acc.get("team_points_known"):
        tp_val = float(acc.get("team_points") or 0)
        # Past_Years often stores literal 0 for missing TP — treat 0 as unknown
        tp_out = round(tp_val, 1) if tp_val else None

    out = {
        "name": acc["name"],
        "name_key": acc["name_key"],
        "player_page": acc.get("player_page"),
        "grad_year": acc.get("grad_year"),
        "seasons": seasons,
        "seasons_label": acc.get("seasons_label"),
        "seasons_count": acc.get("seasons_count") or 0,
        "win": win,
        "loss": loss if (loss > 0 or acc.get("season_rows") or acc.get("breakdown_known")) else (
            loss if loss else (0 if acc.get("season_rows") else None)
        ),
        "win_pct": acc.get("win_pct"),
        "team_points": tp_out,
        "fall_pct": acc.get("fall_pct"),
        "bonus_pct": acc.get("bonus_pct"),
        "pins": pins,
        "has_breakdown": bool(acc.get("breakdown_known")),
        "season_rows": acc.get("season_rows") or [],
    }
    out.update(public_stats)

    # If loss is None (award-only with WP loss 0), keep null
    if not acc.get("season_rows") and not acc.get("breakdown_known") and (acc.get("loss") in (0, None)):
        # Distinguish known 0-loss unicorns vs unknown: WP often stored 0 for unknown
        if "wp_career_stats" in (acc.get("sources") or []) and (acc.get("loss") or 0) == 0:
            out["loss"] = None
            out["win_pct"] = None

    return out


def build() -> Dict[str, Any]:
    by: Dict[str, Dict[str, Any]] = {}

    load_yearly_sheets(by)
    load_past_years(by)

    # Prefer cleaned history season_stats for 2024-25 (has breakdown)
    load_history_stats(
        by, "2024-25", ROOT / "data" / "history" / "2024-25_stats.json", "history:2024-25"
    )
    load_history_stats(
        by, "2025-26", ROOT / "data" / "history" / "2025-26_stats.json", "history:2025-26"
    )

    # Career record CSVs fill alumni gaps / team points
    cr_new = load_career_records_csv(SHEET / "Career_Records_new.csv")
    cr_old = load_career_records_csv(SHEET / "Career_Records_old.csv")
    for key, crec in cr_new.items():
        acc = by.setdefault(key, empty_acc(crec["name"]))
        merge_career_record(acc, crec, "Career_Records_new")
    for key, crec in cr_old.items():
        acc = by.setdefault(key, empty_acc(crec["name"]))
        merge_career_record(acc, crec, "Career_Records_old")

    awards = load_json(ROOT / "data" / "awards.json", {})
    players_index = load_json(ROOT / "data" / "players_index.json", {})
    wp_list = load_json(WP_SNAP, []) or []
    wp_by = {norm_name(r["name"]): r for r in wp_list if r.get("name")}

    apply_awards_and_grad(by, awards, wp_by, players_index)

    # Merge typo key into canonical if both present
    if "matthggins" in by and "matthiggins" in by:
        del by["matthggins"]
    elif "matthggins" in by:
        acc = by.pop("matthggins")
        acc["name"] = "Matt Higgins"
        acc["name_key"] = "matthiggins"
        by["matthiggins"] = acc

    wrestlers = [finalize(acc) for acc in by.values()]
    # Drop fully empty / aggregate junk names
    junk = {"total", "totals", "team", "matthggins"}
    wrestlers = [
        w for w in wrestlers
        if w.get("name")
        and (w.get("name_key") or "") not in junk
        and (w.get("win") or w.get("loss") or w.get("seasons"))
    ]
    wrestlers.sort(key=lambda w: (-(w.get("win") or 0), (w.get("loss") or 9999), w.get("name") or ""))

    # Gaps report (embedded for builders; not shown on page)
    gaps = []
    dun = next((w for w in wrestlers if w["name_key"] == "brycedunleavy"), None)
    if dun and dun.get("win") != 73:
        gaps.append(f"Dunleavy win is {dun.get('win')}, expected 73")
    no_page = sum(1 for w in wrestlers if not w.get("player_page"))
    no_grad = sum(1 for w in wrestlers if not w.get("grad_year"))
    no_bd = sum(1 for w in wrestlers if not w.get("has_breakdown"))
    award_only = [
        w["name"] for w in wrestlers
        if not w.get("season_rows") and (w.get("loss") is None)
    ]

    doc = {
        "schema_version": 1,
        "updated_at": now_est(),
        "title": "Career Stats",
        "count": len(wrestlers),
        "wrestlers": wrestlers,
        "build_meta": {
            "no_player_page": no_page,
            "no_grad_year": no_grad,
            "no_breakdown": no_bd,
            "award_wins_without_losses": award_only,
            "gaps": gaps,
            "dunleavy_wins": dun.get("win") if dun else None,
        },
    }
    return doc


def main() -> None:
    doc = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    meta = doc["build_meta"]
    print(f"Wrote {OUT} — {doc['count']} wrestlers")
    print(f"  Dunleavy wins: {meta.get('dunleavy_wins')}")
    print(f"  no player page: {meta['no_player_page']}")
    print(f"  no grad year: {meta['no_grad_year']}")
    print(f"  no breakdown: {meta['no_breakdown']}")
    print(f"  award-only (no losses): {len(meta['award_wins_without_losses'])}")
    if meta["award_wins_without_losses"]:
        print("   ", ", ".join(meta["award_wins_without_losses"][:20]))
    if meta["gaps"]:
        print("  GAPS:", meta["gaps"])


if __name__ == "__main__":
    main()
