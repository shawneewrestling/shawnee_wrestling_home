# Updating the Shawnee Wrestling site

Branch note: `site-v2-2025-26-closeout` is a **preview** of the 2025-26 closeout static site. Do **not** merge to `main` or deploy to Hostinger until Jeff approves cutover.

## Manual updates (edit JSON, rebuild, preview)

### Files you usually edit

| What | File | Notes |
|------|------|--------|
| Season roster / schedule / dual scores / standings / season stats | `data/wrestling_data.json` | Prefer regenerating via the update script; hand-edit only for one-off fixes (typos, missing dual score). |
| Awards (historical + auto) | `data/awards.json` | Prefer editing the seed (`/workspace/shawnee/awards_seed.json` on the box, or a committed seed once approved) and re-running the script so auto rows stay consistent. |
| Career baseline (empty until 2026-27) | `data/career.json` → `baseline` | Jeff uploads prior-years rows at 2026-27 kickoff; do not invent baseline data. |
| Season IDs | `season_config.py` | `TEAM_ID`, `SEASON_ID`, `CURRENT_SEASON`, `GB_ID`. |
| Opponent logos | `assets/logos/*.png` + `data/logos.json` | Sourced from GoBound; schedule stays on Trackwrestling. |

### Awards
> **Locked:** Award chevron chrome (`AWARDS_CHEVRON_CHROME_LOCKED` in `styles.css`: Graduate titles, fixed navy tip angle/size, Shawnee S in `assets/img/shawnee-s.png`, Graduate in `assets/fonts/`) is locked to match live banners — do not change in automation or data refresh pipelines.
 JSON shape (chevron cards)

Each award row needs at least: `id`, `award_name`, `award_category`, `season`, and usually `wrestler` / `weight` / `placement` / `value`.  
**District Champions** are auto-grouped **one card per decade** in `awards.html` — add a row with `award_name: "District Champions"` (or `award_category: "district"`) and the correct `season` year; do not hand-build decade HTML.

Auto-detected rows set `"auto_detected": true`. Re-running the update script refreshes those; historical seed rows are kept.

### Run the update script

```bash
cd /path/to/shawnee_wrestling_home

# Full refresh from Trackwrestling (Playwright session + Ajax)
python update_site_data.py

# Or rebuild awards + career from the JSON already on disk
python update_site_data.py --skip-scrape

# Optional: point at a seed file
python update_site_data.py --skip-scrape --seed /path/to/awards_seed.json
```

What it does:

1. Hybrid scrape → `data/wrestling_data.json` (+ root `wrestling_data.json` mirror)
2. Auto-awards from season W-L / dual record / (later) TW placements → merge into `data/awards.json`
3. Varsity list + **one-per-weight assignments** + Jotform options + prestige index
4. Career season-aggregate event with `source_event_id` dedupe → `data/career.json`
5. Generate static `players/*.html` + `data/players_index.json`
6. Writes `data/build_summary.json`

Docs for rules: `docs/AUTO_AWARDS.md`, `docs/CAREER.md`, `docs/PRESTIGE.md`, `docs/VARSITY_JOTFORM.md`.

### Preview locally

```bash
python -m http.server 8080
# open http://127.0.0.1:8080/index.html
# pages: roster.html full-roster.html players/*.html schedule.html results.html standings.html stats.html awards.html
```

Static only — no WordPress. Colors: navy `#000080`, accent `#7EB6D9`.

### How changes reach Hostinger (when approved)

Not wired on this branch. Target path after Jeff approves:

1. Commit data/front-end changes on an approved branch
2. Merge to `main` (or the deploy branch Hostinger watches)
3. **Hostinger Git deploy** pulls into `public_html` (preferred), **or** GitHub Action SFTP
4. Hard-refresh shawneewrestling.com

Until cutover: leave live WordPress alone; this branch is preview-only.

---

## Automation path

```
Trackwrestling (Playwright session → Ajax getTeamSchedule / getWrestlers
               + Schedule UI dual scores + later bout/placement feed)
        ↓
  update_site_data.py  →  data/*.json  (+ auto_awards + career dedupe)
        ↓
  git commit on working branch
        ↓
  merge to deploy branch (Jeff-approved)
        ↓
  Hostinger Git deploy → public_html → shawneewrestling.com
```

### Mapped to season routines (America/New_York)

| Routine | Automation |
|---------|------------|
| **Nov 14 kickoff** | Discover new `seasonId` / `teamId` on TW → update `season_config.py` → dry-run `update_site_data.py` → fetch GoBound logos for any new TW opponents → Jeff approves commit → Hostinger pull |
| **Daily Nov–Mar** | Cron (~6:00 AM ET): hybrid scrape → if JSON changed, commit → Hostinger refresh. If TW adds a new opponent, fetch its GoBound logo into `assets/logos/` + `data/logos.json` |
| **Match-day hourly** | For ~2 hours after scheduled start: scrape → push dual score / W-L updates → Hostinger refresh |
| **After districts / regions / state (NJSIAA closeout)** | Ingest tournament placements into auto-awards (rules in `docs/AUTO_AWARDS.md`) → District champs land in the correct decade card automatically → Jeff spot-checks spellings → commit → deploy |
| **End of season (Mar)** | Freeze season JSON; append career season-aggregate; archive TW IDs into `SEASONS` map; prepare empty baseline slot for next year if needed |

### Auto-awards from TW placements

When a placement feed exists (or Jeff pastes a list), `auto_awards.detect_season_awards(..., placements=[…])` adds:

- District / Region / State Champions (1st) and Place Winners  
- Already live without placements: Season 20+ Wins, Season Win Leaders, Varsity Dual Record  

See `docs/AUTO_AWARDS.md` for idempotent IDs and override rules.

### Still manual / Jeff decisions

- Career **baseline** upload at 2026-27 start  
- Hostinger Git vs SFTP secrets  
- Approving first merge of site-v2 to the live deploy branch  
- (resolved) Olympic Conference standings: `data/standings.json` via NJ.com / GoBound — see below  
- NJSIAA placements until bout feed works (2025-26 replay: unavailable)


---

## Varsity roster (main Roster page)

The public **Roster** page shows **one starter per NJSIAA weight class** as image cards (photo / silhouette, name, weight, prestige). Click a card → static **player page**. Full TW team list (searchable) lives on **Full Roster**.

| File | Role |
|------|------|
| `data/varsity_assignments.json` | One wrestler per NJSIAA class (106–285). Consumed by `roster.html`. |
| `data/jotform_roster_options.json` | Active roster names/ids for Jotform dropdowns (rebuild every scrape). |
| `data/varsity_jotform_overrides.json` | Optional coach map from Jotform ingestion (created when form exists). |
| `data/dual_appearances.json` | Bout-level Varsity dual lines — preferred auto seed source. |
| `data/varsity_overrides.json` | Coach include / exclude / weight / `starters` — still applied. |
| `data/varsity.json` | Broader “appeared in varsity” list (not one-per-weight). |
| `data/prestige.json` | Per-wrestler career-best NJSIAA prestige points. |
| `data/players_index.json` | Index for Full Roster search + card links. |
| `players/*.html` | Generated static player pages. |

**NJSIAA weight classes (base):** 106, 113, 120, 126, 132, 138, 144, 150, 157, 165, 175, 190, 215, 285.  
(After Jan 1 growth allowance, weigh-in labels read 108–287; we store the base class.) Assigned class is **independent** of weights wrestled.

Auto seed: most Varsity dual appearances at that weight. **2025-26:** bout feed empty → season-record proxy by roster weight. Rebuild: `python update_site_data.py --skip-scrape` (or `python varsity_assignments.py` then `python players_build.py`).

### Prestige points

Career-best prior placement (not current season; not “prior year only”). Table + rules: `docs/PRESTIGE.md`, `data/njsiaa_prestige.json`. Official source cited in that doc only — never on public pages. Per-match prestige is out of scope.

### Planned coach-input path (Jotform) — do not create the form yet

See `docs/VARSITY_JOTFORM.md`. Stub: `varsity_assignments.ingest_jotform_submission(submission, roster)`.

1. Build a **Jotform** with one dropdown per NJSIAA weight, options from `jotform_roster_options.json`.
2. On submit / daily routine: ingest → `data/varsity_jotform_overrides.json` → `update_site_data.py --skip-scrape` → commit assignments + player pages.
3. Until the form exists, set `varsity_overrides.json` → `starters` `{ "126": "<wrestler_id>", … }` by hand.

## Results ledger (canonical dual record)

**Source of truth for dual W–L is `data/results_ledger.json`**, not “events typed as duals” on Trackwrestling.

### Why
Tri/quad meets and dual tournaments are split into one schedule listing per opponent. The season dual record must count **every** scored dual listing (including those splits and team duals filled from sectionals). Counting only TW `event_kind=D` rows understated the 2025–26 record as 3–5.

### Pipeline
1. Scrape / load `wrestling_data.json`
2. `attach_tournament_results` + `enrich_schedule` (splits + logos)
3. `results_ledger.build_and_apply(...)` writes `data/results_ledger.json` and stamps:
   - `dual_scores.record` / `wins` / `losses` / `conference_record` / `home_record` / `away_record` / `duals`
   - `metadata.dual_record`, `conference_record`, `home_record`, `away_record`
   - `standings.rows` + `shawnee_dual_record` / `conference_record`
4. **Consistency gate** (`test_results_ledger.py` / `assert_consistent`): update aborts with exit code 2 if ledger overall, conference, dual count, or any W/L disagrees with `data/results_external_ref.json` (NJ.com / league validation). Score-only mismatches are reported but do not fail the build.

### Commands
```bash
python results_ledger.py              # rebuild ledger (non-strict print)
python test_results_ledger.py --rebuild   # rebuild + fail on W-L mismatches
python update_site_data.py --skip-scrape  # full pipeline incl. ledger gate
```

### External validation
`data/results_external_ref.json` holds the published overall/league records and per-dual scores used for cross-check (NJ.com Shawnee 2025–26). Conference opponents for Olympic–American are listed there. When TW has no scored dual yet (e.g. a sectional), the ledger gap-fills from this ref and flags `needs_tw_score`.

### Pages
Home, Schedule/Results, and **Results** (`results.html`) all read the ledger-backed `dual_scores` / `standings` / `metadata` fields. Do not reintroduce a `!split` filter on the home dual table.

## Olympic Conference standings

**Standings** (`standings.html`) shows every Olympic Conference wrestling team by division (American / National) with logo, division record, and overall record for the active season. Data: `data/standings.json` (source + as-of date). Sorted by division win%.

**Results** (`results.html`) is Shawnee dual W–L + tournament bout cards (former Standings page).

### Pipeline (`update_site_data.py`)
After the results ledger gate:

1. Try GoBound OC wrestling standings (often HTTP 401/403 for 2025-26 from this server; hub page may still 200).
2. Fall back to [NJ.com Olympic standings](https://highschoolsports.nj.com/wrestling/standings/season/2025-2026?conference=Olympic).
3. Group American / National, sort by division win%, attach logos (`school_aliases` + `data/logos.json`).
4. Validate Shawnee overall (and division) against `data/results_ledger.json` — mismatch → exit 2.
5. Sync `results_external_ref.json` `conference_opponents` to American peers (excl. Shawnee).

Trackwrestling returns HTTP 406 here — use GoBound/NJ.com for peer records. Gaps are recorded in `standings.json`.

```bash
python conference_standings.py            # refresh data/standings.json
python update_site_data.py --skip-scrape  # full pipeline including standings
```
