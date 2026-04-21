"""
Job scraper module for extracting job details from individual job pages
"""
# Add to existing imports
from .external_link_handler import ExternalLinkHandler
import asyncio
import pandas as pd
from pathlib import Path
from playwright.async_api import async_playwright, Page
import json
import logging
from typing import Dict, List, Optional
import re
from datetime import datetime
import time
import sys
import importlib.util

# Add config and utils to path
sys.path.append(str(Path(__file__).parent.parent / "config"))
sys.path.append(str(Path(__file__).parent.parent / "utils"))
sys.path.append(str(Path(__file__).parent.parent / "database"))

# Import settings - no fallback, fail fast if not configured
try:
    from settings import (SCRAPER_SETTINGS, BROWSER_SETTINGS, CAPTCHA_SETTINGS, 
                         VALIDATION_SETTINGS, FILE_MANAGEMENT_SETTINGS, PATHS)
except ImportError:
    try:
        from config.settings import (SCRAPER_SETTINGS, BROWSER_SETTINGS, CAPTCHA_SETTINGS,
                                   VALIDATION_SETTINGS, FILE_MANAGEMENT_SETTINGS, PATHS)
    except ImportError as e:
        raise ImportError(
            f"[ERROR] Settings import failed: {e}\n"
            "Please ensure src/config/settings.py exists and contains required settings."
        )

# Import CAPTCHA solver
try:
    from .captcha_solver import CaptchaSolver
    CAPTCHA_SOLVER_AVAILABLE = True
except ImportError:
    CAPTCHA_SOLVER_AVAILABLE = False
    logging.warning("CaptchaSolver not available. Install transformers and torch for auto-solving.")

# Import FileManager
try:
    # Try absolute import first
    sys.path.append(str(Path(__file__).parent.parent / "utils"))
    from file_manager import FileManager
    FILE_MANAGER_AVAILABLE = True
except ImportError:
    try:
        # Try relative import
        from utils.file_manager import FileManager
        FILE_MANAGER_AVAILABLE = True
    except ImportError:
        try:
            # Try direct path import
            import importlib.util
            spec = importlib.util.spec_from_file_location("file_manager", 
                  str(Path(__file__).parent.parent / "utils" / "file_manager.py"))
            file_manager_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(file_manager_module)
            FileManager = file_manager_module.FileManager
            FILE_MANAGER_AVAILABLE = True
        except ImportError:
            FILE_MANAGER_AVAILABLE = False
            logging.warning("FileManager not available, using legacy file handling")

# Import JobModel for validation
try:
    from models.job_model import JobModel
    JOB_MODEL_AVAILABLE = True
except ImportError:
    try:
        from job_model import JobModel
        JOB_MODEL_AVAILABLE = True
    except ImportError:
        try:
            from database.job_model import JobModel
            JOB_MODEL_AVAILABLE = True
        except ImportError:
            JOB_MODEL_AVAILABLE = False
            logging.warning("JobModel not available, skipping data validation")

# Setup logging
logging.basicConfig(level=logging.INFO)
# Import logger after path is set
try:
    from logger import get_scraper_logger, log_error
    logger = get_scraper_logger('scrapers.job_scraper')
except ImportError:
    logger = logging.getLogger(__name__)

class JobScraper:
    def __init__(self, auto_solve_captcha: bool = True, use_sessions: bool = None, validate_data: bool = None):
        """Initialize the job scraper with enhanced configuration"""
        self.browser = None
        self.context = None
        self.scraped_count = 0
        self.failed_count = 0
        self.auto_solve_captcha = auto_solve_captcha
        
        # Enhanced settings from config
        self.batch_size = SCRAPER_SETTINGS.get('batch_size', 10)
        self.delay_between_jobs = SCRAPER_SETTINGS.get('delay_between_jobs', 1)
        self.max_jobs_per_session = SCRAPER_SETTINGS.get('max_jobs_per_session', 1000)
        self.enable_resume = SCRAPER_SETTINGS.get('enable_resume', True)
        
        # Post-CAPTCHA stabilization settings (simplified)
        self.enable_page_stabilization = SCRAPER_SETTINGS.get('enable_page_stabilization', True)
        self.stabilization_timeout = SCRAPER_SETTINGS.get('stabilization_timeout', 30)
        
        # Session and validation settings
        self.use_sessions = use_sessions if use_sessions is not None else FILE_MANAGEMENT_SETTINGS.get('use_sessions', False)
        self.validate_data = validate_data if validate_data is not None else VALIDATION_SETTINGS.get('validate_on_scrape', False)
        
        # Generate session ID for file management
        if self.use_sessions:
            self.session_id = f"scrape_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        else:
            self.session_id = None
        
        # Initialize FileManager if available
        self.file_manager = None
        if FILE_MANAGER_AVAILABLE and self.use_sessions:
            try:
                self.file_manager = FileManager()
                # Use coordinated session management - try to resume existing session
                if self.session_id:
                    self.session_id = self.file_manager.start_new_session(self.session_id, force_new=False)
                else:
                    self.session_id = self.file_manager.start_new_session()
                logger.info("[SUCCESS] FileManager initialized with session support")
                logger.info(f"Active Session ID: {self.session_id}")
            except Exception as e:
                logger.warning(f"[ERROR] Failed to initialize FileManager: {e}")
                self.use_sessions = False
        
        # Initialize statistics tracking
        self.stats = {
            'total_processed': 0,
            'successful_scrapes': 0,
            'errors': 0,
            'captcha_encounters': 0,
            'captcha_solved': 0,
            'validation_failures': 0,
            'session_start_time': datetime.now(),
            'jobs_per_minute': 0.0,
            # Stabilization statistics (simplified)
            'stabilization_attempts': 0,
            'stabilization_refresh_success': 0,
            'stabilization_failures': 0
        }
        
        # Initialize CAPTCHA solver if available and requested
        self.captcha_solver = None
        if auto_solve_captcha and CAPTCHA_SOLVER_AVAILABLE:
            try:
                self.captcha_solver = CaptchaSolver()
                logger.info("[SUCCESS] CAPTCHA auto-solver initialized")
            except Exception as e:
                logger.warning(f"[ERROR] Failed to initialize CAPTCHA solver: {e}")
                logger.info("[INFO] Falling back to manual CAPTCHA solving")
                self.auto_solve_captcha = False
        elif auto_solve_captcha and not CAPTCHA_SOLVER_AVAILABLE:
            logger.warning("[ERROR] CAPTCHA auto-solver requested but not available")
            logger.info("[INFO] Install requirements: pip install transformers torch torchvision")
            logger.info("[INFO] Falling back to manual CAPTCHA solving")
            self.auto_solve_captcha = False
        
        # Log initialization summary
        logger.info(f"JobScraper initialized:")
        logger.info(f"  - Sessions: {self.use_sessions} (ID: {self.session_id})")
        logger.info(f"  - Data validation: {self.validate_data}")
        logger.info(f"  - CAPTCHA auto-solve: {self.auto_solve_captcha}")
        logger.info(f"  - Batch size: {self.batch_size}")
        logger.info(f"  - Max jobs per session: {self.max_jobs_per_session}")
        
        # CSS Selectors based on analyzed HTML
        self.selectors = {
            # Basic job info (available before CAPTCHA)
            'title': '#detail-kopfbereich-titel',
            'company': '#detail-kopfbereich-firma',
            'location': '#detail-kopfbereich-arbeitsort',
            'start_date': '.eintrittsdatum-tag',
            'job_description': '#detail-beschreibung-beschreibung',
            'job_type': '#detail-kopfbereich-anstellungsart',
            'ausbildungsberuf': '#detail-kopfbereich-ausbildungsberuf',
            
            # CAPTCHA elements
            'captcha_container': '#jobdetails-kontaktdaten-block',
            'captcha_image': '#kontaktdaten-captcha-image',
            'captcha_input': '#kontaktdaten-captcha-input',
            'captcha_submit': '#kontaktdaten-captcha-absenden-button',
            'captcha_reload': '#kontaktdaten-captcha-reload-button',
            
            # Post-CAPTCHA contact info (Scenario 1: Full contact available)
            'contact_phone': '#detail-bewerbung-telefon-Telefon',
            'contact_email': '#detail-bewerbung-mail',
            'contact_address': '#detail-bewerbung-adresse',
            'application_method': '.bewerbungsarten li',
            
            # Post-CAPTCHA links (Scenario 2: Need application link scraping)
            'application_link': '#detail-bewerbung-url',
            'external_link': '#detail-bewerbung-agkontaktieren',
            'ref_nr': '#detail-bewerbung-chiffre',
            'ref_nr_footer': '#detail-footer-referenznummer',
            'company_contact': '#detail-bewerbung-adresse'
        }
        
        # Contact extraction patterns
        self.contact_patterns = {
            'phone': [
                r'\+49[\s\-\(\)]?\d+[\s\-\(\)\d]+',
                r'0\d{2,5}[\s\-]\d+[\s\-\d]+',
                r'Tel\.?[\s:]?\+?[\d\s\-\(\)]+',
                r'Telefon[\s:]?\+?[\d\s\-\(\)]+',
                r'Fon[\s:]?\+?[\d\s\-\(\)]+'
            ],
            'email': [
                r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
                r'E-?Mail[\s:]+([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                r'Kontakt[\s:]+([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
            ]
        }
    
    async def load_job_urls(self, csv_path: str) -> List[Dict]:
        """Load job URLs from CSV file"""
        try:
            df = pd.read_csv(csv_path)
            logger.info(f"Loaded {len(df)} job URLs from {csv_path}")
            return df.to_dict('records')
        except Exception as e:
            logger.error(f"Error loading job URLs: {e}")
            return []
    
    async def setup_browser(self):
        """Setup Playwright browser with enhanced configuration"""
        playwright = await async_playwright().start()
        
        # Use settings for browser configuration
        self.browser = await playwright.chromium.launch(
            headless=SCRAPER_SETTINGS.get('headless', False),
            args=BROWSER_SETTINGS.get('args', ['--disable-blink-features=AutomationControlled'])
        )
        
        # Create context with enhanced settings
        context_settings = {
            'user_agent': BROWSER_SETTINGS.get('user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'),
            'viewport': BROWSER_SETTINGS.get('viewport', {'width': 1920, 'height': 1080}),
            'storage_state': None  # Will be saved after first CAPTCHA solve
        }
        
        # Add optional settings if available
        if 'timezone_id' in BROWSER_SETTINGS:
            context_settings['timezone_id'] = BROWSER_SETTINGS['timezone_id']
        if 'locale' in BROWSER_SETTINGS:
            context_settings['locale'] = BROWSER_SETTINGS['locale']
        
        self.context = await self.browser.new_context(**context_settings)
        
        # Initialize external link handler AFTER context is created
        self.external_handler = ExternalLinkHandler(self.context)
        logger.info("[SUCCESS] External link handler initialized with context")
        
        logger.info("[SUCCESS] Browser setup completed with enhanced configuration")
        logger.info(f"Headless: {SCRAPER_SETTINGS.get('headless', False)}, "
                   f"Viewport: {BROWSER_SETTINGS.get('viewport', {})}")
    
    async def handle_cookie_consent(self, page: Page):
        """Handle cookie consent dialogs that appear on job pages"""
        try:
            # Wait for potential cookie dialogs to appear
            await asyncio.sleep(1)
            
            # Common cookie consent selectors for German job sites
            cookie_selectors = [
                'button:has-text("Akzeptieren")',
                'button:has-text("Alle akzeptieren")',
                'button:has-text("Accept")',
                'button:has-text("OK")',
                '[data-testid="cookie-accept"]',
                '[id*="cookie"][id*="accept"]',
                '[class*="cookie"][class*="accept"]',
                '.cookie-accept',
                '.cookie-banner button',
                '#cookie-banner button',
                'button[aria-label*="Accept"]',
                'button[aria-label*="Akzeptieren"]'
            ]
            
            for selector in cookie_selectors:
                try:
                    # Check if cookie dialog exists
                    cookie_button = await page.query_selector(selector)
                    if cookie_button:
                        # Check if button is visible
                        is_visible = await cookie_button.is_visible()
                        if is_visible:
                            logger.info(f"[COOKIE] Found cookie consent dialog, clicking: {selector}")
                            await cookie_button.click()
                            await asyncio.sleep(1)  # Wait for dialog to close
                            break
                except Exception as e:
                    # Continue trying other selectors
                    continue
                    
        except Exception as e:
            logger.debug(f"Cookie consent handling error (non-critical): {e}")
    
    async def handle_captcha(self, page: Page) -> bool:
        """Handle captcha - auto-solve with OCR or manual solving"""
        try:
            # Wait a moment for page to load completely
            await asyncio.sleep(2)
            
            # Check if captcha is present
            captcha_image = await page.query_selector(self.selectors['captcha_image'])
            
            if captcha_image:
                logger.warning("[CAPTCHA] CAPTCHA detected!")
                
                # Try auto-solving first if available
                if self.auto_solve_captcha and self.captcha_solver:
                    logger.info("[AUTO] Attempting auto-solve with TrOCR")
                    
                    success = await self.captcha_solver.solve_captcha_from_page(
                        page,
                        self.selectors['captcha_image'],
                        self.selectors['captcha_input'],
                        self.selectors['captcha_submit']
                    )
                    
                    if success:
                        logger.info("CAPTCHA auto-solved successfully!")
                        return True
                    else:
                        logger.warning("Auto-solve failed, falling back to manual solving...")
                
                # Fallback to manual solving
                logger.info("Please solve CAPTCHA manually...")
                logger.info("Note: After solving once, other jobs should not require CAPTCHA")
                
                # Manual solving with better detection
                return await self._handle_manual_captcha(page)
            else:
                # No captcha present - check if contact info is already available
                phone_available = await page.query_selector(self.selectors['contact_phone'])
                email_available = await page.query_selector(self.selectors['contact_email'])
                contact_address_available = await page.query_selector(self.selectors['contact_address'])
                
                if phone_available or email_available or contact_address_available:
                    logger.debug("Contact info available (no CAPTCHA required)")
                    return True
                else:
                    logger.debug("Contact info not available yet")
                    return False
            
        except Exception as e:
            logger.error(f"Error handling CAPTCHA: {e}")
            return False
    
    async def _handle_manual_captcha(self, page: Page) -> bool:
        """Handle manual CAPTCHA solving with better detection"""
        try:
            logger.info("=== MANUAL CAPTCHA SOLVING ===")
            logger.info("Please solve the CAPTCHA manually in the browser")
            logger.info("The script will automatically detect when you're done")
            logger.info("Available indicators to watch for:")
            logger.info("  - Contact information appears")
            logger.info("  - Application links become visible")
            logger.info("  - CAPTCHA image disappears")
            
            # Multiple ways to detect CAPTCHA solved
            max_wait_time = 300  # 5 minutes max
            check_interval = 2   # Check every 2 seconds
            elapsed_time = 0
            
            while elapsed_time < max_wait_time:
                # Method 1: Check if contact info appears
                contact_visible = await page.query_selector(self.selectors['contact_address'])
                if contact_visible:
                    logger.info("SUCCESS: Contact information detected - CAPTCHA solved!")
                    return True
                
                # Method 2: Check if application link appears
                app_link_visible = await page.query_selector(self.selectors['application_link'])
                if app_link_visible:
                    logger.info("SUCCESS: Application link detected - CAPTCHA solved!")
                    return True
                
                # Method 3: Check if CAPTCHA image is gone
                captcha_still_present = await page.query_selector(self.selectors['captcha_image'])
                if not captcha_still_present:
                    logger.info("SUCCESS: CAPTCHA image disappeared - CAPTCHA solved!")
                    # Wait a bit more to ensure page loads completely
                    await asyncio.sleep(3)
                    return True
                
                # Method 4: Check if there's a success message or page change
                try:
                    # Look for any content that indicates success
                    page_content = await page.text_content('body')
                    if any(indicator in page_content.lower() for indicator in ['bewerbung', 'kontakt', 'ansprechpartner']):
                        # Verify it's not just the CAPTCHA page
                        if not await page.query_selector(self.selectors['captcha_input']):
                            logger.info("SUCCESS: Page content changed - CAPTCHA solved!")
                            return True
                except:
                    pass
                
                # Wait and check again
                await asyncio.sleep(check_interval)
                elapsed_time += check_interval
                
                # Show progress every 30 seconds
                if elapsed_time % 30 == 0:
                    remaining = max_wait_time - elapsed_time
                    logger.info(f"Still waiting for CAPTCHA solution... ({remaining}s remaining)")
            
            # Timeout reached
            logger.warning("TIMEOUT: Manual CAPTCHA solving took too long")
            logger.info("Trying to continue anyway - some content might still be accessible")
            return False
            
        except Exception as e:
            logger.error(f"Error in manual CAPTCHA handling: {e}")
            return False
    
    async def stabilize_page_after_captcha(self, page: Page, job_url: str) -> Optional[Page]:
        """
        Simple page refresh after CAPTCHA solving - no tab creation to avoid reference issues
        """
        try:
            logger.info("[STABILIZE] Refreshing page after CAPTCHA...")
            self.stats['stabilization_attempts'] += 1
            
            # Simple page refresh only - no tab creation
            refresh_success = await self._try_page_refresh(page)
            if refresh_success:
                logger.info("[OK] Page stabilized with refresh")
                self.stats['stabilization_refresh_success'] += 1
                return page
            else:
                logger.warning("[WARNING] Page refresh failed, continuing with current page")
                self.stats['stabilization_failures'] += 1
                return page
            
        except Exception as e:
            logger.error(f"Error in page stabilization: {e}")
            return page  # Return original page if stabilization fails
    
    async def _try_page_refresh(self, page: Page) -> bool:
        """Try to refresh the current page and verify it's working"""
        try:
            logger.debug("Attempting page refresh...")
            
            # Check if page is responsive before refresh
            try:
                await page.evaluate("document.readyState", timeout=5000)
            except:
                logger.debug("Page seems unresponsive, proceeding with refresh")
            
            # Refresh the page
            await page.reload(timeout=self.stabilization_timeout * 1000, wait_until='networkidle')
            
            # Wait for page to stabilize
            await asyncio.sleep(3)
            
            # Verify page is working by checking for basic elements
            try:
                # Try to find job title or company name
                title_element = await page.query_selector(self.selectors['title'])
                company_element = await page.query_selector(self.selectors['company'])
                
                if title_element or company_element:
                    logger.debug("Page refresh successful - basic elements found")
                    return True
                else:
                    logger.debug("Page refresh didn't restore expected content")
                    return False
                    
            except Exception as e:
                logger.debug(f"Page refresh verification failed: {e}")
                return False
                
        except Exception as e:
            logger.debug(f"Page refresh failed: {e}")
            return False
    
    async def simple_page_refresh_if_needed(self, page: Page) -> bool:
        """Simple refresh if contact info missing - no tab creation"""
        try:
            logger.info("[REFRESH] Refreshing page to get missing contact info")
            await page.reload(timeout=30000, wait_until='networkidle')
            await asyncio.sleep(2)  # Wait for page to stabilize
            return True
        except Exception as e:
            logger.warning(f"Page refresh failed: {e}")
            return False
    
    async def extract_text_safe(self, page: Page, selector: str) -> Optional[str]:
        """Safely extract text from element"""
        try:
            element = await page.query_selector(selector)
            if element:
                text = await element.text_content()
                return text.strip() if text else None
            return None
        except Exception as e:
            logger.debug(f"Error extracting text for {selector}: {e}")
            return None
    
    async def extract_attribute_safe(self, page: Page, selector: str, attribute: str) -> Optional[str]:
        """Safely extract attribute from element"""
        try:
            element = await page.query_selector(selector)
            if element:
                attr = await element.get_attribute(attribute)
                return attr.strip() if attr else None
            return None
        except Exception as e:
            logger.debug(f"Error extracting attribute {attribute} for {selector}: {e}")
            return None
    
    async def extract_contact_from_text(self, text: str) -> Dict[str, Optional[str]]:
        """Extract phone and email from text using regex patterns"""
        contact_info = {'phone': None, 'email': None, 'contact_person': None}
        
        if not text:
            return contact_info
        
        # Extract phone
        for pattern in self.contact_patterns['phone']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                phone = match.group(0).strip()
                # Clean common phone formatting
                phone = re.sub(r'Tel\.?[\s:]?', '', phone, flags=re.IGNORECASE)
                phone = re.sub(r'Telefon[\s:]?', '', phone, flags=re.IGNORECASE)
                phone = re.sub(r'Fon[\s:]?', '', phone, flags=re.IGNORECASE)
                contact_info['phone'] = phone.strip()
                break
        
        # Extract email
        for pattern in self.contact_patterns['email']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Get the full match or the first group if it exists
                email = (match.group(1) if match.groups() else match.group(0)).strip()
                contact_info['email'] = email
                break
        
        # Extract contact person (German patterns)
        contact_patterns = [
            r'(?:melde dich bei|Ansprechpartner[in]*:|Kontakt:)\s*([A-Za-zäöüßÄÖÜ\s]+?)(?:\s+unter|\s+\+|\s+0|\s*$)',
            r'(?:Frau|Herr)\s+([A-Za-zäöüßÄÖÜ\s]+?)(?:\s+unter|\s+\+|\s+0|\n|$)',
            r'([A-Za-zäöüßÄÖÜ]+\s+[A-Za-zäöüßÄÖÜ]+)(?:\s+unter|\s+\+|\s+0)'
        ]
        
        for pattern in contact_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                contact_person = match.group(1).strip()
                # Filter out common false positives
                if len(contact_person) > 3 and not any(word in contact_person.lower() for word in ['position', 'job-id', 'vollzeit', 'stelle']):
                    contact_info['contact_person'] = contact_person
                    break
        
        return contact_info
    
    async def extract_direct_contact_info(self, page: Page) -> Dict[str, Optional[str]]:
        """Extract contact info directly from page (post-CAPTCHA scenario)"""
        contact_info = {'phone': None, 'email': None, 'contact_person': None}
        
        try:
            logger.debug(f"Extracting contact info using selectors: phone='{self.selectors['contact_phone']}', email='{self.selectors['contact_email']}'")
            
            # Extract phone (handle tel: links)
            phone_element = await page.query_selector(self.selectors['contact_phone'])
            if phone_element:
                logger.debug("Phone element found")
                phone_href = await phone_element.get_attribute('href')
                phone_text = await phone_element.text_content()
                logger.debug(f"Phone href: '{phone_href}', text: '{phone_text}'")
                
                if phone_href and phone_href.startswith('tel:'):
                    phone = phone_href.replace('tel:', '').replace('&nbsp;', ' ').strip()
                    contact_info['phone'] = phone
                    logger.debug(f"Extracted phone from href: '{phone}'")
                else:
                    # Fallback to text content
                    if phone_text:
                        contact_info['phone'] = phone_text.strip()
                        logger.debug(f"Extracted phone from text: '{phone_text.strip()}'")
            else:
                logger.debug("Phone element not found")
            
            # Extract email (handle mailto: links)
            email_element = await page.query_selector(self.selectors['contact_email'])
            if email_element:
                logger.debug("Email element found")
                email_href = await email_element.get_attribute('href')
                email_text = await email_element.text_content()
                logger.debug(f"Email href: '{email_href}', text: '{email_text}'")
                
                if email_href and email_href.startswith('mailto:'):
                    contact_info['email'] = email_href.replace('mailto:', '')
                    logger.debug(f"Extracted email from href: '{contact_info['email']}'")
                else:
                    # Fallback to text content
                    if email_text and '@' in email_text:
                        contact_info['email'] = email_text.strip()
                        logger.debug(f"Extracted email from text: '{email_text.strip()}'")
            else:
                logger.debug("Email element not found")
            
            # Extract contact person from address block
            address_text = await self.extract_text_safe(page, self.selectors['contact_address'])
            if address_text:
                # Parse contact person name from address
                lines = address_text.split('\n')
                for line in lines:
                    line = line.strip()
                    if any(title in line for title in ['Frau', 'Herr', 'Mr.', 'Ms.', 'Mrs.']):
                        # Extract the name part
                        name_match = re.search(r'(?:Frau|Herr|Mr\.|Ms\.|Mrs\.)\s+([A-Za-zäöüßÄÖÜ\s]+)', line)
                        if name_match:
                            contact_info['contact_person'] = name_match.group(1).strip()
                            break
                        else:
                            contact_info['contact_person'] = line.strip()
                            break
            
            logger.debug(f"Direct contact extraction: {contact_info}")
            return contact_info
            
        except Exception as e:
            logger.debug(f"Error extracting direct contact info: {e}")
            return contact_info
    
    async def scrape_application_link(self, application_url: str) -> Dict[str, Optional[str]]:
        """Scrape contact info from application link (Bonus Task)"""
        if not application_url:
            return {'phone': None, 'email': None, 'contact_person': None}
        
        try:
            logger.info(f"Scraping application link: {application_url}")
            
            # Create new page for application link (separate from main page)
            app_page = await self.context.new_page()
            await app_page.goto(application_url, timeout=30000)
            await app_page.wait_for_load_state('networkidle', timeout=10000)
            
            # Get full page content
            page_content = await app_page.content()
            contact_info = await self.extract_contact_from_text(page_content)
            
            # If no contact found on main page, try common contact pages
            if not contact_info['phone'] and not contact_info['email']:
                contact_paths = ['/kontakt', '/contact', '/impressum', '/imprint', '/about', '/uber-uns']
                base_url = '/'.join(application_url.split('/')[:3])  # Get domain
                
                for path in contact_paths:
                    try:
                        contact_url = f"{base_url}{path}"
                        await app_page.goto(contact_url, timeout=10000)
                        await app_page.wait_for_load_state('networkidle', timeout=5000)
                        
                        contact_page_content = await app_page.content()
                        contact_page_info = await self.extract_contact_from_text(contact_page_content)
                        
                        if contact_page_info['phone'] or contact_page_info['email']:
                            contact_info.update({k: v for k, v in contact_page_info.items() if v})
                            logger.info(f"Found contact info on {contact_url}")
                            break
                            
                    except Exception as e:
                        logger.debug(f"Could not access {contact_url}: {e}")
                        continue
            
            await app_page.close()
            logger.debug(f"Application link contact extraction: {contact_info}")
            return contact_info
            
        except Exception as e:
            logger.warning(f"Error scraping application link {application_url}: {e}")
            return {'phone': None, 'email': None, 'contact_person': None}
    
    async def scrape_single_job(self, page: Page, job_data: Dict, retry_count: int = 0) -> Dict:
        """Scrape a single job page and return structured data"""
        job_url = job_data['job_url']
        ref_nr_from_csv = job_data['ref_nr']
        max_retries = 3
        
        try:
            logger.info(f"Scraping job: {job_url} (attempt {retry_count + 1}/{max_retries + 1})")
            
            # Navigate to job page with crash detection
            try:
                await page.goto(job_url, timeout=30000)
                await page.wait_for_load_state('networkidle', timeout=15000)
            except Exception as nav_error:
                if "Page crashed" in str(nav_error) or "Target page, context or browser has been closed" in str(nav_error):
                    logger.warning(f"[CRASH] Page crash detected for {job_url}")
                    
                    if retry_count < max_retries:
                        logger.info(f"[RETRY] Restarting browser and retrying job (attempt {retry_count + 2}/{max_retries + 1})")
                        
                        # Close browser completely
                        if self.browser:
                            try:
                                await self.browser.close()
                            except:
                                pass
                        
                        # Reinitialize browser
                        await self.setup_browser()
                        
                        # Get new page from fresh browser
                        new_page = await self.context.new_page()
                        
                        # Retry with new browser and page
                        return await self.scrape_single_job(new_page, job_data, retry_count + 1)
                    else:
                        logger.error(f"[ERROR] Max retries ({max_retries}) exceeded for {job_url}")
                        raise nav_error
                else:
                    raise nav_error
            
            # Handle cookie consent dialog
            await self.handle_cookie_consent(page)
            
            # Wait for main content to load after cookie consent
            await asyncio.sleep(3)
            
            # Wait for key elements to be present before extraction
            try:
                await page.wait_for_selector('#detail-kopfbereich-titel', timeout=10000)
                logger.debug("Main job content loaded successfully")
            except Exception as e:
                logger.warning(f"Main job content loading timeout: {e}")
                # Continue anyway - might still be able to extract some data
            
            # NEW: Check for external redirect FIRST
            external_data = None
            if self.external_handler:
                external_data = await self.external_handler.detect_external_redirect(page)
            
            if external_data and external_data.get('has_external_redirect'):
                logger.info(f"[EXTERNAL] External redirect detected: {external_data.get('partner_domain')}")
                
                # Extract basic info from current page (fallback)
                title = await self.extract_text_safe(page, self.selectors['title'])
                company = await self.extract_text_safe(page, self.selectors['company'])
                location = await self.extract_text_safe(page, self.selectors['location'])
                
                # Scrape external job details
                external_job_data = await self.external_handler.scrape_external_job(external_data['external_url'])
                
                # Merge data (prioritize external data)
                scraped_data = {
                    'profession': external_job_data.get('title') or title,
                    'company_name': external_job_data.get('company') or company,
                    'location': external_job_data.get('location') or location,
                    'job_description': external_job_data.get('description'),
                    'telephone': external_job_data.get('contact_phone'),
                    'email': external_job_data.get('contact_email'),
                    'start_date': external_job_data.get('start_date'),
                    'salary': external_job_data.get('salary'),
                    'ref_nr': ref_nr_from_csv,
                    'external_link': external_data.get('external_url'),
                    'application_link': external_data.get('external_url'),
                    'job_type': None,
                    'ausbildungsberuf': None,
                    'application_method': 'external_redirect',
                    'contact_person': None,
                    'scraped_at': datetime.now().isoformat(),
                    'source_url': job_url,
                    'captcha_solved': False,
                    'is_external_redirect': True,
                    'external_partner': external_data.get('partner_domain'),
                    'external_company': external_data.get('partner_company'),
                    'utm_campaign': external_data.get('utm_campaign'),
                    'utm_source': external_data.get('utm_source'),
                    'external_scraped_at': external_job_data.get('external_scraped_at')
                }
                
                # Add any errors from external scraping
                if external_job_data.get('external_scraping_error'):
                    scraped_data['external_error'] = external_job_data['external_scraping_error']
                
                self.scraped_count += 1
                logger.info(f"[SUCCESS] External job scraped: {scraped_data['profession']} @ {scraped_data['external_partner']}")
                return scraped_data
            
            # EXISTING: Continue with normal scraping if no external redirect
            logger.debug("No external redirect, proceeding with normal scraping")
            
            # Extract basic information (available without CAPTCHA)
            title = await self.extract_text_safe(page, self.selectors['title'])
            company = await self.extract_text_safe(page, self.selectors['company'])
            location = await self.extract_text_safe(page, self.selectors['location'])
            start_date = await self.extract_text_safe(page, self.selectors['start_date'])
            job_description = await self.extract_text_safe(page, self.selectors['job_description'])
            job_type = await self.extract_text_safe(page, self.selectors['job_type'])
            ausbildungsberuf = await self.extract_text_safe(page, self.selectors['ausbildungsberuf'])
            
            # Handle CAPTCHA to get contact information
            captcha_solved = await self.handle_captcha(page)
            
            # Initialize contact variables
            phone = None
            email = None
            contact_person = None
            application_link = None
            external_link = None
            ref_nr = None
            application_method = None
            
            if captcha_solved:
                # POST-CAPTCHA PAGE STABILIZATION
                # After CAPTCHA solving, page may have rendering issues or get stuck
                if self.enable_page_stabilization:
                    page = await self.stabilize_page_after_captcha(page, job_url)
                    if not page:
                        # If stabilization failed, return error data
                        logger.error("Failed to stabilize page after CAPTCHA - continuing with basic data")
                        captcha_solved = False
                else:
                    logger.debug("Page stabilization disabled, continuing without refresh")
                # SCENARIO 1: Try to extract direct contact info (post-CAPTCHA)
                direct_contact = await self.extract_direct_contact_info(page)
                phone = direct_contact['phone']
                email = direct_contact['email']
                contact_person = direct_contact['contact_person']
                
                # Extract application links and ref number
                application_link = await self.extract_attribute_safe(page, self.selectors['application_link'], 'href')
                external_link = await self.extract_attribute_safe(page, self.selectors['external_link'], 'href')
                ref_nr = await self.extract_text_safe(page, self.selectors['ref_nr'])
                application_method = await self.extract_text_safe(page, self.selectors['application_method'])
                
                # If no ref_nr found, try footer location
                if not ref_nr:
                    ref_nr = await self.extract_text_safe(page, self.selectors['ref_nr_footer'])
                
                # SCENARIO 2: If contact info missing, try application link (Bonus Task)
                if (not phone or not email) and application_link:
                    logger.info("Contact info missing, attempting application link scraping (Bonus Task)")
                    app_contact = await self.scrape_application_link(application_link)
                    
                    # Use application link data to fill missing info
                    phone = phone or app_contact['phone']
                    email = email or app_contact['email']
                    contact_person = contact_person or app_contact['contact_person']
                    
                    if app_contact['phone'] or app_contact['email']:
                        logger.info("Successfully extracted contact info from application link")
                
                # Log contact extraction results
                contact_status = []
                if phone: contact_status.append("phone")
                if email: contact_status.append("email")
                if contact_person: contact_status.append("contact_person")
                
                if contact_status:
                    logger.info(f"Contact info extracted: {', '.join(contact_status)}")
                else:
                    # Try page refresh to get missing contact info
                    logger.info("[REFRESH] Trying page refresh to get missing contact info")
                    refresh_success = await self.simple_page_refresh_if_needed(page)
                    if refresh_success:
                        # Retry contact extraction after refresh
                        direct_contact_retry = await self.extract_direct_contact_info(page)
                        phone = direct_contact_retry['phone'] or phone
                        email = direct_contact_retry['email'] or email
                        contact_person = direct_contact_retry['contact_person'] or contact_person
                        
                        # Update contact status after retry
                        contact_status = []
                        if phone: contact_status.append("phone")
                        if email: contact_status.append("email")
                        if contact_person: contact_status.append("contact_person")
                        
                        if contact_status:
                            logger.info(f"[SUCCESS] Contact info found after refresh: {', '.join(contact_status)}")
                        else:
                            logger.warning("No contact information found even after refresh (acceptable per assignment)")
                    else:
                        logger.warning("No contact information found (acceptable per assignment)")
            
            # Extract salary from job description if available
            salary = None
            if job_description:
                salary_patterns = [
                    r'€[\s]?\d+[\.,]?\d*(?:\s*-\s*€?\s*\d+[\.,]?\d*)?',
                    r'\d+[\.,]?\d*[\s]?€(?:\s*-\s*\d+[\.,]?\d*\s*€)?',
                    r'Gehalt[\s:]+[€\d\.,\s\-]+',
                    r'Verdienst[\s:]+[€\d\.,\s\-]+',
                    r'Vergütung[\s:]+[€\d\.,\s\-]+',
                    r'Ausbildungsvergütung[\s:]+[€\d\.,\s\-]+'
                ]
                for pattern in salary_patterns:
                    match = re.search(pattern, job_description, re.IGNORECASE)
                    if match:
                        salary = match.group(0).strip()
                        break
            
            # Clean and structure the data
            scraped_data = {
                'profession': title,
                'salary': salary,
                'company_name': company,
                'location': location,
                'start_date': start_date,
                'telephone': phone,
                'email': email,
                'job_description': job_description,
                'ref_nr': ref_nr or ref_nr_from_csv,
                'external_link': external_link,
                'application_link': application_link,
                'job_type': job_type,
                'ausbildungsberuf': ausbildungsberuf,
                'application_method': application_method,
                'contact_person': contact_person,
                'scraped_at': datetime.now().isoformat(),
                'source_url': job_url,
                'captcha_solved': captcha_solved,
                'is_external_redirect': False
            }
            
            self.scraped_count += 1
            logger.info(f"Successfully scraped job {self.scraped_count}: {title}")
            return scraped_data
            
        except Exception as e:
            # Check if it's a crash-related error that wasn't caught above
            if ("Page crashed" in str(e) or "Target page, context or browser has been closed" in str(e)) and retry_count < max_retries:
                logger.warning(f"[CRASH] Crash detected in main exception handler for {job_url}")
                
                # Close browser completely
                if self.browser:
                    try:
                        await self.browser.close()
                    except:
                        pass
                
                # Reinitialize browser
                await self.setup_browser()
                
                # Get new page from fresh browser
                new_page = await self.context.new_page()
                
                # Retry with new browser and page
                return await self.scrape_single_job(new_page, job_data, retry_count + 1)
            
            logger.error(f"Error scraping job {job_url}: {e}")
            self.failed_count += 1
            return {
                'profession': None,
                'salary': None,
                'company_name': None,
                'location': None,
                'start_date': None,
                'telephone': None,
                'email': None,
                'job_description': None,
                'ref_nr': ref_nr_from_csv,
                'external_link': None,
                'application_link': None,
                'job_type': None,
                'ausbildungsberuf': None,
                'application_method': None,
                'contact_person': None,
                'scraped_at': datetime.now().isoformat(),
                'source_url': job_url,
                'error': str(e),
                'captcha_solved': False,
                'is_external_redirect': False
            }
    
    async def save_progress(self, scraped_jobs: List[Dict], batch_number: int = None):
        """Save current progress using FileManager or legacy method + Database"""
        try:
            # Validate data if JobModel is available
            validated_jobs = scraped_jobs
            if JOB_MODEL_AVAILABLE and self.validate_data:
                validated_jobs = []
                for job_data in scraped_jobs:
                    try:
                        job_model = JobModel.from_scraped_data(job_data)
                        validation_result = job_model.validate()
                        
                        if validation_result.is_valid:
                            validated_jobs.append(job_model.to_dict())
                        else:
                            self.stats['validation_failures'] += 1
                            logger.warning(f"Job validation failed: {job_data.get('ref_nr', 'no-ref')} - {validation_result.errors}")
                            # Still save but mark as invalid
                            job_dict = job_model.to_dict()
                            job_dict['validation_errors'] = validation_result.errors
                            validated_jobs.append(job_dict)
                    except Exception as e:
                        logger.error(f"Validation error for job: {e}")
                        validated_jobs.append(job_data)  # Keep original if validation fails
            
            # REALTIME DATABASE LOADING
            try:
                from database.data_loader import JobDataLoader
                loader = JobDataLoader()
                
                # Load each job immediately into database
                for job_data in validated_jobs:
                    try:
                        result = await loader.load_single_job(job_data)
                        if result and result.get('loaded', 0) > 0:
                            logger.info(f"[DATABASE] Job {job_data.get('ref_nr', 'no-ref')} loaded to database")
                        else:
                            logger.warning(f"[WARNING] Job {job_data.get('ref_nr', 'no-ref')} failed to load to database")
                    except Exception as e:
                        logger.error(f"Database load error for job {job_data.get('ref_nr', 'no-ref')}: {e}")
                        
                logger.info(f"[REALTIME] DB: Attempted to load {len(validated_jobs)} jobs to database")
            except Exception as e:
                logger.error(f"Database loading module error: {e}")
                logger.info("Continuing with file-only saving...")
            
            # Use FileManager if available
            if FILE_MANAGER_AVAILABLE and self.file_manager:
                json_path, csv_path = self.file_manager.save_jobs_batch(
                    validated_jobs, 
                    batch_number=batch_number,
                    session_id=self.session_id,
                    use_session_dir=self.use_sessions
                )
                
                logger.info(f"[SUCCESS] Progress saved using FileManager: {len(validated_jobs)} jobs")
                logger.info(f"Files: {json_path.name}, {csv_path.name}")
                
            else:
                # Legacy file saving method
                output_dir = Path("data/output")
                output_dir.mkdir(parents=True, exist_ok=True)
                
                if batch_number is None:
                    # Find next batch number
                    existing_batches = list(output_dir.glob("scraped_jobs_batch_*.json"))
                    batch_numbers = []
                    for batch_file in existing_batches:
                        try:
                            num = int(batch_file.stem.split('_')[-1])
                            batch_numbers.append(num)
                        except:
                            continue
                    batch_number = max(batch_numbers) + 1 if batch_numbers else 1
                
                # Save as JSON (incremental)
                json_path = output_dir / f"scraped_jobs_batch_{batch_number}.json"
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(validated_jobs, f, ensure_ascii=False, indent=2)
                
                # Save as CSV (consolidated)
                csv_path = output_dir / "scraped_jobs_progress.csv"
                df = pd.DataFrame(validated_jobs)
                df.to_csv(csv_path, index=False, encoding='utf-8')
                
                logger.info(f"[FILES] Progress saved (legacy): {len(validated_jobs)} jobs in batch {batch_number}")
            
        except Exception as e:
            logger.error(f"[ERROR] Error saving progress: {e}")
            self.stats['errors'] += 1
    
    async def load_existing_progress(self) -> List[Dict]:
        """Load previously scraped job data"""
        try:
            progress_file = Path("data/output/scraped_jobs_progress.csv")
            if progress_file.exists():
                df = pd.read_csv(progress_file)
                logger.info(f"Loaded {len(df)} previously scraped jobs")
                return df.to_dict('records')
            return []
        except Exception as e:
            logger.error(f"Error loading existing progress: {e}")
            return []
    
    async def process_jobs_batch(self, job_urls: List[Dict], batch_size: int = 10) -> List[Dict]:
        """Process jobs in batches to avoid overwhelming the server"""
        all_scraped_jobs = []
        total_jobs = len(job_urls)
        
        # Use single page for all jobs to maintain session
        page = await self.context.new_page()
        
        for i, job_data in enumerate(job_urls):
            job_number = i + 1
            logger.info(f"Processing job {job_number}/{total_jobs}")
            
            # Scrape job with enhanced tracking and crash recovery
            try:
                scraped_job = await self.scrape_single_job(page, job_data)
                all_scraped_jobs.append(scraped_job)
            except Exception as e:
                # If scrape_single_job completely fails after retries, create error record
                logger.error(f"Complete failure for job {job_number}: {e}")
                error_job = {
                    'profession': None,
                    'salary': None,
                    'company_name': None,
                    'location': None,
                    'start_date': None,
                    'telephone': None,
                    'email': None,
                    'job_description': None,
                    'ref_nr': job_data.get('ref_nr'),
                    'external_link': None,
                    'application_link': None,
                    'job_type': None,
                    'ausbildungsberuf': None,
                    'application_method': None,
                    'contact_person': None,
                    'scraped_at': datetime.now().isoformat(),
                    'source_url': job_data.get('job_url'),
                    'error': f"Complete failure after retries: {str(e)}",
                    'captcha_solved': False,
                    'is_external_redirect': False
                }
                all_scraped_jobs.append(error_job)
                
                # Try to create a new page for the next job if browser is still available
                try:
                    if self.context:
                        page = await self.context.new_page()
                except Exception as page_error:
                    logger.warning(f"Failed to create new page, will try to continue: {page_error}")
            
            # Update statistics
            self.stats['total_processed'] += 1
            current_job = all_scraped_jobs[-1]  # Get the job we just added
            if current_job.get('captcha_solved'):
                self.stats['captcha_encounters'] += 1
                self.stats['captcha_solved'] += 1
            if not current_job.get('error'):
                self.stats['successful_scrapes'] += 1
            else:
                self.stats['errors'] += 1
            
            # Save progress every N jobs (from settings)
            if job_number % self.batch_size == 0:
                batch_number = job_number // self.batch_size
                await self.save_progress(all_scraped_jobs, batch_number)
                
                # Log enhanced progress with statistics
                success_rate = (self.stats['successful_scrapes'] / max(self.stats['total_processed'], 1)) * 100
                logger.info(f"[PROGRESS] Progress: {job_number}/{total_jobs} jobs ({success_rate:.1f}% success)")
                if self.stats['captcha_encounters'] > 0:
                    captcha_rate = (self.stats['captcha_solved'] / self.stats['captcha_encounters']) * 100
                    logger.info(f"[CAPTCHA] CAPTCHAs: {self.stats['captcha_solved']}/{self.stats['captcha_encounters']} solved ({captcha_rate:.1f}%)")
            
            # Add configurable delay between requests
            await asyncio.sleep(self.delay_between_jobs)
        
        await page.close()
        return all_scraped_jobs
    
    async def validate_job_data(self, job_data: Dict) -> bool:
        """Validate extracted job data"""
        required_fields = ['profession', 'company_name', 'source_url']
        for field in required_fields:
            if not job_data.get(field):
                return False
        return True
    
    async def export_to_csv(self, jobs_data: List[Dict], output_path: str):
        """Export job data to CSV file"""
        try:
            df = pd.DataFrame(jobs_data)
            # Reorder columns to match requirements (11 main fields + additional)
            # Update column_order to include new fields
            column_order = [
                'profession', 'salary', 'company_name', 'location', 'start_date',
                'telephone', 'email', 'job_description', 'ref_nr', 'external_link',
                'application_link',  # 11 required fields
                'job_type', 'ausbildungsberuf', 'application_method', 'contact_person',
                'captcha_solved', 'scraped_at', 'source_url',  # Existing additional fields
                'is_external_redirect', 'external_partner', 'external_company',  # NEW
                'utm_campaign', 'utm_source', 'external_scraped_at'  # NEW
            ]
            
            # Only include columns that exist in the data
            existing_columns = [col for col in column_order if col in df.columns]
            df = df.reindex(columns=existing_columns)
            
            df.to_csv(output_path, index=False, encoding='utf-8')
            logger.info(f"Data exported to {output_path}")
        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
    
    async def export_to_json(self, jobs_data: List[Dict], output_path: str):
        """Export job data to JSON file"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(jobs_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Data exported to {output_path}")
        except Exception as e:
            logger.error(f"Error exporting to JSON: {e}")
    
    async def generate_missing_emails_report(self, jobs_data: List[Dict]):
        """Generate report of jobs with missing email addresses"""
        missing_emails = [job for job in jobs_data if not job.get('email')]
        
        output_dir = Path("data/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        report_path = output_dir / "missing_emails.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(missing_emails, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Missing emails report: {len(missing_emails)}/{len(jobs_data)} jobs missing emails")
        logger.info(f"Report saved to {report_path}")
    
    def get_scraping_statistics(self) -> Dict:
        """Get detailed scraping statistics"""
        # Calculate jobs per minute
        elapsed_time = (datetime.now() - self.stats['session_start_time']).total_seconds() / 60
        if elapsed_time > 0:
            self.stats['jobs_per_minute'] = self.stats['total_processed'] / elapsed_time
        
        # Calculate success rates
        success_rate = 0
        if self.stats['total_processed'] > 0:
            success_rate = (self.stats['successful_scrapes'] / self.stats['total_processed']) * 100
        
        captcha_success_rate = 0
        if self.stats['captcha_encounters'] > 0:
            captcha_success_rate = (self.stats['captcha_solved'] / self.stats['captcha_encounters']) * 100
        
        # Add FileManager statistics if available
        file_stats = {}
        if FILE_MANAGER_AVAILABLE and self.file_manager:
            try:
                file_stats = self.file_manager.get_statistics()
            except Exception as e:
                logger.debug(f"Could not get FileManager stats: {e}")
        
        # Add CAPTCHA solver statistics if available
        captcha_stats = {}
        if self.captcha_solver:
            try:
                captcha_stats = self.captcha_solver.get_statistics()
            except Exception as e:
                logger.debug(f"Could not get CAPTCHA solver stats: {e}")
        
        return {
            'session_info': {
                'session_id': self.session_id,
                'start_time': self.stats['session_start_time'].isoformat(),
                'elapsed_minutes': round(elapsed_time, 2),
                'use_sessions': self.use_sessions,
                'validate_data': self.validate_data
            },
            'scraping_performance': {
                'total_processed': self.stats['total_processed'],
                'successful_scrapes': self.stats['successful_scrapes'],
                'errors': self.stats['errors'],
                'success_rate_percent': round(success_rate, 2),
                'jobs_per_minute': round(self.stats['jobs_per_minute'], 2),
                'validation_failures': self.stats['validation_failures']
            },
            'captcha_performance': {
                'encounters': self.stats['captcha_encounters'],
                'solved': self.stats['captcha_solved'],
                'success_rate_percent': round(captcha_success_rate, 2),
                'auto_solve_enabled': self.auto_solve_captcha,
                **captcha_stats
            },
            'page_stabilization': {
                'attempts': self.stats['stabilization_attempts'],
                'refresh_success': self.stats['stabilization_refresh_success'],
                'failures': self.stats['stabilization_failures'],
                'enabled': self.enable_page_stabilization,
                'timeout_seconds': self.stabilization_timeout
            },
            'file_management': file_stats,
            'configuration': {
                'batch_size': self.batch_size,
                'delay_between_jobs': self.delay_between_jobs,
                'max_jobs_per_session': self.max_jobs_per_session
            }
        }
    
    async def resume_from_session(self, session_id: str) -> bool:
        """Resume scraping from a previous session"""
        if not FILE_MANAGER_AVAILABLE or not self.file_manager:
            logger.warning("Cannot resume: FileManager not available")
            return False
        
        try:
            session_data = self.file_manager.load_session_progress(session_id)
            if session_data:
                logger.info(f"Resuming from session {session_id}: {len(session_data)} jobs found")
                self.session_id = session_id
                return True
            else:
                logger.warning(f"No session data found for {session_id}")
                return False
        except Exception as e:
            logger.error(f"Error resuming from session: {e}")
            return False
    
    def log_final_summary(self, all_jobs: List[Dict]):
        """Log comprehensive final summary"""
        stats = self.get_scraping_statistics()
        
        logger.info("\n" + "="*60)
        logger.info("[COMPLETE] SCRAPING SESSION COMPLETED")
        logger.info("="*60)
        
        # Session info
        session_info = stats['session_info']
        logger.info(f"📅 Session: {session_info['session_id']}")
        logger.info(f"[TIME] Duration: {session_info['elapsed_minutes']} minutes")
        
        # Performance metrics
        perf = stats['scraping_performance']
        logger.info(f"[TOTAL] Total Jobs: {len(all_jobs)}")
        logger.info(f"[SUCCESS] Successful: {perf['successful_scrapes']} ({perf['success_rate_percent']}%)")
        logger.info(f"[ERROR] Errors: {perf['errors']}")
        logger.info(f"[SPEED] Speed: {perf['jobs_per_minute']} jobs/minute")
        
        if perf['validation_failures'] > 0:
            logger.info(f"[WARNING]  Validation failures: {perf['validation_failures']}")
        
        # CAPTCHA performance
        captcha = stats['captcha_performance']
        if captcha['encounters'] > 0:
            logger.info(f"[CAPTCHA] CAPTCHAs: {captcha['solved']}/{captcha['encounters']} solved ({captcha['success_rate_percent']}%)")
        
        # Page stabilization performance
        stabilization = stats['page_stabilization']
        if stabilization['attempts'] > 0:
            success_rate = (stabilization['refresh_success'] / stabilization['attempts'] * 100) if stabilization['attempts'] > 0 else 0
            logger.info(f"[STABILIZE] Page refreshes: {stabilization['refresh_success']}/{stabilization['attempts']} successful ({success_rate:.1f}%)")
            if stabilization['failures'] > 0:
                logger.info(f"  - Failed refreshes: {stabilization['failures']}")
        
        # File management
        if FILE_MANAGER_AVAILABLE and self.file_manager:
            file_stats = stats['file_management']
            if file_stats:
                logger.info(f"[FILES] Files created: {file_stats.get('total_files_created', 0)}")
                if self.use_sessions:
                    logger.info(f"[SESSION] Session directory: {file_stats.get('session_directory', 'N/A')}")
        
        # Data quality insights
        jobs_with_email = len([job for job in all_jobs if job.get('email')])
        jobs_with_phone = len([job for job in all_jobs if job.get('telephone')])
        jobs_with_contact = len([job for job in all_jobs if job.get('contact_person')])
        
        logger.info("\n[QUALITY] DATA QUALITY SUMMARY:")
        logger.info(f"[EMAIL] Jobs with email: {jobs_with_email}/{len(all_jobs)} ({jobs_with_email/len(all_jobs)*100:.1f}%)")
        logger.info(f"[PHONE] Jobs with phone: {jobs_with_phone}/{len(all_jobs)} ({jobs_with_phone/len(all_jobs)*100:.1f}%)")
        logger.info(f"[CONTACT] Jobs with contact: {jobs_with_contact}/{len(all_jobs)} ({jobs_with_contact/len(all_jobs)*100:.1f}%)")
        
        logger.info("="*60)
    
    async def run(self, input_csv_path: str = None, resume: bool = True, auto_solve_captcha: bool = None):
        """Main entry point to run the job scraper"""
        try:
            # Override auto_solve_captcha if provided
            if auto_solve_captcha is not None:
                self.auto_solve_captcha = auto_solve_captcha
                if auto_solve_captcha and not self.captcha_solver and CAPTCHA_SOLVER_AVAILABLE:
                    try:
                        self.captcha_solver = CaptchaSolver()
                        logger.info("[SUCCESS] CAPTCHA auto-solver initialized")
                    except Exception as e:
                        logger.warning(f"[ERROR] Failed to initialize CAPTCHA solver: {e}")
                        self.auto_solve_captcha = False
            
            # Setup
            await self.setup_browser()
            
            # Load job URLs
            if not input_csv_path:
                input_csv_path = PATHS.get('input_csv', 'data/input/job_urls.csv')
            
            job_urls = await self.load_job_urls(input_csv_path)
            if not job_urls:
                logger.error("No job URLs to process")
                return
            
            # Load existing progress if resuming
            existing_jobs = []
            if resume:
                existing_jobs = await self.load_existing_progress()
                processed_urls = {job.get('source_url') for job in existing_jobs}
                job_urls = [job for job in job_urls if job['job_url'] not in processed_urls]
                logger.info(f"Resuming: {len(job_urls)} jobs remaining to scrape")
            
            if not job_urls:
                logger.info("All jobs already scraped!")
                return
            
            # Apply max jobs per session limit for debugging
            logger.info(f"[DEBUG] Loaded {len(job_urls)} job URLs, max_jobs_per_session = {self.max_jobs_per_session}")
            if len(job_urls) > self.max_jobs_per_session:
                logger.info(f"[DEBUG] LIMITING jobs from {len(job_urls)} to {self.max_jobs_per_session} for this session")
                job_urls = job_urls[:self.max_jobs_per_session]
                logger.info(f"[DEBUG] After limiting: {len(job_urls)} jobs will be processed")
            else:
                logger.info(f"[DEBUG] No limiting needed: {len(job_urls)} <= {self.max_jobs_per_session}")
            
            # Process jobs
            captcha_mode = "Auto + Manual fallback" if self.auto_solve_captcha else "Manual only"
            logger.info(f"Starting to scrape {len(job_urls)} jobs...")
            logger.info(f"CAPTCHA solving mode: {captcha_mode}")
            logger.info(f"[DEBUG] Max jobs per session: {self.max_jobs_per_session}")
            
            scraped_jobs = await self.process_jobs_batch(job_urls, batch_size=self.batch_size)
            
            # Combine with existing data
            all_jobs = existing_jobs + scraped_jobs
            
            # Export final results
            output_dir = Path("data/output")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            await self.export_to_csv(all_jobs, output_dir / "scraped_jobs.csv")
            await self.export_to_json(all_jobs, output_dir / "scraped_jobs.json")
            await self.generate_missing_emails_report(all_jobs)
            
            # Final comprehensive summary
            self.log_final_summary(all_jobs)
            
            # Legacy compatibility statistics
            logger.info(f"Legacy stats - Scraped: {self.scraped_count}, Failed: {self.failed_count}")
            
            if self.captcha_solver:
                try:
                    model_info = self.captcha_solver.get_model_info()
                    logger.info(f"CAPTCHA solver used: {model_info['model_name']}")
                except Exception as e:
                    logger.debug(f"Could not get CAPTCHA solver model info: {e}")
            
        except Exception as e:
            logger.error(f"Error in main run: {e}")
        finally:
            if self.browser:
                await self.browser.close()

async def main():
    """Main function to run the scraper with enhanced configuration"""
    # Enhanced options from settings
    auto_solve = 'trocr' in CAPTCHA_SETTINGS.get('solving_strategies', ['manual'])
    use_sessions = FILE_MANAGEMENT_SETTINGS.get('use_sessions', False)
    validate_data = VALIDATION_SETTINGS.get('validate_on_scrape', False)
    enable_resume = SCRAPER_SETTINGS.get('enable_resume', True)
    
    logger.info(f"Enhanced JobScraper starting with:")
    logger.info(f"  - Auto CAPTCHA solving: {auto_solve}")
    logger.info(f"  - Session management: {use_sessions}")
    logger.info(f"  - Data validation: {validate_data}")
    logger.info(f"  - Resume capability: {enable_resume}")
    
    scraper = JobScraper(
        auto_solve_captcha=auto_solve,
        use_sessions=use_sessions,
        validate_data=validate_data
    )
    
    input_path = PATHS.get('input_csv', 'data/input/job_urls.csv')
    try:
        await scraper.run(input_csv_path=input_path, resume=enable_resume)
    finally:
        # Ensure session cleanup
        if scraper.file_manager:
            scraper.file_manager.cleanup_session()

if __name__ == "__main__":
    asyncio.run(main())