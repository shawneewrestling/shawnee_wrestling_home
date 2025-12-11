# ✅ Complete Setup Checklist for Shawnee Wrestling Automation

## Pre-Deployment Checklist

### 1. Files Verification
- [ ] All 12 files present in project folder:
  - [ ] `.github/workflows/deploy-pages.yml`
  - [ ] `.github/workflows/update-data.yml`
  - [ ] `.gitignore`
  - [ ] `DEPLOYMENT_GUIDE.md`
  - [ ] `README.md`
  - [ ] `app.js`
  - [ ] `data/wrestling_data.json`
  - [ ] `index.html`
  - [ ] `requirements.txt`
  - [ ] `scraper.py`
  - [ ] `styles.css`
  - [ ] `test_scraper.py`

### 2. Configuration Check
- [ ] `scraper.py` has correct Team ID: `768996150`
- [ ] `scraper.py` has correct Season ID: `1560212138`
- [ ] Colors in `styles.css` match your preferences

### 3. Optional Local Testing
```bash
# Only if you want to test locally first
pip install -r requirements.txt
python test_scraper.py
```

## Deployment Checklist

### Step 1: Upload to GitHub
- [ ] Files uploaded to `shawneewrestling/shawnee_wrestling_home` repository
- [ ] All files visible in GitHub web interface

### Step 2: Enable GitHub Pages
- [ ] Go to Settings → Pages
- [ ] Source set to "GitHub Actions"
- [ ] Saved changes

### Step 3: Configure Permissions
- [ ] Go to Settings → Actions → General
- [ ] "Read and write permissions" selected
- [ ] "Allow GitHub Actions to create and approve pull requests" checked
- [ ] Saved changes

### Step 4: Enable and Run Workflows
- [ ] Go to Actions tab
- [ ] Enabled workflows (if prompted)
- [ ] Manually triggered "Update Wrestling Data" workflow
- [ ] Workflow completed with green checkmark
- [ ] "Deploy to GitHub Pages" workflow completed

### Step 5: Verify Deployment
- [ ] Visited `https://shawneewrestling.github.io/shawnee_wrestling_home/`
- [ ] Site loads correctly
- [ ] Header shows "Shawnee Renegades"
- [ ] All three sections visible (Roster, Schedule, Results)
- [ ] "Last Updated" timestamp shows

## Post-Deployment Checklist

### Immediate Tasks
- [ ] Bookmark the GitHub Pages URL
- [ ] Test on mobile device
- [ ] Share URL with team/parents

### Within 24 Hours
- [ ] Verify automatic update ran at 6 AM EST
- [ ] Check Actions tab for successful workflow run
- [ ] Confirm data updated on website

### Weekly Monitoring (First Month)
- [ ] Check that daily updates are running
- [ ] Verify data accuracy against TrackWrestling
- [ ] Monitor for any failed workflows

## Troubleshooting Reference

### Issue: Site Not Loading
**Check:**
1. GitHub Pages enabled in Settings
2. Workflows completed successfully in Actions tab
3. Wait 5-10 minutes after first deployment

**Fix:**
- Re-run "Deploy to GitHub Pages" workflow manually

### Issue: Data Not Updating
**Check:**
1. "Update Wrestling Data" workflow running daily
2. Workflow logs for errors
3. TrackWrestling URLs still valid

**Fix:**
- Manually trigger "Update Wrestling Data" workflow
- Check scraper.py for correct IDs

### Issue: Scraper Failing
**Check:**
1. Workflow error logs in Actions tab
2. TrackWrestling site accessibility
3. Season/Team IDs correct

**Fix:**
- Verify IDs at TrackWrestling.com
- Update `scraper.py` if IDs changed
- Check if TrackWrestling changed HTML structure

## Maintenance Schedule

### Weekly (During Season)
- [ ] Spot check data accuracy
- [ ] Review Actions tab for failed runs

### Monthly
- [ ] Verify automatic updates still working
- [ ] Update team colors if needed
- [ ] Add new features as desired

### Start of New Season
- [ ] Update `TEAM_ID` in `scraper.py`
- [ ] Update `SEASON_ID` in `scraper.py`
- [ ] Test scraper with new IDs
- [ ] Commit and push changes

## Success Criteria

You'll know everything is working when:
- ✅ Site loads at GitHub Pages URL
- ✅ Data updates automatically every morning
- ✅ No manual data entry needed
- ✅ Changes to TrackWrestling appear on your site within 24 hours
- ✅ Site works on desktop and mobile
- ✅ No maintenance required (except new season setup)

## Support Resources

### Documentation
- `README.md` - Full technical documentation
- `DEPLOYMENT_GUIDE.md` - Step-by-step deployment
- This file - Checklist and verification

### GitHub Resources
- Actions Tab - View workflow runs
- Issues Tab - Report problems
- Settings → Pages - Configure hosting

### Key Files to Edit
- `scraper.py` - Update IDs for new season
- `styles.css` - Change colors/styling
- `index.html` - Modify content/layout
- `.github/workflows/update-data.yml` - Change update schedule

---

**Current Status:** _Check off items as you complete them_

**Deployment Date:** _______________

**Site URL:** https://shawneewrestling.github.io/shawnee_wrestling_home/

**Notes:**
_____________________________________________________________________
_____________________________________________________________________
_____________________________________________________________________
