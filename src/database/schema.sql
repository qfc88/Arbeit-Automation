-- Job Scraper Database Schema
-- PostgreSQL database schema for German job market data from arbeitsagentur.de
-- Author: Job Scraper Pipeline
-- Created: 2025-08-22

-- =============================================================================
-- Extension for UUID generation
-- =============================================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- Companies Table
-- Stores unique company information
-- =============================================================================
CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(500) NOT NULL,
    normalized_name VARCHAR(500), -- For deduplication
    domain VARCHAR(255), -- Company website domain
    industry VARCHAR(255),
    size_category VARCHAR(50), -- 'small', 'medium', 'large', 'enterprise'
    location VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Indexes
    CONSTRAINT unique_company_name UNIQUE(normalized_name)
);

CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(name);
CREATE INDEX IF NOT EXISTS idx_companies_domain ON companies(domain);
CREATE INDEX IF NOT EXISTS idx_companies_location ON companies(location);

-- =============================================================================
-- Jobs Table - Main table storing all job postings
-- Based on the 11 required fields from assignment + additional metadata
-- =============================================================================
CREATE TABLE IF NOT EXISTS jobs (
    -- Primary key and references
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id),
    
    -- Assignment Required Fields (11 fields)
    profession VARCHAR(500) NOT NULL,               -- Job title/position
    salary VARCHAR(255),                            -- Salary information (often null in German job posts)
    company_name VARCHAR(500) NOT NULL,            -- Company name as scraped
    location VARCHAR(255),                          -- Job location
    start_date VARCHAR(255),                        -- Start date (various formats)
    telephone VARCHAR(50),                          -- Contact telephone
    email VARCHAR(255),                             -- Contact email
    job_description TEXT,                           -- Full job description
    ref_nr VARCHAR(100),                            -- Reference number
    external_link TEXT,                             -- External contact link
    application_link TEXT,                          -- Direct application link
    
    -- Additional scraped fields
    job_type VARCHAR(100),                          -- Vollzeit, Teilzeit, etc.
    ausbildungsberuf VARCHAR(255),                  -- Training profession
    application_method VARCHAR(255),                -- How to apply
    contact_person VARCHAR(255),                    -- Contact person name
    
    -- Metadata fields
    source_url TEXT NOT NULL,                       -- Original job posting URL
    scraped_at TIMESTAMPTZ NOT NULL,               -- When job was scraped
    captcha_solved BOOLEAN DEFAULT FALSE,          -- Whether CAPTCHA was needed
    data_quality_score INTEGER DEFAULT 0,          -- Data completeness score (0-11)
    
    -- Processing status
    status VARCHAR(50) DEFAULT 'active',            -- active, expired, filled, deleted
    processed_at TIMESTAMPTZ,                       -- When job was processed
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    
    -- Data validation
    is_valid BOOLEAN DEFAULT TRUE,                  -- Data validation status
    validation_errors TEXT[],                       -- Array of validation error messages
    
    -- Deduplication
    content_hash VARCHAR(64),                       -- Hash for duplicate detection
    
    -- Indexes and constraints
    CONSTRAINT unique_source_url UNIQUE(source_url)
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_jobs_profession ON jobs(profession);
CREATE INDEX IF NOT EXISTS idx_jobs_company_name ON jobs(company_name);
CREATE INDEX IF NOT EXISTS idx_jobs_location ON jobs(location);
CREATE INDEX IF NOT EXISTS idx_jobs_scraped_at ON jobs(scraped_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_ref_nr ON jobs(ref_nr);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_salary ON jobs(salary) WHERE salary IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_jobs_email ON jobs(email) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_jobs_content_hash ON jobs(content_hash);

-- Composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_jobs_company_location ON jobs(company_name, location);
CREATE INDEX IF NOT EXISTS idx_jobs_status_scraped ON jobs(status, scraped_at DESC);

-- =============================================================================
-- Contact Information Table
-- Enhanced contact details from deep scraping
-- =============================================================================
CREATE TABLE IF NOT EXISTS contact_details (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    
    -- Enhanced contact information
    primary_email VARCHAR(255),
    secondary_email VARCHAR(255),
    hr_email VARCHAR(255),
    phone_main VARCHAR(50),
    phone_hr VARCHAR(50),
    fax VARCHAR(50),
    
    -- Address information
    street_address VARCHAR(500),
    postal_code VARCHAR(20),
    city VARCHAR(255),
    country VARCHAR(100) DEFAULT 'Germany',
    
    -- Company website details
    website_url VARCHAR(500),
    career_page_url VARCHAR(500),
    application_portal_url VARCHAR(500),
    
    -- Social media and additional links
    linkedin_url VARCHAR(500),
    xing_url VARCHAR(500),
    other_social_links TEXT[],
    
    -- Contact preferences
    preferred_contact_method VARCHAR(100), -- email, phone, online_form
    application_deadline DATE,
    response_time_days INTEGER,
    
    -- Metadata
    enhanced_at TIMESTAMPTZ DEFAULT NOW(),
    source_method VARCHAR(100), -- manual, auto_scrape, api
    confidence_score FLOAT DEFAULT 0.0, -- 0.0 to 1.0
    
    CONSTRAINT unique_job_contact UNIQUE(job_id)
);

CREATE INDEX IF NOT EXISTS idx_contact_job_id ON contact_details(job_id);
CREATE INDEX IF NOT EXISTS idx_contact_primary_email ON contact_details(primary_email);

-- =============================================================================
-- Scraping Sessions Table
-- Track scraping performance and sessions
-- =============================================================================
CREATE TABLE IF NOT EXISTS scraping_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_name VARCHAR(255),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status VARCHAR(50) DEFAULT 'running', -- running, completed, failed, interrupted
    
    -- Statistics
    total_urls_processed INTEGER DEFAULT 0,
    jobs_scraped INTEGER DEFAULT 0,
    captchas_encountered INTEGER DEFAULT 0,
    captchas_solved INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,
    
    -- Performance metrics
    avg_processing_time_ms FLOAT,
    total_processing_time_ms BIGINT,
    
    -- Configuration used
    scraper_config JSONB,
    error_log TEXT[],
    
    -- Batch information
    batch_files TEXT[], -- List of generated batch files
    output_directory VARCHAR(500)
);

CREATE INDEX IF NOT EXISTS idx_scraping_sessions_started ON scraping_sessions(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_scraping_sessions_status ON scraping_sessions(status);

-- =============================================================================
-- Data Quality Metrics Table
-- Track data quality and completeness
-- =============================================================================
CREATE TABLE IF NOT EXISTS data_quality_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    
    -- Field completeness (0 or 1 for each required field)
    has_profession SMALLINT DEFAULT 0,
    has_salary SMALLINT DEFAULT 0,
    has_company_name SMALLINT DEFAULT 0,
    has_location SMALLINT DEFAULT 0,
    has_start_date SMALLINT DEFAULT 0,
    has_telephone SMALLINT DEFAULT 0,
    has_email SMALLINT DEFAULT 0,
    has_job_description SMALLINT DEFAULT 0,
    has_ref_nr SMALLINT DEFAULT 0,
    has_external_link SMALLINT DEFAULT 0,
    has_application_link SMALLINT DEFAULT 0,
    
    -- Quality scores
    completeness_score FLOAT, -- 0.0 to 1.0
    content_quality_score FLOAT, -- 0.0 to 1.0 based on content length, formatting
    contact_score FLOAT, -- 0.0 to 1.0 based on contact information availability
    
    -- Validation flags
    email_valid BOOLEAN,
    phone_valid BOOLEAN,
    url_valid BOOLEAN,
    date_parseable BOOLEAN,
    
    calculated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_job_quality UNIQUE(job_id)
);

CREATE INDEX IF NOT EXISTS idx_quality_completeness ON data_quality_metrics(completeness_score DESC);
CREATE INDEX IF NOT EXISTS idx_quality_job_id ON data_quality_metrics(job_id);

-- =============================================================================
-- Views for Common Queries
-- =============================================================================

-- View for complete job information with company details
CREATE OR REPLACE VIEW jobs_complete AS
SELECT 
    j.*,
    c.domain as company_domain,
    c.industry as company_industry,
    c.size_category as company_size,
    cd.primary_email as enhanced_email,
    cd.phone_main as enhanced_phone,
    cd.website_url as company_website,
    dqm.completeness_score,
    dqm.contact_score
FROM jobs j
LEFT JOIN companies c ON j.company_id = c.id  
LEFT JOIN contact_details cd ON j.id = cd.job_id
LEFT JOIN data_quality_metrics dqm ON j.id = dqm.job_id;

-- View for jobs with missing contact information
CREATE OR REPLACE VIEW jobs_missing_contacts AS
SELECT 
    j.id,
    j.profession,
    j.company_name,
    j.location,
    j.ref_nr,
    j.source_url,
    CASE 
        WHEN j.email IS NULL AND j.telephone IS NULL THEN 'both'
        WHEN j.email IS NULL THEN 'email'
        WHEN j.telephone IS NULL THEN 'phone'
        ELSE 'none'
    END as missing_contact_type
FROM jobs j
WHERE j.email IS NULL OR j.telephone IS NULL;

-- View for data quality summary
CREATE OR REPLACE VIEW data_quality_summary AS
SELECT 
    COUNT(*) as total_jobs,
    AVG(completeness_score) as avg_completeness,
    AVG(contact_score) as avg_contact_score,
    COUNT(CASE WHEN completeness_score >= 0.8 THEN 1 END) as high_quality_jobs,
    COUNT(CASE WHEN completeness_score < 0.5 THEN 1 END) as low_quality_jobs,
    COUNT(CASE WHEN email IS NOT NULL THEN 1 END) as jobs_with_email,
    COUNT(CASE WHEN telephone IS NOT NULL THEN 1 END) as jobs_with_phone
FROM jobs_complete;

-- =============================================================================
-- Functions for Data Processing
-- =============================================================================

-- Function to calculate data quality score
CREATE OR REPLACE FUNCTION calculate_data_quality_score(job_record jobs)
RETURNS FLOAT AS $$
DECLARE
    score INTEGER := 0;
BEGIN
    -- Count non-null required fields (max 11 points)
    IF job_record.profession IS NOT NULL AND LENGTH(job_record.profession) > 0 THEN score := score + 1; END IF;
    IF job_record.salary IS NOT NULL AND LENGTH(job_record.salary) > 0 THEN score := score + 1; END IF;
    IF job_record.company_name IS NOT NULL AND LENGTH(job_record.company_name) > 0 THEN score := score + 1; END IF;
    IF job_record.location IS NOT NULL AND LENGTH(job_record.location) > 0 THEN score := score + 1; END IF;
    IF job_record.start_date IS NOT NULL AND LENGTH(job_record.start_date) > 0 THEN score := score + 1; END IF;
    IF job_record.telephone IS NOT NULL AND LENGTH(job_record.telephone) > 0 THEN score := score + 1; END IF;
    IF job_record.email IS NOT NULL AND LENGTH(job_record.email) > 0 THEN score := score + 1; END IF;
    IF job_record.job_description IS NOT NULL AND LENGTH(job_record.job_description) > 100 THEN score := score + 1; END IF;
    IF job_record.ref_nr IS NOT NULL AND LENGTH(job_record.ref_nr) > 0 THEN score := score + 1; END IF;
    IF job_record.external_link IS NOT NULL AND LENGTH(job_record.external_link) > 0 THEN score := score + 1; END IF;
    IF job_record.application_link IS NOT NULL AND LENGTH(job_record.application_link) > 0 THEN score := score + 1; END IF;
    
    RETURN score;
END;
$$ LANGUAGE plpgsql;

-- Function to update data quality metrics
CREATE OR REPLACE FUNCTION update_data_quality_metrics(target_job_id UUID)
RETURNS VOID AS $$
DECLARE
    job_record jobs;
    quality_score FLOAT;
BEGIN
    -- Get job record
    SELECT * INTO job_record FROM jobs WHERE id = target_job_id;
    
    -- Calculate quality score
    quality_score := calculate_data_quality_score(job_record);
    
    -- Insert or update quality metrics
    INSERT INTO data_quality_metrics (
        job_id, 
        has_profession, has_salary, has_company_name, has_location, has_start_date,
        has_telephone, has_email, has_job_description, has_ref_nr, 
        has_external_link, has_application_link, completeness_score
    ) VALUES (
        target_job_id,
        CASE WHEN job_record.profession IS NOT NULL AND LENGTH(job_record.profession) > 0 THEN 1 ELSE 0 END,
        CASE WHEN job_record.salary IS NOT NULL AND LENGTH(job_record.salary) > 0 THEN 1 ELSE 0 END,
        CASE WHEN job_record.company_name IS NOT NULL AND LENGTH(job_record.company_name) > 0 THEN 1 ELSE 0 END,
        CASE WHEN job_record.location IS NOT NULL AND LENGTH(job_record.location) > 0 THEN 1 ELSE 0 END,
        CASE WHEN job_record.start_date IS NOT NULL AND LENGTH(job_record.start_date) > 0 THEN 1 ELSE 0 END,
        CASE WHEN job_record.telephone IS NOT NULL AND LENGTH(job_record.telephone) > 0 THEN 1 ELSE 0 END,
        CASE WHEN job_record.email IS NOT NULL AND LENGTH(job_record.email) > 0 THEN 1 ELSE 0 END,
        CASE WHEN job_record.job_description IS NOT NULL AND LENGTH(job_record.job_description) > 100 THEN 1 ELSE 0 END,
        CASE WHEN job_record.ref_nr IS NOT NULL AND LENGTH(job_record.ref_nr) > 0 THEN 1 ELSE 0 END,
        CASE WHEN job_record.external_link IS NOT NULL AND LENGTH(job_record.external_link) > 0 THEN 1 ELSE 0 END,
        CASE WHEN job_record.application_link IS NOT NULL AND LENGTH(job_record.application_link) > 0 THEN 1 ELSE 0 END,
        quality_score / 11.0
    ) ON CONFLICT (job_id) DO UPDATE SET
        has_profession = EXCLUDED.has_profession,
        has_salary = EXCLUDED.has_salary,
        has_company_name = EXCLUDED.has_company_name,
        has_location = EXCLUDED.has_location,
        has_start_date = EXCLUDED.has_start_date,
        has_telephone = EXCLUDED.has_telephone,
        has_email = EXCLUDED.has_email,
        has_job_description = EXCLUDED.has_job_description,
        has_ref_nr = EXCLUDED.has_ref_nr,
        has_external_link = EXCLUDED.has_external_link,
        has_application_link = EXCLUDED.has_application_link,
        completeness_score = EXCLUDED.completeness_score,
        calculated_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Triggers for Automatic Data Quality Updates
-- =============================================================================

-- Trigger to automatically update data quality when job is inserted/updated
CREATE OR REPLACE FUNCTION trigger_update_data_quality_before()
RETURNS TRIGGER AS $$
BEGIN
    -- Update the data_quality_score in jobs table
    NEW.data_quality_score := calculate_data_quality_score(NEW);
    
    -- Update last_updated timestamp
    NEW.last_updated := NOW();
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION trigger_update_data_quality_after()
RETURNS TRIGGER AS $$
BEGIN
    -- Update quality metrics after the job is inserted
    PERFORM update_data_quality_metrics(NEW.id);
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_jobs_quality_update_before
    BEFORE INSERT OR UPDATE ON jobs
    FOR EACH ROW
    EXECUTE FUNCTION trigger_update_data_quality_before();

CREATE TRIGGER trigger_jobs_quality_update_after
    AFTER INSERT OR UPDATE ON jobs
    FOR EACH ROW
    EXECUTE FUNCTION trigger_update_data_quality_after();

-- =============================================================================
-- Schema version tracking
-- =============================================================================
CREATE TABLE IF NOT EXISTS schema_version (
    version VARCHAR(10) PRIMARY KEY,
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    description TEXT
);

INSERT INTO schema_version (version, description) 
VALUES ('1.0.0', 'Initial schema with jobs, companies, contacts, sessions and quality metrics')
ON CONFLICT (version) DO NOTHING;