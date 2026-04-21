#!/usr/bin/env python3
"""
Local Database Test Script
Test database connection and insert a sample job to verify schema
"""
import asyncio
import sys
import uuid
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

async def test_database_local():
    """Test database connection and schema locally"""
    try:
        print("[TEST] Testing database connection locally...")
        
        # Import after path setup
        from database.connection import db_manager
        from database.data_loader import JobDataLoader
        
        # Test connection
        print(f"Host: {db_manager.host}:{db_manager.port}")
        print(f"Database: {db_manager.database}")
        print(f"Username: {db_manager.username}")
        
        print("\n[CONNECT] Connecting to database...")
        success = await db_manager.connect()
        
        if not success:
            print("[ERROR] Failed to connect to database")
            return False
        
        print("[SUCCESS] Database connected successfully!")
        
        # Test data loader
        print("\n[LOADER] Testing JobDataLoader...")
        loader = JobDataLoader()
        
        # Create a test job
        test_job = {
            'profession': 'Test Software Developer',
            'salary': '50000 EUR',
            'company_name': 'Test Company GmbH',
            'location': 'Berlin',
            'start_date': '2024-09-01',
            'telephone': '+49 30 12345678',
            'email': 'test@example.com',
            'job_description': 'Test job description for debugging',
            'ref_nr': f'TEST-{datetime.now().strftime("%Y%m%d%H%M%S")}',
            'external_link': 'https://example.com/job',
            'application_link': 'https://example.com/apply',
            'job_type': 'Vollzeit',
            'ausbildungsberuf': None,
            'application_method': 'Online',
            'contact_person': 'Test Recruiter',
            'scraped_at': datetime.now().isoformat(),
            'source_url': 'https://example.com/test-job',
            'captcha_solved': False,
            'is_external_redirect': False
        }
        
        print(f"[INSERT] Inserting test job: {test_job['ref_nr']}")
        
        # Try to load the test job
        result = await loader.load_single_job(test_job)
        
        print(f"[RESULT] Result: {result}")
        
        if result.get('loaded', 0) > 0:
            print("[SUCCESS] Test job inserted successfully!")
            print("[SUCCESS] Database schema is working correctly")
        else:
            print("[ERROR] Test job failed to insert")
            print(f"[ERROR] Error: {result.get('error', 'Unknown error')}")
        
        # Close connection
        await db_manager.disconnect()
        print("\n[CLOSE] Database connection closed")
        
        return result.get('loaded', 0) > 0
        
    except Exception as e:
        print(f"[ERROR] Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("LOCAL DATABASE TEST")
    print("=" * 50)
    
    success = asyncio.run(test_database_local())
    
    print("\n" + "=" * 50)
    if success:
        print("[PASS] LOCAL DATABASE TEST PASSED")
        print("Database is working correctly on local machine")
    else:
        print("[FAIL] LOCAL DATABASE TEST FAILED")
        print("Database has issues that need to be fixed")
    print("=" * 50)