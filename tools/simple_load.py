#!/usr/bin/env python3
"""
Simple data loader to import JSON batch files into PostgreSQL
Fixes the schema and datetime issues in the main data_loader
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import uuid

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from database.connection import db_manager, init_database, close_database

async def load_batch_files():
    """Load all batch files into database"""
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
        print(f"Loading from session: {latest_session.name}")
        
        # Find all batch files
        batch_files = list(latest_session.glob("scraped_jobs_batch_*.json"))
        print(f"Found {len(batch_files)} batch files")
        
        total_loaded = 0
        total_skipped = 0
        
        for batch_file in sorted(batch_files):
            print(f"Processing {batch_file.name}...")
            
            try:
                with open(batch_file, 'r', encoding='utf-8') as f:
                    jobs = json.load(f)
                
                for job_data in jobs:
                    try:
                        # Check if job already exists
                        existing = await db_manager.execute_single(
                            "SELECT id FROM jobs WHERE source_url = $1",
                            job_data.get('source_url')
                        )
                        
                        if existing:
                            total_skipped += 1
                            continue
                            
                        # Convert scraped_at to datetime
                        scraped_at_str = job_data.get('scraped_at', datetime.now().isoformat())
                        try:
                            scraped_at = datetime.fromisoformat(scraped_at_str.replace('Z', '+00:00'))
                        except:
                            scraped_at = datetime.now()
                        
                        # Generate UUID
                        job_id = uuid.uuid4()
                        
                        # Insert minimal required fields
                        await db_manager.execute_command("""
                            INSERT INTO jobs (
                                id, profession, company_name, location, source_url, 
                                scraped_at, salary, telephone, email, job_description,
                                ref_nr, external_link, application_link, job_type,
                                ausbildungsberuf, contact_person, captcha_solved
                            ) VALUES (
                                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17
                            )
                        """,
                            job_id,
                            job_data.get('profession'),
                            job_data.get('company_name'), 
                            job_data.get('location'),
                            job_data.get('source_url'),
                            scraped_at,
                            job_data.get('salary'),
                            job_data.get('telephone'),
                            job_data.get('email'),
                            job_data.get('job_description'),
                            job_data.get('ref_nr'),
                            job_data.get('external_link'),
                            job_data.get('application_link'),
                            job_data.get('job_type'),
                            job_data.get('ausbildungsberuf'),
                            job_data.get('contact_person'),
                            job_data.get('captcha_solved', False)
                        )
                        
                        total_loaded += 1
                        
                    except Exception as e:
                        print(f"Error inserting job {job_data.get('ref_nr', 'unknown')}: {e}")
                        continue
                        
            except Exception as e:
                print(f"Error processing {batch_file.name}: {e}")
                continue
                
        print(f"Loading completed: {total_loaded} inserted, {total_skipped} skipped")
        return True
        
    except Exception as e:
        print(f"Fatal error: {e}")
        return False
        
    finally:
        await close_database()

if __name__ == "__main__":
    asyncio.run(load_batch_files())