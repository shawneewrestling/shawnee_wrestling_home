#!/usr/bin/env python3
"""
Single update script for Shawnee Wrestling site-v2.

1) Run hybrid TW scraper → data/wrestling_data.json (+ root mirror)
2) Detect auto-awards from season data → merge into data/awards.json
3) Append season-aggregate career events with source_event_id dedupe
4) Varsity assignments (one per NJSIAA weight) + Jotform options + prestige + player pages
5) Write data/build_summary.json

Does NOT deploy, does NOT touch main. Safe to run on a feature branch.

Usage:
  python update_site_data.py
  python update_site_data.py --skip-scrape   # rebuild awards/career from existing wrestling_data.json
  python update_site_data.py --seed /path/to/awards_seed.json
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from career import apply_season_aggregate, load_career, save_career  # noqa: E402
from auto_awards import detect_season_awards, merge_awards  # noqa: E402
from varsity import build_varsity  # noqa: E402
from varsity_assignments import (  # noqa: E402
    build_varsity_assignments,
    build_jotform_options,
)
from players_build import build_players  # noqa: E402
from prestige import build_prestige_index  # noqa: E402
from schedule_enrich import enrich_schedule  # noqa: E402
from tournament_results import attach_tournament_results  # noqa: E402
from results_ledger import (  # noqa: E402
    build_and_apply,
    assert_consistent,
    LedgerConsistencyError,
    LEDGER_PATH,
)
from conference_standings import (  # noqa: E402
    build_standings,
    sync_external_ref_conference_opponents,
    StandingsConsistencyError,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("update_site_data")
EST = ZoneInfo("America/New_York")


def now_est() -> str:
    t = datetime.now(EST)
    s = t.strftime("%Y-%m-%dT%H:%M:%S%z")
    return s[:-2] + ":" + s[-2:]


def run_scraper(out: Path) -> dict:
    import asyncio
    from scraper_hybrid import scrape
    from season_config import TEAM_ID, SEASON_ID, GB_ID

    logos = ROOT / "data" / "logos.json"
    data = asyncio.run(scrape(TEAM_ID, SEASON_ID, str(GB_ID), logos))
    data.pop("_raw_counts", None)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2) + "\n")
    (ROOT / "wrestling_data.json").write_text(json.dumps(data, indent=2) + "\n")
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-scrape", action="store_true")
    ap.add_argument("--seed", default=str(Path("/workspace/shawnee/awards_seed.json")))
    ap.add_argument("--out-data", default=str(ROOT / "data" / "wrestling_data.json"))
    args = ap.parse_args()

    data_path = Path(args.out_data)
    if args.skip_scrape:
        data = json.loads(data_path.read_text())
        logger.info("Loaded existing %s", data_path)
    else:
        logger.info("Running hybrid scraper…")
        data = run_scraper(data_path)


    # Enrich schedule: split multi-team duals, logos, tournament bout cards
    attach_tournament_results(data)
    data = enrich_schedule(data)
    # Rebuild canonical results ledger (all dual listings) and fail loudly if
    # overall / conference / dual-count disagree with external validation refs.
    try:
        ledger, data = build_and_apply(data, write=True, strict=True)
        assert_consistent(LEDGER_PATH)
        logger.info(
            "Results ledger: duals=%d overall=%s conference=%s discrepancies=%d",
            ledger["summary"]["overall"]["count"],
            ledger["summary"]["overall"]["record"],
            ledger["summary"]["conference"]["record"],
            ledger["validation"]["discrepancy_count"],
        )
    except LedgerConsistencyError as e:
        # Persist whatever we have so the failure is inspectable, then abort.
        data_path.write_text(json.dumps(data, indent=2) + "\n")
        (ROOT / "wrestling_data.json").write_text(json.dumps(data, indent=2) + "\n")
        logger.error("RESULTS LEDGER CONSISTENCY FAILED — refusing to continue update")
        logger.error("%s", e)
        raise SystemExit(2) from e
    data_path.write_text(json.dumps(data, indent=2) + "\n")
    (ROOT / "wrestling_data.json").write_text(json.dumps(data, indent=2) + "\n")
    (ROOT / "data" / "tournament_results.json").write_text(
        json.dumps(data.get("tournament_results") or {}, indent=2) + "\n"
    )
    logger.info(
        "Enrichment: schedule=%d splits=%d tournament_events=%d dual_record=%s",
        len(data.get("schedule") or []),
        len((data.get("enrichment") or {}).get("splits") or []),
        len(data.get("tournament_results") or {}),
        (data.get("dual_scores") or {}).get("record"),
    )

    # Olympic Conference standings (all OC teams by division). GoBound preferred;
    # NJ.com fallback when GoBound bwr standings are blocked. Validates Shawnee vs ledger.
    try:
        standings_doc = build_standings(write=True, strict=True)
        sync_external_ref_conference_opponents(standings_doc)
        logger.info(
            "Conference standings: source=%s as_of=%s shawnee=%s/%s gaps=%s",
            standings_doc.get("source"),
            standings_doc.get("as_of"),
            (standings_doc.get("validation") or {}).get("shawnee_row", {}).get("overall_record"),
            (standings_doc.get("validation") or {}).get("shawnee_row", {}).get("division_record"),
            standings_doc.get("gaps"),
        )
    except StandingsConsistencyError as e:
        logger.error("CONFERENCE STANDINGS VALIDATION FAILED — refusing to continue update")
        logger.error("%s", e)
        raise SystemExit(2) from e

    seed_path = Path(args.seed)
    if seed_path.exists():
        seed_doc = json.loads(seed_path.read_text())
        seed = seed_doc.get("awards") or seed_doc
    else:
        logger.warning("Seed not found at %s — keeping existing awards body", seed_path)
        seed = json.loads((ROOT / "data" / "awards.json").read_text()).get("awards", [])
        seed = [a for a in seed if not a.get("auto_detected")]

    derived = detect_season_awards(data)
    awards_doc = merge_awards(seed, derived, seed_source=str(seed_path))
    awards_path = ROOT / "data" / "awards.json"
    # AWARDS_CHEVRON_CHROME_LOCKED: never write styles.css / awards header chrome here.
    awards_path.write_text(json.dumps(awards_doc, indent=2) + "\n")
    logger.info("Awards: %d total (%d seed + %d derived)", awards_doc["seed_count"] + awards_doc["derived_2025_26_count"], awards_doc["seed_count"], awards_doc["derived_2025_26_count"])

    # Varsity roster (dual appearances + overrides)
    appearances = {}
    ap = ROOT / "data" / "dual_appearances.json"
    if ap.exists():
        appearances = json.loads(ap.read_text())
    overrides = {}
    ov = ROOT / "data" / "varsity_overrides.json"
    if ov.exists():
        overrides = json.loads(ov.read_text())
    varsity_doc = build_varsity(data, appearances, overrides)
    (ROOT / "data" / "varsity.json").write_text(json.dumps(varsity_doc, indent=2) + "\n")
    logger.info("Varsity: %d (%s)", varsity_doc.get("counts", {}).get("total"), varsity_doc.get("derivation"))

    # One-per-weight assignments + Jotform dropdown options + player pages
    jot = {}
    jot_path = ROOT / "data" / "varsity_jotform_overrides.json"
    if jot_path.exists():
        jot = json.loads(jot_path.read_text())
    assign_doc = build_varsity_assignments(data, appearances, overrides, awards_doc, jot or None)
    (ROOT / "data" / "varsity_assignments.json").write_text(json.dumps(assign_doc, indent=2) + "\n")
    logger.info(
        "Varsity assignments: %d filled / %d vacant",
        assign_doc.get("counts", {}).get("filled"),
        assign_doc.get("counts", {}).get("vacant"),
    )
    opts = build_jotform_options(data.get("roster") or [])
    (ROOT / "data" / "jotform_roster_options.json").write_text(json.dumps(opts, indent=2) + "\n")
    season_label = (data.get("metadata") or {}).get("season")
    prest_doc = build_prestige_index(data.get("roster") or [], awards_doc, season_label)
    (ROOT / "data" / "prestige.json").write_text(json.dumps(prest_doc, indent=2) + "\n")

    career = load_career(ROOT / "data" / "career.json")
    career = apply_season_aggregate(career, data)
    save_career(ROOT / "data" / "career.json", career)

    players_index = build_players(data, awards_doc, assign_doc, career)
    logger.info("Player pages: %d", players_index.get("count"))

    summary = {
        "built_at": now_est(),
        "branch_target": "site-v2-2025-26-closeout",
        "counts": {
            "roster": len(data.get("roster") or []),
            "schedule": len(data.get("schedule") or []),
            "scored_duals": len((data.get("dual_scores") or {}).get("duals") or []),
            "awards_total": len(awards_doc.get("awards") or []),
            "awards_derived_2025_26": awards_doc.get("derived_2025_26_count"),
            "logos": len(json.loads((ROOT / "data" / "logos.json").read_text())) if (ROOT / "data" / "logos.json").exists() else 0,
            "varsity": (varsity_doc.get("counts") or {}).get("total"),
            "varsity_assignments_filled": (assign_doc.get("counts") or {}).get("filled"),
            "player_pages": players_index.get("count"),
        },
        "dual_record": (data.get("dual_scores") or {}).get("record") or data.get("metadata", {}).get("dual_record"),
        "conference_record": (data.get("dual_scores") or {}).get("conference_record"),
        "ledger_duals": len((data.get("dual_scores") or {}).get("duals") or []),
        "ledger_discrepancies": (json.loads((ROOT / "data" / "results_ledger.json").read_text()).get("validation") or {}).get("discrepancy_count") if (ROOT / "data" / "results_ledger.json").exists() else None,
        "conference_standings_source": (json.loads((ROOT / "data" / "standings.json").read_text()).get("source") if (ROOT / "data" / "standings.json").exists() else None),
        "conference_standings_as_of": (json.loads((ROOT / "data" / "standings.json").read_text()).get("as_of") if (ROOT / "data" / "standings.json").exists() else None),
        "ids": {
            "team_id": data.get("metadata", {}).get("team_id"),
            "season_id": data.get("metadata", {}).get("season_id"),
        },
    }
    (ROOT / "data" / "build_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    logger.info("Summary: %s", summary)


if __name__ == "__main__":
    main()
