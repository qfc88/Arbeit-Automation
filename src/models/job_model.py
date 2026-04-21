"""
Job data model and validation for the job scraper
Provides data validation, transformation, and standardization for scraped job data
Ensures data quality and consistency before database insertion
"""

import re
import uuid
import logging
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
import hashlib
from urllib.parse import urlparse
import json

logger = logging.getLogger(__name__)

class JobStatus(Enum):
    """Job status enumeration"""
    ACTIVE = "active"
    EXPIRED = "expired"
    FILLED = "filled"
    DELETED = "deleted"
    DRAFT = "draft"

class JobType(Enum):
    """Job type enumeration"""
    VOLLZEIT = "Vollzeit"
    TEILZEIT = "Teilzeit"
    MINIJOB = "Minijob"
    AUSBILDUNG = "Ausbildung"
    PRAKTIKUM = "Praktikum"
    FREELANCE = "Freelance"
    UNKNOWN = "Unknown"

class ValidationLevel(Enum):
    """Validation strictness levels"""
    STRICT = "strict"      # All required fields must be valid
    MODERATE = "moderate"  # Most required fields must be valid
    LENIENT = "lenient"   # Basic validation only

@dataclass
class ValidationResult:
    """Result of data validation"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    quality_score: float = 0.0
    completeness_score: float = 0.0

@dataclass
class JobModel:
    """
    Job data model representing a single job posting
    Based on the 11 required fields from the assignment plus additional metadata
    """
    
    # Assignment Required Fields (11 fields)
    profession: Optional[str] = None              # Job title/position
    salary: Optional[str] = None                  # Salary information
    company_name: Optional[str] = None            # Company name
    location: Optional[str] = None                # Job location
    start_date: Optional[str] = None              # Start date
    telephone: Optional[str] = None               # Contact telephone
    email: Optional[str] = None                   # Contact email
    job_description: Optional[str] = None         # Full job description
    ref_nr: Optional[str] = None                  # Reference number
    external_link: Optional[str] = None           # External contact link
    application_link: Optional[str] = None        # Direct application link
    
    # Additional scraped fields
    job_type: Optional[str] = None                # Vollzeit, Teilzeit, etc.
    ausbildungsberuf: Optional[str] = None        # Training profession
    application_method: Optional[str] = None      # How to apply
    contact_person: Optional[str] = None          # Contact person name
    
    # Metadata fields
    source_url: Optional[str] = None              # Original job posting URL
    scraped_at: Optional[Union[datetime, str]] = None  # When job was scraped
    captcha_solved: bool = False                  # Whether CAPTCHA was needed
    
    # System fields
    id: Optional[uuid.UUID] = None                # Unique identifier
    content_hash: Optional[str] = None            # Hash for duplicate detection
    status: JobStatus = JobStatus.ACTIVE          # Job status
    is_valid: bool = True                         # Validation status
    validation_errors: List[str] = field(default_factory=list)
    data_quality_score: float = 0.0              # Quality score 0-11
    
    # Processed timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Post initialization processing"""
        # Generate ID if not provided
        if self.id is None:
            self.id = uuid.uuid4()
        
        # Set timestamps
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
        
        # Handle scraped_at conversion
        if isinstance(self.scraped_at, str):
            self.scraped_at = self._parse_datetime(self.scraped_at)
        elif self.scraped_at is None:
            self.scraped_at = datetime.utcnow()
        
        # Generate content hash
        if self.content_hash is None:
            self.content_hash = self._generate_content_hash()
    
    def _parse_datetime(self, dt_string: str) -> datetime:
        """Parse datetime string in various formats"""
        if not dt_string:
            return datetime.utcnow()
        
        # Common datetime formats
        formats = [
            "%Y-%m-%dT%H:%M:%S.%f",      # ISO format with microseconds
            "%Y-%m-%dT%H:%M:%S",         # ISO format
            "%Y-%m-%d %H:%M:%S",         # Standard format
            "%Y-%m-%d",                  # Date only
        ]
        
        # Remove timezone info for parsing
        dt_string = re.sub(r'[+\-]\d{2}:?\d{2}$', '', dt_string)
        dt_string = dt_string.replace('Z', '')
        
        for fmt in formats:
            try:
                return datetime.strptime(dt_string, fmt)
            except ValueError:
                continue
        
        logger.warning(f"Could not parse datetime: {dt_string}")
        return datetime.utcnow()
    
    def _generate_content_hash(self) -> str:
        """Generate content hash for duplicate detection"""
        content_fields = [
            str(self.profession or ''),
            str(self.company_name or ''),
            str(self.location or ''),
            str(self.ref_nr or ''),
            str(self.source_url or '')
        ]
        
        content_string = '|'.join(content_fields).lower().strip()
        return hashlib.sha256(content_string.encode()).hexdigest()
    
    def validate(self, level: ValidationLevel = ValidationLevel.MODERATE) -> ValidationResult:
        """Validate job data according to specified level"""
        result = ValidationResult(is_valid=True)
        
        # Required fields validation
        required_fields = {
            'profession': self.profession,
            'company_name': self.company_name,
            'source_url': self.source_url
        }
        
        # Check required fields
        for field_name, field_value in required_fields.items():
            if not field_value or (isinstance(field_value, str) and not field_value.strip()):
                result.errors.append(f"Required field '{field_name}' is missing or empty")
        
        # Validate specific field formats
        self._validate_email(result)
        self._validate_telephone(result)
        self._validate_urls(result)
        self._validate_dates(result)
        self._validate_text_fields(result)
        
        # Calculate quality scores
        result.completeness_score = self._calculate_completeness_score()
        result.quality_score = self._calculate_quality_score()
        
        # Set validation level specific rules
        if level == ValidationLevel.STRICT:
            if result.completeness_score < 0.8:
                result.errors.append("Data completeness below 80% (strict validation)")
        elif level == ValidationLevel.MODERATE:
            if result.completeness_score < 0.5:
                result.errors.append("Data completeness below 50% (moderate validation)")
        # LENIENT has no additional completeness requirements
        
        # Final validation result
        result.is_valid = len(result.errors) == 0
        
        # Update model validation state
        self.is_valid = result.is_valid
        self.validation_errors = result.errors.copy()
        self.data_quality_score = result.quality_score
        
        return result
    
    def _validate_email(self, result: ValidationResult):
        """Validate email format"""
        if self.email:
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, self.email.strip().lower()):
                result.errors.append(f"Invalid email format: {self.email}")
    
    def _validate_telephone(self, result: ValidationResult):
        """Validate telephone format"""
        if self.telephone:
            phone = self.telephone.strip()
            # German phone number patterns
            valid_patterns = [
                r'^\+49\s*\(?\d+\)?\s*\d+[-\s]?\d+',  # +49 format
                r'^0\d+\s*\d+[-\s]?\d+',              # 0 format
                r'^\d{3,}-?\d{3,}-?\d{3,}'            # Generic format
            ]
            
            if not any(re.match(pattern, phone) for pattern in valid_patterns):
                result.warnings.append(f"Unusual telephone format: {self.telephone}")
    
    def _validate_urls(self, result: ValidationResult):
        """Validate URL formats"""
        urls_to_check = [
            ('source_url', self.source_url),
            ('external_link', self.external_link),
            ('application_link', self.application_link)
        ]
        
        for field_name, url in urls_to_check:
            if url:
                try:
                    parsed = urlparse(url)
                    if not parsed.scheme or not parsed.netloc:
                        result.errors.append(f"Invalid URL format in {field_name}: {url}")
                except Exception:
                    result.errors.append(f"Invalid URL in {field_name}: {url}")
    
    def _validate_dates(self, result: ValidationResult):
        """Validate date fields"""
        if self.start_date:
            # Try to parse common German date formats
            date_patterns = [
                r'\d{1,2}\.\d{1,2}\.\d{4}',    # DD.MM.YYYY
                r'\d{4}-\d{1,2}-\d{1,2}',      # YYYY-MM-DD
                r'ab\s+\d{1,2}\.\d{1,2}\.\d{4}',  # ab DD.MM.YYYY
            ]
            
            if not any(re.search(pattern, self.start_date) for pattern in date_patterns):
                result.warnings.append(f"Unusual date format: {self.start_date}")
    
    def _validate_text_fields(self, result: ValidationResult):
        """Validate text field quality"""
        text_fields = {
            'profession': self.profession,
            'company_name': self.company_name,
            'location': self.location,
            'job_description': self.job_description
        }
        
        for field_name, field_value in text_fields.items():
            if field_value:
                # Check for suspiciously short important fields
                if field_name in ['profession', 'company_name'] and len(field_value.strip()) < 3:
                    result.warnings.append(f"{field_name} is very short: {field_value}")
                
                # Check for HTML artifacts
                if '<' in field_value and '>' in field_value:
                    result.warnings.append(f"{field_name} may contain HTML: {field_value[:50]}...")
    
    def _calculate_completeness_score(self) -> float:
        """Calculate data completeness score (0-1)"""
        required_fields = [
            self.profession, self.salary, self.company_name, self.location,
            self.start_date, self.telephone, self.email, self.job_description,
            self.ref_nr, self.external_link, self.application_link
        ]
        
        completed_fields = sum(1 for field in required_fields if field and str(field).strip())
        return completed_fields / len(required_fields)
    
    def _calculate_quality_score(self) -> float:
        """Calculate overall data quality score (0-11)"""
        score = 0
        
        # Score each required field
        fields_with_weights = [
            (self.profession, 1.0),
            (self.salary, 0.5),  # Often missing in German job postings
            (self.company_name, 1.0),
            (self.location, 1.0),
            (self.start_date, 0.8),
            (self.telephone, 1.0),
            (self.email, 1.0),
            (self.job_description, 1.0),
            (self.ref_nr, 0.8),
            (self.external_link, 0.5),
            (self.application_link, 0.7)
        ]
        
        for field_value, weight in fields_with_weights:
            if field_value and str(field_value).strip():
                # Additional quality checks
                field_str = str(field_value).strip()
                field_score = weight
                
                # Bonus for longer content (for description)
                if field_value == self.job_description and len(field_str) > 100:
                    field_score += 0.2
                
                # Penalty for very short important fields
                if field_value in [self.profession, self.company_name] and len(field_str) < 5:
                    field_score *= 0.5
                
                score += field_score
        
        return min(score, 11.0)  # Cap at 11
    
    def clean_data(self):
        """Clean and normalize data fields"""
        # Clean string fields
        string_fields = [
            'profession', 'salary', 'company_name', 'location', 'start_date',
            'telephone', 'email', 'job_description', 'ref_nr', 'job_type',
            'ausbildungsberuf', 'application_method', 'contact_person'
        ]
        
        for field_name in string_fields:
            field_value = getattr(self, field_name)
            if field_value:
                # Basic cleaning
                cleaned = str(field_value).strip()
                cleaned = re.sub(r'\s+', ' ', cleaned)  # Multiple spaces to single
                
                # Field-specific cleaning
                if field_name == 'company_name':
                    cleaned = re.sub(r'^Arbeitgeber:\s*', '', cleaned, flags=re.IGNORECASE)
                elif field_name == 'email':
                    cleaned = cleaned.lower()
                elif field_name == 'telephone':
                    cleaned = re.sub(r'[^\d+\(\)\-\s]', '', cleaned)
                
                setattr(self, field_name, cleaned if cleaned else None)
        
        # Update content hash after cleaning
        self.content_hash = self._generate_content_hash()
        self.updated_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert job model to dictionary"""
        data = {}
        
        for field_name, field_value in self.__dict__.items():
            if isinstance(field_value, datetime):
                data[field_name] = field_value.isoformat()
            elif isinstance(field_value, uuid.UUID):
                data[field_name] = str(field_value)
            elif isinstance(field_value, Enum):
                data[field_name] = field_value.value
            else:
                data[field_name] = field_value
        
        return data
    
    def to_database_dict(self) -> Dict[str, Any]:
        """Convert to dictionary suitable for database insertion"""
        db_dict = {
            'id': self.id,
            'profession': self.profession,
            'salary': self.salary,
            'company_name': self.company_name,
            'location': self.location,
            'start_date': self.start_date,
            'telephone': self.telephone,
            'email': self.email,
            'job_description': self.job_description,
            'ref_nr': self.ref_nr,
            'external_link': self.external_link,
            'application_link': self.application_link,
            'job_type': self.job_type,
            'ausbildungsberuf': self.ausbildungsberuf,
            'application_method': self.application_method,
            'contact_person': self.contact_person,
            'source_url': self.source_url,
            'scraped_at': self.scraped_at,
            'captcha_solved': self.captcha_solved,
            'content_hash': self.content_hash,
            'status': self.status.value if isinstance(self.status, JobStatus) else self.status,
            'is_valid': self.is_valid,
            'validation_errors': self.validation_errors,
            'data_quality_score': int(self.data_quality_score)
        }
        
        return db_dict
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JobModel':
        """Create JobModel from dictionary"""
        # Handle special fields
        if 'id' in data and isinstance(data['id'], str):
            data['id'] = uuid.UUID(data['id'])
        
        if 'status' in data and isinstance(data['status'], str):
            try:
                data['status'] = JobStatus(data['status'])
            except ValueError:
                data['status'] = JobStatus.ACTIVE
        
        # Create instance
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    @classmethod
    def from_scraped_data(cls, scraped_data: Dict[str, Any]) -> 'JobModel':
        """Create JobModel from raw scraped data"""
        # Map scraped data fields to model fields
        job = cls(
            profession=scraped_data.get('profession'),
            salary=scraped_data.get('salary'),
            company_name=scraped_data.get('company_name'),
            location=scraped_data.get('location'),
            start_date=scraped_data.get('start_date'),
            telephone=scraped_data.get('telephone'),
            email=scraped_data.get('email'),
            job_description=scraped_data.get('job_description'),
            ref_nr=scraped_data.get('ref_nr'),
            external_link=scraped_data.get('external_link'),
            application_link=scraped_data.get('application_link'),
            job_type=scraped_data.get('job_type'),
            ausbildungsberuf=scraped_data.get('ausbildungsberuf'),
            application_method=scraped_data.get('application_method'),
            contact_person=scraped_data.get('contact_person'),
            source_url=scraped_data.get('source_url'),
            scraped_at=scraped_data.get('scraped_at'),
            captcha_solved=scraped_data.get('captcha_solved', False)
        )
        
        # Clean and validate
        job.clean_data()
        
        return job
    
    def __str__(self) -> str:
        """String representation"""
        return f"JobModel({self.profession} at {self.company_name}, {self.location})"
    
    def __repr__(self) -> str:
        """Detailed string representation"""
        return f"JobModel(id={self.id}, profession='{self.profession}', company='{self.company_name}')"

class JobModelValidator:
    """Utility class for batch validation of job models"""
    
    def __init__(self, validation_level: ValidationLevel = ValidationLevel.MODERATE):
        self.validation_level = validation_level
        self.stats = {
            'total': 0,
            'valid': 0,
            'invalid': 0,
            'warnings': 0
        }
    
    def validate_batch(self, jobs: List[JobModel]) -> List[ValidationResult]:
        """Validate a batch of job models"""
        results = []
        
        for job in jobs:
            result = job.validate(self.validation_level)
            results.append(result)
            
            # Update statistics
            self.stats['total'] += 1
            if result.is_valid:
                self.stats['valid'] += 1
            else:
                self.stats['invalid'] += 1
            if result.warnings:
                self.stats['warnings'] += 1
        
        return results
    
    def get_validation_report(self) -> Dict[str, Any]:
        """Get validation statistics report"""
        if self.stats['total'] == 0:
            return self.stats
        
        return {
            **self.stats,
            'valid_percentage': (self.stats['valid'] / self.stats['total']) * 100,
            'invalid_percentage': (self.stats['invalid'] / self.stats['total']) * 100,
            'warning_percentage': (self.stats['warnings'] / self.stats['total']) * 100
        }

# Utility functions
def validate_scraped_jobs(scraped_jobs: List[Dict[str, Any]], 
                         validation_level: ValidationLevel = ValidationLevel.MODERATE) -> Tuple[List[JobModel], Dict[str, Any]]:
    """Validate scraped jobs and return models with validation report"""
    validator = JobModelValidator(validation_level)
    job_models = []
    
    # Convert to job models
    for scraped_data in scraped_jobs:
        try:
            job_model = JobModel.from_scraped_data(scraped_data)
            job_models.append(job_model)
        except Exception as e:
            logger.error(f"Error creating job model: {e}")
            continue
    
    # Validate models
    validation_results = validator.validate_batch(job_models)
    validation_report = validator.get_validation_report()
    
    return job_models, validation_report

def clean_scraped_jobs(scraped_jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Clean scraped jobs and return cleaned dictionaries"""
    cleaned_jobs = []
    
    for scraped_data in scraped_jobs:
        try:
            job_model = JobModel.from_scraped_data(scraped_data)
            job_model.clean_data()
            cleaned_jobs.append(job_model.to_dict())
        except Exception as e:
            logger.error(f"Error cleaning job data: {e}")
            # Return original data if cleaning fails
            cleaned_jobs.append(scraped_data)
    
    return cleaned_jobs

# Example usage and testing
def main():
    """Example usage of job model"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Example scraped data
    sample_data = {
        "profession": "Software Developer",
        "salary": "50,000 - 70,000 EUR",
        "company_name": "Arbeitgeber: Tech Company GmbH",
        "location": "Berlin",
        "start_date": "01.09.2025",
        "telephone": "+49 30 12345678",
        "email": "jobs@techcompany.de",
        "job_description": "We are looking for a skilled software developer...",
        "ref_nr": "TC2025001",
        "external_link": "https://example.com/contact",
        "application_link": "https://example.com/apply",
        "source_url": "https://arbeitsagentur.de/job/123456",
        "scraped_at": "2025-08-22T15:30:00",
        "captcha_solved": True
    }
    
    # Create job model
    job = JobModel.from_scraped_data(sample_data)
    logger.info(f"Created job model: {job}")
    
    # Validate job
    validation_result = job.validate(ValidationLevel.MODERATE)
    logger.info(f"Validation result: Valid={validation_result.is_valid}")
    logger.info(f"Quality score: {validation_result.quality_score:.2f}")
    logger.info(f"Completeness score: {validation_result.completeness_score:.2f}")
    
    if validation_result.errors:
        logger.warning(f"Errors: {validation_result.errors}")
    if validation_result.warnings:
        logger.warning(f"Warnings: {validation_result.warnings}")
    
    # Convert to database format
    db_dict = job.to_database_dict()
    logger.info("Converted to database format successfully")

if __name__ == "__main__":
    main()