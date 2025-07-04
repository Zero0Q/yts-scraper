#!/usr/bin/env python3
"""
Real-Debrid Auto Upload Script
Automatically uploads magnet links to Real-Debrid using their API
"""

import os
import sys
import json
import requests
import logging
import time
from pathlib import Path
from datetime import datetime, timedelta

def setup_logging():
    """Setup logging for Real-Debrid upload"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

class RealDebridUploader:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.real-debrid.com/rest/1.0"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "YTS-Scraper-GitHub-Actions/1.0"
        }
        self.logger = setup_logging()
        
        # Rate limiting configuration
        self.rate_limit_delay = 2.0  # Seconds between requests
        self.max_retries = 3
        self.retry_delay = 10  # Seconds to wait before retry
        self.backoff_delay = 60  # Seconds to wait when hitting rate limits
        self.max_concurrent_downloads = 10  # Limit active downloads
        
        # Track upload state
        self.last_request_time = 0
        self.consecutive_rate_limits = 0
        self.active_downloads = 0
    
    def _wait_for_rate_limit(self):
        """Implement rate limiting between requests"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.rate_limit_delay:
            wait_time = self.rate_limit_delay - time_since_last
            self.logger.debug(f"⏱️  Rate limiting: waiting {wait_time:.1f}s")
            time.sleep(wait_time)
        
        self.last_request_time = time.time()
    
    def _handle_rate_limit_error(self, error_code):
        """Handle rate limit errors with exponential backoff"""
        self.consecutive_rate_limits += 1
        
        if error_code == 34:  # too_many_requests
            wait_time = self.backoff_delay * (2 ** min(self.consecutive_rate_limits - 1, 3))
            self.logger.warning(f"⏳ Rate limit hit. Waiting {wait_time}s before continuing...")
            time.sleep(wait_time)
        elif error_code == 21:  # too_many_active_downloads
            wait_time = self.backoff_delay * 2
            self.logger.warning(f"⏳ Too many active downloads. Waiting {wait_time}s for some to complete...")
            time.sleep(wait_time)
    
    def test_api_connection(self):
        """Test if the API key is valid"""
        try:
            self._wait_for_rate_limit()
            response = requests.get(
                f"{self.base_url}/user",
                headers=self.headers,
                timeout=10
            )
            if response.status_code == 200:
                user_info = response.json()
                self.logger.info(f"✅ Connected to Real-Debrid as: {user_info.get('username', 'Unknown')}")
                self.logger.info(f"📊 Premium days remaining: {user_info.get('premium', 0)}")
                return True
            else:
                self.logger.error(f"❌ API connection failed: {response.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"❌ API connection error: {e}")
            return False
    
    def upload_magnet_link(self, magnet_link, movie_info):
        """Upload a magnet link to Real-Debrid with retry logic"""
        movie_name = movie_info.get('movie_name', 'Unknown')
        quality = movie_info.get('quality', 'Unknown')
        
        for attempt in range(self.max_retries):
            try:
                self._wait_for_rate_limit()
                
                data = {'magnet': magnet_link}
                
                response = requests.post(
                    f"{self.base_url}/torrents/addMagnet",
                    headers=self.headers,
                    data=data,
                    timeout=30
                )
                
                if response.status_code == 201:
                    result = response.json()
                    torrent_id = result.get('id')
                    uri = result.get('uri')
                    self.logger.info(f"✅ Uploaded: {movie_name} ({quality}) (ID: {torrent_id})")
                    self.consecutive_rate_limits = 0  # Reset counter on success
                    self.active_downloads += 1
                    return {'success': True, 'id': torrent_id, 'uri': uri}
                else:
                    try:
                        error_data = response.json()
                        error_code = error_data.get('error_code')
                        error_msg = error_data.get('error', response.text)
                        
                        # Handle specific error codes
                        if error_code in [34, 21]:  # Rate limit or too many downloads
                            self._handle_rate_limit_error(error_code)
                            if attempt < self.max_retries - 1:
                                self.logger.info(f"🔄 Retrying {movie_name} (attempt {attempt + 2}/{self.max_retries})")
                                continue
                        
                        self.logger.error(f"❌ Failed to upload {movie_name}: {error_msg}")
                        return {'success': False, 'error': error_msg, 'error_code': error_code}
                        
                    except json.JSONDecodeError:
                        error_msg = response.text
                        self.logger.error(f"❌ Failed to upload {movie_name}: {error_msg}")
                        return {'success': False, 'error': error_msg}
                        
            except Exception as e:
                if attempt < self.max_retries - 1:
                    self.logger.warning(f"⚠️  Error uploading {movie_name} (attempt {attempt + 1}): {e}")
                    time.sleep(self.retry_delay)
                    continue
                else:
                    self.logger.error(f"❌ Error uploading {movie_name}: {e}")
                    return {'success': False, 'error': str(e)}
        
        return {'success': False, 'error': 'Max retries exceeded'}
    
    def get_torrent_info(self, torrent_id):
        """Get information about an uploaded torrent"""
        try:
            self._wait_for_rate_limit()
            response = requests.get(
                f"{self.base_url}/torrents/info/{torrent_id}",
                headers=self.headers,
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            self.logger.error(f"Error getting torrent info: {e}")
            return None
    
    def select_files(self, torrent_id):
        """Select all files in a torrent for download"""
        try:
            # First get torrent info to see available files
            torrent_info = self.get_torrent_info(torrent_id)
            if not torrent_info:
                return False
            
            # Select all files
            files = torrent_info.get('files', [])
            if files:
                file_ids = [str(f['id']) for f in files]
                data = {'files': ','.join(file_ids)}
                
                self._wait_for_rate_limit()
                response = requests.post(
                    f"{self.base_url}/torrents/selectFiles/{torrent_id}",
                    headers=self.headers,
                    data=data,
                    timeout=10
                )
                
                if response.status_code == 204:
                    self.logger.info(f"📁 Selected {len(file_ids)} files for torrent {torrent_id}")
                    return True
                else:
                    self.logger.error(f"Failed to select files for torrent {torrent_id}")
                    return False
            return True
            
        except Exception as e:
            self.logger.error(f"Error selecting files: {e}")
            return False
    
    def get_active_downloads_count(self):
        """Check how many downloads are currently active"""
        try:
            self._wait_for_rate_limit()
            response = requests.get(
                f"{self.base_url}/torrents",
                headers=self.headers,
                timeout=10
            )
            if response.status_code == 200:
                torrents = response.json()
                active_count = sum(1 for t in torrents if t.get('status') in ['downloading', 'queued'])
                return active_count
            return 0
        except Exception as e:
            self.logger.error(f"Error getting active downloads: {e}")
            return 0

def find_magnet_files(directory):
    """Find all .magnet files in the directory"""
    magnet_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.magnet'):
                magnet_files.append(os.path.join(root, file))
    return magnet_files

def load_magnet_info(magnet_file_path):
    """Load magnet link information from file"""
    try:
        with open(magnet_file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading magnet file {magnet_file_path}: {e}")
        return None

def main():
    """Main function with smart batching and rate limiting"""
    logger = setup_logging()
    
    # Get environment variables
    api_key = os.environ.get('REAL_DEBRID_API_KEY')
    magnet_dir = os.environ.get('TORRENT_DIR', 'Downloads/2160p_Movies')
    max_uploads_per_run = int(os.environ.get('MAX_UPLOADS_PER_RUN', '50'))  # Limit uploads per run
    
    if not api_key:
        logger.error("❌ REAL_DEBRID_API_KEY environment variable not set")
        logger.info("💡 To set up Real-Debrid integration:")
        logger.info("   1. Get your API key from https://real-debrid.com/apitoken")
        logger.info("   2. Add it as a GitHub secret named REAL_DEBRID_API_KEY")
        sys.exit(1)
    
    if not os.path.exists(magnet_dir):
        logger.warning(f"⚠️  Magnet directory not found: {magnet_dir}")
        logger.info("No magnet links to upload.")
        return
    
    # Initialize uploader
    uploader = RealDebridUploader(api_key)
    
    # Test API connection
    if not uploader.test_api_connection():
        logger.error("❌ Failed to connect to Real-Debrid API")
        sys.exit(1)
    
    # Check current active downloads
    active_downloads = uploader.get_active_downloads_count()
    logger.info(f"📊 Current active downloads: {active_downloads}")
    
    # Find magnet files
    magnet_files = find_magnet_files(magnet_dir)
    
    if not magnet_files:
        logger.info("📭 No .magnet files found to upload")
        return
    
    # Sort by newest first (based on file modification time)
    magnet_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    
    # Limit the number of uploads per run to avoid overwhelming Real-Debrid
    if len(magnet_files) > max_uploads_per_run:
        logger.info(f"🔍 Found {len(magnet_files)} magnet links, limiting to {max_uploads_per_run} uploads per run")
        magnet_files = magnet_files[:max_uploads_per_run]
    else:
        logger.info(f"🔍 Found {len(magnet_files)} magnet links to upload")
    
    # Upload magnet links with smart rate limiting
    successful_uploads = 0
    failed_uploads = 0
    skipped_uploads = 0
    
    for i, magnet_file in enumerate(magnet_files, 1):
        # Check if we should pause due to too many active downloads
        if uploader.active_downloads >= uploader.max_concurrent_downloads:
            logger.info(f"⏸️  Pausing uploads - too many active downloads ({uploader.active_downloads})")
            time.sleep(30)  # Wait for some downloads to complete
            uploader.active_downloads = uploader.get_active_downloads_count()
        
        magnet_info = load_magnet_info(magnet_file)
        if not magnet_info:
            failed_uploads += 1
            continue
            
        magnet_link = magnet_info.get('magnet_link')
        if not magnet_link:
            logger.error(f"❌ No magnet link found in {os.path.basename(magnet_file)}")
            failed_uploads += 1
            continue
        
        movie_name = magnet_info.get('movie_name', 'Unknown')
        quality = magnet_info.get('quality', 'Unknown')
        
        logger.info(f"📤 Uploading ({i}/{len(magnet_files)}): {movie_name} ({quality})")
        result = uploader.upload_magnet_link(magnet_link, magnet_info)
        
        if result['success']:
            successful_uploads += 1
            # Auto-select files for download
            torrent_id = result['id']
            uploader.select_files(torrent_id)
        else:
            # Check if we should skip remaining uploads due to persistent errors
            error_code = result.get('error_code')
            if error_code in [21, 34] and uploader.consecutive_rate_limits >= 3:
                logger.warning(f"⏸️  Too many consecutive rate limit errors. Skipping remaining {len(magnet_files) - i} uploads.")
                skipped_uploads = len(magnet_files) - i
                break
            failed_uploads += 1
        
        # Progress update every 10 uploads
        if i % 10 == 0:
            logger.info(f"📊 Progress: {i}/{len(magnet_files)} processed, {successful_uploads} successful, {failed_uploads} failed")
    
    # Summary
    total_processed = successful_uploads + failed_uploads
    logger.info(f"📊 Upload Summary:")
    logger.info(f"   ✅ Successful: {successful_uploads}")
    logger.info(f"   ❌ Failed: {failed_uploads}")
    if skipped_uploads > 0:
        logger.info(f"   ⏸️  Skipped: {skipped_uploads}")
    logger.info(f"   🧲 Total processed: {total_processed}")
    logger.info(f"   📁 Total magnet files found: {len(magnet_files) + skipped_uploads}")
    
    if failed_uploads > 0:
        logger.warning(f"⚠️  {failed_uploads} uploads failed. Check logs above for details.")
    
    if skipped_uploads > 0:
        logger.info(f"💡 {skipped_uploads} uploads were skipped due to rate limits. They will be processed in the next run.")
    
    # Calculate success rate
    if total_processed > 0:
        success_rate = (successful_uploads / total_processed) * 100
        logger.info(f"📈 Success rate: {success_rate:.1f}%")