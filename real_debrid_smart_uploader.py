#!/usr/bin/env python3
"""
Real-Debrid Smart Upload Script
Uploads torrents to Real-Debrid with intelligent rate limiting and error handling
"""

import os
import sys
import json
import requests
import logging
import time
from pathlib import Path
from datetime import datetime

def setup_logging():
    """Setup logging for Real-Debrid upload"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

class RealDebridSmartUploader:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.real-debrid.com/rest/1.0"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "YTS-Scraper-Smart/1.0"
        }
        self.logger = setup_logging()
        
        # Conservative rate limiting to avoid 403 errors
        self.rate_limit_delay = 3.0  # 3 seconds between requests
        self.last_request_time = 0
        self.max_retries = 2
        self.backoff_delay = 30  # Wait 30s on rate limit errors
        
    def _wait_for_rate_limit(self):
        """Implement rate limiting between requests"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.rate_limit_delay:
            wait_time = self.rate_limit_delay - time_since_last
            time.sleep(wait_time)
        
        self.last_request_time = time.time()
    
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
    
    def upload_magnet(self, magnet_link, movie_info):
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
                    self.logger.info(f"✅ Uploaded: {movie_name} ({quality}) (ID: {torrent_id})")
                    return {'success': True, 'id': torrent_id, 'uri': result.get('uri')}
                else:
                    try:
                        error_data = response.json()
                        error_code = error_data.get('error_code')
                        error_msg = error_data.get('error', response.text)
                        
                        # Handle specific error codes
                        if error_code in [34, 21]:  # Rate limit or too many downloads
                            if attempt < self.max_retries - 1:
                                self.logger.warning(f"⏳ Rate limit/quota hit for {movie_name}. Waiting {self.backoff_delay}s...")
                                time.sleep(self.backoff_delay)
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
                    time.sleep(10)
                    continue
                else:
                    self.logger.error(f"❌ Error uploading {movie_name}: {e}")
                    return {'success': False, 'error': str(e)}
        
        return {'success': False, 'error': 'Max retries exceeded'}
    
    def select_files(self, torrent_id):
        """Select all files in a torrent for download"""
        try:
            self._wait_for_rate_limit()
            
            # Get torrent info first
            response = requests.get(
                f"{self.base_url}/torrents/info/{torrent_id}",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                torrent_info = response.json()
                files = torrent_info.get('files', [])
                
                if files:
                    # Select all files
                    file_ids = [str(f['id']) for f in files]
                    data = {'files': ','.join(file_ids)}
                    
                    self._wait_for_rate_limit()
                    select_response = requests.post(
                        f"{self.base_url}/torrents/selectFiles/{torrent_id}",
                        headers=self.headers,
                        data=data,
                        timeout=10
                    )
                    
                    if select_response.status_code == 204:
                        self.logger.info(f"📁 Selected {len(file_ids)} files for torrent {torrent_id}")
                        return True
                    else:
                        self.logger.warning(f"Failed to select files for torrent {torrent_id}")
                        return False
                else:
                    self.logger.info(f"No files to select for torrent {torrent_id}")
                    return True
            else:
                self.logger.warning(f"Failed to get torrent info for {torrent_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error selecting files for torrent {torrent_id}: {e}")
            return False

def find_magnet_files(directory):
    """Find all .magnet files in the directory"""
    magnet_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.magnet'):
                magnet_files.append(os.path.join(root, file))
    return magnet_files

def load_magnet_info(magnet_file_path):
    """Load magnet info from .magnet file"""
    try:
        with open(magnet_file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading magnet file {magnet_file_path}: {e}")
        return None

def main():
    """Main function - smart upload with rate limiting"""
    logger = setup_logging()
    
    # Get environment variables
    api_key = os.environ.get('REAL_DEBRID_API_KEY')
    magnet_dir = os.environ.get('TORRENT_DIR', 'Downloads/2160p_Movies')
    max_uploads_per_run = int(os.environ.get('MAX_UPLOADS_PER_RUN', '20'))  # Conservative limit
    
    if not api_key:
        logger.error("❌ REAL_DEBRID_API_KEY environment variable not set")
        sys.exit(1)
    
    if not os.path.exists(magnet_dir):
        logger.warning(f"⚠️  Magnet directory not found: {magnet_dir}")
        return
    
    # Initialize uploader
    uploader = RealDebridSmartUploader(api_key)
    
    # Test API connection
    if not uploader.test_api_connection():
        logger.error("❌ Failed to connect to Real-Debrid API")
        sys.exit(1)
    
    # Find magnet files
    magnet_files = find_magnet_files(magnet_dir)
    
    if not magnet_files:
        logger.info("📭 No .magnet files found to upload")
        return
    
    # Sort by newest first
    magnet_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    
    # Limit uploads to avoid overwhelming Real-Debrid
    if len(magnet_files) > max_uploads_per_run:
        logger.info(f"🔍 Found {len(magnet_files)} magnet files, uploading {max_uploads_per_run} per run")
        magnet_files = magnet_files[:max_uploads_per_run]
    else:
        logger.info(f"🔍 Found {len(magnet_files)} magnet files to upload")
    
    # Upload magnets with smart rate limiting
    successful_uploads = 0
    failed_uploads = 0
    consecutive_failures = 0
    
    for i, magnet_file in enumerate(magnet_files, 1):
        magnet_info = load_magnet_info(magnet_file)
        if not magnet_info or not magnet_info.get('magnet_link'):
            failed_uploads += 1
            continue
            
        movie_name = magnet_info.get('movie_name', 'Unknown')
        quality = magnet_info.get('quality', 'Unknown')
        
        logger.info(f"📤 Uploading ({i}/{len(magnet_files)}): {movie_name} ({quality})")
        result = uploader.upload_magnet(magnet_info['magnet_link'], magnet_info)
        
        if result['success']:
            successful_uploads += 1
            consecutive_failures = 0
            # Auto-select files for download
            torrent_id = result['id']
            uploader.select_files(torrent_id)
        else:
            failed_uploads += 1
            consecutive_failures += 1
            
            # Stop if too many consecutive failures (likely rate limited)
            if consecutive_failures >= 5:
                logger.warning(f"⏸️  Too many consecutive failures ({consecutive_failures}). Stopping to avoid rate limits.")
                logger.info(f"💡 Remaining {len(magnet_files) - i} files will be processed in next run.")
                break
    
    # Final summary
    logger.info(f"\n📊 Upload Summary:")
    logger.info(f"   ✅ Successful: {successful_uploads}")
    logger.info(f"   ❌ Failed: {failed_uploads}")
    logger.info(f"   📁 Total processed: {successful_uploads + failed_uploads}")
    
    if successful_uploads > 0:
        logger.info(f"🎉 {successful_uploads} movies are now available in Real-Debrid!")
    
    if failed_uploads > 0:
        logger.info(f"💡 {failed_uploads} uploads failed. They will be retried in future runs.")

if __name__ == "__main__":
    main()