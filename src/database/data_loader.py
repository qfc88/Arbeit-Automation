"""
Data loader for job scraper database
Handles loading scraped job data from JSON/CSV files into PostgreSQL database
Includes bulk insert operations, duplicate handling, and data transformation
"""

import asyncio
import json
import pandas as pd
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import hashlib
from datetime import datetime
import uuid
import sys
import re

# Add parent directories to path for imports
sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent.parent / "config"))

try:
    from .connection import db_manager, init_database, close_database
    # Try to import from config package
    sys.path.append(str(Path(__file__).parent.parent / "config"))
    from settings import DATABASE_SETTINGS, VALIDATION_SETTINGS, DATA_CLEANING_SETTINGS
except ImportError:
    try:
        # Fallback: try direct import from config directory
        from config.settings import DATABASE_SETTINGS, VALIDATION_SETTINGS, DATA_CLEANING_SETTINGS
    except ImportError as e:
        raise ImportError(
            f"[ERROR] Settings import failed: {e}\n"
            "Please ensure src/config/settings.py exists and contains: "
            "DATABASE_SETTINGS, VALIDATION_SETTINGS, DATA_CLEANING_SETTINGS"
        )

logger = logging.getLogger(__name__)

class JobDataLoader:
    def __init__(self):
        """Initialize job data loader with enhanced settings"""
        self.db_manager = db_manager
        
        # Configuration from settings
        self.batch_size = DATABASE_SETTINGS.get('batch_size', 100)
        self.duplicate_strategy = 'skip'  # skip, update, error
        self.validate_on_load = VALIDATION_SETTINGS.get('validate_on_scrape', True)
        self.clean_data_on_load = DATA_CLEANING_SETTINGS.get('clean_data_on_save', True)
        
        # Data cleaning settings
        self.normalize_companies = DATA_CLEANING_SETTINGS.get('normalize_company_names', True)
        self.clean_phones = DATA_CLEANING_SETTINGS.get('clean_phone_numbers', True)
        self.validate_emails = DATA_CLEANING_SETTINGS.get('validate_email_format', True)
        self.parse_german_dates = DATA_CLEANING_SETTINGS.get('parse_german_dates', True)
        self.remove_html = DATA_CLEANING_SETTINGS.get('remove_html_tags', True)
        self.trim_whitespace = DATA_CLEANING_SETTINGS.get('trim_whitespace', True)
        
        # Quality thresholds
        self.min_quality_score = VALIDATION_SETTINGS.get('min_quality_score', 3.0)
        self.min_completeness = VALIDATION_SETTINGS.get('min_completeness_score', 0.3)
        
        # Statistics
        self.stats = {
            'total_processed': 0,
            'inserted': 0,
            'duplicates_found': 0,
            'errors': 0,
            'companies_created': 0,
            'validation_failures': 0,
            'data_cleaned': 0
        }
        
        logger.info("JobDataLoader initialized with enhanced settings")
        logger.info(f"Validation enabled: {self.validate_on_load}, Data cleaning: {self.clean_data_on_load}")
        logger.info(f"Quality thresholds - Score: {self.min_quality_score}, Completeness: {self.min_completeness}")
    
    def generate_content_hash(self, job_data: Dict[str, Any]) -> str:
        """Generate content hash for duplicate detection"""
        # Create hash from key fields to identify duplicates
        content_fields = [
            str(job_data.get('profession', '')),
            str(job_data.get('company_name', '')),
            str(job_data.get('location', '')),
            str(job_data.get('ref_nr', '')),
            str(job_data.get('source_url', ''))
        ]
        
        content_string = '|'.join(content_fields).lower()
        return hashlib.sha256(content_string.encode()).hexdigest()
    
    def normalize_company_name(self, company_name: str) -> str:
        """Normalize company name for deduplication"""
        if not company_name:
            return ""
        
        if not self.normalize_companies:
            return company_name.strip()
        
        # Remove common prefixes and standardize
        normalized = company_name.strip()
        normalized = re.sub(r'^Arbeitgeber:\s*', '', normalized, flags=re.IGNORECASE)
        
        if self.trim_whitespace:
            normalized = re.sub(r'\s+', ' ', normalized)  # Multiple spaces to single
        
        normalized = normalized.lower()
        
        return normalized
    
    def clean_phone_number(self, phone: str) -> Optional[str]:
        """Clean and validate phone number"""
        if not phone:
            return None
        
        if not self.clean_phones:
            return phone.strip()
        
        # Remove common formatting
        cleaned = re.sub(r'[^\d+\(\)\-\s]', '', phone.strip())
        
        # Validate German phone number pattern
        if re.match(r'^\+49\(?\d+\)?\s*\d+[-\s]?\d+', cleaned) or \
           re.match(r'^0\d+\s*\d+[-\s]?\d+', cleaned):
            return cleaned
        
        return cleaned if len(cleaned) >= 6 else None
    
    def clean_email(self, email: str) -> Optional[str]:
        """Clean and validate email address"""
        if not email:
            return None
        
        email = email.strip()
        
        # Filter out URL parameters, links, and malformed entries
        if (email.startswith('?body=') or 
            email.startswith('http') or 
            email.startswith('mailto:') or
            'azubi.de' in email or
            len(email) > 100):  # Reasonable email length limit
            logger.warning(f"Filtered out invalid email format: {email[:50]}...")
            return None
        
        email = email.lower()
        
        if not self.validate_emails:
            return email
        
        # Enhanced email validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if re.match(email_pattern, email):
            # Additional checks for common issues
            if email.count('@') != 1:
                logger.warning(f"Invalid email format (multiple @): {email}")
                return None
            if email.startswith('.') or email.endswith('.'):
                logger.warning(f"Invalid email format (starts/ends with dot): {email}")
                return None
            if '..' in email:
                logger.warning(f"Invalid email format (double dots): {email}")
                return None
            return email
        
        logger.warning(f"Invalid email format: {email}")
        return None
    
    def parse_date_string(self, date_str: str) -> Optional[str]:
        """Parse various German date formats"""
        if not date_str:
            return None
        
        if not self.parse_german_dates:
            return date_str
        
        # Common German date patterns
        date_patterns = [
            (r'(\d{1,2})\.(\d{1,2})\.(\d{4})', r'\3-\2-\1'),  # DD.MM.YYYY
            (r'(\d{4})-(\d{1,2})-(\d{1,2})', r'\1-\2-\3'),   # YYYY-MM-DD
            (r'ab\s+(\d{1,2})\.(\d{1,2})\.(\d{4})', r'\3-\2-\1'),  # ab DD.MM.YYYY
            (r'Beginn ab\s+(\d{1,2})\.(\d{1,2})\.(\d{4})', r'\3-\2-\1')  # Beginn ab DD.MM.YYYY
        ]
        
        for pattern, replacement in date_patterns:
            match = re.search(pattern, date_str)
            if match:
                try:
                    parsed_date = re.sub(pattern, replacement, date_str)
                    logger.debug(f"Parsed German date: {date_str} -> {parsed_date}")
                    return parsed_date
                except:
                    continue
        
        return date_str  # Return original if no pattern matches
    
    async def find_or_create_company(self, company_name: str, location: str = None) -> Optional[uuid.UUID]:
        """Find existing company or create new one"""
        if not company_name:
            return None
        
        try:
            normalized_name = self.normalize_company_name(company_name)
            
            # Try to find existing company
            existing_company = await self.db_manager.execute_single(
                "SELECT id FROM companies WHERE normalized_name = $1",
                normalized_name
            )
            
            if existing_company:
                return existing_company['id']
            
            # Create new company
            company_id = uuid.uuid4()
            await self.db_manager.execute_command(
                """
                INSERT INTO companies (id, name, normalized_name, location)
                VALUES ($1, $2, $3, $4)
                """,
                company_id, company_name, normalized_name, location
            )
            
            self.stats['companies_created'] += 1
            logger.debug(f"Created new company: {company_name}")
            return company_id
            
        except Exception as e:
            logger.error(f"Error creating company {company_name}: {e}")
            return None
    
    async def check_duplicate_job(self, content_hash: str, ref_nr: str, source_url: str) -> Optional[uuid.UUID]:
        """Check if job already exists in database"""
        try:
            # Check by content hash first
            if content_hash:
                existing = await self.db_manager.execute_single(
                    "SELECT id FROM jobs WHERE content_hash = $1",
                    content_hash
                )
                if existing:
                    return existing['id']
            
            # Check by ref_nr
            if ref_nr:
                existing = await self.db_manager.execute_single(
                    "SELECT id FROM jobs WHERE ref_nr = $1",
                    ref_nr
                )
                if existing:
                    return existing['id']
            
            # Check by source_url
            if source_url:
                existing = await self.db_manager.execute_single(
                    "SELECT id FROM jobs WHERE source_url = $1",
                    source_url
                )
                if existing:
                    return existing['id']
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking duplicates: {e}")
            return None
    
    def clean_html_content(self, text: str) -> str:
        """Remove HTML tags from text content"""
        if not text or not self.remove_html:
            return text
        
        # Remove HTML tags
        cleaned = re.sub(r'<[^>]+>', '', text)
        # Decode HTML entities
        cleaned = re.sub(r'&[a-zA-Z]+;', ' ', cleaned)
        # Clean up whitespace
        if self.trim_whitespace:
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned
    
    def transform_job_data(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        """Transform raw scraped data to database format with enhanced cleaning"""
        # Generate content hash
        content_hash = self.generate_content_hash(raw_job)
        
        # Clean text fields
        def clean_text_field(field_name: str) -> Optional[str]:
            value = raw_job.get(field_name, '')
            if not value:
                return None
            
            # Convert to string and clean
            text = str(value).strip()
            if self.remove_html:
                text = self.clean_html_content(text)
            if self.trim_whitespace:
                text = re.sub(r'\s+', ' ', text).strip()
            
            return text if text else None
        
        # Transform with enhanced cleaning
        transformed = {
            'id': uuid.uuid4(),
            'profession': clean_text_field('profession'),
            'salary': clean_text_field('salary'),
            'company_name': clean_text_field('company_name'),
            'location': clean_text_field('location'),
            'start_date': self.parse_date_string(raw_job.get('start_date', '')),
            'telephone': self.clean_phone_number(raw_job.get('telephone', '')),
            'email': self.clean_email(raw_job.get('email', '')),
            'job_description': clean_text_field('job_description'),
            'ref_nr': clean_text_field('ref_nr'),
            'external_link': clean_text_field('external_link'),
            'application_link': clean_text_field('application_link'),
            
            # Additional fields
            'job_type': clean_text_field('job_type'),
            'ausbildungsberuf': clean_text_field('ausbildungsberuf'),
            'application_method': clean_text_field('application_method'),
            'contact_person': clean_text_field('contact_person'),
            
            # Metadata
            'source_url': clean_text_field('source_url'),
            'scraped_at': raw_job.get('scraped_at', datetime.utcnow().isoformat()),
            'captcha_solved': raw_job.get('captcha_solved', False),
            'content_hash': content_hash,
            'status': 'active',
            'is_valid': True
        }
        
        # Convert scraped_at to proper timestamp
        if isinstance(transformed['scraped_at'], str):
            try:
                # Handle ISO format timestamps
                transformed['scraped_at'] = datetime.fromisoformat(
                    transformed['scraped_at'].replace('Z', '+00:00')
                )
            except:
                transformed['scraped_at'] = datetime.utcnow()
        
        # Calculate data quality score if validation is enabled
        if self.validate_on_load:
            quality_score = self._calculate_data_quality(transformed)
            completeness_score = self._calculate_completeness(transformed)
            
            transformed['data_quality_score'] = quality_score
            transformed['completeness_score'] = completeness_score
            
            # Mark as invalid if below quality thresholds
            if (quality_score < self.min_quality_score or 
                completeness_score < self.min_completeness):
                transformed['is_valid'] = False
                logger.debug(f"Job marked invalid: quality={quality_score}, completeness={completeness_score}")
        
        # Track cleaning statistics
        if self.clean_data_on_load:
            self.stats['data_cleaned'] += 1
        
        return transformed
    
    def _calculate_data_quality(self, job_data: Dict[str, Any]) -> float:
        """Calculate data quality score (0-11) based on field completeness and quality"""
        score = 0.0
        
        # Core required fields (weighted scoring)
        fields_with_weights = [
            ('profession', 1.0),
            ('salary', 0.5),  # Often missing in German job postings
            ('company_name', 1.0),
            ('location', 1.0),
            ('start_date', 0.8),
            ('telephone', 1.0),
            ('email', 1.0),
            ('job_description', 1.0),
            ('ref_nr', 0.8),
            ('external_link', 0.5),
            ('application_link', 0.7)
        ]
        
        for field_name, weight in fields_with_weights:
            field_value = job_data.get(field_name)
            if field_value and str(field_value).strip():
                field_score = weight
                
                # Quality bonuses
                field_str = str(field_value).strip()
                
                # Bonus for longer content (description)
                if field_name == 'job_description' and len(field_str) > 100:
                    field_score += 0.2
                
                # Penalty for very short important fields
                if field_name in ['profession', 'company_name'] and len(field_str) < 5:
                    field_score *= 0.5
                
                score += field_score
        
        return min(score, 11.0)
    
    def _calculate_completeness(self, job_data: Dict[str, Any]) -> float:
        """Calculate completeness score (0-1) based on required fields"""
        required_fields = [
            'profession', 'salary', 'company_name', 'location',
            'start_date', 'telephone', 'email', 'job_description',
            'ref_nr', 'external_link', 'application_link'
        ]
        
        completed_fields = sum(
            1 for field in required_fields 
            if job_data.get(field) and str(job_data.get(field)).strip()
        )
        
        return completed_fields / len(required_fields)
    
    async def insert_job_batch(self, jobs: List[Dict[str, Any]]) -> Tuple[int, int]:
        """Insert batch of jobs into database"""
        inserted_count = 0
        duplicate_count = 0
        
        try:
            async with self.db_manager.get_transaction() as conn:
                for job_data in jobs:
                    try:
                        # Skip invalid jobs if validation is enabled
                        if self.validate_on_load and not job_data.get('is_valid', True):
                            self.stats['validation_failures'] += 1
                            logger.debug(f"Skipping invalid job: {job_data.get('ref_nr', 'no-ref')}")
                            continue
                        
                        # Check for duplicates
                        existing_id = await self.check_duplicate_job(
                            job_data['content_hash'],
                            job_data['ref_nr'],
                            job_data['source_url']
                        )
                        
                        if existing_id:
                            duplicate_count += 1
                            logger.debug(f"Duplicate job found: {job_data.get('ref_nr', 'no-ref')}")
                            continue
                        
                        # Find or create company
                        company_id = await self.find_or_create_company(
                            job_data['company_name'],
                            job_data['location']
                        )
                        job_data['company_id'] = company_id
                        
                        # Insert job
                        await conn.execute(
                            """
                            INSERT INTO jobs (
                                id, company_id, profession, salary, company_name, location,
                                start_date, telephone, email, job_description, ref_nr,
                                external_link, application_link, job_type, ausbildungsberuf,
                                application_method, contact_person, source_url, scraped_at,
                                captcha_solved, content_hash, status, is_valid
                            ) VALUES (
                                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13,
                                $14, $15, $16, $17, $18, $19, $20, $21, $22, $23
                            )
                            """,
                            job_data['id'], job_data['company_id'], job_data['profession'],
                            job_data['salary'], job_data['company_name'], job_data['location'],
                            job_data['start_date'], job_data['telephone'], job_data['email'],
                            job_data['job_description'], job_data['ref_nr'], job_data['external_link'],
                            job_data['application_link'], job_data['job_type'], job_data['ausbildungsberuf'],
                            job_data['application_method'], job_data['contact_person'],
                            job_data['source_url'], job_data['scraped_at'], job_data['captcha_solved'],
                            job_data['content_hash'], job_data['status'], job_data['is_valid']
                        )
                        
                        inserted_count += 1
                        logger.debug(f"Inserted job: {job_data.get('profession', 'no-title')} at {job_data.get('company_name', 'no-company')}")
                        
                    except Exception as e:
                        logger.error(f"Error inserting job: {e}")
                        logger.error(f"Job data: {job_data.get('ref_nr', 'no-ref')}")
                        logger.error(f"Job ID: {job_data.get('id', 'no-id')}")
                        logger.error(f"Company ID: {job_data.get('company_id', 'no-company-id')}")
                        logger.error(f"Status: {job_data.get('status', 'no-status')}")
                        logger.error(f"Is Valid: {job_data.get('is_valid', 'no-valid-flag')}")
                        # Log the actual SQL values for debugging
                        logger.debug(f"Full job data keys: {list(job_data.keys())}")
                        self.stats['errors'] += 1
                        continue
                        
        except Exception as e:
            logger.error(f"Batch insert transaction failed: {e}")
            raise
        
        return inserted_count, duplicate_count
    
    async def load_single_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Load a single job into database realtime"""
        try:
            # Ensure database connection
            if not self.db_manager.is_connected:
                logger.info("Database not connected, connecting...")
                connected = await self.db_manager.connect()
                if not connected:
                    logger.error("Failed to connect to database")
                    return {'loaded': 0, 'error': 'Database connection failed'}
            
            # Process single job as list
            result = await self.process_job_data([job_data], source_file="realtime")
            return {'loaded': 1 if result else 0, 'job_id': job_data.get('ref_nr', 'unknown')}
        except Exception as e:
            logger.error(f"Error loading single job: {e}")
            return {'loaded': 0, 'error': str(e)}

    async def load_from_json_file(self, file_path: str) -> bool:
        """Load job data from JSON file"""
        try:
            logger.info(f"Loading data from JSON file: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_jobs = json.load(f)
            
            if not isinstance(raw_jobs, list):
                logger.error(f"JSON file must contain a list of jobs")
                return False
            
            return await self.process_job_data(raw_jobs, source_file=file_path)
            
        except Exception as e:
            logger.error(f"Error loading JSON file {file_path}: {e}")
            return False
    
    async def load_from_csv_file(self, file_path: str) -> bool:
        """Load job data from CSV file"""
        try:
            logger.info(f"Loading data from CSV file: {file_path}")
            
            df = pd.read_csv(file_path)
            raw_jobs = df.to_dict('records')
            
            return await self.process_job_data(raw_jobs, source_file=file_path)
            
        except Exception as e:
            logger.error(f"Error loading CSV file {file_path}: {e}")
            return False
    
    async def process_job_data(self, raw_jobs: List[Dict[str, Any]], source_file: str = None) -> bool:
        """Process and load job data into database"""
        try:
            # Ensure database connection
            if not self.db_manager.is_connected:
                logger.info("Database not connected, connecting...")
                connected = await self.db_manager.connect()
                if not connected:
                    logger.error("Failed to connect to database")
                    return False
            
            total_jobs = len(raw_jobs)
            logger.info(f"Processing {total_jobs} jobs from {source_file or 'data'}")
            
            # Transform data
            transformed_jobs = []
            for raw_job in raw_jobs:
                try:
                    transformed_job = self.transform_job_data(raw_job)
                    transformed_jobs.append(transformed_job)
                except Exception as e:
                    logger.error(f"Error transforming job data: {e}")
                    self.stats['errors'] += 1
                    continue
            
            logger.info(f"Transformed {len(transformed_jobs)} jobs successfully")
            
            # Insert in batches
            total_inserted = 0
            total_duplicates = 0
            
            for i in range(0, len(transformed_jobs), self.batch_size):
                batch = transformed_jobs[i:i + self.batch_size]
                
                try:
                    inserted, duplicates = await self.insert_job_batch(batch)
                    total_inserted += inserted
                    total_duplicates += duplicates
                    
                    logger.info(f"Batch {i//self.batch_size + 1}: {inserted} inserted, {duplicates} duplicates")
                    
                except Exception as e:
                    logger.error(f"Batch insert failed: {e}")
                    self.stats['errors'] += len(batch)
                    continue
            
            # Update statistics
            self.stats['total_processed'] = len(transformed_jobs)
            self.stats['inserted'] = total_inserted
            self.stats['duplicates_found'] = total_duplicates
            
            logger.info(f"Data loading completed: {total_inserted} inserted, {total_duplicates} duplicates, {self.stats['errors']} errors")
            return True
            
        except Exception as e:
            logger.error(f"Error processing job data: {e}")
            return False
    
    async def load_batch_files(self, data_dir: str) -> bool:
        """Load all batch JSON files from data directory"""
        try:
            data_path = Path(data_dir)
            
            if not data_path.exists():
                logger.error(f"Data directory not found: {data_dir}")
                return False
            
            # Find all batch files
            batch_files = list(data_path.glob("scraped_jobs_batch_*.json"))
            
            if not batch_files:
                logger.warning(f"No batch files found in {data_dir}")
                return False
            
            logger.info(f"Found {len(batch_files)} batch files to process")
            
            success_count = 0
            for batch_file in sorted(batch_files):
                logger.info(f"Processing batch file: {batch_file.name}")
                
                if await self.load_from_json_file(str(batch_file)):
                    success_count += 1
                else:
                    logger.error(f"Failed to load batch file: {batch_file.name}")
            
            logger.info(f"Batch loading completed: {success_count}/{len(batch_files)} files processed successfully")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error loading batch files: {e}")
            return False
    
    async def create_scraping_session_record(self, session_name: str, config: Dict[str, Any] = None) -> uuid.UUID:
        """Create a record of the scraping session"""
        try:
            session_id = uuid.uuid4()
            
            await self.db_manager.execute_command(
                """
                INSERT INTO scraping_sessions (
                    id, session_name, status, scraper_config,
                    jobs_scraped, total_urls_processed
                ) VALUES ($1, $2, $3, $4, $5, $6)
                """,
                session_id, session_name, 'completed', 
                json.dumps(config or {}), self.stats['inserted'], self.stats['total_processed']
            )
            
            return session_id
            
        except Exception as e:
            logger.error(f"Error creating scraping session record: {e}")
            return None
    
    def get_loading_statistics(self) -> Dict[str, Any]:
        """Get enhanced statistics from the loading process"""
        total_processed = max(self.stats['total_processed'], 1)
        
        base_stats = {
            **self.stats,
            'success_rate': (self.stats['inserted'] / total_processed) * 100,
            'duplicate_rate': (self.stats['duplicates_found'] / total_processed) * 100,
            'error_rate': (self.stats['errors'] / total_processed) * 100,
            'validation_failure_rate': (self.stats['validation_failures'] / total_processed) * 100,
            'data_cleaning_rate': (self.stats['data_cleaned'] / total_processed) * 100
        }
        
        # Add configuration info
        base_stats['configuration'] = {
            'batch_size': self.batch_size,
            'validation_enabled': self.validate_on_load,
            'data_cleaning_enabled': self.clean_data_on_load,
            'min_quality_score': self.min_quality_score,
            'min_completeness_score': self.min_completeness,
            'duplicate_strategy': self.duplicate_strategy
        }
        
        # Add cleaning settings summary
        base_stats['cleaning_settings'] = {
            'normalize_companies': self.normalize_companies,
            'clean_phone_numbers': self.clean_phones,
            'validate_emails': self.validate_emails,
            'parse_german_dates': self.parse_german_dates,
            'remove_html_tags': self.remove_html,
            'trim_whitespace': self.trim_whitespace
        }
        
        return base_stats

# Convenience functions
async def load_job_data_from_json(file_path: str) -> bool:
    """Load job data from JSON file"""
    loader = JobDataLoader()
    
    if not await init_database():
        logger.error("Failed to connect to database")
        return False
    
    try:
        return await loader.load_from_json_file(file_path)
    finally:
        await close_database()

async def load_job_data_from_csv(file_path: str) -> bool:
    """Load job data from CSV file"""
    loader = JobDataLoader()
    
    if not await init_database():
        logger.error("Failed to connect to database")
        return False
    
    try:
        return await loader.load_from_csv_file(file_path)
    finally:
        await close_database()

async def load_all_batch_files(data_dir: str = "data/output") -> bool:
    """Load all batch files from data directory"""
    loader = JobDataLoader()
    
    if not await init_database():
        logger.error("Failed to connect to database")
        return False
    
    try:
        success = await loader.load_batch_files(data_dir)
        
        if success:
            # Create session record
            session_name = f"Batch Import {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            await loader.create_scraping_session_record(session_name, {
                'source': 'batch_files',
                'directory': data_dir
            })
            
            # Print statistics
            stats = loader.get_loading_statistics()
            logger.info("=== LOADING STATISTICS ===")
            for key, value in stats.items():
                logger.info(f"{key}: {value}")
        
        return success
        
    finally:
        await close_database()

# Main execution for testing
async def main():
    """Main function for testing data loader"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test loading batch files
    logger.info("Testing data loader with batch files...")
    success = await load_all_batch_files("data/output")
    
    if success:
        logger.info(" Data loading completed successfully")
    else:
        logger.error("L Data loading failed")

if __name__ == "__main__":
    asyncio.run(main())