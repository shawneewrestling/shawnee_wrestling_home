#!/usr/bin/env python3
"""Reusable Trackwrestling pull — season-agnostic.

Modes:
  ids         Discover / verify seasonId, gbId, Shawnee teamId
  preseason   Roster + published schedule
  postseason  Final dual results + (from captures) bouts / win-types / placements
  probe       Report what works server-side from this box
  diff        Compare dry-run vs data/wrestling_data.json

Usage:
  python tw_pull.py probe --season 2025-26 --dry-run
  python tw_pull.py ids --season 2026-27 --season-id 95515140 --save-config
  python tw_pull.py preseason --season 2025-26 --dry-run
  python tw_pull.py postseason --season 2025-26 --dry-run
  python tw_pull.py diff --season 2025-26

See docs/TW_PULL.md for browser capture steps.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from season_config import (  # noqa: E402
    CURRENT_SEASON,
    load_season,
    save_season_config,
    list_seasons,
)
from tw.client import (  # noqa: E402
    TwClient,
    TwClientError,
    schedule_url,
    roster_url,
    statistics_url,
    event_matches_url,
)
from tw.parsers import (  # noqa: E402
    parse_schedule_rows,
    parse_wrestlers,
    find_shawnee_team,
    find_nj_gb,
    build_dual_scores,
    parse_win_types_capture,
    merge_win_types_into_roster,
    parse_placements_capture,
    now_est_iso,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("tw_pull")

BOX_DRYRUN = Path("/workspace/shawnee/dryrun")
BOX_CAPTURE = Path("/workspace/shawnee/tw_capture")
DEFAULT_EVENT_CAPTURES = Path("/workspace/shawnee/tw_event_pages")


def _out_dir(season: str, dry_run: bool) -> Path:
    d = (BOX_DRYRUN / season) if dry_run else (ROOT / "data" / "seasons" / season / "tw_pull")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")
    logger.info("Wrote %s", path)


def cmd_probe(args: argparse.Namespace) -> int:
    cfg = load_season(args.season)
    client = TwClient(cfg["season_id"], cfg.get("team_id") or None, cfg["gb_id"])
    report = client.probe_server_side()
    _write(_out_dir(args.season, args.dry_run) / "probe.json", report)
    print(json.dumps(report, indent=2))
    return 0


def cmd_ids(args: argparse.Namespace) -> int:
    season = args.season
    season_id = args.season_id
    if not season_id:
        try:
            season_id = load_season(season)["season_id"]
        except KeyError:
            print(
                f"No season_id for {season}. Pass --season-id (from TW season list)\n"
                f"or follow docs/TW_PULL.md § Discovering season IDs.",
                file=sys.stderr,
            )
            return 2

    client = TwClient(season_id, team_id=None, gb_id=args.gb_id or "36")
    client.mint_session(page_name="TeamSchedule.jsp")
    gbs = client.get_season_gbs()
    nj = find_nj_gb(gbs)
    gb_id = str((nj or {}).get("gb_id") or args.gb_id or "36")
    client.gb_id = gb_id
    teams = client.get_teams(gb_id=gb_id)
    hit = find_shawnee_team(teams, school="Shawnee", city_hint="Medford")
    result = {
        "season": season,
        "season_id": season_id,
        "gb_id": gb_id,
        "gb_name": (nj or {}).get("name"),
        "team": hit,
        "teams_scanned": len(teams),
        "schedule_url": schedule_url(season_id, hit["team_id"], gb_id) if hit else None,
        "roster_url": roster_url(season_id, hit["team_id"], gb_id) if hit else None,
        "discovered_at": now_est_iso(),
        "method": "server-side getSeasonGBs + getTeams (non-Chrome UA)",
        "season_id_source": (
            "provided --season-id or config.json — TW has no public getSeasons Ajax; "
            "browser discovery documented in docs/TW_PULL.md"
        ),
    }
    _write(_out_dir(season, args.dry_run) / "ids.json", result)
    if hit and args.save_config:
        path = save_season_config(
            season,
            season_id=season_id,
            team_id=hit["team_id"],
            gb_id=gb_id,
            gb_name=(nj or {}).get("name"),
            school="Shawnee",
            school_search=["Shawnee", "Medford"],
            city=hit.get("city"),
        )
        logger.info("Saved config %s", path)
    print(json.dumps({
        "season": season,
        "season_id": season_id,
        "gb_id": gb_id,
        "team_id": (hit or {}).get("team_id"),
        "team_name": (hit or {}).get("name"),
        "city": (hit or {}).get("city"),
        "district_region": (hit or {}).get("district_region"),
        "teams_scanned": len(teams),
    }, indent=2))
    return 0 if hit else 1


def _pull_core(cfg: Dict[str, Any]) -> Dict[str, Any]:
    client = TwClient(cfg["season_id"], cfg["team_id"], cfg["gb_id"])
    client.mint_session()
    raw_sched = client.get_team_schedule()
    raw_wrest = client.get_wrestlers()
    schedule = parse_schedule_rows(raw_sched)
    roster = parse_wrestlers(raw_wrest)
    dual = build_dual_scores(schedule)
    return {
        "metadata": {
            "team": "Shawnee High School",
            "nickname": "Renegades",
            "season": cfg["season"],
            "season_id": cfg["season_id"],
            "team_id": cfg["team_id"],
            "gb_id": cfg["gb_id"],
            "dual_record": dual.get("record"),
            "generated_at": now_est_iso(),
            "timezone": "America/New_York",
            "sources": {
                "schedule": "Trackwrestling getTeamSchedule (server-side Ajax)",
                "roster_stats": "Trackwrestling getWrestlers (server-side Ajax)",
            },
            "gaps": [
                "Pins/tech/major require Win Types capture (docs/TW_PULL.md)",
                "Bout-level dual grids require EventMatches HTML captures",
                "NJSIAA placements require District/Region/State captures or paste",
            ],
        },
        "roster": roster,
        "schedule": schedule,
        "dual_scores": dual,
        "stats": [
            {
                "wrestler_id": w.get("wrestler_id"),
                "name": w.get("name"),
                "weight": w.get("weight"),
                "grade": w.get("grade"),
                "wins": w.get("wins") or 0,
                "losses": w.get("losses") or 0,
                "pins": w.get("pins"),
                "tech_falls": w.get("tech_falls"),
                "major_decisions": w.get("major_decisions"),
                "decisions": w.get("decisions"),
            }
            for w in roster
        ],
        "_raw_counts": {
            "schedule_ajax": len(raw_sched),
            "wrestlers_ajax": len(raw_wrest),
        },
        "_raw_schedule": raw_sched,
        "_raw_wrestlers": raw_wrest,
    }


def cmd_preseason(args: argparse.Namespace) -> int:
    cfg = load_season(args.season)
    if not cfg.get("team_id"):
        logger.error("No team_id — run ids mode first")
        return 2
    data = _pull_core(cfg)
    data["metadata"]["mode"] = "preseason"
    out = _out_dir(args.season, args.dry_run)
    raw_counts = data.pop("_raw_counts", {})
    raw_sched = data.pop("_raw_schedule", None)
    raw_wrest = data.pop("_raw_wrestlers", None)
    _write(out / "wrestling_data.json", data)
    _write(out / "roster.json", data["roster"])
    _write(out / "schedule.json", data["schedule"])
    if args.save_raw:
        _write(out / "raw_schedule.json", raw_sched)
        _write(out / "raw_wrestlers.json", raw_wrest)
    summary = {
        "mode": "preseason",
        "season": args.season,
        "roster": len(data["roster"]),
        "schedule_events": len(data["schedule"]),
        "dual_record": data["dual_scores"]["record"],
        "ajax_counts": raw_counts,
        "dry_run": args.dry_run,
        "out": str(out),
    }
    _write(out / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0


def _load_captures(capture_dir: Path) -> Dict[str, Any]:
    out: Dict[str, Any] = {"win_types": [], "placements": [], "files": []}
    if not capture_dir.exists():
        return out
    for p in sorted(capture_dir.iterdir()):
        if not p.is_file():
            continue
        out["files"].append(p.name)
        text = p.read_text(encoding="utf-8", errors="ignore")
        name = p.name.lower()
        if "win_type" in name or "wintype" in name or name.startswith("report_win"):
            out["win_types"].extend(parse_win_types_capture(text))
        elif "district" in name:
            out["placements"].extend(parse_placements_capture(text, "district"))
        elif "region" in name:
            out["placements"].extend(parse_placements_capture(text, "region"))
        elif "state" in name:
            out["placements"].extend(parse_placements_capture(text, "state"))
        elif "sectional" in name:
            out["placements"].extend(parse_placements_capture(text, "sectional"))
    return out


def cmd_postseason(args: argparse.Namespace) -> int:
    cfg = load_season(args.season)
    if not cfg.get("team_id"):
        logger.error("No team_id — run ids mode first")
        return 2
    data = _pull_core(cfg)
    data["metadata"]["mode"] = "postseason"

    capture_dir = Path(args.capture_dir) if args.capture_dir else BOX_CAPTURE / args.season
    caps = _load_captures(capture_dir)
    if caps["win_types"]:
        data["roster"] = merge_win_types_into_roster(data["roster"], caps["win_types"])
        data["stats"] = [
            {
                "wrestler_id": w.get("wrestler_id"),
                "name": w.get("name"),
                "weight": w.get("weight"),
                "grade": w.get("grade"),
                "wins": w.get("wins") or 0,
                "losses": w.get("losses") or 0,
                "pins": w.get("pins"),
                "tech_falls": w.get("tech_falls"),
                "major_decisions": w.get("major_decisions"),
                "decisions": w.get("decisions"),
            }
            for w in data["roster"]
        ]
        data["metadata"]["sources"]["win_types"] = str(capture_dir)
        data["metadata"]["gaps"] = [g for g in data["metadata"]["gaps"] if "Pins/tech" not in g]

    data["placements"] = caps["placements"]
    if caps["placements"]:
        data["metadata"]["sources"]["placements"] = str(capture_dir)
        data["metadata"]["gaps"] = [g for g in data["metadata"]["gaps"] if "placements" not in g]

    try:
        from tournament_results import attach_tournament_results, index_captures
        event_dir = Path(args.event_capture_dir) if args.event_capture_dir else DEFAULT_EVENT_CAPTURES
        if event_dir.exists():
            attach_tournament_results(data, capture_dir=event_dir)
            data["metadata"]["sources"]["bouts"] = str(event_dir)
            data["metadata"]["gaps"] = [g for g in data["metadata"]["gaps"] if "Bout-level" not in g]
            data["metadata"]["event_captures_indexed"] = len(index_captures(event_dir))
    except Exception as e:
        logger.warning("tournament_results attach skipped: %s", e)

    out = _out_dir(args.season, args.dry_run)
    raw_counts = data.pop("_raw_counts", {})
    raw_sched = data.pop("_raw_schedule", None)
    raw_wrest = data.pop("_raw_wrestlers", None)
    _write(out / "wrestling_data.json", data)
    _write(out / "roster.json", data["roster"])
    _write(out / "schedule.json", data["schedule"])
    _write(out / "dual_scores.json", data["dual_scores"])
    _write(out / "stats.json", data["stats"])
    _write(out / "placements.json", data.get("placements") or [])
    if args.save_raw:
        _write(out / "raw_schedule.json", raw_sched)
        _write(out / "raw_wrestlers.json", raw_wrest)
    _write(out / "capture_index.json", {
        "capture_dir": str(capture_dir),
        "files": caps["files"],
        "win_types_rows": len(caps["win_types"]),
        "placements_rows": len(caps["placements"]),
    })

    scored_events = [
        m for m in data["schedule"]
        if m.get("event_id") and (m.get("score_shawnee") is not None or m.get("home_away") == "event")
    ]
    checklist = {
        "season": args.season,
        "season_id": cfg["season_id"],
        "team_id": cfg["team_id"],
        "gb_id": cfg["gb_id"],
        "pages": [
            {
                "id": "roster",
                "url": roster_url(cfg["season_id"], cfg["team_id"], cfg["gb_id"]),
                "save_as": f"tw_capture/{args.season}/roster.html",
            },
            {
                "id": "schedule",
                "url": schedule_url(cfg["season_id"], cfg["team_id"], cfg["gb_id"]),
                "save_as": f"tw_capture/{args.season}/schedule.html",
            },
            {
                "id": "statistics_list",
                "url": statistics_url(cfg["season_id"], cfg["team_id"], cfg["gb_id"]),
                "save_as": f"tw_capture/{args.season}/statistics.html",
                "then": "Open report 'Win Types by Wrestler' → save as win_types.html",
            },
        ],
        "events": [
            {
                "event_id": m["event_id"],
                "event_name": m.get("event_name"),
                "date_iso": m.get("date_iso"),
                "url": event_matches_url(cfg["season_id"], m["event_id"], cfg["gb_id"]),
                "save_as": f"tw_capture/{args.season}/event_{m['event_id']}.html",
            }
            for m in scored_events
        ],
        "njsiaa": [
            {"id": "district", "save_as": f"tw_capture/{args.season}/placements_district.txt"},
            {"id": "region", "save_as": f"tw_capture/{args.season}/placements_region.txt"},
            {"id": "state", "save_as": f"tw_capture/{args.season}/placements_state.txt"},
        ],
    }
    _write(out / "capture_checklist.json", checklist)

    summary = {
        "mode": "postseason",
        "season": args.season,
        "roster": len(data["roster"]),
        "schedule_events": len(data["schedule"]),
        "dual_record": data["dual_scores"]["record"],
        "duals_scored": len(data["dual_scores"]["duals"]),
        "pins_populated": sum(1 for s in data["stats"] if s.get("pins") is not None),
        "placements": len(data.get("placements") or []),
        "tournament_results": len(data.get("tournament_results") or {}),
        "ajax_counts": raw_counts,
        "dry_run": args.dry_run,
        "out": str(out),
        "gaps": data["metadata"].get("gaps"),
    }
    _write(out / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    dry = BOX_DRYRUN / args.season / "wrestling_data.json"
    live = ROOT / "data" / "wrestling_data.json"
    if not dry.exists():
        logger.error("Missing %s — run preseason/postseason --dry-run first", dry)
        return 2
    a = json.loads(dry.read_text())
    b = json.loads(live.read_text()) if live.exists() else {}

    def names(roster):
        return sorted({(w.get("name") or "").strip() for w in roster or [] if w.get("name")})

    def dual_key(d):
        return (d.get("date_iso"), d.get("opponent"), d.get("shawnee"), d.get("opp"), d.get("result"))

    a_duals = {dual_key(d) for d in (a.get("dual_scores") or {}).get("duals") or []}
    b_duals = {dual_key(d) for d in (b.get("dual_scores") or {}).get("duals") or []}

    report = {
        "season": args.season,
        "dry_roster": len(a.get("roster") or []),
        "live_roster": len(b.get("roster") or []),
        "roster_only_dry": sorted(set(names(a.get("roster"))) - set(names(b.get("roster")))),
        "roster_only_live": sorted(set(names(b.get("roster"))) - set(names(a.get("roster")))),
        "dry_schedule_events": len(a.get("schedule") or []),
        "live_schedule_events": len(b.get("schedule") or []),
        "dry_dual_record": (a.get("dual_scores") or {}).get("record"),
        "live_dual_record": (b.get("dual_scores") or {}).get("record")
            or (b.get("metadata") or {}).get("dual_record"),
        "duals_only_dry": [list(x) for x in sorted(a_duals - b_duals)],
        "duals_only_live": [list(x) for x in sorted(b_duals - a_duals)],
        "dry_event_ids": sorted({m.get("event_id") for m in a.get("schedule") or [] if m.get("event_id")}),
        "live_event_ids": sorted({m.get("event_id") for m in b.get("schedule") or [] if m.get("event_id")}),
    }
    report["event_ids_only_dry"] = sorted(set(report["dry_event_ids"]) - set(report["live_event_ids"]))
    report["event_ids_only_live"] = sorted(set(report["live_event_ids"]) - set(report["dry_event_ids"]))
    _write(BOX_DRYRUN / args.season / "diff_vs_live.json", report)
    print(json.dumps(report, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Shawnee Trackwrestling pull")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--season", default=CURRENT_SEASON)
    common.add_argument("--dry-run", action="store_true")
    common.add_argument("--save-raw", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("probe", parents=[common]); p.set_defaults(func=cmd_probe)

    p = sub.add_parser("ids", parents=[common])
    p.add_argument("--season-id", default=None)
    p.add_argument("--gb-id", default="36")
    p.add_argument("--save-config", action="store_true")
    p.set_defaults(func=cmd_ids)

    p = sub.add_parser("preseason", parents=[common]); p.set_defaults(func=cmd_preseason)

    p = sub.add_parser("postseason", parents=[common])
    p.add_argument("--capture-dir", default=None)
    p.add_argument("--event-capture-dir", default=None)
    p.set_defaults(func=cmd_postseason)

    p = sub.add_parser("diff", parents=[common]); p.set_defaults(func=cmd_diff)

    p = sub.add_parser("list-seasons", parents=[common])
    def _list(args):
        print(json.dumps({
            k: {"season_id": v["season_id"], "team_id": v["team_id"], "gb_id": v["gb_id"]}
            for k, v in list_seasons().items()
        }, indent=2))
        return 0
    p.set_defaults(func=_list)
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
