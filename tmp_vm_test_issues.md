# VM 500-Document Test Issues Log
# Created: 2026-03-09
# VM: phdmutley-pipeline (e2-standard-16, 16 vCPU, 64 GB)
# Purpose: Track issues from 500-decision extraction test on VM

## Test Configuration
- 500 decisions, --concurrent 10 (leveraging 16 vCPU)
- Models: gemini-2.5-flash (extraction, thinking=1024), gemini-2.5-pro (classification, thinking=2048)
- Pipeline: v7.0 anti-hallucination (Phase 0 + hard filters + Phase 5 inline verification)

## Issues Found

### VMISSUE-1 [LOW] — 1 citation with NULL verification_status

**Doc:** 050c5c44-fc99-56eb-a250-395c64553226 (4,684 chars, small doc)
**Citation:** NECEC Transmission LLC, et al. v. Bureau of Parks
**Cause:** Phase 5 verification LLM response likely omitted this citation.
The verification function returns updates keyed by extraction_id; if the LLM
doesn't include a citation in its response, no update is applied.
**Impact:** 1/181 citations (0.5%) — non-critical
**Fix:** Add fallback in Phase 5 — any citation not updated by verification
should default to a status like `UNVERIFIED` instead of NULL.
**Update (72% mark):** Now 6 citations with NULL verification across multiple docs.
Still <1% of total (6/857), but confirms the pattern is systemic, not one-off.
**Final (500/500):** 32 citations with NULL verification out of 1,245 total (2.6%).
Jumped from 14→32 in the last 2 docs (18 NULLs from 2 documents with many citations).
**Severity upgraded to MEDIUM** — 2.6% is non-trivial for full dataset.
The fix remains the same: default unverified citations to `UNVERIFIED` status.

### VMISSUE-2 [LOW] — 3 documents with "Phase 2A extraction failed - no result returned"

**Docs:**
- a1598776-41b4-565b-bb69-aeff5f945fd3 (34.7s processing time)
- 9b6fd417-9635-5096-867b-c7b7da1d0cce (42.1s processing time)
- d97ba56d-3fc4-5f96-823a-b1203e8533d3 (27.8s processing time)
**Cause:** Gemini API returned no usable response after retries. Likely the document
content triggered a safety filter or the response was malformed JSON that couldn't
be parsed. The long processing times (27-42s) suggest multiple retry attempts.
**Impact:** 3/500 documents (0.6%) — non-critical, these docs can be retried later.
**Fix:** Investigate document text length/content. Consider adding a re-queue mechanism
for transient API failures.

### VMISSUE-3 [MEDIUM] — Phase 5 verification fails entirely on rate limit, leaving all doc citations NULL

**Cause:** With `--concurrent 10`, multiple Phase 5 verification calls compete for
the Gemini Flash quota (1M input tokens/min). When exhausted, `verify_document_citations_inline()`
raises a RuntimeError after 5 retries. The `except` block in `extract_citations.py` catches
it as non-fatal but doesn't set any verification status on the citations → they stay NULL.
**Distinct from VMISSUE-1:** VMISSUE-1 covers individual citations omitted from a successful
LLM response. VMISSUE-3 covers entire Phase 5 failure (no LLM response at all).
**Impact:** 25 NULL citations at 191/4724 (4.3% of citations). Will scale with run length.
**Fix applied:** Added UNVERIFIED fallback in the `except` block of Phase 5 in `extract_citations.py`.
For the current run, NULLs will be fixed post-hoc with SQL UPDATE.
**Deployed:** Fix uploaded to VM but NOT applied to running process (not killed — non-critical).
Will take effect on next re-launch.

### VMISSUE-4 [MEDIUM] — Rate limit storm causing elevated Phase 2A failures

**Observed at:** 704/4724 (15%) — burst of concurrent large documents exceeded
Gemini Flash 1M input tokens/min quota. Phase 2A failures spiked to 37% (26/70 docs)
in a 5-min window. Error log lines jumped from 33 to 144 (+111).
**Cause:** `--concurrent 10` with many large docs (>50K chars) hitting simultaneously.
The retry logic (5 attempts, exponential backoff) isn't enough when the suggested
retry delay is 16-31s and multiple workers are competing.
**Impact:** Failed docs get 0 citations — they can be retried later with lower concurrency.
No data corruption; successful extractions are unaffected.
**Monitoring:** If failure rate sustains >20% over multiple checks, reduce to `--concurrent 5`.
**Long-term fix:** Add adaptive concurrency — reduce semaphore when rate limits are hit,
increase when they stop. Or add jitter/longer backoff in retry logic.
**Action taken (at 784/4724):** Process killed. 110 Phase 2A failures deleted from DB.
Re-launched with `--concurrent 5`. VMISSUE-3 fix now active in new process.
Log file: `/tmp/extraction_v7_full_r2.log`
**Still failing with --concurrent 5:** 0 new successes, 65 more Phase 2A failures in 7 min.
Root cause: retry backoff too short (2s base) — API suggests 16-31s retry delay but
code uses 2*2^attempt. Retry storm amplifies rate limit hits across concurrent workers.
**Fix:** Updated `gemini_client.py` retry logic — parse API's suggested delay, use 15s
base backoff for rate limits (was 2s). Capped at 120s max.
**Action (at 740/4724):** Killed r2, cleaned up 65 failures, waiting 60s quota cooldown,
re-launching with `--concurrent 3`. Log: `/tmp/extraction_v7_full_r3.log`
**--concurrent 3 also failed.** Switched to gemini-2.5-pro but Pro hit daily
request limit (1,000 RPD). Flash also daily-capped. Both models unavailable.
**Quota details:**
- Flash: `GenerateContentPaidTierInputTokensPerModelPerMinute` (1M) — also daily capped
- Pro: `GenerateRequestsPerDayPerProjectPerModel` (1,000 RPD) — retry in 18h28m
**Config reverted to Flash.** Pipeline paused until daily reset (~midnight UTC).
**Progress preserved:** 645 success, 42 garbled, 4,037 remaining.
**Root cause:** `--concurrent 10` retry storm consumed thousands of API requests
in minutes, burning through daily quotas for both models.

---

## 500-Doc Test Results Summary

| Metric | Value |
|--------|-------|
| **Total processed** | 500/500 |
| **Success** | 478 (95.6%) |
| **Failed - Garbled** | 19 (3.8%) — correctly skipped by Phase 0 |
| **Failed - API** | 3 (0.6%) — Phase 2A no result |
| **Citations extracted** | 1,245 |
| **CONFIRMED** | 1,190 (95.6%) |
| **NOT_FOUND** | 13 (1.0%) |
| **MISATTRIBUTED** | 10 (0.8%) |
| **NULL (unverified)** | 32 (2.6%) |
| **Extraction cost** | $3.37 |
| **Verification cost** | $0.91 |
| **Total cost** | $4.28 ($0.009/doc) |

### Verdict
Pipeline v7.0 is **production-ready** with two minor fixes needed before full run:
1. **VMISSUE-1 [MEDIUM]:** Default NULL verification to UNVERIFIED (2.6% affected)
2. **VMISSUE-2 [LOW]:** Log/retry mechanism for Phase 2A API failures (0.6% affected)

