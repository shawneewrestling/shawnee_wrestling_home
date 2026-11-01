#!/usr/bin/env python3
"""Pull statewide NJSIAA individual postseason advancement (last 5 seasons).

Source: highschoolsports.nj.com public brackets (Districts 1–32, Regions 1–8,
State Championships × 14 weights) for seasons 2021-22 … 2025-26.

Writes data/opponent_advancement.json keyed by athlete_id with linked season
entries, career-best NJSIAA advancement code, and match metadata.

Identity linking (Jeff 2026-11-01):
  (a) same normalized name AND school → merge
  (b) same name, school change, grade advanced exactly one year (Fr→So→Jr→Sr)
  Seniors cannot appear the next season.
  Nicknames / spelling variants / same-surname-different-first → ambiguous
  (not auto-merged); reported in ambiguous_links.
"""
from __future__ import annotations

import json
import re
import sys
import time
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
OUT_PATH = ROOT / "data" / "opponent_advancement.json"
CACHE_DIR = ROOT / "data" / "cache" / "njcom_brackets"

SEASONS = [
    ("2021-2022", "2021-22", 2022),
    ("2022-2023", "2022-23", 2023),
    ("2023-2024", "2023-24", 2024),
    ("2024-2025", "2024-25", 2025),
    ("2025-2026", "2025-26", 2026),
]
SEASON_ORDER = {s[1]: i for i, s in enumerate(SEASONS)}

BASE = "https://highschoolsports.nj.com"
UA = "Mozilla/5.0 (compatible; ShawneeWrestlingBot/1.0; +https://shawneewrestling.com)"

GRADE_ORDER = {"Fr": 0, "So": 1, "Jr": 2, "Sr": 3}
GRADE_NEXT = {"Fr": "So", "So": "Jr", "Jr": "Sr"}  # Sr has no next

CODE_RANK = {
    "S1 Place": 125,
    "S2 Place": 115,
    "S3 Place": 110,
    "S4 Place": 105,
    "S5 Place": 100,
    "S6 Place": 95,
    "S7 Place": 90,
    "S8 Place": 85,
    "swb4": 80,
    "swb3": 75,
    "swb2": 70,
    "swb1": 65,
    "R1place": 64,
    "R2place": 63,
    "R3place": 62,
    "R4place": 61,
    "R5place": 50,
    "R6place": 45,
    "RWB1": 40,
    "2v3 in Regions": 35,
    "D1": 34,
    "D2": 33,
    "D3": 32,
    "D4": 15,
    "Quarters Dis": 10,
    "Prelim Dis": 5,
    "No post-season": 0,
}

WB_ROUND_TO_CODE = {
    "Wrestleback First Round": "swb1",
    "Wrestleback Second Round": "swb2",
    "Wrestleback Third Round": "swb3",
    "Wrestleback Fourth Round": "swb4",
    "Wrestleback Quarterfinal": "swb4",
    "Wrestleback Semifinal": "swb4",
}

REGION_WB_ROUNDS = set(WB_ROUND_TO_CODE.keys())

NICKNAME_PAIRS = {
    frozenset({"william", "bill"}),
    frozenset({"william", "billy"}),
    frozenset({"william", "will"}),
    frozenset({"robert", "bob"}),
    frozenset({"robert", "bobby"}),
    frozenset({"robert", "rob"}),
    frozenset({"richard", "rick"}),
    frozenset({"richard", "rich"}),
    frozenset({"richard", "dick"}),
    frozenset({"james", "jim"}),
    frozenset({"james", "jimmy"}),
    frozenset({"james", "jamie"}),
    frozenset({"john", "jack"}),
    frozenset({"john", "johnny"}),
    frozenset({"joseph", "joe"}),
    frozenset({"joseph", "joey"}),
    frozenset({"michael", "mike"}),
    frozenset({"michael", "mikey"}),
    frozenset({"thomas", "tom"}),
    frozenset({"thomas", "tommy"}),
    frozenset({"anthony", "tony"}),
    frozenset({"andrew", "andy"}),
    frozenset({"alexander", "alex"}),
    frozenset({"nicholas", "nick"}),
    frozenset({"nicholas", "nicky"}),
    frozenset({"christopher", "chris"}),
    frozenset({"matthew", "matt"}),
    frozenset({"benjamin", "ben"}),
    frozenset({"samuel", "sam"}),
    frozenset({"samuel", "sammy"}),
    frozenset({"daniel", "dan"}),
    frozenset({"daniel", "danny"}),
    frozenset({"stephen", "steve"}),
    frozenset({"steven", "steve"}),
    frozenset({"edward", "ed"}),
    frozenset({"edward", "eddie"}),
    frozenset({"charles", "chuck"}),
    frozenset({"charles", "charlie"}),
    frozenset({"patrick", "pat"}),
    frozenset({"timothy", "tim"}),
    frozenset({"timothy", "timmy"}),
    frozenset({"jonathan", "jon"}),
    frozenset({"jonathan", "john"}),
    frozenset({"zachary", "zach"}),
    frozenset({"zachary", "zack"}),
    frozenset({"joshua", "josh"}),
    frozenset({"dominic", "dom"}),
    frozenset({"dominick", "dom"}),
    frozenset({"landan", "landon"}),
    frozenset({"trenton", "trent"}),
}


def name_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def school_key(school: str) -> str:
    s = (school or "").lower()
    s = s.replace("`", "'")
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\b(high school|hs|h s|regional|prep|preparatory school|school|township)\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def split_name(name: str) -> Tuple[str, str]:
    parts = [p for p in re.split(r"\s+", (name or "").strip()) if p]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0].lower(), ""
    return parts[0].lower(), parts[-1].lower()


def schools_match(a: str, b: str) -> bool:
    ka, kb = school_key(a), school_key(b)
    if not ka or not kb:
        return False
    if ka == kb:
        return True
    if ka in kb or kb in ka:
        return True
    # token overlap of significant tokens
    ta = {t for t in ka.split() if len(t) > 2}
    tb = {t for t in kb.split() if len(t) > 2}
    if ta and tb and (ta <= tb or tb <= ta):
        return True
    return False


def better_code(a: Optional[str], b: Optional[str]) -> Optional[str]:
    if not a:
        return b
    if not b:
        return a
    return a if CODE_RANK.get(a, -1) >= CODE_RANK.get(b, -1) else b


def prestige_points_for(code: Optional[str]) -> int:
    if not code:
        return 0
    direct = {
        "S1 Place": 125, "S2 Place": 115, "S3 Place": 110, "S4 Place": 105,
        "S5 Place": 100, "S6 Place": 95, "S7 Place": 90, "S8 Place": 85,
        "swb4": 80, "swb3": 75, "swb2": 70, "swb1": 65,
        "R5place": 50, "R6place": 45, "RWB1": 40, "2v3 in Regions": 35,
        "D4": 15, "Quarters Dis": 10, "Prelim Dis": 5, "No post-season": 0,
    }
    if code in direct:
        return direct[code]
    if code in ("R1place", "R2place", "R3place", "R4place"):
        return 65
    if code in ("D1", "D2", "D3"):
        return 40
    return CODE_RANK.get(code, 0)


def parse_grade(text: str) -> Optional[str]:
    m = re.search(r"\b(Fr|So|Jr|Sr)\b", text or "", re.I)
    if not m:
        return None
    g = m.group(1).title()
    if g == "Fr":
        return "Fr"
    return g


class Fetcher:
    def __init__(self) -> None:
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept": "text/html"})
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def get(self, url: str, retries: int = 3) -> str:
        rel = url.split(".com", 1)[-1].strip("/")
        cache_path = CACHE_DIR / (rel.replace("/", "__") + ".html")
        if cache_path.exists() and cache_path.stat().st_size > 1000:
            return cache_path.read_text(errors="ignore")
        last_err = None
        for attempt in range(retries):
            try:
                r = self.s.get(url, timeout=60)
                if r.status_code == 200 and len(r.text) > 1000:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_text(r.text)
                    return r.text
                last_err = f"status {r.status_code} len {len(r.text)}"
            except Exception as e:
                last_err = str(e)
            time.sleep(0.35 * (attempt + 1))
        raise RuntimeError(f"fetch failed {url}: {last_err}")


def parse_season_index(html: str, season_path: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    out: List[Dict[str, Any]] = []
    seen = set()
    pat = re.compile(rf"/wrestling/brackets/season/{re.escape(season_path)}/(\d+)$")
    title_pat = re.compile(
        r"(\d{4}) NJSIAA (District (\d+)|Region (\d+)|State Wrestling Championships) - (\d+)"
    )
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = pat.search(href)
        if not m:
            continue
        t = a.get_text(" ", strip=True)
        tm = title_pat.match(t)
        if not tm:
            continue
        bracket_id = m.group(1)
        if bracket_id in seen:
            continue
        seen.add(bracket_id)
        weight = int(tm.group(5))
        if tm.group(3):
            level, num = "district", int(tm.group(3))
        elif tm.group(4):
            level, num = "region", int(tm.group(4))
        else:
            level, num = "state", None
        out.append(
            {
                "level": level,
                "number": num,
                "weight": weight,
                "bracket_id": bracket_id,
                "url": urljoin(BASE, href),
                "title": t,
            }
        )
    return out


def _player_from_row(tr) -> Optional[Dict[str, Any]]:
    name_el = tr.select_one(".bracket-player-name")
    if not name_el:
        return None
    name = name_el.get_text(" ", strip=True)
    if not name or name.upper() == "BYE":
        return None
    school = ""
    grade = None
    col = tr.select_one(".col.d-flex, .col.d-flex.align-items-center")
    if col:
        for sm in col.find_all("small"):
            txt = sm.get_text(" ", strip=True).replace("•", " ").strip()
            if not txt:
                continue
            g = parse_grade(txt)
            if g and re.fullmatch(r"(Fr|So|Jr|Sr)\.?", txt.replace("•", "").strip(), re.I):
                grade = g
                continue
            if g and len(txt) <= 4:
                grade = g
                continue
            if re.match(r"^\d+$", txt):
                continue
            # school text may include "• Sr." already stripped
            cleaned = re.sub(r"\b(Fr|So|Jr|Sr)\.?$", "", txt, flags=re.I).strip(" •")
            if cleaned and not school:
                school = cleaned
            g2 = parse_grade(txt)
            if g2:
                grade = g2
    if not school:
        img = tr.select_one("img.bracket-team-logo")
        if img and img.get("alt"):
            school = img["alt"].strip()
    # final grade pass on full row text
    if not grade:
        grade = parse_grade(tr.get_text(" ", strip=True))
    return {"name": name, "school": school, "grade": grade}


def parse_bracket(html: str, meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    level = meta["level"]
    best: Dict[str, Dict[str, Any]] = {}

    def note(name: str, school: str, grade: Optional[str], code: str, detail: str) -> None:
        if not name:
            return
        # key within bracket: name+school (grade may be missing on some rows)
        k = f"{name_key(name)}|{school_key(school)}"
        prev = best.get(k)
        if prev and CODE_RANK.get(prev["code"], -1) >= CODE_RANK.get(code, -1):
            if grade and not prev.get("grade"):
                prev["grade"] = grade
            return
        best[k] = {
            "name": name,
            "school": school,
            "grade": grade or (prev.get("grade") if prev else None),
            "code": code,
            "detail": detail,
            "weight": meta["weight"],
            "event": meta["title"],
            "level": level,
            "event_number": meta.get("number"),
            "url": meta["url"],
            "bracket_id": meta.get("bracket_id"),
        }

    def process_place_match(match_el, winner_code: str, loser_code: str, label: str) -> None:
        rows = match_el.select("tr[data-bracket-entry]")
        players = []
        winners = []
        for tr in rows:
            p = _player_from_row(tr)
            if not p:
                continue
            players.append(p)
            if "game-winner" in (tr.get("class") or []):
                winners.append(p)
        if len(players) == 1:
            if winners:
                note(players[0]["name"], players[0]["school"], players[0].get("grade"),
                     winner_code, label + " (winner)")
            return
        if len(players) >= 2 and winners:
            w = winners[0]
            note(w["name"], w["school"], w.get("grade"), winner_code, label + " winner")
            for p in players:
                if p["name"] != w["name"] or school_key(p["school"]) != school_key(w["school"]):
                    note(p["name"], p["school"], p.get("grade"), loser_code, label + " loser")

    def iter_matches(bracket_id: str):
        block = soup.find(id=bracket_id)
        if not block:
            return
        for round_el in block.select(".tournament-bracket__round"):
            title_el = round_el.select_one(".tournament-bracket__round-title")
            title = title_el.get_text(strip=True) if title_el else ""
            for match in round_el.select(".tournament-bracket__match"):
                yield title, match

    if level == "state":
        place_map = {
            "Final Round": ("S1 Place", "S2 Place"),
            "Third Place": ("S3 Place", "S4 Place"),
            "Fifth Place": ("S5 Place", "S6 Place"),
            "Seventh Place": ("S7 Place", "S8 Place"),
        }
    elif level == "region":
        place_map = {
            "Final Round": ("R1place", "R2place"),
            "Third Place": ("R3place", "R4place"),
            "Fifth Place": ("R5place", "R6place"),
        }
    else:
        place_map = {
            "Final Round": ("D1", "D2"),
            "Third Place": ("D3", "D4"),
        }

    for bracket_id in ("champBracket", "consBracket"):
        for title, match in iter_matches(bracket_id):
            if title in place_map:
                w_code, l_code = place_map[title]
                process_place_match(match, w_code, l_code, title)

    appearances: Dict[str, Dict[str, Any]] = {}

    def seen_in(name: str, school: str, grade: Optional[str], round_title: str) -> None:
        k = f"{name_key(name)}|{school_key(school)}"
        rec = appearances.setdefault(
            k, {"name": name, "school": school, "grade": grade, "rounds": set()}
        )
        if grade and not rec.get("grade"):
            rec["grade"] = grade
        rec["rounds"].add(round_title)

    for bracket_id in ("champBracket", "consBracket"):
        for title, match in iter_matches(bracket_id):
            for tr in match.select("tr[data-bracket-entry]"):
                p = _player_from_row(tr)
                if p:
                    seen_in(p["name"], p["school"], p.get("grade"), title)

    for k, rec in appearances.items():
        if k in best:
            if rec.get("grade") and not best[k].get("grade"):
                best[k]["grade"] = rec["grade"]
            continue
        name, school, grade = rec["name"], rec["school"], rec.get("grade")
        rounds = rec["rounds"]
        if level == "state":
            wb_code = None
            for rt, code in WB_ROUND_TO_CODE.items():
                if rt in rounds:
                    wb_code = better_code(wb_code, code)
            if wb_code:
                note(name, school, grade, wb_code, "state wrestleback")
            elif rounds & {
                "Preliminary Round", "Pre-Quarterfinal Round",
                "Quarterfinal Round", "Semifinal Round",
            }:
                note(name, school, grade, "swb1", "state champ-bracket exit")
        elif level == "region":
            if rounds & REGION_WB_ROUNDS:
                note(name, school, grade, "RWB1", "region wrestleback")
            elif "Semifinal Round" in rounds:
                note(name, school, grade, "2v3 in Regions", "region semi without place")
            elif "Quarterfinal Round" in rounds:
                note(name, school, grade, "2v3 in Regions", "region quarterfinal exit")
            elif "First Round" in rounds:
                note(name, school, grade, "2v3 in Regions", "region first-round exit")
        else:
            if "Quarterfinal Round" in rounds or "Semifinal Round" in rounds:
                note(name, school, grade, "Quarters Dis", "district quarterfinal/semi exit")
            elif rounds & {"First Round", "Preliminary Round", "Prelim Round"}:
                note(name, school, grade, "Prelim Dis", "district prelim/first-round exit")

    return list(best.values())


# ----- Identity linking -----

def _nickname_match(first_a: str, first_b: str) -> bool:
    a, b = first_a.lower(), first_b.lower()
    if a == b:
        return True
    return frozenset({a, b}) in NICKNAME_PAIRS


def _spelling_variant(a: str, b: str) -> bool:
    """True if names look like spelling variants (edit distance small)."""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 2:
        return False
    # simple levenshtein capped
    if len(a) < 3 or len(b) < 3:
        return a == b
    la, lb = len(a), len(b)
    prev = list(range(lb + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    dist = prev[-1]
    return dist <= 1 or (dist == 2 and min(la, lb) >= 6)


def link_athletes(raw_entries: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, int]]:
    """Group raw season finishes into athletes.

    Returns (athletes_by_id, ambiguous_links, stats).
    """
    # First collapse to one finish per (name, school, season) keeping best code,
    # but retain grade/weight/event list.
    season_person: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    # key: (name_key, school_key, season)

    for e in raw_entries:
        nk = name_key(e["name"])
        sk = school_key(e["school"])
        season = e["season"]
        key = (nk, sk, season)
        fin = {
            "code": e["code"],
            "level": e["level"],
            "weight": e["weight"],
            "event": e["event"],
            "detail": e["detail"],
            "event_number": e.get("event_number"),
            "url": e.get("url"),
            "grade": e.get("grade"),
            "name": e["name"],
            "school": e["school"],
        }
        prev = season_person.get(key)
        if not prev:
            season_person[key] = {
                "name": e["name"],
                "school": e["school"],
                "name_key": nk,
                "school_key": sk,
                "season": season,
                "grade": e.get("grade"),
                "best": fin,
                "entries": [fin],
            }
            continue
        if e.get("grade") and not prev.get("grade"):
            prev["grade"] = e["grade"]
        prev["entries"].append(fin)
        if CODE_RANK.get(e["code"], -1) > CODE_RANK.get(prev["best"]["code"], -1):
            prev["best"] = fin

    # Build nodes: one per (name_key, school_key) cluster seed — actually one node
    # per season_person row, then union-find across seasons.
    nodes = list(season_person.values())
    parent = list(range(len(nodes)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    ambiguous: List[Dict[str, Any]] = []
    link_reasons: Dict[Tuple[int, int], Dict[str, Any]] = {}

    # Index by name_key and by surname
    by_name: Dict[str, List[int]] = defaultdict(list)
    by_surname: Dict[str, List[int]] = defaultdict(list)
    for i, n in enumerate(nodes):
        by_name[n["name_key"]].append(i)
        first, last = split_name(n["name"])
        if last:
            by_surname[last].append(i)

    def seasons_adjacent(a: str, b: str) -> bool:
        return abs(SEASON_ORDER.get(a, -99) - SEASON_ORDER.get(b, -99)) == 1

    def grade_advances(earlier_grade: Optional[str], later_grade: Optional[str],
                       earlier_season: str, later_season: str) -> bool:
        if not earlier_grade or not later_grade:
            return False
        if earlier_grade == "Sr":
            return False  # seniors cannot appear next season
        if not seasons_adjacent(earlier_season, later_season):
            # allow multi-year gap only if grade delta matches season delta
            da = SEASON_ORDER.get(later_season, 0) - SEASON_ORDER.get(earlier_season, 0)
            if da <= 0:
                return False
            eg = GRADE_ORDER.get(earlier_grade)
            lg = GRADE_ORDER.get(later_grade)
            if eg is None or lg is None:
                return False
            return lg - eg == da and lg <= 3
        return GRADE_NEXT.get(earlier_grade) == later_grade

    # Pass 1: exact name+school across seasons
    for nk, idxs in by_name.items():
        for a in range(len(idxs)):
            for b in range(a + 1, len(idxs)):
                i, j = idxs[a], idxs[b]
                ni, nj = nodes[i], nodes[j]
                if ni["season"] == nj["season"]:
                    continue
                if not schools_match(ni["school"], nj["school"]):
                    continue
                # Senior guard: if earlier is Sr, cannot link to later season
                early, late = (ni, nj) if SEASON_ORDER[ni["season"]] < SEASON_ORDER[nj["season"]] else (nj, ni)
                if early.get("grade") == "Sr":
                    ambiguous.append({
                        "type": "senior_reappearance",
                        "a": {"name": early["name"], "school": early["school"],
                              "season": early["season"], "grade": early.get("grade")},
                        "b": {"name": late["name"], "school": late["school"],
                              "season": late["season"], "grade": late.get("grade")},
                        "reason": "same name+school but earlier entry is Sr",
                    })
                    continue
                union(i, j)
                link_reasons[(min(find(i), find(j)), max(i, j))] = {
                    "match_reason": "name_and_school",
                    "confidence": "high",
                }

    # Pass 2: same name, school change, grade +1
    for nk, idxs in by_name.items():
        for a in range(len(idxs)):
            for b in range(a + 1, len(idxs)):
                i, j = idxs[a], idxs[b]
                if find(i) == find(j):
                    continue
                ni, nj = nodes[i], nodes[j]
                if ni["season"] == nj["season"]:
                    continue
                if schools_match(ni["school"], nj["school"]):
                    continue  # already handled (or senior flag)
                early, late = (ni, nj) if SEASON_ORDER[ni["season"]] < SEASON_ORDER[nj["season"]] else (nj, ni)
                ei, ej = (i, j) if early is ni else (j, i)
                if early.get("grade") == "Sr":
                    continue
                if grade_advances(early.get("grade"), late.get("grade"),
                                  early["season"], late["season"]):
                    union(ei, ej)
                    link_reasons[(min(find(ei), find(ej)), max(ei, ej))] = {
                        "match_reason": "name_school_change_grade_plus_one",
                        "confidence": "high",
                        "from_school": early["school"],
                        "to_school": late["school"],
                        "grades": f"{early.get('grade')}→{late.get('grade')}",
                    }

    # Pass 3: flag ambiguous similar names (do NOT merge)
    seen_amb = set()
    for last, idxs in by_surname.items():
        if len(idxs) < 2:
            continue
        for a in range(len(idxs)):
            for b in range(a + 1, len(idxs)):
                i, j = idxs[a], idxs[b]
                if find(i) == find(j):
                    continue
                ni, nj = nodes[i], nodes[j]
                fi, li = split_name(ni["name"])
                fj, lj = split_name(nj["name"])
                if li != lj:
                    continue
                # same full name already considered
                if ni["name_key"] == nj["name_key"]:
                    # same name, different school, grade didn't qualify — ambiguous transfer?
                    if ni["season"] != nj["season"] and not schools_match(ni["school"], nj["school"]):
                        amb_key = tuple(sorted([ni["name_key"] + ni["school_key"] + ni["season"],
                                                nj["name_key"] + nj["school_key"] + nj["season"]]))
                        if amb_key not in seen_amb:
                            seen_amb.add(amb_key)
                            ambiguous.append({
                                "type": "same_name_school_change_no_grade_link",
                                "a": {"name": ni["name"], "school": ni["school"],
                                      "season": ni["season"], "grade": ni.get("grade")},
                                "b": {"name": nj["name"], "school": nj["school"],
                                      "season": nj["season"], "grade": nj.get("grade")},
                                "reason": "same name, different school; grade progression not confirmed",
                            })
                    continue
                # nickname or spelling variant on first name, same surname
                is_nick = _nickname_match(fi, fj)
                is_spell = _spelling_variant(fi, fj)
                is_diff_first = fi != fj and not is_nick and not is_spell
                if is_nick or is_spell or (is_diff_first and schools_match(ni["school"], nj["school"])):
                    amb_key = tuple(sorted([ni["name_key"] + ni["season"], nj["name_key"] + nj["season"]]))
                    if amb_key in seen_amb:
                        continue
                    seen_amb.add(amb_key)
                    if is_nick:
                        atype, reason = "nickname_variant", f"nickname pair {fi}/{fj}"
                    elif is_spell:
                        atype, reason = "spelling_variant", f"spelling variant {fi}/{fj}"
                    else:
                        atype, reason = "same_surname_different_first", f"same school+surname, different first ({fi}/{fj})"
                    ambiguous.append({
                        "type": atype,
                        "a": {"name": ni["name"], "school": ni["school"],
                              "season": ni["season"], "grade": ni.get("grade")},
                        "b": {"name": nj["name"], "school": nj["school"],
                              "season": nj["season"], "grade": nj.get("grade")},
                        "reason": reason,
                    })

    # Build athlete records
    groups: Dict[int, List[int]] = defaultdict(list)
    for i in range(len(nodes)):
        groups[find(i)].append(i)

    athletes: Dict[str, Any] = {}
    for root, members in groups.items():
        member_nodes = [nodes[i] for i in members]
        # stable athlete_id from earliest name_key + school_key + first season
        member_nodes.sort(key=lambda n: SEASON_ORDER.get(n["season"], 99))
        seed = member_nodes[0]
        aid = "ath_" + name_key(seed["name"])[:20] + "_" + school_key(seed["school"]).replace(" ", "")[:16]
        # ensure uniqueness
        base_aid = aid
        n = 2
        while aid in athletes:
            aid = f"{base_aid}_{n}"
            n += 1

        seasons_out: Dict[str, Any] = {}
        names_seen = []
        schools_seen = []
        for n in member_nodes:
            names_seen.append(n["name"])
            schools_seen.append(n["school"])
            best = n["best"]
            seasons_out[n["season"]] = {
                "code": best["code"],
                "level": best["level"],
                "weight": best["weight"],
                "event": best["event"],
                "detail": best["detail"],
                "grade": n.get("grade") or best.get("grade"),
                "name": n["name"],
                "school": n["school"],
                "url": best.get("url"),
                "event_number": best.get("event_number"),
                "entries": [
                    {
                        "code": e["code"],
                        "level": e["level"],
                        "weight": e["weight"],
                        "event": e["event"],
                        "detail": e["detail"],
                        "grade": e.get("grade"),
                    }
                    for e in n["entries"]
                ],
            }

        # career best
        best_code = None
        best_season = None
        for season, fin in seasons_out.items():
            for e in fin.get("entries") or [fin]:
                c = e["code"]
                if best_code is None or CODE_RANK.get(c, -1) > CODE_RANK.get(best_code, -1):
                    best_code = c
                    best_season = season

        # match metadata
        if len(member_nodes) == 1:
            match_reason, confidence = "single_season", "high"
        elif all(schools_match(member_nodes[0]["school"], m["school"]) for m in member_nodes):
            match_reason, confidence = "name_and_school", "high"
        else:
            match_reason, confidence = "name_school_change_grade_plus_one", "high"

        athletes[aid] = {
            "athlete_id": aid,
            "name": seed["name"],
            "school": seed["school"],
            "name_key": seed["name_key"],
            "school_key": seed["school_key"],
            "names": sorted(set(names_seen)),
            "schools": sorted(set(schools_seen)),
            "match_reason": match_reason,
            "confidence": confidence,
            "seasons": seasons_out,
            "career_best": best_code,
            "career_best_season": best_season,
            "career_best_rank": CODE_RANK.get(best_code or "", 0),
            "career_best_prestige_points": prestige_points_for(best_code),
        }

    # Also build a flat lookup by name|school for convenience (points at athlete_id)
    index: Dict[str, str] = {}
    for aid, ath in athletes.items():
        for season, fin in ath["seasons"].items():
            k = f"{name_key(fin['name'])}|{school_key(fin['school'])}"
            index[k] = aid
        k0 = f"{ath['name_key']}|{ath['school_key']}"
        index[k0] = aid

    stats = {
        "season_person_rows": len(nodes),
        "athletes": len(athletes),
        "ambiguous_links": len(ambiguous),
        "ambiguous_by_type": dict(defaultdict(int)),
    }
    by_type: Dict[str, int] = defaultdict(int)
    for a in ambiguous:
        by_type[a["type"]] += 1
    stats["ambiguous_by_type"] = dict(by_type)
    stats["linked_multi_season"] = sum(1 for a in athletes.values() if len(a["seasons"]) > 1)
    stats["school_change_links"] = sum(
        1 for a in athletes.values() if a["match_reason"] == "name_school_change_grade_plus_one"
    )

    return {"athletes": athletes, "index": index}, ambiguous, stats


def validate(athletes: Dict[str, Any], index: Dict[str, str]) -> List[Dict[str, Any]]:
    cases = [
        ("Sammy Spaulding", "Camden Catholic", "S1 Place"),
        ("Giovanni Schinina", "St Peters Prep", "S4 Place"),
        ("Joseph Rizzuto", "DePaul", "S6 Place"),
        ("Dominic Marino", "Cinnaminson", "swb1"),
        ("Landan Riddell", "Immaculata", "swb4"),
        ("Rocco Giangeruso", "Northern Burlington", "R6place"),
        ("Louis Simone", "Rancocas Valley", "RWB1"),
        ("Trenton Landell", "Cherokee", "D4"),
    ]
    by_name: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for ath in athletes.values():
        by_name[ath["name_key"]].append(ath)
        for n in ath.get("names") or []:
            by_name[name_key(n)].append(ath)

    results = []
    for name, school, expected in cases:
        nk = name_key(name)
        sk = school_key(school)
        candidates = by_name.get(nk, [])
        # dedupe by athlete_id
        seen = set()
        uniq = []
        for c in candidates:
            if c["athlete_id"] in seen:
                continue
            seen.add(c["athlete_id"])
            uniq.append(c)
        match = None
        for c in uniq:
            if any(schools_match(school, s) for s in c.get("schools") or [c["school"]]):
                match = c
                break
        if not match and len(uniq) == 1:
            match = uniq[0]
        got = match["career_best"] if match else None
        seasons = {s: fin["code"] for s, fin in match["seasons"].items()} if match else {}
        all_codes = []
        if match:
            for fin in match["seasons"].values():
                all_codes.append(fin["code"])
                for e in fin.get("entries") or []:
                    all_codes.append(e["code"])
        ok = got == expected or expected in all_codes
        if got == expected:
            note = "ok"
        elif expected in all_codes:
            note = "expected present in a season; career_best may be higher"
        elif not match:
            note = "not found"
        else:
            note = "mismatch"
        results.append({
            "name": name,
            "school": school,
            "expected": expected,
            "got_career_best": got,
            "athlete_id": match["athlete_id"] if match else None,
            "schools_found": match.get("schools") if match else None,
            "seasons": seasons,
            "ok": ok,
            "note": note,
        })
    return results


def pull_all(max_workers: int = 12, season_filter: Optional[str] = None) -> Dict[str, Any]:
    fetcher = Fetcher()
    raw_entries: List[Dict[str, Any]] = []
    coverage: Dict[str, Any] = {}
    errors: List[Dict[str, str]] = []

    for season_path, season_label, year in SEASONS:
        if season_filter and season_label != season_filter and season_path != season_filter:
            continue
        print(f"\n=== Season {season_label} ({season_path}) ===", flush=True)
        index_url = f"{BASE}/wrestling/brackets/season/{season_path}"
        index_html = fetcher.get(index_url)
        brackets = parse_season_index(index_html, season_path)
        print(f"  brackets listed: {len(brackets)}", flush=True)
        by_level: Dict[str, int] = defaultdict(int)
        for b in brackets:
            by_level[b["level"]] += 1
        print(f"  by level: {dict(by_level)}", flush=True)

        season_rows: List[Dict[str, Any]] = []
        done = 0

        def job(meta: Dict[str, Any]):
            try:
                html = fetcher.get(meta["url"])
                parsed = parse_bracket(html, meta)
                return meta, parsed, None
            except Exception as e:
                return meta, [], str(e)

        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = [ex.submit(job, b) for b in brackets]
            for fut in as_completed(futs):
                meta, parsed, err = fut.result()
                done += 1
                if err:
                    errors.append({"url": meta["url"], "error": err, "season": season_label})
                else:
                    for p in parsed:
                        p["season"] = season_label
                        season_rows.append(p)
                        raw_entries.append(p)
                if done % 100 == 0 or done == len(brackets):
                    print(f"  fetched {done}/{len(brackets)} (rows {len(season_rows)})", flush=True)

        codes: Dict[str, int] = defaultdict(int)
        levels_hit: Dict[str, set] = defaultdict(set)
        for r in season_rows:
            codes[r["code"]] += 1
            levels_hit[r["level"]].add(r.get("event_number"))
        coverage[season_label] = {
            "brackets": len(brackets),
            "brackets_by_level": dict(by_level),
            "wrestler_finishes": len(season_rows),
            "unique_name_school": len({f"{name_key(r['name'])}|{school_key(r['school'])}" for r in season_rows}),
            "with_grade": sum(1 for r in season_rows if r.get("grade")),
            "codes": dict(sorted(codes.items(), key=lambda kv: -CODE_RANK.get(kv[0], 0))),
            "districts_with_results": sorted(x for x in levels_hit["district"] if x is not None),
            "regions_with_results": sorted(x for x in levels_hit["region"] if x is not None),
            "state_weights": sorted({r["weight"] for r in season_rows if r["level"] == "state"}),
        }

    print("\nLinking athletes…", flush=True)
    linked, ambiguous, link_stats = link_athletes(raw_entries)
    athletes = linked["athletes"]
    index = linked["index"]
    validation = validate(athletes, index)

    # Convenience alias map: composite name|school → career_best (for weekly scorer)
    by_name_school: Dict[str, Any] = {}
    for aid, ath in athletes.items():
        for season, fin in ath["seasons"].items():
            k = f"{name_key(fin['name'])}|{school_key(fin['school'])}"
            by_name_school[k] = {
                "athlete_id": aid,
                "name": fin["name"],
                "school": fin["school"],
                "career_best": ath["career_best"],
                "career_best_prestige_points": ath["career_best_prestige_points"],
                "career_best_season": ath["career_best_season"],
            }

    payload = {
        "schema_version": 2,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source": {
            "name": "NJ.com High School Sports wrestling brackets",
            "base": BASE,
            "seasons": [s[1] for s in SEASONS],
            "method": "public HTML brackets (champ + consolation)",
            "identity_rules": [
                "name_and_school match → merge",
                "name match + school change + grade exactly +1 year → merge",
                "Sr cannot appear in a later season",
                "nicknames/spelling variants/same-surname-diff-first → ambiguous (not merged)",
            ],
        },
        "code_rank": CODE_RANK,
        "coverage": coverage,
        "link_stats": link_stats,
        "validation": validation,
        "errors": errors,
        "ambiguous_links": ambiguous,
        "athletes": athletes,
        "index": index,
        "by_name_school": by_name_school,
        "count": len(athletes),
        "raw_entry_count": len(raw_entries),
    }
    return payload


def main(argv: List[str]) -> int:
    season_filter = None
    workers = 12
    args = list(argv)
    if "--season" in args:
        i = args.index("--season")
        season_filter = args[i + 1]
        del args[i : i + 2]
    if "--workers" in args:
        i = args.index("--workers")
        workers = int(args[i + 1])
        del args[i : i + 2]

    payload = pull_all(max_workers=workers, season_filter=season_filter)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")
    print(f"\nWrote {OUT_PATH} ({payload['count']} athletes, "
          f"{payload['raw_entry_count']} raw finishes)", flush=True)
    print("Validation:", flush=True)
    for v in payload["validation"]:
        status = "PASS" if v["ok"] else "FAIL"
        print(
            f"  [{status}] {v['name']} ({v['school']}): expected {v['expected']}, "
            f"got {v['got_career_best']} seasons={v['seasons']} ({v['note']})",
            flush=True,
        )
    print("Coverage:", flush=True)
    for season, cov in payload["coverage"].items():
        print(
            f"  {season}: {cov['brackets']} brackets, {cov['unique_name_school']} name+school, "
            f"grade={cov['with_grade']}, districts={len(cov['districts_with_results'])}, "
            f"regions={len(cov['regions_with_results'])}, state_wt={cov['state_weights']}",
            flush=True,
        )
    ls = payload["link_stats"]
    print(
        f"Link stats: athletes={ls['athletes']} multi_season={ls['linked_multi_season']} "
        f"school_changes={ls['school_change_links']} ambiguous={ls['ambiguous_links']} "
        f"by_type={ls['ambiguous_by_type']}",
        flush=True,
    )
    if payload["errors"]:
        print(f"Fetch errors: {len(payload['errors'])}", flush=True)
        for e in payload["errors"][:15]:
            print(" ", e, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
