# 🔄 Quick Season Update Reference Card

## When Do I Need to Update?

**Once per year** - When the new wrestling season starts (typically November/December)

## Current Configuration (December 2024)

```
Season:    2025-26
Team ID:   768996150
Season ID: 1560212138
Status:    ✅ ACTIVE - No update needed until Fall 2025
```

---

## 🚀 Option 1: Automatic Update Script (Easiest!)

```bash
python update_season.py
```

Follow the prompts - it walks you through everything!

---

## ✏️ Option 2: Manual Update (Quick!)

### Step 1: Find New IDs
1. Visit: https://www.trackwrestling.com
2. Search: "Shawnee High School"
3. Click your team → Select new season (2025-26)
4. Copy from URL:
   ```
   seasonId=XXXXXX  ← Season ID
   teamId=YYYYYY   ← Team ID
   ```

### Step 2: Edit season_config.py
```python
CURRENT_SEASON = "2025-26"
TEAM_ID = "YYYYYY"        # Paste Team ID here
SEASON_ID = "XXXXXX"      # Paste Season ID here
```

### Step 3: Push to GitHub
```bash
git add season_config.py
git commit -m "Update to 2025-26 season"
git push origin main
```

**Done!** Site updates automatically within minutes.

---

## 📅 Update Schedule

| When | Action |
|------|--------|
| **Now (Dec 2024)** | ✅ No action needed |
| **Through Mar 2025** | ✅ Current season active |
| **Sep-Oct 2025** | 📅 Check for new season |
| **Nov 2025** | 🔄 Update to 2026-27 |
| **Through Mar 2026** | ✅ New season active |

---

## 🧪 Testing (Optional but Recommended)

After updating, test locally:
```bash
python test_scraper.py
```

Should show:
```
✓ Found X wrestlers
✓ Found X matches
✓ Data saved successfully
```

---

## 📚 Detailed Instructions

For complete step-by-step guide, see:
- **`SEASON_UPDATE_GUIDE.md`** - Full documentation
- **`README.md`** - Technical details

---

## 🆘 Troubleshooting

**Problem:** Scraper fails after update
- ✅ **Check:** IDs are correct (no typos)
- ✅ **Check:** New season exists on TrackWrestling
- ✅ **Fix:** Re-run `python test_scraper.py`

**Problem:** Site shows old data
- ✅ **Check:** Changes pushed to GitHub
- ✅ **Check:** GitHub Actions workflow ran
- ✅ **Wait:** 5-10 minutes for deployment

---

## 💡 Pro Tips

1. **Update as soon as new season appears** on TrackWrestling
2. **Test locally first** with `test_scraper.py`
3. **Keep this card handy** for annual updates
4. **Takes 5 minutes** once you know the IDs

---

## 📱 Quick Commands Cheat Sheet

```bash
# Update season (interactive)
python update_season.py

# Test the scraper
python test_scraper.py

# Commit and push
git add season_config.py
git commit -m "Update season"
git push origin main

# Check GitHub Actions
# Visit: https://github.com/shawneewrestling/shawnee_wrestling_home/actions
```

---

## ✅ Checklist for Annual Update

- [ ] New season created on TrackWrestling
- [ ] Found new Team ID and Season ID
- [ ] Updated `season_config.py` (or ran `update_season.py`)
- [ ] Tested locally (optional)
- [ ] Committed and pushed to GitHub
- [ ] Verified GitHub Actions ran successfully
- [ ] Checked site shows new season data

**Average time:** 5-10 minutes per year!

---

**Save this card!** You'll need it once a year. 📌
