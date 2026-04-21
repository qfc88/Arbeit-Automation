#!/usr/bin/env python3
"""
Scheduled Job Scraper for Vietnam Timezone
Runs the scraper at 2 AM Vietnam time when job websites open back up
"""

import os
import sys
import time
import schedule
import subprocess
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path(__file__).parent.parent / 'data' / 'logs' / 'scheduler.log')
    ]
)
logger = logging.getLogger(__name__)

# Vietnam timezone (UTC+7)
VIETNAM_TZ = timezone(timedelta(hours=7))

class JobScraperScheduler:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.docker_compose_file = self.project_root / "docker-compose.yml"
        
    def get_vietnam_time(self):
        """Get current time in Vietnam timezone"""
        return datetime.now(VIETNAM_TZ)
    
    def run_scraper_job(self):
        """Execute the job scraping pipeline"""
        vietnam_time = self.get_vietnam_time()
        logger.info(f"🚀 Starting scheduled job scrape at {vietnam_time.strftime('%Y-%m-%d %H:%M:%S')} (Vietnam time)")
        
        try:
            # Change to project directory
            os.chdir(self.project_root)
            
            # Stop any existing containers
            logger.info("🛑 Stopping existing containers...")
            subprocess.run(["docker-compose", "down"], check=False, capture_output=True)
            
            # Start fresh containers with new database
            logger.info("🐳 Starting fresh Docker containers...")
            result = subprocess.run(
                ["docker-compose", "up", "-d"], 
                check=True, 
                capture_output=True, 
                text=True
            )
            logger.info("✅ Docker containers started successfully")
            
            # Wait a bit for containers to fully start
            time.sleep(30)
            
            # Run the automated pipeline
            logger.info("🔄 Executing automated scraping pipeline...")
            result = subprocess.run(
                ["docker-compose", "exec", "-T", "job-scraper", "python", "scripts/run_automated_pipeline.py"],
                check=True,
                capture_output=True,
                text=True,
                timeout=7200  # 2 hours timeout
            )
            
            logger.info("🎉 Scraping pipeline completed successfully!")
            logger.info(f"Pipeline output: {result.stdout}")
            
        except subprocess.TimeoutExpired:
            logger.error("⏰ Scraping pipeline timed out after 2 hours")
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Pipeline execution failed: {e}")
            logger.error(f"Error output: {e.stderr}")
        except Exception as e:
            logger.error(f"💥 Unexpected error during scraping: {e}")
        
        finally:
            # Log completion
            vietnam_time_end = self.get_vietnam_time()
            logger.info(f"📊 Scraping session ended at {vietnam_time_end.strftime('%Y-%m-%d %H:%M:%S')} (Vietnam time)")
    
    def start_scheduler(self):
        """Start the scheduling system"""
        logger.info("🕐 Job Scraper Scheduler started")
        logger.info("⏰ Scheduled to run daily at 2:00 AM Vietnam time (UTC+7)")
        
        # Schedule for 2 AM Vietnam time
        schedule.every().day.at("02:00").do(self.run_scraper_job)
        
        # Also allow immediate test run if script is called with 'test' argument
        if len(sys.argv) > 1 and sys.argv[1] == 'test':
            logger.info("🧪 Running test scrape immediately...")
            self.run_scraper_job()
            return
        
        # Main scheduling loop
        while True:
            try:
                schedule.run_pending()
                current_time = self.get_vietnam_time()
                
                # Log status every hour
                if current_time.minute == 0:
                    next_run = schedule.next_run()
                    if next_run:
                        logger.info(f"⏳ Next scheduled run: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
                
                time.sleep(60)  # Check every minute
                
            except KeyboardInterrupt:
                logger.info("🛑 Scheduler stopped by user")
                break
            except Exception as e:
                logger.error(f"💥 Scheduler error: {e}")
                time.sleep(300)  # Wait 5 minutes before retrying

def main():
    """Main function"""
    scheduler = JobScraperScheduler()
    
    # Ensure required directories exist
    logs_dir = Path(__file__).parent.parent / 'data' / 'logs'
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        scheduler.start_scheduler()
    except Exception as e:
        logger.error(f"💥 Failed to start scheduler: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()