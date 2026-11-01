#!/usr/bin/env python3
"""Generate static player pages under players/ + data/players_index.json.

Current wrestlers: roster cards / pages use the current season's weights only.
Graduated wrestlers (no current-season record): player pages list every weight
class wrestled across seasons on record (sheet Weight Class + TW/current season
feeds folded into data/weights_history.json).
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from prestige import build_prestige_index

EST = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parent
PLAYERS_DIR = ROOT / "players"
PLACEHOLDER = "../assets/img/wrestler-silhouette.svg"


def now_est() -> str:
    t = datetime.now(EST)
    s = t.strftime("%Y-%m-%dT%H:%M:%S%z")
    return s[:-2] + ":" + s[-2:]


def slug(name: str, wid: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (name or "wrestler").lower()).strip("-")
    return f"{base}-{wid[-6:]}" if wid else base


def name_key(name: str) -> str:
    s = re.sub(r"[`'\"]", "", (name or "").lower())
    s = re.sub(r"\(.*?\)", " ", s)
    parts = re.findall(r"[a-z]+", s)
    if len(parts) >= 2:
        return parts[0] + parts[-1]
    return "".join(parts)


def esc(s: Any) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def _weights_line(weights: List[str], label: str) -> str:
    if not weights:
        return ""
    joined = " / ".join(esc(w) for w in weights)
    return f'<p class="page-sub weights-line" style="margin-top:.35rem">{esc(label)}: {joined}</p>'


def _season_weights_block(by_season: Dict[str, List[str]]) -> str:
    if not by_season:
        return ""
    rows = []
    for sid in sorted(by_season.keys()):
        wts = by_season[sid] or []
        if not wts:
            continue
        # sid like 2023-24 → 2023-2024 Season
        m = re.match(r"^(\d{4})-(\d{2})$", sid)
        if m:
            y1 = int(m.group(1))
            title = f"{y1}-{y1 + 1} Season"
        else:
            title = sid
        rows.append(
            f"<li><strong>{esc(title)}</strong> · {' / '.join(esc(w) for w in wts)}</li>"
        )
    if not rows:
        return ""
    return (
        '<h2 class="section-title">Weights wrestled</h2>\n'
        '    <ul class="recog-list">' + "".join(rows) + "</ul>"
    )


def player_html(w: Dict[str, Any], ctx: Dict[str, Any]) -> str:
    wid = str(w.get("wrestler_id") or "")
    name = w.get("name") or "Wrestler"
    is_alumni = bool(w.get("alumni") or w.get("status") == "alumni")
    photo = w.get("photo") or PLACEHOLDER
    if photo.startswith("assets"):
        photo = "../" + photo
    elif photo and not photo.startswith(("../", "http", "/")):
        photo = "../" + photo.lstrip("/")
    grade = w.get("grade") or ("Alumni" if is_alumni else "—")
    roster_wt = w.get("weight") or "—"
    assigned = ctx["assigned"].get(wid) if wid else None
    wins = w.get("wins") or 0
    losses = w.get("losses") or 0
    prest = (ctx["prestige"].get(wid) if wid else None) or {}
    if not prest and name:
        prest = ctx["prestige_by_name"].get(name_key(name)) or {}
    recognitions = prest.get("recognitions") or []
    career = {}
    if wid:
        career = ctx["career"].get(wid) or {}
    if not career:
        career = ctx["career"].get((name or "").strip().lower()) or {}
    if not career:
        career = ctx["career"].get(name_key(name)) or {}

    weights_current = [str(x) for x in (w.get("weights_wrestled") or []) if x]
    weights_all = [str(x) for x in (w.get("career_weights") or []) if x]
    by_season = w.get("weights_by_season") or {}

    if recognitions:
        items = []
        for r in recognitions:
            bits = [
                esc(r.get("season")),
                esc(r.get("award_name") or r.get("award_category")),
            ]
            if r.get("placement"):
                bits.append(esc(r.get("placement")))
            if r.get("weight"):
                bits.append(esc(r.get("weight")) + " lb")
            badge = ""
            if r.get("counts_for_prestige") and r.get("prestige_points"):
                badge = f'<span class="prest-badge">{esc(r.get("prestige_points"))} pts</span>'
            items.append(f"<li>{' · '.join(bits)}{badge}</li>")
        recog_section = (
            '<h2 class="section-title">Recognitions</h2>\n'
            '    <ul class="recog-list">' + "".join(items) + "</ul>"
        )
    else:
        recog_section = ""

    if prest.get("has_prestige"):
        adv = esc(prest.get("advancement") or "")
        seas = esc(prest.get("season") or "")
        prest_block = (
            '<div class="stat-card prestige">'
            '<div class="label">NJSIAA prestige</div>'
            f'<div class="value">{esc(prest.get("prestige_points"))}</div>'
            f'<div class="sub">{adv} · {seas}</div>'
            "</div>"
        )
    else:
        prest_block = ""

    career_block = ""
    if career.get("show_career") or (
        is_alumni and career.get("career_wins") is not None and (career.get("seasons_on_record") or 0) > 1
    ):
        cw = career.get("career_wins")
        cl = career.get("career_losses")
        seasons = career.get("seasons_on_record")
        sub = f"{esc(seasons)} seasons" if seasons else "Career"
        career_block = (
            '<div class="stat-card">'
            '<div class="label">Career</div>'
            f'<div class="value">{esc(cw)}-{esc(cl)}</div>'
            f'<div class="sub">{sub}</div>'
            "</div>"
        )

    if is_alumni:
        # No current-season record — career weights across all seasons
        sub_line = f'<p class="page-sub" style="margin-bottom:.75rem">{esc(grade)}</p>'
        season_card = ""
        weights_line = _weights_line(weights_all, "Weights wrestled (all seasons)")
        weights_section = _season_weights_block(by_season)
        back_link = (
            '<p class="page-sub"><a href="../full-roster.html">← Full Roster</a> · '
            '<a href="../awards.html">Awards</a></p>'
        )
    else:
        assigned_disp = assigned or "—"
        sub_line = (
            f'<p class="page-sub" style="margin-bottom:.75rem">'
            f"Grade {esc(grade)} · Assigned {esc(assigned_disp)} · Roster wt {esc(roster_wt)}</p>"
        )
        season_card = (
            '<div class="stat-card">'
            '<div class="label">2025-2026 Season</div>'
            f'<div class="value">{esc(wins)}-{esc(losses)}</div>'
            '<div class="sub">Current season record</div>'
            "</div>"
        )
        # Current wrestlers: current-season weights only
        weights_line = _weights_line(weights_current, "2025-2026 weights")
        weights_section = ""
        back_link = (
            '<p class="page-sub"><a href="../roster.html">← Varsity Roster</a> · '
            '<a href="../full-roster.html">Full Roster</a></p>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{esc(name)} · Shawnee Renegades Wrestling</title>
  <link rel="stylesheet" href="../styles.css?v=4b11595" />
  <link rel="stylesheet" href="../roster.css?v=4b11595" />
</head>
<body>
  <header class="site-header">
    <div class="inner">
      <div class="brand">
        <div class="brand-mark"><img src="../assets/img/shawnee-s.png?v=4b11595" alt="Shawnee" width="56" height="56" /></div>
        <div>
          <h1>Shawnee Renegades</h1>
          <div class="tag">Wrestling · 2025-2026 Season</div>
        </div>
      </div>
      <nav class="nav">
        <a href="../index.html">Home</a>
        <a href="../roster.html">Roster</a>
        <a href="../full-roster.html">Full Roster</a>
        <a href="../schedule.html">Schedule &amp; Results</a>
        <a href="../standings.html">Standings</a>
        <a href="../stats.html">Stats</a>
        <a href="../coach-stats.html">Coach Stats</a>
        <a href="../awards.html">Awards</a>
      </nav>
    </div>
  </header>
  <main class="player-page">
    {back_link}
    <div class="player-hero">
      <img class="player-photo" src="{esc(photo)}" alt="{esc(name)}" width="200" height="240"
           onerror="this.src='{PLACEHOLDER}'" />
      <div class="player-hero-text">
        <h1 class="page-title" style="margin-bottom:.25rem">{esc(name)}</h1>
        {sub_line}
        {weights_line}
        <div class="cards player-stats">
          {season_card}
          {career_block}
          {prest_block}
        </div>
      </div>
    </div>

    {weights_section}
    {recog_section}
  </main>
  <footer class="site-footer">
    Shawnee High School Wrestling · 2025-2026 Season
  </footer>
</body>
</html>
"""


def _load_weights_history() -> Dict[str, Any]:
    path = ROOT / "data" / "weights_history.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _prestige_by_name(awards_doc: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Fallback prestige lookup for alumni without wrestler_id (flat awards list)."""
    from prestige import best_career_prestige

    out: Dict[str, Dict[str, Any]] = {}
    awards = awards_doc.get("awards") or []
    # Group by name_key then reuse prestige helper per unique name
    names: Dict[str, str] = {}
    for a in awards:
        nm = (a.get("wrestler") or a.get("name") or "").strip()
        if not nm:
            continue
        key = name_key(nm)
        names.setdefault(key, nm)
    for key, nm in names.items():
        best = best_career_prestige(nm, awards, current_season="2025-2026")
        out[key] = best
    return out


def build_players(
    wrestling_data: Dict[str, Any],
    awards_doc: Dict[str, Any],
    assignments: Dict[str, Any],
    career: Optional[Dict[str, Any]] = None,
    weights_history: Optional[Dict[str, Any]] = None,
    career_baseline: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    roster = wrestling_data.get("roster") or []
    season = (wrestling_data.get("metadata") or {}).get("season") or "2025-2026"
    prestige_doc = build_prestige_index(roster, awards_doc, season)
    prest = prestige_doc.get("wrestlers") or {}
    prest_by_name = _prestige_by_name(awards_doc)

    assigned = {}
    for slot in assignments.get("slots") or []:
        if slot.get("wrestler_id") and not slot.get("vacant"):
            assigned[str(slot["wrestler_id"])] = str(slot["assigned_weight"])

    career_doc = career or {}
    career_by: Dict[str, Any] = {}
    for row in career_doc.get("wrestlers") or []:
        entry = {
            "show_career": bool(row.get("show_career")),
            "career_wins": row.get("career_wins"),
            "career_losses": row.get("career_losses"),
            "seasons_on_record": row.get("seasons_on_record") or 0,
        }
        wid = str(row.get("wrestler_id") or "")
        if wid:
            career_by[wid] = entry
        if row.get("name"):
            career_by[str(row["name"]).strip().lower()] = entry
            career_by[name_key(row["name"])] = entry

    # Baseline career for alumni (prior through 2024-25)
    # Shape: {name, seasons, win, loss, w_fall}
    baseline = career_baseline or {}
    for row in baseline.get("wrestlers") or []:
        key = name_key(row.get("name") or "")
        if not key:
            continue
        if key in career_by:
            continue
        seasons = int(row.get("seasons") or row.get("seasons_on_record") or 0)
        wins = row.get("win")
        if wins is None:
            wins = row.get("wins")
        if wins is None:
            wins = row.get("career_wins")
        losses = row.get("loss")
        if losses is None:
            losses = row.get("losses")
        if losses is None:
            losses = row.get("career_losses")
        entry = {
            "show_career": seasons > 1,
            "career_wins": wins,
            "career_losses": losses,
            "seasons_on_record": seasons,
        }
        career_by[key] = entry
        if row.get("name"):
            career_by[str(row["name"]).strip().lower()] = entry

    wh = weights_history or {}
    career_wh = wh.get("career_by_key") or {}
    # also index by name_key of nested name
    wh_by_key: Dict[str, Any] = {}
    for k, v in career_wh.items():
        wh_by_key[k] = v
        if v.get("name"):
            wh_by_key[name_key(v["name"])] = v

    if PLAYERS_DIR.exists():
        for p in PLAYERS_DIR.glob("*.html"):
            p.unlink()
    else:
        PLAYERS_DIR.mkdir(parents=True, exist_ok=True)

    index: List[Dict[str, Any]] = []
    ctx = {
        "assigned": assigned,
        "prestige": prest,
        "prestige_by_name": prest_by_name,
        "career": career_by,
    }

    current_keys = set()
    for w in roster:
        wid = str(w.get("wrestler_id") or "")
        if not wid:
            continue
        key = name_key(w.get("name") or "")
        current_keys.add(key)
        # Current-season weights only (from wrestling_data.weights_wrestled)
        weights = [str(x) for x in (w.get("weights_wrestled") or []) if x]
        if not weights and w.get("weight"):
            weights = [str(w["weight"])]
        w_page = dict(w)
        w_page["weights_wrestled"] = weights
        w_page["alumni"] = False
        s = slug(w.get("name") or "", wid)
        (PLAYERS_DIR / f"{s}.html").write_text(player_html(w_page, ctx))
        p = prest.get(wid) or {}
        c = career_by.get(wid) or career_by.get(str(w.get("name") or "").strip().lower()) or career_by.get(key) or {}
        index.append(
            {
                "wrestler_id": wid,
                "name": w.get("name"),
                "grade": w.get("grade"),
                "roster_weight": w.get("weight"),
                "assigned_weight": assigned.get(wid),
                "weights_wrestled": weights,
                "wins": w.get("wins") or 0,
                "losses": w.get("losses") or 0,
                "photo": w.get("photo"),
                "player_page": f"players/{s}.html",
                "prestige_points": p.get("prestige_points") or 0,
                "has_prestige": bool(p.get("has_prestige")),
                "show_career": bool(c.get("show_career")),
                "career_wins": c.get("career_wins"),
                "career_losses": c.get("career_losses"),
                "seasons_on_record": c.get("seasons_on_record") or 0,
                "status": "current",
                "search_text": " ".join(
                    filter(
                        None,
                        [
                            w.get("name"),
                            w.get("first_name"),
                            w.get("last_name"),
                            str(w.get("grade") or ""),
                            str(w.get("weight") or ""),
                            assigned.get(wid) or "",
                            " ".join(weights),
                        ],
                    )
                ).lower(),
            }
        )

    # Graduated wrestlers: baseline names with no current-season roster record
    alumni_count = 0
    for row in baseline.get("wrestlers") or []:
        name = (row.get("name") or "").strip()
        key = name_key(name)
        if not key or key in current_keys:
            continue
        wh_row = wh_by_key.get(key) or {}
        all_wts = list(wh_row.get("all_weights") or [])
        by_season = dict(wh_row.get("by_season") or {})
        # Synthetic id for slug stability (deterministic; do not use hash())
        alum_id = "alum" + hashlib.sha1(key.encode()).hexdigest()[:8]
        s = slug(name, alum_id)
        c = career_by.get(key) or career_by.get(name.lower()) or {}
        seasons = int(c.get("seasons_on_record") or row.get("seasons") or row.get("seasons_on_record") or 0)
        # Prefer showing career when multi-season; always show W-L if we have it
        if seasons > 1:
            c = dict(c)
            c["show_career"] = True
        w_page = {
            "wrestler_id": alum_id,
            "name": name,
            "grade": "Alumni",
            "weight": None,
            "wins": 0,
            "losses": 0,
            "photo": None,
            "alumni": True,
            "status": "alumni",
            "career_weights": all_wts,
            "weights_by_season": by_season,
        }
        (PLAYERS_DIR / f"{s}.html").write_text(player_html(w_page, ctx))
        p = prest_by_name.get(key) or {}
        index.append(
            {
                "wrestler_id": alum_id,
                "name": name,
                "grade": "Alumni",
                "roster_weight": None,
                "assigned_weight": None,
                "weights_wrestled": [],
                "career_weights": all_wts,
                "weights_by_season": by_season,
                "wins": 0,
                "losses": 0,
                "photo": None,
                "player_page": f"players/{s}.html",
                "prestige_points": p.get("prestige_points") or 0,
                "has_prestige": bool(p.get("has_prestige")),
                "show_career": bool(c.get("show_career")) or seasons > 1,
                "career_wins": c.get("career_wins"),
                "career_losses": c.get("career_losses"),
                "seasons_on_record": seasons,
                "status": "alumni",
                "search_text": " ".join(
                    filter(None, [name, "alumni", " ".join(all_wts)])
                ).lower(),
            }
        )
        alumni_count += 1

    index_doc = {
        "schema_version": 2,
        "season": season,
        "updated_at": now_est(),
        "count": len(index),
        "current_count": len(index) - alumni_count,
        "alumni_count": alumni_count,
        "wrestlers": index,
    }
    (ROOT / "data" / "players_index.json").write_text(json.dumps(index_doc, indent=2) + "\n")
    (ROOT / "data" / "prestige.json").write_text(json.dumps(prestige_doc, indent=2) + "\n")
    return index_doc


def main():
    wd = json.loads((ROOT / "data" / "wrestling_data.json").read_text())
    awards = json.loads((ROOT / "data" / "awards.json").read_text())
    assignments_path = ROOT / "data" / "varsity_assignments.json"
    if not assignments_path.exists():
        from varsity_assignments import build_varsity_assignments, load_json

        appearances = load_json(ROOT / "data" / "dual_appearances.json", {"bouts": []})
        overrides = load_json(ROOT / "data" / "varsity_overrides.json", {})
        jot = load_json(ROOT / "data" / "varsity_jotform_overrides.json", {})
        assignments = build_varsity_assignments(wd, appearances, overrides, awards, jot or None)
        assignments_path.write_text(json.dumps(assignments, indent=2) + "\n")
    else:
        assignments = json.loads(assignments_path.read_text())
    career = {}
    for cp in (ROOT / "data" / "career_records.json", ROOT / "data" / "career.json"):
        if cp.exists():
            career = json.loads(cp.read_text())
            break
    baseline = {}
    bp = ROOT / "data" / "career_baseline.json"
    if bp.exists():
        baseline = json.loads(bp.read_text())
    weights_history = _load_weights_history()
    doc = build_players(wd, awards, assignments, career, weights_history, baseline)
    print(
        f"Wrote {doc['count']} player pages "
        f"({doc.get('current_count')} current, {doc.get('alumni_count')} alumni) → {PLAYERS_DIR}"
    )


if __name__ == "__main__":
    main()
