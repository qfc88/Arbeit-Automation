-- Temporarily disable the trigger that's causing foreign key errors
-- This will help us see the actual job insertion error

-- Disable trigger
DROP TRIGGER IF EXISTS trigger_jobs_quality_update ON jobs;

-- Test query
SELECT 'Trigger disabled - now we can see the real job insertion error!' as status;