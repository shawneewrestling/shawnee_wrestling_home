# Career stats data model

Files: `data/career.json`, code: `career.py`.

## Shape

```json
{
  "schema_version": 1,
  "baseline": [],
  "baseline_note": "Empty until Jeff uploads prior-years data at start of 2026-27",
  "events": [
    {
      "source_event_id": "season:1560212138:aggregate",
      "season": "2025-26",
      "season_id": "1560212138",
      "kind": "season_aggregate",
      "wrestlers": [{"wrestler_id":"…","name":"…","wins":21,"losses":16,"pins":null}]
    }
  ],
  "rollups": [{"wrestler_id":"…","name":"…","career_wins":21,"career_losses":16,"career_pins":null,"sources":["…"]}]
}
```

## Rules

1. **Baseline empty** on this branch by design.
2. At 2026-27 kickoff Jeff uploads a baseline file (spreadsheet or JSON). Load via `career.ingest_baseline`.
3. Each season scrape appends one `season_aggregate` event (or bout-level events later).
4. **Dedupe** on `(wrestler_id, source_event_id)` — re-scrape replaces the same season aggregate.
5. Rollup = baseline + sum(events).

Bout-level `source_event_id` (preferred long-term) waits on a working TW results feed.
