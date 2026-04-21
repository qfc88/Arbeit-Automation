#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integration Test Script for Enhanced Job Scraper
Tests all components working together: settings, database, file management, validation
"""

import asyncio
import sys
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Add paths for imports
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root / "src"))
sys.path.append(str(project_root / "src" / "config"))
sys.path.append(str(project_root / "src" / "utils"))
sys.path.append(str(project_root / "src" / "database"))
sys.path.append(str(project_root / "src" / "scrapers"))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class IntegrationTest:
    def __init__(self):
        self.test_results = {}
        self.start_time = datetime.now()
        
    def log_test_start(self, test_name: str):
        """Log the start of a test"""
        logger.info(f"🧪 Testing: {test_name}")
        
    def log_test_result(self, test_name: str, success: bool, details: str = ""):
        """Log test result"""
        self.test_results[test_name] = {
            'success': success,
            'details': details,
            'timestamp': datetime.now().isoformat()
        }
        
        status = "[SUCCESS] PASS" if success else "[ERROR] FAIL"
        logger.info(f"{status} {test_name}")
        if details:
            logger.info(f"   Details: {details}")
    
    async def test_settings_import(self) -> bool:
        """Test 1: Settings configuration import"""
        self.log_test_start("Settings Configuration Import")
        
        try:
            from settings import (SCRAPER_SETTINGS, DATABASE_SETTINGS, CAPTCHA_SETTINGS,
                                VALIDATION_SETTINGS, FILE_MANAGEMENT_SETTINGS, PATHS)
            
            # Validate key settings
            required_keys = {
                'SCRAPER_SETTINGS': ['batch_size', 'headless', 'use_sessions'],
                'DATABASE_SETTINGS': ['host', 'database', 'username'],
                'CAPTCHA_SETTINGS': ['trocr_attempts', 'twocaptcha_attempts'],
                'VALIDATION_SETTINGS': ['validate_on_scrape', 'min_quality_score'],
                'FILE_MANAGEMENT_SETTINGS': ['use_sessions', 'auto_backup'],
                'PATHS': ['data_dir', 'output_dir', 'input_dir']
            }
            
            missing_keys = []
            for setting_name, keys in required_keys.items():
                setting_dict = locals()[setting_name]
                for key in keys:
                    if key not in setting_dict:
                        missing_keys.append(f"{setting_name}.{key}")
            
            if missing_keys:
                self.log_test_result("Settings Configuration Import", False, 
                                   f"Missing keys: {', '.join(missing_keys)}")
                return False
            
            self.log_test_result("Settings Configuration Import", True, 
                               "All required settings available")
            return True
            
        except ImportError as e:
            self.log_test_result("Settings Configuration Import", False, f"Import error: {e}")
            return False
        except Exception as e:
            self.log_test_result("Settings Configuration Import", False, f"Error: {e}")
            return False
    
    async def test_database_connection(self) -> bool:
        """Test 2: Database connection and health"""
        self.log_test_start("Database Connection")
        
        try:
            from database.connection import init_database, close_database, db_manager
            
            # Test connection
            connected = await init_database()
            if not connected:
                self.log_test_result("Database Connection", False, "Failed to connect to database")
                return False
            
            # Test basic query
            test_query = "SELECT 1 as test"
            result = await db_manager.execute_single(test_query)
            
            if result and result.get('test') == 1:
                self.log_test_result("Database Connection", True, "Connection and query successful")
                await close_database()
                return True
            else:
                self.log_test_result("Database Connection", False, "Test query failed")
                await close_database()
                return False
                
        except ImportError as e:
            self.log_test_result("Database Connection", False, f"Import error: {e}")
            return False
        except Exception as e:
            self.log_test_result("Database Connection", False, f"Error: {e}")
            return False
    
    async def test_file_manager(self) -> bool:
        """Test 3: FileManager functionality"""
        self.log_test_start("FileManager Functionality")
        
        try:
            from file_manager import FileManager
            
            # Initialize FileManager
            fm = FileManager()
            
            # Test data
            test_jobs = [
                {
                    'profession': 'Test Job',
                    'company_name': 'Test Company',
                    'location': 'Test Location',
                    'telephone': '+49123456789',
                    'email': 'test@example.com',
                    'source_url': 'https://example.com/job1',
                    'scraped_at': datetime.now().isoformat()
                }
            ]
            
            # Test session creation and file saving
            session_id = datetime.now().strftime('%Y%m%d_%H%M%S_test')
            
            json_path, csv_path = fm.save_jobs_batch(
                test_jobs, 
                batch_number=1,
                session_id=session_id,
                use_session_dir=True
            )
            
            # Verify files exist
            if json_path.exists() and csv_path.exists():
                # Test file contents
                with open(json_path, 'r', encoding='utf-8') as f:
                    saved_data = json.load(f)
                
                if len(saved_data) == 1 and saved_data[0]['profession'] == 'Test Job':
                    self.log_test_result("FileManager Functionality", True, 
                                       f"Files created: {json_path.name}, {csv_path.name}")
                    
                    # Cleanup test files
                    json_path.unlink()
                    csv_path.unlink()
                    return True
                else:
                    self.log_test_result("FileManager Functionality", False, "Data mismatch in saved files")
                    return False
            else:
                self.log_test_result("FileManager Functionality", False, "Files not created")
                return False
                
        except ImportError as e:
            self.log_test_result("FileManager Functionality", False, f"Import error: {e}")
            return False
        except Exception as e:
            self.log_test_result("FileManager Functionality", False, f"Error: {e}")
            return False
    
    async def test_job_model_validation(self) -> bool:
        """Test 4: JobModel validation functionality"""
        self.log_test_start("JobModel Validation")
        
        try:
            from job_model import JobModel
            
            # Test valid job data
            valid_job_data = {
                'profession': 'Software Engineer',
                'company_name': 'Tech Corp',
                'location': 'Berlin',
                'telephone': '+49123456789',
                'email': 'jobs@techcorp.com',
                'job_description': 'Great opportunity for software development',
                'source_url': 'https://example.com/job1',
                'scraped_at': datetime.now().isoformat()
            }
            
            # Test JobModel creation and validation
            job_model = JobModel.from_scraped_data(valid_job_data)
            validation_result = job_model.validate()
            
            if validation_result.is_valid:
                # Test invalid job data
                invalid_job_data = {
                    'profession': '',  # Empty required field
                    'company_name': '',  # Empty required field
                    'email': 'invalid-email',  # Invalid email format
                    'source_url': 'not-a-url'  # Invalid URL
                }
                
                invalid_job_model = JobModel.from_scraped_data(invalid_job_data)
                invalid_validation = invalid_job_model.validate()
                
                if not invalid_validation.is_valid and len(invalid_validation.errors) > 0:
                    self.log_test_result("JobModel Validation", True, 
                                       f"Valid data passed, invalid data caught ({len(invalid_validation.errors)} errors)")
                    return True
                else:
                    self.log_test_result("JobModel Validation", False, "Invalid data not caught")
                    return False
            else:
                self.log_test_result("JobModel Validation", False, 
                                   f"Valid data failed validation: {validation_result.errors}")
                return False
                
        except ImportError as e:
            self.log_test_result("JobModel Validation", False, f"Import error: {e}")
            return False
        except Exception as e:
            self.log_test_result("JobModel Validation", False, f"Error: {e}")
            return False
    
    async def test_captcha_solver_import(self) -> bool:
        """Test 5: CAPTCHA solver availability"""
        self.log_test_start("CAPTCHA Solver Import")
        
        try:
            from captcha_solver import CaptchaSolver
            
            # Test initialization (without actually solving)
            solver = CaptchaSolver()
            
            # Test model info
            model_info = solver.get_model_info()
            
            if 'model_name' in model_info and 'status' in model_info:
                self.log_test_result("CAPTCHA Solver Import", True, 
                                   f"Model: {model_info['model_name']}, Status: {model_info['status']}")
                return True
            else:
                self.log_test_result("CAPTCHA Solver Import", False, "Invalid model info")
                return False
                
        except ImportError as e:
            self.log_test_result("CAPTCHA Solver Import", False, f"Import error: {e}")
            return False
        except Exception as e:
            self.log_test_result("CAPTCHA Solver Import", False, f"Error: {e}")
            return False
    
    async def test_data_loader(self) -> bool:
        """Test 6: Data loader functionality"""
        self.log_test_start("Data Loader")
        
        try:
            from database.data_loader import JobDataLoader
            from database.connection import init_database, close_database
            
            # Initialize database
            connected = await init_database()
            if not connected:
                self.log_test_result("Data Loader", False, "Database connection failed")
                return False
            
            # Initialize data loader
            loader = JobDataLoader()
            
            # Test data
            test_jobs = [
                {
                    'profession': 'Test Position',
                    'company_name': 'Test Company',
                    'location': 'Test City',
                    'telephone': '+49987654321',
                    'email': 'test@loader.com',
                    'source_url': f'https://test.com/job_integration_test_{datetime.now().timestamp()}',
                    'scraped_at': datetime.now().isoformat()
                }
            ]
            
            # Test loading jobs
            inserted_count = await loader.load_jobs_batch(test_jobs)
            
            if inserted_count == 1:
                # Test statistics
                stats = loader.get_statistics()
                
                if 'total_jobs_processed' in stats and stats['total_jobs_processed'] >= 1:
                    self.log_test_result("Data Loader", True, 
                                       f"Inserted {inserted_count} job, stats available")
                    await close_database()
                    return True
                else:
                    self.log_test_result("Data Loader", False, "Statistics not available")
                    await close_database()
                    return False
            else:
                self.log_test_result("Data Loader", False, f"Expected 1 insertion, got {inserted_count}")
                await close_database()
                return False
                
        except ImportError as e:
            self.log_test_result("Data Loader", False, f"Import error: {e}")
            return False
        except Exception as e:
            self.log_test_result("Data Loader", False, f"Error: {e}")
            return False
    
    async def test_job_scraper_enhanced_init(self) -> bool:
        """Test 7: Enhanced JobScraper initialization"""
        self.log_test_start("Enhanced JobScraper")
        
        try:
            from job_scraper import JobScraper
            
            # Test enhanced initialization
            scraper = JobScraper(
                auto_solve_captcha=False,  # Don't initialize actual CAPTCHA solver
                use_sessions=True,
                validate_data=True
            )
            
            # Check attributes
            required_attrs = ['use_sessions', 'validate_data', 'session_id', 'stats', 'batch_size']
            missing_attrs = [attr for attr in required_attrs if not hasattr(scraper, attr)]
            
            if missing_attrs:
                self.log_test_result("Enhanced JobScraper", False, 
                                   f"Missing attributes: {', '.join(missing_attrs)}")
                return False
            
            # Test statistics method
            stats = scraper.get_scraping_statistics()
            
            if 'session_info' in stats and 'scraping_performance' in stats:
                self.log_test_result("Enhanced JobScraper", True, 
                                   f"Session: {scraper.session_id}, Stats available")
                return True
            else:
                self.log_test_result("Enhanced JobScraper", False, "Statistics method failed")
                return False
                
        except ImportError as e:
            self.log_test_result("Enhanced JobScraper", False, f"Import error: {e}")
            return False
        except Exception as e:
            self.log_test_result("Enhanced JobScraper", False, f"Error: {e}")
            return False
    
    def generate_test_report(self):
        """Generate comprehensive test report"""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result['success'])
        failed_tests = total_tests - passed_tests
        
        elapsed_time = (datetime.now() - self.start_time).total_seconds()
        
        logger.info("=" * 80)
        logger.info("🧪 INTEGRATION TEST REPORT")
        logger.info("=" * 80)
        logger.info(f"📊 Total Tests: {total_tests}")
        logger.info(f"[SUCCESS] Passed: {passed_tests}")
        logger.info(f"[ERROR] Failed: {failed_tests}")
        logger.info(f"📈 Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        logger.info(f"[TIME]  Duration: {elapsed_time:.2f} seconds")
        
        logger.info("\n📋 DETAILED RESULTS:")
        for test_name, result in self.test_results.items():
            status = "[SUCCESS] PASS" if result['success'] else "[ERROR] FAIL"
            logger.info(f"   {status} {test_name}")
            if result['details']:
                logger.info(f"      {result['details']}")
        
        if failed_tests == 0:
            logger.info("\n🎉 ALL TESTS PASSED! Integration is working correctly.")
        else:
            logger.info(f"\n[WARNING]  {failed_tests} TEST(S) FAILED. Check components before deployment.")
        
        logger.info("=" * 80)
        
        # Save report to file
        report_data = {
            'summary': {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'failed_tests': failed_tests,
                'success_rate': (passed_tests/total_tests)*100,
                'duration_seconds': elapsed_time,
                'test_time': self.start_time.isoformat()
            },
            'results': self.test_results
        }
        
        report_path = project_root / "data" / "logs" / f"integration_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"📄 Test report saved: {report_path}")
        
        return failed_tests == 0
    
    async def run_all_tests(self) -> bool:
        """Run all integration tests"""
        logger.info("🚀 Starting Integration Tests for Enhanced Job Scraper")
        logger.info("Testing all components: settings, database, file management, validation")
        
        # Run tests in sequence
        tests = [
            self.test_settings_import,
            self.test_database_connection,
            self.test_file_manager,
            self.test_job_model_validation,
            self.test_captcha_solver_import,
            self.test_data_loader,
            self.test_job_scraper_enhanced_init
        ]
        
        for test in tests:
            try:
                await test()
            except Exception as e:
                test_name = test.__name__.replace('test_', '').replace('_', ' ').title()
                self.log_test_result(test_name, False, f"Unexpected error: {e}")
        
        # Generate final report
        return self.generate_test_report()

async def main():
    """Main entry point"""
    logger.info("Enhanced Job Scraper - Integration Test Suite")
    
    test_runner = IntegrationTest()
    success = await test_runner.run_all_tests()
    
    if success:
        logger.info("[SUCCESS] All integration tests passed!")
        return 0
    else:
        logger.error("[ERROR] Some integration tests failed!")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)