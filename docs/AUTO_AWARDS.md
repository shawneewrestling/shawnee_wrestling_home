# Auto-award detection (in-season)

> Removed from awards page and auto-generation: **Season 20+ Wins**, **Season Win Leaders**, and **Varsity Dual Record**.

During the season the `update_site_data.py` pipeline runs `auto_awards.detect_season_awards()`
against the latest Trackwrestling scrape and merges rows into `data/awards.json` with
`auto_detected: true`. Historical seed rows (Jeff-confirmed) are never overwritten.

## Rules

| Trigger | Source | Award card | Notes |
|--------|--------|------------|-------|
| District placement 1st | Tournament placement feed | **District Champions** | Decade-grouped at render time |
| District placement 2–6 | Tournament placement feed | **District Place Winner** | Until feed exists, Jeff can paste a list |
| Region placement 1st / 2–6 | Tournament placement feed | **Region Champions** / **Region Place Winner** | |
| State placement 1st / 2–8 | Tournament placement feed | **State Champions** / **State Place Winner** | |
| Career wins cross 100 | `career.py` rollups | **Career Wins** milestone | Requires Jeff baseline + season aggregates |

## Tournament placement feed (not yet live)

The 2025-26 closeout replay could not recover District 28 / Region 7 / State individual
placements (TeamResults.jsp 404; event scraps empty). When a feed exists, pass a list of:

```json
{"level":"district","wrestler":"Name","wrestler_id":"…","weight":"126","placement":"1st"}
```

into `detect_season_awards(season_data, placements=…)`. Until then, leave NJSIAA rows for
Jeff to add manually to the seed / awards JSON after the tournament.

## Idempotency

- Auto rows use stable `id` values (`auto-{season}-…`).
- Re-running `update_site_data.py` replaces prior `auto_detected` rows for that build; seed rows stay.
- Career season aggregates use `source_event_id = season:{seasonId}:aggregate` and dedupe in `career.py`.

## Manual override

Jeff can delete or edit an auto row in `data/awards.json` (set `auto_detected` false and adjust).
Prefer fixing the rule if a class of awards is wrong.
