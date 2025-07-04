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
from pathlib import Path

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
    
    def test_api_connection(self):
        """Test if the API key is valid"""
        try:
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
        """Upload a magnet link to Real-Debrid"""
        try:
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
                movie_name = movie_info.get('movie_name', 'Unknown')
                quality = movie_info.get('quality', 'Unknown')
                self.logger.info(f"✅ Uploaded: {movie_name} ({quality}) (ID: {torrent_id})")
                return {'success': True, 'id': torrent_id, 'uri': uri}
            else:
                error_msg = response.text
                movie_name = movie_info.get('movie_name', 'Unknown')
                self.logger.error(f"❌ Failed to upload {movie_name}: {error_msg}")
                return {'success': False, 'error': error_msg}
                
        except Exception as e:
            movie_name = movie_info.get('movie_name', 'Unknown')
            self.logger.error(f"❌ Error uploading {movie_name}: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_torrent_info(self, torrent_id):
        """Get information about an uploaded torrent"""
        try:
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
    """Main function"""
    logger = setup_logging()
    
    # Get environment variables
    api_key = os.environ.get('REAL_DEBRID_API_KEY')
    magnet_dir = os.environ.get('TORRENT_DIR', 'Downloads/2160p_Movies')
    
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
    
    # Find magnet files
    magnet_files = find_magnet_files(magnet_dir)
    
    if not magnet_files:
        logger.info("📭 No .magnet files found to upload")
        return
    
    logger.info(f"🔍 Found {len(magnet_files)} magnet links to upload")
    
    # Upload magnet links
    successful_uploads = 0
    failed_uploads = 0
    
    for magnet_file in magnet_files:
        magnet_info = load_magnet_info(magnet_file)
        if not magnet_info:
            failed_uploads += 1
            continue
            
        magnet_link = magnet_info.get('magnet_link')
        if not magnet_link:
            logger.error(f"❌ No magnet link found in {os.path.basename(magnet_file)}")
            failed_uploads += 1
            continue
            
        logger.info(f"📤 Uploading: {magnet_info.get('movie_name', 'Unknown')} ({magnet_info.get('quality', 'Unknown')})")
        result = uploader.upload_magnet_link(magnet_link, magnet_info)
        
        if result['success']:
            successful_uploads += 1
            # Auto-select files for download
            torrent_id = result['id']
            uploader.select_files(torrent_id)
        else:
            failed_uploads += 1
    
    # Summary
    logger.info(f"📊 Upload Summary:")
    logger.info(f"   ✅ Successful: {successful_uploads}")
    logger.info(f"   ❌ Failed: {failed_uploads}")
    logger.info(f"   🧲 Total magnet links: {len(magnet_files)}")
    
    if failed_uploads > 0:
        logger.warning(f"⚠️  {failed_uploads} uploads failed. Check logs above for details.")

if __name__ == "__main__":
    main()