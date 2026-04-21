#!/usr/bin/env python3
"""
Update start_dates in database - load from JSON and parse German dates
"""

import asyncio
import json
import sys
import re
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from database.connection import db_manager, init_database, close_database

def parse_german_start_date(date_str: str) -> Optional[datetime]:
    """Parse German start date formats to datetime"""
    if not date_str:
        return None
    
    # German date patterns commonly found in job postings
    patterns = [
        r'Beginn ab (\d{1,2})\.(\d{1,2})\.(\d{4})',
        r'Beginn (\d{1,2})\.(\d{1,2})\.(\d{4})',
        r'ab (\d{1,2})\.(\d{1,2})\.(\d{4})',
        r'^(\d{1,2})\.(\d{1,2})\.(\d{4})$',
        r'zum (\d{1,2})\.(\d{1,2})\.(\d{4})',
        r'(\d{1,2})\.(\d{1,2})\.(\d{4})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, date_str)
        if match:
            day, month, year = match.groups()
            try:
                return datetime(int(year), int(month), int(day))
            except ValueError:
                continue
    
    return None

async def update_start_dates():
    """Load start dates from JSON files and update database"""
    try:
        print("Connecting to database...")
        if not await init_database():
            print("Failed to connect to database")
            return False
            
        # Find latest session directory
        output_dir = Path("data/output")
        session_dirs = [d for d in output_dir.iterdir() if d.is_dir()]
        if not session_dirs:
            print("No session directories found")
            return False
            
        latest_session = max(session_dirs, key=lambda x: x.name)
        print(f"Processing session: {latest_session.name}")
        
        # Find all batch files
        batch_files = list(latest_session.glob("scraped_jobs_batch_*.json"))
        print(f"Found {len(batch_files)} batch files")
        
        total_updated = 0
        total_parsed = 0
        
        for batch_file in sorted(batch_files):
            print(f"Processing {batch_file.name}...")
            
            try:
                with open(batch_file, 'r', encoding='utf-8') as f:
                    jobs = json.load(f)
                
                for job_data in jobs:
                    source_url = job_data.get('source_url')
                    start_date_text = job_data.get('start_date')
                    
                    if not source_url:
                        continue
                        
                    try:
                        # Update start_date text field
                        await db_manager.execute_command(
                            "UPDATE jobs SET start_date = $1 WHERE source_url = $2",
                            start_date_text, source_url
                        )
                        
                        if start_date_text:
                            total_updated += 1
                            
                            # Parse date and update parsed field
                            parsed_date = parse_german_start_date(start_date_text)
                            if parsed_date:
                                await db_manager.execute_command(
                                    "UPDATE jobs SET start_date_parsed = $1 WHERE source_url = $2",
                                    parsed_date.date(), source_url
                                )
                                total_parsed += 1
                                print(f"  Parsed: '{start_date_text}' -> {parsed_date.date()}")
                        
                    except Exception as e:
                        print(f"Error updating job {source_url}: {e}")
                        continue
                        
            except Exception as e:
                print(f"Error processing {batch_file.name}: {e}")
                continue
                
        print(f"\nUpdate completed:")
        print(f"- Start date texts updated: {total_updated}")
        print(f"- Dates successfully parsed: {total_parsed}")
        return True
        
    except Exception as e:
        print(f"Fatal error: {e}")
        return False
        
    finally:
        await close_database()

if __name__ == "__main__":
    asyncio.run(update_start_dates())