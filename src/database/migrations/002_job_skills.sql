-- Migration: Add job_skills table for NER-extracted skills
-- Run after 001_ml_categorization.sql

BEGIN;

-- Normalized skills table (one row per job×skill)
CREATE TABLE IF NOT EXISTS job_skills (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id      UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    skill       VARCHAR(128) NOT NULL,    -- canonical name: "Python", "Führerschein B"
    category    VARCHAR(48)  NOT NULL,    -- "programming", "certification", "language", etc.
    mentions    SMALLINT     NOT NULL DEFAULT 1,
    context     TEXT,                     -- snippet where first found
    extracted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- prevent duplicate skill per job
    CONSTRAINT uq_job_skill UNIQUE (job_id, skill)
);

-- Fast lookups
CREATE INDEX IF NOT EXISTS idx_job_skills_job    ON job_skills (job_id);
CREATE INDEX IF NOT EXISTS idx_job_skills_skill  ON job_skills (skill);
CREATE INDEX IF NOT EXISTS idx_job_skills_cat    ON job_skills (category);

-- For aggregation queries
CREATE INDEX IF NOT EXISTS idx_job_skills_skill_cat ON job_skills (skill, category);

-- Track which jobs have been skill-extracted
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS skills_extracted BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_jobs_skills_extracted
    ON jobs (skills_extracted) WHERE skills_extracted = FALSE;

-- Update schema version
INSERT INTO schema_version (version, description, applied_at)
VALUES (3, 'Add job_skills table for NER extraction', NOW())
ON CONFLICT DO NOTHING;

COMMIT;
