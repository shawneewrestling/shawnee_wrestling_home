#!/usr/bin/env python3
"""NJSIAA District Pre-Seed caliber points (current-season competition).

Official rules (NJSIAA 2025-26 Boys Individual regs + Jeff steering 2026-11-01):
  (1) Replacement wrestlers get advancement credit without winning (prestige side;
      opponent lookup must honor replacement finishes in opponent_advancement).
  (2) Caliber counts only the best 20 matches.
  (3) Win vs a non-NJSIAA member = 2 pts (regardless of out-of-state caliber).
  (4) +1 pin point only for a fall — not MD / TF / DQ / FF.
  (5) Forfeit win = 2 pts with no pin point.
  (6) −1 per loss to a non-regional competitor from a previous tournament;
      chart: decision loss vs Quarters Dis / Prelim Dis / Never = −1
      (D4 decision loss = 0; higher tiers = 20% of caliber).
  (7) District chart applies to out-of-state opponents (when they are treated as
      chart-mapped; non-member wins still capped at 2 by rule 3).
  (8) Per-match points must be shown on the individual match record.

Scoring:
  win  -> opponent caliber (+1 if fall), except forfeit/non-member -> 2
  loss by decision -> 20% caliber (or chart −1 / 0 for low tiers)
  other losses -> 0
  bye -> not a match (0, excluded from top-20 pool)

Total pre-seed = own prestige + sum(best 20 match points).

Opponent advancement for a form in season S uses ONLY the prior 3 seasons
(`prior_seasons_for(S)`), never S itself — current-season postseason finishes
are not available when the pre-seed is computed.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent

# Chart: advancement code -> (prestige, caliber, decision_loss_pts)
# decision_loss uses explicit chart values (not always 0.2 * caliber at the bottom).
CHART: Dict[str, Tuple[float, float, float]] = {
    "S1 Place": (125, 62.5, 12.5),
    "S2 Place": (115, 57.5, 11.5),
    "S3 Place": (110, 55.0, 11.0),
    "S4 Place": (105, 52.5, 10.5),
    "S5 Place": (100, 50.0, 10.0),
    "S6 Place": (95, 47.5, 9.5),
    "S7 Place": (90, 45.0, 9.0),
    "S8 Place": (85, 42.5, 8.5),
    "swb4": (80, 40.0, 8.0),
    "swb3": (75, 37.5, 7.5),
    "swb2": (70, 35.0, 7.0),
    "swb1": (65, 32.5, 6.5),
    "R5place": (50, 25.0, 5.0),
    "R6place": (45, 22.5, 4.5),
    "RWB1": (40, 20.0, 4.0),
    "2v3 in Regions": (35, 17.5, 3.5),
    "D4": (15, 7.5, 0.0),
    "Quarters Dis": (10, 5.0, -1.0),
    "Prelim Dis": (5, 2.5, -1.0),
    "No post-season": (0, 2.0, -1.0),
    # Qualifier floors when only D1–D3 / R1–R4 are known (no deeper row)
    "R1place": (65, 32.5, 6.5),
    "R2place": (65, 32.5, 6.5),
    "R3place": (65, 32.5, 6.5),
    "R4place": (65, 32.5, 6.5),
    "D1": (40, 20.0, 4.0),
    "D2": (40, 20.0, 4.0),
    "D3": (40, 20.0, 4.0),
}

# Codes at or below "non-regional" for rule (6) commentary (chart −1 on decision loss)
NON_REGIONAL_CODES = {"Quarters Dis", "Prelim Dis", "No post-season"}

# Known non-NJSIAA member schools (out-of-state / non-members). Expand as needed.
# Rule (3): win vs these = 2 pts. Chart still usable for losses (rule 7).
NON_NJSIAA_SCHOOL_KEYS = {
    # PA
    "manheimtwp", "manheimtownship", "eastonarea", "easton", "bethlehemcatholic",
    "bethlehemcath", "councilrocknorth", "councilrocksouth", "councilrock",
    "downingtownwest", "downingtowneast", "downingtown", "springfielddelco",
    "neshaminy", "pennsbury", "centralbucks", "northpenn",
    # NY
    "valleycentralsr", "valleycentral", "minisinkvalley", "monroewoodbury",
    "warwickvalley", "kingston",
    # NJ independents / non-NJSIAA members commonly on TW
    "peddie", "thepeddie", "peddieschool", "blairacademy",
}

# Win-type tokens
FALL_TYPES = {"fall", "pin", "p"}
FORFEIT_TYPES = {"forfeit", "ff", "m. for.", "m for", "m.for.", "medical forfeit", "m forfeit"}
DECISION_LOSS_TYPES = {
    "decision", "dec", "dec.", "sudden victory", "sv", "sv-1", "sv-2",
    "tie breaker", "tb", "tb-1", "tb-2", "ultimate tie breaker", "utb",
}
# MD/TF/DQ are NOT pin-eligible and decision-loss scoring does not apply to MD/TF losses
MAJOR_OR_TECH = {"maj. dec.", "major", "major decision", "md", "tech. fall", "tech fall", "tf", "tech"}


def name_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def school_key(school: str) -> str:
    s = (school or "").lower()
    s = s.replace("`", "'")
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\b(high school|hs|h s|regional|prep|preparatory school|school)\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def school_key_compact(school: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", school_key(school))


def is_non_njsiaa_member(team: Optional[str]) -> bool:
    if not team:
        return False
    compact = school_key_compact(team)
    if compact in NON_NJSIAA_SCHOOL_KEYS:
        return True
    # heuristic: explicit out-of-state markers in team string
    low = (team or "").lower()
    if any(x in low for x in ("(pa)", "(ny)", "(md)", "(de)", " pa", " ny", "hs pa")):
        return True
    return False


def normalize_win_type(win_type: Optional[str], score: Optional[str] = None) -> str:
    raw = f"{win_type or ''} {score or ''}".lower().strip()
    if "bye" in raw:
        return "bye"
    if any(t in raw for t in ("forfeit", "m. for", "m for", "inj")) and "inj" in raw and "fall" not in raw:
        # Injury default / medical forfeit — treat as forfeit family for pin rule
        if "forfeit" in raw or "m. for" in raw or "m for" in raw:
            return "forfeit"
    if "forfeit" in raw or re.search(r"\bff\b", raw) or "m. for" in raw:
        return "forfeit"
    if "fall" in raw or re.search(r"\bpin\b", raw):
        # careful: "TF Fall" mislabel — prefer tech if tech present
        if "tech" in raw or re.search(r"\btf\b", raw):
            return "tech"
        return "fall"
    if "tech" in raw or re.search(r"\btf\b", raw):
        return "tech"
    if "maj" in raw or re.search(r"\bmd\b", raw):
        return "major"
    if "dq" in raw or "disqual" in raw:
        return "dq"
    if "dec" in raw or "sv" in raw or "tb" in raw or "utb" in raw:
        return "decision"
    return (win_type or "unknown").lower()


def chart_row_for_code(code: Optional[str]) -> Tuple[float, float, float]:
    """Return (prestige, caliber, decision_loss). Default = Never in Districts."""
    if not code:
        return CHART["No post-season"]
    if code in CHART:
        return CHART[code]
    return CHART["No post-season"]


@dataclass
class MatchScore:
    opponent: str
    opponent_team: str
    result: str  # W/L
    win_type: str
    adv_code: Optional[str]
    caliber: float
    pin_point: float
    match_points: float
    rules_applied: List[str]
    in_top20: bool = False
    non_member: bool = False
    notes: str = ""


def score_match(
    *,
    result: str,
    win_type_raw: Optional[str],
    score: Optional[str],
    opponent: Optional[str],
    opponent_team: Optional[str],
    adv_code: Optional[str],
    non_member: Optional[bool] = None,
) -> Optional[MatchScore]:
    """Score one bout. Returns None for byes (not matches)."""
    wt = normalize_win_type(win_type_raw, score)
    if wt == "bye" or (result == "W" and not opponent and "bye" in (score or "").lower()):
        return None

    rules: List[str] = []
    nm = is_non_njsiaa_member(opponent_team) if non_member is None else non_member
    prestige, caliber, dec_loss = chart_row_for_code(adv_code)
    if not adv_code:
        rules.append("default No post-season (unknown opponent advancement)")
        adv_code = "No post-season"

    pin = 0.0
    pts = 0.0
    notes = ""

    if result == "W":
        if wt == "forfeit":
            pts = 2.0
            pin = 0.0
            rules.append("(5) forfeit win = 2, no pin point")
        elif nm:
            pts = 2.0
            pin = 0.0
            rules.append("(3) win vs non-NJSIAA member = 2")
            if wt == "fall":
                # regs: pin point when match ends in fall — but member rule caps win at 2?
                # Jeff/regs: "Any win against a non-NJSIAA member will earn two (2) points"
                # does not say +1 pin on top; keep at 2 flat.
                rules.append("(3) overrides pin add-on for non-member (flat 2)")
        else:
            pts = caliber
            rules.append("win = opponent caliber")
            if wt == "fall":
                pin = 1.0
                pts += 1.0
                rules.append("(4) +1 pin point for fall")
            elif wt in ("tech", "major", "dq", "forfeit"):
                rules.append("(4) no pin point for MD/TF/DQ/FF")
        if nm and wt != "forfeit":
            # already handled
            pass
    elif result == "L":
        if wt == "decision":
            pts = dec_loss
            if adv_code in NON_REGIONAL_CODES or dec_loss == -1.0:
                rules.append("(6)/chart −1 decision loss vs Quarters/Prelim/Never")
            elif adv_code == "D4":
                rules.append("chart: decision loss vs D4 = 0")
            else:
                rules.append("decision loss = 20% caliber (chart)")
        else:
            pts = 0.0
            rules.append("non-decision loss = 0")
    else:
        pts = 0.0
        notes = f"unrecognized result {result}"

    return MatchScore(
        opponent=opponent or "",
        opponent_team=opponent_team or "",
        result=result,
        win_type=wt,
        adv_code=adv_code,
        caliber=caliber,
        pin_point=pin,
        match_points=pts,
        rules_applied=rules,
        non_member=nm,
        notes=notes,
    )


def select_top20(scores: List[MatchScore]) -> Tuple[List[MatchScore], float, float]:
    """Mark top 20 by match_points; return (scores, top20_sum, all_sum)."""
    all_sum = sum(s.match_points for s in scores)
    ranked = sorted(range(len(scores)), key=lambda i: scores[i].match_points, reverse=True)
    top_idx = set(ranked[:20])
    for i, s in enumerate(scores):
        s.in_top20 = i in top_idx
    top20_sum = sum(scores[i].match_points for i in top_idx)
    return scores, top20_sum, all_sum



def parse_season_start_year(season: str) -> int:
    """Parse '2025-26' / '2025-2026' → start year 2025."""
    s = (season or "").strip()
    m = re.match(r"^(\d{4})\s*[-–]\s*(\d{2,4})$", s)
    if not m:
        raise ValueError(f"unrecognized season label: {season!r}")
    return int(m.group(1))


def format_season(start_year: int) -> str:
    yy = (start_year + 1) % 100
    return f"{start_year}-{yy:02d}"


def prior_seasons_for(season: str, n: int = 4) -> List[str]:
    """Prior *n* seasons for a pre-seed form in `season`, newest first.

    Default n=4 covers a senior's full HS lookback (frosh through prior year).
    For a 2025-26 pre-seed that is 2024-25 … 2021-22 — never the current season
    (those results happen after / during the season the form is for).
    """
    start = parse_season_start_year(season)
    return [format_season(start - i) for i in range(1, n + 1)]

def lookup_opponent_code(
    adv: Dict[str, Any],
    name: str,
    school: str,
    *,
    seasons: Optional[List[str]] = None,
    season_policy: str = "best",
) -> Tuple[Optional[str], Optional[str], str]:
    """Find opponent advancement code, optionally restricted to seasons.

    season_policy:
      - "best": highest-ranked code across the season window (default)
      - "most_recent": first season in `seasons` that has a finish (pass
        seasons newest-first). Falls back through the window — needed for
        opponents like Giangeruso with no prior-year entry but an older finish.

    Works with opponent_advancement schema v2 (`athletes` + `by_name_school` +
    `index`). Legacy `wrestlers` dict is still accepted.

    Returns (code, matched_athlete_id, note).
    """
    athletes = adv.get("athletes") or adv.get("wrestlers") or {}
    by_ns = adv.get("by_name_school") or {}
    index = adv.get("index") or {}
    nk = name_key(name)
    sk = school_key(school)
    skc = school_key_compact(school)

    # Fast path: exact name|school index / by_name_school
    candidates: List[Tuple[str, Dict[str, Any]]] = []
    exact_keys = []
    if sk:
        exact_keys.append(f"{nk}|{sk}")
    # also try compact-normalized school variants from by_name_school
    for key in list(by_ns.keys()) + list(index.keys()):
        if key.startswith(nk + "|"):
            exact_keys.append(key)
    seen_ids = set()
    for key in exact_keys:
        meta = by_ns.get(key) or (index.get(key) if isinstance(index.get(key), dict) else None)
        aid = None
        if isinstance(meta, dict):
            aid = meta.get("athlete_id")
        elif isinstance(meta, str):
            aid = meta
        if aid and aid in athletes and aid not in seen_ids:
            seen_ids.add(aid)
            candidates.append((aid, athletes[aid]))

    # Fallback: scan athletes by name_key
    if not candidates:
        for aid, v in athletes.items():
            if v.get("name_key") == nk or name_key(v.get("name", "")) == nk:
                candidates.append((aid, v))

    def school_fit(v: Dict[str, Any]) -> int:
        schools = [v.get("school_key") or ""] + [
            school_key(s) for s in (v.get("schools") or [])
        ]
        schools = [s for s in schools if s]
        best = 0
        for vk in schools:
            vkc = re.sub(r"[^a-z0-9]+", "", vk)
            score = 0
            if vk == sk or vkc == skc:
                score = 3
            elif sk and (sk in vk or vk in sk):
                score = 2
            elif skc and (skc in vkc or vkc in skc):
                score = 2
            else:
                toks = [t for t in sk.split() if len(t) > 3]
                if toks and any(t in vk for t in toks):
                    score = 1
            if score > best:
                best = score
        return best

    candidates.sort(key=lambda kv: school_fit(kv[1]), reverse=True)
    if not candidates:
        return None, None, "not found in opponent_advancement"
    best = None
    for k, v in candidates:
        if school_fit(v) > 0:
            best = (k, v)
            break
    if not best:
        if len(candidates) == 1:
            best = candidates[0]
        else:
            return None, None, f"ambiguous name match ({len(candidates)} schools)"

    k, v = best
    code_rank = adv.get("code_rank") or {}

    def codes_from_finish(fin: Dict[str, Any]) -> List[str]:
        out: List[str] = []
        if fin.get("code"):
            out.append(fin["code"])
        for a in fin.get("also") or []:
            if isinstance(a, dict) and a.get("code"):
                out.append(a["code"])
            elif isinstance(a, str):
                out.append(a)
        for a in fin.get("entries") or []:
            if isinstance(a, dict) and a.get("code"):
                out.append(a["code"])
        # unique preserve order
        seen = set()
        uniq = []
        for c in out:
            if c not in seen:
                seen.add(c)
                uniq.append(c)
        return uniq

    def best_code_among(codes: List[str]) -> Optional[str]:
        best_c = None
        best_r = -1
        for code in codes:
            r = code_rank.get(code, CHART.get(code, (0, 0, 0))[0])
            if r > best_r:
                best_r = r
                best_c = code
        return best_c

    if seasons:
        if season_policy == "most_recent":
            # seasons should be newest-first
            for season in seasons:
                fin = (v.get("seasons") or {}).get(season)
                if not fin:
                    continue
                codes = codes_from_finish(fin)
                # for a single season, take that season's best code (state > region > district)
                code = best_code_among(codes)
                if code:
                    return code, k, f"most_recent prior={season}"
            return "No post-season", k, f"no finish in {seasons}"
        collected: List[str] = []
        for season, fin in (v.get("seasons") or {}).items():
            if season not in seasons:
                continue
            collected.extend(codes_from_finish(fin))
        best_code = best_code_among(collected)
        if best_code:
            return best_code, k, f"best in {seasons}"
        return "No post-season", k, f"no finish in {seasons}"
    # Career best across all seasons (prefer stored field, else recompute)
    if v.get("career_best"):
        return v["career_best"], k, "career_best"
    collected = []
    for fin in (v.get("seasons") or {}).values():
        collected.extend(codes_from_finish(fin))
    return best_code_among(collected) or "No post-season", k, "career_best recomputed"


def score_bout_list(
    bouts: List[Dict[str, Any]],
    adv: Dict[str, Any],
    *,
    for_season: Optional[str] = None,
    seasons_for_opp: Optional[List[str]] = None,
    season_policy: str = "best",
) -> Tuple[List[Dict[str, Any]], float, float]:
    """Score current-season bouts for a pre-seed form.

    Opponent prestige/caliber codes come only from prior seasons: pass
    `for_season` (e.g. "2025-26") and the window is derived via
    `prior_seasons_for` (never includes `for_season` itself). Explicit
    `seasons_for_opp` overrides the derived window when provided.
    """
    if seasons_for_opp is None:
        if for_season:
            seasons_for_opp = prior_seasons_for(for_season)
        else:
            raise ValueError(
                "score_bout_list requires for_season=... (or explicit seasons_for_opp); "
                "opponent prestige must not use unrestricted career_best (would leak "
                "same-season postseason finishes into a pre-seed form)"
            )
    # Hard guard: drop the form season if a caller accidentally included it
    if for_season:
        seasons_for_opp = [s for s in seasons_for_opp if s != for_season]
    scored: List[MatchScore] = []
    rows: List[Dict[str, Any]] = []
    for b in bouts:
        if (b.get("win_type") or "").lower() == "bye" or b.get("kind") == "bye":
            rows.append({**b, "match_points": None, "excluded": "bye", "rules": []})
            continue
        code, key, note = lookup_opponent_code(
            adv, b.get("opp") or b.get("opponent") or "", b.get("opp_team") or b.get("opponent_team") or "",
            seasons=seasons_for_opp,
            season_policy=season_policy,
        )
        ms = score_match(
            result=b.get("result") or "",
            win_type_raw=b.get("win_type"),
            score=b.get("score"),
            opponent=b.get("opp") or b.get("opponent"),
            opponent_team=b.get("opp_team") or b.get("opponent_team"),
            adv_code=code,
        )
        if ms is None:
            rows.append({**b, "match_points": None, "excluded": "bye", "rules": []})
            continue
        ms.notes = (ms.notes + " | " + note).strip(" |")
        scored.append(ms)
        rows.append({
            **b,
            "adv_code": ms.adv_code,
            "adv_lookup_key": key,
            "caliber": ms.caliber,
            "pin_point": ms.pin_point,
            "match_points": ms.match_points,
            "non_member": ms.non_member,
            "rules": ms.rules_applied,
            "lookup_note": note,
            "normalized_win_type": ms.win_type,
        })

    scored, top20, all_sum = select_top20(scored)
    # copy top20 flags onto rows (match by order of scored)
    si = 0
    for r in rows:
        if r.get("match_points") is None:
            continue
        r["in_top20"] = scored[si].in_top20
        si += 1
    return rows, top20, all_sum


if __name__ == "__main__":
    print("caliber module OK; chart entries:", len(CHART))
    print("prior_seasons_for(2025-26) =", prior_seasons_for("2025-26"))
