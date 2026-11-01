#!/usr/bin/env python3
"""Enrich full roster from 2025-26 TW data; merge live WP home roster for Home.

- Full roster: name, grade, weights wrestled, season record, player pages
- Home roster: WP gallery (weight/name/photo) matched to TW; unmatched listed both ways
- Never invent fields; never surface Trackwrestling or wrestler IDs on pages
"""
from __future__ import annotations

import json
import re
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from zoneinfo import ZoneInfo

EST = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parent
PHOTO_DIR = ROOT / "assets" / "img" / "roster"
WP_HOME_URL = "https://shawneewrestling.com/"

# Explicit nickname / spelling bridges (WP ↔ TW)
NAME_ALIASES = {
    "garret borlaug": "garrett borlaug",
    "garrett borlaug": "garrett borlaug",
    "liam mcsorley": "william liam mcsorley",
    "william liam mcsorley": "william liam mcsorley",
    "william mcsorley": "william liam mcsorley",
    "oleksandr sasha yurovskyi": "oleksandr sasha yurovskyi",
    "oleksandr yurovskyi": "oleksandr sasha yurovskyi",
    "sasha yurovskyi": "oleksandr sasha yurovskyi",
    "chris ahrens": "christopher ahrens",
    "christopher ahrens": "christopher ahrens",
}


def now_est() -> str:
    t = datetime.now(EST)
    s = t.strftime("%Y-%m-%dT%H:%M:%S%z")
    return s[:-2] + ":" + s[-2:]


def norm_name(n: str) -> str:
    n = (n or "").lower().replace("`", " ").replace('"', " ").replace("'", " ")
    n = re.sub(r"\([^)]*\)", " ", n)
    n = re.sub(r"[^a-z0-9]+", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def canon_name(n: str) -> str:
    k = norm_name(n)
    return NAME_ALIASES.get(k, k)


def tokens(n: str) -> Set[str]:
    return {t for t in norm_name(n).split() if t}


def weight_sort_key(w: str) -> int:
    s = str(w or "").strip().upper()
    if s in {"HWT", "HW", "HEAVY", "HEAVYWEIGHT"}:
        return 285
    m = re.search(r"\d+", s)
    return int(m.group()) if m else 999


def fetch_url(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "ShawneeWrestlingSiteBot/1.0 (roster enrich; local preview)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def parse_wp_home_roster(html: str) -> List[Dict[str, Any]]:
    m = re.search(
        r'<h4 class="sp-table-caption">Roster</h4>(.*?)</aside>',
        html,
        flags=re.S | re.I,
    )
    if not m:
        return []
    chunk = m.group(1)
    out: List[Dict[str, Any]] = []
    for dm in re.finditer(r"<dl class='gallery-item'>(.*?)</dl>", chunk, flags=re.S):
        item = dm.group(1)
        href_m = re.search(r'href="([^"]+/player/[^"]+)"', item)
        img_m = re.search(r'<img[^>]+src="([^"]+)"', item)
        cap_m = re.search(r"<strong>(\d+)</strong>\s*([^<]+)", item)
        if not cap_m:
            continue
        src = img_m.group(1) if img_m else None
        if src and src.startswith("//"):
            src = "https:" + src
        photo = src
        if photo and ("gravatar.com" in photo or "d=mm" in photo):
            photo = None  # mystery-man — treat as no photo
        name = cap_m.group(2).strip().replace("`", '"')
        out.append(
            {
                "name": name,
                "display_weight": cap_m.group(1),
                "photo_url": photo,
                "player_url": href_m.group(1) if href_m else None,
                "source": "shawneewrestling.com_home_gallery",
            }
        )
    return out


def match_wp_to_tw(
    wp_rows: List[Dict[str, Any]], tw_roster: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[str], List[str]]:
    tw_by_canon = {canon_name(w["name"]): w for w in tw_roster if w.get("name")}
    tw_by_last: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for w in tw_roster:
        parts = norm_name(w.get("name") or "").split()
        if parts:
            tw_by_last[parts[-1]].append(w)

    matched: List[Dict[str, Any]] = []
    unmatched_wp: List[str] = []
    used_ids: Set[str] = set()

    for row in wp_rows:
        c = canon_name(row["name"])
        hit = tw_by_canon.get(c)
        if not hit:
            parts = norm_name(row["name"]).split()
            last = parts[-1] if parts else ""
            for cand in tw_by_last.get(last, []):
                ct, wt = tokens(cand["name"]), tokens(row["name"])
                inter = ct & wt
                if len(inter) >= 2:
                    hit = cand
                    break
                if parts and any(
                    t in ct for t in parts[:-1] if len(t) > 2
                ):
                    hit = cand
                    break
        if hit:
            wid = str(hit.get("wrestler_id") or "")
            used_ids.add(wid)
            matched.append(
                {
                    **row,
                    "tw_name": hit.get("name"),
                    "wrestler_id": wid,
                    "grade": hit.get("grade"),
                    "wins": hit.get("wins") or 0,
                    "losses": hit.get("losses") or 0,
                    "roster_weight": hit.get("weight"),
                    "match": "exact" if c == canon_name(hit["name"]) or c in NAME_ALIASES else "fuzzy",
                }
            )
        else:
            unmatched_wp.append(row["name"])

    unmatched_tw = [
        w["name"]
        for w in tw_roster
        if str(w.get("wrestler_id") or "") not in used_ids
    ]
    return matched, unmatched_wp, unmatched_tw


def weights_wrestled_by_name(tournament_results: Dict[str, Any]) -> Dict[str, List[str]]:
    by: Dict[str, Set[str]] = defaultdict(set)
    for key, ev in (tournament_results or {}).items():
        if not isinstance(ev, dict):
            continue
        for w in ev.get("wrestlers") or []:
            name = w.get("wrestler") or w.get("name")
            wt = w.get("weight")
            if name and wt:
                by[canon_name(name)].add(str(wt))
            for b in w.get("bouts") or []:
                bwt = b.get("weight")
                if name and bwt:
                    by[canon_name(name)].add(str(bwt))
    return {
        k: sorted(v, key=weight_sort_key)
        for k, v in by.items()
    }


def download_photo(url: str, dest: Path) -> Optional[str]:
    """Save photo under assets/img/roster/; return site-relative path or None."""
    try:
        data = fetch_url(url)
    except Exception as e:
        print(f"  photo fetch failed {url}: {e}")
        return None
    if len(data) < 200:
        return None
    # sniff
    ext = ".jpg"
    if data[:8].startswith(b"\x89PNG"):
        ext = ".png"
    elif data[:2] == b"\xff\xd8":
        ext = ".jpg"
    elif data[:4] == b"RIFF":
        ext = ".webp"
    dest = dest.with_suffix(ext)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    rel = f"assets/img/roster/{dest.name}"
    return rel


def slug_file(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (name or "wrestler").lower()).strip("-") or "wrestler"


def enrich(
    *,
    wp_html: Optional[str] = None,
    download_photos: bool = True,
) -> Dict[str, Any]:
    wd_path = ROOT / "data" / "wrestling_data.json"
    wd = json.loads(wd_path.read_text())
    roster = wd.get("roster") or []
    tr = {}
    tr_path = ROOT / "data" / "tournament_results.json"
    if tr_path.exists():
        tr = json.loads(tr_path.read_text())

    ww_map = weights_wrestled_by_name(tr)

    # Attach weights_wrestled onto roster rows (in-memory + persist non-ID public fields)
    for w in roster:
        c = canon_name(w.get("name") or "")
        weights = list(ww_map.get(c) or [])
        rw = str(w.get("weight") or "").strip()
        if rw and rw not in weights:
            # roster weight is known even when no bout feed — include only if alone or already listed
            if not weights:
                weights = [rw]
            else:
                weights = sorted(set(weights) | {rw}, key=weight_sort_key)
        w["weights_wrestled"] = weights

    if wp_html is None:
        print(f"Fetching {WP_HOME_URL} …")
        wp_html = fetch_url(WP_HOME_URL).decode("utf-8", errors="ignore")

    wp_rows = parse_wp_home_roster(wp_html)
    matched, unmatched_wp, unmatched_tw = match_wp_to_tw(wp_rows, roster)

    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    photo_by_id: Dict[str, str] = {}
    for mrow in matched:
        wid = mrow["wrestler_id"]
        url = mrow.get("photo_url")
        local = None
        if download_photos and url:
            dest = PHOTO_DIR / slug_file(mrow.get("tw_name") or mrow["name"])
            local = download_photo(url, dest)
        if local:
            photo_by_id[wid] = local
            mrow["photo"] = local
        else:
            mrow["photo"] = None

    # Persist photos + weights onto wrestling_data roster
    for w in roster:
        wid = str(w.get("wrestler_id") or "")
        if wid in photo_by_id:
            w["photo"] = photo_by_id[wid]

    wd_path.write_text(json.dumps(wd, indent=2) + "\n")
    (ROOT / "wrestling_data.json").write_text(json.dumps(wd, indent=2) + "\n")

    # players_index enrich
    pi_path = ROOT / "data" / "players_index.json"
    pi = json.loads(pi_path.read_text()) if pi_path.exists() else {"wrestlers": []}
    by_id = {str(w.get("wrestler_id")): w for w in roster}
    for row in pi.get("wrestlers") or []:
        wid = str(row.get("wrestler_id") or "")
        base = by_id.get(wid) or {}
        if wid in photo_by_id:
            row["photo"] = photo_by_id[wid]
        elif base.get("photo"):
            row["photo"] = base["photo"]
        weights = base.get("weights_wrestled") or []
        row["weights_wrestled"] = weights
        # extend search_text
        bits = [
            row.get("name"),
            row.get("grade"),
            row.get("roster_weight"),
            row.get("assigned_weight"),
            " ".join(weights),
        ]
        row["search_text"] = " ".join(str(b) for b in bits if b).lower()
    pi["updated_at"] = now_est()
    pi["count"] = len(pi.get("wrestlers") or [])
    pi_path.write_text(json.dumps(pi, indent=2) + "\n")

    # varsity assignments photos
    va_path = ROOT / "data" / "varsity_assignments.json"
    if va_path.exists():
        va = json.loads(va_path.read_text())
        for slot in va.get("slots") or []:
            wid = str(slot.get("wrestler_id") or "")
            if wid in photo_by_id:
                slot["photo"] = photo_by_id[wid]
        va["updated_at"] = now_est()
        va_path.write_text(json.dumps(va, indent=2) + "\n")

    # player pages — rebuild so photos stick
    from players_build import build_players

    awards = json.loads((ROOT / "data" / "awards.json").read_text())
    assignments = json.loads(va_path.read_text()) if va_path.exists() else {"slots": []}
    career = {}
    cp = ROOT / "data" / "career.json"
    if cp.exists():
        career = json.loads(cp.read_text())
    # ensure roster photos flow into build_players via wrestling_data
    build_players(wd, awards, assignments, career)
    # re-apply weights_wrestled after rebuild (build_players doesn't know them yet)
    pi = json.loads(pi_path.read_text())
    for row in pi.get("wrestlers") or []:
        wid = str(row.get("wrestler_id") or "")
        base = by_id.get(wid) or {}
        weights = base.get("weights_wrestled") or []
        row["weights_wrestled"] = weights
        if wid in photo_by_id:
            row["photo"] = photo_by_id[wid]
        bits = [
            row.get("name"),
            row.get("grade"),
            row.get("roster_weight"),
            row.get("assigned_weight"),
            " ".join(weights),
        ]
        row["search_text"] = " ".join(str(b) for b in bits if b).lower()
    pi["updated_at"] = now_est()
    pi_path.write_text(json.dumps(pi, indent=2) + "\n")

    # WP snapshot + home roster doc
    wp_doc = {
        "schema_version": 1,
        "source": WP_HOME_URL,
        "fetched_at": now_est(),
        "count": len(wp_rows),
        "wrestlers": wp_rows,
    }
    (ROOT / "data" / "site_roster_wp.json").write_text(json.dumps(wp_doc, indent=2) + "\n")

    # Resolve player_page for home cards from players_index
    page_by_id = {
        str(r.get("wrestler_id")): r.get("player_page")
        for r in (pi.get("wrestlers") or [])
    }
    home_cards = []
    for mrow in matched:
        wid = mrow["wrestler_id"]
        home_cards.append(
            {
                "name": mrow.get("tw_name") or mrow["name"],
                "wp_name": mrow["name"],
                "display_weight": mrow.get("display_weight"),
                "grade": mrow.get("grade") or None,
                "wins": mrow.get("wins"),
                "losses": mrow.get("losses"),
                "photo": mrow.get("photo"),
                "player_page": page_by_id.get(wid),
                "weights_wrestled": (by_id.get(wid) or {}).get("weights_wrestled") or [],
                "matched": True,
            }
        )
    # WP-only cards (no TW match) — show WP info only, no invented TW stats
    for name in unmatched_wp:
        src = next((r for r in wp_rows if r["name"] == name), None) or {}
        photo = None
        if download_photos and src.get("photo_url"):
            photo = download_photo(
                src["photo_url"], PHOTO_DIR / ("wp-" + slug_file(name))
            )
        home_cards.append(
            {
                "name": name,
                "wp_name": name,
                "display_weight": src.get("display_weight"),
                "grade": None,
                "wins": None,
                "losses": None,
                "photo": photo,
                "player_page": None,
                "weights_wrestled": [],
                "matched": False,
            }
        )

    def card_sort(c: Dict[str, Any]) -> Tuple[int, str]:
        return (weight_sort_key(c.get("display_weight") or ""), c.get("name") or "")

    home_cards.sort(key=card_sort)

    home_doc = {
        "schema_version": 1,
        "season": "2025-2026",
        "updated_at": now_est(),
        "source_note": "Home roster merges live shawneewrestling.com gallery with 2025-26 season roster data.",
        "counts": {
            "wp_gallery": len(wp_rows),
            "tw_roster": len(roster),
            "matched": len(matched),
            "unmatched_wp": len(unmatched_wp),
            "unmatched_tw": len(unmatched_tw),
            "home_cards": len(home_cards),
            "photos_saved": len(photo_by_id),
        },
        "match_report": {
            "matched": [
                {
                    "wp_name": m["name"],
                    "tw_name": m["tw_name"],
                    "display_weight": m.get("display_weight"),
                }
                for m in matched
            ],
            "unmatched_wp": unmatched_wp,
            "unmatched_tw": unmatched_tw,
        },
        "wrestlers": home_cards,
    }
    (ROOT / "data" / "home_roster.json").write_text(json.dumps(home_doc, indent=2) + "\n")

    print(
        f"TW roster={len(roster)} WP={len(wp_rows)} matched={len(matched)} "
        f"unmatched_wp={len(unmatched_wp)} unmatched_tw={len(unmatched_tw)} "
        f"photos={len(photo_by_id)}"
    )
    return home_doc


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--html", help="Path to saved shawneewrestling.com home HTML")
    ap.add_argument("--no-photos", action="store_true")
    args = ap.parse_args()
    html = Path(args.html).read_text(errors="ignore") if args.html else None
    enrich(wp_html=html, download_photos=not args.no_photos)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
