# GitHub Actions Setup for YTS 2160p Movie Scraper

## 🚀 Yes, it can run from GitHub Actions!

I've created a complete GitHub Actions automation that offers several advantages over local cron jobs:

- **☁️ Cloud-based**: Runs on GitHub's servers, no need to keep your computer on
- **🆓 Free**: GitHub provides 2,000 minutes/month for free accounts
- **🔄 Reliable**: Professional infrastructure with better uptime
- **📦 Automated**: Handles dependencies and environment setup automatically
- **🗂️ Organized**: Automatic artifact management and releases

## 📋 Available Workflows

### 1. Basic Scraper (`scraper.yml`)
- Runs every hour
- Downloads 2160p torrents
- Uploads files as GitHub artifacts
- Creates weekly releases with all torrents

### 2. Real-Debrid Integration (`scraper-realDebrid.yml`) 
- Everything from basic scraper
- **Automatically uploads torrents to Real-Debrid**
- Selects all files for instant streaming
- Full API integration

## 🛠️ Setup Instructions

### Step 1: Push to GitHub
```bash
git add .
git commit -m "Add GitHub Actions automation"
git push origin main
```

### Step 2: Enable GitHub Actions
1. Go to your GitHub repository
2. Click the "Actions" tab
3. Enable workflows if prompted

### Step 3: (Optional) Add Real-Debrid Integration
For automatic Real-Debrid uploads:

1. Get your Real-Debrid API key:
   - Go to https://real-debrid.com/apitoken
   - Generate a new token

2. Add it as a GitHub secret:
   - Go to your repo → Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `REAL_DEBRID_API_KEY`
   - Value: Your API token

### Step 4: Choose Your Workflow
- **Basic**: The `scraper.yml` will run automatically
- **Real-Debrid**: Rename `scraper-realDebrid.yml` to `scraper.yml` to use Real-Debrid integration

## 📊 How It Works

### Hourly Execution
```yaml
schedule:
  - cron: '0 * * * *'  # Every hour at minute 0
```

### Quality Settings
- **2160p only** (4K/UHD)
- **Minimum 6.0 rating**
- **Recent movies** (2020+)
- **All genres**

### File Organization
```
Downloads/2160p_Movies/
├── 6+/action/Movie.Name.2160p-imdb123.torrent
├── 7+/drama/Another.Movie.2160p-imdb456.torrent
└── 8+/sci-fi/Great.Movie.2160p-imdb789.torrent
```

## 📦 Artifact Management

### Hourly Artifacts
- **Torrents**: Keep for 30 days
- **Logs**: Keep for 7 days
- **Auto-cleanup**: Only keep last 10 runs

### Weekly Releases
- Created every Sunday at midnight
- Contains all torrents from the week
- Perfect for batch downloading
- Includes movie posters

## 🔗 Real-Debrid Integration Features

When Real-Debrid is configured:
- ✅ Automatic torrent upload
- ✅ File selection for streaming
- ✅ Error handling and retry logic
- ✅ Usage monitoring and logging
- ✅ API rate limiting respect

## 📋 Monitoring & Management

### View Workflow Runs
- Go to Actions tab in your GitHub repo
- Click on workflow runs to see logs
- Download artifacts from completed runs

### Manual Trigger
- Actions tab → Select workflow → "Run workflow" button
- Useful for testing or getting movies immediately

### Logs & Debugging
- Real-time logs in GitHub Actions interface
- Downloadable log artifacts
- Real-Debrid upload status and statistics

## 🎯 Benefits Over Local Cron

| Feature | Local Cron | GitHub Actions |
|---------|------------|----------------|
| **Reliability** | Depends on your computer | GitHub's infrastructure |
| **Power Usage** | Your computer must stay on | Zero local power usage |
| **Maintenance** | Manual dependency updates | Automatic environment setup |
| **Monitoring** | Basic logs | Rich web interface |
| **Scalability** | Limited by your hardware | GitHub's cloud resources |
| **Cost** | Electricity + hardware | Free (up to limits) |

## ⚙️ Customization

### Change Schedule
Edit the cron expression in the workflow file:
```yaml
schedule:
  - cron: '0 */2 * * *'  # Every 2 hours
  - cron: '0 9,21 * * *'  # Twice daily at 9 AM and 9 PM
```

### Modify Quality Settings
Edit `auto_scraper_2160p.py`:
```python
self.rating = '7'  # Higher minimum rating
self.year_limit = 2022  # Only newer movies
```

## 🚨 Important Notes

- **GitHub Limits**: 2,000 minutes/month free (usually sufficient)
- **YTS Rate Limits**: Workflow includes respectful delays
- **Storage**: Artifacts auto-expire to manage storage
- **Privacy**: Logs may contain movie titles (they're in your private repo)

## 🎬 Ready to Start?

1. **Immediate**: Push the code and it starts working in the cloud
2. **Local Backup**: Keep the local cron setup as backup
3. **Best of Both**: Use GitHub Actions as primary, local as fallback

The GitHub Actions solution is more robust and reliable than local cron jobs!