#!/usr/bin/env python3
"""
Docker Schema Fix Script
This script generates the SQL command to fix the schema in Docker
"""

def generate_schema_fix():
    """Generate SQL commands to fix the schema"""
    
    sql_commands = [
        "-- Fix the ambiguous job_id parameter issue",
        "DROP FUNCTION IF EXISTS update_data_quality_metrics(UUID);",
        "",
        "CREATE OR REPLACE FUNCTION update_data_quality_metrics(target_job_id UUID)",
        "RETURNS VOID AS $$",
        "DECLARE",
        "    job_record jobs;",
        "    quality_score FLOAT;",
        "BEGIN",
        "    -- Get job record",
        "    SELECT * INTO job_record FROM jobs WHERE id = target_job_id;",
        "    ",
        "    -- Calculate quality score",
        "    quality_score := calculate_data_quality_score(job_record);",
        "    ",
        "    -- Insert or update quality metrics",
        "    INSERT INTO data_quality_metrics (",
        "        job_id, ",
        "        has_profession, has_salary, has_company_name, has_location, has_start_date,",
        "        has_telephone, has_email, has_job_description, has_ref_nr, ",
        "        has_external_link, has_application_link, completeness_score",
        "    ) VALUES (",
        "        target_job_id,",
        "        CASE WHEN job_record.profession IS NOT NULL AND LENGTH(job_record.profession) > 0 THEN 1 ELSE 0 END,",
        "        CASE WHEN job_record.salary IS NOT NULL AND LENGTH(job_record.salary) > 0 THEN 1 ELSE 0 END,",
        "        CASE WHEN job_record.company_name IS NOT NULL AND LENGTH(job_record.company_name) > 0 THEN 1 ELSE 0 END,",
        "        CASE WHEN job_record.location IS NOT NULL AND LENGTH(job_record.location) > 0 THEN 1 ELSE 0 END,",
        "        CASE WHEN job_record.start_date IS NOT NULL AND LENGTH(job_record.start_date) > 0 THEN 1 ELSE 0 END,",
        "        CASE WHEN job_record.telephone IS NOT NULL AND LENGTH(job_record.telephone) > 0 THEN 1 ELSE 0 END,",
        "        CASE WHEN job_record.email IS NOT NULL AND LENGTH(job_record.email) > 0 THEN 1 ELSE 0 END,",
        "        CASE WHEN job_record.job_description IS NOT NULL AND LENGTH(job_record.job_description) > 0 THEN 1 ELSE 0 END,",
        "        CASE WHEN job_record.ref_nr IS NOT NULL AND LENGTH(job_record.ref_nr) > 0 THEN 1 ELSE 0 END,",
        "        CASE WHEN job_record.external_link IS NOT NULL AND LENGTH(job_record.external_link) > 0 THEN 1 ELSE 0 END,",
        "        CASE WHEN job_record.application_link IS NOT NULL AND LENGTH(job_record.application_link) > 0 THEN 1 ELSE 0 END,",
        "        quality_score / 11.0",
        "    ) ON CONFLICT (job_id) DO UPDATE SET",
        "        has_profession = EXCLUDED.has_profession,",
        "        has_salary = EXCLUDED.has_salary,",
        "        has_company_name = EXCLUDED.has_company_name,",
        "        has_location = EXCLUDED.has_location,",
        "        has_start_date = EXCLUDED.has_start_date,",
        "        has_telephone = EXCLUDED.has_telephone,",
        "        has_email = EXCLUDED.has_email,",
        "        has_job_description = EXCLUDED.has_job_description,",
        "        has_ref_nr = EXCLUDED.has_ref_nr,",
        "        has_external_link = EXCLUDED.has_external_link,",
        "        has_application_link = EXCLUDED.has_application_link,",
        "        completeness_score = EXCLUDED.completeness_score;",
        "END;",
        "$$ LANGUAGE plpgsql;",
        "",
        "-- Test the function",
        "SELECT 'Schema fix applied successfully!' as result;"
    ]
    
    return "\n".join(sql_commands)

if __name__ == "__main__":
    print("=" * 60)
    print("DOCKER DATABASE SCHEMA FIX")
    print("=" * 60)
    print()
    print("Run this command to fix the database schema in Docker:")
    print()
    print("docker-compose exec postgres psql -U postgres -d job_market_data")
    print()
    print("Then paste this SQL:")
    print("-" * 40)
    print(generate_schema_fix())
    print("-" * 40)
    print()
    print("Or run this one-liner:")
    print("echo \"" + generate_schema_fix().replace("\n", "\\n").replace('"', '\\"') + "\" | docker-compose exec -T postgres psql -U postgres -d job_market_data")
    print()
    print("=" * 60)