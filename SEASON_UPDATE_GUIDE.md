# Season Update Guide: 2025-26 to 2026-27

## Current Status (December 2024)

**Active Season:** 2025-26 (Wrestling Season for School Year 2024-25)
- Team ID: `768996150`
- Season ID: `1560212138`
- Your scraper is correctly configured for the CURRENT season

## Important: 2026-27 Season Not Yet Available

The 2026-27 wrestling season typically starts in **November/December 2025**. TrackWrestling usually creates new seasons in the fall when the season begins. 

**You do NOT need to update anything right now.** Your current configuration will work for the entire 2025-26 season (through February/March 2025).

## When to Update (Fall 2025)

### Step 1: Find New Season IDs

When the 2026-27 season begins, find the new IDs by:

1. Go to TrackWrestling.com
2. Search for "Shawnee High School"
3. Click on the team
4. Select "2025-26" season (when available)
5. Look at the URL in your browser address bar

**Example URL format:**
```
https://www.trackwrestling.com/tw/seasons/LoadBalance.jsp?
  seasonId=XXXXXXXX     ← This is the Season ID
  &teamId=XXXXXXXX      ← This is the Team ID
  &pageName=TeamRoster.jsp
```

### Step 2: Update scraper.py

Edit the `scraper.py` file and update lines 100-103:

```python
def main():
    """Main scraper function"""
    # 2025-26 Season configuration
    TEAM_ID_2026 = "NEW_TEAM_ID_HERE"      # Update this
    SEASON_ID_2026 = "NEW_SEASON_ID_HERE"  # Update this
    
    scraper = TrackWrestlingScraper(TEAM_ID_2026, SEASON_ID_2026)
```

### Step 3: Test Locally (Optional but Recommended)

```bash
python test_scraper.py
```

This will verify the new IDs work correctly.

### Step 4: Commit and Push

```bash
git add scraper.py
git commit -m "Update to 2025-26 season"
git push origin main
```

The automation will automatically start using the new season!

## Historical Reference

### 2024-25 Season (Last Year)
- Team ID: `1441922147`
- Season ID: `842514138`

### 2025-26 Season (CURRENT)
- Team ID: `768996150`
- Season ID: `1560212138`

### 2026-27 Season (FUTURE)
- Team ID: TBD (usually changes)
- Season ID: TBD (will be created in Fall 2025)

## Pattern Recognition

Looking at the pattern:
- **Team IDs change each season** - Shawnee gets a new team ID annually
- **Season IDs are unique** - TrackWrestling assigns new season IDs
- **URL structure stays the same** - The format doesn't change

## Quick Update Checklist for Fall 2025

- [ ] Navigate to TrackWrestling when 2025-26 season starts
- [ ] Find Shawnee High School team page
- [ ] Copy Team ID from URL
- [ ] Copy Season ID from URL
- [ ] Update `scraper.py` with new IDs
- [ ] Test locally (optional): `python test_scraper.py`
- [ ] Commit: `git commit -m "Update to 2025-26 season"`
- [ ] Push: `git push origin main`
- [ ] Verify workflow runs successfully in GitHub Actions

## Alternative: Waiting for Season to Start

If you want to prepare ahead:

1. **September/October 2025**: Check TrackWrestling periodically
2. **When 2025-26 appears**: Grab the new IDs immediately
3. **Update your scraper**: Takes 2 minutes
4. **You're set**: Automated for the whole new season

## Multi-Season Support (Advanced)

If you want to track BOTH seasons simultaneously, you can modify the scraper to support multiple seasons:

```python
# In scraper.py, create separate scrapers
scraper_2025 = TrackWrestlingScraper(TEAM_ID_2025, SEASON_ID_2025)
scraper_2026 = TrackWrestlingScraper(TEAM_ID_2026, SEASON_ID_2026)

# Save to different files
data_2025 = scraper_2025.scrape_all()
data_2026 = scraper_2026.scrape_all()
```

But for most use cases, just tracking the current season is sufficient.

## Current Setup Works Until

Your current configuration will work through the end of the 2025-26 season:
- **Through:** February/March 2025 (end of season)
- **Update needed:** Fall 2025 (when 2026-27 starts)

## Summary

✅ **Right now:** You're all set! Current season is properly configured.

⏰ **Fall 2025:** Spend 5 minutes updating IDs for the new season.

🔄 **Annual process:** Update IDs once per year when new season starts.

---

**Questions?** The process is the same every year - just update two numbers in one file!
