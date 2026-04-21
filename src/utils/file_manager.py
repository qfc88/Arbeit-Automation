"""
File management utilities for job scraper
Handles file operations, batch management, progress tracking, and prevents overwrites
Solves the batch file overwrite issue when restarting scraper sessions
"""

import json
import csv
import pandas as pd
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import shutil
import uuid
import hashlib
import os
import glob
import sys

# Import centralized settings
sys.path.append(str(Path(__file__).parent.parent / "config"))
try:
    from settings import PATHS, FILE_MANAGEMENT_SETTINGS
except ImportError as e:
    raise ImportError(
        f"[ERROR] Settings import failed: {e}\n"
        "Please ensure src/config/settings.py exists and contains PATHS and FILE_MANAGEMENT_SETTINGS"
    )

logger = logging.getLogger(__name__)

class FileManager:
    def __init__(self, base_dir: str = None):
        """Initialize file manager with centralized directory structure"""
        self.base_dir = Path(base_dir) if base_dir else Path(PATHS['data_dir'])
        self.input_dir = Path(PATHS['input_dir'])
        self.output_dir = Path(PATHS['output_dir'])
        self.logs_dir = Path(PATHS['logs_dir'])
        self.temp_dir = Path(PATHS['temp_dir'])
        self.backup_dir = Path(PATHS['backup_dir'])
        
        # Create directories if they don't exist
        self._ensure_directories()
        
        # Session management
        self.current_session_id = None
        self.session_start_time = None
        
        logger.info(f"FileManager initialized with base directory: {self.base_dir}")
    
    def _ensure_directories(self):
        """Ensure all required directories exist"""
        directories = [
            self.input_dir, self.output_dir, self.logs_dir, 
            self.temp_dir, self.backup_dir
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Directory ensured: {directory}")
    
    def find_active_session(self) -> str:
        """Find the most recent active session to resume"""
        try:
            # Look for session directories created within resume window
            from ..config.settings import FILE_MANAGEMENT_SETTINGS
            resume_hours = FILE_MANAGEMENT_SETTINGS.get('session_resume_hours', 24)
            current_time = datetime.now()
            cutoff_time = current_time - timedelta(hours=resume_hours)
            
            session_dirs = []
            for item in self.output_dir.iterdir():
                if item.is_dir() and item.name.startswith('scrape_session_'):
                    try:
                        # Extract timestamp from session name
                        timestamp_str = item.name.replace('scrape_session_', '')
                        session_time = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                        
                        if session_time >= cutoff_time:
                            session_dirs.append((item.name, session_time))
                    except ValueError:
                        continue
            
            if session_dirs:
                # Return the most recent session
                session_dirs.sort(key=lambda x: x[1], reverse=True)
                latest_session = session_dirs[0][0]
                logger.info(f"Found active session to resume: {latest_session}")
                return latest_session
            
        except Exception as e:
            logger.warning(f"Error finding active session: {e}")
        
        return None
    
    def create_session_lock(self, session_id: str) -> bool:
        """Create a lock file for the session to prevent concurrent access"""
        try:
            lock_file = self.output_dir / session_id / ".session_lock"
            lock_file.parent.mkdir(exist_ok=True)
            
            if lock_file.exists():
                # Check if lock is stale (older than 1 hour)
                lock_time = datetime.fromtimestamp(lock_file.stat().st_mtime)
                if datetime.now() - lock_time > timedelta(hours=1):
                    lock_file.unlink()  # Remove stale lock
                    logger.info(f"Removed stale session lock for {session_id}")
                else:
                    logger.warning(f"Session {session_id} is locked by another process")
                    return False
            
            # Create new lock
            with open(lock_file, 'w') as f:
                f.write(f"locked_at={datetime.now().isoformat()}\n")
                f.write(f"process_id={os.getpid()}\n")
            
            logger.debug(f"Created session lock for {session_id}")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to create session lock: {e}")
            return True  # Proceed without lock if can't create
    
    def remove_session_lock(self, session_id: str):
        """Remove session lock file"""
        try:
            lock_file = self.output_dir / session_id / ".session_lock"
            if lock_file.exists():
                lock_file.unlink()
                logger.debug(f"Removed session lock for {session_id}")
        except Exception as e:
            logger.warning(f"Failed to remove session lock: {e}")
    
    def start_new_session(self, session_name: str = None, force_new: bool = False) -> str:
        """Start a new scraping session with unique identifier"""
        from ..config.settings import FILE_MANAGEMENT_SETTINGS
        auto_resume = FILE_MANAGEMENT_SETTINGS.get('auto_resume_sessions', True)
        force_new = force_new or FILE_MANAGEMENT_SETTINGS.get('force_new_session', False)
        
        # Try to find existing active session unless forced to create new
        if not force_new and not session_name and auto_resume:
            existing_session = self.find_active_session()
            if existing_session and self.create_session_lock(existing_session):
                self.current_session_id = existing_session
                self.session_start_time = datetime.now()
                logger.info(f"Resumed existing session: {existing_session}")
                return existing_session
        
        # Create new session
        if not session_name:
            session_name = f"scrape_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Try to acquire lock for new session
        if not self.create_session_lock(session_name):
            # If can't acquire lock, create with unique suffix
            session_name = f"scrape_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"
            self.create_session_lock(session_name)
        
        self.current_session_id = session_name
        self.session_start_time = datetime.now()
        
        # Create session directory
        session_dir = self.output_dir / session_name
        session_dir.mkdir(exist_ok=True)
        
        logger.info(f"Started new scraping session: {session_name}")
        return session_name
    
    def get_current_session_dir(self) -> Path:
        """Get current session output directory"""
        if not self.current_session_id:
            self.start_new_session()
        
        return self.output_dir / self.current_session_id
    
    def get_next_batch_number(self, session_id: str = None) -> int:
        """Get next available batch number to prevent overwrites"""
        if not session_id:
            session_id = self.current_session_id or "default"
        
        session_dir = self.output_dir / session_id
        session_dir.mkdir(exist_ok=True)
        
        # Find existing batch files in session directory
        batch_files = list(session_dir.glob("scraped_jobs_batch_*.json"))
        
        if not batch_files:
            return 1
        
        # Extract batch numbers and find the highest
        batch_numbers = []
        for file in batch_files:
            try:
                # Extract number from filename like "scraped_jobs_batch_5.json"
                batch_num = int(file.stem.split('_')[-1])
                batch_numbers.append(batch_num)
            except (ValueError, IndexError):
                continue
        
        return max(batch_numbers) + 1 if batch_numbers else 1
    
    def get_global_next_batch_number(self) -> int:
        """Get next global batch number across all sessions (for backward compatibility)"""
        # Find all batch files in output directory and subdirectories
        batch_files = list(self.output_dir.rglob("scraped_jobs_batch_*.json"))
        
        if not batch_files:
            return 1
        
        batch_numbers = []
        for file in batch_files:
            try:
                batch_num = int(file.stem.split('_')[-1])
                batch_numbers.append(batch_num)
            except (ValueError, IndexError):
                continue
        
        return max(batch_numbers) + 1 if batch_numbers else 1
    
    def save_jobs_batch(self, jobs: List[Dict[str, Any]], batch_number: int = None, 
                       session_id: str = None, use_session_dir: bool = True) -> Tuple[Path, Path]:
        """
        Save jobs batch with improved file management
        Returns tuple of (json_path, csv_path)
        """
        try:
            if use_session_dir and session_id:
                output_dir = self.output_dir / session_id
            elif use_session_dir and self.current_session_id:
                output_dir = self.get_current_session_dir()
            else:
                output_dir = self.output_dir
            
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Get batch number
            if batch_number is None:
                if use_session_dir:
                    batch_number = self.get_next_batch_number(session_id)
                else:
                    batch_number = self.get_global_next_batch_number()
            
            # Save as JSON (batch file)
            json_path = output_dir / f"scraped_jobs_batch_{batch_number}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(jobs, f, ensure_ascii=False, indent=2)
            
            # Save consolidated CSV (all jobs so far)
            csv_path = output_dir / "scraped_jobs_progress.csv"
            df = pd.DataFrame(jobs)
            
            # If CSV exists, append; otherwise create new
            if csv_path.exists():
                existing_df = pd.read_csv(csv_path)
                combined_df = pd.concat([existing_df, df], ignore_index=True)
                combined_df.drop_duplicates(subset=['ref_nr'], keep='last', inplace=True)
                combined_df.to_csv(csv_path, index=False, encoding='utf-8')
            else:
                df.to_csv(csv_path, index=False, encoding='utf-8')
            
            logger.info(f"Saved batch {batch_number}: {len(jobs)} jobs to {json_path.name}")
            logger.info(f"Updated progress CSV: {csv_path.name}")
            
            return json_path, csv_path
            
        except Exception as e:
            logger.error(f"Error saving jobs batch: {e}")
            raise
    
    def load_existing_progress(self, session_id: str = None) -> List[Dict[str, Any]]:
        """Load existing progress from CSV file"""
        try:
            if session_id:
                csv_path = self.output_dir / session_id / "scraped_jobs_progress.csv"
            elif self.current_session_id:
                csv_path = self.get_current_session_dir() / "scraped_jobs_progress.csv"
            else:
                csv_path = self.output_dir / "scraped_jobs_progress.csv"
            
            if not csv_path.exists():
                logger.info(f"No existing progress file found: {csv_path}")
                return []
            
            df = pd.read_csv(csv_path)
            jobs = df.to_dict('records')
            
            logger.info(f"Loaded {len(jobs)} existing jobs from {csv_path.name}")
            return jobs
            
        except Exception as e:
            logger.error(f"Error loading existing progress: {e}")
            return []
    
    def get_processed_job_urls(self, session_id: str = None) -> set:
        """Get set of already processed job URLs"""
        existing_jobs = self.load_existing_progress(session_id)
        processed_urls = {job.get('source_url', '') for job in existing_jobs if job.get('source_url')}
        
        logger.info(f"Found {len(processed_urls)} previously processed URLs")
        return processed_urls
    
    def backup_existing_files(self, session_id: str = None) -> bool:
        """Backup existing output files before starting new session"""
        try:
            if session_id:
                source_dir = self.output_dir / session_id
            else:
                source_dir = self.output_dir
            
            if not source_dir.exists():
                logger.info("No existing files to backup")
                return True
            
            # Create backup directory with timestamp
            backup_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_session_dir = self.backup_dir / f"backup_{backup_timestamp}"
            backup_session_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy files to backup
            files_backed_up = 0
            for file_path in source_dir.iterdir():
                if file_path.is_file() and (file_path.suffix in ['.json', '.csv']):
                    backup_path = backup_session_dir / file_path.name
                    shutil.copy2(file_path, backup_path)
                    files_backed_up += 1
            
            logger.info(f"Backed up {files_backed_up} files to {backup_session_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Error backing up files: {e}")
            return False
    
    def consolidate_batch_files(self, session_id: str = None, output_filename: str = None) -> Path:
        """Consolidate all batch files into single JSON and CSV files"""
        try:
            if session_id:
                source_dir = self.output_dir / session_id
            elif self.current_session_id:
                source_dir = self.get_current_session_dir()
            else:
                source_dir = self.output_dir
            
            # Find all batch files
            batch_files = sorted(source_dir.glob("scraped_jobs_batch_*.json"))
            
            if not batch_files:
                logger.warning(f"No batch files found in {source_dir}")
                return None
            
            logger.info(f"Consolidating {len(batch_files)} batch files...")
            
            # Load all jobs from batch files
            all_jobs = []
            for batch_file in batch_files:
                try:
                    with open(batch_file, 'r', encoding='utf-8') as f:
                        jobs = json.load(f)
                        all_jobs.extend(jobs)
                        logger.debug(f"Loaded {len(jobs)} jobs from {batch_file.name}")
                except Exception as e:
                    logger.error(f"Error loading batch file {batch_file}: {e}")
                    continue
            
            # Remove duplicates based on ref_nr
            seen_refs = set()
            unique_jobs = []
            for job in all_jobs:
                ref_nr = job.get('ref_nr')
                if ref_nr and ref_nr not in seen_refs:
                    unique_jobs.append(job)
                    seen_refs.add(ref_nr)
                elif not ref_nr:
                    unique_jobs.append(job)  # Keep jobs without ref_nr
            
            logger.info(f"Consolidated {len(all_jobs)} jobs, {len(unique_jobs)} unique jobs")
            
            # Save consolidated files
            if not output_filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = f"scraped_jobs_consolidated_{timestamp}"
            
            # JSON file
            json_path = source_dir / f"{output_filename}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(unique_jobs, f, ensure_ascii=False, indent=2)
            
            # CSV file
            csv_path = source_dir / f"{output_filename}.csv"
            df = pd.DataFrame(unique_jobs)
            df.to_csv(csv_path, index=False, encoding='utf-8')
            
            logger.info(f"Consolidated files saved:")
            logger.info(f"  JSON: {json_path}")
            logger.info(f"  CSV: {csv_path}")
            
            return json_path
            
        except Exception as e:
            logger.error(f"Error consolidating batch files: {e}")
            return None
    
    def clean_temp_files(self, older_than_hours: int = 24):
        """Clean temporary files older than specified hours"""
        try:
            cutoff_time = datetime.now().timestamp() - (older_than_hours * 3600)
            cleaned_count = 0
            
            for temp_file in self.temp_dir.iterdir():
                if temp_file.is_file() and temp_file.stat().st_mtime < cutoff_time:
                    temp_file.unlink()
                    cleaned_count += 1
            
            logger.info(f"Cleaned {cleaned_count} temporary files older than {older_than_hours} hours")
            
        except Exception as e:
            logger.error(f"Error cleaning temp files: {e}")
    
    def cleanup_session(self):
        """Clean up session resources and remove locks"""
        try:
            if self.current_session_id:
                self.remove_session_lock(self.current_session_id)
                logger.info(f"Session cleanup completed for: {self.current_session_id}")
        except Exception as e:
            logger.warning(f"Error during session cleanup: {e}")
    
    def __del__(self):
        """Cleanup session when FileManager is destroyed"""
        try:
            self.cleanup_session()
        except:
            pass  # Ignore errors during destruction
    
    def get_session_statistics(self, session_id: str = None) -> Dict[str, Any]:
        """Get statistics for a scraping session"""
        try:
            if session_id:
                session_dir = self.output_dir / session_id
            elif self.current_session_id:
                session_dir = self.get_current_session_dir()
            else:
                session_dir = self.output_dir
            
            if not session_dir.exists():
                return {}
            
            # Count batch files
            batch_files = list(session_dir.glob("scraped_jobs_batch_*.json"))
            
            # Load progress CSV if exists
            csv_path = session_dir / "scraped_jobs_progress.csv"
            total_jobs = 0
            if csv_path.exists():
                df = pd.read_csv(csv_path)
                total_jobs = len(df)
            
            # Calculate file sizes
            total_size = sum(f.stat().st_size for f in session_dir.iterdir() if f.is_file())
            total_size_mb = total_size / (1024 * 1024)
            
            stats = {
                'session_id': session_id or self.current_session_id or 'default',
                'session_dir': str(session_dir),
                'batch_files_count': len(batch_files),
                'total_jobs': total_jobs,
                'total_size_mb': round(total_size_mb, 2),
                'files': [f.name for f in session_dir.iterdir() if f.is_file()]
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting session statistics: {e}")
            return {}
    
    def list_available_sessions(self) -> List[Dict[str, Any]]:
        """List all available scraping sessions"""
        try:
            sessions = []
            
            # Check for session directories
            for item in self.output_dir.iterdir():
                if item.is_dir() and item.name.startswith('scrape_session_'):
                    session_stats = self.get_session_statistics(item.name)
                    if session_stats:
                        sessions.append(session_stats)
            
            # Add default session if it has files
            default_files = [f for f in self.output_dir.iterdir() if f.is_file()]
            if default_files:
                default_stats = self.get_session_statistics()
                if default_stats:
                    sessions.append(default_stats)
            
            return sorted(sessions, key=lambda x: x.get('session_id', ''))
            
        except Exception as e:
            logger.error(f"Error listing sessions: {e}")
            return []
    
    def resume_session(self, session_id: str) -> bool:
        """Resume an existing scraping session"""
        try:
            session_dir = self.output_dir / session_id
            
            if not session_dir.exists():
                logger.error(f"Session directory not found: {session_dir}")
                return False
            
            self.current_session_id = session_id
            self.session_start_time = datetime.now()
            
            logger.info(f"Resumed scraping session: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error resuming session: {e}")
            return False

# Convenience functions for backward compatibility
def save_progress(scraped_jobs: List[Dict], batch_number: int, use_sessions: bool = True):
    """Save progress using file manager (backward compatibility)"""
    file_manager = FileManager()
    
    if use_sessions and not file_manager.current_session_id:
        file_manager.start_new_session()
    
    return file_manager.save_jobs_batch(scraped_jobs, batch_number, use_session_dir=use_sessions)

def load_existing_jobs(session_id: str = None) -> List[Dict[str, Any]]:
    """Load existing jobs (backward compatibility)"""
    file_manager = FileManager()
    return file_manager.load_existing_progress(session_id)

def get_processed_urls(session_id: str = None) -> set:
    """Get processed URLs (backward compatibility)"""
    file_manager = FileManager()
    return file_manager.get_processed_job_urls(session_id)

# Example usage and testing
async def main():
    """Example usage of file manager"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    file_manager = FileManager()
    
    # List available sessions
    sessions = file_manager.list_available_sessions()
    logger.info(f"Available sessions: {len(sessions)}")
    for session in sessions:
        logger.info(f"  {session['session_id']}: {session['total_jobs']} jobs, {session['total_size_mb']} MB")
    
    # Example: Start new session
    session_id = file_manager.start_new_session("test_session")
    
    # Example: Save some test data
    test_jobs = [
        {
            "profession": "Test Job 1",
            "company_name": "Test Company",
            "location": "Test City",
            "ref_nr": "TEST001",
            "source_url": "https://example.com/job1"
        }
    ]
    
    json_path, csv_path = file_manager.save_jobs_batch(test_jobs)
    logger.info(f"Test batch saved to {json_path}")
    
    # Get session statistics
    stats = file_manager.get_session_statistics()
    logger.info(f"Session statistics: {stats}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())