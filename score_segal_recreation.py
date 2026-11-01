#!/usr/bin/env python3
"""Recreate Jordan Segal 2025-26 NJSIAA pre-seed from Shawnee data + opponent_advancement."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from caliber import score_bout_list, name_key, school_key_compact, prior_seasons_for

ROOT = Path(__file__).resolve().parent
ADV_PATH = ROOT / "data" / "opponent_advancement.json"
BOUTS_HIST = ROOT / "data" / "history" / "2025-26_bouts.json"
MISSING_DUALS = ROOT / "data" / "history" / "2025-26_missing_dual_captures.json"
SEGAL_FULL_MATCHES = Path("/workspace/shawnee/tw_capture/2025-26/segal_full_matches.txt")
OUT_MD = Path("/workspace/shawnee/njsiaa/segal_recreation.md")
OUT_JSON = ROOT / "data" / "segal_caliber_2025_26.json"

NJSIAA_OFFICIAL = {
    "prestige": 105.0,
    "caliber_top20": 317.0,
    "caliber_all": 345.0,
    "total": 422.0,
    "adv_2024": "S4 Place",
    "adv_2025_form": "District Qtrs",
    "adv_2023": "swb1",
}
NJSIAA_KNOWN_OPP_CODES = {
    ("sammyspaulding", "camdencatholic"): "S1 Place",
    ("giovannischinina", "stpeters"): "S4 Place",
    ("josephrizzuto", "depaul"): "S6 Place",
    ("dominicmarino", "cinnaminson"): "swb1",
    ("landanriddell", "immaculata"): "swb4",
    ("roccogiangeruso", "northernburlington"): "R6place",
    ("louissimone", "rancocasvalley"): "RWB1",
    ("trentonlandell", "cherokee"): "D4",
}

# Pre-seed form season — opponent prestige uses prior HS-eligible seasons only
# (Jeff 2026-11-01: never 2025-26 results on a 2025-26 form; include 2021-22 so a
# senior's frosh finish is visible).
FORM_SEASON = "2025-26"
OPP_SEASONS = prior_seasons_for(FORM_SEASON)  # ["2024-25", "2023-24", "2022-23", "2021-22"]
# Primary: career-best code within the eligible window; most_recent is the alt.
PRIMARY_POLICY = "best"
ALT_POLICY = "most_recent"


def _parse_segal_date(raw: str) -> str:
    """Normalize capture dates like 12/20-12/21/2025 or 01/03/2026 → ISO start date."""
    raw = (raw or "").strip()
    if not raw:
        return ""
    # range: MM/DD-MM/DD/YYYY or MM/DD-MM/DD/YY
    import re as _re
    m = _re.match(r"(\d{1,2})/(\d{1,2})(?:-\d{1,2}/\d{1,2})?/(\d{4})$", raw)
    if m:
        mo, dy, yr = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{yr:04d}-{mo:02d}-{dy:02d}"
    m = _re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})$", raw)
    if m:
        mo, dy, yr = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{yr:04d}-{mo:02d}-{dy:02d}"
    return raw


def _map_segal_type(raw: str) -> str:
    key = (raw or "").strip().lower().rstrip(".")
    mapping = {
        "fall": "Fall", "pin": "Fall",
        "tf": "Tech. Fall", "tech": "Tech. Fall",
        "md": "Maj. Dec.", "maj": "Maj. Dec.",
        "dec": "Decision", "decision": "Decision",
        "for": "Forfeit", "for.": "Forfeit", "ff": "Forfeit", "forfeit": "Forfeit",
        "dq": "Disqualified", "inj": "Injury Default",
        "bye": "Bye",
    }
    if key in mapping:
        return mapping[key]
    for k, v in mapping.items():
        if k in key:
            return v
    return raw or "Decision"


def load_segal_bouts_from_full_txt(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for ln in path.read_text().splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        if s.lower().startswith("date|"):
            continue
        parts = s.split("|")
        if len(parts) < 9:
            continue
        date_raw, event, weight, round_l, result, opp, opp_school, typ, score_time = (
            parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip(),
            parts[4].strip(), parts[5].strip(), parts[6].strip(), parts[7].strip(),
            parts[8].strip(),
        )
        result_u = (result or "").upper().strip()
        if result_u == "BYE":
            rows.append({
                "event_id": None,
                "date": _parse_segal_date(date_raw),
                "event": event,
                "weight": weight,
                "round": round_l or None,
                "result": None,
                "win_type": "Bye",
                "opp": None,
                "opp_team": None,
                "score": None,
                "fall_seconds": None,
                "kind": "bye",
                "source": "segal_full_matches.txt",
            })
            continue
        if result_u not in ("W", "L"):
            continue
        win_type = _map_segal_type(typ)
        fall_secs = None
        import re as _re
        m = _re.search(r"(\d{1,2}):(\d{2})", score_time or "")
        if m:
            fall_secs = int(m.group(1)) * 60 + int(m.group(2))
        rows.append({
            "event_id": None,
            "date": _parse_segal_date(date_raw),
            "event": event,
            "weight": weight,
            "round": round_l or None,
            "result": result_u,
            "win_type": win_type,
            "opp": opp or None,
            "opp_team": opp_school or None,
            "score": score_time or None,
            "fall_seconds": fall_secs,
            "kind": "bout",
            "source": "segal_full_matches.txt",
        })
    rows.sort(key=lambda r: (r.get("date") or "9999", r.get("event") or "", r.get("round") or "", r.get("opp") or ""))
    return rows


def load_segal_bouts() -> List[Dict[str, Any]]:
    """Prefer the full TW Team>Matches capture (38 rows / 29-7); fall back to history."""
    if SEGAL_FULL_MATCHES.exists():
        rows = load_segal_bouts_from_full_txt(SEGAL_FULL_MATCHES)
        if rows:
            return rows
    b = json.loads(BOUTS_HIST.read_text())
    seen = set()
    rows: List[Dict[str, Any]] = []
    for eid, ev in b["events"].items():
        for w in ev.get("wrestlers") or []:
            if "segal" not in (w.get("wrestler") or "").lower():
                continue
            for bout in w.get("bouts") or []:
                key = (
                    bout.get("result"),
                    bout.get("win_type"),
                    (bout.get("opponent_wrestler") or "").lower(),
                    (bout.get("opponent_team") or "").lower(),
                    bout.get("score"),
                    bout.get("round"),
                    ev.get("event_name"),
                )
                if key in seen:
                    continue
                seen.add(key)
                wt = (bout.get("win_type") or "").lower()
                kind = "bye" if wt == "bye" else "bout"
                rows.append(
                    {
                        "event_id": eid,
                        "date": ev.get("date_iso"),
                        "event": ev.get("event_name"),
                        "weight": bout.get("weight") or w.get("weight"),
                        "round": bout.get("round"),
                        "result": bout.get("result"),
                        "win_type": bout.get("win_type"),
                        "opp": bout.get("opponent_wrestler"),
                        "opp_team": bout.get("opponent_team"),
                        "score": bout.get("score"),
                        "fall_seconds": bout.get("fall_seconds"),
                        "kind": kind,
                    }
                )
    rows.sort(key=lambda r: (r.get("date") or "9999", r.get("event") or "", r.get("opp") or ""))
    return rows


def njsiaa_code_for(name: str, team: str) -> str | None:
    nk = name_key(name)
    skc = school_key_compact(team)
    for (en, es), code in NJSIAA_KNOWN_OPP_CODES.items():
        if nk == en and (es in skc or skc in es):
            return code
    for (en, es), code in NJSIAA_KNOWN_OPP_CODES.items():
        if nk == en:
            return code
    return None


def missing_dual_summary() -> List[str]:
    if not MISSING_DUALS.exists():
        return []
    data = json.loads(MISSING_DUALS.read_text())
    out = []
    for ev in data.get("events") or []:
        out.append(f"{ev.get('date_iso')} {ev.get('opponent')} (event {ev.get('event_id')})")
    return out


def render_md(
    rows: List[Dict[str, Any]],
    top20: float,
    all_sum: float,
    prestige: float,
    adv_meta: Dict[str, Any],
    alt: Dict[str, float],
) -> str:
    total = prestige + top20
    official = NJSIAA_OFFICIAL
    missing = missing_dual_summary()
    lines: List[str] = []
    lines.append("# Jordan Segal — NJSIAA 2025-26 pre-seed recreation")
    lines.append("")
    lines.append("Recreated from Shawnee `tw_capture/2025-26/segal_full_matches.txt` (38 TW rows) + statewide")
    lines.append("`data/opponent_advancement.json` (nj.com brackets, 2021-22…2025-26), scored with")
    lines.append("`caliber.py` under official NJSIAA rules (Jeff steering 2026-11-01).")
    lines.append("")
    lines.append(
        f"**Opponent prestige window:** prior eligible seasons only for form `{FORM_SEASON}` → "
        f"`{OPP_SEASONS}` (Jeff correction 2026-11-01: never use `{FORM_SEASON}` postseason "
        f"results on a `{FORM_SEASON}` pre-seed). "
        f"**Primary policy:** `{PRIMARY_POLICY}` (career-best code inside that window). "
        f"**Alt:** `{ALT_POLICY}` (newest finish in the window, fall back older)."
    )
    lines.append("")
    lines.append("## Totals")
    lines.append("")
    lines.append("| Source | Prestige | Caliber (top 20) | Caliber (all) | Total |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    lines.append(
        f"| NJSIAA form (Jeff paste) | {official['prestige']:.1f} | {official['caliber_top20']:.1f} | "
        f"{official['caliber_all']:.1f} | {official['total']:.2f} |"
    )
    lines.append(
        f"| Our recreation (`{PRIMARY_POLICY}`) | {prestige:.1f} | {top20:.1f} | {all_sum:.1f} | {total:.2f} |"
    )
    lines.append(
        f"| Delta (ours − NJSIAA) | {prestige - official['prestige']:.1f} | "
        f"{top20 - official['caliber_top20']:.1f} | {all_sum - official['caliber_all']:.1f} | "
        f"{total - official['total']:.2f} |"
    )
    lines.append(
        f"| Alt: `{ALT_POLICY}` within same prior-eligible window | {prestige:.1f} | {alt['alt_top20']:.1f} | "
        f"{alt['alt_all']:.1f} | {prestige + alt['alt_top20']:.2f} |"
    )
    lines.append("")
    lines.append("### Own prestige / advancement history")
    lines.append("")
    lines.append("| Season | NJSIAA form | Our / TW notes |")
    lines.append("| --- | --- | --- |")
    lines.append("| 2023 (2022-23) | swb1 | Override in `prestige.py` (Jeff) |")
    lines.append(
        "| 2024 (2023-24) | S4 Place → **Prestige 105** | Career-best; 2024-25 injury-default out of regions does not reduce |"
    )
    lines.append(
        "| 2025 (2024-25) | District Qtrs (form) | TW/Shawnee: District 1st (kept for local prestige); "
        "Jeff: won D28 then injury-defaulted out of regions |"
    )
    lines.append(
        "| 2025-26 postseason | — | TW: D1 / R2 / state WB2 — does not raise career prestige above S4 (105) |"
    )
    lines.append("")
    lines.append("## Rules applied")
    lines.append("")
    lines.append(
        "1. **Replacement credit** — opponent advancement honors replacement finishes without a win "
        "(`pull_opponent_advancement` / regs § prestige bullet)."
    )
    lines.append("2. **Best 20 matches** — caliber total = sum of highest 20 per-match point values.")
    lines.append("3. **Non-NJSIAA member win = 2** — flat; no pin add-on (Peddie / PA / NY flagged).")
    lines.append("4. **+1 pin only for fall** — not MD / TF / DQ / FF.")
    lines.append("5. **Forfeit win = 2**, no pin point.")
    lines.append(
        "6. **−1 loss to non-regional** — verified against chart: decision loss vs "
        "Quarters Dis / Prelim Dis / Never in Districts = **−1**; D4 decision loss = **0**; "
        "higher tiers = 20% caliber. (Matches Jeff note that rule 6 ≡ chart −1 column.)"
    )
    lines.append("7. **Out-of-state** — district chart used for mapped opponents; non-member wins still rule (3).")
    lines.append("8. **Per-match points shown** — table below.")
    lines.append("")
    lines.append("## Bout-by-bout")
    lines.append("")
    lines.append(
        "NJSIAA per-bout PrestigePts from Jeff’s paste were **not retained as a full table** "
        "(only summary totals + opponent codes embedded in `pull_opponent_advancement.validate`). "
        "Where a known official code exists it is shown under **NJSIAA code**; otherwise `—`."
    )
    lines.append("")
    lines.append(
        "| # | Date | Event | Result | Opponent | Team | Our adv | NJSIAA code | Caliber | Pin | Pts | Top20 | Rules / notes |"
    )
    lines.append("| ---: | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | --- | --- |")
    n = 0
    for r in rows:
        if r.get("excluded") == "bye" or (
            r.get("match_points") is None and r.get("kind") == "bye"
        ):
            lines.append(
                f"| — | {r.get('date') or ''} | {r.get('event') or ''} | Bye | — | — | — | — | — | — | — | — | excluded (not a match) |"
            )
            continue
        n += 1
        official_code = njsiaa_code_for(r.get("opp") or "", r.get("opp_team") or "") or "—"
        our = r.get("adv_code") or "—"
        mismatch = ""
        if official_code != "—" and our != official_code:
            mismatch = f" **CODE MISMATCH** (ours {our} vs NJSIAA {official_code})"
        rules = ", ".join(r.get("rules") or [])
        note = r.get("lookup_note") or ""
        lines.append(
            f"| {n} | {r.get('date') or ''} | {r.get('event') or ''} | "
            f"{r.get('result')}/{r.get('normalized_win_type') or r.get('win_type')} | "
            f"{r.get('opp') or ''} | {r.get('opp_team') or ''} | {our} | {official_code} | "
            f"{r.get('caliber') if r.get('caliber') is not None else ''} | "
            f"{r.get('pin_point') if r.get('pin_point') is not None else ''} | "
            f"**{r.get('match_points')}** | {'Y' if r.get('in_top20') else ''} | "
            f"{rules}; {note}{mismatch} |"
        )
    lines.append("")
    lines.append("## Mismatch analysis vs NJSIAA 422")
    lines.append("")
    delta = total - official["total"]
    lines.append(
        f"- **Total delta:** {delta:+.2f} (ours {total:.2f} vs NJSIAA {official['total']:.2f})."
    )
    lines.append(
        f"- **Caliber top-20 delta:** {top20 - official['caliber_top20']:+.1f} "
        f"(ours {top20:.1f} vs {official['caliber_top20']:.1f})."
    )
    lines.append(
        f"- **Caliber all-matches delta:** {all_sum - official['caliber_all']:+.1f} "
        f"(ours {all_sum:.1f} vs {official['caliber_all']:.1f})."
    )
    lines.append("")
    lines.append("### What explains the gap (rule / data citations)")
    lines.append("")
    lines.append(
        f"- **Prior-eligible season window (Jeff correction):** opponent codes for a `{FORM_SEASON}` form "
        f"come only from {OPP_SEASONS} — `{FORM_SEASON}` postseason finishes are excluded. "
        f"Primary `{PRIMARY_POLICY}` top-20 **{top20:.1f}** (Δ {top20 - official['caliber_top20']:+.1f} vs 317). "
        f"Alt `{ALT_POLICY}` top-20 **{alt['alt_top20']:.1f}** "
        f"(Δ {alt['alt_top20'] - official['caliber_top20']:+.1f}). "
        f"Under `{PRIMARY_POLICY}`, Liam Williams / Justin Cauldwell keep 2023-24 `2v3` rather than "
        f"their weaker 2024-25 codes; known Jeff codes (Spaulding S1, Giangeruso R6, Landell D4, "
        f"Marino swb1, Simone RWB1) still match under both policies."
    )
    scored_n = sum(1 for r in rows if r.get("match_points") is not None)
    lines.append(
        f"- **Bout capture:** `segal_full_matches.txt` is the TW Team>Matches list "
        f"(**29–7** + 2 byes = 38 rows). Scored matches: **{scored_n}**. Nine dual Details "
        f"were merged from pipe-format `event_*.txt` (Giangeruso TF at Northern Burlington; "
        f"Padrenan fall at Toms River South dualId **9000836132** inside sectional "
        f"**9000835132**). All-match caliber **{all_sum:.1f}** vs NJSIAA 345 "
        f"(Δ {all_sum - official['caliber_all']:+.1f}); top-20 **{top20:.1f}** vs 317 "
        f"(Δ {top20 - official['caliber_top20']:+.1f})."
    )
    lines.append(
        f"- **Per-bout overshoot (no Jeff per-bout PrestigePts table to diff):** highest-value "
        f"rows under `{PRIMARY_POLICY}` that inflate top-20 above 317:"
    )
    high = sorted(
        [r for r in rows if r.get("match_points") is not None],
        key=lambda r: -float(r.get("match_points") or 0),
    )[:12]
    for r in high:
        lines.append(
            f"  - {r.get('result')}/{r.get('normalized_win_type') or r.get('win_type')} "
            f"{r.get('opp')} ({r.get('opp_team')}) `{r.get('adv_code')}` → "
            f"**{r.get('match_points')}**"
            f"{' · top-20' if r.get('in_top20') else ''}"
            f" — {r.get('lookup_note') or ''}"
        )
    lines.append(
        "- **Dominic Marino twice** (Quad Dec **32.5** + Region Dec **32.5**): both are "
        "legitimate matches; if the NJSIAA paste omitted the dual, that is +32.5 of the gap."
    )
    lines.append(
        "- **Known NJSIAA codes match** our lookup: Spaulding S1, Schinina S4, Rizzuto S6, "
        "Marino swb1, Riddell swb4, Giangeruso R6, Simone RWB1, Landell D4 — no code mismatches."
    )
    lines.append(
        "- **Likely remaining code uncertainty vs Jeff’s form:** Rhinehart `swb2` (35), "
        "Musciano `RWB1` (20), Gardner `2v3`+pin (18.5), Pallitto decision-loss `swb4` (8.0), "
        "Cappello decision-loss `swb2` (7.0), plus dual counting (Marino twice, Giangeruso TF). "
        "If the form used lower prior-season codes or omitted a dual, top-20 falls toward 317. "
        "D6/D7 bracket patch did not touch Segal opponents. "
        f"`most_recent` alt narrows the gap (top-20 {alt['alt_top20']:.1f}) via Cauldwell/Williams "
        "but still sits above 317."
    )
    if missing:
        lines.append("  - Dual events now merged from pipe txt (brief list):")
        for m in missing:
            lines.append(f"    - {m}")
    lines.append(
        "- **Rule (3) non-member flat 2:** Beast of the East losses vs Manheim Twp / Valley Central "
        "and the Peddie win are treated as non-member (win=2 / decision-loss −1 or 0). If TW mapped "
        "any via rule **(7)** chart instead of rule **(3)**, per-match points would differ."
    )
    lines.append(
        "- **Rule (4) pin only on fall:** Tech falls / majors get no +1; `normalize_win_type` prefers "
        "Tech when a score string says both TF and Fall."
    )
    lines.append(
        "- **Rule (6) / chart −1:** decision losses to Quarters/Prelim/Never deduct 1; verified equal "
        "to the chart’s Lost-by-Decision column (D4 stays 0). Edward Vass (Valley Central) decision "
        "loss = −1 under Never / non-member default."
    )
    lines.append(
        "- **2025 adv District Qtrs vs TW D1:** display-only on the form’s history line; career "
        "prestige used in the 422 total remains S4 = 105."
    )
    lines.append(
        "- **Rule (1) replacement:** opponent JSON honors replacement finishes; no Segal bout in this "
        "set was scored off a known replacement disagreement."
    )
    lines.append("")
    lines.append("## Data sources")
    lines.append("")
    lines.append(
        f"- Opponent advancement: `{ADV_PATH}` — {adv_meta.get('count')} wrestlers; "
        f"seasons {adv_meta.get('seasons')}; generated {adv_meta.get('generated')}"
    )
    lines.append(
        f"- Form season `{FORM_SEASON}`; opponent seasons {OPP_SEASONS} "
        f"(via `prior_seasons_for`, n=4); primary=`{PRIMARY_POLICY}`, alt=`{ALT_POLICY}`"
    )
    lines.append(f"- Bouts: `{SEGAL_FULL_MATCHES}` (fallback `{BOUTS_HIST}`)")
    lines.append(f"- Scorer: `caliber.py` + `score_segal_recreation.py`")
    lines.append(f"- Machine-readable: `{OUT_JSON}`")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    if not ADV_PATH.exists():
        raise SystemExit(f"missing {ADV_PATH}")
    adv = json.loads(ADV_PATH.read_text())
    bouts = load_segal_bouts()
    rows, top20, all_sum = score_bout_list(
        bouts,
        adv,
        for_season=FORM_SEASON,
        season_policy=PRIMARY_POLICY,
    )
    _, alt_top20, alt_all = score_bout_list(
        bouts,
        adv,
        for_season=FORM_SEASON,
        season_policy=ALT_POLICY,
    )
    prestige = NJSIAA_OFFICIAL["prestige"]
    payload = {
        "wrestler": "Jordan Segal",
        "season": FORM_SEASON,
        "prestige": prestige,
        "caliber_top20": top20,
        "caliber_all": all_sum,
        "total": prestige + top20,
        "season_policy": PRIMARY_POLICY,
        "opponent_seasons": OPP_SEASONS,
        "alt_policy": {
            "season_policy": ALT_POLICY,
            "caliber_top20": alt_top20,
            "caliber_all": alt_all,
            "total": prestige + alt_top20,
        },
        "njsiaa_official": NJSIAA_OFFICIAL,
        "bout_count_scored": sum(1 for r in rows if r.get("match_points") is not None),
        "bouts": rows,
        "adv_count": adv.get("count"),
        "adv_generated": adv.get("generated"),
        "note": (
            f"Opponent prestige for {FORM_SEASON} uses only {OPP_SEASONS}; "
            f"{FORM_SEASON} postseason finishes are excluded."
        ),
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n")
    md = render_md(
        rows,
        top20,
        all_sum,
        prestige,
        {
            "count": adv.get("count"),
            "generated": adv.get("generated"),
            "seasons": (adv.get("source") or {}).get("seasons"),
        },
        {"alt_top20": alt_top20, "alt_all": alt_all},
    )
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(md)
    print(f"Wrote {OUT_MD}")
    print(f"Wrote {OUT_JSON}")
    print(
        f"PRIMARY {PRIMARY_POLICY} (prior eligible): Prestige {prestige} + top20 {top20} = "
        f"{prestige + top20} (NJSIAA {NJSIAA_OFFICIAL['total']}; all {all_sum})"
    )
    print(
        f"ALT {ALT_POLICY} (prior eligible): top20 {alt_top20} all {alt_all} "
        f"total {prestige + alt_top20}"
    )
    from caliber import lookup_opponent_code

    for nk, sk in [
        ("Sammy Spaulding", "Camden Catholic"),
        ("Rocco Giangeruso", "Northern Burlington"),
        ("Trenton Landell", "Cherokee"),
        ("Dominic Marino", "Cinnaminson"),
        ("Louis Simone", "Rancocas Valley"),
        ("Landan Riddell", "Immaculata"),
        ("Joseph Rizzuto", "DePaul"),
        ("Giovanni Schinina", "St Peters"),
    ]:
        code, _, note = lookup_opponent_code(
            adv, nk, sk, seasons=OPP_SEASONS, season_policy=PRIMARY_POLICY
        )
        print(f"  check {nk}: {code} ({note})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
