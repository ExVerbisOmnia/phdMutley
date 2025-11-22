# Citation Extraction v5 - Implementation Guide
## Deployment Checklist and Instructions

**Created:** November 22, 2025  
**Status:** Ready for Deployment  
**Location:** `/home/claude/`

---

## 📦 FILES CREATED

### 1. Database Schema Migration
**File:** `migrate_citation_phased_schema.sql`
- Creates `citation_extraction_phased` table
- Creates `citation_extraction_phased_summary` table
- Adds indexes for performance
- Includes triggers for timestamp management

### 2. Main Extraction Script
**File:** `extract_citations_v5_phased.py`
- Complete 4-phase extraction architecture
- Enhanced dictionaries (80+ courts, 20+ landmark cases)
- 3-tier origin identification
- Caching system for repeated citations
- Comprehensive error handling and logging

---

## 🚀 DEPLOYMENT STEPS

### Step 1: Deploy Database Schema

```bash
# Navigate to your project directory
cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley

# Copy SQL file from Claude's workspace
cp /home/claude/migrate_citation_phased_schema.sql ./scripts/phase2/

# Run migration using psql or DBeaver
# Option A: Using psql
psql -h localhost -U your_username -d phdMutley -f scripts/phase2/migrate_citation_phased_schema.sql

# Option B: Using DBeaver
# - Open DBeaver
# - Connect to phdMutley database
# - Open SQL Editor
# - Load migrate_citation_phased_schema.sql
# - Execute script
```

### Step 2: Verify Schema Creation

```sql
-- Run these queries in DBeaver or psql to verify:

-- Check tables exist
SELECT table_name 
FROM information_schema.tables 
WHERE table_name IN ('citation_extraction_phased', 'citation_extraction_phased_summary');

-- Check indexes
SELECT indexname, tablename
FROM pg_indexes 
WHERE tablename IN ('citation_extraction_phased', 'citation_extraction_phased_summary')
ORDER BY tablename, indexname;

-- Expected output:
-- citation_extraction_phased (main table)
-- citation_extraction_phased_summary (summary table)
-- 6+ indexes created
```

### Step 3: Deploy Python Script

```bash
# Copy script to your project
cp /home/claude/extract_citations_v5_phased.py ./scripts/phase2/

# Verify file location
ls -lh ./scripts/phase2/extract_citations_v5_phased.py

# Make executable
chmod +x ./scripts/phase2/extract_citations_v5_phased.py
```

### Step 4: Test on Small Sample

```bash
# First, enable trial batch mode in config.py
# Set TRIAL_BATCH_CONFIG['ENABLED'] = True
# Ensure you have 5-10 documents marked in trial batch

# Run the script
python scripts/phase2/extract_citations_v5_phased.py

# Monitor log output for:
# - Phase 1: Source jurisdiction identification
# - Phase 2: Extraction counts
# - Phase 3: Origin identification tier usage
# - Phase 4: Classification results
```

### Step 5: Verify Results

```sql
-- Check summary table
SELECT 
    document_id,
    total_references_extracted,
    foreign_citations_count,
    international_citations_count,
    foreign_international_citations_count,
    average_confidence,
    items_requiring_review,
    extraction_success
FROM citation_extraction_phased_summary
ORDER BY created_at DESC
LIMIT 10;

-- Check detailed citations
SELECT 
    case_name,
    source_jurisdiction,
    case_law_origin,
    citation_type,
    origin_identification_tier,
    origin_confidence,
    requires_manual_review
FROM citation_extraction_phased
ORDER BY created_at DESC
LIMIT 20;

-- Performance metrics by tier
SELECT 
    origin_identification_tier,
    COUNT(*) as citations,
    AVG(origin_confidence) as avg_confidence,
    COUNT(*) FILTER (WHERE requires_manual_review = TRUE) as needs_review
FROM citation_extraction_phased
GROUP BY origin_identification_tier
ORDER BY origin_identification_tier;
```

---

## 🧪 TESTING PROTOCOL

### Control Group Documents

Test the script on these known documents from your project:

1. **Thomson v Minister (NZ)** - Should find Urgenda citation
2. **Plan B Earth v PM (UK)** - Should find Massachusetts v. EPA
3. **Mathur v Ontario (Canada)** - Should find international references
4. **Friends of Irish Environment** - Should find European cases
5. **Greenpeace Nordic v Norway** - Should find comparative law

### Success Criteria

For each test document, verify:

✅ **Phase 1:** Correct source jurisdiction identified  
✅ **Phase 2:** All case references extracted (not just foreign)  
✅ **Phase 3:** Origin correctly identified for known cases  
✅ **Phase 4:** Proper classification (Foreign/International/Foreign International)  
✅ **Quality:** Confidence scores ≥ 0.70 for dictionary/Sonnet matches  
✅ **Performance:** Processing time < 60 seconds per document  
✅ **Cost:** Total cost < $0.10 per document  

### Expected Performance Improvements

| Metric | v4 (Old) | v5 (New) | Target |
|--------|----------|----------|--------|
| **Recall** | 40-50% | 75-85% | ≥75% |
| **Precision** | 95% | 85-90% | ≥85% |
| **Cost per doc** | $0.02-0.05 | $0.02-0.05 | Similar |

---

## 📊 MONITORING & VALIDATION

### Key Metrics to Monitor

1. **Extraction Rate**
   ```sql
   SELECT 
       COUNT(*) as total_processed,
       SUM(CASE WHEN extraction_success THEN 1 ELSE 0 END) as successful,
       ROUND(AVG(total_references_extracted), 2) as avg_references_per_doc,
       ROUND(AVG(foreign_citations_count + international_citations_count), 2) as avg_cross_jurisdictional
   FROM citation_extraction_phased_summary;
   ```

2. **Tier Performance**
   ```sql
   SELECT 
       origin_identification_tier,
       COUNT(*) as count,
       ROUND(AVG(origin_confidence), 3) as avg_confidence,
       COUNT(*) FILTER (WHERE requires_manual_review) as needs_review
   FROM citation_extraction_phased
   GROUP BY origin_identification_tier
   ORDER BY origin_identification_tier;
   ```

3. **Cost Analysis**
   ```sql
   SELECT 
       COUNT(*) as documents,
       SUM(total_api_calls) as total_calls,
       SUM(total_tokens_input) as total_input_tokens,
       SUM(total_tokens_output) as total_output_tokens,
       ROUND(SUM(total_cost_usd), 2) as total_cost,
       ROUND(AVG(total_cost_usd), 4) as avg_cost_per_doc
   FROM citation_extraction_phased_summary
   WHERE extraction_success = TRUE;
   ```

4. **Citation Type Distribution**
   ```sql
   SELECT 
       citation_type,
       COUNT(*) as count,
       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage
   FROM citation_extraction_phased
   GROUP BY citation_type
   ORDER BY count DESC;
   ```

5. **Items Requiring Manual Review**
   ```sql
   SELECT 
       document_id,
       case_name,
       case_law_origin,
       origin_confidence,
       manual_review_reason
   FROM citation_extraction_phased
   WHERE requires_manual_review = TRUE
   ORDER BY origin_confidence ASC
   LIMIT 50;
   ```

---

## 🔧 CONFIGURATION OPTIONS

### Trial Batch Mode

In `config.py`:

```python
TRIAL_BATCH_CONFIG = {
    'ENABLED': True,  # Set to True for testing, False for full run
    'COLUMN_NAME': 'Trial Batch Phase 2',
    'TRUE_VALUES': ['x', 'X', True, 'TRUE', 'true']
}
```

### Confidence Threshold for Manual Review

In script (line ~1200+), you can adjust:

```python
# Current threshold: 0.7
needs_review = confidence < 0.7

# To be more/less strict:
needs_review = confidence < 0.8  # More items for review
needs_review = confidence < 0.6  # Fewer items for review
```

### Dictionary Expansion

To add more courts or cases, edit the dictionaries in the script:

```python
# Add to KNOWN_FOREIGN_COURTS (line ~220)
"Your Court Name": {"country": "Country", "region": "Global North/South", "type": "Type"}

# Add to LANDMARK_CLIMATE_CASES (line ~290)
"Case Short Name": {"full_name": "Full Case Name", "country": "Country", ...}
```

---

## 🐛 TROUBLESHOOTING

### Common Issues

**Issue 1: "Table does not exist"**
- **Solution:** Run the migration script first (`migrate_citation_phased_schema.sql`)

**Issue 2: "No documents to process"**
- **Check:** Are documents classified? (`is_decision = True`)
- **Check:** Are they in trial batch? (if enabled)
- **Check:** Already processed? (check `citation_extraction_phased_summary`)

**Issue 3: High cost per document**
- **Cause:** Many Tier 2 (Sonnet) lookups
- **Solution:** Expand KNOWN_FOREIGN_COURTS dictionary
- **Solution:** Review cases triggering Tier 2 and add to LANDMARK_CLIMATE_CASES

**Issue 4: Low confidence scores**
- **Cause:** Ambiguous citations or missing context
- **Solution:** Manual review flagged items
- **Solution:** Add found cases to dictionaries for future runs

**Issue 5: "JSON parse error"**
- **Cause:** LLM returned malformed JSON
- **Check:** Log file for raw LLM response
- **Solution:** Usually temporary - retry the document

---

## 📈 OPTIMIZATION TIPS

### 1. Expand Dictionaries Based on Results

After initial run:

```sql
-- Find commonly cited courts not in dictionary (Tier 2+)
SELECT 
    cited_court,
    case_law_origin,
    COUNT(*) as frequency
FROM citation_extraction_phased
WHERE origin_identification_tier > 1
GROUP BY cited_court, case_law_origin
HAVING COUNT(*) > 3
ORDER BY frequency DESC;

-- Add these to KNOWN_FOREIGN_COURTS for future runs
```

### 2. Cache Utilization

The script includes a cache for repeated citations. Monitor cache hits:

```python
# Cache statistics are logged at the end
# Look for: "Cache size: X entries"
```

### 3. Batch Processing

For large datasets:

```bash
# Process in batches using trial batch
# Batch 1: Documents 1-100
# Batch 2: Documents 101-200
# etc.

# Or modify script to process by date ranges
```

---

## 📁 FILE LOCATIONS SUMMARY

```
/home/gusrodgs/Gus/cienciaDeDados/phdMutley/
├── scripts/
│   └── phase2/
│       ├── extract_citations_v4.py (old version - keep for reference)
│       ├── extract_citations_v5_phased.py (NEW - main script)
│       └── migrate_citation_phased_schema.sql (NEW - database schema)
├── logs/
│   └── citation_extraction_v5.log (created automatically)
└── config.py (existing - no changes needed)
```

---

## ✅ PRE-DEPLOYMENT CHECKLIST

Before running on full dataset:

- [ ] Database schema deployed and verified
- [ ] Script copied to correct location
- [ ] Trial batch enabled with 5-10 test documents
- [ ] Test run completed successfully
- [ ] Results verified in database
- [ ] Control group documents tested (known citations found)
- [ ] Performance metrics acceptable (recall ≥75%, precision ≥85%)
- [ ] Cost per document acceptable (<$0.10)
- [ ] Confidence thresholds reviewed
- [ ] Manual review process established

---

## 🎯 NEXT STEPS

1. **Deploy schema** → Run SQL migration
2. **Test on trial batch** → 5-10 documents
3. **Verify results** → Check database queries
4. **Review flagged items** → Low confidence citations
5. **Expand dictionaries** → Add frequently found courts/cases
6. **Full deployment** → Disable trial batch, run on all documents
7. **Continuous monitoring** → Track performance metrics
8. **Manual review workflow** → Process flagged citations

---

## 📞 SUPPORT

If issues arise during deployment:

1. Check log file: `logs/citation_extraction_v5.log`
2. Review error messages in terminal output
3. Query database for processing status
4. Verify configuration in `config.py`
5. Contact Lucas for academic/methodological questions

---

**Document Version:** 1.0  
**Last Updated:** November 22, 2025  
**Status:** Ready for Deployment
