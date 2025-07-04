#!/bin/bash

# YTS 2160p Movie Scraper - Hourly Automation Script
# This script runs the Python scraper and handles environment setup

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Set up environment variables
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

# Log file for the shell script
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
SHELL_LOG="$LOG_DIR/automation_$(date +%Y%m%d).log"

# Function to log messages
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$SHELL_LOG"
}

log_message "Starting YTS 2160p scraper automation..."

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    log_message "ERROR: Python3 not found. Please install Python3."
    exit 1
fi

# Check if required packages are installed
python3 -c "import requests, tqdm, fake_useragent" 2>/dev/null
if [ $? -ne 0 ]; then
    log_message "WARNING: Some Python packages may be missing. Attempting to install..."
    pip3 install requests tqdm fake-useragent
fi

# Run the Python scraper
log_message "Executing Python scraper..."
python3 "$SCRIPT_DIR/auto_scraper_2160p.py" 2>&1 | tee -a "$SHELL_LOG"

# Check exit status
if [ $? -eq 0 ]; then
    log_message "Scraper completed successfully."
else
    log_message "ERROR: Scraper failed with exit code $?"
    exit 1
fi

# Optional: Clean up old log files (keep last 30 days)
find "$LOG_DIR" -name "*.log" -mtime +30 -delete 2>/dev/null

log_message "Automation script completed."