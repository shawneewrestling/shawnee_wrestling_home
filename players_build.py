#!/usr/bin/env python3
"""Generate static player pages under players/ + data/players_index.json."""

from __future__ import annotations

import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
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


def esc(s: Any) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def player_html(w: Dict[str, Any], ctx: Dict[str, Any]) -> str:
    wid = str(w.get("wrestler_id"))
    name = w.get("name") or "Wrestler"
    photo = w.get("photo") or PLACEHOLDER
    if photo.startswith("assets"):
        photo = "../" + photo
    elif photo and not photo.startswith(("../", "http", "/")):
        photo = "../" + photo.lstrip("/")
    grade = w.get("grade") or "—"
    roster_wt = w.get("weight") or "—"
    assigned = ctx["assigned"].get(wid)
    wins = w.get("wins") or 0
    losses = w.get("losses") or 0
    prest = ctx["prestige"].get(wid) or {}
    recognitions = prest.get("recognitions") or []
    prior = ctx["prior_stats"].get(wid)

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
        recog_html = '<ul class="recog-list">' + "".join(items) + "</ul>"
    else:
        recog_html = (
            '<p class="empty-state">No district / region / state placements on file yet.</p>'
        )

    if prior:
        prior_html = (
            '<div class="stat-card"><div class="label">Prior seasons</div>'
            f'<div class="value">{esc(prior.get("wins", 0))}-{esc(prior.get("losses", 0))}</div>'
            f'<div class="sub">{esc(prior.get("note") or "")}</div></div>'
        )
    else:
        prior_html = (
            '<div class="callout">Prior-season stats will appear here after the career '
            "baseline upload (planned for 2026-27 kickoff) and as archived seasons are "
            "backfilled.</div>"
        )

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
        prest_block = (
            '<div class="stat-card">'
            '<div class="label">NJSIAA prestige</div>'
            '<div class="value">0</div>'
            '<div class="sub">No prior placement on file</div>'
            "</div>"
        )

    assigned_disp = assigned or "—"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{esc(name)} · Shawnee Renegades Wrestling</title>
  <link rel="stylesheet" href="../styles.css" />
  <link rel="stylesheet" href="../roster.css" />
</head>
<body>
  <header class="site-header">
    <div class="inner">
      <div class="brand">
        <div class="brand-mark"><img src="../assets/img/shawnee-s.png" alt="Shawnee" width="56" height="56" /></div>
        <div>
          <h1>Shawnee Renegades</h1>
          <div class="tag">Wrestling · 2025-2026 Season</div>
        </div>
      </div>
      <nav class="nav">
        <a href="../index.html">Home</a>
        <a href="../roster.html">Roster</a>
        <a href="../full-roster.html">Full Roster</a>
        <a href="../schedule.html">Schedule / Results</a>
        <a href="../standings.html">Standings</a>
        <a href="../stats.html">Stats</a>
        <a href="../coach-stats.html">Coach Stats</a>
        <a href="../awards.html">Awards</a>
      </nav>
    </div>
  </header>
  <main class="player-page">
    <p class="page-sub"><a href="../roster.html">← Varsity Roster</a> · <a href="../full-roster.html">Full Roster</a></p>
    <div class="player-hero">
      <img class="player-photo" src="{esc(photo)}" alt="{esc(name)}" width="200" height="240"
           onerror="this.src='{PLACEHOLDER}'" />
      <div class="player-hero-text">
        <h1 class="page-title" style="margin-bottom:.25rem">{esc(name)}</h1>
        <p class="page-sub" style="margin-bottom:.75rem">Grade {esc(grade)} · Assigned {esc(assigned_disp)} · Roster wt {esc(roster_wt)}</p>
        <div class="cards player-stats">
          <div class="stat-card">
            <div class="label">2025-2026 Season</div>
            <div class="value">{esc(wins)}-{esc(losses)}</div>
            <div class="sub">Current season record</div>
          </div>
          {prest_block}
        </div>
      </div>
    </div>

    <h2 class="section-title">Recognitions</h2>
    {recog_html}

    <h2 class="section-title">Prior seasons</h2>
    {prior_html}
  </main>
  <footer class="site-footer">
    Shawnee High School Wrestling · 2025-2026 Season
  </footer>
</body>
</html>
"""


def build_players(
    wrestling_data: Dict[str, Any],
    awards_doc: Dict[str, Any],
    assignments: Dict[str, Any],
    career: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    roster = wrestling_data.get("roster") or []
    season = (wrestling_data.get("metadata") or {}).get("season") or "2025-2026"
    prestige_doc = build_prestige_index(roster, awards_doc, season)
    prest = prestige_doc.get("wrestlers") or {}

    assigned = {}
    for slot in assignments.get("slots") or []:
        if slot.get("wrestler_id") and not slot.get("vacant"):
            assigned[str(slot["wrestler_id"])] = str(slot["assigned_weight"])

    prior_stats: Dict[str, Any] = {}
    career = career or {}
    for row in career.get("baseline") or []:
        wid = str(row.get("wrestler_id") or "")
        if wid:
            prior_stats[wid] = {
                "wins": row.get("wins") or row.get("career_wins") or 0,
                "losses": row.get("losses") or row.get("career_losses") or 0,
                "note": "Career baseline",
            }

    if PLAYERS_DIR.exists():
        for p in PLAYERS_DIR.glob("*.html"):
            p.unlink()
    else:
        PLAYERS_DIR.mkdir(parents=True, exist_ok=True)

    index = []
    ctx = {"assigned": assigned, "prestige": prest, "prior_stats": prior_stats}
    for w in roster:
        wid = str(w.get("wrestler_id") or "")
        if not wid:
            continue
        s = slug(w.get("name") or "", wid)
        (PLAYERS_DIR / f"{s}.html").write_text(player_html(w, ctx))
        p = prest.get(wid) or {}
        index.append({
            "wrestler_id": wid,
            "name": w.get("name"),
            "grade": w.get("grade"),
            "roster_weight": w.get("weight"),
            "assigned_weight": assigned.get(wid),
            "wins": w.get("wins") or 0,
            "losses": w.get("losses") or 0,
            "photo": w.get("photo"),
            "player_page": f"players/{s}.html",
            "prestige_points": p.get("prestige_points") or 0,
            "has_prestige": bool(p.get("has_prestige")),
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
                    ],
                )
            ).lower(),
        })

    index_doc = {
        "schema_version": 1,
        "season": season,
        "updated_at": now_est(),
        "count": len(index),
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
    cp = ROOT / "data" / "career.json"
    if cp.exists():
        career = json.loads(cp.read_text())
    doc = build_players(wd, awards, assignments, career)
    print(f"Wrote {doc['count']} player pages → {PLAYERS_DIR}")


if __name__ == "__main__":
    main()
