-- Fix for foreign key constraint violation in data_quality_metrics table
-- The issue is that the trigger was trying to insert into data_quality_metrics
-- before the job was actually inserted into the jobs table

-- Drop existing trigger and function
DROP TRIGGER IF EXISTS trigger_jobs_quality_update ON jobs;
DROP FUNCTION IF EXISTS trigger_update_data_quality();

-- Create separate BEFORE and AFTER trigger functions
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

-- Create BEFORE trigger for job data updates
CREATE TRIGGER trigger_jobs_quality_update_before
    BEFORE INSERT OR UPDATE ON jobs
    FOR EACH ROW
    EXECUTE FUNCTION trigger_update_data_quality_before();

-- Create AFTER trigger for quality metrics insertion
CREATE TRIGGER trigger_jobs_quality_update_after
    AFTER INSERT OR UPDATE ON jobs
    FOR EACH ROW
    EXECUTE FUNCTION trigger_update_data_quality_after();