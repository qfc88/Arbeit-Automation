"""
Specialized contact scraper for extracting company contact information
Handles cases where basic contact extraction fails or needs enhancement
"""

import re
import asyncio
from typing import Dict, List, Optional, Set
from playwright.async_api import Page
import logging
from urllib.parse import urljoin, urlparse
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class ContactScraper:
    def __init__(self, context=None):
        """Initialize contact scraper with browser context"""
        self.context = context
        self.session_contacts = {}  # Cache for session
        
        # German-specific contact page patterns
        self.contact_page_patterns = [
            r'/kontakt',
            r'/contact', 
            r'/impressum',
            r'/imprint',
            r'/about',
            r'/uber[-_]uns',
            r'/team',
            r'/ansprechpartner',
            r'/karriere',
            r'/jobs',
            r'/bewerbung',
            r'/standorte',
            r'/filiale'
        ]
        
        # Email priority patterns (German companies)
        self.email_priorities = {
            'hr': ['hr@', 'personal@', 'bewerbung@', 'jobs@', 'karriere@'],
            'info': ['info@', 'kontakt@', 'mail@'],
            'general': ['office@', 'zentrale@', 'verwaltung@'],
            'specific': []  # Will be filled with job-specific emails
        }
        
        # German phone patterns
        self.german_phone_patterns = [
            r'\+49[\s\-\(\)]?\d+[\s\-\(\)\d]+',           # +49 format
            r'0\d{2,5}[\s\-\/]\d+[\s\-\/\d]+',           # German local
            r'Tel\.?[\s:]?\+?49[\s\-\(\)]?\d+[\s\-\(\)\d]+',  # Tel: +49...
            r'Telefon[\s:]?\+?49[\s\-\(\)]?\d+[\s\-\(\)\d]+', # Telefon: +49...
            r'Fon[\s:]?\+?49[\s\-\(\)]?\d+[\s\-\(\)\d]+',     # Fon: +49...
            r'0\d{3,5}[\s\-\/]\d{6,8}',                  # Standard German format
        ]
    
    async def extract_basic_contact(self, page: Page) -> Dict[str, str]:
        """Extract basic contact info from current job page"""
        contact_info = {'phone': None, 'email': None, 'contact_person': None}
        
        try:
            # Get page content for analysis
            page_content = await page.content()
            
            # Extract emails
            emails = await self.extract_emails_from_page(page)
            if emails:
                prioritized_emails = self.prioritize_emails(emails)
                contact_info['email'] = prioritized_emails[0] if prioritized_emails else None
            
            # Extract phone numbers
            phones = await self.extract_phone_numbers(page)
            if phones:
                contact_info['phone'] = list(phones)[0]  # Take first valid phone
            
            # Extract contact person from various selectors
            contact_person_selectors = [
                '#detail-bewerbung-adresse',
                '.ansprechpartner',
                '.kontakt-person',
                'address'
            ]
            
            for selector in contact_person_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        text = await element.text_content()
                        person = self._extract_contact_person_from_text(text)
                        if person:
                            contact_info['contact_person'] = person
                            break
                except:
                    continue
            
            logger.debug(f"Basic contact extraction: {contact_info}")
            return contact_info
            
        except Exception as e:
            logger.error(f"Error in basic contact extraction: {e}")
            return contact_info
    
    async def find_company_website(self, page: Page) -> Optional[str]:
        """Find company website URL from job page"""
        try:
            # Method 1: Look for application links that go to company domain
            app_link_selectors = [
                '#detail-bewerbung-url',
                'a[href*="bewerbung"]',
                'a[href*="karriere"]',
                'a[href*="jobs"]'
            ]
            
            for selector in app_link_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        href = await element.get_attribute('href')
                        if href and self._is_company_website(href):
                            return self._extract_base_domain(href)
                except:
                    continue
            
            # Method 2: Look for company homepage links
            company_link_selectors = [
                'a[href*="www."]',
                'a[title*="Homepage"]',
                'a[title*="Website"]'
            ]
            
            for selector in company_link_selectors:
                try:
                    links = await page.query_selector_all(selector)
                    for link in links:
                        href = await link.get_attribute('href')
                        if href and self._is_company_website(href):
                            return self._extract_base_domain(href)
                except:
                    continue
            
            # Method 3: Extract from text content (look for website mentions)
            page_text = await page.text_content('body')
            website_patterns = [
                r'www\.[\w\-\.]+\.[a-zA-Z]{2,}',
                r'https?://[\w\-\.]+\.[a-zA-Z]{2,}',
                r'[\w\-]+\.de(?:\s|$)',
                r'[\w\-]+\.com(?:\s|$)'
            ]
            
            for pattern in website_patterns:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                for match in matches:
                    clean_url = self._clean_website_url(match)
                    if clean_url and self._is_company_website(clean_url):
                        return clean_url
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding company website: {e}")
            return None
    
    async def scrape_company_website(self, website_url: str) -> Dict[str, str]:
        """Scrape contact info from company website"""
        if not website_url or not self.context:
            return {'phone': None, 'email': None, 'contact_person': None}
        
        try:
            logger.info(f"Scraping company website: {website_url}")
            
            # Create new page for company website
            company_page = await self.context.new_page()
            await company_page.goto(website_url, timeout=15000)
            await company_page.wait_for_load_state('networkidle', timeout=8000)
            
            # Start with homepage
            contact_info = await self._scrape_page_for_contacts(company_page)
            
            # If no contacts found, try contact pages
            if not contact_info['phone'] and not contact_info['email']:
                contact_links = await self.find_contact_page_links(company_page)
                enhanced_contacts = await self.scrape_contact_pages(contact_links)
                
                # Merge results, prioritizing enhanced contacts
                for key, value in enhanced_contacts.items():
                    if value and not contact_info[key]:
                        contact_info[key] = value
            
            await company_page.close()
            
            # Clean and validate results
            contact_info = self.clean_contact_data(contact_info)
            logger.info(f"Company website contact extraction: {contact_info}")
            
            return contact_info
            
        except Exception as e:
            logger.warning(f"Error scraping company website {website_url}: {e}")
            return {'phone': None, 'email': None, 'contact_person': None}
    
    async def extract_emails_from_page(self, page: Page) -> Set[str]:
        """Extract all email addresses from a page"""
        emails = set()
        
        try:
            # Get page content
            page_content = await page.content()
            
            # Email patterns
            email_patterns = [
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                r'mailto:([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})',
                r'E-?Mail[\s:]+([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})',
                r'Kontakt[\s:]+([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})'
            ]
            
            for pattern in email_patterns:
                matches = re.findall(pattern, page_content, re.IGNORECASE)
                for match in matches:
                    email = match if isinstance(match, str) else match[0] if match else None
                    if email and self.validate_email(email):
                        emails.add(email.lower())
            
            # Also check for emails in href attributes
            try:
                email_links = await page.query_selector_all('a[href^="mailto:"]')
                for link in email_links:
                    href = await link.get_attribute('href')
                    if href:
                        email = href.replace('mailto:', '')
                        if self.validate_email(email):
                            emails.add(email.lower())
            except:
                pass
            
            return emails
            
        except Exception as e:
            logger.debug(f"Error extracting emails: {e}")
            return emails
    
    async def extract_phone_numbers(self, page: Page) -> Set[str]:
        """Extract phone numbers from page"""
        phones = set()
        
        try:
            page_content = await page.content()
            
            for pattern in self.german_phone_patterns:
                matches = re.findall(pattern, page_content, re.IGNORECASE)
                for match in matches:
                    cleaned_phone = self._clean_phone_number(match)
                    if cleaned_phone and self.validate_phone(cleaned_phone):
                        phones.add(cleaned_phone)
            
            # Also check tel: links
            try:
                phone_links = await page.query_selector_all('a[href^="tel:"]')
                for link in phone_links:
                    href = await link.get_attribute('href')
                    if href:
                        phone = href.replace('tel:', '')
                        cleaned_phone = self._clean_phone_number(phone)
                        if cleaned_phone and self.validate_phone(cleaned_phone):
                            phones.add(cleaned_phone)
            except:
                pass
            
            return phones
            
        except Exception as e:
            logger.debug(f"Error extracting phone numbers: {e}")
            return phones
    
    async def find_contact_page_links(self, page: Page) -> List[str]:
        """Find links to contact/about/team pages"""
        contact_links = []
        base_url = page.url
        
        try:
            # Get all links on the page
            links = await page.query_selector_all('a[href]')
            
            for link in links:
                try:
                    href = await link.get_attribute('href')
                    text = await link.text_content()
                    
                    if href:
                        # Convert relative URLs to absolute
                        if href.startswith('/'):
                            full_url = urljoin(base_url, href)
                        elif href.startswith('http'):
                            full_url = href
                        else:
                            continue
                        
                        # Check if this looks like a contact page
                        if self._is_contact_page_url(full_url, text):
                            contact_links.append(full_url)
                        
                except Exception as e:
                    logger.debug(f"Error processing link: {e}")
                    continue
            
            # Remove duplicates and limit to reasonable number
            unique_links = list(set(contact_links))[:10]
            logger.debug(f"Found contact page links: {unique_links}")
            
            return unique_links
            
        except Exception as e:
            logger.debug(f"Error finding contact page links: {e}")
            return contact_links
    
    async def scrape_contact_pages(self, contact_links: List[str]) -> Dict[str, str]:
        """Scrape multiple contact-related pages"""
        best_contact_info = {'phone': None, 'email': None, 'contact_person': None}
        
        if not contact_links or not self.context:
            return best_contact_info
        
        for url in contact_links:
            try:
                logger.debug(f"Scraping contact page: {url}")
                
                contact_page = await self.context.new_page()
                await contact_page.goto(url, timeout=10000)
                await contact_page.wait_for_load_state('networkidle', timeout=5000)
                
                page_contact_info = await self._scrape_page_for_contacts(contact_page)
                await contact_page.close()
                
                # Merge best results
                for key, value in page_contact_info.items():
                    if value and not best_contact_info[key]:
                        best_contact_info[key] = value
                
                # If we have all info, no need to continue
                if all(best_contact_info.values()):
                    break
                    
            except Exception as e:
                logger.debug(f"Error scraping contact page {url}: {e}")
                continue
        
        return best_contact_info
    
    def validate_email(self, email: str) -> bool:
        """Validate email address format"""
        if not email or len(email) > 254:
            return False
        
        # Basic email validation
        pattern = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$'
        if not re.match(pattern, email, re.IGNORECASE):
            return False
        
        # Filter out common false positives
        invalid_patterns = [
            r'@example\.',
            r'@test\.',
            r'@localhost',
            r'noreply@',
            r'no-reply@',
            r'@placeholder\.',
            r'@domain\.',
            r'\.jpg@',
            r'\.png@',
            r'\.pdf@'
        ]
        
        for pattern in invalid_patterns:
            if re.search(pattern, email, re.IGNORECASE):
                return False
        
        return True
    
    def validate_phone(self, phone: str) -> bool:
        """Validate phone number format"""
        if not phone:
            return False
        
        # Remove all non-digit characters for length check
        digits_only = re.sub(r'\D', '', phone)
        
        # German phone numbers should have 10-12 digits (excluding country code)
        if len(digits_only) < 8 or len(digits_only) > 15:
            return False
        
        # Should start with + or 0 for German numbers
        if not (phone.startswith('+49') or phone.startswith('0') or phone.startswith('49')):
            return False
        
        return True
    
    def clean_contact_data(self, contact_data: Dict[str, str]) -> Dict[str, str]:
        """Clean and normalize contact data"""
        cleaned_data = {}
        
        # Clean email
        email = contact_data.get('email')
        if email:
            email = email.lower().strip()
            if self.validate_email(email):
                cleaned_data['email'] = email
            else:
                cleaned_data['email'] = None
        else:
            cleaned_data['email'] = None
        
        # Clean phone
        phone = contact_data.get('phone')
        if phone:
            cleaned_phone = self._clean_phone_number(phone)
            if self.validate_phone(cleaned_phone):
                cleaned_data['phone'] = cleaned_phone
            else:
                cleaned_data['phone'] = None
        else:
            cleaned_data['phone'] = None
        
        # Clean contact person
        contact_person = contact_data.get('contact_person')
        if contact_person:
            # Remove extra whitespace and common prefixes
            contact_person = re.sub(r'\s+', ' ', contact_person.strip())
            contact_person = re.sub(r'^(Ansprechpartner[in]*:|Kontakt:|Contact:)\s*', '', contact_person, flags=re.IGNORECASE)
            
            if len(contact_person) > 2 and len(contact_person) < 100:
                cleaned_data['contact_person'] = contact_person
            else:
                cleaned_data['contact_person'] = None
        else:
            cleaned_data['contact_person'] = None
        
        return cleaned_data
    
    async def enhance_single_job_contact(self, job_data: Dict) -> Optional[Dict]:
        """Enhance single job contact information for realtime processing"""
        try:
            ref_nr = job_data.get('ref_nr', 'unknown')
            company_name = job_data.get('company_name', 'Unknown')
            
            logger.info(f"[ENHANCE] Realtime enhancement: {company_name} ({ref_nr})")
            
            # Check if we already have complete contact info
            has_email = job_data.get('current_email') and str(job_data.get('current_email')).strip()
            has_phone = job_data.get('current_phone') and str(job_data.get('current_phone')).strip()
            
            if has_email and has_phone:
                return None  # No enhancement needed
            
            # Try company website first
            company_website = job_data.get('company_website')
            if not company_website and job_data.get('job_url'):
                # Extract domain from job URL
                company_website = self._extract_base_domain(job_data['job_url'])
            
            enhanced_contacts = {}
            
            if company_website:
                try:
                    # Scrape company website for contact info with timeout
                    website_contacts = await asyncio.wait_for(
                        self.scrape_company_website(company_website),
                        timeout=25  # 25 second timeout
                    )
                    
                    if website_contacts:
                        # Add missing contacts
                        if not has_email and website_contacts.get('email'):
                            enhanced_contacts['email'] = website_contacts['email']
                            logger.info(f"[SUCCESS] Found email: {website_contacts['email']}")
                        
                        if not has_phone and website_contacts.get('phone'):
                            enhanced_contacts['phone'] = website_contacts['phone']
                            logger.info(f"[SUCCESS] Found phone: {website_contacts['phone']}")
                        
                        # Add source information
                        enhanced_contacts['enhancement_source'] = 'company_website'
                        enhanced_contacts['enhanced_from_url'] = company_website
                        
                    else:
                        logger.info(f"[WARNING] No contacts found on website: {company_website}")
                
                except asyncio.TimeoutError:
                    logger.warning(f"[TIMEOUT] Website scraping timeout: {company_website}")
                except Exception as e:
                    logger.warning(f"[ERROR] Website scraping error: {company_website} - {e}")
            
            # If still missing info, try alternative approaches
            if not enhanced_contacts.get('email') and not has_email:
                # Try to generate educated guesses based on company name
                guessed_email = self._generate_email_guesses(company_name, company_website)
                if guessed_email:
                    enhanced_contacts['email'] = guessed_email
                    enhanced_contacts['email_confidence'] = 'guessed'
                    logger.info(f"[GUESS] Guessed email: {guessed_email}")
            
            return enhanced_contacts if enhanced_contacts else None
            
        except Exception as e:
            logger.error(f"Error in single job contact enhancement: {e}")
            return None
    
    async def enhance_job_contacts(self, jobs_data: List[Dict]) -> List[Dict]:
        """Enhance job data with additional contact information"""
        enhanced_jobs = []
        
        for i, job in enumerate(jobs_data):
            logger.info(f"Enhancing job {i+1}/{len(jobs_data)}: {job.get('company_name', 'Unknown')}")
            
            enhanced_job = job.copy()
            
            # Skip if already has complete contact info
            if job.get('phone') and job.get('email'):
                enhanced_jobs.append(enhanced_job)
                continue
            
            # Try to find company website
            company_website = None
            if job.get('application_link'):
                company_website = self._extract_base_domain(job['application_link'])
            
            if company_website:
                # Scrape company website for contact info
                website_contacts = await self.scrape_company_website(company_website)
                
                # Enhance missing fields
                if not enhanced_job.get('phone') and website_contacts.get('phone'):
                    enhanced_job['phone'] = website_contacts['phone']
                
                if not enhanced_job.get('email') and website_contacts.get('email'):
                    enhanced_job['email'] = website_contacts['email']
                
                if not enhanced_job.get('contact_person') and website_contacts.get('contact_person'):
                    enhanced_job['contact_person'] = website_contacts['contact_person']
            
            enhanced_jobs.append(enhanced_job)
            
            # Add delay to be respectful
            await asyncio.sleep(2)
        
        return enhanced_jobs
    
    async def process_missing_contacts(self, jobs_without_contacts: List[Dict]) -> List[Dict]:
        """Process jobs that are missing contact information"""
        logger.info(f"Processing {len(jobs_without_contacts)} jobs with missing contacts")
        
        processed_jobs = []
        
        for job in jobs_without_contacts:
            # Try multiple strategies to find contact info
            contact_info = {'phone': None, 'email': None, 'contact_person': None}
            
            # Strategy 1: Enhanced application link scraping
            if job.get('application_link'):
                website_contacts = await self.scrape_company_website(job['application_link'])
                contact_info.update({k: v for k, v in website_contacts.items() if v})
            
            # Strategy 2: Company name search (if no application link)
            if not any(contact_info.values()) and job.get('company_name'):
                # This would require search engine integration
                # For now, just log that we could implement this
                logger.debug(f"Could implement company search for: {job['company_name']}")
            
            # Update job with found contact info
            updated_job = job.copy()
            updated_job.update(contact_info)
            updated_job['contact_enhanced'] = True
            
            processed_jobs.append(updated_job)
            
            # Respectful delay
            await asyncio.sleep(3)
        
        return processed_jobs
    
    def prioritize_emails(self, emails: Set[str]) -> List[str]:
        """Prioritize emails by relevance (HR, jobs, info, etc.)"""
        if not emails:
            return []
        
        prioritized = []
        email_list = list(emails)
        
        # Priority levels
        for priority_group in ['hr', 'info', 'general']:
            for pattern in self.email_priorities[priority_group]:
                for email in email_list:
                    if email.startswith(pattern) and email not in prioritized:
                        prioritized.append(email)
        
        # Add remaining emails
        for email in email_list:
            if email not in prioritized:
                prioritized.append(email)
        
        return prioritized
    
    # Helper methods
    def _extract_contact_person_from_text(self, text: str) -> Optional[str]:
        """Extract contact person name from text"""
        if not text:
            return None
        
        # German contact person patterns
        patterns = [
            r'(?:Frau|Herr)\s+([A-Za-zäöüßÄÖÜ\s]{3,30})',
            r'Ansprechpartner[in]*:\s*([A-Za-zäöüßÄÖÜ\s]{3,30})',
            r'Kontakt:\s*([A-Za-zäöüßÄÖÜ\s]{3,30})',
            r'([A-Za-zäöüßÄÖÜ]+\s+[A-Za-zäöüßÄÖÜ]+)(?:\s|$)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                # Filter out common false positives
                if not any(word in name.lower() for word in ['gmbh', 'kg', 'ag', 'ltd', 'inc', 'straße', 'platz']):
                    return name
        
        return None
    
    def _is_company_website(self, url: str) -> bool:
        """Check if URL appears to be a company website"""
        if not url:
            return False
        
        # Skip obvious non-company domains
        excluded_domains = [
            'arbeitsagentur.de',
            'jobcenter.de', 
            'google.com',
            'facebook.com',
            'linkedin.com',
            'xing.de',
            'indeed.com',
            'stepstone.de'
        ]
        
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        
        for excluded in excluded_domains:
            if excluded in domain:
                return False
        
        return True
    
    def _generate_email_guesses(self, company_name: str, company_website: str = None) -> Optional[str]:
        """Generate educated email guesses based on company name and website"""
        try:
            if not company_name:
                return None
            
            # Clean company name
            clean_name = re.sub(r'[^\w\s]', '', company_name.lower())
            clean_name = re.sub(r'\s+', '', clean_name)
            
            # Remove common suffixes
            suffixes = ['gmbh', 'ag', 'kg', 'ohg', 'mbh', 'co', 'ltd', 'inc', 'corp']
            for suffix in suffixes:
                clean_name = clean_name.replace(suffix, '')
            
            # Get domain from website
            domain = None
            if company_website:
                try:
                    parsed = urlparse(company_website if company_website.startswith('http') else f'http://{company_website}')
                    domain = parsed.netloc or parsed.path
                    domain = domain.replace('www.', '')
                except:
                    pass
            
            # Generate email guesses
            if domain and clean_name:
                # Common German business email patterns
                email_patterns = [
                    f"bewerbung@{domain}",
                    f"jobs@{domain}",
                    f"hr@{domain}",
                    f"personal@{domain}",
                    f"info@{domain}",
                    f"kontakt@{domain}"
                ]
                
                # Return first reasonable guess
                return email_patterns[0] if email_patterns else None
            
            return None
            
        except Exception as e:
            logger.error(f"Error generating email guesses: {e}")
            return None

    def _extract_base_domain(self, url: str) -> str:
        """Extract base domain from URL"""
        try:
            parsed_url = urlparse(url)
            return f"{parsed_url.scheme}://{parsed_url.netloc}"
        except:
            return url
    
    def _clean_website_url(self, url_text: str) -> str:
        """Clean and format website URL"""
        url_text = url_text.strip()
        
        if not url_text.startswith('http'):
            if url_text.startswith('www.'):
                url_text = 'https://' + url_text
            else:
                url_text = 'https://www.' + url_text
        
        return url_text
    
    def _is_contact_page_url(self, url: str, link_text: str = '') -> bool:
        """Check if URL/text indicates a contact page"""
        url_lower = url.lower()
        text_lower = link_text.lower() if link_text else ''
        
        # URL patterns
        for pattern in self.contact_page_patterns:
            if re.search(pattern, url_lower):
                return True
        
        # Link text patterns (German)
        contact_text_patterns = [
            'kontakt', 'contact', 'impressum', 'imprint', 'about',
            'über uns', 'team', 'ansprechpartner', 'standort', 'filiale'
        ]
        
        for pattern in contact_text_patterns:
            if pattern in text_lower:
                return True
        
        return False
    
    def _clean_phone_number(self, phone: str) -> str:
        """Clean and format phone number"""
        if not phone:
            return ''
        
        # Remove common prefixes
        phone = re.sub(r'^(Tel\.?|Telefon|Fon)[\s:]*', '', phone, flags=re.IGNORECASE)
        
        # Clean formatting but keep + and digits
        phone = re.sub(r'[^\d\+\-\s\(\)]', '', phone)
        
        # Normalize spacing
        phone = re.sub(r'\s+', ' ', phone.strip())
        
        return phone
    
    async def _scrape_page_for_contacts(self, page: Page) -> Dict[str, str]:
        """Scrape a single page for contact information"""
        contact_info = {'phone': None, 'email': None, 'contact_person': None}
        
        try:
            # Extract emails
            emails = await self.extract_emails_from_page(page)
            if emails:
                prioritized_emails = self.prioritize_emails(emails)
                contact_info['email'] = prioritized_emails[0]
            
            # Extract phones
            phones = await self.extract_phone_numbers(page)
            if phones:
                contact_info['phone'] = list(phones)[0]
            
            # Extract contact person from page text
            page_text = await page.text_content('body')
            contact_person = self._extract_contact_person_from_text(page_text)
            if contact_person:
                contact_info['contact_person'] = contact_person
            
            return contact_info
            
        except Exception as e:
            logger.debug(f"Error scraping page for contacts: {e}")
            return contact_info


# Utility functions
def is_business_email(email: str) -> bool:
    """Check if email appears to be a business email"""
    if not email:
        return False
    
    # Common personal email domains
    personal_domains = [
        'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
        'web.de', 'gmx.de', 't-online.de', 'freenet.de'
    ]
    
    domain = email.split('@')[1].lower() if '@' in email else ''
    return domain not in personal_domains

def extract_domain_from_email(email: str) -> str:
    """Extract domain from email address"""
    return email.split('@')[1] if '@' in email else ''

def is_contact_related_url(url: str) -> bool:
    """Check if URL likely contains contact information"""
    contact_indicators = [
        'kontakt', 'contact', 'impressum', 'imprint', 'about',
        'team', 'ansprechpartner', 'standort', 'office'
    ]
    
    url_lower = url.lower()
    return any(indicator in url_lower for indicator in contact_indicators)