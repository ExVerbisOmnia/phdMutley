-- migrate_run_state_add_prefilter.sql
-- Adds the 'prefiltered' status + audit columns to citation_agent_v1_run_state.
--
-- After execution, move this file to scripts/0-initialize-database/ alongside
-- the other migration SQL.
--
-- Idempotent: safe to re-run.

BEGIN;

ALTER TABLE citation_agent_v1_run_state
    DROP CONSTRAINT IF EXISTS citation_agent_v1_run_state_status_check;

ALTER TABLE citation_agent_v1_run_state
    ADD CONSTRAINT citation_agent_v1_run_state_status_check
    CHECK (status IN (
        'pending',
        'in_progress',
        'complete',
        'failed',
        'skipped',
        'prefiltered'
    ));

ALTER TABLE citation_agent_v1_run_state
    ADD COLUMN IF NOT EXISTS prefilter_reason TEXT,
    ADD COLUMN IF NOT EXISTS prefilter_confidence NUMERIC(3,2),
    ADD COLUMN IF NOT EXISTS prefilter_signals JSONB;

COMMENT ON COLUMN citation_agent_v1_run_state.prefilter_reason
    IS 'Haiku pre-filter justification (one-sentence). Populated when status=prefiltered.';
COMMENT ON COLUMN citation_agent_v1_run_state.prefilter_confidence
    IS 'Haiku pre-filter confidence in [0.00, 1.00]. Bypass threshold = 0.90.';
COMMENT ON COLUMN citation_agent_v1_run_state.prefilter_signals
    IS 'JSONB array of signal slugs the pre-filter observed (audit trail).';

COMMIT;
