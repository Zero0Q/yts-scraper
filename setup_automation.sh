#!/bin/bash

# Setup script for YTS 2160p Movie Scraper Automation
# This script helps configure hourly execution using cron

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRAPER_SCRIPT="$SCRIPT_DIR/run_hourly_scraper.sh"

echo "=== YTS 2160p Movie Scraper - Automation Setup ==="
echo ""
echo "This script will help you set up hourly automation for scraping 2160p movies."
echo ""

# Check if the scraper script exists
if [ ! -f "$SCRAPER_SCRIPT" ]; then
    echo "ERROR: Scraper script not found at $SCRAPER_SCRIPT"
    exit 1
fi

# Make sure the script is executable
chmod +x "$SCRAPER_SCRIPT"

echo "1. Testing the scraper script..."
echo "   This will run a test to make sure everything is working."
echo "   Press Enter to continue or Ctrl+C to cancel."
read

# Test run the scraper
echo "Running test scraper (this may take a few minutes)..."
if "$SCRAPER_SCRIPT"; then
    echo "✅ Test run completed successfully!"
else
    echo "❌ Test run failed. Please check the logs in $SCRIPT_DIR/logs/"
    exit 1
fi

echo ""
echo "2. Setting up hourly cron job..."
echo ""

# Create cron entry
CRON_ENTRY="0 * * * * $SCRAPER_SCRIPT >/dev/null 2>&1"

echo "The following cron entry will be added to run the scraper every hour:"
echo "$CRON_ENTRY"
echo ""
echo "This means the scraper will run at the top of every hour (e.g., 1:00, 2:00, 3:00, etc.)"
echo ""

# Check if cron entry already exists
if crontab -l 2>/dev/null | grep -q "$SCRAPER_SCRIPT"; then
    echo "⚠️  A cron job for this scraper already exists."
    echo "Would you like to replace it? (y/n): "
    read -r response
    if [[ "$response" != "y" && "$response" != "Y" ]]; then
        echo "Keeping existing cron job."
        exit 0
    fi
    # Remove existing entry
    crontab -l 2>/dev/null | grep -v "$SCRAPER_SCRIPT" | crontab -
fi

echo "Adding cron job..."

# Add new cron entry
(crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -

if [ $? -eq 0 ]; then
    echo "✅ Cron job added successfully!"
else
    echo "❌ Failed to add cron job. You may need to add it manually."
    echo "Manual cron entry: $CRON_ENTRY"
    exit 1
fi

echo ""
echo "=== Setup Complete! ==="
echo ""
echo "Your YTS 2160p movie scraper is now set up to run automatically every hour."
echo ""
echo "📁 Downloads will be saved to: $SCRIPT_DIR/Downloads/2160p_Movies/"
echo "📋 Logs will be saved to: $SCRIPT_DIR/logs/"
echo ""
echo "🔧 Management commands:"
echo "  View cron jobs:     crontab -l"
echo "  Remove cron job:    crontab -e (then delete the line)"
echo "  View recent logs:   tail -f $SCRIPT_DIR/logs/yts_scraper_$(date +%Y%m%d).log"
echo "  Manual test run:    $SCRAPER_SCRIPT"
echo ""
echo "📝 Configuration details:"
echo "  - Quality: 2160p (4K/UHD)"
echo "  - Minimum rating: 6.0"
echo "  - Year limit: Movies from $(date -v-5y +%Y) onwards"
echo "  - Includes movie posters and IMDb IDs"
echo "  - Organized by rating and genre"
echo ""
echo "💡 For Real-Debrid integration:"
echo "   1. The .torrent files will be saved in organized folders"
echo "   2. You can manually upload these to Real-Debrid"
echo "   3. Or set up a script to auto-upload using Real-Debrid API"
echo ""
echo "🚀 The scraper will start running at the next hour mark!"
echo "   Check the logs to monitor its progress."