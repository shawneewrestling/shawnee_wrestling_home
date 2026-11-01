#!/usr/bin/env python3
"""Build per-season stats archives + /stats/<YYYY-YY>/ pages.

Sources:
  - history/individual_sheet/{2015..2024}.csv → seasons 2014-15 .. 2023-24
  - history/individual_sheet/Past_Years.csv → earlier seasons (Weight Class = start year)
  - data/history/2024-25_stats.json, 2025-26_stats.json (prefer existing cleaned)
  - wrestling_data.json → current 2026-27 preseason

Also refreshes data/history/index.json and writes
data/build_reports/season_stats_archive_report.json (merge doubts, gaps).
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
HISTORY = ROOT / "data" / "history"
STATS_PAGES = ROOT / "stats"
REPORT = ROOT / "data" / "build_reports" / "season_stats_archive_report.json"
CURRENT = "2026-27"
EST = ZoneInfo("America/New_York")

WIN_KEYS = ["w_fall", "w_tech", "w_maj", "w_dec", "w_sv", "w_tb", "w_ff", "w_inj", "w_dq"]
LOSS_KEYS = ["l_fall", "l_tech", "l_maj", "l_dec", "l_sv", "l_tb", "l_ff", "l_inj", "l_dq"]
STAT_KEYS = WIN_KEYS + LOSS_KEYS

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


def now_est() -> str:
    t = datetime.now(EST)
    s = t.strftime("%Y-%m-%dT%H:%M:%S%z")
    return s[:-2] + ":" + s[-2:]


def season_label(sid: str) -> str:
    m = re.match(r"^(\d{4})-(\d{2})$", sid)
    if not m:
        return f"{sid} Season"
    start = int(m.group(1))
    return f"{start}-{start + 1} Season"


def norm_name(n: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (n or "").lower())


def to_int(v: Any) -> Optional[int]:
    if v is None or v == "":
        return None
    try:
        return int(float(str(v).replace(",", "").replace("%", "").strip()))
    except (TypeError, ValueError):
        return None


def clean_person_name(name: str) -> Optional[str]:
    nm = (name or "").strip()
    if not nm:
        return None
    low = nm.lower()
    if low in ("total", "totals", "team", "name", "#"):
        return None
    if re.fullmatch(r"f+(?:\s+f+)*", low):
        return None
    nm = re.sub(r"(?i)\bHggins\b", "Higgins", nm)
    return nm


def name_from_sheet_row(r: Dict[str, Any]) -> str:
    nm = (r.get("Name") or "").strip()
    if nm and "," in nm:
        last, first = nm.split(",", 1)
        return clean_person_name(f"{first.strip()} {last.strip()}") or ""
    if nm:
        return clean_person_name(nm) or ""
    first = (r.get("First") or "").strip()
    last = (r.get("Last") or "").strip()
    if last.lower() == "hggins":
        last = "Higgins"
    return clean_person_name(f"{first} {last}".strip()) or ""


def parse_sheet_row(r: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    name = name_from_sheet_row(r)
    if not name:
        return None
    wc = (r.get("Weight Class") or "").strip()
    if wc.lower() == "total" or name.lower() in ("total", "totals", "team"):
        return None
    win = to_int(r.get("Win")) or 0
    loss = to_int(r.get("Losses")) or 0
    row: Dict[str, Any] = {
        "name": name,
        "name_key": norm_name(name),
        "win": win,
        "loss": loss,
        "wins": win,
        "losses": loss,
        "weight": wc or None,
        "weights": wc or None,
        "grade": None,
        "team_points": to_int(r.get("Team Points")),
        "advancement": (r.get("Advancement") or "").strip() or None,
    }
    known = False
    for k, col in SHEET_MAP.items():
        v = to_int(r.get(col))
        row[k] = v
        if v is not None:
            known = True
    row["pins"] = row.get("w_fall")
    row["has_breakdown"] = known
    return row


def load_players_index() -> Dict[str, str]:
    doc = json.loads((ROOT / "data" / "players_index.json").read_text()) if (ROOT / "data" / "players_index.json").exists() else {}
    pages: Dict[str, str] = {}
    for w in doc.get("wrestlers") or []:
        href = w.get("player_page") or ""
        if not href:
            continue
        if w.get("name"):
            pages[norm_name(w["name"])] = href
            pages[str(w["name"]).strip().lower()] = href
        if w.get("wrestler_id"):
            pages["id:" + str(w["wrestler_id"])] = href
    return pages


def attach_pages(rows: List[Dict[str, Any]], pages: Dict[str, str]) -> Tuple[List[Dict[str, Any]], List[str]]:
    missing = []
    out = []
    for r in rows:
        key = r.get("name_key") or norm_name(r.get("name") or "")
        href = pages.get(key) or pages.get(str(r.get("name") or "").strip().lower())
        if r.get("wrestler_id"):
            href = pages.get("id:" + str(r["wrestler_id"])) or href
        row = dict(r)
        row["player_page"] = href
        if not href:
            missing.append(row.get("name") or key)
        out.append(row)
    return out, missing


def write_stats_doc(season: str, rows: List[Dict[str, Any]], source: str, has_breakdown: bool) -> Path:
    rows = sorted(rows, key=lambda w: (-(w.get("wins") or w.get("win") or 0), (w.get("losses") or w.get("loss") or 0), w.get("name") or ""))
    doc = {
        "schema_version": 1,
        "season": season,
        "title": season_label(season),
        "generated_at": now_est(),
        "source": source,
        "has_breakdown": has_breakdown,
        "count": len(rows),
        "wrestlers": rows,
    }
    path = HISTORY / f"{season}_stats.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    # Also mirror into data/seasons/<id>/stats.json when season dir exists
    season_dir = ROOT / "data" / "seasons" / season
    if season_dir.exists():
        (season_dir / "stats.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    return path


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title} Stats · Shawnee Renegades Wrestling</title>
  <link rel="stylesheet" href="../../styles.css?v={v}" />
</head>
<body data-stats-season="{season}" data-asset-prefix="../..">
  <header class="site-header">
    <div class="inner">
      <div class="brand">
        <div class="brand-mark"><img src="../../assets/img/shawnee-s.png?v={v}" alt="Shawnee" width="56" height="56" /></div>
        <div>
          <h1>Shawnee Renegades</h1>
          <div class="tag">Wrestling · {title}</div>
        </div>
      </div>
      <nav class="nav">
        <a href="../../index.html">Home</a>
        <a href="../../roster.html">Roster</a>
        <a href="../../full-roster.html">Full Roster</a>
        <a href="../../schedule.html">Schedule &amp; Results</a>
        <a href="../../standings.html">Standings</a>
        <a href="../../stats.html" class="active">Stats</a>
        <a href="../../career-stats.html">Career Stats</a>
        <a href="../../coach-stats.html">Coach Stats</a>
        <a href="../../awards.html">Awards</a>
      </nav>
    </div>
  </header>
  <main>
    <h1 class="page-title">{title} Stats</h1>
    <p class="page-sub">Individual W-L for the {title}.</p>
    <div class="season-toolbar" id="seasonToolbar">
      <label for="seasonSelect">Season</label>
      <select id="seasonSelect" aria-label="Select season"></select>
    </div>
    <div class="table-wrap"><table id="statsTable"><thead><tr><th>Name</th><th>Wt</th><th>Grade</th><th>W</th><th>L</th><th>Win%</th><th>Pins</th></tr></thead><tbody></tbody></table></div>
  </main>
  <footer class="site-footer">
    Shawnee High School <a class="footer-stealth" href="/seeding-af11147f5304/" rel="nofollow">Wrestling</a> · {title}
  </footer>
  <script src="../../app.js?v={v}"></script>
  <script src="../../history.js?v={v}"></script>
</body>
</html>
"""


def write_season_page(season: str, cache_bust: str) -> Path:
    title = season_label(season)
    path = STATS_PAGES / season / "index.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(PAGE_TEMPLATE.format(season=season, title=title, v=cache_bust))
    return path


def build_from_sheets(pages: Dict[str, str], report: Dict[str, Any]) -> List[str]:
    seasons: List[str] = []
    # Past_Years: Weight Class = start year
    past = SHEET / "Past_Years.csv"
    by_season: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    if past.exists():
        with past.open(newline="", encoding="utf-8-sig", errors="replace") as f:
            for r in csv.DictReader(f):
                yr = to_int(r.get("Weight Class"))
                if not yr or yr < 1980 or yr > 2020:
                    continue
                sid = f"{yr}-{str(yr + 1)[2:]}"
                r2 = dict(r)
                r2["Weight Class"] = ""
                row = parse_sheet_row(r2)
                if row:
                    by_season[sid].append(row)
    for end_year in range(2015, 2025):
        path = SHEET / f"{end_year}.csv"
        if not path.exists():
            continue
        sid = f"{end_year - 1}-{str(end_year)[2:]}"
        with path.open(newline="", encoding="utf-8-sig", errors="replace") as f:
            for r in csv.DictReader(f):
                row = parse_sheet_row(r)
                if row:
                    by_season[sid].append(row)

    for sid in sorted(by_season.keys()):
        # Prefer existing cleaned history for 2024-25 / 2025-26
        existing = HISTORY / f"{sid}_stats.json"
        if sid in ("2024-25", "2025-26") and existing.exists():
            seasons.append(sid)
            continue
        rows, missing = attach_pages(by_season[sid], pages)
        has_bd = any(r.get("has_breakdown") for r in rows)
        # normalize has_breakdown field off rows for public? keep for builder; history.js uses doc.has_breakdown
        for r in rows:
            r.pop("has_breakdown", None)
            r.pop("name_key", None)
        write_stats_doc(sid, rows, f"sheet:{sid}", has_bd)
        if missing:
            report.setdefault("no_player_page_by_season", {})[sid] = missing
        seasons.append(sid)
        report.setdefault("built_from_sheets", []).append({"season": sid, "count": len(rows)})
    return seasons


def refresh_existing(pages: Dict[str, str], report: Dict[str, Any], seasons: List[str]) -> None:
    for sid in ("2024-25", "2025-26"):
        path = HISTORY / f"{sid}_stats.json"
        if not path.exists():
            report.setdefault("missing_cleaned", []).append(sid)
            continue
        doc = json.loads(path.read_text())
        rows, missing = attach_pages(doc.get("wrestlers") or [], pages)
        doc["wrestlers"] = rows
        doc["count"] = len(rows)
        doc["title"] = season_label(sid)
        doc["generated_at"] = now_est()
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        season_dir = ROOT / "data" / "seasons" / sid
        if season_dir.exists():
            (season_dir / "stats.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        if missing:
            report.setdefault("no_player_page_by_season", {})[sid] = missing
        if sid not in seasons:
            seasons.append(sid)


def build_current(pages: Dict[str, str], report: Dict[str, Any], seasons: List[str]) -> None:
    wd = json.loads((ROOT / "wrestling_data.json").read_text())
    rows = []
    for w in wd.get("stats") or wd.get("roster") or []:
        wins = int(w.get("wins") or 0)
        losses = int(w.get("losses") or 0)
        rows.append({
            "name": w.get("name"),
            "wrestler_id": w.get("wrestler_id"),
            "weight": w.get("weight"),
            "grade": w.get("grade"),
            "win": wins,
            "loss": losses,
            "wins": wins,
            "losses": losses,
            "pins": w.get("pins"),
            "w_fall": w.get("pins"),
            "w_tech": w.get("tech_falls"),
            "w_maj": w.get("major_decisions"),
            "w_dec": w.get("decisions"),
        })
    rows, missing = attach_pages(rows, pages)
    write_stats_doc(CURRENT, rows, "wrestling_data.json (preseason)", False)
    if missing:
        report.setdefault("no_player_page_by_season", {})[CURRENT] = missing
    if CURRENT not in seasons:
        seasons.append(CURRENT)
    report["current_season"] = {"id": CURRENT, "count": len(rows), "mode": (wd.get("metadata") or {}).get("mode")}


def write_index(seasons: List[str]) -> None:
    # Preserve roster/bouts flags from prior index when present
    prev = {}
    idx_path = HISTORY / "index.json"
    if idx_path.exists():
        old = json.loads(idx_path.read_text())
        for s in old.get("seasons") or []:
            prev[s["id"]] = s
    # Also include roster-only seasons from prev
    ids = sorted(set(seasons) | set(prev.keys()), key=lambda s: (int(s[:4]) if re.match(r"^\d{4}", s) else 0), reverse=True)
    out_seasons = []
    for sid in ids:
        old = prev.get(sid) or {}
        stats_exists = (HISTORY / f"{sid}_stats.json").exists() or sid == CURRENT
        roster_exists = (HISTORY / f"{sid}_roster.json").exists() or sid == CURRENT or bool(old.get("roster"))
        bouts_exists = (HISTORY / f"{sid}_bouts.json").exists()
        entry = {
            "id": sid,
            "label": season_label(sid),
            "roster": bool(roster_exists),
            "stats": bool(stats_exists),
            "bouts": bool(bouts_exists),
            "roster_path": f"data/history/{sid}_roster.json",
            "stats_path": f"data/history/{sid}_stats.json",
            "bouts_path": f"data/history/{sid}_bouts.json",
            "page_path": f"stats/{sid}/",
        }
        out_seasons.append(entry)
    doc = {
        "default": CURRENT,
        "generated_at": now_est(),
        "seasons": out_seasons,
        "bouts_summary": {
            "with_bouts": [s["id"] for s in out_seasons if s["bouts"]],
            "without_bouts": [s["id"] for s in out_seasons if not s["bouts"]],
        },
    }
    idx_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")


def detect_cache_bust() -> str:
    # Prefer query already used on stats.html
    stats = (ROOT / "stats.html").read_text()
    m = re.search(r"styles\.css\?v=([a-zA-Z0-9]+)", stats)
    return m.group(1) if m else "d1e64c8"


def main() -> None:
    report: Dict[str, Any] = {"generated_at": now_est(), "uncertain_merges": [], "built_from_sheets": [], "pages": []}
    pages = load_players_index()
    seasons = build_from_sheets(pages, report)
    refresh_existing(pages, report, seasons)
    build_current(pages, report, seasons)

    # Name collisions within a season (same name_key twice) → uncertain
    for sid in seasons:
        path = HISTORY / f"{sid}_stats.json"
        if not path.exists():
            continue
        doc = json.loads(path.read_text())
        seen = defaultdict(list)
        for w in doc.get("wrestlers") or []:
            seen[norm_name(w.get("name") or "")].append(w.get("name"))
        for k, names in seen.items():
            if len(names) > 1:
                report["uncertain_merges"].append({"season": sid, "name_key": k, "names": names})

    cache = detect_cache_bust()
    for sid in sorted(set(seasons), key=lambda s: int(s[:4]) if re.match(r"^\d{4}", s) else 0):
        if not (HISTORY / f"{sid}_stats.json").exists() and sid != CURRENT:
            continue
        if not (HISTORY / f"{sid}_stats.json").exists():
            continue
        p = write_season_page(sid, cache)
        report["pages"].append(str(p.relative_to(ROOT)))

    write_index(seasons)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    report["seasons_with_stats"] = sorted(
        [s for s in seasons if (HISTORY / f"{s}_stats.json").exists()],
        key=lambda s: int(s[:4]) if re.match(r"^\d{4}", s) else 0,
    )
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(f"Seasons with stats: {', '.join(report['seasons_with_stats'])}")
    print(f"Pages: {len(report['pages'])}")
    print(f"Uncertain merges: {len(report['uncertain_merges'])}")
    print(f"Report: {REPORT}")


if __name__ == "__main__":
    main()
