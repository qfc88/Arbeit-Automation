import os
import pandas as pd
import time
import json
import sys
from pathlib import Path
from playwright.async_api import async_playwright

# Add config path and import centralized settings
sys.path.append(str(Path(__file__).parent.parent / "config"))

try:
    from settings import PATHS, SCRAPER_SETTINGS
except ImportError as e:
    raise ImportError(
        f"[ERROR] Settings import failed: {e}\n"
        "Please ensure src/config/settings.py exists and contains required settings."
    )


class JobURLScraper:
    def __init__(self, url):
        self.url = url
        # Use centralized paths from settings
        self.input_dir = PATHS['input_dir']
        self.temp_dir = PATHS['temp_dir']
        
        # Ensure directories exist
        os.makedirs(self.input_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # File paths
        self.base_dir = self.input_dir  # For compatibility with existing code
        self.progress_file = os.path.join(self.temp_dir, 'scraping_progress.json')
        self.temp_urls_file = os.path.join(self.temp_dir, 'temp_job_urls.csv')
        
    def save_progress(self, page_count, total_urls):
        """Save current scraping progress to file"""
        progress_data = {
            'last_page': page_count,
            'total_urls_found': total_urls,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'url': self.url
        }
        
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, indent=2, ensure_ascii=False)
            print(f"Progress saved: Page {page_count}, {total_urls} URLs")
        except Exception as e:
            print(f"Failed to save progress: {e}")
    
    def load_progress(self):
        """Load previous scraping progress"""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    progress_data = json.load(f)
                print(f"Found previous progress: Page {progress_data['last_page']}, {progress_data['total_urls_found']} URLs")
                return progress_data
            except Exception as e:
                print(f"Failed to load progress: {e}")
        return None
    
    def save_temp_urls(self, job_urls):
        """Save current URLs to temporary file"""
        try:
            df = pd.DataFrame({
                'job_url': list(job_urls),
                'ref_nr': [url.split('/')[-1] for url in job_urls]
            })
            df.to_csv(self.temp_urls_file, index=False, encoding='utf-8-sig')
            print(f"Temp URLs saved: {len(job_urls)} URLs")
        except Exception as e:
            print(f"Failed to save temp URLs: {e}")
    
    def load_temp_urls(self):
        """Load URLs from temporary file"""
        if os.path.exists(self.temp_urls_file):
            try:
                df = pd.read_csv(self.temp_urls_file, encoding='utf-8-sig')
                urls = set(df['job_url'].tolist())
                print(f"Loaded {len(urls)} URLs from temp file")
                return urls
            except Exception as e:
                print(f"Failed to load temp URLs: {e}")
        return set()
    
    def cleanup_temp_files(self):
        """Clean up temporary files after successful completion"""
        try:
            if os.path.exists(self.progress_file):
                os.remove(self.progress_file)
            if os.path.exists(self.temp_urls_file):
                os.remove(self.temp_urls_file)
            print("Temporary files cleaned up")
        except Exception as e:
            print(f"Failed to cleanup temp files: {e}")

    async def handle_connection_error_modal(self, page):
        """Handle 'Keine Verbindung' (No Connection) error modal with infinite retry until connection is stable"""
        retry_count = 0
        
        while True:  # Infinite loop until connection is resolved
            try:
                # Check for connection error modal
                error_modal = page.locator('#modal[aria-label="Modaldialog"]')
                modal_title = page.locator('#modal-title:has-text("Keine Verbindung")')
                
                # Wait briefly to see if modal appears
                if await error_modal.is_visible(timeout=3000) and await modal_title.is_visible():
                    retry_count += 1
                    print(f"Connection error modal detected (attempt {retry_count})...")
                    
                    # Always try "Erneut versuchen" (Try again) button
                    retry_btn = page.locator('#modal-ok:has-text("Erneut versuchen")')
                    if await retry_btn.is_visible():
                        print("Clicking 'Erneut versuchen'")
                        await retry_btn.click()
                        
                        # Wait for modal to disappear
                        try:
                            await page.wait_for_selector('#modal', state="hidden", timeout=10000)
                            print("Modal disappeared, waiting for network idle...")
                            
                            # Wait for network idle - this is crucial for connection stability
                            await page.wait_for_load_state("networkidle", timeout=30000)
                            
                            # Additional wait for page to fully stabilize
                            time.sleep(3)
                            
                            # Check if page is now accessible by looking for job results or main content
                            if await page.locator(".ergebnisliste-item").count() > 0 or await page.locator("#app").is_visible():
                                print(f"Page loaded successfully after {retry_count} retries")
                                return True
                            else:
                                print("Page still not loading properly, retrying...")
                                # Continue the loop to retry again
                                
                        except Exception as wait_error:
                            print(f"Timeout waiting for page to load: {wait_error}")
                            print("Will retry again...")
                            # Continue the loop to retry again
                    
                    else:
                        print("Retry button not found, waiting and checking again...")
                    
                    # Wait before next retry attempt
                    print("Waiting 5 seconds before next retry...")
                    time.sleep(5)
                    
                else:
                    # No modal visible, connection is stable
                    if retry_count > 0:
                        print(f"Connection stabilized after {retry_count} retries")
                    return True
                    
            except Exception as e:
                retry_count += 1
                print(f"Error in connection modal handling (attempt {retry_count}): {e}")
                print("Waiting 5 seconds before retry...")
                time.sleep(5)
                # Continue infinite loop
        
        # This return will never be reached due to infinite loop
        # return False
    
    async def handle_cookie_modal(self, page):
        """Handle cookie consent modal if it appears"""
        try:
            # Wait for cookie modal to appear (max 5 seconds)
            cookie_modal = page.locator("#bahf-cookie-disclaimer-modal")
            
            if await cookie_modal.is_visible(timeout=5000):
                print("Cookie modal detected, handling...")
                
                # Click "Alle Cookies ablehnen" (Reject all cookies)
                reject_btn = page.locator('[data-testid="bahf-cookie-disclaimer-btn-ablehnen"]')
                
                if await reject_btn.is_visible():
                    await reject_btn.click()
                    print("Clicked 'Alle Cookies ablehnen'")
                    
                    # Wait for modal to disappear
                    await page.wait_for_selector("#bahf-cookie-disclaimer-modal", state="hidden", timeout=5000)
                    
                    # Wait for network idle after cookie selection
                    await page.wait_for_load_state("networkidle")
                    print("Cookie modal closed and page settled")
                else:
                    print("Reject button not found, trying alternative...")
                    # Alternative: click outside modal or use other buttons
                    close_btn = page.locator('[data-testid="bahf-cookie-disclaimer-btn-schliessen"]')
                    if await close_btn.is_visible():
                        await close_btn.click()
                        # Wait for network idle after closing
                        await page.wait_for_load_state("networkidle")
                        print("Cookie modal closed via close button")
                        
        except Exception as e:
            print(f"Cookie modal handling failed: {e}")
            # Continue anyway, maybe modal didn't appear

    async def handle_modals(self, page):
        """Handle cookie consent modal and connection error modal if they appear"""
        # Handle connection error modal first with infinite retry logic
        await self.handle_connection_error_modal(page)
        
        # After connection is stable, handle cookie modal
        await self.handle_cookie_modal(page)

    async def check_and_handle_connection_during_scraping(self, page):
        """Check for connection error modal during scraping and handle it"""
        if await page.locator('#modal[aria-label="Modaldialog"]').is_visible():
            modal_title = page.locator('#modal-title:has-text("Keine Verbindung")')
            if await modal_title.is_visible():
                print("Connection modal detected during scraping, handling...")
                await self.handle_connection_error_modal(page)
                return True
        return False

    async def scrape_all_job_urls(self):
        """Scrape all job URLs from arbeitsagentur.de using pagination with recovery"""
        start_time = time.time()
        
        # Check for previous progress
        progress = self.load_progress()
        existing_urls = self.load_temp_urls()
        
        if progress and existing_urls:
            response = input(f"Found previous session: Page {progress['last_page']}, {len(existing_urls)} URLs. Continue? (y/n): ")
            if response.lower() != 'y':
                existing_urls = set()
                progress = None
        
        start_page = progress['last_page'] if progress else 1
        all_job_urls = existing_urls if existing_urls else set()
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=SCRAPER_SETTINGS.get('headless', True))
                page = await browser.new_page()
                
                print(f"Navigating to: {self.url}")
                await page.goto(self.url)
                
                # Wait for initial page load
                await page.wait_for_load_state("networkidle")
                
                # Handle modals if they appear (including infinite retry for connection errors)
                await self.handle_modals(page)
                
                page_count = start_page
                
                # If resuming, navigate to the correct page
                if start_page > 1:
                    print(f"Resuming from page {start_page}...")
                    for _ in range(start_page - 1):
                        load_more_btn = page.locator("#ergebnisliste-ladeweitere-button")
                        if await load_more_btn.is_visible():
                            await load_more_btn.click()
                            await page.wait_for_load_state("networkidle")
                            time.sleep(0.5)
                        else:
                            print("Could not resume to previous page, starting fresh")
                            page_count = 1
                            break
                
                while True:
                    print(f"Scraping page {page_count}...")
                    
                    # Check for connection error before processing each page
                    await self.check_and_handle_connection_during_scraping(page)
                    
                    # Get current job count before processing
                    current_job_count = len(all_job_urls)
                    
                    try:
                        # Extract URLs using JavaScript for better performance
                        new_urls = await page.evaluate("""
                            () => {
                                const links = Array.from(document.querySelectorAll('a.ergebnisliste-item'));
                                return links.map(link => link.href);
                            }
                        """)
                        
                    except Exception as eval_error:
                        print(f"Error extracting URLs: {eval_error}")
                        # Check if it's a connection issue and handle it
                        if self.check_and_handle_connection_during_scraping(page):
                            print("Connection issue resolved, retrying URL extraction...")
                            continue
                        else:
                            print("Non-connection error, skipping this page...")
                            time.sleep(5)
                            continue
                    
                    # Add new URLs to set
                    for url in new_urls:
                        all_job_urls.add(url)
                    
                    new_jobs_found = len(all_job_urls) - current_job_count
                    print(f"Page {page_count}: Found {len(new_urls)} jobs on page, {new_jobs_found} new unique jobs")
                    print(f"Total unique jobs: {len(all_job_urls)}")
                    
                    # Save progress every page
                    self.save_progress(page_count, len(all_job_urls))
                    self.save_temp_urls(all_job_urls)
                    
                    # Check for "Weitere Ergebnisse" button
                    load_more_btn = page.locator("#ergebnisliste-ladeweitere-button")
                    
                    if await load_more_btn.is_visible():
                        print("Clicking 'Weitere Ergebnisse'...")
                        
                        try:
                            await load_more_btn.click()
                            
                            # Wait for network idle
                            await page.wait_for_load_state("networkidle", timeout=30000)
                            
                            # Check for connection issues after clicking
                            await self.check_and_handle_connection_during_scraping(page)
                            
                            # Small buffer for rendering
                            time.sleep(1)
                            page_count += 1
                            
                        except Exception as click_error:
                            print(f"Error clicking load more button: {click_error}")
                            # Check if it's a connection issue
                            if await self.check_and_handle_connection_during_scraping(page):
                                print("Connection issue resolved, retrying click...")
                                continue
                            else:
                                print("Non-connection error, stopping scrape")
                                break
                            
                    else:
                        print("No more 'Weitere Ergebnisse' button - scraping complete!")
                        break
                
                await browser.close()
                
                processing_time = time.time() - start_time
                print(f"\n=== SCRAPING COMPLETE ===")
                print(f"Total pages scraped: {page_count}")
                print(f"Total unique job URLs: {len(all_job_urls)}")
                print(f"Processing time: {processing_time:.2f} seconds")
                
                # Clean up temp files on successful completion
                self.cleanup_temp_files()
                
                return list(all_job_urls)
                
        except Exception as e:
            print(f"\n=== SCRAPING INTERRUPTED ===")
            print(f"Error: {e}")
            print(f"Progress saved: Page {page_count}, {len(all_job_urls)} URLs")
            print("You can resume later by running the script again")
            
            # Save final state before exit
            self.save_progress(page_count, len(all_job_urls))
            self.save_temp_urls(all_job_urls)
            
            return list(all_job_urls)
    
    def save_job_urls_to_csv(self, job_urls):
        """Save job URLs to CSV for later processing"""
        print(f"DEBUG: Attempting to save {len(job_urls)} URLs")
        
        if len(job_urls) == 0:
            print("WARNING: No job URLs to save!")
            return pd.DataFrame()
        
        df = pd.DataFrame({
            'job_url': job_urls,
            'ref_nr': [url.split('/')[-1] for url in job_urls]
        })
        
        # Save to file directory with UTF-8-SIG encoding
        csv_path = PATHS['input_csv']
        print(f"DEBUG: Saving to path: {csv_path}")
        
        try:
            # Save with UTF-8-SIG encoding (better for Excel compatibility)
            df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            print(f"SUCCESS: Saved {len(job_urls)} job URLs to '{csv_path}'")
            
            # Verify file was created and has content
            if os.path.exists(csv_path):
                file_size = os.path.getsize(csv_path)
                print(f"File verification: {csv_path} exists, size: {file_size} bytes")
            else:
                print(f"ERROR: File was not created at {csv_path}")
                
        except Exception as e:
            print(f"ERROR saving CSV: {e}")
            
        return df
    
    def load_job_urls_from_csv(self):
        """Load previously scraped job URLs from CSV"""
        csv_path = PATHS['input_csv']
        
        if os.path.exists(csv_path):
            try:
                df = pd.read_csv(csv_path, encoding='utf-8-sig')
                print(f"Loaded {len(df)} job URLs from '{csv_path}'")
                return df
            except Exception as e:
                print(f"Error loading CSV: {e}")
                return None
        else:
            print(f"No existing CSV found at '{csv_path}'")
            return None
    
    async def incremental_scrape(self):
        """Re-scrape to find new jobs and update existing data"""
        print("Starting incremental scrape to find new jobs...")
        
        # Load existing URLs
        existing_df = self.load_job_urls_from_csv()
        existing_urls = set()
        
        if existing_df is not None:
            existing_urls = set(existing_df['job_url'].tolist())
            print(f"Found {len(existing_urls)} existing job URLs")
        else:
            print("No existing data found, performing full scrape...")
            return await self.run_scraping()
        
        # Scrape current jobs
        current_urls = await self.scrape_all_job_urls()
        current_urls_set = set(current_urls)
        
        # Find new jobs
        new_jobs = current_urls_set - existing_urls
        removed_jobs = existing_urls - current_urls_set
        
        print(f"\n=== INCREMENTAL SCRAPE RESULTS ===")
        print(f"Existing jobs: {len(existing_urls)}")
        print(f"Current jobs found: {len(current_urls_set)}")
        print(f"New jobs: {len(new_jobs)}")
        print(f"Removed/expired jobs: {len(removed_jobs)}")
        
        if new_jobs:
            print("\nNew job URLs found:")
            for i, url in enumerate(list(new_jobs)[:5], 1):
                ref_nr = url.split('/')[-1]
                print(f"  {i}. {ref_nr}")
            if len(new_jobs) > 5:
                print(f"  ... and {len(new_jobs) - 5} more")
        
        if removed_jobs:
            print(f"\nRemoved jobs: {len(removed_jobs)} jobs are no longer available")
        
        # Update CSV with current data
        df = self.save_job_urls_to_csv(current_urls)
        
        # Save update report
        self.save_update_report(existing_urls, current_urls_set, new_jobs, removed_jobs)
        
        return df
    
    def save_update_report(self, existing_urls, current_urls, new_jobs, removed_jobs):
        """Save detailed update report"""
        report_path = os.path.join(self.base_dir, 'update_report.json')
        
        report_data = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'existing_count': len(existing_urls),
            'current_count': len(current_urls),
            'new_jobs_count': len(new_jobs),
            'removed_jobs_count': len(removed_jobs),
            'new_jobs': list(new_jobs)[:50],  # Save first 50 new jobs
            'removed_jobs': list(removed_jobs)[:50],  # Save first 50 removed jobs
            'url': self.url
        }
        
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            print(f"Update report saved to: {report_path}")
        except Exception as e:
            print(f"Failed to save update report: {e}")
    
    async def run_scraping(self):
        """Main method to run the scraping process"""
        print("Starting job URL scraping...")
        
        # Check if we already have scraped URLs
        existing_df = self.load_job_urls_from_csv()
        
        if existing_df is not None:
            print(f"Found existing {len(existing_df)} job URLs.")
            print("Options:")
            print("1. Skip scraping (use existing data)")
            print("2. Full re-scrape (replace all data)")
            print("3. Incremental scrape (add new jobs only)")
            
            choice = input("Choose option (1/2/3): ").strip()
            
            if choice == '1':
                return existing_df
            elif choice == '3':
                return await self.incremental_scrape()
            # choice == '2' or any other input will continue to full scrape
        
        # Full scrape all job URLs
        job_urls = await self.scrape_all_job_urls()
        
        # Save to CSV
        df = self.save_job_urls_to_csv(job_urls)
        
        return df


# Example usage
if __name__ == "__main__":
    # URL from the assignment
    url = "https://www.arbeitsagentur.de/jobsuche/suche?angebotsart=4&ausbildungsart=0&arbeitszeit=vz&branche=22;1;2;9;3;5;7;10;11;16;12;21;26;15;17;19;20;8;23;29&veroeffentlichtseit=7&sort=veroeffdatum"
    
    # Initialize scraper
    scraper = JobURLScraper(url)
    
    # Run scraping process
    df = scraper.run_scraping()
    
    # Display results
    print("\n=== RESULTS ===")
    print(f"Total jobs: {len(df)}")
    print("\nFirst 5 URLs:")
    print(df.head())
    
    print(f"\nFiles saved in: {scraper.base_dir}/")