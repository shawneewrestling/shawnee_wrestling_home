# 🚀 Quick Start Deployment Guide

## Step-by-Step Setup (10 minutes)

### 1. Upload Files to GitHub

**Option A: Using GitHub Web Interface**
1. Go to https://github.com/shawneewrestling/shawnee_wrestling_home
2. Click "Add file" → "Upload files"
3. Drag and drop all files from this folder
4. Commit with message: "Initial automated wrestling site setup"

**Option B: Using Git Command Line**
```bash
cd /path/to/your/local/folder
git init
git add .
git commit -m "Initial automated wrestling site setup"
git branch -M main
git remote add origin https://github.com/shawneewrestling/shawnee_wrestling_home.git
git push -u origin main
```

### 2. Enable GitHub Pages

1. Go to repository **Settings** → **Pages**
2. Under "Build and deployment":
   - **Source**: Select "GitHub Actions"
3. Click **Save**

### 3. Configure GitHub Actions Permissions

1. Go to **Settings** → **Actions** → **General**
2. Scroll to "Workflow permissions"
3. Select ✅ **"Read and write permissions"**
4. Check ✅ **"Allow GitHub Actions to create and approve pull requests"**
5. Click **Save**

### 4. Run Initial Workflow

1. Go to **Actions** tab
2. Click **"I understand my workflows, go ahead and enable them"** (if shown)
3. Click on **"Update Wrestling Data"** workflow
4. Click **"Run workflow"** dropdown → **"Run workflow"** button
5. Wait 1-2 minutes for green checkmark ✅

### 5. Access Your Live Site

Your site is now live at:
```
https://shawneewrestling.github.io/shawnee_wrestling_home/
```

Bookmark this URL! 🔖

---

## ✅ Verification Checklist

- [ ] Repository has all files uploaded
- [ ] GitHub Pages is set to "GitHub Actions" source
- [ ] Actions have "Read and write permissions"
- [ ] "Update Wrestling Data" workflow ran successfully
- [ ] "Deploy to GitHub Pages" workflow ran successfully
- [ ] Site loads at the GitHub Pages URL

---

## 🔧 What Happens Next?

### Automatic Daily Updates
- Every day at **6:00 AM EST**, GitHub Actions will:
  1. Scrape latest data from TrackWrestling
  2. Update `data/wrestling_data.json`
  3. Commit changes to repository
  4. Trigger site redeployment
  5. Your site shows new data within 2-3 minutes

### Manual Updates
To update data immediately:
1. Go to **Actions** tab
2. Click **"Update Wrestling Data"**
3. Click **"Run workflow"** → **"Run workflow"**

---

## 🎨 Customization Quick Tips

### Change Team Colors
Edit `styles.css` lines 1-5:
```css
:root {
    --primary-color: #003366;  /* Main color (header, etc) */
    --secondary-color: #FFD700; /* Accent color (nav hover) */
    --accent-color: #CC0000;    /* Highlight color */
}
```

### Update Header Text
Edit `index.html` lines 12-14:
```html
<h1>Shawnee Renegades</h1>
<p class="tagline">Wrestling</p>
```

### Change Update Time
Edit `.github/workflows/update-data.yml` line 5:
```yaml
- cron: '0 11 * * *'  # 6 AM EST
```

Common times:
- `0 11 * * *` - 6:00 AM EST
- `0 14 * * *` - 9:00 AM EST  
- `0 23 * * *` - 6:00 PM EST

---

## 🐛 Troubleshooting

### Site not loading?
1. Check Actions tab for failed workflows
2. Verify GitHub Pages is enabled
3. Wait 5 minutes after first deployment

### Data not updating?
1. Check if workflows are running in Actions tab
2. Verify scraper workflow completed successfully
3. Check if TrackWrestling URLs are still valid

### Need to update season?
Edit `scraper.py` lines 100-101:
```python
TEAM_ID_2025 = "768996150"      # Your team ID
SEASON_ID_2025 = "1560212138"   # Your season ID
```

---

## 📞 Next Steps

1. **Test the site** - Visit your GitHub Pages URL
2. **Bookmark it** - Add to your favorites
3. **Share it** - Send the URL to team, parents, fans
4. **Relax** - Everything updates automatically now! 

Your wrestling site is now fully automated! 🎉
