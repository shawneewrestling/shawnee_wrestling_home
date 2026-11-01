# Varsity assignments + Jotform (planned)

## Data

| File | Role |
|------|------|
| `data/varsity_assignments.json` | **One wrestler per NJSIAA weight class** for the public Roster page (image cards). |
| `data/jotform_roster_options.json` | Active roster names/ids — rebuild every scrape; use to populate Jotform dropdowns. |
| `data/varsity_jotform_overrides.json` | Optional coach override map written from Jotform ingestion (not created until form exists). |
| `data/varsity_overrides.json` | Legacy include/exclude + `starters` map; `starters` still applied. |
| `data/varsity.json` | Broader “appeared in varsity” list (not one-per-weight). |

NJSIAA boys classes (base): 106, 113, 120, 126, 132, 138, 144, 150, 157, 165, 175, 190, 215, 285.  
(After the Jan 1 growth allowance, weigh-in labels read 108–287; we store the base class.)

Assigned weight is **independent** of weights wrestled in bouts.

## Auto seed

`varsity_assignments.seed_assignments_from_appearances` picks, per weight, the wrestler with the most Varsity dual appearances at that weight. If the bout feed is empty (2025-26 replay), falls back to `varsity.build_varsity` season-record proxy grouped by TW roster weight.

## Jotform ingestion stub

```python
from varsity_assignments import ingest_jotform_submission

overrides = ingest_jotform_submission(submission_json, roster)
# → { "106": {wrestler_id, name, …}, … }
# Write to data/varsity_jotform_overrides.json then re-run update_site_data.py --skip-scrape
```

Expected submission shape: `answers` keyed by weight (`106`, `weight_106`, …) with name string or `{name, wrestler_id}`. `"Vacant"` clears a slot.

**Do not create the Jotform yet** — wait for Jeff to review the Roster cards.

## Prestige on cards

See `docs/PRESTIGE.md`. Points shown on varsity cards and player pages come from career-best prior placement.
