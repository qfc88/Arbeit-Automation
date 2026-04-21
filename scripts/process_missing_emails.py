#!/usr/bin/env python3
"""
Phase 3: Contact Enhancement Script
Standalone script for deep contact mining from company websites
Handles the "Missing Emails & Websites" bonus task
"""

import asyncio
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright

# Add config path and import centralized settings
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root / "src" / "config"))

try:
    from settings import BROWSER_SETTINGS, CONTACT_SCRAPER_SETTINGS, PATHS
except ImportError as e:
    raise ImportError(
        f"[ERROR] Settings import failed: {e}\n"
        "Please ensure src/config/settings.py exists and contains required settings."
    )

# Add src to Python path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from scrapers.contact_scraper import ContactScraper

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def load_missing_jobs() -> list:
    """Load jobs with missing contact information"""
    missing_path = Path("data/output/missing_emails.json")
    
    if not missing_path.exists():
        logger.warning("� missing_emails.json not found")
        logger.info("=� This could mean:")
        logger.info("   " All jobs have complete contact info")
        logger.info("   " Phase 2 hasn't been completed yet")
        logger.info("   " Jobs were processed but no missing contacts were found")
        return []
    
    try:
        with open(missing_path, 'r', encoding='utf-8') as f:
            missing_jobs = json.load(f)
        
        logger.info(f"=� Loaded {len(missing_jobs)} jobs with missing contacts")
        return missing_jobs
        
    except Exception as e:
        logger.error(f"L Error loading missing_emails.json: {e}")
        return []

async def analyze_missing_contacts(jobs: list) -> dict:
    """Analyze what types of contact info are missing"""
    analysis = {
        'total_jobs': len(jobs),
        'missing_email': 0,
        'missing_phone': 0,
        'missing_both': 0,
        'has_application_link': 0,
        'has_external_link': 0
    }
    
    for job in jobs:
        has_email = bool(job.get('email'))
        has_phone = bool(job.get('telephone'))
        
        if not has_email:
            analysis['missing_email'] += 1
        if not has_phone:
            analysis['missing_phone'] += 1
        if not has_email and not has_phone:
            analysis['missing_both'] += 1
        
        if job.get('application_link'):
            analysis['has_application_link'] += 1
        if job.get('external_link'):
            analysis['has_external_link'] += 1
    
    return analysis

async def process_contact_enhancement(missing_jobs: list, max_jobs: int = None) -> list:
    """Process jobs for contact enhancement using ContactScraper"""
    if not missing_jobs:
        logger.info(" No jobs need contact enhancement")
        return []
    
    # Limit processing if requested
    if max_jobs and len(missing_jobs) > max_jobs:
        logger.info(f"=" Limiting processing to first {max_jobs} jobs")
        jobs_to_process = missing_jobs[:max_jobs]
    else:
        jobs_to_process = missing_jobs
    
    logger.info(f"=u Starting deep contact mining for {len(jobs_to_process)} jobs...")
    logger.info("=� Will scrape company websites and contact pages")
    logger.info("=� Using German-specific patterns (/kontakt, /impressum, etc.)")
    logger.info("� This process is slower but more thorough (3-5s per job)")
    
    # Setup browser for ContactScraper
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(
        headless=BROWSER_SETTINGS.get('headless', False),
        args=BROWSER_SETTINGS.get('args', ['--disable-blink-features=AutomationControlled'])
    )
    context = await browser.new_context(
        user_agent=BROWSER_SETTINGS.get('user_agent'),
        viewport=BROWSER_SETTINGS.get('viewport', {'width': 1920, 'height': 1080})
    )
    
    # Initialize contact scraper with browser context
    contact_scraper = ContactScraper(context=context)
    
    try:
        # Use ContactScraper's process_missing_contacts method
        logger.info("= Processing missing contacts with ContactScraper...")
        enhanced_jobs = await contact_scraper.process_missing_contacts(jobs_to_process)
        
        await browser.close()
        return enhanced_jobs
        
    except Exception as e:
        logger.error(f"L Error during contact enhancement: {e}")
        await browser.close()
        return []

async def save_enhanced_results(enhanced_jobs: list, original_jobs: list):
    """Save enhanced contact results and generate report"""
    output_dir = Path("data/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save enhanced jobs
    enhanced_path = output_dir / "enhanced_contacts.json"
    with open(enhanced_path, 'w', encoding='utf-8') as f:
        json.dump(enhanced_jobs, f, ensure_ascii=False, indent=2)
    
    logger.info(f"=� Enhanced results saved to {enhanced_path}")
    
    # Calculate improvements
    original_missing_emails = len([job for job in original_jobs if not job.get('email')])
    original_missing_phones = len([job for job in original_jobs if not job.get('telephone')])
    
    # Count how many enhanced jobs now have contacts
    enhanced_with_emails = len([job for job in enhanced_jobs if job.get('email')])
    enhanced_with_phones = len([job for job in enhanced_jobs if job.get('telephone')])
    
    # Count original jobs that already had contacts
    original_with_emails = len(original_jobs) - original_missing_emails
    original_with_phones = len(original_jobs) - original_missing_phones
    
    # Calculate actual improvements (new contacts found)
    email_improvement = enhanced_with_emails - original_with_emails
    phone_improvement = enhanced_with_phones - original_with_phones
    
    # Generate comprehensive report
    report = {
        'timestamp': datetime.now().isoformat(),
        'processing_summary': {
            'jobs_processed': len(enhanced_jobs),
            'original_jobs': len(original_jobs),
            'original_missing_emails': original_missing_emails,
            'original_missing_phones': original_missing_phones,
            'emails_found': max(0, email_improvement),
            'phones_found': max(0, phone_improvement),
            'email_success_rate': f"{(max(0, email_improvement)/original_missing_emails)*100:.1f}%" if original_missing_emails > 0 else "N/A",
            'phone_success_rate': f"{(max(0, phone_improvement)/original_missing_phones)*100:.1f}%" if original_missing_phones > 0 else "N/A"
        },
        'detailed_results': {
            'jobs_with_new_emails': [job for job in enhanced_jobs if job.get('email') and not any(orig.get('ref_nr') == job.get('ref_nr') and orig.get('email') for orig in original_jobs)],
            'jobs_with_new_phones': [job for job in enhanced_jobs if job.get('telephone') and not any(orig.get('ref_nr') == job.get('ref_nr') and orig.get('telephone') for orig in original_jobs)],
            'jobs_still_missing_contacts': [job for job in enhanced_jobs if not job.get('email') and not job.get('telephone')]
        }
    }
    
    report_path = output_dir / "contact_enhancement_report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    logger.info(f"=� Enhancement report saved to {report_path}")
    return report

async def merge_enhanced_with_original():
    """Merge enhanced contacts back into the main scraped_jobs.csv"""
    try:
        # Load original scraped jobs
        import pandas as pd
        original_path = Path("data/output/scraped_jobs.csv")
        enhanced_path = Path("data/output/enhanced_contacts.json")
        
        if not original_path.exists() or not enhanced_path.exists():
            logger.warning("� Cannot merge - missing original or enhanced files")
            return
        
        # Load data
        df_original = pd.read_csv(original_path)
        with open(enhanced_path, 'r', encoding='utf-8') as f:
            enhanced_jobs = json.load(f)
        
        # Create enhanced DataFrame
        df_enhanced = pd.DataFrame(enhanced_jobs)
        
        # Merge based on ref_nr
        if 'ref_nr' in df_original.columns and 'ref_nr' in df_enhanced.columns:
            # Update original with enhanced data
            for idx, enhanced_job in df_enhanced.iterrows():
                ref_nr = enhanced_job['ref_nr']
                original_idx = df_original[df_original['ref_nr'] == ref_nr].index
                
                if not original_idx.empty:
                    # Update with enhanced contact info
                    for col in ['email', 'telephone', 'contact_person']:
                        if pd.notna(enhanced_job.get(col)) and enhanced_job.get(col):
                            df_original.loc[original_idx[0], col] = enhanced_job[col]
            
            # Save merged results
            merged_path = Path("data/output/scraped_jobs_enhanced.csv")
            df_original.to_csv(merged_path, index=False, encoding='utf-8')
            logger.info(f"= Merged results saved to {merged_path}")
        else:
            logger.warning("� Cannot merge - ref_nr column missing")
            
    except Exception as e:
        logger.error(f"L Error merging enhanced results: {e}")

async def main():
    """Main function for Phase 3: Contact Enhancement"""
    logger.info("=� PHASE 3: CONTACT ENHANCEMENT")
    logger.info("=" * 50)
    logger.info("<� Bonus Task: Handle Missing Emails & Websites")
    logger.info("=' Using ContactScraper with German-specific patterns")
    
    try:
        # Load missing jobs
        missing_jobs = await load_missing_jobs()
        
        if not missing_jobs:
            logger.info(" Phase 3 completed - no enhancement needed")
            return True
        
        # Analyze what's missing
        analysis = await analyze_missing_contacts(missing_jobs)
        
        logger.info("=� Missing Contact Analysis:")
        logger.info(f"   " Total jobs with missing contacts: {analysis['total_jobs']}")
        logger.info(f"   " Missing email: {analysis['missing_email']}")
        logger.info(f"   " Missing phone: {analysis['missing_phone']}")
        logger.info(f"   " Missing both: {analysis['missing_both']}")
        logger.info(f"   " Have application links: {analysis['has_application_link']}")
        logger.info(f"   " Have external links: {analysis['has_external_link']}")
        
        # Get user preferences
        if analysis['total_jobs'] > 50:
            limit_choice = input(f"Process all {analysis['total_jobs']} jobs? (y/n/number): ").strip()
            
            if limit_choice.lower() == 'n':
                logger.info("� Skipping contact enhancement")
                return True
            elif limit_choice.isdigit():
                max_jobs = int(limit_choice)
                logger.info(f"=" Will process first {max_jobs} jobs")
            else:
                max_jobs = None
        else:
            proceed = input(f"Process {analysis['total_jobs']} jobs for contact enhancement? (y/n): ").strip().lower()
            if proceed != 'y':
                logger.info("� Skipping contact enhancement")
                return True
            max_jobs = None
        
        # Process enhancement using ContactScraper
        enhanced_jobs = await process_contact_enhancement(missing_jobs, max_jobs)
        
        if enhanced_jobs:
            # Save results and generate report
            report = await save_enhanced_results(enhanced_jobs, missing_jobs)
            
            # Merge with original data
            await merge_enhanced_with_original()
            
            # Display results
            logger.info(" Phase 3 completed successfully!")
            logger.info("=� Contact Enhancement Results:")
            summary = report['processing_summary']
            logger.info(f"   " Jobs processed: {summary['jobs_processed']}")
            logger.info(f"   " Additional emails found: {summary['emails_found']}")
            logger.info(f"   " Additional phones found: {summary['phones_found']}")
            logger.info(f"   " Email success rate: {summary['email_success_rate']}")
            logger.info(f"   " Phone success rate: {summary['phone_success_rate']}")
            
            # Show some examples of successful enhancements
            detailed = report['detailed_results']
            if detailed['jobs_with_new_emails']:
                logger.info(f"=� Example jobs with new emails found:")
                for job in detailed['jobs_with_new_emails'][:3]:
                    logger.info(f"   " {job.get('company_name', 'Unknown')}: {job.get('email')}")
            
        else:
            logger.warning("� No enhanced results generated")
        
        logger.info("=" * 50)
        return True
        
    except KeyboardInterrupt:
        logger.info("� Phase 3 interrupted by user")
        return False
    except Exception as e:
        logger.error(f"L Error in Phase 3: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)