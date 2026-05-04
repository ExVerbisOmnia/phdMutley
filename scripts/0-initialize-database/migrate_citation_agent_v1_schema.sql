-- ============================================================================
-- DATABASE SCHEMA MIGRATION — Citation Agent v1 (D37 fresh dataset)
-- ============================================================================
-- Purpose:  Create the new tables that hold the 2-agent (extractor + verifier)
--           pipeline output, alongside the frozen v7 baseline tables.
--
-- Date:     2026-05-03
-- Version:  agent v1
-- Author:   Gus
--
-- Context (D37):
--   The v7 pipeline output (`citation_extraction_phased`,
--   `citation_extraction_phased_summary`, view `citation_sixfold_classification`)
--   is FROZEN as a methodological baseline. The agent pipeline writes to a
--   parallel set of tables in the same database. Both are queryable; the
--   methodology section reports both with the delta.
--
-- Tables created:
--   - citation_agent_v1            (per-citation, mirrors citation_extraction_phased)
--   - citation_agent_v1_summary    (per-document, mirrors *_summary)
--   - citation_sixfold_agent_v1    (VIEW over citation_agent_v1; mirrors the
--                                   v7 sixfold view pattern — see Section "Why
--                                   a view, not a table" below.)
--
-- Key new fields beyond v7 (every per-citation row):
--   - is_vertical_dialogue BOOLEAN NOT NULL  (D30)
--   - functional_use TEXT with extended CHECK incl. 'dismissed' (D31)
--   - verification_verdict TEXT with CHECK incl. NOT_A_CASE, DUPLICATE
--   - sixfold_type TEXT with CHECK incl. 'Domestic' (D29) and 'Unclassified'
--   - source_year, verbatim_snippet, opinion_type, citation_pattern,
--     functional_use_confidence, is_duplicate_of, case_number, etc.
--
-- Idempotency:
--   This migration uses `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT
--   EXISTS`, and `CREATE OR REPLACE VIEW`/FUNCTION/TRIGGER patterns and is
--   safe to run multiple times.
--
-- Convention sources:
--   - PK type & FK pattern follow `migrate_citation_phased_schema.sql`
--     (UUID + gen_random_uuid(), CASCADE on delete).
--   - case_id column type matches the v7 `citation_extraction_phased`
--     SQLAlchemy model (String(100)) so the FK lines up with `cases.case_id`.
--     The legacy `migrate_citation_phased_schema.sql` SQL-level DDL
--     mistakenly typed it as UUID, but the SQLAlchemy model and live DB use
--     VARCHAR(100). T13 will rationalize the project-wide UUID strategy
--     separately; this migration deliberately mirrors the v7 live state.
--   - Indexes mirror v7 plus new fields (is_vertical_dialogue,
--     verification_verdict, sixfold_type, functional_use).
--   - COMMENT ON every column to keep the schema self-documenting.
-- ============================================================================

BEGIN;

-- ============================================================================
-- TABLE 1 — citation_agent_v1
-- One row per extracted citation. 1:1 with each object in the verifier
-- output's `citations[]` array (see citation-verifier.md §12).
-- ============================================================================

CREATE TABLE IF NOT EXISTS citation_agent_v1 (
    -- Primary Key (same convention as v7: UUID + gen_random_uuid())
    extraction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- ------------------------------------------------------------------------
    -- Foreign keys & document/case linkage
    -- ------------------------------------------------------------------------
    document_id UUID NOT NULL
        REFERENCES documents(document_id) ON DELETE CASCADE,
    case_id VARCHAR(100)
        REFERENCES cases(case_id) ON DELETE CASCADE,

    -- Verifier-output position (1-based index within the citations[] array)
    citation_index INTEGER NOT NULL,

    -- ------------------------------------------------------------------------
    -- Source metadata (lifted from frontmatter — verifier echoes these on
    -- every per-document JSON, replicated per row for query convenience)
    -- ------------------------------------------------------------------------
    source_jurisdiction VARCHAR(300),
    source_region VARCHAR(50),       -- 'Global North' | 'Global South' | 'International'
    source_year INTEGER,             -- Document year per D35 (header-extracted)

    -- ------------------------------------------------------------------------
    -- Verification verdict (verifier §3)
    -- ------------------------------------------------------------------------
    verification_verdict VARCHAR(20) NOT NULL,
    CONSTRAINT chk_cav1_verdict CHECK (verification_verdict IN (
        'CONFIRMED', 'NOT_FOUND', 'MISATTRIBUTED', 'NOT_A_CASE', 'DUPLICATE'
    )),

    -- ------------------------------------------------------------------------
    -- Citation core fields (verifier §12)
    -- ------------------------------------------------------------------------
    case_name VARCHAR(500),
    raw_text TEXT,                   -- The verbatim citation string from the doc
    verbatim_snippet TEXT,           -- 1–3 sentences of context (CONFIRMED only)
    cited_court VARCHAR(500),
    case_number VARCHAR(500),
    cited_year INTEGER,
    citation_pattern VARCHAR(100),   -- traditional | narrative | shorthand | scholarly | ...

    -- Extractor confidence (Agent 1's score; verifier may carry it through)
    confidence DECIMAL(3, 2),

    -- ------------------------------------------------------------------------
    -- Functional use (Nollkaemper typology + D31 'dismissed')
    -- ------------------------------------------------------------------------
    functional_use VARCHAR(20),
    CONSTRAINT chk_cav1_functional_use CHECK (
        functional_use IS NULL OR functional_use IN (
            'aligned', 'contested', 'avoided', 'invoked', 'dismissed'
        )
    ),
    functional_use_confidence DECIMAL(3, 2),

    -- Opinion type the citation appears in
    opinion_type VARCHAR(20),
    CONSTRAINT chk_cav1_opinion_type CHECK (
        opinion_type IS NULL OR opinion_type IN (
            'majority', 'dissent', 'concurrence', 'unclear'
        )
    ),

    -- ------------------------------------------------------------------------
    -- Origin identification (verifier §5)
    -- ------------------------------------------------------------------------
    origin_country VARCHAR(200),
    origin_region VARCHAR(50),       -- 'Global North' | 'Global South' | 'International' | 'Domestic'
    origin_court VARCHAR(500),

    -- ------------------------------------------------------------------------
    -- Sixfold classification (verifier §7) + D29 + D30
    -- ------------------------------------------------------------------------
    sixfold_type VARCHAR(50),
    CONSTRAINT chk_cav1_sixfold_type CHECK (
        sixfold_type IS NULL OR sixfold_type IN (
            'Foreign Citation',
            'International Citation',
            'Foreign International Citation',
            'Inter-System Citation',
            'Member-State Citation',
            'Non-Member Citation',
            'Domestic',
            'Unclassified'
        )
    ),

    -- D30 — vertical dialogue boolean. NOT NULL: verifier guarantees this on
    -- every citation, defaulting to false for non-CONFIRMED or non-Type-2
    -- rows.
    is_vertical_dialogue BOOLEAN NOT NULL DEFAULT FALSE,

    -- ------------------------------------------------------------------------
    -- Quality control / manual review
    -- ------------------------------------------------------------------------
    requires_manual_review BOOLEAN DEFAULT FALSE,
    manual_review_reason TEXT,
    reviewed_by VARCHAR(100),
    reviewed_at TIMESTAMP,

    -- D22 dedup pointer: when verdict = 'DUPLICATE', this is the
    -- citation_index of the primary citation (within the same document).
    -- NULL for non-duplicate rows.
    is_duplicate_of INTEGER,

    -- Verifier free-form notes (e.g., "Agent 1 confidence was 0.45...")
    verification_notes TEXT,
    verification_timestamp TIMESTAMP,

    -- ------------------------------------------------------------------------
    -- Processing metadata
    -- ------------------------------------------------------------------------
    extractor_model VARCHAR(50),     -- e.g., 'claude-haiku-4.5'
    verifier_model VARCHAR(50),      -- e.g., 'claude-opus-4.7'
    extraction_run_id VARCHAR(50),   -- Batch identifier for grouping

    -- ------------------------------------------------------------------------
    -- System metadata
    -- ------------------------------------------------------------------------
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- One verifier-output position per document
    CONSTRAINT uq_cav1_doc_idx UNIQUE (document_id, citation_index)
);

-- ----------------------------------------------------------------------------
-- COMMENT ON columns (citation_agent_v1)
-- ----------------------------------------------------------------------------
COMMENT ON TABLE  citation_agent_v1
    IS 'Per-citation output of the 2-agent pipeline (extractor + verifier). Parallel to v7 citation_extraction_phased; v7 frozen as baseline (D37).';

COMMENT ON COLUMN citation_agent_v1.extraction_id          IS 'Auto-generated UUID PK';
COMMENT ON COLUMN citation_agent_v1.document_id            IS 'FK to documents.document_id (CASCADE)';
COMMENT ON COLUMN citation_agent_v1.case_id                IS 'FK to cases.case_id (VARCHAR — matches v7 live schema)';
COMMENT ON COLUMN citation_agent_v1.citation_index         IS '1-based position in the verifier JSON citations[] array';
COMMENT ON COLUMN citation_agent_v1.source_jurisdiction    IS 'Citing court jurisdiction (from frontmatter)';
COMMENT ON COLUMN citation_agent_v1.source_region          IS 'Citing court region: Global North | Global South | International';
COMMENT ON COLUMN citation_agent_v1.source_year            IS 'Document year (D35 header-extracted, fallback case_number/case_filing_year)';
COMMENT ON COLUMN citation_agent_v1.verification_verdict   IS 'CONFIRMED | NOT_FOUND | MISATTRIBUTED | NOT_A_CASE | DUPLICATE';
COMMENT ON COLUMN citation_agent_v1.case_name              IS 'Cited case name as verified';
COMMENT ON COLUMN citation_agent_v1.raw_text               IS 'Verbatim citation text from the source document';
COMMENT ON COLUMN citation_agent_v1.verbatim_snippet       IS '1–3 sentence context snippet (CONFIRMED only); exact substring of doc';
COMMENT ON COLUMN citation_agent_v1.cited_court            IS 'Court that issued the cited decision';
COMMENT ON COLUMN citation_agent_v1.case_number            IS 'Cited case docket/reference number (e.g., 19/00135)';
COMMENT ON COLUMN citation_agent_v1.cited_year             IS 'Year the cited decision was issued';
COMMENT ON COLUMN citation_agent_v1.citation_pattern       IS 'Citation format: traditional | narrative | shorthand | scholarly | procedural | comparative | parallel_citations | ...';
COMMENT ON COLUMN citation_agent_v1.confidence             IS 'Agent 1 extraction confidence 0.00–1.00';
COMMENT ON COLUMN citation_agent_v1.functional_use         IS 'Nollkaemper typology + D31: aligned|contested|avoided|invoked|dismissed';
COMMENT ON COLUMN citation_agent_v1.functional_use_confidence IS 'Verifier confidence in the functional_use label 0.00–1.00';
COMMENT ON COLUMN citation_agent_v1.opinion_type           IS 'Opinion the citation appears in: majority|dissent|concurrence|unclear';
COMMENT ON COLUMN citation_agent_v1.origin_country         IS 'Identified country of the cited court';
COMMENT ON COLUMN citation_agent_v1.origin_region          IS 'Region of the cited court: Global North | Global South | International | Domestic';
COMMENT ON COLUMN citation_agent_v1.origin_court           IS 'Identified court of origin';
COMMENT ON COLUMN citation_agent_v1.sixfold_type           IS 'Sixfold classification + Domestic (D29) + Unclassified';
COMMENT ON COLUMN citation_agent_v1.is_vertical_dialogue   IS 'D30: TRUE iff source = national court AND cited = international court of which source country is a member';
COMMENT ON COLUMN citation_agent_v1.requires_manual_review IS 'Verifier flagged this citation for human review';
COMMENT ON COLUMN citation_agent_v1.manual_review_reason   IS 'Why review is required (e.g., NOT_FOUND, low origin_confidence)';
COMMENT ON COLUMN citation_agent_v1.reviewed_by            IS 'Reviewer name (post-pipeline manual review workflow)';
COMMENT ON COLUMN citation_agent_v1.reviewed_at            IS 'Timestamp of manual review';
COMMENT ON COLUMN citation_agent_v1.is_duplicate_of        IS 'D22 dedup: when verdict=DUPLICATE, citation_index of the primary mention in the same document';
COMMENT ON COLUMN citation_agent_v1.verification_notes     IS 'Free-form verifier notes on the verdict / classification';
COMMENT ON COLUMN citation_agent_v1.verification_timestamp IS 'When verifier produced this row (from JSON top-level field)';
COMMENT ON COLUMN citation_agent_v1.extractor_model        IS 'Agent 1 model identifier';
COMMENT ON COLUMN citation_agent_v1.verifier_model         IS 'Agent 2 model identifier';
COMMENT ON COLUMN citation_agent_v1.extraction_run_id      IS 'Batch identifier for grouping a pipeline run';

-- ----------------------------------------------------------------------------
-- Indexes (citation_agent_v1)
-- Mirror v7's index set; add indexes for the new agent-pipeline fields.
-- ----------------------------------------------------------------------------

-- v7-equivalent indexes
CREATE INDEX IF NOT EXISTS idx_cav1_document_id
    ON citation_agent_v1(document_id);
CREATE INDEX IF NOT EXISTS idx_cav1_case_id
    ON citation_agent_v1(case_id);
CREATE INDEX IF NOT EXISTS idx_cav1_origin_country
    ON citation_agent_v1(origin_country);
CREATE INDEX IF NOT EXISTS idx_cav1_source_jurisdiction
    ON citation_agent_v1(source_jurisdiction);
CREATE INDEX IF NOT EXISTS idx_cav1_review
    ON citation_agent_v1(requires_manual_review)
    WHERE requires_manual_review = TRUE;
CREATE INDEX IF NOT EXISTS idx_cav1_source_origin_region
    ON citation_agent_v1(source_region, origin_region);

-- New indexes for the v1-specific fields
CREATE INDEX IF NOT EXISTS idx_cav1_verdict
    ON citation_agent_v1(verification_verdict);
CREATE INDEX IF NOT EXISTS idx_cav1_sixfold_type
    ON citation_agent_v1(sixfold_type);
CREATE INDEX IF NOT EXISTS idx_cav1_functional_use
    ON citation_agent_v1(functional_use);
CREATE INDEX IF NOT EXISTS idx_cav1_vertical_dialogue
    ON citation_agent_v1(is_vertical_dialogue)
    WHERE is_vertical_dialogue = TRUE;
CREATE INDEX IF NOT EXISTS idx_cav1_run_id
    ON citation_agent_v1(extraction_run_id);

-- Common analytical filter: confirmed-only, non-dismissed default analysis
CREATE INDEX IF NOT EXISTS idx_cav1_confirmed_active
    ON citation_agent_v1(document_id, sixfold_type)
    WHERE verification_verdict = 'CONFIRMED'
      AND (functional_use IS NULL OR functional_use <> 'dismissed');


-- ============================================================================
-- TABLE 2 — citation_agent_v1_summary
-- One row per document. Mirrors verifier output's top-level + summary block.
-- ============================================================================

CREATE TABLE IF NOT EXISTS citation_agent_v1_summary (
    summary_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    document_id UUID NOT NULL UNIQUE
        REFERENCES documents(document_id) ON DELETE CASCADE,
    case_id VARCHAR(100)
        REFERENCES cases(case_id) ON DELETE CASCADE,

    -- ------------------------------------------------------------------------
    -- Source echoes (verifier top-level)
    -- ------------------------------------------------------------------------
    source_jurisdiction VARCHAR(300),
    source_region VARCHAR(50),
    source_year INTEGER,
    verification_timestamp TIMESTAMP,

    -- ------------------------------------------------------------------------
    -- Verdict counts (verifier top-level totals)
    -- ------------------------------------------------------------------------
    total_citations_extracted INTEGER DEFAULT 0,
    total_confirmed INTEGER DEFAULT 0,
    total_not_found INTEGER DEFAULT 0,
    total_misattributed INTEGER DEFAULT 0,
    total_not_a_case INTEGER DEFAULT 0,
    total_duplicates INTEGER DEFAULT 0,
    unique_citations_confirmed INTEGER DEFAULT 0,

    -- ------------------------------------------------------------------------
    -- Sixfold breakdown (verifier summary.by_sixfold_type)
    -- ------------------------------------------------------------------------
    sixfold_foreign_citation_count INTEGER DEFAULT 0,
    sixfold_international_citation_count INTEGER DEFAULT 0,
    sixfold_foreign_international_citation_count INTEGER DEFAULT 0,
    sixfold_inter_system_citation_count INTEGER DEFAULT 0,
    sixfold_member_state_citation_count INTEGER DEFAULT 0,
    sixfold_non_member_citation_count INTEGER DEFAULT 0,
    sixfold_domestic_count INTEGER DEFAULT 0,
    sixfold_unclassified_count INTEGER DEFAULT 0,

    -- ------------------------------------------------------------------------
    -- Functional use breakdown (D31 incl. 'dismissed')
    -- ------------------------------------------------------------------------
    functional_aligned_count INTEGER DEFAULT 0,
    functional_contested_count INTEGER DEFAULT 0,
    functional_avoided_count INTEGER DEFAULT 0,
    functional_invoked_count INTEGER DEFAULT 0,
    functional_dismissed_count INTEGER DEFAULT 0,

    -- ------------------------------------------------------------------------
    -- Vertical dialogue breakdown (D30)
    -- ------------------------------------------------------------------------
    vertical_dialogue_true_count INTEGER DEFAULT 0,
    vertical_dialogue_false_count INTEGER DEFAULT 0,

    -- ------------------------------------------------------------------------
    -- Origin region breakdown (verifier summary.by_origin_region)
    -- ------------------------------------------------------------------------
    origin_global_north_count INTEGER DEFAULT 0,
    origin_global_south_count INTEGER DEFAULT 0,
    origin_international_count INTEGER DEFAULT 0,
    origin_domestic_count INTEGER DEFAULT 0,
    origin_unknown_count INTEGER DEFAULT 0,

    -- ------------------------------------------------------------------------
    -- Quality flags
    -- ------------------------------------------------------------------------
    flagged_for_review_count INTEGER DEFAULT 0,
    extraction_success BOOLEAN DEFAULT TRUE,
    extraction_error TEXT,
    average_confidence DECIMAL(3, 2),

    -- ------------------------------------------------------------------------
    -- Processing metadata (extractor + verifier — not in verifier JSON, but
    -- the ingest script records them for cost/latency tracking)
    -- ------------------------------------------------------------------------
    extractor_model VARCHAR(50),
    verifier_model VARCHAR(50),
    extraction_started_at TIMESTAMP,
    extraction_completed_at TIMESTAMP,
    verification_started_at TIMESTAMP,
    verification_completed_at TIMESTAMP,
    total_processing_time_seconds DECIMAL(10, 2),

    extraction_run_id VARCHAR(50),

    -- ------------------------------------------------------------------------
    -- System metadata
    -- ------------------------------------------------------------------------
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE citation_agent_v1_summary
    IS 'Per-document summary of the 2-agent pipeline output. Mirrors verifier JSON summary{} + top-level counts. Parallel to v7 citation_extraction_phased_summary (D37).';

COMMENT ON COLUMN citation_agent_v1_summary.document_id                        IS 'FK to documents.document_id (UNIQUE — one summary per document)';
COMMENT ON COLUMN citation_agent_v1_summary.source_year                        IS 'Document year (D35)';
COMMENT ON COLUMN citation_agent_v1_summary.total_citations_extracted          IS 'Verifier top-level total_citations_extracted';
COMMENT ON COLUMN citation_agent_v1_summary.unique_citations_confirmed         IS 'Confirmed citations after D22 dedup (= summary.confirmed_unique)';
COMMENT ON COLUMN citation_agent_v1_summary.sixfold_domestic_count             IS 'D29 same-court/same-system citations (excluded from transnational analysis)';
COMMENT ON COLUMN citation_agent_v1_summary.functional_dismissed_count         IS 'D31 mere-acknowledgement citations (filtered out of default analysis)';
COMMENT ON COLUMN citation_agent_v1_summary.vertical_dialogue_true_count       IS 'D30 vertical dialogue citations (national → member international court)';

-- Indexes (citation_agent_v1_summary)
CREATE INDEX IF NOT EXISTS idx_cav1_summary_document_id
    ON citation_agent_v1_summary(document_id);
CREATE INDEX IF NOT EXISTS idx_cav1_summary_case_id
    ON citation_agent_v1_summary(case_id);
CREATE INDEX IF NOT EXISTS idx_cav1_summary_success
    ON citation_agent_v1_summary(extraction_success);
CREATE INDEX IF NOT EXISTS idx_cav1_summary_run_id
    ON citation_agent_v1_summary(extraction_run_id);


-- ============================================================================
-- TABLE 3 — citation_sixfold_agent_v1 (VIEW)
-- ============================================================================
-- Why a VIEW, not a TABLE:
--   In the v7 pipeline, `citation_sixfold_classification` is a VIEW over
--   `citation_extraction_phased` (see scripts/7-queries/sixfold_classification_complete.sql)
--   — sixfold classification was derived at query time from
--   case_law_region/source_region. The agent pipeline goes one better: the
--   verifier writes `sixfold_type` and `is_vertical_dialogue` directly into
--   `citation_agent_v1` per row. There is no derivation work left to do.
--
--   Adding a separate `citation_sixfold_agent_v1` TABLE would duplicate
--   `citation_agent_v1` 1-for-1 with no new columns, and force every write
--   to maintain two tables in sync. The clean equivalent — and the closest
--   mirror of the v7 pattern — is a thin VIEW that filters/projects
--   `citation_agent_v1` to the canonical sixfold-analysis shape.
--
-- This view restricts to CONFIRMED, non-dismissed rows by default (the
-- transnational-analysis dataset). For raw access including all verdicts,
-- query `citation_agent_v1` directly.
-- ============================================================================

CREATE OR REPLACE VIEW citation_sixfold_agent_v1 AS
SELECT
    extraction_id,
    document_id,
    case_id,
    citation_index,
    source_jurisdiction,
    source_region,
    source_year,
    case_name,
    cited_court,
    case_number,
    cited_year,
    origin_country,
    origin_region,
    origin_court,
    sixfold_type,
    is_vertical_dialogue,
    functional_use,
    functional_use_confidence,
    opinion_type,
    citation_pattern,
    confidence,
    verbatim_snippet,
    requires_manual_review,
    manual_review_reason,
    -- Direction grouping (mirrors v7 citation_direction column)
    CASE
        WHEN sixfold_type = 'Domestic' THEN 'Domestic'
        WHEN source_region IN ('Global North', 'Global South')
             AND origin_region IN ('Global North', 'Global South')
            THEN 'National → National'
        WHEN source_region IN ('Global North', 'Global South')
             AND origin_region = 'International'
            THEN 'National → International'
        WHEN source_region = 'International'
             AND origin_region = 'International'
            THEN 'International → International'
        WHEN source_region = 'International'
             AND origin_region IN ('Global North', 'Global South')
            THEN 'International → National'
        ELSE 'Other'
    END AS citation_direction,
    created_at,
    updated_at
FROM citation_agent_v1
WHERE verification_verdict = 'CONFIRMED'
  AND (functional_use IS NULL OR functional_use <> 'dismissed');

COMMENT ON VIEW citation_sixfold_agent_v1
    IS 'Sixfold-classified citations from the agent v1 pipeline. Filtered to CONFIRMED + non-dismissed (D31 default analysis layer). Mirrors v7 citation_sixfold_classification VIEW pattern. Query citation_agent_v1 directly for all verdicts.';


-- ============================================================================
-- updated_at TRIGGER (reuse the v7 function if present; else create it)
-- ============================================================================

CREATE OR REPLACE FUNCTION update_citation_agent_v1_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_cav1_updated_at ON citation_agent_v1;
CREATE TRIGGER trg_cav1_updated_at
    BEFORE UPDATE ON citation_agent_v1
    FOR EACH ROW EXECUTE FUNCTION update_citation_agent_v1_timestamp();

DROP TRIGGER IF EXISTS trg_cav1_summary_updated_at ON citation_agent_v1_summary;
CREATE TRIGGER trg_cav1_summary_updated_at
    BEFORE UPDATE ON citation_agent_v1_summary
    FOR EACH ROW EXECUTE FUNCTION update_citation_agent_v1_timestamp();


-- ============================================================================
-- VERIFICATION QUERIES (run manually after migration)
-- ============================================================================

-- Confirm tables exist
-- SELECT table_name FROM information_schema.tables
-- WHERE table_name IN ('citation_agent_v1', 'citation_agent_v1_summary')
-- ORDER BY table_name;

-- Confirm view exists
-- SELECT table_name FROM information_schema.views
-- WHERE table_name = 'citation_sixfold_agent_v1';

-- Confirm CHECK constraints
-- SELECT conname, consrc FROM pg_constraint
-- WHERE conrelid = 'citation_agent_v1'::regclass AND contype = 'c'
-- ORDER BY conname;

-- Confirm indexes
-- SELECT indexname FROM pg_indexes
-- WHERE tablename IN ('citation_agent_v1', 'citation_agent_v1_summary')
-- ORDER BY tablename, indexname;

COMMIT;

-- ============================================================================
-- END OF MIGRATION
-- ============================================================================
