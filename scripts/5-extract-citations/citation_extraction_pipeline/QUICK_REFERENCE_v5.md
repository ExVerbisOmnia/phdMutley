# Citation Extraction v5 - Quick Reference Card
## Essential Commands & Queries

---

## 🚀 DEPLOYMENT COMMANDS

### Deploy Database Schema
```bash
cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley
psql -d phdMutley -f scripts/phase2/migrate_citation_phased_schema.sql
```

### Run Script (Trial Batch)
```bash
# Ensure TRIAL_BATCH_CONFIG['ENABLED'] = True in config.py
python scripts/phase2/extract_citations_v5_phased.py
```

### Run Script (Full Dataset)
```bash
# Ensure TRIAL_BATCH_CONFIG['ENABLED'] = False in config.py
python scripts/phase2/extract_citations_v5_phased.py
```

### Monitor Logs
```bash
tail -f logs/citation_extraction_v5.log
```

---

## 📊 ESSENTIAL QUERIES

### 1. Quick Status Check
```sql
SELECT 
    COUNT(*) as total_processed,
    SUM(CASE WHEN extraction_success THEN 1 ELSE 0 END) as successful,
    SUM(foreign_citations_count) as foreign,
    SUM(international_citations_count) as international,
    ROUND(AVG(total_cost_usd), 4) as avg_cost,
    ROUND(SUM(total_cost_usd), 2) as total_cost
FROM citation_extraction_phased_summary;
```

### 2. Latest Processing Results
```sql
SELECT 
    document_id,
    total_references_extracted,
    foreign_citations_count + international_citations_count as cross_jurisdictional,
    average_confidence,
    items_requiring_review,
    extraction_success,
    created_at
FROM citation_extraction_phased_summary
ORDER BY created_at DESC
LIMIT 10;
```

### 3. Tier Performance
```sql
SELECT 
    origin_identification_tier,
    CASE origin_identification_tier
        WHEN 1 THEN 'Dictionary'
        WHEN 2 THEN 'Sonnet'
        WHEN 3 THEN 'Web Search'
        ELSE 'Failed'
    END as tier_name,
    COUNT(*) as citations,
    ROUND(AVG(origin_confidence), 3) as avg_confidence,
    COUNT(*) FILTER (WHERE requires_manual_review) as needs_review
FROM citation_extraction_phased
GROUP BY origin_identification_tier
ORDER BY origin_identification_tier;
```

### 4. Citation Type Distribution
```sql
SELECT 
    citation_type,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) as percentage
FROM citation_extraction_phased
GROUP BY citation_type
ORDER BY count DESC;
```

### 5. Items for Manual Review
```sql
SELECT 
    case_name,
    case_law_origin,
    citation_type,
    origin_confidence,
    origin_identification_tier,
    manual_review_reason
FROM citation_extraction_phased
WHERE requires_manual_review = TRUE
ORDER BY origin_confidence ASC
LIMIT 20;
```

### 6. Most Cited Foreign Jurisdictions
```sql
SELECT 
    case_law_origin,
    case_law_region,
    COUNT(*) as citation_count
FROM citation_extraction_phased
WHERE citation_type IN ('Foreign Citation', 'Foreign International Citation')
GROUP BY case_law_origin, case_law_region
ORDER BY citation_count DESC
LIMIT 15;
```

### 7. Cost Analysis
```sql
SELECT 
    COUNT(DISTINCT document_id) as documents,
    SUM(total_api_calls) as total_api_calls,
    SUM(total_tokens_input) as input_tokens,
    SUM(total_tokens_output) as output_tokens,
    ROUND(SUM(total_cost_usd), 2) as total_cost_usd,
    ROUND(AVG(total_cost_usd), 4) as avg_cost_per_doc
FROM citation_extraction_phased_summary
WHERE extraction_success = TRUE;
```

### 8. Processing Time Stats
```sql
SELECT 
    MIN(total_processing_time_seconds) as min_time,
    AVG(total_processing_time_seconds) as avg_time,
    MAX(total_processing_time_seconds) as max_time,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total_processing_time_seconds) as median_time
FROM citation_extraction_phased_summary
WHERE extraction_success = TRUE;
```

### 9. Courts to Add to Dictionary
```sql
-- Find frequently cited courts not in Tier 1
SELECT 
    cited_court,
    case_law_origin,
    COUNT(*) as frequency
FROM citation_extraction_phased
WHERE origin_identification_tier > 1
  AND cited_court IS NOT NULL
GROUP BY cited_court, case_law_origin
HAVING COUNT(*) >= 3
ORDER BY frequency DESC
LIMIT 20;
```

### 10. Control Group Verification
```sql
-- Check specific known documents
SELECT 
    d.document_id,
    d.pdf_filename,
    s.total_references_extracted,
    s.foreign_citations_count,
    s.international_citations_count,
    s.average_confidence
FROM citation_extraction_phased_summary s
JOIN documents d ON s.document_id = d.document_id
WHERE d.pdf_filename IN (
    'thomsonvministerforclimatechangeissues_d2d9bebac91a8d4459fe50ee6b7083b8.pdf',
    'planbearthandothersvprimeminister_c6834502d9f262036de6b22123356f6e.pdf',
    'mathuretalvhermajestythequeeninrightofontario_b43295fec7c3835706eff71f4cd83db9_1.pdf'
);
```

---

## 🔍 DETAILED CITATION INSPECTION

### View All Citations from a Document
```sql
SELECT 
    case_name,
    citation_type,
    case_law_origin,
    case_law_region,
    origin_confidence,
    origin_identification_tier,
    citation_format,
    position_in_document
FROM citation_extraction_phased
WHERE document_id = 'YOUR_DOCUMENT_UUID_HERE'
ORDER BY position_in_document;
```

### View Citation Context
```sql
SELECT 
    case_name,
    raw_citation_text,
    context_before,
    context_after,
    full_paragraph
FROM citation_extraction_phased
WHERE document_id = 'YOUR_DOCUMENT_UUID_HERE'
  AND case_name = 'CASE_NAME_HERE';
```

---

## 📈 PERFORMANCE BENCHMARKS

### Target Metrics
| Metric | Target | Query |
|--------|--------|-------|
| Recall | ≥75% | Manual verification on control group |
| Precision | ≥85% | Manual verification on control group |
| Cost/doc | <$0.10 | Query #7 |
| Proc. Time | <60s | Query #8 |
| Tier 1 % | ≥60% | Query #3 (tier 1 / total) |
| Review % | <20% | (needs_review / total) from Query #3 |

---

## 🐛 TROUBLESHOOTING QUERIES

### Check for Errors
```sql
SELECT 
    document_id,
    extraction_error,
    created_at
FROM citation_extraction_phased_summary
WHERE extraction_success = FALSE
ORDER BY created_at DESC;
```

### Find Documents Not Yet Processed
```sql
SELECT 
    d.document_id,
    d.pdf_filename,
    c.case_name
FROM documents d
JOIN cases c ON d.case_id = c.case_id
WHERE d.is_decision = TRUE
  AND d.document_id NOT IN (
      SELECT document_id 
      FROM citation_extraction_phased_summary
  )
LIMIT 20;
```

### Check for Duplicate Processing
```sql
SELECT 
    document_id,
    COUNT(*) as process_count
FROM citation_extraction_phased_summary
GROUP BY document_id
HAVING COUNT(*) > 1;
```

---

## 🔧 CONFIGURATION SNIPPETS

### Enable Trial Batch (config.py)
```python
TRIAL_BATCH_CONFIG = {
    'ENABLED': True,
    'COLUMN_NAME': 'Trial Batch Phase 2',
    'TRUE_VALUES': ['x', 'X', True, 'TRUE', 'true']
}
```

### Disable Trial Batch (config.py)
```python
TRIAL_BATCH_CONFIG = {
    'ENABLED': False,
    'COLUMN_NAME': 'Trial Batch Phase 2',
    'TRUE_VALUES': ['x', 'X', True, 'TRUE', 'true']
}
```

### Adjust Confidence Threshold (in script)
```python
# Line ~1200 in extract_citations_v5_phased.py
# Current: 0.7
needs_review = confidence < 0.7

# More strict (flag more):
needs_review = confidence < 0.8

# Less strict (flag fewer):
needs_review = confidence < 0.6
```

---

## 📊 EXPORT QUERIES FOR ANALYSIS

### Export All Cross-Jurisdictional Citations
```sql
COPY (
    SELECT 
        c.case_name as citing_case,
        c.country as citing_country,
        cp.source_jurisdiction,
        cp.source_region,
        cp.case_name as cited_case,
        cp.case_law_origin,
        cp.case_law_region,
        cp.citation_type,
        cp.origin_confidence,
        cp.cited_court,
        cp.cited_year
    FROM citation_extraction_phased cp
    JOIN documents d ON cp.document_id = d.document_id
    JOIN cases c ON d.case_id = c.case_id
    WHERE cp.is_cross_jurisdictional = TRUE
    ORDER BY c.case_name, cp.position_in_document
) TO '/tmp/cross_jurisdictional_citations.csv' 
WITH CSV HEADER;
```

### Export North-South Citation Patterns
```sql
COPY (
    SELECT 
        cp.source_jurisdiction,
        cp.source_region,
        cp.case_law_origin,
        cp.case_law_region,
        cp.citation_type,
        COUNT(*) as citation_count
    FROM citation_extraction_phased cp
    WHERE cp.is_cross_jurisdictional = TRUE
    GROUP BY 
        cp.source_jurisdiction,
        cp.source_region,
        cp.case_law_origin,
        cp.case_law_region,
        cp.citation_type
    ORDER BY citation_count DESC
) TO '/tmp/north_south_patterns.csv' 
WITH CSV HEADER;
```

---

## 📝 NOTES

### Remember
- Always check `extraction_success = TRUE` in summary queries
- Phase 2 extracts ALL references (including domestic)
- Only cross-jurisdictional saved to `citation_extraction_phased`
- Confidence < 0.7 automatically flagged for review
- Cache builds during processing (improves speed for repeated cases)

### Common Pitfalls
- ❌ Forgetting to run schema migration first
- ❌ Not verifying documents are classified (`is_decision = TRUE`)
- ❌ Running without trial batch on first test
- ❌ Not checking log files for errors
- ❌ Assuming all references are saved (domestic excluded)

### Best Practices
- ✅ Always test on trial batch first
- ✅ Verify control group results before full run
- ✅ Monitor cost throughout processing
- ✅ Review flagged items regularly
- ✅ Expand dictionaries based on Tier 2+ results

---

**Quick Reference Version:** 1.0  
**Last Updated:** November 22, 2025  
**For:** Citation Extraction v5 Phased Implementation
