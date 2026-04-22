--
-- Migration 001: ML categorization columns + feedback table
--
-- Pha 3.4 adds industry-category classification (IT / Sales / Healthcare / ...)
-- Jobs are labelled by the ml-inference service; admins can override via the
-- dashboard, and the feedback loop retrains offline.
--
-- Safe to run repeatedly (IF NOT EXISTS everywhere).
--

BEGIN;

ALTER TABLE jobs
    ADD COLUMN IF NOT EXISTS predicted_category VARCHAR(64),
    ADD COLUMN IF NOT EXISTS category_confidence NUMERIC(3,2),
    ADD COLUMN IF NOT EXISTS category_source VARCHAR(16) DEFAULT 'ml'
        CHECK (category_source IN ('ml', 'human_override'));

CREATE INDEX IF NOT EXISTS idx_jobs_predicted_category
    ON jobs (predicted_category)
    WHERE predicted_category IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_jobs_low_confidence
    ON jobs (category_confidence)
    WHERE category_confidence IS NOT NULL AND category_confidence < 0.6;

CREATE TABLE IF NOT EXISTS ml_feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    predicted_category VARCHAR(64),
    predicted_confidence NUMERIC(3,2),
    corrected_category VARCHAR(64) NOT NULL,
    corrected_by VARCHAR(64) NOT NULL,
    corrected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_ml_feedback_job_id ON ml_feedback (job_id);
CREATE INDEX IF NOT EXISTS idx_ml_feedback_corrected_at ON ml_feedback (corrected_at DESC);

-- Rebuild jobs_complete view to expose the new columns for the API.
DROP VIEW IF EXISTS jobs_complete CASCADE;
CREATE VIEW jobs_complete AS
SELECT
    j.*,
    c.domain       AS company_domain,
    c.industry     AS company_industry,
    c.size_category AS company_size,
    cd.primary_email AS enhanced_email,
    cd.phone_main    AS enhanced_phone,
    cd.website_url   AS company_website,
    dqm.completeness_score,
    dqm.contact_score
FROM jobs j
LEFT JOIN companies c           ON j.company_id = c.id
LEFT JOIN contact_details cd    ON j.id = cd.job_id
LEFT JOIN data_quality_metrics dqm ON j.id = dqm.job_id;

COMMIT;
