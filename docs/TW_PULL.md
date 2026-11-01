# Trackwrestling pull process (Shawnee)

Season-agnostic pull driven by `data/seasons/<YYYY-YY>/config.json` and `python tw_pull.py`.

## Modes

| Mode | Command | What it does |
|------|---------|--------------|
| **ids** | `python tw_pull.py ids --season 2026-27 --season-id <ID> --save-config` | Resolve `gbId` (NJ=36) + Shawnee `teamId` via Ajax `getTeams` |
| **preseason** | `python tw_pull.py preseason --season 2026-27 --dry-run` | Roster + schedule (dates, opponents, home/away, times, venue) |
| **postseason** | `python tw_pull.py postseason --season 2025-26 --dry-run` | Final dual scores from schedule Ajax + optional capture merges (bouts, win-types, placements) |
| **probe** | `python tw_pull.py probe --season 2025-26 --dry-run` | Capability report for this box |
| **diff** | `python tw_pull.py diff --season 2025-26` | Compare dry-run vs `data/wrestling_data.json` |

Dry-run output: `/workspace/shawnee/dryrun/<season>/` (never live `data/` unless you drop `--dry-run` and write under `data/seasons/<season>/tw_pull/`).

---

## What works server-side (this box, verified 2026-11-01)

**Do not send a Chrome/Firefox User-Agent.** TW returns **HTTP 406** for browser-like UAs from this network. The client in `tw/client.py` uses a non-browser UA.

| Ajax / URL | Works? | Notes |
|------------|--------|-------|
| `LoadBalance.jsp` (no Chrome UA) | Yes | Returns a small shell HTML containing `twSessionId` |
| `getTeamSchedule` | Yes | Dual scores in cols 18/21 (home: Shawnee=18, opp=21; away: swapped) |
| `getWrestlers` | Yes | W–L only — **no** pins/tech/major |
| `getTeams` + `gbId=36` | Yes | Find Shawnee / Medford → `teamId` |
| `getSeasonGBs` | Yes | NJ governing body id = **36** |
| `getTeamReports` | Yes | Report *list* only (ids/names) |
| `getEventMatchesJSP` | No (null) | Bout grids need browser EventMatches HTML |
| `getSeasons` / PreDefinedSeasons | No | **seasonId discovery is browser (or known config)** |
| Win Types report body | No | Browser capture of Statistics → Win Types by Wrestler |
| Chrome-like UA on any of the above | **406** | Never “fix” with cookie scraping or credentials |

NJ.com (`highschoolsports.nj.com/school/medford-shawnee/wrestling`) is reachable server-side and is a **fallback for historic standings/results**, not a replacement for TW roster/schedule IDs.

---

## (a) Discovering season IDs

TW does **not** expose a working `getSeasons` Ajax from this box. `seasonId` must come from:

1. An existing `data/seasons/<YYYY-YY>/config.json`, or
2. A browser visit (below), then `tw_pull.py ids --season-id … --save-config`.

### Browser click path (preseason startup)

1. Open [https://www.trackwrestling.com](https://www.trackwrestling.com) in a normal browser.
2. Open **Seasons** (or **High School** seasons list).
3. Choose **New Jersey** / **NJSIAA** high school wrestling for the school year you want  
   (e.g. **2026-2027**).
4. Note `seasonId` in the URL (`seasonId=########`) — this is the season id. `gbId` for NJSIAA is **36**.
5. Search teams for **Shawnee** (city **Medford**).
6. Open the team **Schedule** or **Roster** page. Copy `teamId` from the URL:
   ```
   …/LoadBalance.jsp?seasonId=SEASON&gbId=36&pageName=TeamSchedule.jsp;teamId=TEAM
   ```
7. On the box:
   ```bash
   python tw_pull.py ids --season 2026-27 --season-id SEASON --save-config --dry-run
   # review /workspace/shawnee/dryrun/2026-27/ids.json then re-run without --dry-run --save-config
   python tw_pull.py ids --season 2026-27 --season-id SEASON --save-config
   ```

### Known IDs (config already seeded)

| Season | seasonId | teamId | gbId |
|--------|----------|--------|------|
| 2023-24 | 170451138 | 424308143 | 36 |
| 2024-25 | 842514138 | 1441922147 | 36 |
| 2025-26 | 1560212138 | 768996150 | 36 |
| 2026-27 | 95515140 | 1912611150 | 36 |

Team IDs change every season; gbId 36 is stable for NJSIAA.

---

## (b) Preseason pull

```bash
python tw_pull.py preseason --season 2026-27 --dry-run --save-raw
```

Produces `roster.json`, `schedule.json`, `wrestling_data.json` under the dry-run dir.

Optional browser saves (for audit / logo / UI scores):

| Page | URL pattern | Save as |
|------|-------------|---------|
| Roster | `LoadBalance.jsp?seasonId=SID&gbId=36&pageName=TeamRoster.jsp;teamId=TID` | `tw_capture/<season>/roster.html` |
| Schedule | `…pageName=TeamSchedule.jsp;teamId=TID` | `tw_capture/<season>/schedule.html` |

---

## (c) Postseason pull

```bash
python tw_pull.py postseason --season 2025-26 --dry-run \
  --capture-dir /workspace/shawnee/tw_capture/2025-26 \
  --event-capture-dir /workspace/shawnee/tw_event_pages
```

Server-side portion: final schedule dual scores + roster W–L.

### Browser capture checklist (hand to browser agent)

Substitute `SID` = seasonId, `TID` = teamId, `EID` = eventId. Save files under `/workspace/shawnee/tw_capture/<season>/` (create the folder first).

1. **Schedule page (full HTML)**  
   URL: `https://www.trackwrestling.com/tw/seasons/LoadBalance.jsp?seasonId=SID&gbId=36&pageName=TeamSchedule.jsp;teamId=TID`  
   Save: `schedule.html`  
   Wait until the event grid is populated before saving.

2. **Roster page**  
   URL: `…pageName=TeamRoster.jsp;teamId=TID`  
   Save: `roster.html`

3. **Statistics → Win Types by Wrestler** (pins / tech / major / dec)  
   URL: `…pageName=Statistics.jsp;teamId=TID`  
   Click **Win Types by Wrestler**. When the report table is visible, save:  
   `win_types.html` (HTML) **or** paste TSV as `win_types.txt`  
   Columns expected: Wrestler, Fall/Pin, Tech Fall, Major, Decision (order may vary; parser maps headers).

4. **Each dual / multi-dual / tournament event (bout grid)**  
   From the Schedule page, open the event so the **EventMatches** grid with Fall/Dec/etc. is visible (must include `initDataGrid(...)` in the HTML).  
   Direct attempt: `…pageName=EventMatches.jsp;eventId=EID`  
   Save: `event_<EID>.html`  
   Existing 2025-26 captures also live in `/workspace/shawnee/tw_event_pages/*.html` and are accepted via `--event-capture-dir`.

5. **NJSIAA placements** (if not parsed from event HTML)  
   Save plain text or JSON lists:  
   - `placements_district.txt`  
   - `placements_region.txt`  
   - `placements_state.txt`  
   Line formats accepted: `First Last 126 1st` or `First Last — 126 — District Champion`.

After captures:

```bash
python tw_pull.py postseason --season 2025-26 --dry-run
python tw_pull.py diff --season 2025-26
```

`postseason` also writes `capture_checklist.json` with concrete URLs for that season’s event ids.

---

## 2025-26 capture list (ready for browser agent)

Use IDs: `seasonId=1560212138`, `teamId=768996150`, `gbId=36`.

| # | File | How |
|---|------|-----|
| 1 | `tw_capture/2025-26/schedule.html` | Open [TeamSchedule](https://www.trackwrestling.com/tw/seasons/LoadBalance.jsp?seasonId=1560212138&gbId=36&pageName=TeamSchedule.jsp;teamId=768996150) → save full page HTML after grid loads |
| 2 | `tw_capture/2025-26/roster.html` | Open [TeamRoster](https://www.trackwrestling.com/tw/seasons/LoadBalance.jsp?seasonId=1560212138&gbId=36&pageName=TeamRoster.jsp;teamId=768996150) → save |
| 3 | `tw_capture/2025-26/statistics.html` | Open [Statistics](https://www.trackwrestling.com/tw/seasons/LoadBalance.jsp?seasonId=1560212138&gbId=36&pageName=Statistics.jsp;teamId=768996150) → save list page |
| 4 | `tw_capture/2025-26/win_types.html` | From Statistics, open **Win Types by Wrestler** → save report table HTML |
| 5 | `tw_capture/2025-26/event_<EID>.html` | For each schedule event id (see dry-run `capture_checklist.json` → `events[]`), open event matches grid → save HTML with `initDataGrid` |
| 6 | `tw_capture/2025-26/placements_{district,region,state}.txt` | Optional if placements not already in awards / event captures |

Priority events if time-boxed: scored duals + `8978282132` (District 28), `8978292132` (Region 7), `8978305132` (States). Many event HTMLs may already exist under `/workspace/shawnee/tw_event_pages/`.

---

## Safety

- Do **not** merge dry-run output to `main` or Hostinger without Jeff’s approval.
- Do **not** scrape login cookies or use TW credentials to bypass 406.
- Prefer `--dry-run` + `diff` before any live `data/wrestling_data.json` replace.

---

## 2025-26 dry-run findings (2026-11-01)

Ran `probe` / `ids` / `postseason --dry-run` / `diff` against live `data/wrestling_data.json`.

| Check | Result |
|-------|--------|
| Chrome UA | HTTP **406** |
| Non-browser UA Ajax | Schedule 24, wrestlers 58, teams 320, GBs 60, reports 9 |
| IDs | seasonId `1560212138`, teamId `768996150`, Medford, District 28 / Region 7 |
| Roster | 58 = live 58 (same names) |
| Event ids | 24 = live event id set |
| Dual record from schedule Ajax alone | **3-5** (8 scored parent duals) |
| Live dual record | **12-15** (multi-team events expanded into individual duals via captures / enrichment) |
| Pins / placements | Need Win Types + NJSIAA captures (still gaps) |
| Bout grids | 13 events attached from existing `/workspace/shawnee/tw_event_pages` |

**Implication:** `getTeamSchedule` scores only single-opponent duals. Quads / tris / Beast / Escape the Rock duals are rebuilt from EventMatches captures (or prior enrichment). Always run postseason with `--event-capture-dir` and compare via `diff` before replacing live data.

Dry-run artifacts: `/workspace/shawnee/dryrun/2025-26/` (includes `capture_checklist.json` with concrete EventMatches URLs).

