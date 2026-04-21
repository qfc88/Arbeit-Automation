#!/usr/bin/env python3
"""
Enhanced Job Scraper V2 - Comprehensive Integration
Scrape → Enhanced Validation → Complete Cleaning → Single DB Load

Key Features:
- Comprehensive data validation before any storage
- Enhanced data cleaning and normalization
- Single database load (no duplicates)
- Complete data integrity
- Fail-safe error handling
"""

import asyncio
import logging
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import hashlib
import re

# Import base scraper
from .job_scraper_v1 import JobScraper as JobScraperV1

# Import enhanced components
try:
    from database.data_loader import JobDataLoader
    from utils.data_validator import DataValidator
    from models.job_model import JobModel, ValidationResult
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False
    logging.warning("Enhanced database components not available")

logger = logging.getLogger(__name__)

class JobScraper(JobScraperV1):
    """Enhanced Job Scraper with comprehensive validation and cleaning"""
    
    def __init__(self, auto_solve_captcha=True, enable_comprehensive_validation=True, 
                 enable_enhanced_cleaning=True, enable_single_db_load=True, 
                 enable_realtime_enhancement=True, **kwargs):
        """Initialize V2 scraper with enhanced features"""
        super().__init__(auto_solve_captcha=auto_solve_captcha, **kwargs)
        
        # V2 specific settings
        self.enable_comprehensive_validation = enable_comprehensive_validation
        self.enable_enhanced_cleaning = enable_enhanced_cleaning
        self.enable_single_db_load = enable_single_db_load
        self.enable_realtime_enhancement = enable_realtime_enhancement
        
        # V2 statistics
        self.v2_stats = {
            'scraped_count': 0,
            'cleaned_count': 0,
            'loaded_count': 0,
            'validation_failures': 0,
            'cleaning_failures': 0,
            'database_failures': 0,
            'realtime_enhancements': 0,
            'enhancement_successes': 0,
            'enhancement_failures': 0,
            'data_quality_score': 0.0
        }
        
        # Initialize enhanced components
        if DATABASE_AVAILABLE and enable_single_db_load:
            self.db_loader = JobDataLoader()
        else:
            self.db_loader = None
            
        self.data_validator = DataValidator() if DATABASE_AVAILABLE else None
        
        # Initialize contact scraper for realtime enhancement
        if enable_realtime_enhancement:
            try:
                from scrapers.contact_scraper import ContactScraper
                self.contact_scraper = None  # Will be initialized when needed
                self.contact_scraper_available = True
            except ImportError:
                logger.warning("ContactScraper not available for realtime enhancement")
                self.contact_scraper = None
                self.contact_scraper_available = False
        else:
            self.contact_scraper = None
            self.contact_scraper_available = False
        
        # Enhanced validation rules
        self.validation_rules = {
            'required_fields': ['ref_nr', 'profession', 'company_name'],
            'min_completeness': 0.7,  # 70% field completion required
            'email_validation': True,
            'phone_validation': True,
            'date_validation': True,
            'url_validation': True
        }
        
        # Enhanced cleaning rules
        self.cleaning_rules = {
            'normalize_whitespace': True,
            'clean_special_chars': True,
            'validate_emails': True,
            'validate_phones': True,
            'normalize_dates': True,
            'clean_company_names': True,
            'extract_skills': True,
            'normalize_locations': True
        }
    
    async def comprehensive_validate_job(self, job_data: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
        """Comprehensive job validation with detailed error reporting"""
        errors = []
        enhanced_data = job_data.copy()
        
        try:
            # 1. Required fields validation
            for field in self.validation_rules['required_fields']:
                if not job_data.get(field) or str(job_data.get(field)).strip() == '':
                    errors.append(f"Missing required field: {field}")
            
            # 2. Data completeness check
            non_empty_fields = sum(1 for v in job_data.values() if v and str(v).strip())
            total_fields = len(job_data)
            completeness = non_empty_fields / total_fields if total_fields > 0 else 0
            
            if completeness < self.validation_rules['min_completeness']:
                errors.append(f"Data completeness {completeness:.1%} below required {self.validation_rules['min_completeness']:.1%}")
            
            enhanced_data['data_completeness'] = completeness
            
            # 3. Email validation
            if self.validation_rules['email_validation'] and job_data.get('email'):
                email = str(job_data['email']).strip()
                if email and not self._validate_email(email):
                    errors.append(f"Invalid email format: {email[:50]}...")
            
            # 4. Phone validation
            if self.validation_rules['phone_validation'] and job_data.get('phone'):
                phone = str(job_data['phone']).strip()
                if phone and not self._validate_phone(phone):
                    errors.append(f"Invalid phone format: {phone}")
            
            # 5. Date validation
            if self.validation_rules['date_validation']:
                for date_field in ['start_date', 'application_deadline', 'posted_date']:
                    if job_data.get(date_field):
                        if not self._validate_date_field(job_data[date_field]):
                            errors.append(f"Invalid date format in {date_field}")
            
            # 6. URL validation
            if self.validation_rules['url_validation']:
                for url_field in ['job_url', 'company_website']:
                    if job_data.get(url_field):
                        if not self._validate_url(job_data[url_field]):
                            errors.append(f"Invalid URL format in {url_field}")
            
            # 7. Business logic validation
            ref_nr = job_data.get('ref_nr')
            if ref_nr and not str(ref_nr).strip():
                errors.append("Empty reference number")
            
            company_name = job_data.get('company_name')
            if company_name and len(str(company_name).strip()) < 2:
                errors.append("Company name too short")
            
            profession = job_data.get('profession')
            if profession and len(str(profession).strip()) < 3:
                errors.append("Profession description too short")
            
            # Calculate validation score
            validation_score = max(0, 1 - (len(errors) / 10))  # Normalize to 0-1
            enhanced_data['validation_score'] = validation_score
            
            is_valid = len(errors) == 0
            
            return is_valid, errors, enhanced_data
            
        except Exception as e:
            logger.error(f"Error in comprehensive validation: {e}")
            errors.append(f"Validation system error: {str(e)}")
            return False, errors, enhanced_data
    
    async def enhanced_clean_job(self, job_data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Enhanced data cleaning and normalization"""
        try:
            cleaned_data = job_data.copy()
            
            # 1. Normalize whitespace
            if self.cleaning_rules['normalize_whitespace']:
                for key, value in cleaned_data.items():
                    if isinstance(value, str):
                        cleaned_data[key] = ' '.join(value.split())
            
            # 2. Clean special characters
            if self.cleaning_rules['clean_special_chars']:
                for key in ['profession', 'company_name', 'description']:
                    if cleaned_data.get(key):
                        cleaned_data[key] = self._clean_special_chars(str(cleaned_data[key]))
            
            # 3. Enhanced email cleaning
            if self.cleaning_rules['validate_emails'] and cleaned_data.get('email'):
                cleaned_email = self._clean_email_advanced(str(cleaned_data['email']))
                cleaned_data['email'] = cleaned_email if cleaned_email else None
            
            # 4. Enhanced phone cleaning
            if self.cleaning_rules['validate_phones'] and cleaned_data.get('phone'):
                cleaned_phone = self._clean_phone_advanced(str(cleaned_data['phone']))
                cleaned_data['phone'] = cleaned_phone if cleaned_phone else None
            
            # 5. Date normalization
            if self.cleaning_rules['normalize_dates']:
                for date_field in ['start_date', 'application_deadline', 'posted_date']:
                    if cleaned_data.get(date_field):
                        normalized_date = self._normalize_date(cleaned_data[date_field])
                        if normalized_date:
                            cleaned_data[f"{date_field}_parsed"] = normalized_date
            
            # 6. Company name cleaning
            if self.cleaning_rules['clean_company_names'] and cleaned_data.get('company_name'):
                cleaned_data['company_name'] = self._clean_company_name(str(cleaned_data['company_name']))
            
            # 7. Skills extraction
            if self.cleaning_rules['extract_skills'] and cleaned_data.get('description'):
                skills = self._extract_skills(str(cleaned_data['description']))
                if skills:
                    cleaned_data['extracted_skills'] = skills
            
            # 8. Location normalization
            if self.cleaning_rules['normalize_locations'] and cleaned_data.get('location'):
                normalized_location = self._normalize_location(str(cleaned_data['location']))
                if normalized_location:
                    cleaned_data['location_normalized'] = normalized_location
            
            # Add cleaning metadata
            cleaned_data['cleaned_at'] = datetime.now().isoformat()
            cleaned_data['cleaning_version'] = 'v2.0'
            
            return True, cleaned_data
            
        except Exception as e:
            logger.error(f"Error in enhanced cleaning: {e}")
            return False, job_data
    
    async def realtime_contact_enhancement(self, job_data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Realtime contact enhancement for jobs missing email/phone"""
        try:
            # Check if enhancement is needed
            has_email = job_data.get('email') and str(job_data.get('email')).strip()
            has_phone = job_data.get('phone') and str(job_data.get('phone')).strip()
            
            if has_email and has_phone:
                return True, job_data  # No enhancement needed
            
            # Check if we have company info for enhancement
            company_name = job_data.get('company_name')
            company_website = job_data.get('company_website')
            
            if not company_name and not company_website:
                logger.info(f"No company info for enhancement: {job_data.get('ref_nr', 'unknown')}")
                return True, job_data  # Skip enhancement but continue
            
            self.v2_stats['realtime_enhancements'] += 1
            
            logger.info(f"[ENHANCE] Realtime enhancement for {job_data.get('ref_nr', 'unknown')}: missing {'email' if not has_email else ''}{'&' if not has_email and not has_phone else ''}{'phone' if not has_phone else ''}")
            
            # Initialize contact scraper if needed
            if not self.contact_scraper and self.contact_scraper_available:
                try:
                    from scrapers.contact_scraper import ContactScraper
                    # Use current browser context if available
                    if hasattr(self, 'context') and self.context:
                        self.contact_scraper = ContactScraper(context=self.context)
                    else:
                        # Will create its own browser context
                        self.contact_scraper = ContactScraper()
                except Exception as e:
                    logger.error(f"Failed to initialize contact scraper: {e}")
                    self.contact_scraper_available = False
                    return True, job_data
            
            if not self.contact_scraper_available:
                return True, job_data
            
            # Prepare job for contact enhancement
            enhancement_job = {
                'ref_nr': job_data.get('ref_nr'),
                'company_name': company_name,
                'company_website': company_website,
                'job_url': job_data.get('job_url'),
                'current_email': job_data.get('email'),
                'current_phone': job_data.get('phone')
            }
            
            # Perform contact enhancement with timeout
            try:
                enhanced_contact = await asyncio.wait_for(
                    self.contact_scraper.enhance_single_job_contact(enhancement_job),
                    timeout=30  # 30 second timeout per job
                )
                
                if enhanced_contact:
                    # Update job with enhanced contacts
                    if enhanced_contact.get('email') and not has_email:
                        job_data['email'] = enhanced_contact['email']
                        job_data['email_source'] = 'realtime_enhancement'
                        logger.info(f"[SUCCESS] Enhanced email: {job_data.get('ref_nr')} → {enhanced_contact['email']}")
                    
                    if enhanced_contact.get('phone') and not has_phone:
                        job_data['phone'] = enhanced_contact['phone']
                        job_data['phone_source'] = 'realtime_enhancement'
                        logger.info(f"[SUCCESS] Enhanced phone: {job_data.get('ref_nr')} → {enhanced_contact['phone']}")
                    
                    # Add enhancement metadata
                    job_data['realtime_enhanced'] = True
                    job_data['enhanced_at'] = datetime.now().isoformat()
                    
                    self.v2_stats['enhancement_successes'] += 1
                    return True, job_data
                else:
                    logger.info(f"[WARNING] No additional contacts found: {job_data.get('ref_nr')}")
                    self.v2_stats['enhancement_failures'] += 1
                    return True, job_data  # Continue even if enhancement failed
            
            except asyncio.TimeoutError:
                logger.warning(f"[TIMEOUT] Enhancement timeout: {job_data.get('ref_nr')}")
                self.v2_stats['enhancement_failures'] += 1
                return True, job_data
            
            except Exception as e:
                logger.error(f"[ERROR] Enhancement error for {job_data.get('ref_nr')}: {e}")
                self.v2_stats['enhancement_failures'] += 1
                return True, job_data  # Continue even if enhancement failed
            
        except Exception as e:
            logger.error(f"Error in realtime contact enhancement: {e}")
            self.v2_stats['enhancement_failures'] += 1
            return True, job_data  # Continue even if enhancement system failed
    
    async def save_progress_v2(self, scraped_jobs: List[Dict], batch_number: int = None):
        """V2 Save progress with comprehensive validation, cleaning, and single DB load"""
        try:
            processed_jobs = []
            
            for job_data in scraped_jobs:
                self.v2_stats['scraped_count'] += 1
                
                # Step 1: Comprehensive validation
                if self.enable_comprehensive_validation:
                    is_valid, errors, enhanced_data = await self.comprehensive_validate_job(job_data)
                    
                    if not is_valid:
                        self.v2_stats['validation_failures'] += 1
                        logger.warning(f"Validation failed for {job_data.get('ref_nr', 'unknown')}: {errors}")
                        continue  # Skip invalid jobs
                    
                    job_data = enhanced_data
                
                # Step 2: Enhanced cleaning
                if self.enable_enhanced_cleaning:
                    cleaned_success, cleaned_data = await self.enhanced_clean_job(job_data)
                    
                    if not cleaned_success:
                        self.v2_stats['cleaning_failures'] += 1
                        logger.warning(f"Cleaning failed for {job_data.get('ref_nr', 'unknown')}")
                        continue  # Skip failed cleaning
                    
                    job_data = cleaned_data
                    self.v2_stats['cleaned_count'] += 1
                
                # Step 2.5: Realtime contact enhancement (if missing contact info)
                if self.enable_realtime_enhancement:
                    enhanced_success, enhanced_data = await self.realtime_contact_enhancement(job_data)
                    
                    if enhanced_success:
                        job_data = enhanced_data
                    else:
                        logger.warning(f"Realtime enhancement failed for {job_data.get('ref_nr', 'unknown')}")
                
                # Step 3: Single database load
                if self.enable_single_db_load and self.db_loader:
                    try:
                        result = await self.db_loader.load_single_job(job_data)
                        if result and result.get('loaded', 0) > 0:
                            self.v2_stats['loaded_count'] += 1
                            logger.info(f"[DATABASE] {job_data.get('ref_nr', 'unknown')} loaded to database")
                        else:
                            self.v2_stats['database_failures'] += 1
                            logger.warning(f"[ERROR] Database load failed: {job_data.get('ref_nr', 'unknown')}")
                            
                    except Exception as e:
                        self.v2_stats['database_failures'] += 1
                        logger.error(f"Database error for {job_data.get('ref_nr', 'unknown')}: {e}")
                
                processed_jobs.append(job_data)
            
            # Still save to files as backup (but not the primary method)
            if processed_jobs:
                await super().save_progress(processed_jobs, batch_number)
                
            # Calculate data quality score
            if self.v2_stats['scraped_count'] > 0:
                quality_score = (self.v2_stats['loaded_count'] / self.v2_stats['scraped_count'])
                self.v2_stats['data_quality_score'] = quality_score
            
            logger.info(f"[V2] Batch processed: {len(processed_jobs)} jobs")
            logger.info(f"   [DATABASE] Loaded to DB: {self.v2_stats['loaded_count']}")
            logger.info(f"   [ENHANCE] Realtime enhancements: {self.v2_stats['realtime_enhancements']}")
            logger.info(f"   [SUCCESS] Enhancement successes: {self.v2_stats['enhancement_successes']}")
            logger.info(f"   [QUALITY] Quality score: {self.v2_stats['data_quality_score']:.1%}")
            
        except Exception as e:
            logger.error(f"Error in V2 save progress: {e}")
            raise
    
    async def run_enhanced(self, input_csv_path: str, resume: bool = False, 
                          auto_solve_captcha: bool = True) -> Dict[str, Any]:
        """Run enhanced V2 scraping with integrated validation, cleaning, and DB loading"""
        try:
            logger.info("[START] Starting V2 enhanced scraping...")
            
            # Override the save_progress method to use V2
            original_save_progress = self.save_progress
            self.save_progress = self.save_progress_v2
            
            # Run base scraping
            await self.run(
                input_csv_path=input_csv_path,
                resume=resume,
                auto_solve_captcha=auto_solve_captcha
            )
            
            # Restore original method
            self.save_progress = original_save_progress
            
            logger.info("[COMPLETE] V2 Enhanced scraping completed!")
            return self.v2_stats
            
        except Exception as e:
            logger.error(f"Error in V2 enhanced run: {e}")
            return self.v2_stats
    
    def _validate_email(self, email: str) -> bool:
        """Enhanced email validation"""
        if not email or email.strip() == '':
            return False
            
        # Remove common issues
        email = email.strip().lower()
        
        # Skip URLs masquerading as emails
        if email.startswith('http') or email.startswith('?body='):
            return False
            
        # Basic email regex
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(email_pattern, email) is not None
    
    def _validate_phone(self, phone: str) -> bool:
        """Enhanced phone validation"""
        if not phone or phone.strip() == '':
            return False
            
        # Clean phone number
        cleaned_phone = re.sub(r'[^\d+()-\s]', '', phone.strip())
        
        # German phone number patterns
        phone_patterns = [
            r'^\+49[\d\s()-]{8,15}$',  # International
            r'^0[\d\s()-]{8,15}$',     # National
            r'^[\d\s()-]{7,15}$'       # Local
        ]
        
        return any(re.match(pattern, cleaned_phone) for pattern in phone_patterns)
    
    def _validate_date_field(self, date_value: Any) -> bool:
        """Validate date field"""
        if not date_value:
            return True  # Empty is OK
            
        # Add date validation logic here
        return True
    
    def _validate_url(self, url: str) -> bool:
        """Validate URL format"""
        if not url or url.strip() == '':
            return True  # Empty is OK
            
        url_pattern = r'^https?://[^\s]+\.[^\s]+'
        return re.match(url_pattern, url.strip()) is not None
    
    def _clean_special_chars(self, text: str) -> str:
        """Clean special characters from text"""
        # Remove excessive whitespace and special chars
        cleaned = re.sub(r'[^\w\s.,-]', ' ', text)
        return ' '.join(cleaned.split())
    
    def _clean_email_advanced(self, email: str) -> Optional[str]:
        """Advanced email cleaning"""
        if not email:
            return None
            
        email = email.strip().lower()
        
        # Remove URL parameters
        if '?body=' in email or 'azubi.de' in email or email.startswith('http'):
            return None
            
        if self._validate_email(email):
            return email
        
        return None
    
    def _clean_phone_advanced(self, phone: str) -> Optional[str]:
        """Advanced phone cleaning"""
        if not phone:
            return None
            
        # Clean and validate
        cleaned_phone = re.sub(r'[^\d+()-\s]', '', phone.strip())
        
        if self._validate_phone(cleaned_phone):
            return cleaned_phone
        
        return None
    
    def _normalize_date(self, date_value: Any) -> Optional[str]:
        """Normalize date to standard format"""
        # Add date normalization logic here
        return None
    
    def _clean_company_name(self, company_name: str) -> str:
        """Clean and normalize company name"""
        # Remove common suffixes and clean up
        cleaned = company_name.strip()
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return cleaned
    
    def _extract_skills(self, description: str) -> List[str]:
        """Extract skills from job description"""
        # Simple skill extraction - can be enhanced
        common_skills = [
            'python', 'java', 'javascript', 'sql', 'html', 'css',
            'react', 'angular', 'vue', 'node.js', 'docker', 'kubernetes'
        ]
        
        description_lower = description.lower()
        found_skills = [skill for skill in common_skills if skill in description_lower]
        
        return found_skills
    
    def _normalize_location(self, location: str) -> Dict[str, str]:
        """Normalize location information"""
        # Simple location parsing - can be enhanced
        return {
            'original': location,
            'normalized': location.strip()
        }