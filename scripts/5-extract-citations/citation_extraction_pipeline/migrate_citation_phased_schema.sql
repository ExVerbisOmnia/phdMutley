-- ============================================================================
-- DATABASE SCHEMA MIGRATION - Citation Extraction Phased (v5)
-- ============================================================================
-- Purpose: Add new table for phased citation extraction with enhanced metadata
-- Date: November 22, 2025
-- Version: 5.0
-- ============================================================================

-- Create citation_extraction_phased table
CREATE TABLE IF NOT EXISTS citation_extraction_phased (
    -- Primary Key
    extraction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Foreign Keys
    document_id UUID NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    case_id UUID REFERENCES cases(case_id) ON DELETE CASCADE,
    
    -- Phase 1: Source Jurisdiction
    source_jurisdiction VARCHAR(200),
    source_region VARCHAR(50), -- 'Global North' / 'Global South' / 'International'
    
    -- Phase 2: Extraction Results
    case_name VARCHAR(500),
    raw_citation_text TEXT,
    citation_format VARCHAR(100), -- 'traditional', 'narrative', 'shorthand', etc.
    context_before TEXT,
    context_after TEXT,
    section_heading VARCHAR(500),
    location_in_document VARCHAR(50), -- 'main_text', 'footnote', 'dissent', 'concurrence'
    
    -- Phase 3: Origin Identification
    case_law_origin VARCHAR(200), -- Identified country/jurisdiction
    case_law_region VARCHAR(50), -- 'Global North' / 'Global South' / 'International'
    origin_identification_tier INTEGER, -- 1 (dictionary), 2 (Sonnet), 3 (web search)
    origin_confidence DECIMAL(3,2), -- 0.00 - 1.00
    
    -- Phase 4: Classification
    citation_type VARCHAR(50), -- 'Foreign Citation', 'International Citation', 'Foreign International Citation'
    is_cross_jurisdictional BOOLEAN,
    
    -- Extended Metadata
    cited_court VARCHAR(500),
    cited_year INTEGER,
    cited_case_citation VARCHAR(500), -- e.g., "347 U.S. 483"
    
    -- Citation Context (full paragraph)
    full_paragraph TEXT,
    position_in_document INTEGER,
    start_char_index INTEGER,
    end_char_index INTEGER,
    
    -- Processing Metadata
    phase_2_model VARCHAR(50) DEFAULT 'claude-haiku-4.5',
    phase_3_model VARCHAR(50),
    phase_4_model VARCHAR(50) DEFAULT 'claude-haiku-4.5',
    processing_time_seconds DECIMAL(10,2),
    api_calls_used INTEGER,
    
    -- Quality Control
    requires_manual_review BOOLEAN DEFAULT FALSE,
    manual_review_reason TEXT,
    reviewed_by VARCHAR(100),
    reviewed_at TIMESTAMP,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_citation_phased_document ON citation_extraction_phased(document_id);
CREATE INDEX IF NOT EXISTS idx_citation_phased_type ON citation_extraction_phased(citation_type);
CREATE INDEX IF NOT EXISTS idx_citation_phased_origin ON citation_extraction_phased(case_law_origin);
CREATE INDEX IF NOT EXISTS idx_citation_phased_review ON citation_extraction_phased(requires_manual_review);
CREATE INDEX IF NOT EXISTS idx_citation_phased_source ON citation_extraction_phased(source_jurisdiction);
CREATE INDEX IF NOT EXISTS idx_citation_phased_case ON citation_extraction_phased(case_id);

-- Create trigger for updated_at timestamp
CREATE OR REPLACE FUNCTION update_citation_phased_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_citation_phased_updated_at
    BEFORE UPDATE ON citation_extraction_phased
    FOR EACH ROW
    EXECUTE FUNCTION update_citation_phased_timestamp();

-- Create summary table for document-level extraction metadata
CREATE TABLE IF NOT EXISTS citation_extraction_phased_summary (
    summary_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    
    -- Processing Results
    total_references_extracted INTEGER DEFAULT 0,
    foreign_citations_count INTEGER DEFAULT 0,
    international_citations_count INTEGER DEFAULT 0,
    foreign_international_citations_count INTEGER DEFAULT 0,
    
    -- API Usage
    total_api_calls INTEGER DEFAULT 0,
    total_tokens_input INTEGER DEFAULT 0,
    total_tokens_output INTEGER DEFAULT 0,
    total_cost_usd DECIMAL(10,4) DEFAULT 0.0000,
    
    -- Processing Metadata
    extraction_started_at TIMESTAMP,
    extraction_completed_at TIMESTAMP,
    total_processing_time_seconds DECIMAL(10,2),
    extraction_success BOOLEAN DEFAULT FALSE,
    extraction_error TEXT,
    
    -- Quality Metrics
    average_confidence DECIMAL(3,2),
    items_requiring_review INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(document_id)
);

-- Create index on summary table
CREATE INDEX IF NOT EXISTS idx_citation_phased_summary_document ON citation_extraction_phased_summary(document_id);
CREATE INDEX IF NOT EXISTS idx_citation_phased_summary_success ON citation_extraction_phased_summary(extraction_success);

-- Create trigger for summary updated_at timestamp
CREATE TRIGGER trigger_citation_phased_summary_updated_at
    BEFORE UPDATE ON citation_extraction_phased_summary
    FOR EACH ROW
    EXECUTE FUNCTION update_citation_phased_timestamp();

-- ============================================================================
-- COMMENTS AND DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE citation_extraction_phased IS 'Phased citation extraction with enhanced foreign case law capture (v5)';
COMMENT ON COLUMN citation_extraction_phased.source_jurisdiction IS 'Primary jurisdiction where the citing court is located (Phase 1)';
COMMENT ON COLUMN citation_extraction_phased.origin_identification_tier IS 'Method used to identify case origin: 1=Dictionary, 2=Sonnet, 3=Web Search';
COMMENT ON COLUMN citation_extraction_phased.citation_type IS 'Foreign Citation | International Citation | Foreign International Citation';
COMMENT ON COLUMN citation_extraction_phased.citation_format IS 'Format pattern: traditional, narrative, shorthand, scholarly, procedural, comparative, parallel_citations, etc.';

COMMENT ON TABLE citation_extraction_phased_summary IS 'Document-level summary of phased citation extraction processing';

-- ============================================================================
-- MIGRATION VERIFICATION QUERIES
-- ============================================================================

-- Verify table creation
SELECT 
    table_name, 
    table_type
FROM information_schema.tables 
WHERE table_name IN ('citation_extraction_phased', 'citation_extraction_phased_summary')
ORDER BY table_name;

-- Verify indexes
SELECT 
    indexname, 
    tablename
FROM pg_indexes 
WHERE tablename IN ('citation_extraction_phased', 'citation_extraction_phased_summary')
ORDER BY tablename, indexname;

-- Verify triggers
SELECT 
    trigger_name, 
    event_object_table
FROM information_schema.triggers 
WHERE event_object_table IN ('citation_extraction_phased', 'citation_extraction_phased_summary')
ORDER BY event_object_table, trigger_name;

-- ============================================================================
-- END OF MIGRATION SCRIPT
-- ============================================================================
