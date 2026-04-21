#!/usr/bin/env python3
"""
Phase 2: Job Scraping Script
Standalone script for scraping job details with CAPTCHA solving
Can be run independently or as part of full pipeline
"""

import asyncio
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

from scrapers.job_scraper import JobScraper

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Main function for Phase 2: Job Scraping"""
    logger.info("=� PHASE 2: JOB DETAILS SCRAPING")
    logger.info("=" * 50)
    
    try:
        # Configuration options
        logger.info("=' Configuration Options:")
        
        # CAPTCHA solving mode
        captcha_choice = input("Enable auto-CAPTCHA solving with TrOCR? (y/n): ").strip().lower()
        auto_solve_captcha = captcha_choice == 'y'
        
        if auto_solve_captcha:
            logger.info("> TrOCR auto-CAPTCHA solver enabled")
            logger.info("=� First job may need CAPTCHA, then others should be fast")
        else:
            logger.info("=d Manual CAPTCHA solving mode")
            logger.info("=� You'll need to solve CAPTCHAs manually when they appear")
        
        # Resume option
        resume_choice = input("Resume from existing progress? (y/n): ").strip().lower()
        resume = resume_choice == 'y'
        
        # Initialize job scraper
        logger.info("=' Initializing JobScraper...")
        scraper = JobScraper(auto_solve_captcha=auto_solve_captcha)
        
        # Check for input file
        input_path = Path(PATHS['input_csv'])
        if not input_path.exists():
            logger.error("[ERROR] job_urls.csv not found!")
            logger.error("📋 Please run Phase 1 (run_link_scraper.py) first")
            return False
        
        logger.info(f"📁 Input file: {input_path}")
        
        # Check existing progress
        if resume:
            existing_jobs = await scraper.load_existing_progress()
            if existing_jobs:
                logger.info(f"=� Found {len(existing_jobs)} previously scraped jobs")
            else:
                logger.info("9 No existing progress found, starting fresh")
                resume = False
        
        # Run scraping
        logger.info("=w Starting job detail extraction...")
        logger.info("=� Extracting 11 required fields per assignment:")
        logger.info("   " Profession, Salary, Company, Location, Start Date")
        logger.info("   " Telephone, Email, Job Description, Ref-Nr")
        logger.info("   " External Link, Application Link")
        
        await scraper.run(
            input_csv_path=str(input_path),
            resume=resume,
            auto_solve_captcha=auto_solve_captcha
        )
        
        # Results summary
        logger.info(" Phase 2 completed successfully!")
        logger.info(f"=� Jobs successfully scraped: {scraper.scraped_count}")
        logger.info(f"L Jobs failed: {scraper.failed_count}")
        
        # Output files
        output_dir = Path(PATHS['output_dir'])
        logger.info("[SUCCESS] Output files generated:")
        
        output_files = [
            "scraped_jobs.csv",
            "scraped_jobs.json", 
            "missing_emails.json"
        ]
        
        for filename in output_files:
            file_path = output_dir / filename
            if file_path.exists():
                file_size = file_path.stat().st_size / 1024  # KB
                logger.info(f"   " {filename} ({file_size:.1f} KB)")
        
        logger.info("=" * 50)
        return True
        
    except KeyboardInterrupt:
        logger.info("� Phase 2 interrupted by user")
        return False
    except Exception as e:
        logger.error(f"L Error in Phase 2: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)