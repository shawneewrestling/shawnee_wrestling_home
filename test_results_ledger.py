#!/usr/bin/env python3
"""Fail loudly if the canonical results ledger disagrees with validation sources.

  python test_results_ledger.py
  python test_results_ledger.py --rebuild
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from results_ledger import (  # noqa: E402
    LEDGER_PATH,
    LedgerConsistencyError,
    assert_consistent,
    build_and_apply,
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--strict/--no-strict", default=True, dest="strict")
    args = ap.parse_args()

    data_path = ROOT / "data" / "wrestling_data.json"
    data = json.loads(data_path.read_text())

    if args.rebuild or not LEDGER_PATH.exists():
        try:
            ledger, data = build_and_apply(data, write=True, strict=args.strict)
        except LedgerConsistencyError as e:
            print(e, file=sys.stderr)
            return 2
        data_path.write_text(json.dumps(data, indent=2) + "\n")
        (ROOT / "wrestling_data.json").write_text(json.dumps(data, indent=2) + "\n")
    else:
        ledger = json.loads(LEDGER_PATH.read_text())
        try:
            assert_consistent(LEDGER_PATH)
        except LedgerConsistencyError as e:
            print(e, file=sys.stderr)
            return 2

    s = ledger["summary"]
    v = ledger["validation"]
    print(
        f"OK overall={s['overall']['record']} conference={s['conference']['record']} "
        f"duals={s['overall']['count']} score_flags={v['discrepancy_count']}"
    )
    score_mismatches = [
        d for d in (v.get("discrepancies") or []) if d["type"] == "external_score_mismatch"
    ]
    if score_mismatches:
        print(f"Note: {len(score_mismatches)} bout/posted vs NJ.com score mismatches (W/L still agree):")
        for d in score_mismatches:
            print(
                f"  {d.get('date_iso')} {d.get('opponent')}: "
                f"ledger {d['ledger']['shawnee']}-{d['ledger']['opp']} "
                f"vs ext {d['external']['shawnee']}-{d['external']['opp']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
