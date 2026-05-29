-- Migration: Add text quality flags and verification summary columns
-- Run: psql -U phdmutley -p 5433 -d climate_litigation -f scripts/0-initialize-database/add_quality_columns.sql

BEGIN;

-- Document quality flags (computed during text extraction)
ALTER TABLE documents ADD COLUMN IF NOT EXISTS is_garbled BOOLEAN;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS is_too_long BOOLEAN;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS text_char_count INTEGER;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS text_token_estimate INTEGER;

COMMENT ON COLUMN documents.is_garbled IS 'True if text appears garbled/corrupted';
COMMENT ON COLUMN documents.is_too_long IS 'True if text exceeds model token limit';
COMMENT ON COLUMN documents.text_char_count IS 'Character count of extracted text';
COMMENT ON COLUMN documents.text_token_estimate IS 'Estimated token count (~chars/4)';

-- Verification summary columns on citation_extraction_phased_summary
ALTER TABLE citation_extraction_phased_summary ADD COLUMN IF NOT EXISTS verified_confirmed INTEGER DEFAULT 0;
ALTER TABLE citation_extraction_phased_summary ADD COLUMN IF NOT EXISTS verified_not_found INTEGER DEFAULT 0;
ALTER TABLE citation_extraction_phased_summary ADD COLUMN IF NOT EXISTS verified_misattributed INTEGER DEFAULT 0;
ALTER TABLE citation_extraction_phased_summary ADD COLUMN IF NOT EXISTS verified_skipped INTEGER DEFAULT 0;
ALTER TABLE citation_extraction_phased_summary ADD COLUMN IF NOT EXISTS verification_cost_usd DECIMAL(10,4) DEFAULT 0.0;

COMMENT ON COLUMN citation_extraction_phased_summary.verified_confirmed IS 'Citations verified as CONFIRMED';
COMMENT ON COLUMN citation_extraction_phased_summary.verified_not_found IS 'Citations verified as NOT_FOUND';
COMMENT ON COLUMN citation_extraction_phased_summary.verified_misattributed IS 'Citations verified as MISATTRIBUTED';
COMMENT ON COLUMN citation_extraction_phased_summary.verified_skipped IS 'Citations skipped (garbled/too long)';
COMMENT ON COLUMN citation_extraction_phased_summary.verification_cost_usd IS 'Cost of verification API calls';

-- Indexes for new quality columns
CREATE INDEX IF NOT EXISTS idx_documents_is_garbled ON documents(is_garbled) WHERE is_garbled = TRUE;
CREATE INDEX IF NOT EXISTS idx_documents_is_too_long ON documents(is_too_long) WHERE is_too_long = TRUE;

-- Additional indexes for analysis engine performance (Step 2C preview)
CREATE INDEX IF NOT EXISTS idx_cep_source_case_law_region
    ON citation_extraction_phased(source_region, case_law_region);
CREATE INDEX IF NOT EXISTS idx_cep_verification_status
    ON citation_extraction_phased(verification_status);
CREATE INDEX IF NOT EXISTS idx_cep_source_origin
    ON citation_extraction_phased(source_jurisdiction, case_law_origin);
CREATE INDEX IF NOT EXISTS idx_cep_sabin_cited
    ON citation_extraction_phased(sabin_case_id_cited) WHERE sabin_case_id_cited IS NOT NULL;

COMMIT;
