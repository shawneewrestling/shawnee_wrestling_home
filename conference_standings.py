#!/usr/bin/env python3
"""Olympic Conference wrestling standings for the site Standings page.

Primary source: NJ.com conference standings (GoBound sport standings for
2025-26 currently return HTTP 401/403 from this environment; TW returns 406).
Writes data/standings.json and validates Shawnee's overall vs results ledger.
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from school_aliases import lookup_logo, load_logos_map, resolve_school, slugify_raw

logger = logging.getLogger("conference_standings")
ROOT = Path(__file__).resolve().parent
EST = ZoneInfo("America/New_York")
STANDINGS_PATH = ROOT / "data" / "standings.json"
LEDGER_PATH = ROOT / "data" / "results_ledger.json"
EXTERNAL_REF_PATH = ROOT / "data" / "results_external_ref.json"

NJ_URL = "https://highschoolsports.nj.com/wrestling/standings/season/2025-2026?conference=Olympic"
GOBOUND_OC = "https://www.gobound.com/nj/conferences/oc"
GOBOUND_BWR_ATTEMPTS = [
    "https://www.gobound.com/nj/conferences/oc/sports/bwr/2025-26/standings",
    "https://www.gobound.com/nj/conferences/oc/sports/bwr/2025-2026/standings",
    "https://www.gobound.com/nj/conferences/oc/sports/bwr/standings",
]

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# 2025-26 Olympic wrestling divisions (verified via NJ.com standings page).
# Shawnee is American. Used as fallback if scrape fails mid-season.
STATIC_DIVISIONS = {
    "American": [
        "Lenape",
        "Rancocas Valley",
        "Eastern Regional",
        "Cherokee",
        "Shawnee",
        "Cherry Hill East",
    ],
    "National": [
        "Camden Catholic",
        "Seneca",
        "Moorestown",
        "Cherry Hill West",
        "Paul VI",
        "Winslow",
        "Camden",
    ],
}


class StandingsConsistencyError(RuntimeError):
    pass


def _now() -> str:
    t = datetime.now(EST)
    s = t.strftime("%Y-%m-%dT%H:%M:%S%z")
    return s[:-2] + ":" + s[-2:]


def _slug_key(name: str) -> str:
    slug, _ = resolve_school(name)
    return slug or slugify_raw(name) or re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")


def _parse_key(name: str) -> str:
    """Dedupe key during scrape — exact raw slug, not fuzzy alias."""
    return slugify_raw(name)


def _parse_record(rec: str) -> Tuple[int, int, int]:
    parts = [int(x) for x in (rec or "0-0").split("-")]
    w = parts[0] if len(parts) > 0 else 0
    l = parts[1] if len(parts) > 1 else 0
    t = parts[2] if len(parts) > 2 else 0
    return w, l, t


def _win_pct(rec: str) -> float:
    w, l, t = _parse_record(rec)
    n = w + l + t
    return (w + 0.5 * t) / n if n else 0.0


def _curl(url: str, referer: str | None = None) -> Tuple[int, str]:
    cmd = ["curl", "-sL", "-A", UA, "-w", "\n__HTTP__:%{http_code}", url]
    if referer:
        cmd[1:1] = []  # keep simple
        cmd = ["curl", "-sL", "-A", UA, "-H", f"Referer: {referer}", "-w", "\n__HTTP__:%{http_code}", url]
    try:
        out = subprocess.check_output(cmd, text=True, errors="replace", timeout=45)
    except Exception as e:
        logger.warning("fetch failed %s: %s", url, e)
        return 0, ""
    if "__HTTP__:" in out:
        body, _, code = out.rpartition("__HTTP__:")
        try:
            return int(code.strip()), body
        except ValueError:
            return 0, body
    return 0, out


def try_gobound() -> Dict[str, Any]:
    """Attempt GoBound OC wrestling standings. Returns status notes; rarely body for 2025-26."""
    notes = []
    code, body = _curl(GOBOUND_OC)
    notes.append({"url": GOBOUND_OC, "http": code, "bytes": len(body)})
    for url in GOBOUND_BWR_ATTEMPTS:
        c, b = _curl(url, referer=GOBOUND_OC)
        notes.append({"url": url, "http": c, "bytes": len(b)})
        if c == 200 and len(b) > 20000 and ("Shawnee" in b or "Lenape" in b):
            return {"ok": True, "html": b, "url": url, "attempts": notes}
    return {"ok": False, "html": None, "url": None, "attempts": notes,
            "note": "GoBound boys wrestling 2025-26 standings blocked (401/403); OC hub ok"}


def parse_nj_com(html: str) -> List[Dict[str, Any]]:
    """Parse NJ.com Olympic wrestling standings tables (American then National)."""
    text = re.sub(r"<script[\s\S]*?</script>", "", html)
    # Locate division sections
    am = text.find(">American</")
    nat = text.find(">National</")
    if am < 0:
        am = text.find("American")
    if nat < 0:
        nat = text.find("National")
    sections = []
    if am >= 0 and nat > am:
        sections.append(("American", text[am:nat]))
        # National table ends before a second full conference table / footer —
        # take until second Shawnee or 80k chars
        sections.append(("National", text[nat:nat + 80000]))
    else:
        sections.append(("Unknown", text))

    row_pat = re.compile(
        r">([A-Za-z0-9 .\'()\-/]+)</a>\s*</td>\s*"
        r"<td>(\d+-\d+(?:-\d+)?)</td>\s*"
        r"<td[^>]*>([.\d]+)</td>\s*"
        r"<td[^>]*>(\d+-\d+(?:-\d+)?)</td>\s*"
        r"<td[^>]*>([.\d]+)</td>",
        re.S,
    )
    teams: List[Dict[str, Any]] = []
    seen = set()
    for div, chunk in sections:
        for name, overall, opct, division, dpct in row_pat.findall(chunk):
            name = name.strip()
            key = (_parse_key(name), div)
            if key in seen:
                continue
            # Skip second conference-wide table rows once we have division sets
            # Conference-wide table repeats every OC team after the division tables.
            if div == "National" and name in {t["team"] for t in teams if t["division"] == "American"}:
                break
            if _parse_key(name) in {_parse_key(t["team"]) for t in teams}:
                continue
            seen.add(key)
            teams.append({
                "team": name,
                "division": div,
                "overall_record": overall,
                "overall_pct": float(opct) if opct else _win_pct(overall),
                "division_record": division,
                "division_pct": float(dpct) if dpct else _win_pct(division),
            })
    return teams


def fetch_nj_com() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    code, body = _curl(NJ_URL)
    meta = {"url": NJ_URL, "http": code, "bytes": len(body)}
    if code != 200 or not body:
        return [], meta
    teams = parse_nj_com(body)
    meta["teams_parsed"] = len(teams)
    return teams, meta


def attach_logos(teams: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    logos = load_logos_map(ROOT / "data" / "logos.json")
    out = []
    for t in teams:
        info = lookup_logo(t["team"], logos, make_badge=True)
        row = dict(t)
        row["team"] = info.get("opponent") or t["team"]
        row["team_slug"] = info.get("opponent_slug")
        row["logo_local"] = info.get("opponent_logo_local")
        row["logo"] = info.get("opponent_logo")
        row["is_shawnee"] = _slug_key(row["team"]) in ("shawnee",) or "shawnee" in (row["team"] or "").lower()
        out.append(row)
    return out


def group_and_sort(teams: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_div: Dict[str, List[Dict[str, Any]]] = {}
    for t in teams:
        by_div.setdefault(t["division"], []).append(t)
    divisions = []
    # Prefer American then National then others
    order = ["American", "National"] + sorted(k for k in by_div if k not in ("American", "National"))
    for div in order:
        rows = by_div.get(div) or []
        rows.sort(key=lambda r: (-float(r.get("division_pct") or 0), -float(r.get("overall_pct") or 0), r.get("team") or ""))
        for i, r in enumerate(rows, 1):
            r["rank"] = i
        divisions.append({
            "name": div,
            "teams": rows,
        })
    return divisions


def validate_shawnee(divisions: List[Dict[str, Any]], ledger_path: Path | None = None) -> Dict[str, Any]:
    ledger_path = ledger_path or LEDGER_PATH
    shawnee_row = None
    for div in divisions:
        for t in div.get("teams") or []:
            if t.get("is_shawnee"):
                shawnee_row = t
                break
    result = {"ok": True, "shawnee_row": shawnee_row, "issues": []}
    if not shawnee_row:
        result["ok"] = False
        result["issues"].append("Shawnee missing from conference standings")
        return result
    if (shawnee_row.get("division") or "").lower() != "american":
        result["ok"] = False
        result["issues"].append(
            f"Shawnee division is {shawnee_row.get('division')!r}, expected American"
        )
    ledger_rec = None
    if ledger_path.exists():
        ledger = json.loads(ledger_path.read_text())
        ledger_rec = (ledger.get("summary") or {}).get("overall", {}).get("record")
        conf_rec = (ledger.get("summary") or {}).get("conference", {}).get("record")
        if ledger_rec and shawnee_row.get("overall_record") != ledger_rec:
            result["ok"] = False
            result["issues"].append(
                f"Shawnee overall {shawnee_row.get('overall_record')} != ledger {ledger_rec}"
            )
        if conf_rec and shawnee_row.get("division_record") != conf_rec:
            # Soft: division record should match ledger conference when conference_opponents aligned
            result["issues"].append(
                f"note: Shawnee division {shawnee_row.get('division_record')} vs ledger conference {conf_rec}"
            )
            if shawnee_row.get("division_record") != conf_rec:
                result["ok"] = False
    result["ledger_overall"] = ledger_rec
    return result


def build_standings(*, write: bool = True, strict: bool = True) -> Dict[str, Any]:
    sources_tried = []
    gaps = []

    gb = try_gobound()
    sources_tried.append({"name": "GoBound", "detail": gb})
    if not gb.get("ok"):
        gaps.append(gb.get("note") or "GoBound wrestling standings unavailable")

    teams, nj_meta = fetch_nj_com()
    sources_tried.append({"name": "NJ.com", "detail": nj_meta})
    primary = "NJ.com"
    primary_url = NJ_URL
    if not teams:
        gaps.append("NJ.com parse returned no teams")
        # Fallback skeleton with empty records from static alignment
        teams = []
        for div, names in STATIC_DIVISIONS.items():
            for n in names:
                teams.append({
                    "team": n,
                    "division": div,
                    "overall_record": "—",
                    "overall_pct": 0.0,
                    "division_record": "—",
                    "division_pct": 0.0,
                })
        primary = "static_division_alignment"
        primary_url = None

    teams = attach_logos(teams)
    divisions = group_and_sort(teams)
    validation = validate_shawnee(divisions)

    doc = {
        "season": "2025-2026",
        "conference": "Olympic",
        "sport": "wrestling",
        "generated_at": _now(),
        "as_of": _now()[:10],
        "source": primary,
        "source_url": primary_url,
        "sources_tried": [
            {"name": s["name"], "http": (s.get("detail") or {}).get("http") or (s.get("detail") or {}).get("attempts"),
             "ok": bool((s.get("detail") or {}).get("ok") if s["name"] == "GoBound" else (s.get("detail") or {}).get("teams_parsed"))}
            for s in sources_tried
        ],
        "gaps": gaps + ([{"type": "validation", "issues": validation["issues"]}] if validation["issues"] else []),
        "validation": validation,
        "divisions": divisions,
        "policy": (
            "Conference standings for all Olympic wrestling teams by division. "
            "Shawnee dual schedule remains Trackwrestling-sourced via results_ledger; "
            "peer records from GoBound when available, else NJ.com."
        ),
    }

    if write:
        STANDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        STANDINGS_PATH.write_text(json.dumps(doc, indent=2) + "\n")
        logger.info(
            "Conference standings: %s divisions, Shawnee=%s overall=%s div=%s ok=%s",
            len(divisions),
            (validation.get("shawnee_row") or {}).get("division"),
            (validation.get("shawnee_row") or {}).get("overall_record"),
            (validation.get("shawnee_row") or {}).get("division_record"),
            validation.get("ok"),
        )

    if strict and not validation.get("ok"):
        raise StandingsConsistencyError(
            "CONFERENCE STANDINGS VALIDATION FAILED:\n" + json.dumps(validation, indent=2)
        )
    return doc


def sync_external_ref_conference_opponents(doc: Dict[str, Any] | None = None) -> None:
    """Keep results_external_ref conference_opponents = American division peers (excl. Shawnee)."""
    if not EXTERNAL_REF_PATH.exists():
        return
    ref = json.loads(EXTERNAL_REF_PATH.read_text())
    american = []
    for div in (doc or {}).get("divisions") or []:
        if (div.get("name") or "").lower() == "american":
            for t in div.get("teams") or []:
                if not t.get("is_shawnee"):
                    american.append(t["team"])
    if not american:
        american = [n for n in STATIC_DIVISIONS["American"] if n.lower() != "shawnee"]
    ref["conference_opponents"] = american
    ref["conference_name"] = "Olympic - American"
    EXTERNAL_REF_PATH.write_text(json.dumps(ref, indent=2) + "\n")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        doc = build_standings(write=True, strict=False)
    except StandingsConsistencyError as e:
        print(e)
        raise SystemExit(1)
    sync_external_ref_conference_opponents(doc)
    print(json.dumps({
        "source": doc["source"],
        "gaps": doc["gaps"],
        "validation": doc["validation"],
        "divisions": [
            {"name": d["name"], "teams": [
                {"team": t["team"], "overall": t["overall_record"], "div": t["division_record"]}
                for t in d["teams"]
            ]}
            for d in doc["divisions"]
        ],
    }, indent=2))
