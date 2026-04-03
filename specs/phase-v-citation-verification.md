# Phase V — Citation Verification Pipeline

> **Status:** DRAFT — under discussion (Gustavo + Lucas call, 8 Mar 2026)
> **Open issues:** 4 questions pending answers (see §6)

---

## 1. Context & Problem Statement

Lucas reported two issues with the exported citation data:

1. **Missing/bad snippets**: 36.3% of 11,932 citations have no `snippet_text`, and many existing snippets don't actually contain the claimed citation (LLM paraphrased `raw_text` instead of copying verbatim, so text matching fails)
2. **Wrong URL in export**: `export_to_excel.py` uses `document_content_url` (always NULL) instead of `document_url` (16,332 populated with direct PDF links)

**Root cause (snippets):** The extraction prompt asks for verbatim text, but the LLM often returns normalized forms like `"Case Name (Year) | Jurisdiction"`. The snippet extractor then can't find this in the document. Additionally, some citations may be hallucinated entirely.

**Proposed solution:** An LLM-based verification pass that reads each document and confirms whether each claimed citation actually exists, returning truly verbatim quotes that can be char-anchored.

---

## 2. Data Picture (as of 8 Mar 2026)

| Metric                                          | Count         |
| ----------------------------------------------- | ------------- |
| Total documents in DB                           | 16,352        |
| Documents classified as decisions               | 4,755         |
| Decisions processed through extraction          | 4,725         |
| Decisions with kept citations                   | 2,680         |
| Decisions with zero kept citations              | 2,045         |
| **Unprocessed decisions**                       | **31**        |
| Total citations in `citation_extraction_phased` | 11,932        |
| Citations WITH snippet_text                     | 7,600 (63.7%) |
| Citations WITHOUT snippet_text                  | 4,332 (36.3%) |
| **Citations discarded by Sabin filter**         | **75,704**    |
| Documents with discarded citations              | 3,175         |
| Discard reason: `below_threshold`               | 75,697        |
| Discard reason: `empty_after_normalization`     | 7             |
| Orphaned summaries (data integrity gap)         | 0             |

**Key finding:** The Sabin filter discarded 6.3× more citations than it kept. These sit in `citation_extraction_discarded`. Some may be real citations to cases not in the 4,741-case Sabin knowledge base.

comment from us — we will abide by the sabin filter step for now, as we really don't need data concerning decisions not referenced in the Sabin seed. If we have relevant findings spawning from this verification steps that point to an issue in the sabin filter, we'll assess whether or not to apply logic from this verification step into previous steps in the pipeline to execute a fresh re-run of citations extraction.

---

## 3. Plan (Original Draft)

### Step 1: DB Migration

**File**: `scripts/6-verify-citations/migrate_verification_columns.sql`

Add 5 columns + 1 index to `citation_extraction_phased`:

```sql
ALTER TABLE citation_extraction_phased
    ADD COLUMN IF NOT EXISTS verification_status VARCHAR(20),
    ADD COLUMN IF NOT EXISTS verification_snippet TEXT,
    ADD COLUMN IF NOT EXISTS verification_notes TEXT,
    ADD COLUMN IF NOT EXISTS verification_model VARCHAR(50),
    ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP;
CREATE INDEX IF NOT EXISTS idx_cep_verification_status
    ON citation_extraction_phased(verification_status);
```

Also update `CitationExtractionPhased` model in `scripts/0-initialize-database/init_database.py` (after the `reviewed_at` column, ~line 404).

### Step 2: Extend `gemini_client.py` — add `response_json_schema` support

Currently `call_gemini_async()` only supports `response_mime_type`. Add a `response_schema` parameter that accepts a Pydantic BaseModel class:

```python
async def call_gemini_async(
    prompt: str,
    *,
    model: str = None,
    response_mime_type: str = None,
    response_schema = None,        # NEW: Pydantic BaseModel class
    ...
) -> dict:
    # In config_kwargs building:
    if response_schema:
        config_kwargs["response_mime_type"] = "application/json"
        config_kwargs["response_schema"] = response_schema
```

Same change to sync `call_gemini()` for consistency.

comment from us — have you built this codeblock assuring that the mime_type response is a valid option? In which scenarios are mime_type responses useful for our scope or better then json responses? Can't we unify the response method into json? If we cannot, state the logic that implies one or the other kind of response.

### Step 3: Create `scripts/6-verify-citations/verify_citations.py`

#### 3a. Pydantic schemas (structured output)

```python
class SingleCitationVerification(BaseModel):
    citation_index: int
    verdict: Literal["CONFIRMED", "NOT_FOUND", "MISATTRIBUTED"]
    verbatim_quote: str | None = None
    corrected_case_name: str | None = None
    notes: str | None = None

class DocumentVerificationResponse(BaseModel):
    verifications: list[SingleCitationVerification]
```

#### 3b. Verification prompt

System instruction + user content. The prompt:

1. Receives full document text
2. Receives numbered list of claimed citations (`case_name` + `raw_citation_text`)
3. For each: verdict + verbatim copy-paste quote (1-3 sentences) + corrections
4. Enforced via `response_json_schema=DocumentVerificationResponse`

Key instruction: **verbatim_quote MUST be an exact substring of the source document** — copy-paste only, no paraphrasing.

comment from us — check discussion below on the raw_citation_text issue and other topics of prompting. 

#### 3c. Async processing (mirrors `extract_citations.py`)

```
main()
├── Run migration (ALTER TABLE IF NOT EXISTS)
├── Query document_ids with unverified citations
├── Create concurrent engine (pool_size=concurrent+5)
├── run_concurrent()
│   ├── sem = asyncio.Semaphore(concurrent)
│   ├── lock = asyncio.Lock()
│   └── asyncio.gather(*[process_one(doc) for doc in docs])
│       └── verify_single_document(doc_id, session_factory, stats, lock, sem)
│           ├── Load document text from extracted_text
│           ├── Load citations from citation_extraction_phased
│           ├── Batch citations (max 50 per LLM call)
│           ├── For each batch:
│           │   ├── build_verification_prompt()
│           │   ├── call_gemini_async(schema=DocumentVerificationResponse)
│           │   └── Parse structured response
│           ├── For each CONFIRMED citation with verbatim_quote:
│           │   ├── extract_snippet(document_text, verbatim_quote)
│           │   └── Update snippet_text + char anchors if found
│           ├── UPDATE all citation rows (verification_* columns)
│           └── Update stats under lock
└── Print final report (confirmed/not_found/misattributed, snippets improved, cost)
```

#### 3d. CLI

```bash
python verify_citations.py                     # verify all unverified
python verify_citations.py --concurrent 40     # VM full capacity
python verify_citations.py --model gemini-3.1-pro-preview
python verify_citations.py --limit 50          # test batch
python verify_citations.py --re-verify         # re-process already verified
python verify_citations.py --dry-run           # show counts + cost estimate
python verify_citations.py --budget 25         # halt if cost exceeds $25
```

#### 3e. Key design decisions

| #   | Decision                | Choice                                                                      | Rationale                                                    |
| --- | ----------------------- | --------------------------------------------------------------------------- | ------------------------------------------------------------ |
| D1  | Batch size              | 50 citations/LLM call                                                       | Keeps output manageable; only 5% of docs have >13 citations  |
| D2  | Concurrency default     | 25 (local), recommend 40 (VM)                                               | VM has 16 cores; Gemini rate limits ~1500 RPM for Flash-Lite |
| D3  | Snippet update strategy | Only update `snippet_text` if `extract_snippet()` confirms char-level match | `verification_snippet` preserves raw LLM output regardless   |
| D4  | NOT_FOUND handling      | Set `requires_manual_review=True`                                           | Lucas can review likely hallucinations                       |
| D5  | Doc with 875 citations  | Batch into 18 calls of 50                                                   | Sequential within that doc, parallel across docs             |
| D6  | Cost tracking           | Per-call accumulation, print every 100 docs, halt at `--budget`             | Budget safety                                                |
| D7  | Graceful shutdown       | `_shutdown_requested` flag on SIGINT                                        | Same pattern as extract_citations.py                         |

### Step 4: Fix export URL

**File**: `scripts/export_to_excel.py`

Change `d.document_content_url` → `d.document_url` in three places:

- Line 77 (`_export_data_quality_sheet` download failures query)
- Line 191 (enriched query for `citation_extraction_phased`)
- Line 203 (enriched query for `citation_extraction_phased_summary`)

Also rename the alias from `source_pdf_url` to `source_document_url` for clarity.

### Step 5: Add verification columns to export

The new `verification_status` and `verification_snippet` columns will be automatically included since the enriched query uses `cep.*`.

### Files to Create/Modify

| File                                                          | Action                                                          |
| ------------------------------------------------------------- | --------------------------------------------------------------- |
| `scripts/6-verify-citations/verify_citations.py`              | **CREATE** — main verification script (~450 lines)              |
| `scripts/6-verify-citations/migrate_verification_columns.sql` | **CREATE** — SQL migration                                      |
| `scripts/gemini_client.py`                                    | **MODIFY** — add `response_schema` param to both call functions |
| `scripts/0-initialize-database/init_database.py`              | **MODIFY** — add 5 columns to model                             |
| `scripts/export_to_excel.py`                                  | **MODIFY** — fix URL column (3 lines)                           |

### Existing Code to Reuse

| What                                                     | Where                                              |
| -------------------------------------------------------- | -------------------------------------------------- |
| `call_gemini_async()`                                    | `scripts/gemini_client.py`                         |
| `extract_snippet()`                                      | `scripts/snippet_extractor.py`                     |
| `get_engine()`, SQLAlchemy models                        | `scripts/0-initialize-database/init_database.py`   |
| `CONFIG`, model IDs                                      | `scripts/config.py`                                |
| Async pattern (semaphore, stats lock, graceful shutdown) | `scripts/5-extract-citations/extract_citations.py` |
| `get_database_url_auto()`                                | `scripts/gcp_secrets.py`                           |

### Verification Steps

1. **Local dry-run**: `python verify_citations.py --dry-run` — confirms query, counts, cost estimate
2. **Local small test**: `python verify_citations.py --limit 5 --concurrent 1` — inspect results in DB
3. **VM medium test**: `python verify_citations.py --limit 50 --concurrent 10` — validate concurrency
4. **VM full run**: `python verify_citations.py --concurrent 40 --budget 25`
5. **Post-run validation**:
   
   ```sql
   SELECT verification_status, COUNT(*) FROM citation_extraction_phased GROUP BY 1;
   SELECT COUNT(*) FILTER (WHERE snippet_text IS NOT NULL) as improved_snippets
     FROM citation_extraction_phased WHERE verification_status = 'CONFIRMED';
   ```
6. **Export**: `python export_to_excel.py` — verify `document_url` column is populated

---

## 4. Issues Identified During Review

### Issue A: Truncation of `raw_citation_text`

**Problem:** The original plan proposed truncating `raw_citation_text` to ~500 chars to save tokens. If the distinguishing detail (specific holding, year, jurisdiction) falls after the truncation point, the verification LLM won't have enough to identify the correct citation — leading to false NOT_FOUND verdicts.

**Assessment:** Premature optimization. At Flash-Lite prices, the token savings are negligible compared to the risk of wrong verdicts.

**Options:**

- A) Send full `raw_citation_text` (modest cost increase — most are short, only outliers are long)
- B) Don't send `raw_citation_text` at all (see Issue B)
  
  
  
  comment from us — we opt for B.

### Issue B: Circular reliance on `raw_citation_text`</mark>

<mark></mark>**Problem:** The whole pipeline exists because the extraction LLM produced unreliable output. Using that same unreliable output as the search query for verification is circular. If `raw_citation_text` says *"The Hague Court held in Urgenda (2015) that climate obligations..."* but the actual document says *"In the Urgenda Foundation v. State of the Netherlands, the District Court of The Hague ruled..."* — the verification LLM might struggle to match these, or worse, return NOT_FOUND for a citation that genuinely exists.

**Proposed revision:** Use `case_name` as the **primary identifier** sent to the LLM. The prompt becomes: *"For each case name below, find where this case is cited in the document. Return the exact verbatim passage, or confirm it's not present."*

`raw_citation_text` could still be included as **optional hint/context**, but the identification should not depend on it.

**Trade-off:** `case_name` alone may be ambiguous if a document cites the same case multiple times in different contexts. The prompt would need to handle this (e.g., "return ALL passages where this case is cited").

comment from us — 

### Issue C: Scope — documents with discarded citations only

**Problem:** The plan queries `document_ids with unverified citations` — only documents that already have rows in `citation_extraction_phased`. This misses:

- **3,175 documents** where the LLM extracted citations but the Sabin filter rejected ALL of them. These documents appear to have zero citations. Some discarded citations may be legitimate references to cases not in the 4,741-case Sabin KB.
- **31 unprocessed decisions** that were never run through extraction at all.

The **75,704 discarded citations** (6.3× the kept count) sitting in `citation_extraction_discarded` are the elephant in the room. Nearly all were discarded for `below_threshold` — they didn't match any known case with sufficient confidence. But "not in our knowledge base" ≠ "not a real citation."

**Options:**

- A) **Phase V = verify kept citations only** (11,932). Audit discards as a separate Phase VI.
- B) **Phase V also samples discards** — e.g., verify 500 random discarded citations to estimate false-discard rate. If high, expand.
- C) **Phase V includes all documents with ANY extraction output** (kept or discarded). Much larger scope.

comment from us — check comment above on the sabin filter - we'll follow option A.

### Issue D: Snippet char-matching strategy (Design Decision D3)

**Problem:** The plan says: store the LLM's output in `verification_snippet` always, but only overwrite `snippet_text` (the canonical field) if `extract_snippet()` confirms an exact char-level match. But common mismatches (whitespace normalization, Unicode variants like `"` vs `"`, ligatures, line breaks) would cause false negatives — the snippet is correct but technically not an exact substring.

**Options:**

- A) **Strict exact match** — current plan. Safe but leaves some good snippets un-promoted.
- B) **Fuzzy match with high threshold** (e.g., 95% character similarity) — promotes more, small risk of near-miss snippets.
- C) **Normalize both texts before matching** (collapse whitespace, normalize quotes/dashes/Unicode, then match) — addresses the most common mismatch causes without accepting truly different text.

**Assessment:** Option C seems most principled. The mismatches are almost always encoding/formatting artifacts, not semantic differences.

comment from us — we'll implement option B

---

## 5. Revised Data-Driven Summary

| Original Assumption                             | Reality                                            | Impact on Plan                                |
| ----------------------------------------------- | -------------------------------------------------- | --------------------------------------------- |
| `raw_citation_text` is the claim to verify      | It's often paraphrased/wrong itself                | Use `case_name` as primary identifier instead |
| Truncating raw_citation_text saves cost         | Negligible savings, risks wrong verdicts           | Send full text or drop entirely               |
| Only docs with kept citations need verification | 75K discarded citations may include real ones      | Scope decision needed (§6 Q1)                 |
| Exact char match for snippet promotion          | Unicode/whitespace artifacts cause false negatives | — Fuzzy Match                                 |

## 6. Open Questions (for Gustavo & Lucas)

### Q1 — Verification scope

Should Phase V be limited to the **11,932 existing kept citations** (confirm/deny what we have), or also audit a sample of the **75,704 discarded citations**?

Auditing discards is essentially asking "did the Sabin filter reject real citations?" — a different research question, possibly a separate Phase VI.

**Options:**

- A) Phase V = kept citations only. Discards = separate future phase.
- B) Phase V + a sample of ~500 discards to estimate false-discard rate.
- C) Phase V covers all documents with any extraction output (kept or discarded).

> **Lucas's answer:**
> 
> _______________________________________________________________________
> 
> _______________________________________________________________________
> 
> **Gustavo's answer:**
> 
> _______________________________________________________________________
> 
> _______________________________________________________________________
> 
> **Decision:** See above the option to accpept sabin filter : option A
> 
> _______________________________________________________________________

---

### Q2 — Identification strategy for the prompt

Use `case_name` only (not `raw_citation_text`) as the identifier sent to the verification LLM?

The prompt would become: *"For each case name below, find where this case is cited in the document."* This avoids circular reliance on the extraction LLM's bad output.

`raw_citation_text` could still be included as optional context/hint.

**Options:**

- A) `case_name` only — clean, avoids circular reliance.
- B) `case_name` + full `raw_citation_text` as hint — gives the LLM more to work with.
- C) `case_name` + first N chars of `raw_citation_text` — compromise.

> **Lucas's answer:**
> 
> _______________________________________________________________________
> 
> _______________________________________________________________________
> 
> **Gustavo's answer:**
> 
> _______________________________________________________________________
> 
> _______________________________________________________________________
> 
> **Decision: ** = A
> 
> _______________________________________________________________________

---

### Q3 — Snippet normalization strategy

When promoting the verification LLM's `verbatim_quote` to the canonical `snippet_text` field, how strict should the char-level matching be?

**Options:**

- A) Strict exact substring match (current plan).
- B) Fuzzy match ≥95% character similarity.
- C) Normalize both texts first (collapse whitespace, normalize Unicode quotes/dashes), then exact match.

> **Lucas's answer:**
> 
> _______________________________________________________________________
> 
> _______________________________________________________________________
> 
> **Gustavo's answer:**
> 
> _______________________________________________________________________
> 
> _______________________________________________________________________
> 
> **Decision: ** — option B
> 
> _______________________________________________________________________

---

### Q4 — The 31 unprocessed decisions

There are 31 decisions that were never run through the extraction pipeline. Should we:

- A) Run extraction on them before Phase V (they'd then enter the verification scope automatically).
- B) Ignore them for now — investigate why they were skipped.
- C) Note them as a known gap, address later.

> **Lucas's answer:**
> 
> _______________________________________________________________________
> 
> _______________________________________________________________________
> 
> **Gustavo's answer:**
> 
> _______________________________________________________________________
> 
> _______________________________________________________________________
> 
> **Decision:** — ignore them, but register a note on them
> 
> _______________________________________________________________________

---

## 7. Revision Log

| Date       | Author             | Change                                                                                       |
| ---------- | ------------------ | -------------------------------------------------------------------------------------------- |
| 8 Mar 2026 | Claude (plan mode) | Original plan drafted                                                                        |
| 8 Mar 2026 | Claude + Gustavo   | Issues A-D identified, 4 open questions raised, data investigation (75K discards discovered) |
|            |                    |                                                                                              |
