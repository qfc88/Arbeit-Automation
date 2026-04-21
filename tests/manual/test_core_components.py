#!/usr/bin/env python3
"""
Simple test script to verify core components work without Playwright dependencies
"""

import sys
from pathlib import Path

# Add paths
project_root = Path(__file__).parent
sys.path.append(str(project_root / "src"))
sys.path.append(str(project_root / "src" / "config"))
sys.path.append(str(project_root / "src" / "utils"))
sys.path.append(str(project_root / "src" / "database"))
sys.path.append(str(project_root / "src" / "models"))

def test_settings():
    """Test settings import"""
    print("[TEST] Testing settings...")
    try:
        from settings import SCRAPER_SETTINGS, DATABASE_SETTINGS, CAPTCHA_SETTINGS
        print(f"[PASS] Settings loaded: batch_size={SCRAPER_SETTINGS['batch_size']}")
        return True
    except Exception as e:
        print(f"[FAIL] Settings failed: {e}")
        return False

def test_file_manager():
    """Test FileManager"""
    print("[TEST] Testing FileManager...")
    try:
        from file_manager import FileManager
        fm = FileManager()
        print("[PASS] FileManager initialized successfully")
        return True
    except Exception as e:
        print(f"[FAIL] FileManager failed: {e}")
        return False

def test_job_model():
    """Test JobModel validation"""
    print("[TEST] Testing JobModel...")
    try:
        from job_model import JobModel
        from datetime import datetime
        
        test_data = {
            'profession': 'Test Job',
            'company_name': 'Test Company',
            'source_url': 'https://example.com/test',
            'scraped_at': datetime.now().isoformat()
        }
        
        job = JobModel.from_scraped_data(test_data)
        validation = job.validate()
        print(f"[PASS] JobModel validation: {validation.is_valid}")
        return True
    except Exception as e:
        print(f"[FAIL] JobModel failed: {e}")
        return False

def test_database_connection():
    """Test database connection (without actually connecting)"""
    print("[TEST] Testing Database components...")
    try:
        from database.connection import DatabaseManager
        dm = DatabaseManager()
        print(f"[PASS] Database manager initialized: {dm.host}:{dm.port}")
        return True
    except Exception as e:
        print(f"[FAIL] Database failed: {e}")
        return False

def main():
    """Run core component tests"""
    print("Testing Enhanced Job Scraper Core Components")
    print("=" * 50)
    
    tests = [
        test_settings,
        test_file_manager,
        test_job_model,
        test_database_connection
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("SUCCESS: All core components working!")
        return True
    else:
        print("WARNING: Some components need attention")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)