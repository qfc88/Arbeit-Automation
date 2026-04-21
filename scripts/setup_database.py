#!/usr/bin/env python3
"""
Database setup script for Job Scraper
Creates PostgreSQL database and tables with proper schema
"""

import asyncio
import sys
import logging
from pathlib import Path

# Add src directory to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root / "src"))

async def setup_database():
    """Set up the database with comprehensive schema"""
    try:
        from database.connection import init_database, close_database, db_manager
        
        print("Setting up job scraper database...")
        
        # Initialize connection
        success = await init_database()
        if not success:
            print("L Failed to connect to database")
            return False
        
        print(" Connected to database")
        
        # Create schema from SQL file
        schema_file = project_root / "src" / "database" / "schema.sql"
        if schema_file.exists():
            print("=Ä Loading schema from schema.sql...")
            
            with open(schema_file, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            
            # Execute schema
            async with db_manager.get_transaction() as conn:
                await conn.execute(schema_sql)
            
            print(" Database schema created successfully")
            
            # Verify tables
            tables_query = '''
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name
            '''
            tables = await db_manager.execute_query(tables_query)
            
            print(f"=Ê Created {len(tables)} tables:")
            for table in tables:
                print(f"   - {table['table_name']}")
            
        else:
            print("  schema.sql not found, creating basic jobs table...")
            
            # Fallback: create basic table
            basic_sql = """
            CREATE TABLE IF NOT EXISTS jobs (
                id SERIAL PRIMARY KEY,
                profession VARCHAR(500),
                company_name VARCHAR(500),
                location VARCHAR(255),
                salary VARCHAR(255),
                email VARCHAR(255),
                telephone VARCHAR(100),
                job_description TEXT,
                ref_nr VARCHAR(100),
                external_link TEXT,
                application_link TEXT,
                source_url TEXT,
                scraped_at TIMESTAMP DEFAULT NOW()
            )
            """
            await db_manager.execute_command(basic_sql)
            print(" Basic jobs table created")
        
        await close_database()
        print("<‰ Database setup completed successfully!")
        return True
        
    except Exception as e:
        print(f"L Database setup failed: {e}")
        return False

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Run setup
    success = asyncio.run(setup_database())
    sys.exit(0 if success else 1)