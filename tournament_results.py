#!/usr/bin/env python3
"""Parse Trackwrestling EventMatches bout grids for Shawnee tournament cards.

Primary offline path: HTML captures under /workspace/shawnee/tw_event_pages that
embed initDataGrid(...). Live path (optional): Playwright in-page fetch of
getEventMatchesJSP from a TeamSchedule session — not required for rebuild.

Match row schema (EventMatches dataGrid):
  [0] match_id
  [1] weight
  [2] bout / sequence
  [3] win_type_label
  [6] winner_side  '1' = cols 16-19, '2' = cols 20-23
  [7] score_w1 (points)
  [10] score_w2
  [13] fall_seconds
  [16]/[17] w1 first/last
  [18]/[19] w1 team / abbr
  [20]/[21] w2 first/last
  [22]/[23] w2 team / abbr
  [24] win_type_long
  [25] win_type_abbr
  [31] round label (tournaments)
"""
from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("tournament_results")

ROOT = Path(__file__).resolve().parent
DEFAULT_CAPTURE_DIR = Path("/workspace/shawnee/tw_event_pages")

SHAWNEE_NAMES = {"shawnee", "shawnee high school", "shaw"}

DUAL_POINTS = {
    "fall": 6,
    "pin": 6,
    "forfeit": 6,
    "injury default": 6,
    "default": 6,
    "disqualified": 6,
    "dq": 6,
    "tech. fall": 5,
    "technical fall": 5,
    "tf": 5,
    "maj. dec.": 4,
    "major decision": 4,
    "md": 4,
    "decision": 3,
    "dec.": 3,
    "dec": 3,
    "sudden victory": 3,
    "sv": 3,
    "tie breaker": 3,
    "ultimate tie breaker": 3,
}


def _norm_team(s: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def is_shawnee(team: Optional[str]) -> bool:
    n = _norm_team(team)
    return n in SHAWNEE_NAMES or n.startswith("shawnee")


def extract_init_datagrid(html: str) -> List[List[Any]]:
    m = re.search(r'initDataGrid\(\s*\d+\s*,\s*(?:true|false)\s*,\s*"', html)
    if not m:
        return []
    start = m.end()
    j = start
    while j < len(html):
        if html[j] == "\\":
            j += 2
            continue
        if html[j] == '"':
            break
        j += 1
    raw = html[start:j]
    if not raw.strip() or raw.strip() == "null":
        return []
    s = raw.replace(r"\"", '"')
    try:
        data = json.loads(s)
    except json.JSONDecodeError as e:
        logger.warning("initDataGrid JSON parse failed: %s", e)
        return []
    return data if isinstance(data, list) else []


def points_for_win_type(label: Optional[str]) -> int:
    if not label:
        return 3
    key = label.strip().lower()
    if key in DUAL_POINTS:
        return DUAL_POINTS[key]
    for k, v in DUAL_POINTS.items():
        if k in key:
            return v
    return 3


def parse_bout_row(row: List[Any]) -> Optional[Dict[str, Any]]:
    if not row or len(row) < 25:
        return None
    weight = str(row[1] or "").strip()
    winner_side = str(row[6] or "").strip()
    w1 = {
        "first": row[16],
        "last": row[17],
        "team": row[18],
        "abbr": row[19],
        "name": " ".join(x for x in (row[16], row[17]) if x).strip() or None,
    }
    w2 = {
        "first": row[20],
        "last": row[21],
        "team": row[22],
        "abbr": row[23],
        "name": " ".join(x for x in (row[20], row[21]) if x).strip() or None,
    }
    win_type = row[24] or row[3] or row[25]
    fall_secs = row[13]
    try:
        fall_secs_i = int(fall_secs) if fall_secs not in (None, "", "0") else None
    except (TypeError, ValueError):
        fall_secs_i = None
    score_w1 = row[7]
    score_w2 = row[10]
    round_label = row[31] if len(row) > 31 else None

    if winner_side == "1":
        winner, loser = w1, w2
    elif winner_side == "2":
        winner, loser = w2, w1
    else:
        winner, loser = w1, w2

    shawnee_is_w1 = is_shawnee(w1["team"])
    shawnee_is_w2 = is_shawnee(w2["team"])
    if not (shawnee_is_w1 or shawnee_is_w2):
        # Keep all bouts for dual scoring between any teams in multi-meets;
        # callers filter as needed.
        shawnee_side = None
        result = None
    else:
        shawnee_side = "w1" if shawnee_is_w1 else "w2"
        if winner_side == "1":
            result = "W" if shawnee_is_w1 else "L"
        elif winner_side == "2":
            result = "W" if shawnee_is_w2 else "L"
        else:
            result = None

    opp_team = None
    opp_wrestler = None
    shawnee_wrestler = None
    if shawnee_is_w1:
        shawnee_wrestler = w1["name"]
        opp_team = w2["team"]
        opp_wrestler = w2["name"]
    elif shawnee_is_w2:
        shawnee_wrestler = w2["name"]
        opp_team = w1["team"]
        opp_wrestler = w1["name"]

    return {
        "match_id": str(row[0]) if row[0] is not None else None,
        "weight": weight,
        "bout": str(row[2] or ""),
        "win_type": win_type,
        "win_type_abbr": row[25],
        "winner_side": winner_side,
        "score_w1": score_w1,
        "score_w2": score_w2,
        "fall_seconds": fall_secs_i,
        "round": round_label,
        "w1": w1,
        "w2": w2,
        "winner_name": winner["name"],
        "winner_team": winner["team"],
        "loser_name": loser["name"],
        "loser_team": loser["team"],
        "shawnee_side": shawnee_side,
        "result": result,
        "shawnee_wrestler": shawnee_wrestler,
        "opponent_team": opp_team,
        "opponent_wrestler": opp_wrestler,
        "dual_points": points_for_win_type(str(win_type) if win_type else None),
    }


def parse_event_html(html: str) -> List[Dict[str, Any]]:
    rows = extract_init_datagrid(html)
    out = []
    for r in rows:
        b = parse_bout_row(r)
        if b:
            out.append(b)
    return out



PIPE_RESULT_TYPES = {
    "fall": "Fall",
    "pin": "Fall",
    "tf": "Tech. Fall",
    "tech": "Tech. Fall",
    "tech. fall": "Tech. Fall",
    "technical fall": "Tech. Fall",
    "md": "Maj. Dec.",
    "maj": "Maj. Dec.",
    "maj. dec.": "Maj. Dec.",
    "major decision": "Maj. Dec.",
    "dec": "Decision",
    "dec.": "Decision",
    "decision": "Decision",
    "for": "Forfeit",
    "for.": "Forfeit",
    "ff": "Forfeit",
    "forfeit": "Forfeit",
    "inj": "Injury Default",
    "injury": "Injury Default",
    "injury default": "Injury Default",
    "dq": "Disqualified",
    "default": "Default",
    "sv": "Sudden Victory",
    "tb": "Tie Breaker",
    "utb": "Ultimate Tie Breaker",
}


def _map_pipe_result_type(raw: Optional[str]) -> str:
    key = (raw or "").strip().lower().rstrip(".")
    if key in PIPE_RESULT_TYPES:
        return PIPE_RESULT_TYPES[key]
    # strip trailing punctuation variants like "For."
    key2 = key.rstrip(".")
    if key2 in PIPE_RESULT_TYPES:
        return PIPE_RESULT_TYPES[key2]
    for k, v in PIPE_RESULT_TYPES.items():
        if k in key:
            return v
    return (raw or "").strip() or "Decision"


def _parse_score_time(score_time: Optional[str], win_type: str) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    """Return (fall_seconds, score_w1_display, score_w2_display-ish)."""
    st = (score_time or "").strip()
    if not st:
        return None, None, None
    # time like 1:55 or 0:58 or 5:47
    m_time = re.search(r"(\d{1,2}):(\d{2})", st)
    fall_secs = None
    if m_time:
        fall_secs = int(m_time.group(1)) * 60 + int(m_time.group(2))
    # score like 15-11 or 24-9
    m_score = re.search(r"(\d+)\s*-\s*(\d+)", st)
    s1 = s2 = None
    if m_score:
        s1, s2 = m_score.group(1), m_score.group(2)
    wt = win_type.lower()
    if "fall" in wt or "pin" in wt:
        # fall time is primary; keep score parts None
        return fall_secs, s1, s2
    if "tech" in wt:
        return fall_secs, s1, s2
    return fall_secs, s1, s2


def _repair_pipe_name_team(loser: str, loser_team: str) -> Tuple[str, str]:
    """Fix captures that split \"William (Liam) McSorley|Shawnee\" into
    William|Liam) McSorley (Shawnee."""
    m = re.match(r"^(.+)\) (.+) \((.+)$", (loser_team or "").strip())
    if m and loser and " " not in loser.strip():
        return f"{loser.strip()} ({m.group(1)}) {m.group(2)}", m.group(3).rstrip(")")
    # also: loser_team ends with school and name leaked
    if loser_team and "Shawnee" in loser_team and not is_shawnee(loser_team):
        m2 = re.search(r"\(([^)]+)\)\s*$", loser_team)
        if m2 and is_shawnee(m2.group(1)):
            name_part = loser_team[: m2.start()].strip(" (")
            return f"{loser} {name_part}".strip(), m2.group(1)
    return loser, loser_team


def parse_pipe_dual_txt(text: str) -> List[Dict[str, Any]]:
    """Parse pipe-format dual captures:
    weight|winner|winner_team|loser|loser_team|result_type|score_time
    """
    lines = [ln.rstrip("\n") for ln in text.splitlines()]
    # skip comments / blank / header
    rows = []
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        if s.lower().startswith("weight|"):
            continue
        parts = s.split("|")
        if len(parts) < 7:
            # try to tolerate extra pipes inside names by taking first 3 + last 3 + middle join
            if len(parts) > 7:
                weight = parts[0]
                winner = parts[1]
                winner_team = parts[2]
                score_time = parts[-1]
                result_type = parts[-2]
                # remaining middle: loser ... loser_team — assume last of middle is team if Shawnee/known
                mid = parts[3:-2]
                if len(mid) >= 2:
                    loser_team = mid[-1]
                    loser = "|".join(mid[:-1])
                else:
                    continue
                parts = [weight, winner, winner_team, loser, loser_team, result_type, score_time]
            else:
                continue
        weight, winner, winner_team, loser, loser_team, result_type, score_time = (
            parts[0].strip(),
            parts[1].strip(),
            parts[2].strip(),
            parts[3].strip(),
            parts[4].strip(),
            parts[5].strip(),
            parts[6].strip(),
        )
        loser, loser_team = _repair_pipe_name_team(loser, loser_team)
        # also repair winner side symmetrically
        winner, winner_team = _repair_pipe_name_team(winner, winner_team)
        win_type = _map_pipe_result_type(result_type)
        fall_secs, s1, s2 = _parse_score_time(score_time, win_type)

        w_win = {
            "first": None,
            "last": None,
            "team": winner_team,
            "abbr": None,
            "name": winner or None,
        }
        w_lose = {
            "first": None,
            "last": None,
            "team": loser_team,
            "abbr": None,
            "name": loser or None,
        }
        # Put winner as w1 for consistency with winner_side=1
        w1, w2 = w_win, w_lose
        shawnee_is_w1 = is_shawnee(w1["team"])
        shawnee_is_w2 = is_shawnee(w2["team"])
        if shawnee_is_w1 or shawnee_is_w2:
            shawnee_side = "w1" if shawnee_is_w1 else "w2"
            result = "W" if shawnee_is_w1 else "L"
        else:
            shawnee_side = None
            result = None
        shawnee_wrestler = opp_team = opp_wrestler = None
        if shawnee_is_w1:
            shawnee_wrestler = w1["name"]
            opp_team = w2["team"]
            opp_wrestler = w2["name"]
        elif shawnee_is_w2:
            shawnee_wrestler = w2["name"]
            opp_team = w1["team"]
            opp_wrestler = w1["name"]

        rows.append({
            "match_id": None,
            "weight": weight,
            "bout": "",
            "win_type": win_type,
            "win_type_abbr": result_type,
            "winner_side": "1",
            "score_w1": s1,
            "score_w2": s2,
            "fall_seconds": fall_secs,
            "round": None,
            "w1": w1,
            "w2": w2,
            "winner_name": winner or None,
            "winner_team": winner_team,
            "loser_name": loser or None,
            "loser_team": loser_team,
            "shawnee_side": shawnee_side,
            "result": result,
            "shawnee_wrestler": shawnee_wrestler,
            "opponent_team": opp_team,
            "opponent_wrestler": opp_wrestler,
            "dual_points": points_for_win_type(win_type),
            "score_time_raw": score_time,
        })
    return rows


def parse_dual_header_meta(text: str) -> Dict[str, Any]:
    """Extract dualId / parent eventId / score line from leading # comments."""
    meta: Dict[str, Any] = {}
    for ln in text.splitlines()[:5]:
        if not ln.startswith("#"):
            continue
        m = re.search(r"dualId\s*=?\s*(\d{8,})", ln, re.I)
        if m:
            # Prefer explicit "(dualId N, within event M)" over trailing source dualId=
            m_within = re.search(
                r"\(dualId\s+(\d{8,})\s*,\s*within\s+event\s+(\d{8,})",
                ln,
                re.I,
            )
            if m_within:
                meta["dual_id"] = m_within.group(1)
                meta["parent_event_id"] = m_within.group(2)
            elif "dual_id" not in meta:
                meta["dual_id"] = m.group(1)
        m_eid = re.search(r"event[_ ]?Id[= ](\d{8,})", ln, re.I)
        if m_eid and "parent_event_id" not in meta:
            meta.setdefault("file_event_id", m_eid.group(1))
        m_score = re.search(
            r"(Shawnee|Toms River South|NBC|CHW|CHE|Eastern|Moorestown|Haddonfield|Robbinsville|Paul VI)"
            r"[^|]*?(\d+)\s*[-–]\s*(\d+)",
            ln,
            re.I,
        )
        if m_score:
            meta["header_score"] = ln.strip("# ").split("|")[0].strip()
    return meta


def load_capture(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    raw = path.read_text(errors="ignore")
    if path.suffix.lower() == ".txt" or (
        "weight|winner|winner_team|loser|loser_team" in raw[:2000]
    ):
        return parse_pipe_dual_txt(raw)
    return parse_event_html(raw)


def infer_placement(bouts: List[Dict[str, Any]], wrestler: str) -> Optional[str]:
    """Infer place from round labels of the wrestler's final relevant bout."""
    mine = [b for b in bouts if (b.get("shawnee_wrestler") or "").lower() == wrestler.lower()]
    if not mine:
        return None
    # Prefer explicit place-match rounds
    place_map = [
        (r"\b1st place\b", "1st"),
        (r"\b2nd place\b", "2nd"),
        (r"\b3rd place\b", "3rd"),
        (r"\b4th place\b", "4th"),
        (r"\b5th place\b", "5th"),
        (r"\b6th place\b", "6th"),
        (r"\b7th place\b", "7th"),
        (r"\b8th place\b", "8th"),
    ]
    for b in reversed(mine):
        rnd = str(b.get("round") or "")
        low = rnd.lower()
        for pat, place in place_map:
            if re.search(pat, low):
                # If they won a 1st place match → 1st; lost → 2nd, etc.
                if b.get("result") == "W":
                    return place
                # lost 1st place match → 2nd; lost 3rd → 4th; lost 5th → 6th
                odd_places = {"1st": "2nd", "3rd": "4th", "5th": "6th", "7th": "8th"}
                return odd_places.get(place, place)
    return None


def wrestler_cards(bouts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group Shawnee bouts by wrestler for expandable tournament UI."""
    by: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for b in bouts:
        if not b.get("shawnee_wrestler"):
            continue
        by[b["shawnee_wrestler"]].append(b)

    cards = []
    for name, rows in by.items():
        rows_sorted = sorted(rows, key=lambda x: (x.get("bout") or "", x.get("match_id") or ""))
        weights = [r["weight"] for r in rows_sorted if r.get("weight")]
        weight = max(set(weights), key=weights.count) if weights else None
        wins = sum(1 for r in rows_sorted if r.get("result") == "W")
        losses = sum(1 for r in rows_sorted if r.get("result") == "L")
        placement = infer_placement(rows_sorted, name)
        cards.append({
            "wrestler": name,
            "weight": weight,
            "record": f"{wins}-{losses}",
            "wins": wins,
            "losses": losses,
            "placement": placement,
            "bouts": [
                {
                    "weight": r.get("weight"),
                    "round": r.get("round"),
                    "result": r.get("result"),
                    "win_type": r.get("win_type"),
                    "fall_seconds": r.get("fall_seconds"),
                    "opponent_wrestler": r.get("opponent_wrestler"),
                    "opponent_team": r.get("opponent_team"),
                    "score": _bout_score_display(r),
                }
                for r in rows_sorted
            ],
        })
    cards.sort(key=lambda c: (int(c["weight"]) if str(c.get("weight") or "").isdigit() else 999, c["wrestler"]))
    return cards


def _bout_score_display(r: Dict[str, Any]) -> Optional[str]:
    wt = str(r.get("win_type") or "").lower()
    # Check tech BEFORE fall — "Tech. Fall" contains the substring "fall"
    if "tech" in wt:
        s1, s2 = r.get("score_w1"), r.get("score_w2")
        secs = r.get("fall_seconds")
        score = f"{s1}-{s2}" if s1 not in (None, "") and s2 not in (None, "") else ""
        if secs and score:
            return f"TF {score} {secs // 60}:{secs % 60:02d}"
        if score:
            return f"TF {score}"
        if secs:
            return f"TF {secs // 60}:{secs % 60:02d}"
        return "TF"
    if ("fall" in wt or "pin" in wt) and "tech" not in wt:
        secs = r.get("fall_seconds")
        if secs:
            return f"Fall {secs // 60}:{secs % 60:02d}"
        return "Fall"
    if "forfeit" in wt:
        return "Forfeit"
    s1, s2 = r.get("score_w1"), r.get("score_w2")
    if s1 not in (None, "", "0") or s2 not in (None, "", "0"):
        # orient score with Shawnee first when possible
        if r.get("shawnee_side") == "w1":
            return f"{s1}-{s2}"
        if r.get("shawnee_side") == "w2":
            return f"{s2}-{s1}"
        return f"{s1}-{s2}"
    return r.get("win_type")


def dual_scores_vs_opponents(bouts: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Compute Shawnee dual team scores vs each opposing school from bout results."""
    scores: Dict[str, Dict[str, int]] = defaultdict(lambda: {"shawnee": 0, "opp": 0})
    for b in bouts:
        if not b.get("shawnee_wrestler"):
            continue
        opp = b.get("opponent_team")
        if not opp or is_shawnee(opp):
            continue
        pts = b.get("dual_points") or 3
        if b.get("result") == "W":
            scores[opp]["shawnee"] += pts
        elif b.get("result") == "L":
            scores[opp]["opp"] += pts
    out = {}
    for opp, sc in scores.items():
        result = "W" if sc["shawnee"] > sc["opp"] else ("L" if sc["shawnee"] < sc["opp"] else "T")
        out[opp] = {
            "opponent": opp,
            "shawnee": sc["shawnee"],
            "opp": sc["opp"],
            "result": result,
            "score_display": f"{sc['shawnee']}-{sc['opp']}",
        }
    return out


def opposing_teams(bouts: List[Dict[str, Any]]) -> List[str]:
    teams = []
    seen = set()
    for b in bouts:
        for t in (b.get("w1", {}).get("team"), b.get("w2", {}).get("team")):
            if not t or is_shawnee(t):
                continue
            key = _norm_team(t)
            if key in seen:
                continue
            seen.add(key)
            teams.append(t)
    return teams


def build_event_results(event_id: str, html_or_bouts) -> Dict[str, Any]:
    if isinstance(html_or_bouts, (str, Path)):
        path = Path(html_or_bouts)
        bouts = load_capture(path) if path.exists() else parse_event_html(str(html_or_bouts))
    else:
        bouts = list(html_or_bouts)
    shawnee_bouts = [b for b in bouts if b.get("shawnee_wrestler")]
    return {
        "event_id": str(event_id),
        "bout_count": len(bouts),
        "shawnee_bout_count": len(shawnee_bouts),
        "opponents": opposing_teams(bouts),
        "dual_scores": dual_scores_vs_opponents(bouts),
        "wrestlers": wrestler_cards(shawnee_bouts),
        "bouts": shawnee_bouts,
    }


def index_captures(capture_dir: Path | None = None) -> Dict[str, Path]:
    """Index HTML EventMatches and pipe-format dual .txt captures by event/dual id.

    For sectional duals saved under the parent event id (e.g. Toms River South
    dual 9000836132 inside sectional 9000835132), both ids map to the same file.
    """
    capture_dir = capture_dir or DEFAULT_CAPTURE_DIR
    out: Dict[str, Path] = {}
    if not capture_dir.exists():
        return out
    patterns = ("*.html", "*.txt")
    files: List[Path] = []
    for pat in patterns:
        files.extend(sorted(capture_dir.glob(pat)))
    for p in files:
        m = re.search(r"(\d{8,})", p.stem)
        if m:
            out[m.group(1)] = p
        head = p.read_text(errors="ignore")[:4000]
        m2 = re.search(r"eventId=(\d+)", head)
        if m2:
            out[m2.group(1)] = p
        meta = parse_dual_header_meta(head)
        if meta.get("dual_id"):
            out[str(meta["dual_id"])] = p
        if meta.get("parent_event_id"):
            out[str(meta["parent_event_id"])] = p
    return out


def attach_tournament_results(
    data: Dict[str, Any],
    capture_dir: Path | None = None,
) -> Dict[str, Any]:
    """Add data['tournament_results'][event_id] from offline captures."""
    idx = index_captures(capture_dir)
    results: Dict[str, Any] = {}
    for ev in data.get("schedule") or []:
        eid = str(ev.get("event_id") or "")
        if not eid:
            continue
        path = idx.get(eid)
        if not path:
            continue
        built = build_event_results(eid, path)
        if built["shawnee_bout_count"] == 0 and built["bout_count"] == 0:
            continue
        results[eid] = {
            "event_id": eid,
            "event_name": ev.get("event_name"),
            "date_iso": ev.get("date_iso"),
            "source_file": str(path.name),
            "opponents": built["opponents"],
            "dual_scores": built["dual_scores"],
            "wrestlers": built["wrestlers"],
            "shawnee_bout_count": built["shawnee_bout_count"],
        }
    data["tournament_results"] = results
    return data


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    idx = index_captures()
    print(f"captures: {len(idx)}")
    for eid, path in sorted(idx.items()):
        b = load_capture(path)
        print(eid, path.name, "bouts", len(b), "shawnee", sum(1 for x in b if x.get("shawnee_wrestler")))
