# Phase 1 Test Issues Log
# Created: 2026-03-08
# Purpose: Track all issues found during Phase 1 verification testing

## FINAL STATUS: ALL FIXES APPLIED AND VERIFIED

Re-test passed on 2026-03-08 23:37. All 5 documents processed successfully.
- Phase 5 inline verification: CONFIRMED 1 citation (Pakistan doc)
- DB verification columns populated correctly
- Thinking mode active (thinking_config accepted by SDK)
- Sequential mode now uses async code path

## Test Setup
- 5 small documents (5K chars each) cleared and re-extracted
- Pipeline ran in sequential mode (no `--concurrent` flag)
- All docs: Australia, US/DC, US/RI, Pakistan/Punjab

## Issues Found

### ISSUE-1 [CRITICAL] — Sync code path missing ALL Phase 1 improvements

**Impact:** All Phase 1 features are dead code when running in sequential mode.

The sequential code path calls `process_single_document_phased()` (line 1966), which has
NONE of the v7 improvements. All new features only exist in `process_single_document_phased_async()`
(line 2734):

- Phase 0 (quality pre-check) — only in async (line 2761)
- Hard filters (pipe-format, anachronism) — only in async (line 2842)
- Phase 5 (inline verification) — only in async (line 3057)

**Evidence:**
- Logs show NO "Phase 0:", "Hard filters:", or "Phase 5:" lines
- DB: all 4 extracted citations have `verification_status=NULL`
- DB: summary rows have `verified_confirmed=0, verified_not_found=0, verified_misattributed=0`

**Root cause:** `main()` line 3430 calls the sync function. The async function at line 2734
is only called when `--concurrent N` flag is used (line 3390).

**Fix:** Port Phase 0, hard filters, and Phase 5 into the sync `process_single_document_phased()`,
OR make async the default code path (even for sequential).

### ISSUE-2 [HIGH] — Sync `call_gemini()` calls lack `thinking_budget`

**Impact:** Thinking mode is never enabled when running in sequential mode.

Lines 1204, 1221, 1502, 1515, 1647 all call `call_gemini()` without `thinking_budget`.
Only the async `call_gemini_async()` calls (lines 2413, 2428, 2545, 2556, 2627) pass it.

**Fix:** Add `thinking_budget=1024` to extraction calls and `thinking_budget=2048` to
classification calls in the sync functions.

### ISSUE-3 [MEDIUM] — `document_year` not passed to extraction prompt

**Impact:** The prompt's anachronism self-check ("this document CANNOT cite cases from after this year")
is never included in the prompt, reducing anti-hallucination effectiveness.

`generate_v6_extraction_prompt()` accepts `document_year` param (extraction_prompt_v6.py:53),
but neither sync (line 1196) nor async (line 2405) callers pass it. The async path computes
`document_year` at line 2827-2840 but only uses it for `apply_hard_filters()` (line 2843).

**Fix:** Pass `document_year` to `generate_v6_extraction_prompt()` in both sync and async callers.

### ISSUE-4 [MEDIUM] — Quality flags not populated for pre-existing documents

**Impact:** Documents already extracted before the code update still have NULL quality flags
(`is_garbled`, `is_too_long`, `text_char_count`, `text_token_estimate`).

Phase 0 in the async path checks `is_garbled_text(raw_text)` at runtime (line 2762) but doesn't
write the result back to the `documents` table. Quality flags are only set during text extraction
(Step 1C.3), which won't re-run for already-extracted docs.

**Evidence:** All 5 test docs show `garbled=None, too_long=None, chars=None, tokens=None` after extraction.

**Fix:** Either (a) add a backfill query to compute quality flags for all existing docs, or
(b) have the extraction pipeline compute and store flags on first encounter when they're NULL.

### ISSUE-5 [LOW] — Banner version labels outdated

**Impact:** Cosmetic only. Misleading version identifiers.

- Line ~1: "CITATION EXTRACTION v6.0 - KB-ENHANCED PIPELINE" (KB removed in v7)
- Line 3436: "EXTRACTION COMPLETE - FINAL STATISTICS (v5.3)"

**Fix:** Update version labels to v7.0.

### ISSUE-6 [LOW] — JSON truncation on short responses

**Impact:** Minor — auto-repair succeeds, but indicates potential data loss risk on larger responses.

**Evidence:** Doc 3abb92d7 Phase 3 origin ID:
```
JSON parse failed (20 tokens out) — attempting truncated JSON repair
Truncated JSON repair succeeded (trimmed 9 chars, closed 1 braces + 0 brackets)
```

This happened for a Tier 2 origin ID call with only 20 output tokens. The model may be
truncating very short JSON responses.

**Fix:** Consider increasing `max_output_tokens` for origin ID calls, or adding a retry
with explicit "return valid JSON" instruction.

### ISSUE-7 [INFO] — Hard filters not testable on small docs

The 5 test documents didn't trigger pipe-format or anachronism filters. While the functions
unit-tested correctly, the integration wasn't exercised in the end-to-end test because:
- No citations had `|` pipe characters
- No anachronistic citations were extracted (Flash model with KB-removed prompt is cleaner)

Not a bug — just a testing coverage gap.

## Summary

| Issue | Severity | Category |
|-------|----------|----------|
| ISSUE-1 | CRITICAL | Sync/async code path divergence |
| ISSUE-2 | HIGH | Missing thinking in sync path |
| ISSUE-3 | MEDIUM | Missing prompt parameter |
| ISSUE-4 | MEDIUM | Backfill needed for quality flags |
| ISSUE-5 | LOW | Cosmetic version labels |
| ISSUE-6 | LOW | JSON truncation edge case |
| ISSUE-7 | INFO | Test coverage gap |

---

## Fix Plan

### Strategy: Unify to async-only code path

Instead of duplicating all Phase 1 features into the sync function (maintenance nightmare),
make the sequential mode also use the async code path with `concurrent=1`. This:
- Eliminates 770+ lines of duplicate sync code
- Ensures all future improvements apply to both modes
- Uses `asyncio.run()` which already works in the concurrent path

### FIX-1: Make sequential mode use async path [ISSUE-1, ISSUE-2]

**File:** `scripts/5-extract-citations/extract_citations.py`

Replace the sequential code block (lines 3425-3432):
```python
else:
    # Sequential mode (original code path)
    for i, doc in enumerate(
        tqdm(documents, total=total_to_process, desc="Processing Documents")
    ):
        process_single_document_phased(doc, session, stats)
```

With:
```python
else:
    # Sequential mode via async (ensures Phase 0, hard filters, Phase 5 are active)
    sequential_engine = get_engine(pool_size=5, max_overflow=5)
    Base.metadata.create_all(sequential_engine)
    SequentialSessionFactory = sessionmaker(bind=sequential_engine)

    async def run_sequential():
        lock = asyncio.Lock()
        sem = asyncio.Semaphore(1)
        pbar = tqdm(total=len(documents), desc="Processing Documents")
        for doc in documents:
            if _shutdown_requested:
                pbar.update(1)
                continue
            await process_single_document_phased_async(
                doc, SequentialSessionFactory, stats, lock, sem
            )
            pbar.update(1)
        pbar.close()

    try:
        asyncio.run(run_sequential())
    finally:
        sequential_engine.dispose()
```

This makes the async function the single code path for all modes.

### FIX-2: Pass `document_year` to extraction prompt [ISSUE-3]

**File:** `scripts/5-extract-citations/extract_citations.py`

In the async extraction function `extract_all_case_references_phase2_async` (line 2405),
the `generate_v6_extraction_prompt()` call needs to accept `document_year`. However, this
function doesn't have access to `document_year` — it's computed later in the processing flow.

**Better approach:** Compute `document_year` BEFORE Phase 2A in the async function,
then pass it through. This requires:

1. Move the `document_year` extraction (lines 2827-2840) to BEFORE Phase 2A (line 2793)
2. Pass `document_year` to `extract_all_case_references_phase2_async()` as a new parameter
3. Inside that function, pass it to `generate_v6_extraction_prompt()`

### FIX-3: Backfill quality flags for existing documents [ISSUE-4]

**File:** One-time SQL or Python script

```sql
-- Backfill text_char_count and text_token_estimate from extracted_text
UPDATE documents d
SET text_char_count = LENGTH(et.raw_text),
    text_token_estimate = LENGTH(et.raw_text) / 4,
    is_garbled = FALSE,
    is_too_long = CASE WHEN LENGTH(et.raw_text) > 3600000 THEN TRUE ELSE FALSE END
FROM extracted_text et
WHERE d.document_id = et.document_id
  AND d.text_char_count IS NULL
  AND et.raw_text IS NOT NULL;
```

This won't detect garbled text (needs Python `is_garbled_text()` function), but sets
the basic flags. A Python backfill could compute the precise garbled check.

### FIX-4: Update version labels [ISSUE-5]

**File:** `scripts/5-extract-citations/extract_citations.py`

- Line ~1: Change "v6.0 - KB-ENHANCED PIPELINE" → "v7.0 - ANTI-HALLUCINATION PIPELINE"
- Line 3436: Change "v5.3" → "v7.0"

### FIX-5: Optional — deprecate sync functions [ISSUE-1 cleanup]

After FIX-1 is verified working, the entire sync `process_single_document_phased()` function
(lines 1966-2731, ~770 lines) and its sync helper functions can be removed or marked deprecated.
The sync `call_gemini()` extraction calls (lines 1175-1260, 1475-1570, etc.) can also be removed.

This reduces the file from ~3500 lines to ~2700 lines with no functionality loss.

### Execution Order & Results

1. ✅ FIX-1 (critical — unify code paths) — DONE
2. ✅ FIX-2 (pass document_year to prompt) — DONE
3. ✅ FIX-4 (version labels — trivial) — DONE
4. ✅ Re-test with the same 5 documents — PASSED
5. ✅ FIX-3 (backfill — 5,513 documents updated) — DONE
6. FIX-5 (cleanup — optional, deferred)

### Additional Issues Found During Fix Implementation

**ISSUE-8 [CRITICAL]** — `thinking_config` field name wrong in gemini_client.py.
The code used `config_kwargs["thinking"]` but the google-genai SDK v1.65 field is
`thinking_config`. Pydantic rejected it with "Extra inputs are not permitted".
**Fixed:** Changed to `config_kwargs["thinking_config"]` in both sync and async paths.

**ISSUE-9 [HIGH]** — Rate limit detection false positive on "GenerateContentConfig".
The check `"rate" in error_str` matched the substring "rate" in "GenerateContentConfig",
causing all Pydantic validation errors to be misclassified as rate limits and retried 5 times.
**Fixed:** Changed to `"rate limit" in error_str`.

**ISSUE-10 [HIGH]** — `call_gemini_async` returns None on exhausted rate limit retries.
When all 5 retries failed, the function fell through the loop and returned None implicitly.
The caller then crashed with `TypeError: 'NoneType' object is not subscriptable`.
**Fixed:** Added `raise RuntimeError(...)` on last retry attempt. Also added null guard in caller.
