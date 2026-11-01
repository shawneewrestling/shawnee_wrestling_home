#!/usr/bin/env python3
"""Canonical dual-meet results ledger for Shawnee Wrestling.

Every scored dual listing (including duals split out of tri/quad meets and
team-tournament duals) becomes one ledger row. Overall / conference / home /
away records are computed ONLY from this ledger. Schedule UI, standings, and
home cards must read the ledger-backed dual_scores block — never a TW
event_kind filter alone.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from school_aliases import lookup_logo, load_logos_map, resolve_school

logger = logging.getLogger("results_ledger")
ROOT = Path(__file__).resolve().parent
EST = ZoneInfo("America/New_York")

LEDGER_PATH = ROOT / "data" / "results_ledger.json"
EXTERNAL_REF_PATH = ROOT / "data" / "results_external_ref.json"


def _now() -> str:
    t = datetime.now(EST)
    s = t.strftime("%Y-%m-%dT%H:%M:%S%z")
    return s[:-2] + ":" + s[-2:]


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _slug_key(name: str) -> str:
    slug, disp = resolve_school(name)
    return slug or _norm(name)


def result_from_scores(shawnee: Any, opp: Any) -> Optional[str]:
    try:
        s, o = int(shawnee), int(opp)
    except (TypeError, ValueError):
        return None
    if s > o:
        return "W"
    if s < o:
        return "L"
    return "T"


def load_external_ref(path: Path | None = None) -> Dict[str, Any]:
    path = path or EXTERNAL_REF_PATH
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _match_external(row: Dict[str, Any], ext_duals: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    date = row.get("date_iso")
    key = _slug_key(row.get("opponent") or "")
    for e in ext_duals:
        if e.get("date_iso") != date:
            continue
        if _slug_key(e.get("opponent") or "") == key:
            return e
    same_day = [e for e in ext_duals if e.get("date_iso") == date]
    for e in same_day:
        if _norm(e.get("opponent") or "")[:6] == _norm(row.get("opponent") or "")[:6]:
            return e
    return None


def build_ledger_rows(
    data: Dict[str, Any],
    *,
    external: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """One row per scored dual listing on the enriched schedule."""
    logos_map = load_logos_map(ROOT / "data" / "logos.json")
    external = external if external is not None else load_external_ref()
    ext_duals = list(external.get("duals") or [])
    conf_set = {_slug_key(x) for x in (external.get("conference_opponents") or [])}
    tr = data.get("tournament_results") or {}

    rows: List[Dict[str, Any]] = []
    seen = set()

    for m in data.get("schedule") or []:
        if m.get("score_shawnee") is None or not m.get("opponent"):
            continue
        eid = str(m.get("event_id") or "")
        opp = m.get("opponent")
        key = (m.get("date_iso"), _slug_key(opp), eid)
        if key in seen:
            continue
        seen.add(key)

        shawnee = int(m["score_shawnee"])
        opp_score = int(m["score_opp"]) if m.get("score_opp") is not None else None
        result = m.get("result") or result_from_scores(shawnee, opp_score)
        split = bool(m.get("split"))
        source_kind = "bout_derived" if split else "posted_tw_schedule"
        bout_score = None
        if eid and eid in tr:
            ds = (tr[eid].get("dual_scores") or {})
            for k, v in ds.items():
                if _slug_key(k) == _slug_key(opp):
                    bout_score = v
                    break

        logo = lookup_logo(opp, logos_map, make_badge=True)
        home_away = m.get("home_away")
        if home_away not in ("home", "away"):
            loc = (m.get("location") or "") + " " + (m.get("event_name") or "")
            if re.search(r"\b@\b", m.get("event_name") or "") or home_away == "away":
                home_away = "away"
            elif _norm(m.get("location") or "") in ("shawnee", "") or "shawnee" in _norm(m.get("event_name") or ""):
                home_away = "home"
            else:
                home_away = "event"

        conf = _slug_key(logo.get("opponent") or opp) in conf_set

        ext = _match_external(
            {"date_iso": m.get("date_iso"), "opponent": logo.get("opponent") or opp},
            ext_duals,
        )
        flags: List[str] = []
        validation = "ok"
        if bout_score and not split:
            if int(bout_score.get("shawnee", -1)) != shawnee or int(bout_score.get("opp", -1)) != opp_score:
                flags.append("posted_vs_bout_mismatch")
                validation = "score_mismatch"
        if split and bout_score:
            source_kind = "bout_derived"
        if ext:
            if int(ext.get("shawnee", -1)) != shawnee or int(ext.get("opp", -1)) != opp_score:
                flags.append("external_score_mismatch")
                validation = "score_mismatch"
            if (ext.get("result") or "").upper() != (result or "").upper():
                flags.append("external_result_mismatch")
                validation = "result_mismatch"
        else:
            flags.append("missing_external_ref")

        rows.append({
            "id": f"{m.get('date_iso')}_{_slug_key(opp)}_{eid or 'x'}",
            "date_iso": m.get("date_iso"),
            "date": m.get("date"),
            "opponent": logo.get("opponent") or opp,
            "opponent_slug": logo.get("opponent_slug"),
            "opponent_logo_local": logo.get("opponent_logo_local") or m.get("opponent_logo_local"),
            "opponent_logo": logo.get("opponent_logo") or m.get("opponent_logo"),
            "shawnee": shawnee,
            "opp": opp_score,
            "score_display": m.get("score_display") or f"{shawnee}-{opp_score}",
            "result": result,
            "home_away": home_away,
            "conference": conf,
            "split_from_multi": split,
            "event_id": eid or None,
            "event_name": m.get("event_name"),
            "parent_event_id": m.get("parent_event_id") or (eid if split else None),
            "source": source_kind,
            "source_detail": (
                f"TW event {eid}; bout-grid dual score"
                if source_kind == "bout_derived"
                else f"TW event {eid}; schedule UI posted score"
            ),
            "bout_derived_score": (
                {"shawnee": bout_score["shawnee"], "opp": bout_score["opp"], "score_display": bout_score.get("score_display")}
                if bout_score else None
            ),
            "external_ref_score": (
                {"shawnee": ext["shawnee"], "opp": ext["opp"], "result": ext.get("result"), "source": "NJ.com"}
                if ext else None
            ),
            "validation": validation,
            "flags": flags,
        })

    have_keys = {(r["date_iso"], _slug_key(r["opponent"])) for r in rows}
    for e in ext_duals:
        k = (e.get("date_iso"), _slug_key(e.get("opponent") or ""))
        if k in have_keys:
            continue
        logo = lookup_logo(e.get("opponent") or "", logos_map, make_badge=True)
        eid = None
        event_name = e.get("note")
        home_away = "event"
        for m in data.get("schedule") or []:
            if m.get("date_iso") == e.get("date_iso") and not m.get("opponent"):
                eid = str(m.get("event_id") or "") or eid
                event_name = m.get("event_name") or event_name
                home_away = m.get("home_away") or home_away
        rows.append({
            "id": f"{e.get('date_iso')}_{_slug_key(e.get('opponent') or '')}_{eid or 'ext'}",
            "date_iso": e.get("date_iso"),
            "date": None,
            "opponent": logo.get("opponent") or e.get("opponent"),
            "opponent_slug": logo.get("opponent_slug"),
            "opponent_logo_local": logo.get("opponent_logo_local"),
            "opponent_logo": logo.get("opponent_logo"),
            "shawnee": int(e["shawnee"]),
            "opp": int(e["opp"]),
            "score_display": f"{e['shawnee']}-{e['opp']}",
            "result": e.get("result") or result_from_scores(e["shawnee"], e["opp"]),
            "home_away": home_away,
            "conference": _slug_key(logo.get("opponent") or e.get("opponent") or "") in conf_set,
            "split_from_multi": False,
            "event_id": eid,
            "event_name": event_name,
            "parent_event_id": eid,
            "source": "external_ref_gapfill",
            "source_detail": "Present on NJ.com / external ref; no scored TW dual listing yet",
            "bout_derived_score": None,
            "external_ref_score": {"shawnee": e["shawnee"], "opp": e["opp"], "result": e.get("result"), "source": "NJ.com"},
            "validation": "external_gapfill",
            "flags": ["filled_from_external_ref", "needs_tw_score"],
        })

    rows.sort(key=lambda r: (r.get("date_iso") or "", r.get("opponent") or ""))
    return rows


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    def tally(subset: List[Dict[str, Any]]) -> Dict[str, Any]:
        w = sum(1 for r in subset if r.get("result") == "W")
        l = sum(1 for r in subset if r.get("result") == "L")
        t = sum(1 for r in subset if r.get("result") == "T")
        rec = f"{w}-{l}" if t == 0 else f"{w}-{l}-{t}"
        return {"wins": w, "losses": l, "ties": t, "record": rec, "count": len(subset)}

    return {
        "overall": tally(rows),
        "conference": tally([r for r in rows if r.get("conference")]),
        "home": tally([r for r in rows if r.get("home_away") == "home"]),
        "away": tally([r for r in rows if r.get("home_away") == "away"]),
        "neutral_or_event": tally([r for r in rows if r.get("home_away") not in ("home", "away")]),
    }


def validate_ledger(
    rows: List[Dict[str, Any]],
    summary: Dict[str, Any],
    external: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    external = external if external is not None else load_external_ref()
    discrepancies: List[Dict[str, Any]] = []
    sources = external.get("sources") or []
    src0 = sources[0] if sources else {}

    for r in rows:
        for flag in r.get("flags") or []:
            if flag in ("external_score_mismatch", "posted_vs_bout_mismatch", "external_result_mismatch"):
                discrepancies.append({
                    "type": flag,
                    "dual_id": r.get("id"),
                    "date_iso": r.get("date_iso"),
                    "opponent": r.get("opponent"),
                    "ledger": {"shawnee": r.get("shawnee"), "opp": r.get("opp"), "result": r.get("result"), "source": r.get("source")},
                    "bout": r.get("bout_derived_score"),
                    "external": r.get("external_ref_score"),
                })

    ext_overall = src0.get("overall_record")
    if ext_overall and summary["overall"]["record"] != ext_overall:
        discrepancies.append({
            "type": "overall_record_mismatch",
            "ledger_record": summary["overall"]["record"],
            "external_record": ext_overall,
            "external_source": src0.get("name"),
            "external_url": src0.get("url"),
        })

    ext_league = src0.get("league_record")
    if ext_league and summary["conference"]["record"] != ext_league:
        discrepancies.append({
            "type": "conference_record_mismatch",
            "ledger_record": summary["conference"]["record"],
            "external_record": ext_league,
            "conference_opponents": external.get("conference_opponents"),
            "external_source": src0.get("name"),
        })

    ext_n = len(external.get("duals") or [])
    if ext_n and summary["overall"]["count"] != ext_n:
        discrepancies.append({
            "type": "dual_count_mismatch",
            "ledger_count": summary["overall"]["count"],
            "external_count": ext_n,
        })

    for r in rows:
        if "missing_external_ref" in (r.get("flags") or []):
            discrepancies.append({
                "type": "missing_external_ref",
                "dual_id": r.get("id"),
                "opponent": r.get("opponent"),
                "date_iso": r.get("date_iso"),
            })

    ok = not any(
        d["type"] in (
            "overall_record_mismatch",
            "conference_record_mismatch",
            "dual_count_mismatch",
            "external_result_mismatch",
        )
        for d in discrepancies
    )
    return {
        "ok": ok,
        "discrepancy_count": len(discrepancies),
        "discrepancies": discrepancies,
        "external_overall": ext_overall,
        "external_league": ext_league,
        "checked_at": _now(),
    }


class LedgerConsistencyError(RuntimeError):
    """Raised when ledger totals disagree with authoritative external sources."""


def build_and_apply(
    data: Dict[str, Any],
    *,
    write: bool = True,
    strict: bool = True,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Build ledger, write JSON, stamp dual_scores/metadata/standings from it."""
    external = load_external_ref()
    rows = build_ledger_rows(data, external=external)
    summary = summarize(rows)
    validation = validate_ledger(rows, summary, external)

    ledger = {
        "season": "2025-2026",
        "generated_at": _now(),
        "policy": (
            "Canonical dual record is the count of ALL scored dual listings, "
            "including duals split from tri/quad/dual-tournament meets. "
            "Individual tournaments are not duals. Trackwrestling is the schedule "
            "source; external refs (NJ.com / GoBound) are validation only."
        ),
        "summary": summary,
        "validation": validation,
        "duals": rows,
    }

    duals_for_ui = []
    for r in rows:
        duals_for_ui.append({
            "opponent": r["opponent"],
            "shawnee": r["shawnee"],
            "opp": r["opp"],
            "result": r["result"],
            "date_iso": r.get("date_iso"),
            "event_id": r.get("event_id"),
            "split": r.get("split_from_multi"),
            "conference": r.get("conference"),
            "home_away": r.get("home_away"),
            "opponent_logo_local": r.get("opponent_logo_local"),
            "opponent_logo": r.get("opponent_logo"),
            "opponent_slug": r.get("opponent_slug"),
            "score_display": r.get("score_display"),
            "source": r.get("source"),
            "validation": r.get("validation"),
        })

    data["dual_scores"] = {
        "record": summary["overall"]["record"],
        "wins": summary["overall"]["wins"],
        "losses": summary["overall"]["losses"],
        "ties": summary["overall"]["ties"],
        "conference_record": summary["conference"]["record"],
        "home_record": summary["home"]["record"],
        "away_record": summary["away"]["record"],
        "ledger_path": "data/results_ledger.json",
        "duals": duals_for_ui,
    }
    meta = data.setdefault("metadata", {})
    meta["dual_record"] = summary["overall"]["record"]
    meta["conference_record"] = summary["conference"]["record"]
    meta["home_record"] = summary["home"]["record"]
    meta["away_record"] = summary["away"]["record"]
    meta["season"] = "2025-2026"

    st = data.setdefault("standings", {})
    st["source"] = "results ledger (all dual listings)"
    st["shawnee_dual_record"] = summary["overall"]["record"]
    st["conference_record"] = summary["conference"]["record"]
    st["note"] = (
        f"Overall dual record {summary['overall']['record']} from {summary['overall']['count']} duals "
        f"(including multi-meet splits). Olympic–American conference slice: "
        f"{summary['conference']['record']}. Canonical list: data/results_ledger.json."
    )
    st["rows"] = [
        {
            "opponent": r["opponent"],
            "result": r["result"],
            "score": r["score_display"],
            "date_iso": r.get("date_iso"),
            "conference_dual": r.get("conference"),
            "opponent_logo_local": r.get("opponent_logo_local"),
            "opponent_logo": r.get("opponent_logo"),
            "opponent_slug": r.get("opponent_slug"),
            "home_away": r.get("home_away"),
            "source": r.get("source"),
        }
        for r in rows
    ]

    for r in rows:
        if r.get("source") != "external_ref_gapfill":
            continue
        exists = any(
            m.get("date_iso") == r["date_iso"]
            and m.get("opponent")
            and _slug_key(m["opponent"]) == _slug_key(r["opponent"])
            for m in data.get("schedule") or []
        )
        if exists:
            continue
        data.setdefault("schedule", []).append({
            "event_id": r.get("event_id"),
            "date": r.get("date"),
            "date_iso": r.get("date_iso"),
            "time": None,
            "opponent": r["opponent"],
            "event_name": r.get("event_name"),
            "location": None,
            "home_away": r.get("home_away") or "event",
            "level": "Varsity",
            "event_kind": "D",
            "result": r.get("result"),
            "score_shawnee": r.get("shawnee"),
            "score_opp": r.get("opp"),
            "score_display": r.get("score_display"),
            "opponent_slug": r.get("opponent_slug"),
            "opponent_logo": r.get("opponent_logo"),
            "opponent_logo_local": r.get("opponent_logo_local"),
            "split": False,
            "split_note": "Team dual from sectionals (external-validated)",
            "source": "external_ref_gapfill",
        })
    data["schedule"] = sorted(
        data.get("schedule") or [],
        key=lambda m: (m.get("date_iso") or "", m.get("opponent") or m.get("event_name") or ""),
    )

    if write:
        LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
        LEDGER_PATH.write_text(json.dumps(ledger, indent=2) + "\n")
        logger.info(
            "Ledger %s duals record=%s conf=%s discrepancies=%d",
            summary["overall"]["count"],
            summary["overall"]["record"],
            summary["conference"]["record"],
            validation["discrepancy_count"],
        )

    if strict and not validation["ok"]:
        bad = [d for d in validation["discrepancies"] if d["type"] in (
            "overall_record_mismatch", "conference_record_mismatch",
            "dual_count_mismatch", "external_result_mismatch",
        )]
        msg = "RESULTS LEDGER CONSISTENCY FAILED:\n" + json.dumps(bad, indent=2)
        raise LedgerConsistencyError(msg)

    return ledger, data


def assert_consistent(ledger_path: Path | None = None) -> Dict[str, Any]:
    """Load written ledger and re-check validation block; raise if not ok."""
    path = ledger_path or LEDGER_PATH
    ledger = json.loads(path.read_text())
    v = ledger.get("validation") or {}
    if not v.get("ok"):
        raise LedgerConsistencyError(
            "results_ledger.json validation.ok is false:\n"
            + json.dumps(v.get("discrepancies") or [], indent=2)
        )
    return v


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = json.loads((ROOT / "data" / "wrestling_data.json").read_text())
    ledger, data = build_and_apply(data, write=True, strict=False)
    (ROOT / "data" / "wrestling_data.json").write_text(json.dumps(data, indent=2) + "\n")
    (ROOT / "wrestling_data.json").write_text(json.dumps(data, indent=2) + "\n")
    print(json.dumps(ledger["summary"], indent=2))
    print("validation ok", ledger["validation"]["ok"], "discrepancies", ledger["validation"]["discrepancy_count"])
