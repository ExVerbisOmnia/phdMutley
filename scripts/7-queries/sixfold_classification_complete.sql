-- ============================================================================
-- SIXFOLD CITATION CLASSIFICATION - COMPREHENSIVE ANALYSIS
-- Climate Litigation PhD Research Project
-- 
-- Author: Gustavo (with Claude assistance)
-- Date: November 28, 2025
-- Purpose: Generate complete analysis for ALL 6 citation categories,
--          with individual metrics nested under each category
--
-- Prerequisites: Run international_court_jurisdiction.sql first
-- Execute with: psql -d climate_litigation -f sixfold_classification_complete.sql
-- ============================================================================

-- ============================================================================
-- CLASSIFICATION CATEGORIES
-- ============================================================================
-- 1. Foreign Citation:              National → National (different countries)
-- 2. International Citation:        National → Int'l tribunal (member state)
-- 3. Foreign International Citation: National → Int'l tribunal (non-member)
-- 4. Inter-System Citation:         Int'l tribunal → Int'l tribunal
-- 5. Member-State Citation:         Int'l tribunal → National (member state)
-- 6. Non-Member Citation:           Int'l tribunal → National (non-member)
-- ============================================================================

-- ============================================================================
-- HELPER FUNCTION: Check if a jurisdiction is a member of an international court
-- ============================================================================

CREATE OR REPLACE FUNCTION is_member_of_court(
    p_jurisdiction TEXT,
    p_court_pattern TEXT
) RETURNS BOOLEAN AS $$
DECLARE
    v_is_member BOOLEAN := FALSE;
BEGIN
    SELECT EXISTS (
        SELECT 1 
        FROM international_court_jurisdiction icj
        WHERE (
            LOWER(p_court_pattern) LIKE '%' || LOWER(icj.court_abbreviation) || '%'
            OR LOWER(p_court_pattern) LIKE '%' || LOWER(icj.court_name) || '%'
            OR LOWER(icj.court_name) LIKE '%' || LOWER(p_court_pattern) || '%'
        )
        AND (
            p_jurisdiction = ANY(icj.member_jurisdictions)
            OR '*ALL*' = ANY(icj.member_jurisdictions)
        )
    ) INTO v_is_member;
    
    RETURN v_is_member;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- MAIN CLASSIFICATION VIEW
-- ============================================================================

DROP VIEW IF EXISTS citation_sixfold_classification CASCADE;

CREATE OR REPLACE VIEW citation_sixfold_classification AS
SELECT 
    c.extraction_id,
    c.document_id,
    c.case_id,
    c.source_jurisdiction,
    c.source_region,
    c.case_name,
    c.cited_court,
    c.case_law_origin,
    c.case_law_region,
    c.citation_type AS original_type,
    
    -- SIXFOLD CLASSIFICATION LOGIC
    CASE 
        -- 4. INTER-SYSTEM CITATION: International → International
        WHEN c.source_region = 'International' 
             AND c.case_law_region = 'International' 
        THEN 'Inter-System Citation'
        
        -- 1. FOREIGN CITATION: National → National (different countries)
        WHEN c.source_region IN ('Global North', 'Global South')
             AND c.case_law_region IN ('Global North', 'Global South')
             AND c.citation_type = 'Foreign Citation'
        THEN 'Foreign Citation'
        
        -- 2 & 3. National → International: Check membership
        WHEN c.source_region IN ('Global North', 'Global South')
             AND c.case_law_region = 'International'
        THEN 
            CASE 
                WHEN EXISTS (
                    SELECT 1 FROM international_court_jurisdiction icj
                    WHERE (
                        LOWER(COALESCE(c.cited_court, '')) LIKE '%' || LOWER(icj.court_abbreviation) || '%'
                        OR LOWER(COALESCE(c.case_law_origin, '')) LIKE '%' || LOWER(icj.court_abbreviation) || '%'
                        OR LOWER(COALESCE(c.cited_court, '')) LIKE '%' || LOWER(icj.court_name) || '%'
                        OR LOWER(COALESCE(c.case_law_origin, '')) LIKE '%' || LOWER(icj.court_name) || '%'
                        OR (LOWER(COALESCE(c.case_law_origin, '')) LIKE '%european union%' AND icj.court_abbreviation IN ('CJEU', 'ECJ'))
                        OR (LOWER(COALESCE(c.case_law_origin, '')) LIKE '%council of europe%' AND icj.court_abbreviation IN ('ECtHR', 'CoE'))
                        OR (LOWER(COALESCE(c.case_law_origin, '')) LIKE '%inter-american%' AND icj.court_abbreviation IN ('IACtHR', 'IAHRS'))
                        OR (LOWER(COALESCE(c.case_law_origin, '')) LIKE '%african%' AND icj.court_abbreviation = 'ACtHPR')
                        OR (LOWER(COALESCE(c.case_law_origin, '')) LIKE '%wto%' AND icj.court_abbreviation = 'WTO')
                        OR (LOWER(COALESCE(c.case_law_origin, '')) LIKE '%world trade%' AND icj.court_abbreviation = 'WTO')
                        OR (LOWER(COALESCE(c.case_law_origin, '')) LIKE '%icsid%' AND icj.court_abbreviation = 'ICSID')
                        OR (LOWER(COALESCE(c.case_law_origin, '')) LIKE '%united nations%' AND icj.court_abbreviation = 'ICJ')
                    )
                    AND (
                        c.source_jurisdiction = ANY(icj.member_jurisdictions)
                        OR '*ALL*' = ANY(icj.member_jurisdictions)
                    )
                ) THEN 'International Citation'
                ELSE 'Foreign International Citation'
            END
        
        -- 5 & 6. International → National: Check membership
        WHEN c.source_region = 'International'
             AND c.case_law_region IN ('Global North', 'Global South')
        THEN 
            CASE 
                WHEN EXISTS (
                    SELECT 1 FROM international_court_jurisdiction icj
                    WHERE (
                        LOWER(COALESCE(c.source_jurisdiction, '')) LIKE '%' || LOWER(icj.court_abbreviation) || '%'
                        OR LOWER(COALESCE(c.source_jurisdiction, '')) LIKE '%' || LOWER(icj.court_name) || '%'
                        OR (c.source_jurisdiction = 'International' AND (
                            LOWER(COALESCE(c.cited_court, '')) LIKE '%european%' AND icj.court_system = 'Council of Europe'
                            OR LOWER(COALESCE(c.cited_court, '')) LIKE '%inter-american%' AND icj.court_system = 'Organization of American States'
                        ))
                    )
                    AND (
                        c.case_law_origin = ANY(icj.member_jurisdictions)
                        OR '*ALL*' = ANY(icj.member_jurisdictions)
                    )
                ) THEN 'Member-State Citation'
                ELSE 'Non-Member Citation'
            END
        
        ELSE 'Unclassified'
    END AS sixfold_type,
    
    -- Category grouping for nesting
    CASE 
        WHEN c.source_region IN ('Global North', 'Global South') 
             AND c.case_law_region IN ('Global North', 'Global South')
        THEN 'National → National'
        
        WHEN c.source_region IN ('Global North', 'Global South') 
             AND c.case_law_region = 'International'
        THEN 'National → International'
        
        WHEN c.source_region = 'International' 
             AND c.case_law_region = 'International'
        THEN 'International → International'
        
        WHEN c.source_region = 'International' 
             AND c.case_law_region IN ('Global North', 'Global South')
        THEN 'International → National'
        
        ELSE 'Other'
    END AS citation_direction

FROM citation_extraction_phased c;

-- ============================================================================
-- ============================================================================
--                    COMPREHENSIVE ANALYSIS - ALL 6 CATEGORIES
-- ============================================================================
-- ============================================================================

\echo ''
\echo '╔══════════════════════════════════════════════════════════════════════╗'
\echo '║           SIXFOLD CITATION CLASSIFICATION - COMPLETE ANALYSIS        ║'
\echo '╚══════════════════════════════════════════════════════════════════════╝'

-- ============================================================================
-- SECTION 0: OVERALL SUMMARY
-- ============================================================================

\echo ''
\echo '┌──────────────────────────────────────────────────────────────────────┐'
\echo '│ SECTION 0: OVERALL SUMMARY                                          │'
\echo '└──────────────────────────────────────────────────────────────────────┘'

\echo ''
\echo '0.1 Total citations by sixfold classification:'
SELECT 
    sixfold_type,
    citation_direction,
    COUNT(*) as citation_count,
    COUNT(DISTINCT document_id) as decision_count,
    ROUND(COUNT(*)::numeric / SUM(COUNT(*)) OVER () * 100, 2) as pct_citations
FROM citation_sixfold_classification
GROUP BY sixfold_type, citation_direction
ORDER BY citation_direction, sixfold_type;

\echo ''
\echo '0.2 Summary by direction:'
SELECT 
    citation_direction,
    COUNT(*) as total_citations,
    COUNT(DISTINCT document_id) as decisions_involved,
    ROUND(COUNT(*)::numeric / SUM(COUNT(*)) OVER () * 100, 2) as pct
FROM citation_sixfold_classification
GROUP BY citation_direction
ORDER BY total_citations DESC;

-- ============================================================================
-- SECTION 1: FOREIGN CITATION (National → National)
-- ============================================================================

\echo ''
\echo '┌──────────────────────────────────────────────────────────────────────┐'
\echo '│ SECTION 1: FOREIGN CITATION (National → National)                   │'
\echo '└──────────────────────────────────────────────────────────────────────┘'

\echo ''
\echo '1.1 Overview:'
SELECT 
    COUNT(*) as total_citations,
    COUNT(DISTINCT document_id) as decisions_with_foreign,
    COUNT(DISTINCT case_id) as cases_with_foreign
FROM citation_sixfold_classification
WHERE sixfold_type = 'Foreign Citation';

\echo ''
\echo '1.2 Regional flow matrix (North-South):'
SELECT 
    source_region AS "Source →",
    SUM(CASE WHEN case_law_region = 'Global North' THEN 1 ELSE 0 END) AS "→ Global North",
    SUM(CASE WHEN case_law_region = 'Global South' THEN 1 ELSE 0 END) AS "→ Global South",
    COUNT(*) AS "Total"
FROM citation_sixfold_classification
WHERE sixfold_type = 'Foreign Citation'
  AND source_region IN ('Global North', 'Global South')
GROUP BY source_region
ORDER BY source_region;

\echo ''
\echo '1.3 Top 10 source jurisdictions (citing courts):'
SELECT 
    source_jurisdiction,
    source_region,
    COUNT(*) as citations_made
FROM citation_sixfold_classification
WHERE sixfold_type = 'Foreign Citation'
GROUP BY source_jurisdiction, source_region
ORDER BY citations_made DESC
LIMIT 10;

\echo ''
\echo '1.4 Top 10 cited jurisdictions:'
SELECT 
    case_law_origin,
    case_law_region,
    COUNT(*) as times_cited
FROM citation_sixfold_classification
WHERE sixfold_type = 'Foreign Citation'
GROUP BY case_law_origin, case_law_region
ORDER BY times_cited DESC
LIMIT 10;

\echo ''
\echo '1.5 Top 10 most cited cases:'
SELECT 
    case_name,
    case_law_origin,
    case_law_region,
    COUNT(*) as citation_count
FROM citation_sixfold_classification
WHERE sixfold_type = 'Foreign Citation'
GROUP BY case_name, case_law_origin, case_law_region
ORDER BY citation_count DESC
LIMIT 10;

-- ============================================================================
-- SECTION 2: INTERNATIONAL CITATION (National → Int'l, member state)
-- ============================================================================

\echo ''
\echo '┌──────────────────────────────────────────────────────────────────────┐'
\echo '│ SECTION 2: INTERNATIONAL CITATION (National → Int''l, member)        │'
\echo '└──────────────────────────────────────────────────────────────────────┘'

\echo ''
\echo '2.1 Overview:'
SELECT 
    COUNT(*) as total_citations,
    COUNT(DISTINCT document_id) as decisions_with_intl,
    COUNT(DISTINCT case_id) as cases_with_intl
FROM citation_sixfold_classification
WHERE sixfold_type = 'International Citation';

\echo ''
\echo '2.2 By source region (who cites international tribunals they belong to):'
SELECT 
    source_region,
    COUNT(*) as citations,
    COUNT(DISTINCT document_id) as decisions
FROM citation_sixfold_classification
WHERE sixfold_type = 'International Citation'
GROUP BY source_region
ORDER BY citations DESC;

\echo ''
\echo '2.3 Top source jurisdictions citing their own tribunals:'
SELECT 
    source_jurisdiction,
    source_region,
    COUNT(*) as citations_made
FROM citation_sixfold_classification
WHERE sixfold_type = 'International Citation'
GROUP BY source_jurisdiction, source_region
ORDER BY citations_made DESC
LIMIT 10;

\echo ''
\echo '2.4 Most cited international tribunals (by members):'
SELECT 
    case_law_origin,
    COUNT(*) as times_cited
FROM citation_sixfold_classification
WHERE sixfold_type = 'International Citation'
GROUP BY case_law_origin
ORDER BY times_cited DESC
LIMIT 10;

\echo ''
\echo '2.5 Top 10 most cited international cases (by member states):'
SELECT 
    case_name,
    case_law_origin,
    COUNT(*) as citation_count
FROM citation_sixfold_classification
WHERE sixfold_type = 'International Citation'
GROUP BY case_name, case_law_origin
ORDER BY citation_count DESC
LIMIT 10;

-- ============================================================================
-- SECTION 3: FOREIGN INTERNATIONAL CITATION (National → Int'l, non-member)
-- ============================================================================

\echo ''
\echo '┌──────────────────────────────────────────────────────────────────────┐'
\echo '│ SECTION 3: FOREIGN INTERNATIONAL CITATION (National → Int''l, non)   │'
\echo '└──────────────────────────────────────────────────────────────────────┘'

\echo ''
\echo '3.1 Overview:'
SELECT 
    COUNT(*) as total_citations,
    COUNT(DISTINCT document_id) as decisions_with_foreign_intl,
    COUNT(DISTINCT case_id) as cases_with_foreign_intl
FROM citation_sixfold_classification
WHERE sixfold_type = 'Foreign International Citation';

\echo ''
\echo '3.2 By source region (who cites tribunals they DON''T belong to):'
SELECT 
    source_region,
    COUNT(*) as citations,
    COUNT(DISTINCT document_id) as decisions
FROM citation_sixfold_classification
WHERE sixfold_type = 'Foreign International Citation'
GROUP BY source_region
ORDER BY citations DESC;

\echo ''
\echo '3.3 Top source jurisdictions citing foreign tribunals:'
SELECT 
    source_jurisdiction,
    source_region,
    COUNT(*) as citations_made
FROM citation_sixfold_classification
WHERE sixfold_type = 'Foreign International Citation'
GROUP BY source_jurisdiction, source_region
ORDER BY citations_made DESC
LIMIT 10;

\echo ''
\echo '3.4 Most cited foreign international tribunals:'
SELECT 
    case_law_origin,
    COUNT(*) as times_cited
FROM citation_sixfold_classification
WHERE sixfold_type = 'Foreign International Citation'
GROUP BY case_law_origin
ORDER BY times_cited DESC
LIMIT 10;

\echo ''
\echo '3.5 Top 10 most cited foreign international cases:'
SELECT 
    case_name,
    case_law_origin,
    COUNT(*) as citation_count
FROM citation_sixfold_classification
WHERE sixfold_type = 'Foreign International Citation'
GROUP BY case_name, case_law_origin
ORDER BY citation_count DESC
LIMIT 10;

\echo ''
\echo '3.6 Cross-system citations (e.g., Americas citing Europe):'
SELECT 
    source_jurisdiction,
    case_law_origin,
    COUNT(*) as citations
FROM citation_sixfold_classification
WHERE sixfold_type = 'Foreign International Citation'
GROUP BY source_jurisdiction, case_law_origin
ORDER BY citations DESC
LIMIT 15;

-- ============================================================================
-- SECTION 4: INTER-SYSTEM CITATION (International → International)
-- ============================================================================

\echo ''
\echo '┌──────────────────────────────────────────────────────────────────────┐'
\echo '│ SECTION 4: INTER-SYSTEM CITATION (Int''l → Int''l)                    │'
\echo '└──────────────────────────────────────────────────────────────────────┘'

\echo ''
\echo '4.1 Overview:'
SELECT 
    COUNT(*) as total_citations,
    COUNT(DISTINCT document_id) as decisions_with_intersystem,
    COUNT(DISTINCT case_id) as cases_with_intersystem
FROM citation_sixfold_classification
WHERE sixfold_type = 'Inter-System Citation';

\echo ''
\echo '4.2 Tribunal-to-tribunal citation flows:'
SELECT 
    source_jurisdiction AS citing_tribunal,
    case_law_origin AS cited_tribunal,
    COUNT(*) as citation_count
FROM citation_sixfold_classification
WHERE sixfold_type = 'Inter-System Citation'
GROUP BY source_jurisdiction, case_law_origin
ORDER BY citation_count DESC
LIMIT 15;

\echo ''
\echo '4.3 Most active citing tribunals:'
SELECT 
    source_jurisdiction,
    COUNT(*) as citations_made,
    COUNT(DISTINCT case_law_origin) as tribunals_cited
FROM citation_sixfold_classification
WHERE sixfold_type = 'Inter-System Citation'
GROUP BY source_jurisdiction
ORDER BY citations_made DESC
LIMIT 10;

\echo ''
\echo '4.4 Most cited tribunals (by other tribunals):'
SELECT 
    case_law_origin,
    COUNT(*) as times_cited,
    COUNT(DISTINCT source_jurisdiction) as citing_tribunals
FROM citation_sixfold_classification
WHERE sixfold_type = 'Inter-System Citation'
GROUP BY case_law_origin
ORDER BY times_cited DESC
LIMIT 10;

\echo ''
\echo '4.5 Top 10 most cited inter-system cases:'
SELECT 
    case_name,
    case_law_origin,
    COUNT(*) as citation_count
FROM citation_sixfold_classification
WHERE sixfold_type = 'Inter-System Citation'
GROUP BY case_name, case_law_origin
ORDER BY citation_count DESC
LIMIT 10;

-- ============================================================================
-- SECTION 5: MEMBER-STATE CITATION (International → National, member)
-- ============================================================================

\echo ''
\echo '┌──────────────────────────────────────────────────────────────────────┐'
\echo '│ SECTION 5: MEMBER-STATE CITATION (Int''l → National, member)         │'
\echo '└──────────────────────────────────────────────────────────────────────┘'

\echo ''
\echo '5.1 Overview:'
SELECT 
    COUNT(*) as total_citations,
    COUNT(DISTINCT document_id) as decisions_with_member_state,
    COUNT(DISTINCT case_id) as cases_with_member_state
FROM citation_sixfold_classification
WHERE sixfold_type = 'Member-State Citation';

\echo ''
\echo '5.2 By cited region (which regions do tribunals cite from their members):'
SELECT 
    case_law_region AS cited_region,
    COUNT(*) as citations,
    COUNT(DISTINCT document_id) as decisions
FROM citation_sixfold_classification
WHERE sixfold_type = 'Member-State Citation'
GROUP BY case_law_region
ORDER BY citations DESC;

\echo ''
\echo '5.3 Top source tribunals citing their member states:'
SELECT 
    source_jurisdiction,
    COUNT(*) as citations_made,
    COUNT(DISTINCT case_law_origin) as member_states_cited
FROM citation_sixfold_classification
WHERE sixfold_type = 'Member-State Citation'
GROUP BY source_jurisdiction
ORDER BY citations_made DESC
LIMIT 10;

\echo ''
\echo '5.4 Most cited member state jurisdictions:'
SELECT 
    case_law_origin,
    case_law_region,
    COUNT(*) as times_cited
FROM citation_sixfold_classification
WHERE sixfold_type = 'Member-State Citation'
GROUP BY case_law_origin, case_law_region
ORDER BY times_cited DESC
LIMIT 10;

\echo ''
\echo '5.5 Top 10 most cited member state cases:'
SELECT 
    case_name,
    case_law_origin,
    case_law_region,
    COUNT(*) as citation_count
FROM citation_sixfold_classification
WHERE sixfold_type = 'Member-State Citation'
GROUP BY case_name, case_law_origin, case_law_region
ORDER BY citation_count DESC
LIMIT 10;

-- ============================================================================
-- SECTION 6: NON-MEMBER CITATION (International → National, non-member)
-- ============================================================================

\echo ''
\echo '┌──────────────────────────────────────────────────────────────────────┐'
\echo '│ SECTION 6: NON-MEMBER CITATION (Int''l → National, non-member)       │'
\echo '└──────────────────────────────────────────────────────────────────────┘'

\echo ''
\echo '6.1 Overview:'
SELECT 
    COUNT(*) as total_citations,
    COUNT(DISTINCT document_id) as decisions_with_non_member,
    COUNT(DISTINCT case_id) as cases_with_non_member
FROM citation_sixfold_classification
WHERE sixfold_type = 'Non-Member Citation';

\echo ''
\echo '6.2 By cited region (which regions do tribunals cite outside their system):'
SELECT 
    case_law_region AS cited_region,
    COUNT(*) as citations,
    COUNT(DISTINCT document_id) as decisions
FROM citation_sixfold_classification
WHERE sixfold_type = 'Non-Member Citation'
GROUP BY case_law_region
ORDER BY citations DESC;

\echo ''
\echo '6.3 Top source tribunals citing non-member states:'
SELECT 
    source_jurisdiction,
    COUNT(*) as citations_made,
    COUNT(DISTINCT case_law_origin) as non_members_cited
FROM citation_sixfold_classification
WHERE sixfold_type = 'Non-Member Citation'
GROUP BY source_jurisdiction
ORDER BY citations_made DESC
LIMIT 10;

\echo ''
\echo '6.4 Most cited non-member state jurisdictions:'
SELECT 
    case_law_origin,
    case_law_region,
    COUNT(*) as times_cited
FROM citation_sixfold_classification
WHERE sixfold_type = 'Non-Member Citation'
GROUP BY case_law_origin, case_law_region
ORDER BY times_cited DESC
LIMIT 10;

\echo ''
\echo '6.5 Top 10 most cited non-member state cases:'
SELECT 
    case_name,
    case_law_origin,
    case_law_region,
    COUNT(*) as citation_count
FROM citation_sixfold_classification
WHERE sixfold_type = 'Non-Member Citation'
GROUP BY case_name, case_law_origin, case_law_region
ORDER BY citation_count DESC
LIMIT 10;

\echo ''
\echo '6.6 Cross-regional citations (tribunals citing outside their region):'
SELECT 
    source_jurisdiction AS citing_tribunal,
    case_law_origin AS cited_jurisdiction,
    case_law_region,
    COUNT(*) as citations
FROM citation_sixfold_classification
WHERE sixfold_type = 'Non-Member Citation'
GROUP BY source_jurisdiction, case_law_origin, case_law_region
ORDER BY citations DESC
LIMIT 15;

-- ============================================================================
-- SECTION 7: COMPARATIVE ANALYSIS
-- ============================================================================

\echo ''
\echo '┌──────────────────────────────────────────────────────────────────────┐'
\echo '│ SECTION 7: COMPARATIVE ANALYSIS ACROSS ALL CATEGORIES               │'
\echo '└──────────────────────────────────────────────────────────────────────┘'

\echo ''
\echo '7.1 Decisions by number of citation types present:'
WITH decision_types AS (
    SELECT 
        document_id,
        COUNT(DISTINCT sixfold_type) as num_types,
        STRING_AGG(DISTINCT sixfold_type, ', ' ORDER BY sixfold_type) as types_present
    FROM citation_sixfold_classification
    GROUP BY document_id
)
SELECT 
    num_types AS "Citation Types Present",
    COUNT(*) as "Number of Decisions",
    ROUND(COUNT(*)::numeric / SUM(COUNT(*)) OVER () * 100, 1) as "Percentage"
FROM decision_types
GROUP BY num_types
ORDER BY num_types;

\echo ''
\echo '7.2 North-South asymmetry across all relevant categories:'
SELECT 
    sixfold_type,
    SUM(CASE WHEN source_region = 'Global North' AND case_law_region = 'Global North' THEN 1 ELSE 0 END) AS "N→N",
    SUM(CASE WHEN source_region = 'Global North' AND case_law_region = 'Global South' THEN 1 ELSE 0 END) AS "N→S",
    SUM(CASE WHEN source_region = 'Global South' AND case_law_region = 'Global North' THEN 1 ELSE 0 END) AS "S→N",
    SUM(CASE WHEN source_region = 'Global South' AND case_law_region = 'Global South' THEN 1 ELSE 0 END) AS "S→S",
    COUNT(*) AS "Total"
FROM citation_sixfold_classification
WHERE sixfold_type IN ('Foreign Citation', 'Member-State Citation', 'Non-Member Citation')
GROUP BY sixfold_type
ORDER BY sixfold_type;

\echo ''
\echo '7.3 Global South engagement summary:'
SELECT 
    sixfold_type,
    COUNT(*) FILTER (WHERE source_region = 'Global South') AS "Citations FROM South",
    COUNT(*) FILTER (WHERE case_law_region = 'Global South') AS "Citations TO South",
    COUNT(*) AS "Total Citations"
FROM citation_sixfold_classification
GROUP BY sixfold_type
ORDER BY "Citations FROM South" DESC;

\echo ''
\echo '7.4 Top 10 most cited cases overall (all categories):'
SELECT 
    case_name,
    case_law_origin,
    case_law_region,
    sixfold_type,
    COUNT(*) as citation_count
FROM citation_sixfold_classification
GROUP BY case_name, case_law_origin, case_law_region, sixfold_type
ORDER BY citation_count DESC
LIMIT 10;

-- ============================================================================
-- SECTION 8: EXPORT-READY SUMMARY TABLES
-- ============================================================================

\echo ''
\echo '┌──────────────────────────────────────────────────────────────────────┐'
\echo '│ SECTION 8: EXPORT-READY SUMMARY TABLES                              │'
\echo '└──────────────────────────────────────────────────────────────────────┘'

\echo ''
\echo '8.1 Final summary table (for thesis):'
SELECT 
    sixfold_type AS "Citation Category",
    citation_direction AS "Direction",
    COUNT(*) AS "Total Citations",
    COUNT(DISTINCT document_id) AS "Decisions",
    COUNT(DISTINCT case_id) AS "Cases",
    ROUND(COUNT(*)::numeric / SUM(COUNT(*)) OVER () * 100, 2) AS "% of Total"
FROM citation_sixfold_classification
GROUP BY sixfold_type, citation_direction
ORDER BY 
    CASE citation_direction 
        WHEN 'National → National' THEN 1
        WHEN 'National → International' THEN 2
        WHEN 'International → International' THEN 3
        WHEN 'International → National' THEN 4
        ELSE 5
    END,
    sixfold_type;

\echo ''
\echo '============================================================================'
\echo '✓ COMPREHENSIVE SIXFOLD CLASSIFICATION ANALYSIS COMPLETED!'
\echo '============================================================================'
\echo ''
