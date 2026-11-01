# Shawnee Wrestling Home (site-v2 closeout branch)

> **Branch `site-v2-2025-26-closeout`**: static multi-page preview simulating 2025-26 season closeout.
> Not live. Do not deploy to Hostinger from this branch. Data from Trackwrestling seasonId `1560212138` / teamId `768996150`.

Pages: Home · Roster · Schedule/Results · Standings · Stats · Awards (chevron cards).

Update data:
```bash
python update_site_data.py            # scrape TW + rebuild awards/career
python update_site_data.py --skip-scrape
python -m http.server 8080            # then open index.html
```

Docs: `docs/AUTO_AWARDS.md`, `docs/CAREER.md`.

---

# Shawnee Wrestling Automation

Automated wrestling website for Shawnee High School that pulls roster, schedule, and results data from TrackWrestling daily.

## 🎯 Features

- **Daily Automated Updates**: Scrapes TrackWrestling data every day at 6 AM EST
- **Clean, Professional Design**: Modern responsive website matching school colors
- **Zero Maintenance**: Once set up, runs completely automatically
- **GitHub Pages Hosting**: Free hosting with automatic deployment
- **Mobile Friendly**: Responsive design works on all devices

## 📋 Setup Instructions

### Step 1: Initial Repository Setup

1. Make sure this repository is named `shawnee_wrestling_home`
2. Go to repository Settings → Pages
3. Under "Build and deployment":
   - Source: GitHub Actions
   - (No need to select a branch)

### Step 2: Configure Repository Permissions

1. Go to Settings → Actions → General
2. Scroll to "Workflow permissions"
3. Select "Read and write permissions"
4. Check "Allow GitHub Actions to create and approve pull requests"
5. Click "Save"

### Step 3: Initialize Data Directory

Run the scraper manually first to create the data structure:

```bash
# Install Python dependencies
pip install -r requirements.txt

# Run scraper to create initial data
python scraper.py
```

This creates `data/wrestling_data.json` with the initial data.

### Step 4: Push to GitHub

```bash
git add .
git commit -m "Initial setup of Shawnee wrestling automation"
git push origin main
```

### Step 5: Enable GitHub Actions

1. Go to the "Actions" tab in your repository
2. If prompted, click "I understand my workflows, go ahead and enable them"
3. Click on "Update Wrestling Data" workflow
4. Click "Run workflow" → "Run workflow" to test it
5. Wait for it to complete (green checkmark)

### Step 6: Access Your Site

Your site will be available at:
```
https://shawneewrestling.github.io/shawnee_wrestling_home/
```

## 🔧 Configuration

### Update Season/Team IDs

**Easy Method (Recommended):**
Run the interactive update script:
```bash
python update_season.py
```

**Manual Method:**
Edit `season_config.py`:
```python
CURRENT_SEASON = "2025-26"
TEAM_ID = "new_team_id"
SEASON_ID = "new_season_id"
```

Then commit and push:
```bash
git add season_config.py
git commit -m "Update to 2025-26 season"
git push origin main
```

See `SEASON_UPDATE_GUIDE.md` for detailed instructions on finding new IDs.

### Change Update Schedule

To modify when data updates run, edit `.github/workflows/update-data.yml`:

```yaml
schedule:
  - cron: '0 11 * * *'  # Daily at 6 AM EST (11 AM UTC)
```

Cron format: `minute hour day month dayofweek`
- `0 11 * * *` = 11:00 UTC daily (6 AM EST)
- `0 14 * * *` = 9:00 AM EST
- `0 */6 * * *` = Every 6 hours

## 📁 Project Structure

```
shawnee_wrestling_home/
├── .github/
│   └── workflows/
│       ├── update-data.yml      # Daily data scraping
│       └── deploy-pages.yml     # Site deployment
├── data/
│   └── wrestling_data.json      # Scraped data (auto-generated)
├── index.html                   # Main website page
├── styles.css                   # Styling
├── app.js                       # Dynamic data loading
├── scraper.py                   # TrackWrestling scraper
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

## 🔄 How It Works

1. **Daily Trigger**: GitHub Actions runs the scraper every morning at 6 AM EST
2. **Data Scraping**: Python script fetches latest data from TrackWrestling
3. **Data Storage**: Updates `data/wrestling_data.json` with new information
4. **Auto Commit**: GitHub Actions commits changes if data has changed
5. **Auto Deploy**: Changes trigger GitHub Pages to rebuild the site
6. **Live Update**: Site reflects new data within minutes

## 🎨 Customization

### Colors

Edit CSS variables in `styles.css`:

```css
:root {
    --primary-color: #003366;  /* Navy blue */
    --secondary-color: #FFD700; /* Gold */
    --accent-color: #CC0000;    /* Red */
}
```

### Content

- **Header**: Edit `index.html` header section
- **Footer**: Edit `index.html` footer section
- **Sections**: Add/remove sections in `index.html`

## 🐛 Troubleshooting

### Data not updating?

1. Check Actions tab for failed workflows
2. Click on failed run to see error logs
3. Most common issue: TrackWrestling changed their HTML structure

### Site not deploying?

1. Verify GitHub Pages is enabled in Settings
2. Check Actions tab for deployment failures
3. Ensure "Read and write permissions" are enabled for Actions

### Scraper failing?

1. Verify season/team IDs are correct
2. Check if TrackWrestling changed their URL structure
3. Test scraper locally: `python scraper.py`

## 📊 Data Format

The `wrestling_data.json` file structure:

```json
{
  "metadata": {
    "team_id": "768996150",
    "season_id": "1560212138",
    "last_updated": "2024-12-10T10:30:00",
    "team_name": "Shawnee High School"
  },
  "roster": [
    {
      "name": "John Doe",
      "weight_class": "152",
      "grade": "Senior",
      "record": "12-3"
    }
  ],
  "schedule": [
    {
      "date": "2024-12-14",
      "opponent": "West Windsor-Plainsboro North",
      "location": "Shawnee High School",
      "time": "9:00 AM",
      "result": "TBD"
    }
  ],
  "results": [
    {
      "date": "2024-12-14",
      "opponent": "West Windsor-Plainsboro North",
      "score": "45-30",
      "result": "Win",
      "location": "Shawnee High School"
    }
  ]
}
```

## 🚀 Advanced Features

### Manual Trigger

You can manually trigger data updates:
1. Go to Actions tab
2. Click "Update Wrestling Data"
3. Click "Run workflow" button
4. Select branch (main)
5. Click "Run workflow"

### Local Development

Test the site locally:

```bash
# Simple HTTP server
python -m http.server 8000

# Then visit: http://localhost:8000
```

## 📝 License

This project is open source and available for use by other wrestling programs.

## 🤝 Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review GitHub Actions logs
3. Open an issue in this repository

## 🏆 Credits

Built for Shawnee High School Wrestling
Data provided by TrackWrestling.com
