-- 004_add_prefilter_keep.sql
-- Adds 'prefilter_keep' to the citation_agent_v1_run_state.status enum.
--
-- Context: --prefilter-only mode previously released "keep" verdicts back to
-- 'pending', which let the same docs be re-claimed within the same run
-- (infinite loop on the lowest-word-count docs). The new status records the
-- triage outcome persistently:
--   - 'prefiltered'    : Haiku said "no citations, conf >= threshold" → bypass Sonnet
--   - 'prefilter_keep' : Haiku said "keep" (has_citations or conf < threshold)
--                        → full pipeline still owes work; not re-claimed by
--                          another --prefilter-only pass.
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
        'prefiltered',
        'prefilter_keep'
    ));

COMMENT ON COLUMN citation_agent_v1_run_state.status
    IS 'Lifecycle status. prefiltered = Haiku bypassed extractor; prefilter_keep = Haiku triaged as worth running through extractor (claimed by full-pipeline runs alongside pending).';

COMMIT;
