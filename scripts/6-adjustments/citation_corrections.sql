-- ============================================================================
-- CITATION DATA CORRECTIONS SCRIPT
-- Climate Litigation PhD Research Project
-- 
-- Author: Gustavo (with Claude assistance)
-- Date: November 28, 2025
-- Purpose: Correct classification errors in citation_extraction_phased table
--
-- IMPORTANT: Run this script AFTER backing up your database
-- Execute with: psql -d climate_litigation -f citation_corrections.sql
-- ============================================================================

-- Start transaction for safety (can ROLLBACK if needed)
BEGIN;

-- ============================================================================
-- PRE-CORRECTION COUNTS (for verification)
-- ============================================================================

\echo ''
\echo '============================================================'
\echo 'PRE-CORRECTION COUNTS'
\echo '============================================================'

\echo ''
\echo 'Citation types before corrections:'
SELECT citation_type, COUNT(*) as count 
FROM citation_extraction_phased 
GROUP BY citation_type 
ORDER BY count DESC;

-- ============================================================================
-- CORRECTION 1: EU/CJEU cases → International Citation
-- 
-- Criteria:
--   - case_law_origin = 'European Union'
--   - citation_type = 'Foreign Citation'
--
-- Changes:
--   - citation_type → 'International Citation'
--   - case_law_region → 'International'
--
-- Expected records: 158
-- ============================================================================

\echo ''
\echo '============================================================'
\echo 'CORRECTION 1: EU/CJEU cases → International Citation'
\echo '============================================================'

-- Count before
\echo 'Records matching criteria:'
SELECT COUNT(*) as records_to_update
FROM citation_extraction_phased
WHERE case_law_origin = 'European Union'
  AND citation_type = 'Foreign Citation';

-- Apply correction
UPDATE citation_extraction_phased
SET 
    citation_type = 'International Citation',
    case_law_region = 'International',
    updated_at = NOW()
WHERE case_law_origin = 'European Union'
  AND citation_type = 'Foreign Citation';

\echo 'Correction 1 applied.'

-- ============================================================================
-- CORRECTION 2: International courts in cited_court → International Citation
-- 
-- Criteria:
--   - citation_type = 'Foreign Citation'
--   - cited_court contains international court patterns
--
-- Changes:
--   - citation_type → 'International Citation'
--   - case_law_region → 'International'
--
-- Expected records: 42 (after Correction 1)
-- ============================================================================

\echo ''
\echo '============================================================'
\echo 'CORRECTION 2: International courts → International Citation'
\echo '============================================================'

-- Count before
\echo 'Records matching criteria:'
SELECT COUNT(*) as records_to_update
FROM citation_extraction_phased
WHERE citation_type = 'Foreign Citation'
  AND (
    LOWER(cited_court) LIKE '%european court of human rights%'
    OR LOWER(cited_court) LIKE '%echr%'
    OR LOWER(cited_court) LIKE '%ecthr%'
    OR LOWER(cited_court) LIKE '%inter-american court%'
    OR LOWER(cited_court) LIKE '%iachr%'
    OR LOWER(cited_court) LIKE '%corte interamericana%'
    OR LOWER(cited_court) LIKE '%international court of justice%'
    OR LOWER(cited_court) LIKE '%icj%'
    OR LOWER(cited_court) LIKE '%court of justice of the european union%'
    OR LOWER(cited_court) LIKE '%cjeu%'
    OR LOWER(cited_court) LIKE '%ecj%'
    OR LOWER(cited_court) LIKE '%european court of justice%'
    OR LOWER(cited_court) LIKE '%wto%'
    OR LOWER(cited_court) LIKE '%world trade organization%'
    OR LOWER(cited_court) LIKE '%icsid%'
    OR LOWER(cited_court) LIKE '%international centre for settlement%'
    OR LOWER(cited_court) LIKE '%african court%'
    OR LOWER(cited_court) LIKE '%international tribunal%'
    OR LOWER(cited_court) LIKE '%un human rights committee%'
  );

-- Apply correction
UPDATE citation_extraction_phased
SET 
    citation_type = 'International Citation',
    case_law_region = 'International',
    updated_at = NOW()
WHERE citation_type = 'Foreign Citation'
  AND (
    LOWER(cited_court) LIKE '%european court of human rights%'
    OR LOWER(cited_court) LIKE '%echr%'
    OR LOWER(cited_court) LIKE '%ecthr%'
    OR LOWER(cited_court) LIKE '%inter-american court%'
    OR LOWER(cited_court) LIKE '%iachr%'
    OR LOWER(cited_court) LIKE '%corte interamericana%'
    OR LOWER(cited_court) LIKE '%international court of justice%'
    OR LOWER(cited_court) LIKE '%icj%'
    OR LOWER(cited_court) LIKE '%court of justice of the european union%'
    OR LOWER(cited_court) LIKE '%cjeu%'
    OR LOWER(cited_court) LIKE '%ecj%'
    OR LOWER(cited_court) LIKE '%european court of justice%'
    OR LOWER(cited_court) LIKE '%wto%'
    OR LOWER(cited_court) LIKE '%world trade organization%'
    OR LOWER(cited_court) LIKE '%icsid%'
    OR LOWER(cited_court) LIKE '%international centre for settlement%'
    OR LOWER(cited_court) LIKE '%african court%'
    OR LOWER(cited_court) LIKE '%international tribunal%'
    OR LOWER(cited_court) LIKE '%un human rights committee%'
  );

\echo 'Correction 2 applied.'

-- ============================================================================
-- CORRECTION 3: UK citing UK → Domestic Citation (Intra-UK)
-- 
-- Criteria:
--   - citation_type = 'Foreign Citation'
--   - source_jurisdiction contains UK terms
--   - case_law_origin contains UK terms
--
-- Changes:
--   - citation_type → 'Domestic Citation (Intra-UK)'
--
-- Expected records: 313
-- ============================================================================

\echo ''
\echo '============================================================'
\echo 'CORRECTION 3: UK citing UK → Domestic Citation (Intra-UK)'
\echo '============================================================'

-- Count before
\echo 'Records matching criteria:'
SELECT COUNT(*) as records_to_update
FROM citation_extraction_phased
WHERE citation_type = 'Foreign Citation'
  AND (
    source_jurisdiction ILIKE '%United Kingdom%'
    OR source_jurisdiction ILIKE '%England%'
    OR source_jurisdiction ILIKE '%Wales%'
    OR source_jurisdiction ILIKE '%Scotland%'
    OR source_jurisdiction ILIKE '%Northern Ireland%'
  )
  AND (
    case_law_origin ILIKE '%United Kingdom%'
    OR case_law_origin ILIKE '%England%'
    OR case_law_origin ILIKE '%Wales%'
    OR case_law_origin ILIKE '%Scotland%'
    OR case_law_origin ILIKE '%Northern Ireland%'
    OR case_law_origin ILIKE '%Britain%'
  );

-- Apply correction
UPDATE citation_extraction_phased
SET 
    citation_type = 'Domestic Citation (Intra-UK)',
    updated_at = NOW()
WHERE citation_type = 'Foreign Citation'
  AND (
    source_jurisdiction ILIKE '%United Kingdom%'
    OR source_jurisdiction ILIKE '%England%'
    OR source_jurisdiction ILIKE '%Wales%'
    OR source_jurisdiction ILIKE '%Scotland%'
    OR source_jurisdiction ILIKE '%Northern Ireland%'
  )
  AND (
    case_law_origin ILIKE '%United Kingdom%'
    OR case_law_origin ILIKE '%England%'
    OR case_law_origin ILIKE '%Wales%'
    OR case_law_origin ILIKE '%Scotland%'
    OR case_law_origin ILIKE '%Northern Ireland%'
    OR case_law_origin ILIKE '%Britain%'
  );

\echo 'Correction 3 applied.'

-- ============================================================================
-- CORRECTION 4: Australia region consistency → Global North
-- 
-- Criteria:
--   - case_law_origin contains 'Australia'
--   - case_law_region != 'Global North'
--
-- Changes:
--   - case_law_region → 'Global North'
--
-- Expected records: 1
-- ============================================================================

\echo ''
\echo '============================================================'
\echo 'CORRECTION 4: Australia region → Global North'
\echo '============================================================'

-- Count before
\echo 'Records matching criteria:'
SELECT COUNT(*) as records_to_update
FROM citation_extraction_phased
WHERE case_law_origin ILIKE '%Australia%'
  AND case_law_region != 'Global North';

-- Apply correction
UPDATE citation_extraction_phased
SET 
    case_law_region = 'Global North',
    updated_at = NOW()
WHERE case_law_origin ILIKE '%Australia%'
  AND case_law_region != 'Global North';

\echo 'Correction 4 applied.'

-- ============================================================================
-- CORRECTION 5: Taiwan citing Taiwan → Domestic Citation
-- 
-- Criteria:
--   - source_jurisdiction = 'Taiwan'
--   - case_law_origin contains 'Taiwan'
--   - citation_type = 'Foreign Citation'
--
-- Changes:
--   - citation_type → 'Domestic Citation'
--
-- Expected records: 9
-- ============================================================================

\echo ''
\echo '============================================================'
\echo 'CORRECTION 5: Taiwan citing Taiwan → Domestic Citation'
\echo '============================================================'

-- Count before
\echo 'Records matching criteria:'
SELECT COUNT(*) as records_to_update
FROM citation_extraction_phased
WHERE source_jurisdiction = 'Taiwan'
  AND case_law_origin ILIKE '%Taiwan%'
  AND citation_type = 'Foreign Citation';

-- Apply correction
UPDATE citation_extraction_phased
SET 
    citation_type = 'Domestic Citation',
    updated_at = NOW()
WHERE source_jurisdiction = 'Taiwan'
  AND case_law_origin ILIKE '%Taiwan%'
  AND citation_type = 'Foreign Citation';

\echo 'Correction 5 applied.'

-- ============================================================================
-- CORRECTION 6: Ambiguous origins → Unknown
-- 
-- Criteria:
--   - citation_type = 'Foreign Citation'
--   - case_law_origin contains ambiguous patterns
--
-- Changes:
--   - citation_type → 'Unknown'
--
-- Expected records: 3
-- ============================================================================

\echo ''
\echo '============================================================'
\echo 'CORRECTION 6: Ambiguous origins → Unknown'
\echo '============================================================'

-- Count before
\echo 'Records matching criteria:'
SELECT COUNT(*) as records_to_update
FROM citation_extraction_phased
WHERE citation_type = 'Foreign Citation'
  AND (
    LOWER(case_law_origin) LIKE '%or canada%'
    OR LOWER(case_law_origin) LIKE '%or new zealand%'
    OR LOWER(case_law_origin) LIKE '%or australia%'
    OR LOWER(case_law_origin) LIKE '%or uganda%'
    OR LOWER(case_law_origin) LIKE '%or tanzania%'
    OR LOWER(case_law_origin) LIKE '%east africa%'
    OR LOWER(case_law_origin) LIKE '%, or %'
  );

-- Apply correction
UPDATE citation_extraction_phased
SET 
    citation_type = 'Unknown',
    updated_at = NOW()
WHERE citation_type = 'Foreign Citation'
  AND (
    LOWER(case_law_origin) LIKE '%or canada%'
    OR LOWER(case_law_origin) LIKE '%or new zealand%'
    OR LOWER(case_law_origin) LIKE '%or australia%'
    OR LOWER(case_law_origin) LIKE '%or uganda%'
    OR LOWER(case_law_origin) LIKE '%or tanzania%'
    OR LOWER(case_law_origin) LIKE '%east africa%'
    OR LOWER(case_law_origin) LIKE '%, or %'
  );

\echo 'Correction 6 applied.'

-- ============================================================================
-- POST-CORRECTION VERIFICATION
-- ============================================================================

\echo ''
\echo '============================================================'
\echo 'POST-CORRECTION COUNTS'
\echo '============================================================'

\echo ''
\echo 'Citation types after corrections:'
SELECT citation_type, COUNT(*) as count 
FROM citation_extraction_phased 
GROUP BY citation_type 
ORDER BY count DESC;

\echo ''
\echo 'Foreign Citations by case_law_region:'
SELECT case_law_region, COUNT(*) as count 
FROM citation_extraction_phased 
WHERE citation_type = 'Foreign Citation'
GROUP BY case_law_region 
ORDER BY count DESC;

-- ============================================================================
-- COMMIT TRANSACTION
-- ============================================================================

\echo ''
\echo '============================================================'
\echo 'COMMITTING TRANSACTION'
\echo '============================================================'

COMMIT;

\echo ''
\echo '✓ All corrections applied successfully!'
\echo ''
\echo 'Summary of corrections:'
\echo '  1. EU/CJEU cases → International Citation'
\echo '  2. International courts → International Citation'
\echo '  3. UK citing UK → Domestic Citation (Intra-UK)'
\echo '  4. Australia region → Global North'
\echo '  5. Taiwan citing Taiwan → Domestic Citation'
\echo '  6. Ambiguous origins → Unknown'
\echo ''
