-- Phase V: Citation Verification Pipeline
-- Adds verification columns to citation_extraction_phased
-- Safe to run multiple times (IF NOT EXISTS)

ALTER TABLE citation_extraction_phased
    ADD COLUMN IF NOT EXISTS verification_status VARCHAR(20),
    ADD COLUMN IF NOT EXISTS verification_snippet TEXT,
    ADD COLUMN IF NOT EXISTS verification_notes TEXT,
    ADD COLUMN IF NOT EXISTS verification_model VARCHAR(50),
    ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_cep_verification_status
    ON citation_extraction_phased(verification_status);

COMMENT ON COLUMN citation_extraction_phased.verification_status IS 'CONFIRMED, NOT_FOUND, or MISATTRIBUTED';
COMMENT ON COLUMN citation_extraction_phased.verification_snippet IS 'Raw LLM verbatim quote (before fuzzy matching)';
COMMENT ON COLUMN citation_extraction_phased.verification_notes IS 'LLM notes on the verification result';
COMMENT ON COLUMN citation_extraction_phased.verification_model IS 'Model used for verification';
COMMENT ON COLUMN citation_extraction_phased.verified_at IS 'Timestamp of verification';
