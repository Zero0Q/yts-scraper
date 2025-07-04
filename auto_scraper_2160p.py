#!/usr/bin/env python3
"""
Automated 2160p Movie Scraper for Real-Debrid
Runs hourly to scrape high-quality 2160p movies from YTS
"""

import os
import sys
import subprocess
import logging
from datetime import datetime

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from yts_scraper.scraper import Scraper
import argparse

def setup_logging():
    """Setup logging for the automated scraper"""
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f'yts_scraper_{datetime.now().strftime("%Y%m%d")}.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

def create_args_for_2160p():
    """Create optimized arguments for 2160p movie scraping"""
    class Args:
        def __init__(self):
            # Output directory for 2160p movies
            self.output = 'Downloads/2160p_Movies'
            
            # Quality settings
            self.quality = '2160p'  # 4K/UHD quality
            
            # Genre settings - get all genres for maximum coverage
            self.genre = 'all'
            
            # Rating settings - all ratings (no minimum restriction)
            self.rating = '0'
            
            # Sort by latest to get newest releases first
            self.sort_by = 'latest'
            
            # Categorization - now using movie name and year organization
            self.categorize_by = 'none'
            
            # All years (no year restriction)
            self.year_limit = 0
            
            # Start from page 1
            self.page = 1
            
            # Download movie posters for better organization
            self.background = True
            
            # Include IMDb ID in filename for Real-Debrid compatibility
            self.imdb_id = True
            
            # Use multiprocessing for faster downloads (be careful with rate limits)
            self.multiprocess = False  # Set to False to avoid being blocked
            
            # Don't use CSV only mode - we want the torrent files
            self.csv_only = False
    
    return Args()

def run_scraper():
    """Run the YTS scraper with 2160p settings"""
    logger = setup_logging()
    
    try:
        logger.info("Starting automated 2160p movie scraper...")
        logger.info(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Create arguments for 2160p scraping
        args = create_args_for_2160p()
        
        # Log the configuration
        logger.info(f"Configuration:")
        logger.info(f"  Quality: {args.quality}")
        logger.info(f"  Genre: {args.genre}")
        logger.info(f"  Minimum Rating: {args.rating}")
        logger.info(f"  Year Limit: {args.year_limit}")
        logger.info(f"  Output Directory: {args.output}")
        logger.info(f"  Categorization: {args.categorize_by}")
        
        # Initialize and run the scraper
        scraper = Scraper(args)
        scraper.download()
        
        logger.info("Scraper completed successfully!")
        
        # Log statistics
        output_dir = os.path.join(os.getcwd(), args.output)
        if os.path.exists(output_dir):
            torrent_count = sum(len([f for f in files if f.endswith('.torrent')]) 
                              for _, _, files in os.walk(output_dir))
            logger.info(f"Total .torrent files in output directory: {torrent_count}")
        
    except KeyboardInterrupt:
        logger.warning("Scraper interrupted by user")
    except Exception as e:
        logger.error(f"Error occurred during scraping: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)

def main():
    """Main function"""
    run_scraper()

if __name__ == "__main__":
    main()