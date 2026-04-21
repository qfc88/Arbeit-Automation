"""
Configuration settings for the job scraper
Comprehensive configuration for all components: scraping, database, validation, file management
"""

import os
from pathlib import Path

# =============================================================================
# API Configurations
# =============================================================================

# 2captcha API Configuration
TWOCAPTCHA_API_KEY = "5865b4e02e5bc91f671a60bc18fd75d1"

# =============================================================================
# Scraper Configuration
# =============================================================================

# Main scraper settings
SCRAPER_SETTINGS = {
    'headless': True,               # Set to True for faster performance
    'timeout': 15000,               # Reduced timeout for faster processing
    'delay_between_jobs': 0.5,      # Minimal delay for speed
    'batch_size': 100,              # Large batch size for efficiency
    'max_retries': 2,               # Balanced retries
    'save_every_n_jobs': 50,        # Save less frequently for speed
    'max_jobs_per_session': 1000,   # Large session capacity
    'enable_resume': True,          # Enable resume functionality
    'use_sessions': True,           # Use session-based file management
}

# Browser Configuration
BROWSER_SETTINGS = {
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'viewport': {'width': 1920, 'height': 1080},
    'args': [
        '--disable-blink-features=AutomationControlled',
        '--disable-web-security',
        '--disable-features=VizDisplayCompositor',
        '--no-sandbox',
        '--disable-dev-shm-usage'
    ],
    'download_behavior': 'allow',
    'timezone_id': 'Europe/Berlin',
    'locale': 'de-DE',
}

# =============================================================================
# CAPTCHA Configuration
# =============================================================================

CAPTCHA_SETTINGS = {
    'trocr_attempts': 0,            # TrOCR attempts before fallback
    'twocaptcha_attempts': 15,       # 2Captcha attempts before fallback
    'manual_timeout': 300,          # Manual solving timeout in seconds (5 min)
    'confidence_threshold': 0.7,    # TrOCR confidence threshold
    'solving_strategies': ['trocr', '2captcha', 'manual'],  # Priority order
    'trocr_model': 'anuashok/ocr-captcha-v3',
    'reload_captcha_between_attempts': True,
    'max_total_attempts': 20,       # Maximum total attempts across all strategies
}

# =============================================================================
# Database Configuration
# =============================================================================

DATABASE_SETTINGS = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'job_market_data'),
    'username': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'working'),
    'min_connections': 5,
    'max_connections': 20,
    'connection_timeout': 60,
    'command_timeout': 30,
    'ssl_mode': 'prefer',
    'enable_logging': True,
}

# =============================================================================
# File Management Configuration
# =============================================================================

# Base paths
BASE_DIR = Path(__file__).parent.parent.parent  # job-scraper root directory
DATA_DIR = BASE_DIR / "data"

PATHS = {
    'base_dir': str(BASE_DIR),
    'data_dir': str(DATA_DIR),
    'input_dir': str(DATA_DIR / "input"),
    'output_dir': str(DATA_DIR / "output"),
    'logs_dir': str(DATA_DIR / "logs"),
    'temp_dir': str(DATA_DIR / "temp"),
    'backup_dir': str(DATA_DIR / "backup"),
    
    # Specific files
    'input_csv': str(DATA_DIR / "input" / "job_urls.csv"),
    'progress_csv': 'scraped_jobs_progress.csv',
    'consolidated_json': 'scraped_jobs_consolidated.json',
    'missing_emails_json': 'missing_emails.json',
}

# File management settings
FILE_MANAGEMENT_SETTINGS = {
    'use_sessions': True,                    # Use session-based directories
    'auto_backup': True,                     # Backup files before new sessions
    'session_name_format': 'scrape_session_%Y%m%d_%H%M%S',
    'batch_file_format': 'scraped_jobs_batch_{batch_number}.json',
    'max_batch_size': 100,                   # Maximum jobs per batch file
    'consolidate_on_completion': True,       # Auto-consolidate when scraping completes
    'clean_temp_files_hours': 24,           # Clean temp files after N hours
    'max_backup_files': 10,                  # Keep max N backup sets
    'session_resume_hours': 24,              # Resume sessions created within N hours
    'auto_resume_sessions': True,            # Automatically resume recent sessions
    'force_new_session': False,              # Force creation of new session instead of resuming
}

# =============================================================================
# Data Validation Configuration
# =============================================================================

VALIDATION_SETTINGS = {
    'default_level': 'moderate',             # strict, moderate, lenient
    'required_fields': [
        'profession', 'company_name', 'source_url'  # Minimum required fields
    ],
    'validate_on_scrape': True,              # Validate data immediately after scraping
    'clean_data_on_save': True,              # Clean/normalize data before saving
    'skip_invalid_jobs': False,              # Skip invalid jobs or save with warnings
    'min_quality_score': 3.0,               # Minimum quality score (0-11)
    'min_completeness_score': 0.3,          # Minimum completeness score (0-1)
}

# Data cleaning settings
DATA_CLEANING_SETTINGS = {
    'normalize_company_names': True,         # Remove "Arbeitgeber:" prefixes
    'clean_phone_numbers': True,            # Format phone numbers
    'validate_email_format': True,          # Check email format
    'parse_german_dates': True,             # Parse German date formats
    'remove_html_tags': True,               # Strip HTML from text fields
    'trim_whitespace': True,                # Remove excess whitespace
    'standardize_job_types': True,          # Normalize job type values
}

# =============================================================================
# Contact Scraper Configuration
# =============================================================================

CONTACT_SCRAPER_SETTINGS = {
    'max_contact_pages': 15,
    'contact_page_timeout': 5000,            # Skip contact pages that load >5 seconds (optimized for speed)
    'delay_between_pages': 0.5,              # Reduced delay for speed
    'max_search_depth': 2,                   # Reduced depth for faster processing
    'preferred_email_domains': [              # Prioritize certain email domains
        'hr', 'jobs', 'karriere', 'bewerbung', 'personal'
    ],
    'contact_page_patterns': [               # German contact page patterns
        '/kontakt', '/impressum', '/karriere', '/jobs', '/bewerbung'
    ],
    'enable_deep_scraping': True,            # Enable deep contact mining
    'parallel_contact_requests': 5,          # More parallel requests for speed
}

# =============================================================================
# Logging Configuration
# =============================================================================

LOGGING_SETTINGS = {
    'level': 'DEBUG',                        # DEBUG, INFO, WARNING, ERROR - Set to DEBUG for troubleshooting
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'date_format': '%Y-%m-%d %H:%M:%S',
    'enable_file_logging': True,
    'enable_console_logging': True,
    'log_file_max_size': '50MB',
    'log_file_backup_count': 5,
    'separate_error_log': True,
    
    # Component-specific log levels - Set to DEBUG for database debugging
    'component_levels': {
        'scrapers.job_scraper': 'INFO',
        'scrapers.captcha_solver': 'INFO',
        'scrapers.contact_scraper': 'WARNING',
        'database.connection': 'DEBUG',        # Enable debug logging for database
        'database.data_loader': 'DEBUG',       # Enable debug logging for data loader
        'utils.file_manager': 'INFO',
    }
}

# =============================================================================
# Performance and Monitoring
# =============================================================================

PERFORMANCE_SETTINGS = {
    'enable_metrics': True,                  # Enable performance metrics
    'metrics_interval': 60,                  # Metrics reporting interval (seconds)
    'monitor_memory_usage': True,            # Monitor memory consumption
    'monitor_cpu_usage': True,               # Monitor CPU usage
    'alert_on_high_memory': True,            # Alert when memory usage is high
    'memory_threshold_mb': 1000,             # Memory alert threshold
    'enable_profiling': False,               # Enable code profiling (dev only)
}

MONITORING_SETTINGS = {
    'track_scraping_speed': True,            # Track jobs per minute
    'track_captcha_success_rate': True,      # Monitor CAPTCHA solving success
    'track_data_quality': True,              # Monitor data quality metrics
    'export_metrics': True,                  # Export metrics to files
    'metrics_format': 'json',                # json, csv
}

# =============================================================================
# Testing Configuration
# =============================================================================

TESTING_SETTINGS = {
    'enable_test_mode': False,               # Enable test mode
    'test_job_limit': 10,                    # Limit jobs in test mode
    'use_test_database': False,              # Use separate test database
    'mock_captcha_solving': False,           # Mock CAPTCHA for testing
    'test_data_dir': str(DATA_DIR / "test"),
    'enable_dry_run': False,                 # Dry run mode (no actual scraping)
}

# =============================================================================
# Environment-Specific Overrides
# =============================================================================

# Production environment settings
if os.getenv('ENVIRONMENT') == 'production':
    SCRAPER_SETTINGS['headless'] = True
    # Override with environment variables if provided
    if os.getenv('SCRAPER_BATCH_SIZE'):
        SCRAPER_SETTINGS['batch_size'] = int(os.getenv('SCRAPER_BATCH_SIZE'))
    else:
        SCRAPER_SETTINGS['batch_size'] = 50
    
    if os.getenv('MAX_JOBS_PER_SESSION'):
        SCRAPER_SETTINGS['max_jobs_per_session'] = int(os.getenv('MAX_JOBS_PER_SESSION'))
    
    LOGGING_SETTINGS['level'] = 'WARNING'
    DATABASE_SETTINGS['min_connections'] = 10
    DATABASE_SETTINGS['max_connections'] = 50
    PERFORMANCE_SETTINGS['enable_profiling'] = False

# Development environment settings
elif os.getenv('ENVIRONMENT') == 'development':
    SCRAPER_SETTINGS['headless'] = False
    SCRAPER_SETTINGS['batch_size'] = 5
    LOGGING_SETTINGS['level'] = 'DEBUG'
    PERFORMANCE_SETTINGS['enable_profiling'] = True
    TESTING_SETTINGS['enable_test_mode'] = True

# =============================================================================
# Validation and Environment Check
# =============================================================================

def validate_settings():
    """Validate configuration settings"""
    errors = []
    
    # Check required directories
    required_dirs = [PATHS['data_dir'], PATHS['input_dir'], PATHS['output_dir']]
    for dir_path in required_dirs:
        if not Path(dir_path).exists():
            try:
                Path(dir_path).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                errors.append(f"Cannot create directory {dir_path}: {e}")
    
    # Check API key
    if not TWOCAPTCHA_API_KEY or TWOCAPTCHA_API_KEY == "your_api_key_here":
        errors.append("2Captcha API key not configured")
    
    # Check database settings
    if not DATABASE_SETTINGS['password'] and DATABASE_SETTINGS['username'] != 'postgres':
        errors.append("Database password not configured")
    
    return errors

def get_config_summary():
    """Get configuration summary for logging"""
    return {
        'scraper_batch_size': SCRAPER_SETTINGS['batch_size'],
        'captcha_strategies': CAPTCHA_SETTINGS['solving_strategies'],
        'database_host': DATABASE_SETTINGS['host'],
        'use_sessions': FILE_MANAGEMENT_SETTINGS['use_sessions'],
        'validation_level': VALIDATION_SETTINGS['default_level'],
        'logging_level': LOGGING_SETTINGS['level'],
    }

# Validate settings on import
_validation_errors = validate_settings()
if _validation_errors:
    import warnings
    for error in _validation_errors:
        warnings.warn(f"Configuration warning: {error}")

# =============================================================================
# Export commonly used settings groups
# =============================================================================

__all__ = [
    'TWOCAPTCHA_API_KEY',
    'SCRAPER_SETTINGS',
    'BROWSER_SETTINGS', 
    'CAPTCHA_SETTINGS',
    'DATABASE_SETTINGS',
    'PATHS',
    'FILE_MANAGEMENT_SETTINGS',
    'VALIDATION_SETTINGS',
    'DATA_CLEANING_SETTINGS',
    'CONTACT_SCRAPER_SETTINGS',
    'LOGGING_SETTINGS',
    'PERFORMANCE_SETTINGS',
    'MONITORING_SETTINGS',
    'TESTING_SETTINGS',
    'validate_settings',
    'get_config_summary'
]