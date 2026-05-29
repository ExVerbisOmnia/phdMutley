# Plan: Decision-Filtered Pipeline (Phases 3-5)

## Context

After alignment with Lucas, the strategy is: **don't extract text from all 16,380 docs — classify first, then extract only decisions.** The Sabin `Document Type` column is unreliable, so we use **Document Title keywords** as the primary classifier, with **LLM fallback** for ambiguous docs.

**Classification logic (title-based):**

Sabin document titles follow the pattern `"Case Name - [keyword]"` (e.g., `"Smith v. EPA - judgment"`). The keyword after the last ` - ` separator is the document type signal. Documents fall into three buckets:

1. **Step A — Decision keyword match:** Title ends with a known decision keyword → `is_decision = TRUE`
2. **Step B — No keyword / ambiguous:** Title ends with `- Other` OR title has **no ` - ` separator at all** (no keyword) → LLM classification needed
3. **Skip — Non-decision keyword:** Title ends with a known non-decision keyword (complaint, motion, brief, petition, etc.) → `is_decision = FALSE`

**Numbers from analysis (16,380 total docs):**

| Bucket           | Criteria                          | Count     | Action                                 |
| ---------------- | --------------------------------- | ---------:| -------------------------------------- |
| Step A           | Title keyword = decision type     | **2,921** | Auto-classify `is_decision = TRUE`     |
| Step B           | Title keyword = `other`           | **580**   | Partial text extraction → LLM classify |
| Step B           | No ` - ` separator (no keyword)   | **3,504** | Partial text extraction → LLM classify |
| Skip             | Title keyword = non-decision type | **9,000** | Auto-classify `is_decision = FALSE`    |
| N/A              | No title in Excel                 | **375**   | Auto-classify `is_decision = FALSE`    |
| **Step B total** |                                   | **4,084** |                                        |

**Why Step B is large:** 3,504 docs have free-form titles without the standard `"Name - keyword"` pattern (e.g., *"D.C. Circuit Denied Rehearing on AIM Act Rule..."*). Among these, 696 have `Document Type = 'Decision'` in Sabin — but since Document Type is unreliable, all 4,084 go through LLM classification for accuracy.

**Token-to-char conversion:** 600 tokens ≈ 2,400 characters. First 2,400 + last 2,400 chars = ~4,800 chars per doc for LLM classification.

## Pipeline Steps

### Step A: Title-Based Classification (rule-based, $0)

**New script:** `scripts/classify_by_title.py`

Reads the Sabin Excel, extracts the **keyword** from `Document Title` (text after last ` - ` separator). Matches against decision keywords:

**Decision keywords (case-insensitive):**

```
judgment, decision, order, ruling, sentence, sentencia, arrêt, urteil,
decreto, acórdão, verdict, opinion, opinion and order, memorandum opinion,
memorandum opinion and order, memorandum decision, memorandum and order,
minute order, order to show cause, order list, order denying petition for review,
administrative order, consent order, consent decree, consent decree/order,
findings of fact and conclusions of law, findings and recommendations,
report and recommendation, tentative ruling, minute proceedings
```

For each document in the DB:

- **Keyword matches decision list** → set `is_decision = TRUE`, `decision_classification_method = 'title_keyword'`, `confidence = 0.95`
- **Keyword matches non-decision list** (complaint, motion, brief, etc.) → set `is_decision = FALSE`, `decision_classification_method = 'title_keyword_excluded'`, `confidence = 0.95`
- **Keyword = "other" OR no separator** → leave `is_decision = NULL` (Step B handles these)
- **No title at all** → set `is_decision = FALSE`, `decision_classification_method = 'no_title'`, `confidence = 1.0`

**SQL logic (decision match):**

```sql
UPDATE documents
SET is_decision = TRUE,
    decision_classification_method = 'title_keyword',
    decision_classification_confidence = 0.95,
    decision_classification_date = NOW()
WHERE document_id = :uuid
  AND is_decision IS NULL;
```

**Input:** Sabin Excel `Document Title` column
**Output:** ~2,921 docs → `is_decision = TRUE`, ~9,375 docs → `is_decision = FALSE`, ~4,084 docs → `NULL` (pending Step B)

### Step B: LLM Classification for Ambiguous Docs

**New script:** `scripts/classify_ambiguous_docs.py`

For the **4,084 docs** with either `- Other` keyword or **no keyword** (no ` - ` separator in title):

1. **Extract partial text** from their PDFs: first 2,400 chars + last 2,400 chars (~1,200 tokens total)
2. **Send to Gemini** with classification prompt: "Is this a judicial decision? Respond TRUE/FALSE with confidence."
3. **Update DB:** set `is_decision`, `decision_classification_method = 'llm_partial_text'`, confidence from model
4. **Docs without downloaded PDFs:** set `is_decision = FALSE`, `method = 'no_pdf'`, `confidence = 0.5`

**Partial extraction approach:**

- Open PDF with pdfplumber (fastest)
- Extract text from first 2 pages + last 2 pages
- Truncate to first 2,400 chars + last 2,400 chars
- No DB write for extracted text (just classification)

**Workers:** 8 (matching local machine's 8 logical processors, ~8 GB RAM — headroom is sufficient since each pdfplumber worker uses ~200 MB)

**Cost:** ~4,084 docs × ~$0.001/doc (small context) = **~$4.08**

### Step C: Classification Aggregation

**In the same script as Step B (or a small aggregation step):**

After Steps A and B complete:

1. All docs with `is_decision = TRUE` (from A + B) are **decision candidates**
2. All remaining NULL docs → set `is_decision = FALSE`, `method = 'unclassified_default'`
3. Log summary: X decisions from title, Y decisions from LLM, Z non-decisions

**Expected totals:**

- ~2,921 decisions from title keywords (Step A)
- ~800-1,100 additional decisions from LLM classification (Step B estimate — ~696 have `Document Type = Decision` in Sabin)
- Total decisions: **~3,700-4,000**

### Step D: Text Extraction (decisions only, 8 workers, plain text)

**Modified file:** `scripts/3-extract-texts/extract_texts.py`

Add decision-only filter:

- After loading PDF file list, query `documents WHERE is_decision = TRUE` for document IDs
- Filter `pdf_files` to only include matching PDFs
- Skip already-extracted docs (existing idempotency check)
- `SAFE_WORKERS = 8` (8 logical processors, ~8 GB RAM), `--format plain`

**Estimate:** ~3,700-4,000 decision PDFs, ~348 already extracted

- New extractions: ~3,350-3,650
- At ~37 docs/min with 8 workers: **~90-100 minutes**

### Step E: Citation Extraction (Phase 5)

**No changes to:** `scripts/5-extract-citations/extract_citations.py`

Already filters by `is_decision = TRUE` AND `raw_text IS NOT NULL`.

- 31 already done from prior run
- ~3,700-4,000 new documents to process
- Uses Gemini API (~$0.002/doc)

**Cost:** ~4,000 × $0.002 = **~$8.00**

### Step F: Export and Manual Review

```bash
python scripts/export_to_excel.py
```

- Excel file with enriched citation sheets (case_name, URLs) from earlier session's work
- `_data_quality` sheet shows download/extraction failures
- **Wait for Lucas's manual inspection** before proceeding further

## Files to Create/Modify

| File                                       | Action     | Description                                                               |
| ------------------------------------------ | ---------- | ------------------------------------------------------------------------- |
| `scripts/classify_by_title.py`             | **CREATE** | Step A: title keyword classification + non-decision exclusion             |
| `scripts/classify_ambiguous_docs.py`       | **CREATE** | Step B: partial extraction + LLM classification for no-keyword/Other docs |
| `scripts/3-extract-texts/extract_texts.py` | **MODIFY** | Add `--decisions-only` flag to filter PDFs by `is_decision = TRUE`        |

**No changes needed to:**

- `scripts/5-extract-citations/extract_citations.py` — already filters by `is_decision = TRUE`
- `scripts/export_to_excel.py` — already enriched from earlier session
- `scripts/config.py` — no config changes

## Cost Summary

| Step                      | Docs   | API Cost       |
| ------------------------- | ------ | -------------- |
| A: Title classification   | 2,921  | $0             |
| A: Non-decision exclusion | 9,375  | $0             |
| B: LLM classification     | 4,084  | ~$4.08         |
| D: Text extraction        | ~3,700 | $0 (local CPU) |
| E: Citation extraction    | ~4,000 | ~$8.00         |
| **Total**                 |        | **~$12.08**    |

## Workers & Machine Constraints

**Local machine:** 8 logical processors, ~8 GB RAM

| Task                         | Workers            | Bottleneck       | RAM per worker | Total RAM est. |
| ---------------------------- | ------------------ | ---------------- | -------------- | -------------- |
| Step B (partial PDF + LLM)   | 8                  | I/O (API calls)  | ~200 MB        | ~1.6 GB        |
| Step D (full PDF extraction) | 8                  | CPU (pdfplumber) | ~200 MB        | ~1.6 GB        |
| Step E (citation extraction) | 1 (sequential API) | API rate limit   | N/A            | N/A            |

`SAFE_WORKERS = 8` — matches `os.cpu_count()`. With ~8 GB total RAM and ~2 GB for OS + PostgreSQL, 8 workers × 200 MB = 1.6 GB leaves comfortable headroom.

## GCP VM Reference (Optional Acceleration)

If you want to offload the CPU work to a VM and free up your local machine:

### Recommended Options

| Machine Type     | vCPUs | RAM    | Workers | Spot $/hr | On-Demand $/hr | Est. Phase D Time |
| ---------------- | ----- | ------ | ------- | --------- | -------------- | ----------------- |
| `e2-standard-8`  | 8     | 32 GB  | 8       | ~$0.12    | ~$0.27         | ~100 min          |
| `e2-standard-16` | 16    | 64 GB  | 16      | ~$0.25    | ~$0.54         | ~50 min           |
| `e2-standard-32` | 32    | 128 GB | 32      | ~$0.49    | ~$1.07         | ~25 min           |

**Worker formula:** `min(vCPUs, RAM_GB // 2)` — each worker uses ~200 MB but we budget 2 GB headroom per worker for safety. On VMs with abundant RAM, workers = vCPUs.

**Disk:** 50 GB `pd-balanced` (~$0.10/GB/month, prorated to pennies)

### VM Workflow

1. **Local → VM: Export**
   
   - `pg_dump -U phdmutley -p 5433 -d climate_litigation -Fc > db.dump` (local DB)
   - Upload `db.dump` + filtered decision PDFs (only ~3,700 files, ~3-4 GB estimated) via SCP or GCS bucket
   - VM receives only the PDFs flagged by Step C — not all 14 GB

2. **On VM: Run**
   
   - Install PostgreSQL + Python + deps
   - `pg_restore` the dump
   - Run Steps D and E
   - `pg_dump` the updated DB

3. **VM → Local: Import**
   
   - Download the updated `db.dump`
   - `pg_restore -U phdmutley -p 5433 -d climate_litigation --clean --no-owner db.dump`
   - Run Step F (export) locally

4. **Cleanup:** Delete VM instance

**Total VM cost estimate:** < $2.00 for the entire job (Spot pricing, ~1-2 hours)

### Setup Requirements

- `gcloud` CLI installed locally (`gcloud --version`)
- Lucas's GCP project ID
- Compute Engine API enabled in the project
- Gemini API key accessible on VM (via env var or Secret Manager)

## Verification Checklist

1. After Step A: `SELECT COUNT(*) FROM documents WHERE is_decision = TRUE AND decision_classification_method = 'title_keyword'` → ~2,921
2. After Step A: `SELECT COUNT(*) FROM documents WHERE is_decision = FALSE AND decision_classification_method LIKE 'title_keyword%'` → ~9,375
3. After Step B: `SELECT COUNT(*) FROM documents WHERE decision_classification_method = 'llm_partial_text'` → ~4,084 classified (some TRUE, some FALSE)
4. After Step C: `SELECT COUNT(*) FROM documents WHERE is_decision = TRUE` → ~3,700-4,000
5. After Step D: `SELECT COUNT(*) FROM extracted_text et JOIN documents d ON et.document_id = d.document_id WHERE d.is_decision = TRUE` → matches Step C count
6. After Step E: `SELECT COUNT(DISTINCT document_id) FROM citation_extraction_phased_summary WHERE extraction_success = TRUE` → close to Step C count
7. Step F: Excel export opens cleanly, citation sheets have case_name and URLs, _data_quality sheet present
