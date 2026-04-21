#!/usr/bin/env python3
"""
Phase 1: Link Collection Script
Standalone script for collecting job URLs from arbeitsagentur.de
Can be run independently or as part of full pipeline
"""

import sys
import logging
from pathlib import Path
from datetime import datetime

# Add config path and import centralized settings
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root / "src" / "config"))

try:
    from settings import PATHS
except ImportError as e:
    raise ImportError(
        f"[ERROR] Settings import failed: {e}\n"
        "Please ensure src/config/settings.py exists and contains required settings."
    )

# Add src to Python path
sys.path.append(str(project_root / "src"))

from scrapers.link_job import JobURLScraper

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Main function for Phase 1: Link Collection"""
    logger.info("=� PHASE 1: JOB URL COLLECTION")
    logger.info("=" * 50)
    
    try:
        # arbeitsagentur.de URL from assignment
        url = "https://www.arbeitsagentur.de/jobsuche/suche?angebotsart=4&ausbildungsart=0&arbeitszeit=vz&branche=22;1;2;9;3;5;7;10;11;16;12;21;26;15;17;19;20;8;23;29&veroeffentlichtseit=7&sort=veroeffdatum"
        
        # Initialize scraper
        logger.info("=' Initializing JobURLScraper...")
        scraper = JobURLScraper(url)
        
        # Check existing data
        existing_df = scraper.load_job_urls_from_csv()
        if existing_df is not None and len(existing_df) > 0:
            logger.info(f"=� Found existing {len(existing_df)} job URLs")
            choice = input("Use existing URLs? (y/n/i for incremental): ").strip().lower()
            
            if choice == 'y':
                logger.info(" Using existing job URLs")
                return True
            elif choice == 'i':
                logger.info("= Running incremental scrape...")
                df = scraper.incremental_scrape()
            else:
                logger.info("= Running full re-scrape...")
                df = scraper.run_scraping()
        else:
            logger.info("=w No existing data found, starting fresh scrape...")
            df = scraper.run_scraping()
        
        # Verify results
        if df is not None and len(df) > 0:
            logger.info(f" Phase 1 completed successfully!")
            logger.info(f"=� Total job URLs collected: {len(df)}")
            logger.info(f"📁 Saved to: {PATHS['input_csv']}")
            logger.info("=" * 50)
            return True
        else:
            logger.error("L Phase 1 failed - no URLs collected")
            return False
            
    except KeyboardInterrupt:
        logger.info("� Phase 1 interrupted by user")
        return False
    except Exception as e:
        logger.error(f"L Error in Phase 1: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)