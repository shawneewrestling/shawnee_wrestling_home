#!/usr/bin/env python3
"""Parsers for Trackwrestling Ajax rows and browser HTML/text captures."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

MONTHS = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

SCORE_RE = re.compile(r"(\d+)\s*[-–]\s*(\d+)")
SHAWNEE_RE = re.compile(r"shawnee", re.I)


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


def _clean_opp(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    s = str(name).strip()
    if SCORE_RE.fullmatch(s):
        return None
    s = re.sub(r",\s*NJ$", "", s, flags=re.I).strip()
    s = re.sub(r"\s+", " ", s)
    return s or None


def _scores_from_dual_row(entry: List[Any], home_away: str) -> Optional[Dict[str, Any]]:
    """Home: col18=Shawnee, col21=opp. Away: col18=opp, col21=Shawnee."""
    try:
        a = entry[18] if len(entry) > 18 else None
        b = entry[21] if len(entry) > 21 else None
        if a is None or b is None:
            return None
        sa, sb = int(str(a)), int(str(b))
    except (TypeError, ValueError):
        return None
    if home_away == "away":
        shawnee, opp = sb, sa
    else:
        shawnee, opp = sa, sb
    return {
        "shawnee": shawnee,
        "opp": opp,
        "result": "W" if shawnee > opp else ("L" if shawnee < opp else "T"),
    }


def parse_schedule_rows(rows: List[Any]) -> List[Dict[str, Any]]:
    schedule: List[Dict[str, Any]] = []
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
            level = entry[36] if len(entry) > 36 else "Varsity"
            if not isinstance(level, str) or level.isdigit() or level in ("Y", "N"):
                level = "Varsity"
            event_kind = entry[7] if len(entry) > 7 else None

            date_fmt, date_iso = format_date(str(date_str or ""))
            home_away = {"H": "home", "A": "away", "E": "event"}.get(
                str(home_away_raw).upper(), "event"
            )

            opp_clean = _clean_opp(opponent)
            if opp_clean and SHAWNEE_RE.search(opp_clean):
                loc16 = _clean_opp(location)
                if loc16 and not SHAWNEE_RE.search(loc16):
                    opp_clean = loc16
                    home_away = "away"
                else:
                    opp_clean = None
            if not opp_clean and event_name:
                parts = re.split(r"\s*@\s*", str(event_name), maxsplit=1)
                if len(parts) == 2:
                    left, right = parts[0].strip(), parts[1].strip()
                    if SHAWNEE_RE.search(right):
                        opp_clean = _clean_opp(left)
                        home_away = "home"
                    elif SHAWNEE_RE.search(left):
                        opp_clean = _clean_opp(right)
                        home_away = "away"

            score = _scores_from_dual_row(list(entry), home_away)
            if not score:
                for text in (opponent, event_name):
                    if not text:
                        continue
                    m = SCORE_RE.search(str(text))
                    if m:
                        a, b = int(m.group(1)), int(m.group(2))
                        if home_away == "away":
                            shawnee, opp = b, a
                        else:
                            shawnee, opp = a, b
                        score = {
                            "shawnee": shawnee,
                            "opp": opp,
                            "result": "W" if shawnee > opp else ("L" if shawnee < opp else "T"),
                        }
                        break

            venue = None
            if home_away == "home":
                venue = "Shawnee"
            elif home_away == "away" and opp_clean:
                venue = opp_clean
            elif location and not SHAWNEE_RE.search(str(location)):
                venue = _clean_opp(location)

            schedule.append({
                "event_id": event_id,
                "date": date_fmt,
                "date_iso": date_iso,
                "time": format_time(str(time_str or "")),
                "time_raw": str(time_str or ""),
                "opponent": opp_clean,
                "event_name": event_name,
                "location": venue or (location if location else None),
                "home_away": home_away,
                "level": level or "Varsity",
                "event_kind": event_kind,
                "result": score["result"] if score else None,
                "score_shawnee": score["shawnee"] if score else None,
                "score_opp": score["opp"] if score else None,
                "score_display": (
                    f"{score['shawnee']}-{score['opp']}" if score else None
                ),
                "opponent_slug": slugify(opp_clean) if opp_clean else None,
            })
        except Exception:
            continue
    return schedule


def parse_wrestlers(rows: List[Any]) -> List[Dict[str, Any]]:
    """getWrestlers: [0]=id [2]=first [3]=last [9]=weight [11]=grade
    [17]=wins [18]=losses [20]=gender. No pins in this feed."""
    roster: List[Dict[str, Any]] = []
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
            roster.append({
                "wrestler_id": wid,
                "name": f"{first} {last}".strip(),
                "first_name": first,
                "last_name": last,
                "weight": weight,
                "grade": grade,
                "wins": wins,
                "losses": losses,
                "gender": gender,
                "pins": None,
                "tech_falls": None,
                "major_decisions": None,
                "decisions": None,
            })
        except Exception:
            continue
    return roster


def find_shawnee_team(
    teams: List[Any],
    school: str = "Shawnee",
    city_hint: Optional[str] = "Medford",
) -> Optional[Dict[str, Any]]:
    hits: List[Dict[str, Any]] = []
    for row in teams or []:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        name = str(row[1] or "")
        if name.lower() != school.lower() and school.lower() not in name.lower():
            continue
        hits.append({
            "team_id": str(row[0]),
            "name": name,
            "state": row[2] if len(row) > 2 else None,
            "abbr": row[3] if len(row) > 3 else None,
            "gb_name": row[4] if len(row) > 4 else None,
            "district_region": row[5] if len(row) > 5 else None,
            "gb_id": str(row[6]) if len(row) > 6 else None,
            "school_full": row[13] if len(row) > 13 else None,
            "address": row[14] if len(row) > 14 else None,
            "city": row[15] if len(row) > 15 else None,
            "zip": row[16] if len(row) > 16 else None,
            "raw": row,
        })
    if not hits:
        return None
    if city_hint:
        city_hits = [h for h in hits if str(h.get("city") or "").lower() == city_hint.lower()]
        if city_hits:
            return city_hits[0]
    exact = [h for h in hits if h["name"].lower() == school.lower()]
    return (exact or hits)[0]


def find_nj_gb(gbs: List[Any]) -> Optional[Dict[str, Any]]:
    for row in gbs or []:
        if not isinstance(row, (list, tuple)):
            continue
        if len(row) > 7 and str(row[7]).upper() == "NJ":
            return {"gb_id": str(row[0]), "name": row[1], "raw": row}
        if any("New Jersey" in str(c) for c in row):
            return {"gb_id": str(row[0]), "name": row[1], "raw": row}
    return None


def build_dual_scores(schedule: List[Dict[str, Any]]) -> Dict[str, Any]:
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
                "home_away": m.get("home_away"),
            })
    wins = sum(1 for d in duals if d["result"] == "W")
    losses = sum(1 for d in duals if d["result"] == "L")
    ties = sum(1 for d in duals if d["result"] == "T")
    return {
        "record": f"{wins}-{losses}" + (f"-{ties}" if ties else ""),
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "duals": duals,
    }


WIN_TYPE_KEYS = {
    "fall": "pins",
    "pin": "pins",
    "falls": "pins",
    "tech. fall": "tech_falls",
    "tech fall": "tech_falls",
    "technical fall": "tech_falls",
    "tf": "tech_falls",
    "maj. dec.": "major_decisions",
    "major decision": "major_decisions",
    "major": "major_decisions",
    "md": "major_decisions",
    "decision": "decisions",
    "dec.": "decisions",
    "dec": "decisions",
}


def parse_win_types_capture(text: str) -> List[Dict[str, Any]]:
    text = text or ""
    stripped = text.strip()
    if stripped.startswith("[") or stripped.startswith("{"):
        try:
            data = json.loads(stripped)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "wrestlers" in data:
                return data["wrestlers"]
        except json.JSONDecodeError:
            pass

    rows_out: List[Dict[str, Any]] = []
    trs = re.findall(r"<tr[^>]*>(.*?)</tr>", text, flags=re.I | re.S)
    header_map: Dict[int, str] = {}
    for tr in trs:
        cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, flags=re.I | re.S)
        cells = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
        if not cells:
            continue
        lower = [c.lower() for c in cells]
        if any(k in " ".join(lower) for k in ("fall", "tech", "major", "wrestler", "name")):
            for i, c in enumerate(lower):
                for key, field in WIN_TYPE_KEYS.items():
                    if key in c:
                        header_map[i] = field
                if "wrestler" in c or c == "name" or c == "athlete":
                    header_map[i] = "name"
            continue
        if not header_map:
            continue
        item: Dict[str, Any] = {
            "name": None, "pins": 0, "tech_falls": 0,
            "major_decisions": 0, "decisions": 0,
        }
        for i, c in enumerate(cells):
            field = header_map.get(i)
            if not field:
                continue
            if field == "name":
                item["name"] = c
            else:
                try:
                    item[field] = int(re.sub(r"[^\d-]", "", c) or 0)
                except ValueError:
                    item[field] = 0
        if item.get("name"):
            rows_out.append(item)
    if rows_out:
        return rows_out

    for line in text.splitlines():
        line = line.strip()
        if not line or line.lower().startswith(("wrestler", "name")):
            continue
        parts = re.split(r"[\t,;|]+", line)
        if len(parts) < 2:
            continue
        name = parts[0].strip()
        nums = []
        for p in parts[1:]:
            p = p.strip()
            if re.fullmatch(r"-?\d+", p):
                nums.append(int(p))
        if name and nums:
            rows_out.append({
                "name": name,
                "pins": nums[0] if len(nums) > 0 else 0,
                "tech_falls": nums[1] if len(nums) > 1 else 0,
                "major_decisions": nums[2] if len(nums) > 2 else 0,
                "decisions": nums[3] if len(nums) > 3 else 0,
            })
    return rows_out


def merge_win_types_into_roster(
    roster: List[Dict[str, Any]],
    win_types: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    def key(n: str) -> str:
        return re.sub(r"\s+", " ", (n or "").strip().lower())

    by_name = {key(w.get("name") or ""): w for w in win_types}
    out = []
    for w in roster:
        item = dict(w)
        wt = by_name.get(key(w.get("name") or ""))
        if not wt:
            parts = (w.get("name") or "").replace(",", " ").split()
            if len(parts) >= 2:
                wt = by_name.get(key(f"{parts[-1]} {' '.join(parts[:-1])}")) or \
                     by_name.get(key(f"{parts[0]} {parts[-1]}"))
        if wt:
            for f in ("pins", "tech_falls", "major_decisions", "decisions"):
                if wt.get(f) is not None:
                    item[f] = wt[f]
        out.append(item)
    return out


def parse_placements_capture(text: str, meet: str) -> List[Dict[str, Any]]:
    text = text or ""
    stripped = text.strip()
    if stripped.startswith("["):
        try:
            data = json.loads(stripped)
            if isinstance(data, list):
                for row in data:
                    row.setdefault("meet", meet)
                return data
        except json.JSONDecodeError:
            pass

    out: List[Dict[str, Any]] = []
    line_re = re.compile(
        r"^(?P<name>.+?)\s+[—\-|]\s*(?P<weight>\d{3})\s*[—\-|]\s*(?P<place>.+)$",
        re.I,
    )
    champ_re = re.compile(r"champion|1st|first", re.I)
    place_num = re.compile(r"(\d+)")
    for raw in text.splitlines():
        line = re.sub(r"<[^>]+>", "", raw).strip()
        if not line or len(line) < 5:
            continue
        m = line_re.match(line)
        if m:
            place_s = m.group("place")
            pn = place_num.search(place_s)
            place = int(pn.group(1)) if pn else (1 if champ_re.search(place_s) else None)
            out.append({
                "name": m.group("name").strip(" -|"),
                "weight": m.group("weight"),
                "place": place,
                "place_label": place_s.strip(),
                "meet": meet,
            })
            continue
        m2 = re.match(
            r"^(?P<name>[A-Za-z'`.\-]+(?:\s+[A-Za-z'`.\-]+)+)\s+"
            r"(?P<weight>\d{3})\s+"
            r"(?P<place>\d+)(?:st|nd|rd|th)?\b",
            line,
        )
        if m2:
            out.append({
                "name": m2.group("name"),
                "weight": m2.group("weight"),
                "place": int(m2.group("place")),
                "place_label": f"{m2.group('place')}",
                "meet": meet,
            })
    return out


def now_est_iso() -> str:
    try:
        from zoneinfo import ZoneInfo
        t = datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        t = datetime.now()
    s = t.strftime("%Y-%m-%dT%H:%M:%S%z")
    if len(s) >= 5 and s[-5] in "+-" and s[-3] != ":":
        s = s[:-2] + ":" + s[-2:]
    return s
