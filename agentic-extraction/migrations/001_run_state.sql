-- ============================================================================
-- DATABASE SCHEMA MIGRATION — Citation Agent v1 Run State (orchestration)
-- ============================================================================
-- Purpose:  Tracks the per-document state of the corpus-run orchestrator
--           (T16). One row per document; the orchestrator reads this table
--           to decide what to process next, and updates it as work progresses.
--
-- Date:     2026-05-03
-- Version:  agent v1 / orchestrator v1
-- Author:   Gus
--
-- Context:
--   See `docs/plans/corpus-orchestrator-plan.md` for the full design.
--   Per Gus's hard requirement (2026-05-03): a document interrupted
--   mid-extraction must be re-run from scratch on resume, overriding any
--   partial entries. This table is the resume mechanism — combined with
--   idempotent DELETEs of `citation_agent_v1*` rows for the affected docs.
--
-- Idempotency:
--   `CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS`. Safe to
--   run multiple times; a second run is a no-op.
--
-- Seeding:
--   This file does NOT seed rows — that's done separately by the
--   orchestrator's startup phase (or by a manual `INSERT … FROM documents`
--   query — see end of file for the canonical seeding statement).
-- ============================================================================

BEGIN;

-- ============================================================================
-- TABLE — citation_agent_v1_run_state
-- ============================================================================

CREATE TABLE IF NOT EXISTS citation_agent_v1_run_state (
    document_id           UUID            PRIMARY KEY
        REFERENCES documents(document_id) ON DELETE CASCADE,

    -- ------------------------------------------------------------------------
    -- Lifecycle status
    --   pending      — seeded, never attempted
    --   in_progress  — currently being processed (or was, when prev session died)
    --   complete     — extracted + verified + ingested successfully
    --   failed       — terminal error after retries
    --   skipped      — manually excluded (e.g., known-bad doc)
    -- ------------------------------------------------------------------------
    status                VARCHAR(20)     NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'complete', 'failed', 'skipped')),

    -- ------------------------------------------------------------------------
    -- Tier classification (per D32: 1 ≤ 25K words, 2 ≤ 100K words, 3 > 100K words)
    -- ------------------------------------------------------------------------
    tier                  SMALLINT
        CHECK (tier IN (1, 2, 3)),

    -- Word count copied from extracted_text for query convenience without join
    word_count            INTEGER,

    -- ------------------------------------------------------------------------
    -- Attempt tracking
    -- ------------------------------------------------------------------------
    attempts              SMALLINT        NOT NULL DEFAULT 0,
    last_attempt_started  TIMESTAMP,
    last_attempt_finished TIMESTAMP,

    -- ------------------------------------------------------------------------
    -- Output artifact paths (filesystem paths, relative to project root)
    -- ------------------------------------------------------------------------
    extract_path          TEXT,           -- data/extraction_results/{doc_id}_extracted.json
    verify_path           TEXT,           -- data/extraction_results/{doc_id}_verified.json

    -- ------------------------------------------------------------------------
    -- Result counts (populated on `complete`; null otherwise)
    -- ------------------------------------------------------------------------
    citations_extracted   INTEGER,        -- raw count from extractor
    citations_verified    INTEGER,        -- count after verifier (CONFIRMED only)
    citations_dismissed   INTEGER,        -- D31 soft-tag count
    citations_vertical    INTEGER,        -- D30 is_vertical_dialogue=true count

    -- ------------------------------------------------------------------------
    -- Diagnostics
    -- ------------------------------------------------------------------------
    error_message         TEXT,           -- last error if failed/in_progress reset
    notes                 TEXT,           -- agent's brief summary, observations

    -- ------------------------------------------------------------------------
    -- Audit
    -- ------------------------------------------------------------------------
    created_at            TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMP       NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  citation_agent_v1_run_state              IS 'Orchestrator state — one row per document, drives the corpus-run loop and supports resume-from-interruption.';
COMMENT ON COLUMN citation_agent_v1_run_state.document_id  IS 'FK to documents.document_id';
COMMENT ON COLUMN citation_agent_v1_run_state.status       IS 'Lifecycle: pending → in_progress → (complete | failed); skipped = manual exclusion';
COMMENT ON COLUMN citation_agent_v1_run_state.tier         IS 'D32 chunking tier (1 single-pass / 2 progressive / 3 pre-split-and-merge)';
COMMENT ON COLUMN citation_agent_v1_run_state.attempts     IS 'How many times this doc has been attempted; default retry cap is 2';
COMMENT ON COLUMN citation_agent_v1_run_state.error_message IS 'Last error message; cleared on successful complete';

-- ============================================================================
-- INDEXES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_run_state_status
    ON citation_agent_v1_run_state(status);

CREATE INDEX IF NOT EXISTS idx_run_state_tier
    ON citation_agent_v1_run_state(tier);

-- Composite for the orchestrator's "what to process next" query
CREATE INDEX IF NOT EXISTS idx_run_state_pending_by_tier
    ON citation_agent_v1_run_state(tier, attempts)
    WHERE status = 'pending';

-- For monitoring failed-doc reports
CREATE INDEX IF NOT EXISTS idx_run_state_failed
    ON citation_agent_v1_run_state(last_attempt_finished)
    WHERE status = 'failed';

-- ============================================================================
-- TRIGGER — auto-update updated_at on row changes
-- ============================================================================

CREATE OR REPLACE FUNCTION run_state_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_run_state_updated_at ON citation_agent_v1_run_state;
CREATE TRIGGER trg_run_state_updated_at
    BEFORE UPDATE ON citation_agent_v1_run_state
    FOR EACH ROW
    EXECUTE FUNCTION run_state_set_updated_at();

COMMIT;

-- ============================================================================
-- SEEDING (run separately when the orchestrator first starts)
-- ============================================================================
-- Filters:
--   1. raw_text NOT NULL and not empty (LENGTH > 0)         — must have content
--   2. word_count >= 100                                    — must have enough
--                                                            content for meaningful
--                                                            extraction (per
--                                                            citation-extractor.md
--                                                            §2 quality pre-check)
--   3. is_decision = TRUE                                   — only judicial
--                                                            decisions (excludes
--                                                            briefs, indices, etc.)
--   4. NOT is_garbled                                       — text quality OK
--
-- The CASE WHEN uses BETWEEN-style explicit bounds so NULL word_count NEVER
-- silently falls into Tier 3 (we hit this bug on first seeding 2026-05-03 —
-- 164 empty-content docs got mis-classified as Tier 3 because NULL <= 25000
-- evaluates to NULL, falling through to ELSE).
--
-- INSERT INTO citation_agent_v1_run_state (document_id, status, tier, word_count)
-- SELECT
--     d.document_id,
--     'pending',
--     CASE
--         WHEN et.word_count <= 25000  THEN 1
--         WHEN et.word_count <= 100000 THEN 2
--         WHEN et.word_count > 100000  THEN 3
--         -- NULL word_count would land here; should be filtered upstream
--     END AS tier,
--     et.word_count
-- FROM documents d
-- JOIN extracted_text et ON et.document_id = d.document_id
-- WHERE et.raw_text IS NOT NULL
--   AND LENGTH(et.raw_text) > 0
--   AND et.word_count IS NOT NULL
--   AND et.word_count >= 100
--   AND d.is_decision = TRUE
--   AND COALESCE(d.is_garbled, FALSE) = FALSE
-- ON CONFLICT (document_id) DO NOTHING;
--
-- After seeding, mark short/empty docs as skipped (defense-in-depth):
-- UPDATE citation_agent_v1_run_state rs
-- SET status = 'skipped',
--     tier   = NULL,
--     notes  = 'word_count < 100 or empty raw_text — insufficient content'
-- FROM extracted_text et
-- WHERE rs.document_id = et.document_id
--   AND rs.status = 'pending'
--   AND (et.word_count IS NULL OR et.word_count < 100 OR LENGTH(et.raw_text) = 0);

-- ============================================================================
-- RESUME-FROM-INTERRUPTION (orchestrator startup hook)
-- ============================================================================
-- Per Gus 2026-05-03: an interrupted doc must be re-run from scratch.
-- The orchestrator runs this on every startup before picking up new work.
--
-- UPDATE citation_agent_v1_run_state
-- SET status = 'pending',
--     error_message = COALESCE(error_message, '') ||
--                     '; reset from in_progress on resume at ' || NOW()::TEXT
-- WHERE status = 'in_progress';
--
-- DELETE FROM citation_agent_v1_summary
-- WHERE document_id IN (
--     SELECT document_id FROM citation_agent_v1_run_state
--     WHERE status = 'pending' AND error_message LIKE '%reset from in_progress%'
-- );
--
-- DELETE FROM citation_agent_v1
-- WHERE document_id IN (
--     SELECT document_id FROM citation_agent_v1_run_state
--     WHERE status = 'pending' AND error_message LIKE '%reset from in_progress%'
-- );
