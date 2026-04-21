"""
External Link Handler for Job Scraper
Handles cases where job details are redirected to external partner sites
"""

import re
import asyncio
from typing import Dict, List, Optional, Set
from playwright.async_api import Page, BrowserContext
import logging
from urllib.parse import urlparse, parse_qs, urljoin
from datetime import datetime
import sys
from pathlib import Path

# Add project paths
sys.path.append(str(Path(__file__).parent.parent / "utils"))

# Setup logging
logger = logging.getLogger(__name__)

class ExternalLinkHandler:
    """
    Handles detection and scraping of external job redirects
    Common in German job aggregator sites
    """
    
    def __init__(self, context: BrowserContext = None):
        """Initialize external link handler"""
        self.context = context
        self.partner_cache = {}  # Cache for partner site layouts
        
        # Enhanced external redirect detection patterns
        self.external_selectors = {
            'external_container': [
                '.externe-Beschreibung',
                '.external-description',
                '[class*="extern"]',
                '[id*="extern"]',
                '.partner-redirect',
                '.job-redirect',
                '.external-link-container',
                '[class*="redirect"]',
                '[class*="weiterleitung"]',
                '[class*="partner"]',
                '.job-external',
                '.third-party',
                '.external-job',
                '[id*="redirect"]'
            ],
            'external_button': [
                '#detail-beschreibung-externe-url-btn',
                'a[href*="externe"]',
                'a[target="_blank"][href*="stellenanzeige"]',
                'a[target="_blank"][href*="bewerbung"]',
                'a[target="_blank"][href*="ausbildung"]',
                'a[target="_blank"][href*="job"]',
                'a[target="_blank"][href*="position"]',
                'a[target="_blank"][href*="karriere"]',
                '.ba-btn[target="_blank"]',
                '.redirect-btn',
                'a[rel*="noopener"][href*="utm_"]',
                'a[rel*="noopener"][target="_blank"]',
                'button[data-external-url]',
                'a[class*="external"]',
                'a[class*="redirect"]',
                '.job-apply-btn[target="_blank"]',
                '.apply-now[target="_blank"]',
                'a[href*="stepstone"]',
                'a[href*="indeed"]',
                'a[href*="xing"]',
                'a[href*="monster"]',
                'a[href*="azubi"]',
                'a[href*="jobs.de"]'
            ],
            'external_source': [
                '.externe-quelle',
                '.external-source',
                '[class*="quelle"]',
                '.partner-info',
                '.source-info'
            ],
            'external_text_indicators': [
                'vollständige stellenbeschreibung',
                'externe seite',
                'kooperationspartner',
                'partner site',
                'jetzt bewerben',
                'zur stellenanzeige',
                'originalanzeige',
                'weiter zur',
                'direkt bewerben',
                'apply now',
                'zur bewerbung',
                'job ansehen',
                'stelle ansehen',
                'original job',
                'complete job description',
                'full description',
                'more details',
                'weitere informationen',
                'detailseite',
                'auf partnerseite'
            ]
        }
        
        # Known German job partner sites with their characteristics
        self.partner_sites = {
            'azubi.de': {
                'company': 'Funke Works GmbH',
                'type': 'apprenticeship',
                'selectors': {
                    'title': ['h1', '.job-title', '[data-testid="job-title"]'],
                    'company': ['.company-name', '[data-testid="company-name"]'],
                    'location': ['.job-location', '[data-testid="location"]'],
                    'description': ['.job-description', '.description-content'],
                    'contact_email': ['a[href^="mailto:"]'],
                    'contact_phone': ['a[href^="tel:"]', '[class*="phone"]'],
                    'start_date': ['[class*="start"]', '[class*="beginn"]'],
                    'salary': ['[class*="salary"]', '[class*="gehalt"]', '[class*="vergütung"]']
                }
            },
            'stepstone.de': {
                'company': 'StepStone Deutschland GmbH',
                'type': 'general',
                'selectors': {
                    'title': ['h1[data-at="job-title"]', '.job-title'],
                    'company': ['[data-at="company-name"]', '.company-name'],
                    'location': ['[data-at="job-location"]', '.location'],
                    'description': ['[data-at="job-description"]', '.job-description'],
                    'contact_email': ['a[href^="mailto:"]'],
                    'contact_phone': ['a[href^="tel:"]']
                }
            },
            'indeed.com': {
                'company': 'Indeed',
                'type': 'general',
                'selectors': {
                    'title': ['h1[data-testid="jobsearch-JobInfoHeader-title"]', '.jobsearch-JobInfoHeader-title'],
                    'company': ['[data-testid="inlineHeader-companyName"]', '.icl-u-lg-mr--sm'],
                    'location': ['[data-testid="job-location"]', '.icl-u-xs-mt--xs'],
                    'description': ['#jobDescriptionText', '.jobsearch-jobDescriptionText']
                }
            },
            'xing.de': {
                'company': 'XING AG',
                'type': 'professional',
                'selectors': {
                    'title': ['h1', '.job-title'],
                    'company': ['.company-name', '[data-testid="company"]'],
                    'location': ['.location', '[data-testid="location"]'],
                    'description': ['.job-description', '.description']
                }
            },
            'monster.de': {
                'company': 'Monster Worldwide Deutschland GmbH',
                'type': 'general',
                'selectors': {
                    'title': ['h1', '.job-title'],
                    'company': ['.company', '.employer'],
                    'location': ['.location', '.job-location'],
                    'description': ['.job-description', '.description']
                }
            },
            'jobware.de': {
                'company': 'Jobware Online-Service GmbH',
                'type': 'general'
            },
            'stellenanzeigen.de': {
                'company': 'Stellenanzeigen.de GmbH',
                'type': 'general'
            },
            'jobs.de': {
                'company': 'Jobs.de GmbH',
                'type': 'general'
            },
            'karriere.at': {
                'company': 'Karriere.at',
                'type': 'general'
            },
            'jobscout24.de': {
                'company': 'JobScout24',
                'type': 'general'
            },
            'meinestadt.de': {
                'company': 'meinestadt.de GmbH',
                'type': 'local'
            },
            'stellenwerk.de': {
                'company': 'Stellenwerk GmbH',
                'type': 'student'
            },
            'academics.de': {
                'company': 'academics.de',
                'type': 'academic'
            },
            'get-in-it.de': {
                'company': 'get-in-it.de',
                'type': 'it'
            }
        }
        
        # German phone number patterns
        self.phone_patterns = [
            r'\+49[\s\-\(\)]?\d+[\s\-\(\)\d]+',
            r'0\d{2,5}[\s\-\/]\d+[\s\-\/\d]+',
            r'Tel\.?[\s:]?\+?49[\s\-\(\)]?\d+[\s\-\(\)\d]+',
            r'Telefon[\s:]?\+?49[\s\-\(\)]?\d+[\s\-\(\)\d]+',
            r'Fon[\s:]?\+?49[\s\-\(\)]?\d+[\s\-\(\)\d]+'
        ]
        
        # Email patterns
        self.email_patterns = [
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            r'mailto:([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})',
            r'E-?Mail[\s:]+([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})'
        ]
    
    async def detect_external_redirect(self, page: Page) -> Optional[Dict]:
        """
        Detect if job page has external partner redirect
        Returns external link info or None
        """
        try:
            logger.debug("Checking for external redirect...")
            
            # Method 1: Check for external container elements
            external_container = await self._find_external_container(page)
            if external_container:
                logger.info("External container found")
                
                # Extract external link
                external_link = await self._extract_external_link(page)
                if not external_link:
                    logger.warning("External container found but no link extracted")
                    return None
                
                # Extract source information
                source_info = await self._extract_source_info(page)
                
                # Parse UTM parameters
                utm_params = self._parse_utm_parameters(external_link)
                
                # Identify partner type
                partner_info = self._identify_partner(external_link)
                
                external_info = {
                    'has_external_redirect': True,
                    'external_url': external_link,
                    'partner_domain': partner_info['domain'],
                    'partner_company': partner_info['company'],
                    'partner_type': partner_info['type'],
                    'source_text': source_info.get('text'),
                    'utm_campaign': utm_params.get('utm_campaign'),
                    'utm_source': utm_params.get('utm_source'),
                    'utm_medium': utm_params.get('utm_medium'),
                    'detected_at': datetime.now().isoformat()
                }
                
                logger.info(f"External redirect detected: {partner_info['domain']}")
                return external_info
            
            # Method 2: Check for external text patterns in page content
            page_text = await page.text_content('body')
            if await self._has_external_text_indicators(page_text):
                logger.debug("External text indicators found, searching for links...")
                
                # Look for any external job site links
                external_links = await self._find_external_job_links(page)
                if external_links:
                    best_link = external_links[0]  # Take first/best match
                    partner_info = self._identify_partner(best_link)
                    
                    return {
                        'has_external_redirect': True,
                        'external_url': best_link,
                        'partner_domain': partner_info['domain'],
                        'partner_company': partner_info['company'],
                        'partner_type': partner_info['type'],
                        'detection_method': 'text_pattern',
                        'detected_at': datetime.now().isoformat()
                    }
            
            logger.debug("No external redirect detected")
            return None
            
        except Exception as e:
            logger.error(f"Error detecting external redirect: {e}")
            return None
    
    async def scrape_external_job(self, external_url: str) -> Dict:
        """
        Dynamically scrape job details from ANY external partner site
        """
        if not external_url or not self.context:
            logger.warning("No external URL or context for scraping")
            return {}
        
        try:
            logger.info(f"<LINK> Following external link: {external_url}")
            
            # Create new page for external site
            external_page = await self.context.new_page()
            
            # Set reasonable timeouts for external sites
            await external_page.goto(external_url, timeout=30000)
            await external_page.wait_for_load_state('networkidle', timeout=15000)
            
            # Handle cookie consent on external site
            await self._handle_external_cookies(external_page)
            
            # Wait for content to load
            await asyncio.sleep(2)
            
            # Extract job details dynamically based on the specific site
            partner_domain = self._get_domain_from_url(external_url)
            logger.info(f"<PARTNER> Scraping from partner: {partner_domain}")
            
            # Try comprehensive extraction for ANY site
            external_data = await self._scrape_comprehensive_external_data(external_page, partner_domain)
            
            await external_page.close()
            
            # Add metadata
            external_data['external_scraped_at'] = datetime.now().isoformat()
            external_data['external_source_url'] = external_url
            external_data['external_partner_domain'] = partner_domain
            
            extracted_fields = len([k for k, v in external_data.items() if v and str(v).strip()])
            logger.info(f"<SUCCESS> External scraping completed: {extracted_fields} fields extracted from {partner_domain}")
            return external_data
            
        except Exception as e:
            logger.warning(f"<ERROR> Error scraping external job {external_url}: {e}")
            return {'external_scraping_error': str(e)}
    
    async def _scrape_comprehensive_external_data(self, page: Page, partner_domain: str) -> Dict:
        """
        Comprehensive scraping that works for ANY external job site
        """
        data = {}
        
        try:
            # Step 1: Try partner-specific extraction first
            partner_data = await self._scrape_by_partner(page, partner_domain)
            data.update(partner_data)
            
            # Step 2: Universal scraping for missing fields
            universal_data = await self._scrape_universal_job_data(page)
            # Only add if not already found in partner-specific extraction
            for key, value in universal_data.items():
                if key not in data and value:
                    data[key] = value
            
            # Step 3: Extract emails and phones like contact_scraper
            contact_data = await self._extract_contact_info_comprehensive(page)
            data.update(contact_data)
            
            logger.info(f"<EXTRACT> Comprehensive extraction from {partner_domain}: {len([k for k, v in data.items() if v])} fields found")
            return data
            
        except Exception as e:
            logger.error(f"Error in comprehensive external scraping: {e}")
            return data
    
    async def _scrape_universal_job_data(self, page: Page) -> Dict:
        """
        Universal selectors that work across most job sites
        """
        data = {}
        
        # Universal job field selectors - work for most sites
        universal_selectors = {
            'profession': [
                'h1', 'h2', '.job-title', '.position-title', '.title', '.jobtitle',
                '[class*="title"]', '[data-testid*="title"]', '[role="heading"]',
                '.job-name', '.position-name', '.vacancy-title', '.stelle-title',
                '.stellenbezeichnung', '.jobangebot-title', '.position', '.headline'
            ],
            'job_description': [
                '.job-description', '.description', '.beschreibung', '.content', '.job-content',
                '[class*="description"]', '[data-testid*="description"]', '.details',
                '.job-details', '.position-description', '.text-content', '.aufgaben',
                '.tätigkeiten', '.verantwortlichkeiten', '.job-info', '.inhalt',
                '[class*="content"]', '.vacancy-description', '.stellenbeschreibung'
            ],
            'company_name': [
                '.company-name', '.company', '.employer', '.arbeitgeber', '.firma',
                '[class*="company"]', '[data-testid*="company"]', '.unternehmen',
                '.organization', '.org-name', '.company-info', '.employer-name'
            ],
            'location': [
                '.location', '.job-location', '.ort', '.standort', '.adresse',
                '[class*="location"]', '[data-testid*="location"]', '.address',
                '.place', '.city', '.region', '.arbeitsort', '.geography'
            ],
            'salary': [
                '.salary', '.gehalt', '.vergütung', '.lohn', '.bezahlung', '.wage',
                '[class*="salary"]', '[data-testid*="salary"]', '.compensation',
                '.pay', '.income', '.entlohnung', '.verdienst', '[class*="gehalt"]'
            ],
            'start_date': [
                '.start-date', '.antritt', '.beginn', '.datum', '.employment-start',
                '[class*="start"]', '[class*="beginn"]', '.verfügbar', '.beginning',
                '[class*="eintrittsdatum"]', '.begin-date', '[id*="start"]'
            ],
            'job_type': [
                '.job-type', '.employment-type', '.anstellungsart', '.arbeitszeit',
                '[class*="type"]', '[class*="employment"]', '.work-type', '.position-type'
            ]
        }
        
        # Extract using universal selectors
        for field, selectors in universal_selectors.items():
            for selector in selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        text = await element.text_content()
                        if text and text.strip() and len(text.strip()) > 2:
                            data[field] = text.strip()
                            break
                except:
                    continue
        
        return data
    
    async def _extract_contact_info_comprehensive(self, page: Page) -> Dict:
        """
        Extract contact info like contact_scraper does
        """
        contact_data = {}
        
        try:
            # Extract emails from page content
            page_content = await page.content()
            
            # Email extraction patterns
            email_patterns = [
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                r'mailto:([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})',
                r'E-?Mail[\s:]+([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})',
                r'Kontakt[\s:]+([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})'
            ]
            
            emails = set()
            for pattern in email_patterns:
                matches = re.findall(pattern, page_content, re.IGNORECASE)
                for match in matches:
                    email = match if isinstance(match, str) else match[0] if match else None
                    if email and self._validate_email(email):
                        emails.add(email.lower())
            
            # Extract from mailto links
            try:
                email_links = await page.query_selector_all('a[href^="mailto:"]')
                for link in email_links:
                    href = await link.get_attribute('href')
                    if href:
                        email = href.replace('mailto:', '')
                        if self._validate_email(email):
                            emails.add(email.lower())
            except:
                pass
            
            if emails:
                # Prioritize HR/job-related emails
                hr_emails = [e for e in emails if any(prefix in e for prefix in ['hr@', 'jobs@', 'karriere@', 'bewerbung@'])]
                contact_data['email'] = hr_emails[0] if hr_emails else list(emails)[0]
            
            # Extract phone numbers
            german_phone_patterns = [
                r'\+49[\s\-\(\)]?\d+[\s\-\(\)\d]+',
                r'0\d{2,5}[\s\-\/]\d+[\s\-\/\d]+',
                r'Tel\.?[\s:]?\+?49[\s\-\(\)]?\d+[\s\-\(\)\d]+',
                r'Telefon[\s:]?\+?49[\s\-\(\)]?\d+[\s\-\(\)\d]+',
                r'0\d{3,5}[\s\-\/]\d{6,8}'
            ]
            
            phones = set()
            for pattern in german_phone_patterns:
                matches = re.findall(pattern, page_content, re.IGNORECASE)
                for match in matches:
                    cleaned_phone = self._clean_phone_number(match)
                    if cleaned_phone and self._validate_phone(cleaned_phone):
                        phones.add(cleaned_phone)
            
            # Extract from tel: links
            try:
                phone_links = await page.query_selector_all('a[href^="tel:"]')
                for link in phone_links:
                    href = await link.get_attribute('href')
                    if href:
                        phone = href.replace('tel:', '')
                        cleaned_phone = self._clean_phone_number(phone)
                        if cleaned_phone and self._validate_phone(cleaned_phone):
                            phones.add(cleaned_phone)
            except:
                pass
            
            if phones:
                contact_data['telephone'] = list(phones)[0]
            
            return contact_data
            
        except Exception as e:
            logger.debug(f"Error extracting contact info: {e}")
            return contact_data
    
    async def _find_external_container(self, page: Page) -> bool:
        """Find external redirect container on page"""
        for selector in self.external_selectors['external_container']:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    logger.debug(f"Found external container: {selector}")
                    return True
            except:
                continue
        return False
    
    async def _extract_external_link(self, page: Page) -> Optional[str]:
        """Extract external link URL from page"""
        try:
            # Try button/link selectors
            for selector in self.external_selectors['external_button']:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        # Check for href attribute
                        href = await element.get_attribute('href')
                        if href and href.startswith('http'):
                            logger.debug(f"Found external link via {selector}: {href}")
                            return href
                        
                        # Check for data attributes
                        data_url = await element.get_attribute('data-external-url')
                        if data_url and data_url.startswith('http'):
                            return data_url
                except:
                    continue
            
            # Fallback: search for any external job site links in page
            external_links = await self._find_external_job_links(page)
            if external_links:
                return external_links[0]
            
            return None
            
        except Exception as e:
            logger.debug(f"Error extracting external link: {e}")
            return None
    
    async def _extract_source_info(self, page: Page) -> Dict[str, Optional[str]]:
        """Extract source/partner information from page"""
        source_info = {'text': None, 'company': None}
        
        try:
            for selector in self.external_selectors['external_source']:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        text = await element.text_content()
                        if text:
                            source_info['text'] = text.strip()
                            
                            # Parse "Quelle: Company / site.de" format
                            match = re.search(r'Quelle:\s*(.+?)\s*/\s*(.+?)(?:\s|$)', text, re.IGNORECASE)
                            if match:
                                source_info['company'] = match.group(1).strip()
                            break
                except:
                    continue
            
            return source_info
            
        except Exception as e:
            logger.debug(f"Error extracting source info: {e}")
            return source_info
    
    def _parse_utm_parameters(self, url: str) -> Dict[str, Optional[str]]:
        """Parse UTM tracking parameters from URL"""
        try:
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            
            utm_params = {}
            for param in ['utm_campaign', 'utm_source', 'utm_medium', 'utm_content', 'utm_term']:
                values = query_params.get(param, [])
                utm_params[param] = values[0] if values else None
            
            return utm_params
            
        except Exception as e:
            logger.debug(f"Error parsing UTM parameters: {e}")
            return {}
    
    def _identify_partner(self, url: str) -> Dict[str, str]:
        """Identify partner site from URL"""
        try:
            domain = self._get_domain_from_url(url)
            
            for site_domain, site_info in self.partner_sites.items():
                if site_domain in domain:
                    return {
                        'domain': site_domain,
                        'company': site_info.get('company', 'Unknown'),
                        'type': site_info.get('type', 'general')
                    }
            
            return {
                'domain': domain,
                'company': 'Unknown Partner',
                'type': 'unknown'
            }
            
        except Exception:
            return {
                'domain': 'unknown',
                'company': 'Unknown Partner',
                'type': 'unknown'
            }
    
    def _get_domain_from_url(self, url: str) -> str:
        """Extract domain from URL"""
        try:
            parsed_url = urlparse(url)
            return parsed_url.netloc.lower()
        except:
            return 'unknown'
    
    async def _has_external_text_indicators(self, page_text: str) -> bool:
        """Check if page text contains external redirect indicators"""
        if not page_text:
            return False
        
        page_text_lower = page_text.lower()
        for indicator in self.external_selectors['external_text_indicators']:
            if indicator in page_text_lower:
                logger.debug(f"Found external text indicator: {indicator}")
                return True
        return False
    
    async def _find_external_job_links(self, page: Page) -> List[str]:
        """Find all external job site links on page"""
        external_links = []
        
        try:
            # Get all links
            links = await page.query_selector_all('a[href]')
            
            for link in links:
                try:
                    href = await link.get_attribute('href')
                    if href and href.startswith('http'):
                        domain = self._get_domain_from_url(href)
                        if any(partner in domain for partner in self.partner_sites.keys()):
                            external_links.append(href)
                except:
                    continue
            
            return external_links
            
        except Exception as e:
            logger.debug(f"Error finding external job links: {e}")
            return external_links
    
    async def _handle_external_cookies(self, page: Page):
        """Handle cookie consent dialogs on external sites"""
        try:
            await asyncio.sleep(1)  # Wait for dialogs to appear
            
            cookie_selectors = [
                'button:has-text("Akzeptieren")',
                'button:has-text("Alle akzeptieren")',
                'button:has-text("Zustimmen")',
                'button:has-text("Accept")',
                'button:has-text("OK")',
                '[data-testid*="cookie"][data-testid*="accept"]',
                '[id*="cookie"][id*="accept"]',
                '.cookie-accept',
                '.consent-accept',
                '#onetrust-accept-btn-handler',
                '.ot-sdk-btn-primary'
            ]
            
            for selector in cookie_selectors:
                try:
                    button = await page.query_selector(selector)
                    if button and await button.is_visible():
                        await button.click()
                        await asyncio.sleep(1)
                        logger.debug(f"Clicked external cookie consent: {selector}")
                        break
                except:
                    continue
                    
        except Exception as e:
            logger.debug(f"External cookie handling error: {e}")
    
    async def _scrape_by_partner(self, page: Page, partner_domain: str) -> Dict:
        """Scrape job details based on partner site"""
        try:
            # Find matching partner configuration
            partner_config = None
            for site_domain, config in self.partner_sites.items():
                if site_domain in partner_domain:
                    partner_config = config
                    break
            
            if partner_config and 'selectors' in partner_config:
                logger.debug(f"Using specific selectors for {partner_domain}")
                return await self._scrape_with_selectors(page, partner_config['selectors'])
            else:
                logger.debug(f"Using generic scraping for {partner_domain}")
                return await self._scrape_generic_partner(page)
                
        except Exception as e:
            logger.error(f"Error scraping {partner_domain}: {e}")
            return {}
    
    async def _scrape_with_selectors(self, page: Page, selectors: Dict) -> Dict:
        """Scrape using partner-specific selectors"""
        data = {}
        
        for field, selector_list in selectors.items():
            try:
                for selector in selector_list:
                    element = await page.query_selector(selector)
                    if element:
                        if field in ['contact_email', 'contact_phone']:
                            # Extract from href attribute
                            href = await element.get_attribute('href')
                            if href:
                                if field == 'contact_email' and href.startswith('mailto:'):
                                    data[field] = href.replace('mailto:', '')
                                elif field == 'contact_phone' and href.startswith('tel:'):
                                    data[field] = href.replace('tel:', '')
                                break
                        else:
                            # Extract text content
                            text = await element.text_content()
                            if text and text.strip():
                                data[field] = text.strip()
                                break
            except:
                continue
        
        # Also try regex extraction for emails and phones
        if not data.get('contact_email') or not data.get('contact_phone'):
            page_content = await page.content()
            
            if not data.get('contact_email'):
                email = self._extract_email_from_text(page_content)
                if email:
                    data['contact_email'] = email
            
            if not data.get('contact_phone'):
                phone = self._extract_phone_from_text(page_content)
                if phone:
                    data['contact_phone'] = phone
        
        return data
    
    async def _scrape_generic_partner(self, page: Page) -> Dict:
        """Enhanced generic scraping for ALL partner sites - comprehensive like contact_scraper"""
        data = {}
        
        try:
            # Extract ALL job information comprehensively
            await self._extract_comprehensive_job_data(page, data)
            
            # Enhanced generic selectors that work across ALL job sites
            generic_selectors = {
                'profession': [
                    'h1', 'h2', '.job-title', '.position-title', '.title', '.jobtitle',
                    '[class*="title"]', '[data-testid*="title"]', '[id*="title"]',
                    '.job-name', '.position-name', '.vacancy-title', '.stelle-title',
                    '[class*="heading"]', '[class*="header"]', '.job-header h1',
                    '.stellenbezeichnung', '.jobangebot-title', '.position'
                ],
                'company_name': [
                    '.company-name', '.company', '.employer', '.arbeitgeber',
                    '[class*="company"]', '[data-testid*="company"]', '[id*="company"]',
                    '.firma', '.unternehmen', '.organization', '.org-name'
                ],
                'location': [
                    '.location', '.job-location', '.ort', '.standort', '.adresse',
                    '[class*="location"]', '[data-testid*="location"]', '[id*="location"]',
                    '.address', '.place', '.city', '.region'
                ],
                'salary': [
                    '.salary', '.gehalt', '.vergütung', '.lohn', '.bezahlung',
                    '[class*="salary"]', '[data-testid*="salary"]', '[id*="salary"]',
                    '.wage', '.compensation', '.pay', '.remuneration'
                ],
                'job_description': [
                    '.job-description', '.description', '.beschreibung', '.content',
                    '[class*="description"]', '[data-testid*="description"]', 
                    '.job-content', '.text-content', '.details', '.aufgaben',
                    '.tätigkeiten', '.verantwortlichkeiten', '.job-details'
                ],
                'start_date': [
                    '.start-date', '.antritt', '.beginn', '.datum',
                    '[class*="start"]', '[class*="date"]', '.verfügbar-ab'
                ]
            }
            
            # Extract using universal selectors
            for field, selectors in universal_selectors.items():
                for selector in selectors:
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            text = await element.text_content()
                            if text and text.strip() and len(text.strip()) > 2:
                                data[field] = text.strip()
                                break
                    except:
                        continue
            
            return data
            
            return data
            
        except Exception as e:
            logger.error(f"Error in generic partner scraping: {e}")
            return {}
    
    def _extract_email_from_text(self, text: str) -> Optional[str]:
        """Extract email from text using regex"""
        if not text:
            return None
        
        for pattern in self.email_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                email = match.group(1) if match.groups() else match.group(0)
                if self._validate_email(email):
                    return email.lower()
        return None
    
    def _extract_phone_from_text(self, text: str) -> Optional[str]:
        """Extract phone number from text using regex"""
        if not text:
            return None
        
        for pattern in self.phone_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                phone = match.group(0).strip()
                cleaned_phone = self._clean_phone_number(phone)
                if self._validate_phone(cleaned_phone):
                    return cleaned_phone
        return None
    
    def _validate_email(self, email: str) -> bool:
        """Validate email address"""
        if not email or len(email) > 254:
            return False
        
        # Basic email validation
        pattern = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$'
        if not re.match(pattern, email, re.IGNORECASE):
            return False
        
        # Filter out common false positives
        invalid_patterns = [
            r'@example\.', r'@test\.', r'@localhost',
            r'noreply@', r'no-reply@', r'@placeholder\.',
            r'@domain\.', r'\.jpg@', r'\.png@', r'\.pdf@'
        ]
        
        for pattern in invalid_patterns:
            if re.search(pattern, email, re.IGNORECASE):
                return False
        
        return True
    
    def _validate_phone(self, phone: str) -> bool:
        """Validate German phone number"""
        if not phone:
            return False
        
        digits_only = re.sub(r'\D', '', phone)
        
        # German phone numbers should have 8-15 digits
        if len(digits_only) < 8 or len(digits_only) > 15:
            return False
        
        # Should start with appropriate prefixes for German numbers
        if not (phone.startswith('+49') or phone.startswith('0') or phone.startswith('49')):
            return False
        
        return True
    
    def _clean_phone_number(self, phone: str) -> str:
        """Clean and format phone number"""
        if not phone:
            return ''
        
        # Remove common prefixes
        phone = re.sub(r'^(Tel\.?|Telefon|Fon)[\s:]*', '', phone, flags=re.IGNORECASE)
        
        # Clean formatting but keep important characters
        phone = re.sub(r'[^\d\+\-\s\(\)]', '', phone)
        
        # Normalize spacing
        phone = re.sub(r'\s+', ' ', phone.strip())
        
        return phone
    
    async def _extract_enhanced_contacts(self, page: Page) -> Dict:
        """Enhanced contact extraction for any job site"""
        contact_data = {}
        
        try:
            # Universal contact selectors that work across most job sites
            contact_selectors = {
                'contact_email': [
                    'a[href^="mailto:"]',
                    '[class*="email"]',
                    '[class*="mail"]',
                    '[id*="email"]',
                    '[id*="mail"]',
                    '.kontakt-email',
                    '.contact-email'
                ],
                'contact_phone': [
                    'a[href^="tel:"]',
                    '[class*="phone"]',
                    '[class*="telefon"]',
                    '[class*="tel"]',
                    '[id*="phone"]',
                    '[id*="telefon"]',
                    '.kontakt-phone',
                    '.contact-phone'
                ],
                'contact_person': [
                    '[class*="contact-person"]',
                    '[class*="ansprechpartner"]',
                    '[class*="kontakt"]',
                    '.contact-name',
                    '.recruiter',
                    '.hr-contact'
                ]
            }
            
            for field, selectors in contact_selectors.items():
                if contact_data.get(field):
                    continue  # Skip if already found
                    
                for selector in selectors:
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            if field in ['contact_email', 'contact_phone']:
                                # Check href first
                                href = await element.get_attribute('href')
                                if href:
                                    if field == 'contact_email' and href.startswith('mailto:'):
                                        contact_data[field] = href.replace('mailto:', '')
                                        break
                                    elif field == 'contact_phone' and href.startswith('tel:'):
                                        contact_data[field] = href.replace('tel:', '')
                                        break
                            
                            # Fallback to text content
                            text = await element.text_content()
                            if text and text.strip():
                                if field == 'contact_email' and '@' in text:
                                    contact_data[field] = text.strip()
                                    break
                                elif field == 'contact_phone' and any(char.isdigit() for char in text):
                                    cleaned_phone = self._clean_phone_number(text)
                                    if self._validate_phone(cleaned_phone):
                                        contact_data[field] = cleaned_phone
                                        break
                                elif field == 'contact_person':
                                    person_name = self._extract_contact_person_from_text(text)
                                    if person_name:
                                        contact_data[field] = person_name
                                        break
                    except:
                        continue
            
            return contact_data
            
        except Exception as e:
            logger.debug(f"Error in enhanced contact extraction: {e}")
            return {}
    
    def _extract_contact_person_from_text(self, text: str) -> Optional[str]:
        """Extract contact person name from text - universal patterns"""
        if not text or len(text) > 500:  # Skip very long texts
            return None
        
        # Universal contact person patterns (German + English)
        patterns = [
            r'(?:Frau|Herr|Mr\.?|Ms\.?|Mrs\.?)\s+([A-Za-z\u00e4\u00f6\u00fc\u00df\u00c4\u00d6\u00dc\s]{3,40})',
            r'(?:Ansprechpartner[in]*|Contact Person|Recruiter):\s*([A-Za-z\u00e4\u00f6\u00fc\u00df\u00c4\u00d6\u00dc\s]{3,40})',
            r'(?:Kontakt|Contact):\s*([A-Za-z\u00e4\u00f6\u00fc\u00df\u00c4\u00d6\u00dc\s]{3,40})',
            r'(?:HR Manager|Personalreferent[in]*|Recruiter):\s*([A-Za-z\u00e4\u00f6\u00fc\u00df\u00c4\u00d6\u00dc\s]{3,40})',
            r'([A-Za-z\u00e4\u00f6\u00fc\u00df\u00c4\u00d6\u00dc]+\s+[A-Za-z\u00e4\u00f6\u00fc\u00df\u00c4\u00d6\u00dc]+)(?:\s+\+|\s+0|\s+\(\d|\s*$)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                name = match.group(1).strip()
                # Filter out common false positives
                if (len(name) >= 3 and len(name) <= 50 and 
                    not any(word in name.lower() for word in [
                        'gmbh', 'ag', 'ltd', 'inc', 'co.', 'kg', 'ohg',
                        'stra\u00dfe', 'platz', 'alle', 'ring', 'weg',
                        'position', 'job-id', 'vollzeit', 'stelle', 'jobs',
                        'email', 'telefon', 'phone', 'mail', 'www',
                        'deutschland', 'germany', 'austria', 'schweiz'
                    ])):
                    return name
        
        return None
    
    def get_statistics(self) -> Dict:
        """Get handler statistics"""
        return {
            'partner_sites_supported': len(self.partner_sites),
            'cache_size': len(self.partner_cache),
            'detection_methods': len(self.external_selectors),
            'supported_partners': list(self.partner_sites.keys())
        }


# Utility functions for integration
def is_external_partner_url(url: str) -> bool:
    """Check if URL is from a known job partner site"""
    handler = ExternalLinkHandler()
    domain = handler._get_domain_from_url(url)
    return any(partner in domain for partner in handler.partner_sites.keys())

def get_partner_info(url: str) -> Dict:
    """Get partner information from URL"""
    handler = ExternalLinkHandler()
    return handler._identify_partner(url)