# 🔑 Real-Debrid GitHub Secrets Setup Guide

## Step-by-Step Instructions

### 1. Get Your Real-Debrid API Key
1. Visit **https://real-debrid.com/apitoken**
2. Log in to your Real-Debrid account
3. Click **"Generate"** to create a new API token
4. **Copy the generated token** (keep it secure!)

### 2. Add API Key to GitHub Secrets
1. Go to your repository on GitHub
2. Click **"Settings"** (in the top menu of your repo)
3. In the left sidebar, click **"Secrets and variables"** → **"Actions"**
4. Click **"New repository secret"**
5. Enter:
   - **Name:** `REAL_DEBRID_API_KEY`
   - **Secret:** [paste your API token here]
6. Click **"Add secret"**

### 3. Verify the Setup
Once you've added the secret, your workflow will automatically:
- ✅ Scrape 2160p movies every hour
- ✅ Upload .torrent files to Real-Debrid automatically
- ✅ Select all files for instant streaming
- ✅ Log all activities for monitoring

### 4. Test the Integration
You can manually trigger a test run:
1. Go to **Actions** tab in your repo
2. Click **"YTS 2160p Movie Scraper with Real-Debrid"**
3. Click **"Run workflow"** button
4. Click **"Run workflow"** to confirm

### 5. Monitor the Results
After running, check:
- **Action logs** to see Real-Debrid upload status
- **Your Real-Debrid account** for new torrents
- **Downloads artifacts** for the .torrent files

## 🔒 Security Notes
- The API key is securely stored in GitHub's encrypted secrets
- It's only accessible to your GitHub Actions workflows
- Never commit API keys directly to your code

## 🎬 What Happens Now
Every hour at the top of the hour (1:00, 2:00, 3:00, etc.), the system will:
1. Scrape YTS for new 2160p movies (rating 6.0+)
2. Download .torrent files and organize them
3. **Automatically upload torrents to Real-Debrid**
4. **Select all files for instant availability**
5. Store backups as GitHub artifacts
6. Create weekly releases for batch access

Your movies will be ready to stream on Real-Debrid immediately after each hourly run!