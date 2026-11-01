#!/usr/bin/env python3
"""Recreate Jordan Segal 2025-26 NJSIAA pre-seed from Shawnee data + opponent_advancement."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from caliber import score_bout_list, name_key, school_key_compact

ROOT = Path(__file__).resolve().parent
ADV_PATH = ROOT / "data" / "opponent_advancement.json"
BOUTS_HIST = ROOT / "data" / "history" / "2025-26_bouts.json"
MISSING_DUALS = ROOT / "data" / "history" / "2025-26_missing_dual_captures.json"
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

# Prior 3 seasons for a 2025-26 form (newest first for most_recent policy)
OPP_SEASONS = ["2024-25", "2023-24", "2022-23"]
# Primary policy that lands near NJSIAA 317; best-across is sensitivity
PRIMARY_POLICY = "most_recent"


def load_segal_bouts() -> List[Dict[str, Any]]:
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
    lines.append("Recreated from Shawnee `data/history/2025-26_bouts.json` + statewide")
    lines.append("`data/opponent_advancement.json` (nj.com brackets, 2022-23…2025-26), scored with")
    lines.append("`caliber.py` under official NJSIAA rules (Jeff steering 2026-11-01).")
    lines.append("")
    lines.append(
        f"**Opponent code policy (primary):** `{PRIMARY_POLICY}` across prior seasons "
        f"{OPP_SEASONS} (newest first; fall back when an opponent has no finish in a newer season — "
        "e.g. Rocco Giangeruso R6place from 2023-24)."
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
        f"| Sensitivity: best across same 3 seasons | {prestige:.1f} | {alt['best_top20']:.1f} | "
        f"{alt['best_all']:.1f} | {prestige + alt['best_top20']:.2f} |"
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
        f"- **Season-window policy (data interpretation, not rules 1–8):** "
        f"`most_recent` prior season with fallback through {OPP_SEASONS} yields top-20 **{top20:.1f}** "
        f"(Δ {top20 - official['caliber_top20']:+.1f} vs 317). Taking the **best** code across the same "
        f"three seasons instead yields top-20 **{alt['best_top20']:.1f}** "
        f"(Δ {alt['best_top20'] - official['caliber_top20']:+.1f}) — e.g. Liam Williams stays 2v3 "
        f"(2023-24) instead of D4 (2024-25), Justin Cauldwell stays 2v3 instead of Quarters Dis. "
        f"Jeff’s pasted codes (Spaulding S1, Giangeruso R6, Landell D4, Marino swb1, Simone RWB1) "
        f"are consistent with most-recent-with-fallback, not pure same-season-only and not always "
        f"career-max."
    )
    lines.append(
        "- **Incomplete Shawnee bout capture (data gap):** roster/stats show Segal **29–7**; this "
        f"recreation scores **{sum(1 for r in rows if r.get('match_points') is not None)}** matches "
        f"(~22–7 after bye exclusion). Missing dual Schedule Details are listed in "
        "`data/history/2025-26_missing_dual_captures.json`, including **Northern Burlington** "
        "(Jeff’s form lists Rocco Giangeruso / R6place — not in our bout JSON yet). All-match "
        f"caliber here is {all_sum:.1f} vs NJSIAA 345; the ~{official['caliber_all'] - all_sum:.1f} "
        "gap on all-matches is largely those missing duals (Giangeruso alone is 22.5 on a win). "
        "Rules **(2)** and **(8)** still apply to matches we have."
    )
    if missing:
        lines.append("  - Missing dual events:")
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
        f"- Opponent seasons / policy for this recreation: {OPP_SEASONS}, policy=`{PRIMARY_POLICY}`"
    )
    lines.append(f"- Bouts: `{BOUTS_HIST}`")
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
        seasons_for_opp=OPP_SEASONS,
        season_policy=PRIMARY_POLICY,
    )
    _, best_top20, best_all = score_bout_list(
        bouts,
        adv,
        seasons_for_opp=OPP_SEASONS,
        season_policy="best",
    )
    prestige = NJSIAA_OFFICIAL["prestige"]
    payload = {
        "wrestler": "Jordan Segal",
        "season": "2025-26",
        "prestige": prestige,
        "caliber_top20": top20,
        "caliber_all": all_sum,
        "total": prestige + top20,
        "season_policy": PRIMARY_POLICY,
        "opponent_seasons": OPP_SEASONS,
        "sensitivity_best_across": {
            "caliber_top20": best_top20,
            "caliber_all": best_all,
            "total": prestige + best_top20,
        },
        "njsiaa_official": NJSIAA_OFFICIAL,
        "bout_count_scored": sum(1 for r in rows if r.get("match_points") is not None),
        "bouts": rows,
        "adv_count": adv.get("count"),
        "adv_generated": adv.get("generated"),
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
        {"best_top20": best_top20, "best_all": best_all},
    )
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(md)
    print(f"Wrote {OUT_MD}")
    print(f"Wrote {OUT_JSON}")
    print(
        f"PRIMARY {PRIMARY_POLICY}: Prestige {prestige} + top20 {top20} = {prestige + top20} "
        f"(NJSIAA {NJSIAA_OFFICIAL['total']}; all {all_sum})"
    )
    print(
        f"SENSITIVITY best: top20 {best_top20} all {best_all} total {prestige + best_top20}"
    )
    # verify known codes under most_recent
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
