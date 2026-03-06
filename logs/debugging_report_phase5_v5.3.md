# Phase 5 Citation Extraction v5.3 — Debugging Report

**Date:** 2026-03-05
**Script:** `scripts/5-extract-citations/extract_citations.py`
**Run:** 31 documents (all classified decisions from test pipeline)

---

## Summary

Phase 5 citation extraction v5.3 processed 31 judicial decisions. The debugging session identified and fixed **10 bugs** across 2 cycles of analysis-fix-test. Bugs ranged from critical (wrong dictionary key causing 100% functional classification failure) to low (cosmetic cursor error). Total API cost for the debugging run: ~$6-8 (inflated by Bug 6).

---

## Bug Inventory

### Bug 1 (CRITICAL) — Functional classification wrong dict key
- **File:** `extract_citations.py:1526` (original line)
- **Root cause:** `result.get("parsed")` but `call_gemini()` returns key `"data"`
- **Impact:** ALL functional classifications returned `{}`. Every citation had `functional_use=unknown`
- **Fix:** `result.get("parsed")` -> `result.get("data")`
- **Status:** FIXED, VERIFIED

### Bug 2 (HIGH) — UniqueViolation from duplicate extracted_text rows
- **File:** `extract_citations.py:2195` (original line)
- **Root cause:** JOIN `Document <- ExtractedText <- Case` produces duplicates when a document has >1 extracted_text row. First succeeds, second hits UniqueViolation, poisons session.
- **Impact:** 2 documents failed, next document got PendingRollbackError
- **Fix:** (a) `.distinct(Document.document_id)` on query, (b) `session.rollback()` before error summary insert, (c) cleaned 6 duplicate extracted_text rows in DB
- **Status:** FIXED, VERIFIED

### Bug 3 (MEDIUM) — JSON parse failure no retry or logging
- **File:** `extract_citations.py:1285-1292` (original lines)
- **Root cause:** When Gemini returns non-JSON, silently skips document
- **Fix:** (a) Log raw response (first 500 chars), (b) Retry with `response_mime_type="application/json"` (later flipped: use response_mime_type by default, retry without)
- **Status:** FIXED, VERIFIED

### Bug 4 (MEDIUM) — Phase 2A failure creates no summary record
- **File:** `extract_citations.py:1866-1869` (original lines)
- **Root cause:** Failed documents have no summary -> retried on every run, burning API calls
- **Fix:** Create `extraction_success=False` summary when Phase 2A fails
- **Status:** FIXED (code in place, not triggered in test runs)

### Bug 5 (LOW) — Named cursor error on exit
- **File:** `extract_citations.py:2237` (original line)
- **Root cause:** `yield_per(50)` creates server-side cursor that becomes invalid after commits
- **Fix:** `query.yield_per(50)` -> `query.all()`
- **Status:** FIXED, VERIFIED

### Bug 6 (CRITICAL) — MAX_OUTPUT_TOKENS=65536 causes repetitive JSON output
- **File:** `extract_citations.py:126`
- **Root cause:** `response_mime_type="application/json"` + high token limit causes Gemini to fill budget with repeated JSON entries. Cost $1+/doc instead of $0.06/doc.
- **Impact:** 2 documents hit $1+ cost (30x normal). Total run cost inflated by ~$2.
- **Fix:** (a) `MAX_OUTPUT_TOKENS = 16384`, (b) Anti-repetition instruction in prompt, (c) Fallback retry without response_mime_type
- **Status:** FIXED (applied for next run)

### Bug 7 (MEDIUM) — Functional classification fails for >30 citations
- **File:** `extract_citations.py:1521`
- **Root cause:** `citations[:30]` truncation in prompt; documents with >30 refs only classify first 30
- **Impact:** Doc with 42 refs: only 30 classified. Doc with 88 refs: only 30 classified.
- **Fix:** Batch processing in `classify_citations_functionally()` — splits into 30-citation batches, calls Gemini per batch, merges results
- **Status:** FIXED (applied for next run)

### Bug 8 (MEDIUM) — Treaties and academic references extracted as case law
- **File:** `extract_citations.py:1186-1298` (extraction prompt)
- **Root cause:** Prompt says "extract EVERYTHING" without distinguishing case law from treaties/academic refs. "Acordo de Paris" (Paris Agreement), "Hogg" (author), academic article citations all extracted.
- **Impact:** False positive citations inflating counts, wasting Tier 2 API calls on non-cases
- **Fix:** Added explicit exclusion instructions: "Do NOT extract treaties, conventions, statutes" and "Do NOT extract academic articles, books, or author names"
- **Status:** FIXED (applied for next run)

### Bug 9 (MEDIUM) — Tier 2 LLM fails for abbreviated case names
- **File:** `extract_citations.py:1687-1772`
- **Root cause:** Abbreviated domestic case names ("Sparrow", "Hodges", "Marsh", "N.C. Alliance", "Overton Park") have no citation format signals. Tier 2 prompt didn't emphasize defaulting to source jurisdiction.
- **Impact:** 30+ domestic citations per large US/Canadian document sent to Tier 2, all failing
- **Fix:** Improved Tier 2 prompt with explicit rule: "abbreviated case names without citation format are almost always domestic" + "default to source jurisdiction with confidence 0.7+"
- **Status:** FIXED (applied for next run)

### Bug 10 (MEDIUM) — Domestic detection patterns too narrow
- **File:** `extract_citations.py:1790-1900`
- **Root cause:** Canada patterns only covered `SCC|SCR|FC`. Missing `ABCA, BCCA, ONCA, DLR, WWR, CCC, CR` and `Reference re` pattern. South Africa missing provincial court codes and reporter abbreviations. US `v.` pattern too broad (matched every case).
- **Impact:** Most Canadian and South African domestic citations fell through to Tier 2
- **Fix:** Expanded patterns for Canada (15+ court codes, 6 reporters, "Reference re"), South Africa (8+ provincial codes, 4 reporters, entity patterns), and narrowed US patterns
- **Status:** FIXED (applied for next run)

---

### Bug 11 (HIGH) — Thinking tokens consuming output budget
- **File:** `gemini_client.py:69-74`
- **Root cause:** Gemini 2.5 Flash-Lite has thinking enabled by default. Thinking tokens (512-24,576) consume `max_output_tokens`, reducing actual output capacity. With 16K limit, up to 24K could be wasted on thinking.
- **Impact:** Output truncation on medium-length documents, lost citations
- **Fix:** Added `ThinkingConfig(thinking_budget=0)` to `call_gemini()` — disables thinking since we use `temperature=0.0` anyway
- **Status:** FIXED
- **Source:** google-genai SDK docs, GitHub issues #1039, #782

## Additional Issues (non-bug)

### cp1252 Unicode logging
- Windows Python logging with UTF-8 emojis fails on cp1252 console
- Fixed with explicit UTF-8 StreamHandler + `force=True` on `basicConfig`

### datetime.utcnow() deprecation
- Changed to `datetime.now(timezone.utc)` in 4 locations

---

## Cost Analysis (Current Run, 31 docs)

| Category | Count | Total Cost | Avg/Doc |
|----------|-------|-----------|---------|
| Healthy docs (<$0.20) | ~24 | ~$1.50 | $0.06 |
| Repetitive output docs (>$1.00) | 2 | ~$2.04 | $1.02 |
| Large chunked docs | ~3 | ~$1.50 | $0.50 |
| **TOTAL** | **~29** | **~$5.00** | **$0.17** |

With Bug 6 fix (MAX_OUTPUT_TOKENS=16384), expected cost for full 2,924-doc run: ~$175 (within $200 budget).

---

## Files Modified

| File | Changes |
|------|---------|
| `scripts/5-extract-citations/extract_citations.py` | Bugs 1-10, logging fix, datetime fix |
| `scripts/gemini_client.py` | Added `response_mime_type` parameter support |

---

## Verification Plan (Next Run)

1. Delete existing summaries: `DELETE FROM citation_extraction_phased_summary;`
2. Delete existing citations: `DELETE FROM citation_extraction_phased;`
3. Run: `cd scripts/5-extract-citations && python extract_citations.py --test-run 10`
4. Verify:
   - No $1+ cost documents (Bug 6 fix)
   - Functional classification count matches total citations (Bug 7 fix)
   - No "Acordo de Paris" or author names extracted (Bug 8 fix)
   - Fewer "Could not identify origin" warnings (Bugs 9-10 fix)
   - Canadian "Reference re" cases identified as domestic
   - South African cases with "(Pty) Ltd" identified as domestic
