"""
Database package for job scraper
Provides database connection management and data loading functionality
"""

from .connection import (
    DatabaseManager,
    db_manager,
    init_database,
    close_database,
    get_db_connection,
    get_db_transaction
)

from .data_loader import JobDataLoader

# Alias for backward compatibility
DataLoader = JobDataLoader

__all__ = [
    'DatabaseManager',
    'db_manager', 
    'init_database',
    'close_database',
    'get_db_connection',
    'get_db_transaction',
    'DataLoader',
    'JobDataLoader'
]