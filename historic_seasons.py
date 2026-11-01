#!/usr/bin/env python3
"""Build static Schedule / Results / Standings archives from NJ.com (2010-11 .. 2024-25)
plus export the current 2025-26 season into data/seasons/.

Never writes Trackwrestling/NJ.com numeric IDs into page-facing JSON fields that
the front end displays. Coaching history is validated, never modified.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from school_aliases import lookup_logo, load_logos_map

ROOT = Path(__file__).resolve().parent
SEASONS_DIR = ROOT / "data" / "seasons"
COACH_PATH = ROOT / "data" / "coaching_history.json"
STANDINGS_CURRENT = ROOT / "data" / "standings.json"
WRESTLING_CURRENT = ROOT / "wrestling_data.json"
EST = ZoneInfo("America/New_York")
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# short id -> (label start, label end) for 'YYYY-YYYY Season'
HISTORIC = [f"{y}-{str(y+1)[2:]}" for y in range(2010, 2025)]  # 2010-11 .. 2024-25
CURRENT = "2025-26"


def _now() -> str:
    t = datetime.now(EST)
    s = t.strftime("%Y-%m-%dT%H:%M:%S%z")
    return s[:-2] + ":" + s[-2:]


def short_to_long(short: str) -> str:
    a, b = short.split("-")
    start = int(a)
    end = start + 1
    return f"{start}-{end}"


def short_to_label(short: str) -> str:
    return f"{short_to_long(short)} Season"


def season_start_year(short: str) -> int:
    return int(short.split("-")[0])


def _curl(url: str) -> Tuple[int, str]:
    cmd = ["curl", "-sL", "-A", UA, "-w", "\n__HTTP__:%{http_code}", url]
    try:
        out = subprocess.check_output(cmd, text=True, errors="replace", timeout=60)
    except Exception as e:
        return 0, str(e)
    if "__HTTP__:" in out:
        body, _, code = out.rpartition("__HTTP__:")
        try:
            return int(code.strip()), body
        except ValueError:
            return 0, body
    return 0, out


def parse_pct(rec: str) -> Optional[float]:
    if not rec:
        return None
    parts = [int(x) for x in rec.split("-")]
    w = parts[0] if parts else 0
    l = parts[1] if len(parts) > 1 else 0
    t = parts[2] if len(parts) > 2 else 0
    n = w + l + t
    if not n:
        return None
    return round((w + 0.5 * t) / n, 3)


def format_pct(p: Optional[float]) -> Optional[str]:
    if p is None:
        return None
    return f"{p:.3f}"


def parse_nj_date(date_text: str, start_year: int) -> Tuple[str, str]:
    """'Sat, 12/14' -> (date_iso, display)."""
    m = re.search(r"(\d{1,2})/(\d{1,2})", date_text or "")
    if not m:
        return "", date_text or ""
    month, day = int(m.group(1)), int(m.group(2))
    year = start_year if month >= 8 else start_year + 1
    iso = f"{year:04d}-{month:02d}-{day:02d}"
    display = datetime(year, month, day).strftime("%B %-d, %Y")
    return iso, display


def parse_result_cell(raw: str) -> Tuple[Optional[str], Optional[int], Optional[int], Optional[str]]:
    """Return (result, shawnee_score, opp_score, score_display)."""
    raw = (raw or "").strip()
    if not raw:
        return None, None, None, None
    m = re.match(r"^([WLT])\s+(\d+)\s*-\s*(\d+)\s*$", raw, re.I)
    if m:
        res = m.group(1).upper()
        a, b = int(m.group(2)), int(m.group(3))
        # NJ.com lists Shawnee's score first when W/L prefix is present
        return res, a, b, f"{a}-{b}"
    m = re.match(r"^(\d+)\s*-\s*(\d+)$", raw)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        return None, a, b, f"{a}-{b}"
    return None, None, None, None


def is_tournament_event(opponent: str, result: Optional[str], score_display: Optional[str]) -> bool:
    if result or score_display:
        return False
    name = (opponent or "").lower()
    keys = (
        "tournament", "invitational", "districts", "regions", "state championship",
        "njsiaa", "pride", "escape", "classic", "duals",
    )
    if any(k in name for k in keys):
        return True
    # No score and no W/L — treat as event/tournament listing
    return True


def attach_logo(name: str, logos: Dict[str, Any]) -> Dict[str, Any]:
    info = lookup_logo(name, logos, make_badge=False)
    return {
        "opponent": info.get("opponent") or name,
        "opponent_slug": info.get("opponent_slug"),
        "opponent_logo": info.get("opponent_logo"),
        "opponent_logo_local": info.get("opponent_logo_local"),
        "logo_source": info.get("logo_source"),
    }


def fetch_schedule(short: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    long = short_to_long(short)
    url = f"https://highschoolsports.nj.com/school/medford-shawnee/wrestling/season/{long}/"
    code, html = _curl(url)
    meta = {"url": url, "http": code, "bytes": len(html or "")}
    if code != 200 or not html:
        return [], meta
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.table")
    if not table:
        meta["error"] = "no schedule table"
        return [], meta
    logos = load_logos_map()
    start = season_start_year(short)
    events: List[Dict[str, Any]] = []
    for tr in table.select("tbody tr"):
        tds = tr.select("td")
        if len(tds) < 3:
            continue
        date_raw = tds[0].get_text(" ", strip=True)
        opp_raw = tds[1].get_text(" ", strip=True)
        result_raw = tds[2].get_text(" ", strip=True)
        ha = "home"
        opp = opp_raw
        if opp_raw.startswith("@"):
            ha = "away"
            opp = opp_raw[1:].strip()
        elif opp_raw.lower().startswith("vs"):
            ha = "home"
            opp = re.sub(r"^vs\.?\s*", "", opp_raw, flags=re.I).strip()
        date_iso, date_display = parse_nj_date(date_raw, start)
        result, sh, opp_sc, score_display = parse_result_cell(result_raw)
        tourney = is_tournament_event(opp, result, score_display)
        logo = attach_logo(opp, logos)
        # Prefer cleaned display name from alias table for duals; keep raw for events
        display_name = logo["opponent"] if not tourney else opp
        event = {
            "date": date_display or date_raw,
            "date_iso": date_iso,
            "date_raw": date_raw,
            "home_away": "event" if tourney else ha,
            "opponent": display_name,
            "event_name": display_name if tourney else None,
            "event_kind": "T" if tourney else "D",
            "result": result,
            "score_shawnee": sh,
            "score_opp": opp_sc,
            "score_display": score_display,
            "status": "final" if (result or tourney) else None,
            "completed": bool(result or tourney),
            "opponent_slug": logo.get("opponent_slug"),
            "opponent_logo": logo.get("opponent_logo"),
            "opponent_logo_local": logo.get("opponent_logo_local"),
            "logo_source": logo.get("logo_source"),
            "source": "NJ.com",
        }
        if tourney:
            event["results_unavailable"] = True
            event["result_note"] = "Tournament / multi-team event"
        events.append(event)
    meta["events"] = len(events)
    meta["duals"] = sum(1 for e in events if e.get("event_kind") == "D" and e.get("result"))
    return events, meta


def summarize_duals(duals: List[Dict[str, Any]]) -> Dict[str, Any]:
    w = l = t = 0
    hw = hl = ht = 0
    aw = al = at = 0
    pf = pa = 0
    for d in duals:
        res = d.get("result")
        if res == "W":
            w += 1
        elif res == "L":
            l += 1
        elif res == "T":
            t += 1
        sh = d.get("score_shawnee")
        opp = d.get("score_opp")
        if isinstance(sh, int) and isinstance(opp, int):
            pf += sh
            pa += opp
        ha = d.get("home_away")
        if ha == "home":
            if res == "W":
                hw += 1
            elif res == "L":
                hl += 1
            elif res == "T":
                ht += 1
        elif ha == "away":
            if res == "W":
                aw += 1
            elif res == "L":
                al += 1
            elif res == "T":
                at += 1
    def rec(ww, ll, tt=0):
        return f"{ww}-{ll}-{tt}" if tt else f"{ww}-{ll}"
    overall = rec(w, l, t)
    return {
        "overall": {"wins": w, "losses": l, "ties": t, "record": rec(w, l, t), "count": w + l + t},
        "home": {"wins": hw, "losses": hl, "ties": ht, "record": rec(hw, hl, ht), "count": hw + hl + ht},
        "away": {"wins": aw, "losses": al, "ties": at, "record": rec(aw, al, at), "count": aw + al + at},
        "pf": pf,
        "pa": pa,
        "overall_pct": parse_pct(overall),
    }


def parse_standings_html(html: str) -> List[Dict[str, Any]]:
    """Parse first (division) standings table: American then National blocks."""
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.select("table")
    if not tables:
        return []
    # Table 0 on NJ.com has American then National rows with columns:
    # Team, OVERALL, PCT, DIV, PCT, HOME, AWAY, PF, PA
    table = tables[0]
    teams: List[Dict[str, Any]] = []
    logos = load_logos_map()
    # Infer division from heading cells / order: American block then National
    # Count American teams by looking for 'American' header context — use STATIC order length heuristic
    # Better: find which rows appear before National header in thead — but thead lists both.
    # Use known switch: after we see Camden Catholic (typical National #1) following Cherry Hill East,
    # OR split when we hit a team that was already listed? Simpler: parse all rows, then assign
    # division by matching against subsequent National-only presence in table 0 after American count.
    rows = []
    for tr in table.select("tbody tr"):
        tds = [td.get_text(" ", strip=True) for td in tr.select("td")]
        if len(tds) < 9:
            continue
        name, overall, opct, div_rec, dpct, home, away, pf, pa = tds[:9]
        if not name or not re.match(r"^\d+-\d+", overall or ""):
            continue
        rows.append({
            "team_raw": name,
            "overall_record": overall,
            "overall_pct": float(opct) if re.match(r"^[.\d]+$", opct or "") else parse_pct(overall),
            "division_record": div_rec,
            "division_pct": float(dpct) if re.match(r"^[.\d]+$", dpct or "") else parse_pct(div_rec),
            "home_record": home,
            "away_record": away,
            "pf": int(pf) if pf.isdigit() else None,
            "pa": int(pa) if pa.isdigit() else None,
        })
    if not rows:
        return []

    # Split American / National: NJ.com lists American first. Detect split by finding
    # the first team that is classically National lead (Camden Catholic) after at least 4 American,
    # else split at midpoint of Olympic (often 6+7). Prefer: American until we see a repeat of structure.
    # Use header text order from page: count 'American' section length via STATIC from first rows
    # until we hit a team whose name appears in a known National seed list heuristic.
    national_starters = {
        "camden catholic", "seneca", "paul vi", "moorestown", "cherry hill west",
        "winslow", "camden", "bishop eustace", "timber creek",
    }
    split = None
    for i, r in enumerate(rows):
        if i >= 4 and r["team_raw"].strip().lower() in national_starters:
            split = i
            break
    if split is None:
        # fallback: 6 American if 13 teams, else half
        split = 6 if len(rows) >= 12 else max(1, len(rows) // 2)

    out = []
    for i, r in enumerate(rows):
        div = "American" if i < split else "National"
        logo = attach_logo(r["team_raw"], logos)
        out.append({
            "team": logo.get("opponent") or r["team_raw"],
            "division": div,
            "overall_record": r["overall_record"],
            "overall_pct": r["overall_pct"],
            "division_record": r["division_record"],
            "division_pct": r["division_pct"],
            "home_record": r["home_record"],
            "away_record": r["away_record"],
            "pf": r["pf"],
            "pa": r["pa"],
            "team_slug": logo.get("opponent_slug"),
            "logo_local": logo.get("opponent_logo_local"),
            "logo": logo.get("opponent_logo"),
            "is_shawnee": (logo.get("opponent_slug") == "shawnee")
            or ("shawnee" in (r["team_raw"] or "").lower()),
        })
    return out


def group_divisions(teams: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by: Dict[str, List[Dict[str, Any]]] = {}
    for t in teams:
        by.setdefault(t["division"], []).append(t)
    order = ["American", "National"] + sorted(k for k in by if k not in ("American", "National"))
    divisions = []
    for name in order:
        rows = by.get(name) or []
        rows.sort(
            key=lambda r: (
                -float(r.get("division_pct") or 0),
                -float(r.get("overall_pct") or 0),
                r.get("team") or "",
            )
        )
        for i, r in enumerate(rows, 1):
            r["rank"] = i
        if rows:
            divisions.append({"name": name, "teams": rows})
    return divisions


def fetch_standings(short: str) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    long = short_to_long(short)
    url = f"https://highschoolsports.nj.com/wrestling/standings/season/{long}?conference=Olympic"
    code, html = _curl(url)
    meta = {"url": url, "http": code, "bytes": len(html or "")}
    if code != 200 or not html or "Shawnee" not in html:
        meta["available"] = False
        return None, meta
    teams = parse_standings_html(html)
    if not teams:
        meta["available"] = False
        meta["error"] = "no teams parsed"
        return None, meta
    meta["available"] = True
    meta["teams_parsed"] = len(teams)
    divisions = group_divisions(teams)
    doc = {
        "season": long,
        "season_short": short,
        "title": short_to_label(short),
        "conference": "Olympic",
        "sport": "wrestling",
        "generated_at": _now(),
        "source": "NJ.com",
        "source_url": url,
        "status": "final",
        "season_status": "final",
        "columns": ["overall", "pct", "div", "div_pct", "home", "away", "pf", "pa"],
        "divisions": divisions,
        "gaps": [],
    }
    return doc, meta


def reconstruct_shawnee_standings(short: str, summary: Dict[str, Any], duals: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Shawnee-only standings line when conference table unavailable. No Div columns."""
    logos = load_logos_map()
    logo = attach_logo("Shawnee", logos)
    overall = summary["overall"]["record"]
    # Strip trailing -0 ties for display consistency with NJ.com when ties=0
    if summary["overall"]["ties"] == 0:
        overall = f"{summary['overall']['wins']}-{summary['overall']['losses']}"
    home = summary["home"]["record"]
    if summary["home"]["ties"] == 0:
        home = f"{summary['home']['wins']}-{summary['home']['losses']}"
    away = summary["away"]["record"]
    if summary["away"]["ties"] == 0:
        away = f"{summary['away']['wins']}-{summary['away']['losses']}"
    pct = summary.get("overall_pct")
    row = {
        "team": "Shawnee",
        "division": None,
        "overall_record": overall,
        "overall_pct": pct,
        "division_record": None,
        "division_pct": None,
        "home_record": home,
        "away_record": away,
        "pf": summary.get("pf"),
        "pa": summary.get("pa"),
        "team_slug": "shawnee",
        "logo_local": logo.get("opponent_logo_local"),
        "logo": logo.get("opponent_logo"),
        "is_shawnee": True,
        "rank": 1,
    }
    return {
        "season": short_to_long(short),
        "season_short": short,
        "title": short_to_label(short),
        "conference": "Olympic",
        "sport": "wrestling",
        "generated_at": _now(),
        "source": "Reconstructed from NJ.com Shawnee results",
        "source_url": f"https://highschoolsports.nj.com/school/medford-shawnee/wrestling/season/{short_to_long(short)}/",
        "status": "final",
        "season_status": "final",
        "columns": ["overall", "pct", "home", "away", "pf", "pa"],
        "reconstructed": True,
        "divisions": [{"name": "Shawnee", "teams": [row]}],
        "gaps": [
            "Olympic Conference division standings not published on NJ.com for this season; "
            "Shawnee Overall / PCT / Home / Away / PF / PA reconstructed from dual results. "
            "Div / Div PCT left blank."
        ],
        "validation": {
            "dual_count": len(duals),
            "overall": overall,
        },
    }


def coaching_record(short: str) -> Optional[str]:
    if not COACH_PATH.exists():
        return None
    doc = json.loads(COACH_PATH.read_text())
    for s in doc.get("seasons") or []:
        if s.get("season") == short:
            w, l, t = s.get("w", 0), s.get("l", 0), s.get("t", 0)
            return f"{w}-{l}" if not t else f"{w}-{l}-{t}"
    return None


def normalize_record(rec: str) -> str:
    parts = [int(x) for x in (rec or "0-0").split("-")]
    w = parts[0] if parts else 0
    l = parts[1] if len(parts) > 1 else 0
    t = parts[2] if len(parts) > 2 else 0
    return f"{w}-{l}" if t == 0 else f"{w}-{l}-{t}"


def build_season(short: str) -> Dict[str, Any]:
    events, sched_meta = fetch_schedule(short)
    duals = [e for e in events if e.get("event_kind") == "D" and e.get("result")]
    summary = summarize_duals(duals)
    standings, stand_meta = fetch_standings(short)
    if standings is None:
        standings = reconstruct_shawnee_standings(short, summary, duals)
        standings_mode = "reconstructed"
    else:
        standings_mode = "nj.com"
        # Enrich standings validation vs dual summary
        overall = summary["overall"]["record"]
        if summary["overall"]["ties"] == 0:
            overall_cmp = f"{summary['overall']['wins']}-{summary['overall']['losses']}"
        else:
            overall_cmp = overall
        shawnee = None
        for div in standings.get("divisions") or []:
            for t in div.get("teams") or []:
                if t.get("is_shawnee"):
                    shawnee = t
                    break
        issues = []
        if shawnee and normalize_record(shawnee.get("overall_record") or "") != normalize_record(overall_cmp):
            issues.append(
                f"NJ.com standings overall {shawnee.get('overall_record')} != duals {overall_cmp}"
            )
        standings["validation"] = {
            "ok": not issues,
            "issues": issues,
            "duals_overall": overall_cmp,
            "shawnee_row": shawnee,
        }

    coach_rec = coaching_record(short)
    dual_rec = (
        f"{summary['overall']['wins']}-{summary['overall']['losses']}"
        if summary["overall"]["ties"] == 0
        else summary["overall"]["record"]
    )
    mismatch = None
    if coach_rec and normalize_record(coach_rec) != normalize_record(dual_rec):
        mismatch = {
            "season": short,
            "coaching_history": coach_rec,
            "nj_com_duals": dual_rec,
        }

    # Conference record from standings Shawnee row when available
    conf_rec = None
    if standings_mode == "nj.com":
        for div in standings.get("divisions") or []:
            for t in div.get("teams") or []:
                if t.get("is_shawnee"):
                    conf_rec = t.get("division_record")
                    break

    out_dir = SEASONS_DIR / short
    out_dir.mkdir(parents=True, exist_ok=True)

    schedule_doc = {
        "season": short_to_long(short),
        "season_short": short,
        "title": short_to_label(short),
        "status": "final",
        "season_status": "final",
        "generated_at": _now(),
        "source": "NJ.com",
        "source_url": sched_meta.get("url"),
        "dual_record": dual_rec,
        "conference_record": conf_rec,
        "home_record": (
            f"{summary['home']['wins']}-{summary['home']['losses']}"
            if summary["home"]["ties"] == 0
            else summary["home"]["record"]
        ),
        "away_record": (
            f"{summary['away']['wins']}-{summary['away']['losses']}"
            if summary["away"]["ties"] == 0
            else summary["away"]["record"]
        ),
        "pf": summary["pf"],
        "pa": summary["pa"],
        "schedule": events,
    }

    results_rows = []
    for d in duals:
        results_rows.append({
            "date_iso": d.get("date_iso"),
            "opponent": d.get("opponent"),
            "score": d.get("score_display"),
            "result": d.get("result"),
            "home_away": d.get("home_away"),
            "opponent_logo_local": d.get("opponent_logo_local"),
            "opponent_logo": d.get("opponent_logo"),
            "score_shawnee": d.get("score_shawnee"),
            "score_opp": d.get("score_opp"),
        })

    results_doc = {
        "season": short_to_long(short),
        "season_short": short,
        "title": short_to_label(short),
        "status": "final",
        "season_status": "final",
        "generated_at": _now(),
        "source": "NJ.com",
        "shawnee_dual_record": dual_rec,
        "conference_record": conf_rec,
        "note": "Dual meets only — tournaments listed on Schedule.",
        "summary": summary,
        "rows": results_rows,
        "duals": results_rows,
    }

    meta_doc = {
        "season": short_to_long(short),
        "season_short": short,
        "title": short_to_label(short),
        "status": "final",
        "generated_at": _now(),
        "schedule_fetch": {k: v for k, v in sched_meta.items() if k != "html"},
        "standings_fetch": {k: v for k, v in stand_meta.items() if k != "html"},
        "standings_mode": standings_mode,
        "dual_record": dual_rec,
        "conference_record": conf_rec,
        "coaching_history_record": coach_rec,
        "coaching_mismatch": mismatch,
        "event_count": len(events),
        "dual_count": len(duals),
    }

    (out_dir / "schedule.json").write_text(json.dumps(schedule_doc, indent=2) + "\n")
    (out_dir / "results.json").write_text(json.dumps(results_doc, indent=2) + "\n")
    (out_dir / "standings.json").write_text(json.dumps(standings, indent=2) + "\n")
    (out_dir / "meta.json").write_text(json.dumps(meta_doc, indent=2) + "\n")
    return meta_doc


def export_current_2025_26() -> Dict[str, Any]:
    """Mirror live 2025-26 site data into data/seasons/2025-26/."""
    short = CURRENT
    out_dir = SEASONS_DIR / short
    out_dir.mkdir(parents=True, exist_ok=True)
    wd = json.loads(WRESTLING_CURRENT.read_text()) if WRESTLING_CURRENT.exists() else {}
    st = json.loads(STANDINGS_CURRENT.read_text()) if STANDINGS_CURRENT.exists() else {}
    md = wd.get("metadata") or {}
    schedule = wd.get("schedule") or []
    # Strip any accidental TW id fields from schedule copies for safety on display paths
    cleaned = []
    for m in schedule:
        row = {k: v for k, v in m.items() if k not in ("event_id", "parent_event_id", "tournament_key", "season_id", "team_id")}
        # Keep expandable panels working: preserve tournament_key/event_id only as opaque keys
        # Front end uses them for expand buttons — keep but never render as text.
        for keep in ("event_id", "parent_event_id", "tournament_key"):
            if keep in m:
                row[keep] = m[keep]
        cleaned.append(row)

    duals = (wd.get("dual_scores") or {}).get("duals") or []
    standings_block = wd.get("standings") or {}
    rows = standings_block.get("rows")
    if not rows:
        rows = [
            {
                "opponent": d.get("opponent"),
                "score": d.get("score_display") or f"{d.get('shawnee')}-{d.get('opp')}",
                "result": d.get("result"),
                "opponent_logo_local": d.get("opponent_logo_local"),
                "opponent_logo": d.get("opponent_logo"),
                "conference_dual": d.get("conference"),
                "date_iso": d.get("date_iso"),
                "home_away": d.get("home_away"),
            }
            for d in duals
        ]

    schedule_doc = {
        "season": "2025-2026",
        "season_short": short,
        "title": "2025-2026 Season",
        "status": "final",
        "season_status": "final",
        "generated_at": _now(),
        "source": md.get("sources", {}).get("schedule") or "Trackwrestling schedule feed",
        "dual_record": md.get("dual_record"),
        "conference_record": md.get("conference_record"),
        "home_record": md.get("home_record"),
        "away_record": md.get("away_record"),
        "schedule": cleaned,
        "tournament_results": wd.get("tournament_results"),
    }
    results_doc = {
        "season": "2025-2026",
        "season_short": short,
        "title": "2025-2026 Season",
        "status": "final",
        "season_status": "final",
        "generated_at": _now(),
        "shawnee_dual_record": md.get("dual_record"),
        "conference_record": md.get("conference_record"),
        "note": "Dual meets only — tournaments listed on Schedule.",
        "rows": rows,
        "duals": duals,
    }
    # Ensure standings has title/status/columns
    st = dict(st)
    st.setdefault("title", "2025-2026 Season")
    st.setdefault("season_short", short)
    st.setdefault("status", "final")
    st.setdefault("season_status", "final")
    st.setdefault("columns", ["overall", "div"])
    # Try to enrich from NJ.com for full columns
    nj_doc, nj_meta = fetch_standings(short)
    if nj_doc:
        st = nj_doc
        st["merged_from_site"] = True

    meta = {
        "season": "2025-2026",
        "season_short": short,
        "title": "2025-2026 Season",
        "status": "final",
        "generated_at": _now(),
        "dual_record": md.get("dual_record"),
        "conference_record": md.get("conference_record"),
        "coaching_history_record": coaching_record(short),
        "standings_mode": "nj.com" if nj_doc else "site",
        "standings_fetch": nj_meta,
        "event_count": len(cleaned),
        "dual_count": len(duals),
        "source": "site export + NJ.com standings when available",
    }
    (out_dir / "schedule.json").write_text(json.dumps(schedule_doc, indent=2) + "\n")
    (out_dir / "results.json").write_text(json.dumps(results_doc, indent=2) + "\n")
    (out_dir / "standings.json").write_text(json.dumps(st, indent=2) + "\n")
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    return meta


def write_index(built: List[str], mismatches: List[Dict[str, Any]], gaps: List[str]) -> None:
    # Newest first
    seasons = []
    for short in [CURRENT] + list(reversed(HISTORIC)):
        if short not in built:
            continue
        seasons.append({
            "id": short,
            "label": short_to_label(short),
            "path": f"data/seasons/{short}",
        })
    doc = {
        "default": CURRENT,
        "generated_at": _now(),
        "seasons": seasons,
        "coaching_mismatches": mismatches,
        "gaps": gaps,
    }
    SEASONS_DIR.mkdir(parents=True, exist_ok=True)
    (SEASONS_DIR / "index.json").write_text(json.dumps(doc, indent=2) + "\n")


def main(argv: List[str]) -> int:
    only = None
    if len(argv) > 1:
        only = argv[1]
    built = []
    mismatches = []
    gaps = []

    targets = [CURRENT] + list(reversed(HISTORIC))
    if only:
        targets = [only]

    for short in targets:
        print(f"Building {short} …", flush=True)
        try:
            if short == CURRENT:
                meta = export_current_2025_26()
            else:
                meta = build_season(short)
            built.append(short)
            if meta.get("coaching_mismatch"):
                mismatches.append(meta["coaching_mismatch"])
                print(f"  MISMATCH coaching={meta['coaching_mismatch']}")
            if meta.get("standings_mode") == "reconstructed":
                gaps.append(f"{short}: standings reconstructed (no NJ.com Olympic table)")
                print(f"  standings reconstructed")
            else:
                print(f"  duals={meta.get('dual_count')} standings={meta.get('standings_mode')}")
        except Exception as e:
            gaps.append(f"{short}: build failed: {e}")
            print(f"  FAILED {e}", flush=True)

    write_index(built, mismatches, gaps)
    report = {
        "built": built,
        "mismatches": mismatches,
        "gaps": gaps,
    }
    (SEASONS_DIR / "build_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
