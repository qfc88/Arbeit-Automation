"""
Centralized logging configuration for job scraper
Provides consistent logging across all components with file and console handlers
"""

import logging
import logging.handlers
import sys
from pathlib import Path

def setup_logger(name, log_file, level=logging.INFO):
    """
    Set up a logger with both file and console handlers
    
    Args:
        name: Logger name (e.g., 'scrapers.job_scraper')
        log_file: Path to log file (e.g., 'scraper.log')
        level: Logging level (default: INFO)
    
    Returns:
        Configured logger instance
    """
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler with rotation
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=50*1024*1024,  # 50MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Could not create file handler for {log_file}: {e}")
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

def get_scraper_logger(component_name):
    """Get logger for scraper components"""
    from config.settings import PATHS, LOGGING_SETTINGS
    
    log_level = getattr(logging, LOGGING_SETTINGS.get('level', 'INFO'))
    logs_dir = Path(PATHS['logs_dir'])
    
    if 'job_scraper' in component_name:
        log_file = logs_dir / 'scraper.log'
    elif 'captcha' in component_name:
        log_file = logs_dir / 'scraper.log'
    elif 'contact' in component_name:
        log_file = logs_dir / 'scraper.log'
    elif 'link' in component_name:
        log_file = logs_dir / 'scraper.log'
    elif 'pipeline' in component_name:
        log_file = logs_dir / 'pipeline.log'
    elif 'database' in component_name:
        log_file = logs_dir / 'pipeline.log'
    else:
        log_file = logs_dir / 'scraper.log'
    
    return setup_logger(component_name, log_file, log_level)

def get_error_logger():
    """Get logger specifically for errors"""
    from config.settings import PATHS
    
    logs_dir = Path(PATHS['logs_dir'])
    error_log_file = logs_dir / 'errors.log'
    
    return setup_logger('errors', error_log_file, logging.ERROR)

def log_error(message, exception=None):
    """Log error to error.log file"""
    error_logger = get_error_logger()
    if exception:
        error_logger.error(f"{message}: {exception}", exc_info=True)
    else:
        error_logger.error(message)