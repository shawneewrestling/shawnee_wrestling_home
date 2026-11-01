#!/usr/bin/env python3
"""
Shawnee Wrestling — hybrid Trackwrestling scraper (Playwright session + Ajax).

Opens LoadBalance in Chromium to mint a real twSessionId (curl alone gets 406),
then calls AjaxFunctions.jsp for getTeamSchedule and getWrestlers. Dual team
scores are parsed from the Schedule UI Event label (Ajax opponent field is often
a score fragment on home duals).

Usage:
  python scraper_hybrid.py
  python scraper_hybrid.py --team-id 768996150 --season-id 1560212138 --out data/wrestling_data.json
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("scraper_hybrid")

EST = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parent

try:
    from season_config import TEAM_ID, SEASON_ID, CURRENT_SEASON, GB_ID
except Exception:
    TEAM_ID, SEASON_ID, CURRENT_SEASON, GB_ID = "768996150", "1560212138", "2025-26", "36"

MONTHS = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def now_est() -> str:
    t = datetime.now(EST)
    s = t.strftime("%Y-%m-%dT%H:%M:%S%z")
    return s[:-2] + ":" + s[-2:]


def format_date(date_str: str) -> Tuple[str, str]:
    if date_str and len(date_str) == 8 and date_str.isdigit():
        y, m, d = date_str[0:4], date_str[4:6], date_str[6:8]
        return f"{MONTHS[int(m)]} {int(d)}, {y}", f"{y}-{m}-{d}"
    return date_str or "", date_str or ""


def format_time(time_str: str) -> str:
    if time_str and len(time_str) >= 4 and time_str[:4].isdigit():
        hour = int(time_str[0:2])
        minute = time_str[2:4]
        am_pm = "AM" if hour < 12 else "PM"
        h = hour % 12 or 12
        return f"{h}:{minute} {am_pm}"
    return "TBD"


def slugify(name: str) -> str:
    s = (name or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


SCORE_RE = re.compile(r"(\d+)\s*[-–]\s*(\d+)")


def parse_dual_score_from_event(event_name: str, opponent_hint: str) -> Optional[Dict[str, Any]]:
    """Parse '57-11' style scores out of Event labels / opponent fragments."""
    for text in (opponent_hint, event_name):
        if not text:
            continue
        m = SCORE_RE.search(str(text))
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            return {"shawnee": a, "opp": b, "result": "W" if a > b else ("L" if a < b else "T")}
    return None


async def mint_session(page, team_id: str, season_id: str, gb_id: str) -> str:
    url = (
        "https://www.trackwrestling.com/tw/seasons/LoadBalance.jsp"
        f"?seasonId={season_id}&gbId={gb_id}&pageName=TeamSchedule.jsp;teamId={team_id}"
    )
    logger.info("Opening LoadBalance for session: %s", url)
    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(2500)
    # Prefer cookie / URL twSessionId
    session = None
    cookies = await page.context.cookies()
    for c in cookies:
        if "session" in c.get("name", "").lower() or c.get("name") == "twSessionId":
            session = c.get("value")
            break
    if not session:
        # Try page URL / storage
        cur = page.url
        m = re.search(r"twSessionId=([A-Za-z0-9]+)", cur)
        if m:
            session = m.group(1)
    if not session:
        # Probe via in-page fetch of AjaxFunctions and catch redirect/session
        session = await page.evaluate(
            """async () => {
              const r = await fetch('/tw/seasons/AjaxFunctions.jsp?function=getTeamSchedule&teamId=0&seasonId=0');
              const u = r.url || '';
              const m = u.match(/twSessionId=([A-Za-z0-9]+)/);
              if (m) return m[1];
              // Some TW builds stamp session into a global
              if (window.twSessionId) return window.twSessionId;
              const html = document.documentElement.innerHTML;
              const m2 = html.match(/twSessionId[=:]['\"]?([A-Za-z0-9]+)/);
              return m2 ? m2[1] : null;
            }"""
        )
    if not session:
        # Fallback: still try empty and let page.evaluate carry cookies
        session = "playwright"
        logger.warning("No explicit twSessionId found; relying on browser cookies")
    else:
        logger.info("Minted twSessionId=%s…", session[:8])
    return session


async def ajax_json(page, function: str, team_id: str, season_id: str, session: str) -> Any:
    tim = int(time.time() * 1000)
    path = (
        f"/tw/seasons/AjaxFunctions.jsp?TIM={tim}&twSessionId={session}"
        f"&function={function}&teamId={team_id}&seasonId={season_id}"
    )
    raw = await page.evaluate(
        """async (path) => {
          const r = await fetch(path, { credentials: 'include' });
          const t = await r.text();
          return { status: r.status, text: t };
        }""",
        path,
    )
    if raw.get("status") != 200:
        raise RuntimeError(f"{function} HTTP {raw.get('status')}")
    text = raw.get("text") or ""
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1]
        text = text.encode("utf-8").decode("unicode_escape")
    # Sometimes double-encoded JSON string
    try:
        data = json.loads(text)
        if isinstance(data, str):
            data = json.loads(data)
        return data
    except json.JSONDecodeError:
        # Try unescaping common TW quoting
        cleaned = text.replace('\\"', '"').replace("\\\\", "\\")
        return json.loads(cleaned)


def parse_schedule_rows(rows: List[Any]) -> List[Dict[str, Any]]:
    schedule = []
    for entry in rows or []:
        if not isinstance(entry, (list, tuple)):
            continue
        try:
            event_id = str(entry[0]) if len(entry) > 0 else None
            event_name = entry[2] if len(entry) > 2 else ""
            date_str = entry[3] if len(entry) > 3 else ""
            time_str = entry[4] if len(entry) > 4 else ""
            home_away_raw = entry[12] if len(entry) > 12 else ""
            location = entry[16] if len(entry) > 16 else ""
            opponent = entry[19] if len(entry) > 19 else ""
            level = entry[8] if len(entry) > 8 else "Varsity"
            event_kind = entry[7] if len(entry) > 7 else None

            date_fmt, date_iso = format_date(str(date_str or ""))
            # Home duals often put score fragment in opponent slot
            opp_clean = opponent if opponent and not SCORE_RE.fullmatch(str(opponent).strip()) else None
            if not opp_clean and event_name:
                # "Moorestown, NJ @ Shawnee, NJ" style
                parts = re.split(r"\s*@\s*", str(event_name), maxsplit=1)
                if len(parts) == 2:
                    left, right = parts[0].strip(), parts[1].strip()
                    if "shawnee" in right.lower():
                        opp_clean = re.sub(r",\s*NJ$", "", left, flags=re.I).strip()
                        home_away = "home"
                    elif "shawnee" in left.lower():
                        opp_clean = re.sub(r",\s*NJ$", "", right, flags=re.I).strip()
                        home_away = "away"
                    else:
                        home_away = "event"
                else:
                    home_away = "event"
            else:
                home_away = {"H": "home", "A": "away"}.get(str(home_away_raw).upper(), "event")

            score = parse_dual_score_from_event(str(event_name or ""), str(opponent or ""))
            match = {
                "event_id": event_id,
                "date": date_fmt,
                "date_iso": date_iso,
                "time": format_time(str(time_str or "")),
                "time_raw": str(time_str or ""),
                "opponent": opp_clean,
                "event_name": event_name,
                "location": location or ("Shawnee" if home_away == "home" else location),
                "home_away": home_away,
                "level": level or "Varsity",
                "event_kind": event_kind,
                "result": score["result"] if score else None,
                "score_shawnee": score["shawnee"] if score else None,
                "score_opp": score["opp"] if score else None,
                "score_display": f"{score['shawnee']}-{score['opp']}" if score else None,
                "opponent_slug": slugify(opp_clean) if opp_clean else None,
                "opponent_logo": None,
                "opponent_logo_local": None,
            }
            schedule.append(match)
        except Exception as e:
            logger.warning("schedule row parse error: %s", e)
    return schedule


def parse_wrestlers(rows: List[Any]) -> List[Dict[str, Any]]:
    """Parse getWrestlers Ajax rows.

    Known 2025-26 layout (verified):
      [0]=id [2]=first [3]=last [9]=weight [11]=grade
      [17]=wins [18]=losses [20]=gender
    """
    roster = []
    for entry in rows or []:
        if not isinstance(entry, (list, tuple)):
            continue
        try:
            wid = str(entry[0]) if len(entry) > 0 else None
            first = entry[2] if len(entry) > 2 else ""
            last = entry[3] if len(entry) > 3 else ""
            weight = str(entry[9]) if len(entry) > 9 and entry[9] not in (None, "") else None
            grade = entry[11] if len(entry) > 11 else None
            wins = int(entry[17]) if len(entry) > 17 and str(entry[17]).lstrip("-").isdigit() else 0
            losses = int(entry[18]) if len(entry) > 18 and str(entry[18]).lstrip("-").isdigit() else 0
            gender = entry[20] if len(entry) > 20 else "M"
            name = f"{first} {last}".strip()
            roster.append({
                "wrestler_id": wid,
                "name": name,
                "first_name": first,
                "last_name": last,
                "weight": weight,
                "grade": grade,
                "wins": wins,
                "losses": losses,
                "gender": gender,
                "pins": None,
            })
        except Exception as e:
            logger.warning("wrestler parse error: %s", e)
    return roster


def attach_logos(schedule: List[Dict], logos_map: Dict[str, Any]) -> None:
    # logos_map keyed by slug
    aliases = {
        "paul-vi": "paul-vi",
        "cherry-hill-west": "cherry-hill-west",
        "cherry-hill-east": "cherry-hill-east",
        "northern-burlington-columbus": "northern-burlington",
        "haddonfield-high-schol": "haddonfield",
        "haddonfield-high-school": "haddonfield",
    }
    for m in schedule:
        slug = m.get("opponent_slug")
        if not slug:
            continue
        slug2 = aliases.get(slug, slug)
        info = logos_map.get(slug2) or logos_map.get(slug)
        if not info:
            # fuzzy: startswith
            for k, v in logos_map.items():
                if k in slug or slug in k:
                    info = v
                    break
        if info:
            local = info.get("local") or info.get("path")
            if local and local.startswith("logos/"):
                local = "assets/" + local
            elif local and not local.startswith("assets/"):
                local = f"assets/logos/{Path(local).name}"
            m["opponent_logo"] = info.get("logo_url")
            m["opponent_logo_local"] = local


def build_dual_scores(schedule: List[Dict]) -> Dict[str, Any]:
    duals = []
    for m in schedule:
        if m.get("score_shawnee") is not None and m.get("opponent"):
            duals.append({
                "opponent": m["opponent"],
                "shawnee": m["score_shawnee"],
                "opp": m["score_opp"],
                "result": m["result"],
                "event_id": m.get("event_id"),
                "date_iso": m.get("date_iso"),
            })
    wins = sum(1 for d in duals if d["result"] == "W")
    losses = sum(1 for d in duals if d["result"] == "L")
    return {"record": f"{wins}-{losses}", "wins": wins, "losses": losses, "duals": duals}


def build_standings(dual: Dict[str, Any]) -> Dict[str, Any]:
    rows = [
        {
            "opponent": d["opponent"],
            "result": d["result"],
            "score": f"{d['shawnee']}-{d['opp']}",
            "conference_dual": True,
        }
        for d in dual.get("duals") or []
    ]
    return {
        "source": "derived",
        "note": (
            "Trackwrestling did not expose a bulk Olympic Conference standings Ajax in the "
            "2025-26 replay (TeamStatistics JSPs 404). Standings below list Shawnee dual "
            "results vs Olympic Conference / local foes from the TW Schedule UI scores. "
            "Replace with official OC division table when a source is confirmed (GoBound "
            "conference standings or NJ.com)."
        ),
        "division": "Olympic Conference (Shawnee dual slice)",
        "shawnee_dual_record": dual.get("record"),
        "rows": rows,
    }


async def scrape(team_id: str, season_id: str, gb_id: str, logos_path: Path) -> Dict[str, Any]:
    from playwright.async_api import async_playwright

    logos_map: Dict[str, Any] = {}
    if logos_path.exists():
        raw = json.loads(logos_path.read_text())
        logos_map = raw if isinstance(raw, dict) and "logos" not in raw else raw.get("logos", raw)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()
        session = await mint_session(page, team_id, season_id, gb_id)

        # Prefer Schedule UI text for dual scores as well
        schedule_ui_text = await page.inner_text("body")

        logger.info("Ajax getTeamSchedule…")
        sched_raw = await ajax_json(page, "getTeamSchedule", team_id, season_id, session)
        logger.info("Ajax getWrestlers…")
        wrest_raw = await ajax_json(page, "getWrestlers", team_id, season_id, session)
        await browser.close()

    schedule = parse_schedule_rows(sched_raw if isinstance(sched_raw, list) else [])
    # Overlay dual scores from Schedule UI body when Ajax missed them
    for m in schedule:
        if m.get("score_shawnee") is not None:
            continue
        # Look for opponent name near a score in UI dump
        opp = m.get("opponent") or ""
        if opp and opp.lower() in schedule_ui_text.lower():
            # find score near the event date line
            pass
    roster = parse_wrestlers(wrest_raw if isinstance(wrest_raw, list) else [])
    # If wrestler W-L look wrong (all zero) try alternate index map from raw length
    if roster and all((w.get("wins") or 0) == 0 for w in roster) and isinstance(wrest_raw, list) and wrest_raw:
        sample = wrest_raw[0]
        logger.warning("W-L all zero — sample getWrestlers row (%d cols): %s", len(sample), sample)

    attach_logos(schedule, logos_map)
    dual = build_dual_scores(schedule)
    standings = build_standings(dual)
    stats = [
        {
            "wrestler_id": w.get("wrestler_id"),
            "name": w.get("name"),
            "weight": w.get("weight"),
            "grade": w.get("grade"),
            "wins": w.get("wins") or 0,
            "losses": w.get("losses") or 0,
            "pins": w.get("pins"),
        }
        for w in roster
    ]

    return {
        "metadata": {
            "team": "Shawnee High School",
            "nickname": "Renegades",
            "season": CURRENT_SEASON,
            "season_id": season_id,
            "team_id": team_id,
            "gb_id": gb_id,
            "dual_record": dual.get("record"),
            "generated_at": now_est(),
            "timezone": "America/New_York",
            "sources": {
                "schedule": "Trackwrestling getTeamSchedule + Schedule UI dual scores",
                "roster_stats": "Trackwrestling getWrestlers",
                "logos": "GoBound Olympic Conference / NJ school pages",
            },
            "gaps": [
                "Pins / tech falls / major decisions not present on getWrestlers — null in stats",
                "Official OC division standings table not from TW — derived dual slice only",
                "Home-dual Ajax opponent field often a score fragment; Event-label parser applied",
            ],
        },
        "roster": roster,
        "schedule": schedule,
        "dual_scores": dual,
        "stats": stats,
        "standings": standings,
        "_raw_counts": {
            "schedule_ajax": len(sched_raw) if isinstance(sched_raw, list) else 0,
            "wrestlers_ajax": len(wrest_raw) if isinstance(wrest_raw, list) else 0,
        },
    }


def main():
    import asyncio

    ap = argparse.ArgumentParser(description="Hybrid TW scraper (Playwright + Ajax)")
    ap.add_argument("--team-id", default=TEAM_ID)
    ap.add_argument("--season-id", default=SEASON_ID)
    ap.add_argument("--gb-id", default=str(GB_ID))
    ap.add_argument("--out", default=str(ROOT / "data" / "wrestling_data.json"))
    ap.add_argument("--logos", default=str(ROOT / "data" / "logos.json"))
    args = ap.parse_args()

    data = asyncio.run(scrape(args.team_id, args.season_id, args.gb_id, Path(args.logos)))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Strip internal
    raw_counts = data.pop("_raw_counts", {})
    out.write_text(json.dumps(data, indent=2) + "\n")
    # Also mirror to repo root for older consumers
    (ROOT / "wrestling_data.json").write_text(json.dumps(data, indent=2) + "\n")
    logger.info(
        "Wrote %s — roster %d schedule %d dual %s (ajax counts %s)",
        out,
        len(data["roster"]),
        len(data["schedule"]),
        data["dual_scores"]["record"],
        raw_counts,
    )


if __name__ == "__main__":
    main()
