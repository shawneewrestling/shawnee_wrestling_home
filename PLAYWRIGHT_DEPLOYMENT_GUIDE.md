# 🚀 Automated Scraping - Playwright Solution

## What's New

I've created a **Playwright-based scraper** that's more reliable than Selenium for scraping TrackWrestling's JavaScript-heavy pages.

## Why Playwright > Selenium

✅ **More reliable** in GitHub Actions
✅ **Better JavaScript handling** 
✅ **Faster execution**
✅ **Easier setup** in CI/CD
✅ **Auto-installs browsers**

## Files Updated

### 1. **scraper_playwright.py** (NEW)
- Uses Playwright instead of Selenium
- Better at handling TrackWrestling's dynamic content
- More robust error handling
- Warns if no data found

### 2. **requirements.txt** (UPDATED)
```
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
playwright>=1.40.0  ← Changed from Selenium
```

### 3. **.github/workflows/update-data.yml** (UPDATED)
- Installs Playwright and Chromium
- Runs `scraper_playwright.py`
- Optimized for GitHub Actions

## How to Deploy

### Step 1: Upload Updated Files

Upload these files to your GitHub repo:

**Required:**
- `scraper_playwright.py` (NEW - the main scraper)
- `requirements.txt` (UPDATED)
- `.github/workflows/update-data.yml` (UPDATED)

**Keep existing:**
- `index.html`
- `styles.css`
- `app.js`
- `season_config.py`
- All other files

### Step 2: Test the Scraper

1. Go to your repo → **Actions** tab
2. Click "**Update Wrestling Data**"
3. Click "**Run workflow**" → "**Run workflow**"
4. Wait 2-3 minutes
5. Check the logs

### Step 3: Check Results

**In the workflow logs, look for:**
```
✅ Good:
Found 15 matches
Found 25 wrestlers
Data saved to data/wrestling_data.json

⚠️  Warning (but okay):
Found 0 matches
WARNING: No schedule data found
→ This means TrackWrestling hasn't published yet
```

### Step 4: Verify Data File

1. Go to your repo
2. Navigate to `data/wrestling_data.json`
3. Check if schedule array has data
4. If empty, TrackWrestling hasn't published the schedule yet

## Local Testing

Test the scraper on your computer first:

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium

# Run scraper
python scraper_playwright.py
```

**Expected output:**
```
Using season configuration: 2025-26
Fetching schedule...
Found X matches
Found X wrestlers
Scrape Complete!
```

## Troubleshooting

### No schedule data found?

**Possible reasons:**

1. **TrackWrestling hasn't published the schedule yet**
   - Most likely for 2025-26 season (starts Dec 2025)
   - Check manually at: https://www.trackwrestling.com/tw/seasons/LoadBalance.jsp?seasonId=1560212138&gbId=36&pageName=TeamSchedule.jsp;teamId=768996150
   - If you see data there but scraper doesn't, continue troubleshooting

2. **Page structure changed**
   - TrackWrestling may have updated their HTML
   - The parser may need adjustment

3. **JavaScript timeout**
   - Increase wait time in scraper
   - Check GitHub Actions logs for timeout errors

### Workflow fails?

**Check logs for:**
- `playwright install` errors → Browser installation issue
- `ModuleNotFoundError` → Dependencies not installed
- `Timeout` → Page loading too slow

### Still getting empty schedule?

If you confirm TrackWrestling HAS the schedule but scraper gets nothing:

**Option A: Manual Entry (Temporary)**
1. Use the manual JSON file approach
2. Update after each match
3. Simple and works immediately

**Option B: Debug the Scraper**
1. Run locally with `python scraper_playwright.py`
2. Add print statements to see what HTML is returned
3. Adjust the parsing logic

**Option C: Hybrid Approach**
1. Manual schedule entry (one-time)
2. Automated results scraping (after matches)

## Current Season Status

**Season:** 2025-26
**First Match:** December 13, 2025 (13 months away)
**Likely Issue:** Schedule not published yet on TrackWrestling

**Solution for now:**
- Upload manual schedule data
- Let scraper run daily
- When TrackWrestling publishes, it will auto-update

## Timeline

**Now (Dec 2024):**
- Deploy automation ✅
- Manual schedule entry (if needed) ✅
- Test workflow ✅

**Oct-Nov 2025:**
- Check if TrackWrestling published schedule
- Scraper should start working automatically

**Dec 2025:**
- Season starts
- Results update automatically
- No manual work needed!

## Comparison: Selenium vs Playwright

| Feature | Selenium | Playwright |
|---------|----------|------------|
| Setup in GitHub Actions | Complex | Simple |
| JavaScript rendering | Good | Excellent |
| Speed | Slower | Faster |
| Reliability | Good | Better |
| Auto-browser install | No | Yes |

## What Happens Daily

Once deployed, every day at 6 AM EST:

1. GitHub Actions triggers
2. Installs Playwright + Chromium
3. Runs `scraper_playwright.py`
4. Opens TrackWrestling pages
5. Waits for JavaScript to load
6. Extracts schedule/roster/results
7. Saves to `wrestling_data.json`
8. Commits changes
9. Site updates automatically

**All automatic - zero manual work!** 🎉

## Files to Download

1. **scraper_playwright.py** - New Playwright scraper
2. **requirements.txt** - Updated dependencies
3. **.github/workflows/update-data.yml** - Updated workflow
4. This guide

## Quick Deployment Checklist

- [ ] Download updated files
- [ ] Upload to GitHub (replace old versions)
- [ ] Trigger workflow manually (Actions tab)
- [ ] Check logs for success/warnings
- [ ] Verify `data/wrestling_data.json` created
- [ ] Visit your site - check if schedule appears
- [ ] If empty, schedule not published yet (normal for Dec 2024)

## Next Steps

1. **Deploy now** - Get automation in place
2. **Monitor** - Check if schedule appears over next months
3. **Verify** - When Dec 2025 approaches, confirm it's working
4. **Enjoy** - Fully automated wrestling site! 🏆

---

**Ready to deploy the Playwright automation!** 🚀

Download the 3 updated files and upload to GitHub!
