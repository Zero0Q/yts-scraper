#!/usr/bin/env python3
"""
Real-Debrid Cached Upload Script
Only uploads torrents that are already cached on Real-Debrid for instant availability
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
    """Setup logging for Real-Debrid cached upload"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

class RealDebridCachedUploader:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.real-debrid.com/rest/1.0"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "YTS-Scraper-Cached/1.0"
        }
        self.logger = setup_logging()
        
        # Rate limiting - more conservative for cache checking
        self.rate_limit_delay = 1.0  # 1 second between requests
        self.last_request_time = 0
        self.cache_check_batch_size = 10  # Check 10 hashes at once
        
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
    
    def check_cache_availability(self, torrent_hashes):
        """Check if torrents are cached on Real-Debrid (batch operation)"""
        try:
            self._wait_for_rate_limit()
            
            # Real-Debrid expects hashes separated by '/'
            hash_string = '/'.join(torrent_hashes)
            
            response = requests.get(
                f"{self.base_url}/torrents/instantAvailability/{hash_string}",
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(f"❌ Cache check failed: {response.status_code}")
                return {}
                
        except Exception as e:
            self.logger.error(f"❌ Error checking cache availability: {e}")
            return {}
    
    def is_torrent_cached(self, torrent_hash, cache_data):
        """Check if a specific torrent hash is cached and has good quality files"""
        if torrent_hash not in cache_data:
            return False, []
            
        torrent_info = cache_data[torrent_hash]
        
        # Real-Debrid returns cache info for each quality/group
        cached_variants = []
        for variant_id, variant_info in torrent_info.items():
            if isinstance(variant_info, dict):
                # Check if this variant has files
                files = variant_info.get('files', [])
                if files:
                    # Look for video files (common video extensions)
                    video_extensions = ['.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v']
                    video_files = []
                    
                    for file_info in files:
                        filename = file_info.get('filename', '').lower()
                        if any(filename.endswith(ext) for ext in video_extensions):
                            video_files.append({
                                'filename': file_info.get('filename'),
                                'filesize': file_info.get('filesize', 0)
                            })
                    
                    if video_files:
                        cached_variants.append({
                            'variant_id': variant_id,
                            'video_files': video_files,
                            'total_files': len(files)
                        })
        
        return len(cached_variants) > 0, cached_variants
    
    def upload_cached_magnet(self, magnet_link, movie_info):
        """Upload a magnet link that's confirmed to be cached"""
        movie_name = movie_info.get('movie_name', 'Unknown')
        quality = movie_info.get('quality', 'Unknown')
        
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
                self.logger.info(f"✅ Uploaded cached torrent: {movie_name} ({quality}) (ID: {torrent_id})")
                return {'success': True, 'id': torrent_id, 'uri': result.get('uri')}
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', response.text)
                    self.logger.error(f"❌ Failed to upload {movie_name}: {error_msg}")
                    return {'success': False, 'error': error_msg}
                except json.JSONDecodeError:
                    self.logger.error(f"❌ Failed to upload {movie_name}: {response.text}")
                    return {'success': False, 'error': response.text}
                    
        except Exception as e:
            self.logger.error(f"❌ Error uploading {movie_name}: {e}")
            return {'success': False, 'error': str(e)}
    
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
                        self.logger.error(f"Failed to select files for torrent {torrent_id}")
                        return False
                else:
                    self.logger.warning(f"No files found for torrent {torrent_id}")
                    return True  # Still consider success if no files to select
            else:
                self.logger.error(f"Failed to get torrent info for {torrent_id}")
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

def extract_hash_from_magnet(magnet_link):
    """Extract the torrent hash from a magnet link"""
    try:
        # Magnet links format: magnet:?xt=urn:btih:HASH&...
        if 'xt=urn:btih:' in magnet_link:
            start = magnet_link.find('xt=urn:btih:') + 12
            end = magnet_link.find('&', start)
            if end == -1:
                hash_value = magnet_link[start:]
            else:
                hash_value = magnet_link[start:end]
            return hash_value.upper()
    except Exception as e:
        logging.error(f"Error extracting hash from magnet link: {e}")
    return None

def main():
    """Main function - only upload cached torrents"""
    logger = setup_logging()
    
    # Get environment variables
    api_key = os.environ.get('REAL_DEBRID_API_KEY')
    magnet_dir = os.environ.get('TORRENT_DIR', 'Downloads/2160p_Movies')
    max_uploads_per_run = int(os.environ.get('MAX_CACHED_UPLOADS_PER_RUN', '100'))  # Higher limit since we're only doing cached
    
    if not api_key:
        logger.error("❌ REAL_DEBRID_API_KEY environment variable not set")
        logger.info("💡 To set up Real-Debrid integration:")
        logger.info("   1. Get your API key from https://real-debrid.com/apitoken")
        logger.info("   2. Add it as a GitHub secret named REAL_DEBRID_API_KEY")
        sys.exit(1)
    
    if not os.path.exists(magnet_dir):
        logger.warning(f"⚠️  Magnet directory not found: {magnet_dir}")
        logger.info("No magnet links to check.")
        return
    
    # Initialize uploader
    uploader = RealDebridCachedUploader(api_key)
    
    # Test API connection
    if not uploader.test_api_connection():
        logger.error("❌ Failed to connect to Real-Debrid API")
        sys.exit(1)
    
    # Find magnet files
    magnet_files = find_magnet_files(magnet_dir)
    
    if not magnet_files:
        logger.info("📭 No .magnet files found to check")
        return
    
    # Sort by newest first
    magnet_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    
    # Limit the number to check per run
    if len(magnet_files) > max_uploads_per_run:
        logger.info(f"🔍 Found {len(magnet_files)} magnet links, checking {max_uploads_per_run} for cache status")
        magnet_files = magnet_files[:max_uploads_per_run]
    else:
        logger.info(f"🔍 Found {len(magnet_files)} magnet links to check for cache status")
    
    # Load magnet info and extract hashes
    magnet_data = []
    for magnet_file in magnet_files:
        magnet_info = load_magnet_info(magnet_file)
        if magnet_info and magnet_info.get('magnet_link'):
            torrent_hash = extract_hash_from_magnet(magnet_info['magnet_link'])
            if torrent_hash:
                magnet_data.append({
                    'file_path': magnet_file,
                    'hash': torrent_hash,
                    'magnet_info': magnet_info
                })
    
    if not magnet_data:
        logger.warning("⚠️  No valid magnet links found")
        return
    
    logger.info(f"🔍 Checking cache status for {len(magnet_data)} torrents...")
    
    # Check cache availability in batches
    cached_torrents = []
    uncached_torrents = []
    
    for i in range(0, len(magnet_data), uploader.cache_check_batch_size):
        batch = magnet_data[i:i + uploader.cache_check_batch_size]
        batch_hashes = [item['hash'] for item in batch]
        
        logger.info(f"🔍 Checking batch {i//uploader.cache_check_batch_size + 1}/{(len(magnet_data) + uploader.cache_check_batch_size - 1)//uploader.cache_check_batch_size}")
        
        cache_data = uploader.check_cache_availability(batch_hashes)
        
        for item in batch:
            is_cached, variants = uploader.is_torrent_cached(item['hash'], cache_data)
            
            if is_cached:
                cached_torrents.append({
                    **item,
                    'variants': variants
                })
                movie_name = item['magnet_info'].get('movie_name', 'Unknown')
                quality = item['magnet_info'].get('quality', 'Unknown')
                logger.info(f"✅ CACHED: {movie_name} ({quality}) - {len(variants)} variant(s)")
            else:
                uncached_torrents.append(item)
                movie_name = item['magnet_info'].get('movie_name', 'Unknown')
                quality = item['magnet_info'].get('quality', 'Unknown')
                logger.info(f"❌ NOT CACHED: {movie_name} ({quality})")
    
    # Summary of cache check
    logger.info(f"\n📊 Cache Check Results:")
    logger.info(f"   ✅ Cached: {len(cached_torrents)}")
    logger.info(f"   ❌ Not Cached: {len(uncached_torrents)}")
    logger.info(f"   📈 Cache Rate: {(len(cached_torrents)/len(magnet_data)*100):.1f}%")
    
    if not cached_torrents:
        logger.info("💡 No cached torrents found. Try again later as cache status can change.")
        return
    
    # Upload only cached torrents
    logger.info(f"\n🚀 Uploading {len(cached_torrents)} cached torrents...")
    
    successful_uploads = 0
    failed_uploads = 0
    
    for i, torrent_data in enumerate(cached_torrents, 1):
        magnet_info = torrent_data['magnet_info']
        magnet_link = magnet_info['magnet_link']
        movie_name = magnet_info.get('movie_name', 'Unknown')
        quality = magnet_info.get('quality', 'Unknown')
        
        logger.info(f"📤 Uploading ({i}/{len(cached_torrents)}): {movie_name} ({quality})")
        result = uploader.upload_cached_magnet(magnet_link, magnet_info)
        
        if result['success']:
            successful_uploads += 1
            # Auto-select files for download
            torrent_id = result['id']
            uploader.select_files(torrent_id)
        else:
            failed_uploads += 1
    
    # Final summary
    logger.info(f"\n📊 Final Summary:")
    logger.info(f"   🔍 Total torrents checked: {len(magnet_data)}")
    logger.info(f"   ✅ Cached torrents found: {len(cached_torrents)}")
    logger.info(f"   📤 Successfully uploaded: {successful_uploads}")
    logger.info(f"   ❌ Failed uploads: {failed_uploads}")
    logger.info(f"   💾 Cache hit rate: {(len(cached_torrents)/len(magnet_data)*100):.1f}%")
    
    if successful_uploads > 0:
        logger.info(f"🎉 {successful_uploads} movies are now available for instant download!")

if __name__ == "__main__":
    main()