# Pipeline Data Flow Report — PhD Climate Litigation Citation Analysis

Complete data lineage from PDF download to citation classification. Each step describes what data enters, what transformations occur, and what comes out.

---

## Pipeline Overview

```
Excel (Sabin DB)  ──>  Script 0: Schema  ──>  Script 1: Download PDFs
                            |                       |
                            v                       v
                       Script 2: Metadata  ──>  Script 3: Extract Text
                                                    |
                                                    v
                                            Script 4: Classify Decisions
                                                    |
                                                    v
                                          Script 5: Extract Citations (v6)
                                                    |
                                            ========|========
                                            | Phase 1: Source ID       |
                                            | Phase 2A: LLM Extraction |
                                            | Sabin Filter             |
                                            | Snippet Extraction       |
                                            | Phase 2B: Functional     |
                                            | Phase 3: Origin ID       |
                                            | Phase 4: Classification  |
                                            ===========================
                                                    |
                                                    v
                                            6 database tables populated
```

---

## Step 0 — Database Initialization (`init_database.py`)

- **Input**: None (schema-only)
- **Process**: Creates PostgreSQL schema on port 5433 via SQLAlchemy ORM
- **Output**: 6 tables with CASCADE foreign keys and 12 indexes

| Table | Purpose | PK |
|-------|---------|------|
| `cases` | Case metadata (2,924 records) | `case_id` (String) |
| `documents` | Individual documents per case | `document_id` (UUID v4) |
| `extracted_text` | PDF text extraction results | `text_id` (UUID v4) |
| `citation_extraction_phased` | Individual kept citations | `extraction_id` (UUID v4) |
| `citation_extraction_phased_summary` | Document-level extraction stats | `summary_id` (UUID v4) |
| `citation_extraction_discarded` | Citations filtered out by Sabin | `id` (auto-increment) |

---

## Step 1 — PDF Download (`download_decisions.py`)

- **Input**: Excel column `Document Content URL` (direct PDF links)
- **Filter**: Trial batch mode (if enabled) limits to marked rows; `--test-run N` samples N docs
- **Process**: Async HTTP GET with 10 concurrent downloads, 30s timeout per file
- **Output**: `pdfs/downloaded/doc_{document_id}.pdf` — one file per document
- **Data created**: Binary PDF files on disk. No database writes.
- **Cost**: $0

---

## Step 2 — Metadata Population (`populate_metadata.py`)

- **Input**: `data/seed/SABIN_DB-2026-02-23.xlsx` (16,380 rows, ~2,924 unique cases)
- **Filter**: Trial batch + test-run sampling (expands to all docs in sampled cases)
- **Process**:

| Transformation | Input Column | Output Field | Logic |
|----------------|-------------|--------------|-------|
| UUID generation | Case ID / Document ID | `case_id` / `document_id` | Deterministic `uuid5(NAMESPACE, f"case_{id}")` |
| Jurisdiction parse | `Jurisdictions` (e.g., "United States; U.S. Court of Appeals") | `cases.jurisdiction` | Split by `;`, extract court name from second part |
| Region classification | `Geography ISOs` (e.g., "USA;CA") | `cases.region` | Lookup in hard-coded Global North set (16+ countries) |
| Date parsing | `First event in timeline` | `cases.case_filing_year` | Multi-format parser (ISO, US, Excel serial) |
| Metadata JSON | Multiple columns | `metadata_data` (JSONB) | Aggregate: summary, categories, laws, timeline |
| Upsert | All above | `cases` + `documents` | Insert or update by UUID |

- **Output**: `cases` table (2,924 rows), `documents` table (~4,500 rows)
- **Cost**: $0

---

## Step 3 — PDF Text Extraction (`extract_texts.py`)

- **Input**: PDF files from `pdfs/downloaded/` + `documents` table (for UUID mapping)
- **Filter**: Skip documents with existing `extracted_text` records
- **Process**: Hierarchical extraction with memory safety (8GB RAM limit)

| Tier | Library | Success Rate | Fallback Trigger |
|------|---------|-------------|------------------|
| 1 | pdfplumber | ~94% | MemoryError or extraction failure |
| 2 | PyMuPDF (fitz) | ~5% | MemoryError or extraction failure |
| 3 | PyPDF2 | ~1% | Extraction failure |
| 4 | Failed | - | All above fail |

- **Quality assessment**: word count, chars/page ratio, scanned detection (<100 words = likely scanned)
- **Optional**: Markdown formatting via `pymupdf4llm.to_markdown()` (non-blocking)
- **Data created**:

| Field | Content |
|-------|---------|
| `raw_text` | Full unprocessed text from PDF |
| `processed_text` | Same as raw_text (no cleaning) |
| `text_md` | Markdown-formatted text (if enabled) |
| `extraction_method` | "pdfplumber", "pymupdf", "pypdf2", or "failed" |
| `extraction_quality` | "excellent", "good", "fair", "poor", "failed" |
| `word_count` / `character_count` | Text statistics |

- **Output**: `extracted_text` table (~2,847 rows), `documents` table updated (page_count, file path)
- **Cost**: $0

---

## Step 4 — Decision Classification (`classify_decisions.py`)

- **Input**: `documents` + `extracted_text` (raw_text) + Excel (Document Title)
- **Filter**: Skip already-classified documents (`is_decision IS NOT NULL`)
- **Process**: Two-tier classification

| Tier | Method | Trigger | Confidence | Cost |
|------|--------|---------|------------|------|
| 1 | Document Title heuristic | Title ends in "judgment"/"decision"/"judgement" | 1.0 | $0 |
| 2 | Gemini LLM | Title doesn't match Tier 1 | 0.0-1.0 | ~$0.001/doc |

- **LLM interaction (Tier 2 only)**:
  - **Sent to LLM**: First 3,000 chars of document text + classification prompt
  - **Expected back**: `{"is_judicial_decision": bool, "confidence_score": float}`
  - **Model**: Gemini 3.1 Pro, temperature=0.0
- **Data modified**: `documents.is_decision`, `decision_classification_method`, `decision_classification_confidence`
- **Output**: ~2,700 decisions identified, ~220 non-decisions filtered out
- **Cost**: ~$3 total

---

## Step 5 — Citation Extraction (`extract_citations.py`, v6)

This is the core pipeline. It processes each decision through 4 phases plus 3 intermediate steps.

### 5.0 — Initialization (in `main()`)

- **Loads**: Knowledge base (4,741 Sabin climate cases from JSON)
- **Initializes**: `SabinFilter` (builds normalized name index for matching)
- **Sets**: `_extraction_run_id` (timestamp for batch grouping)
- **Migrates**: Adds v6 columns to `citation_extraction_phased` if missing; creates `citation_extraction_discarded` if missing
- **Queries documents**:
  ```
  Documents WHERE is_decision=True AND raw_text IS NOT NULL
  MINUS documents already in citation_extraction_phased_summary
  ```

### 5.1 — Phase 1: Source Jurisdiction Identification

- **Input**: `Case.geographies` string (e.g., "United States;California;Washington, D.C.")
- **Algorithm**:
  1. Split by `;`, take first element (country level)
  2. Normalize via `JURISDICTION_ALIASES` (e.g., "USA" -> "United States")
  3. Classify region: lookup in `GLOBAL_NORTH_COUNTRIES` set (24 countries + EU)
- **Output**: `source_jurisdiction` (string), `source_region` ("Global North" | "Global South" | "International")
- **Cost**: $0 (pure lookup)

### 5.2 — Phase 2A: Extract ALL Case Law References

- **Input**: Full document text + source jurisdiction/region + knowledge base (4,741 cases)
- **Chunking decision**: If document > 40,000 tokens (~160K chars), split into overlapping chunks of ~30,000 tokens with 2,000-token overlap at paragraph boundaries. Otherwise single call.

#### What is sent to the LLM

The v6 prompt (~150K-180K tokens) contains:
1. Source court context (jurisdiction + region)
2. Compact knowledge base: one line per case — `"Case Name (Year) | Jurisdiction"` (~150K tokens for 4,741 cases)
3. 10 extraction pattern categories (traditional, narrative, shorthand, scholarly, procedural, comparative, signal, footnote, dissenting, advisory)
4. Output JSON schema
5. Full document text (or chunk)

Critical instruction: "Extract EVERY case reference. Do NOT filter. Do NOT classify. Be EXHAUSTIVE."

#### What comes back from the LLM

```json
{
  "case_law_references": [
    {
      "case_name": "Urgenda Foundation v. State of the Netherlands",
      "raw_text": "VERBATIM citation passage from document",
      "confidence": 0.95
    }
  ],
  "total_references_found": 12,
  "extraction_notes": "..."
}
```

- **Model**: Gemini 3.1 Flash-Lite, temperature=0.0, no output token limit
- **Retry**: On JSON parse failure, retry entire call (up to 3 attempts)
- **List guard**: If LLM wraps response in `[{...}]`, unwrap to `{...}`
- **Chunked docs**: Merge references from all chunks, deduplicate by normalized case_name (keep longer raw_text on collision)
- **Output**: List of reference dicts with case_name, raw_text, confidence
- **Cost**: ~$0.002/document

### 5.3 — Sabin Filter

- **Input**: All references extracted in Phase 2A
- **Algorithm**: Two-tier matching against 4,741 KB cases

| Tier | Method | Threshold | Confidence |
|------|--------|-----------|------------|
| 1 | Exact normalized name match | Exact | 1.0 |
| 2 | Fuzzy (Jaccard + containment) | 0.70 score | score (capped at 1.0) |

- **Normalization**: Unicode NFKD, lowercase, strip case numbers, reporter citations, bracketed years, noise words (the, of, and, in, v, vs)
- **Fuzzy similarity**: `0.5 * jaccard(token_sets) + 0.5 * max_containment_ratio` with +0.15 year-match bonus
- **Year mismatch penalty**: confidence * 0.8

#### Data split

| Destination | What | Fields saved |
|-------------|------|-------------|
| **Kept** (passed forward) | Citations matching a Sabin case | Original ref + `sabin_match` dict (sabin_case_id, tier, confidence, kb_case_name) |
| **Discarded** (saved to DB) | Citations NOT matching any Sabin case | case_name, raw_text, confidence, closest KB match name + score, discard_reason, run_id -> `citation_extraction_discarded` table |

- **Typical ratio**: ~10-15% kept, ~85-90% discarded (most citations in a decision are domestic non-climate cases)
- **Cost**: $0 (pure computation)

### 5.4 — Snippet Extraction

- **Input**: Full document text + kept citations (post-Sabin)
- **Algorithm**: Three-tier text location for each citation's `raw_text`

| Tier | Method | How |
|------|--------|-----|
| 1 | Exact substring | `document_text.find(raw_citation_text)` |
| 2 | Normalized | Collapse whitespace, case-insensitive find, map position back to original |
| 3 | Key phrase | Extract "X v. Y" pattern or first 50 chars, find in document, expand to sentence boundaries |

- **Context window**: 300 chars before + 300 chars after the match, snapped to word boundaries
- **Paragraph extraction**: Find surrounding `\n\n` boundaries, truncate at 2,000 chars

#### Data produced per citation

| Field | Content |
|-------|---------|
| `found` | True/False |
| `match_type` | "exact", "normalized", "key_phrase" |
| `start_char` / `end_char` | Character offsets in document |
| `snippet` | Context window text (~600 chars) |
| `paragraph` | Full containing paragraph (up to 2,000 chars) |

- **Current hit rate**: ~65% (35% miss rate, especially on chunked documents — tracked as task #74)
- **Cost**: $0 (pure string operations)

### 5.5 — Phase 2B: Functional Classification

- **Input**: Kept citations + their snippet context + full document text
- **Prerequisite**: Snippet text injected into each reference as `context_snippet` field before prompting

#### What is sent to the LLM

Prompt with (batched, up to 30 citations per call):
1. Source court context
2. Numbered list of citations (first 200 chars of raw_text + context_snippet each)
3. Classification categories:
   - **functional_use**: `"parties_argument"` | `"dismissed"` | `"contributed"`
   - **opinion_type**: `"majority"` | `"dissent"` | `"concurrence"` | `"unclear"`
4. Key signal words for each category
5. JSON output schema

#### What comes back from the LLM

```json
{
  "classifications": [
    {
      "citation_index": 1,
      "functional_use": "contributed",
      "opinion_type": "majority",
      "key_signals": ["following", "as held in"],
      "reasoning": "Court applies this precedent directly"
    }
  ]
}
```

- **Index mapping**: `citation_index` is 1-based within batch -> converted to global index: `batch_start + (citation_index - 1)`
- **Failure mode**: When snippet is missing, LLM asks "Please provide the Context" instead of classifying. Pipeline logs warning and continues — citation saved without functional classification.
- **Model**: Gemini 3.1 Flash-Lite, temperature=0.0
- **Cost**: ~$0.0005/batch

### 5.6 — Phase 3: Origin Identification

- **Input**: Each kept citation's case_name, raw_text, source_jurisdiction
- **Cache**: `CITATION_ORIGIN_CACHE` dict (key: lowercased case_name) avoids repeat Tier 2 calls within same run

| Tier | Method | Cost | Confidence |
|------|--------|------|------------|
| 1 | Dictionary lookup (381 known courts) | $0 | 0.95 |
| 1.5 | Domestic pattern heuristic (35 countries, regex) | $0 | 0.80 |
| 2 | Gemini LLM analysis | ~$0.001 | 0.5-1.0 |
| 3 | Web search (stub, not implemented) | - | - |
| Fallback | Assume domestic if source known | $0 | 0.60 |

**Tier 1 — Dictionary lookup** (`KNOWN_FOREIGN_COURTS`, 381 entries):
- Word-boundary regex match against court names in raw_text
- Handles ambiguity: skip if court is ambiguous for source jurisdiction (e.g., "FCA" ambiguous for both Australia and Canada)
- Returns country, region, court name

**Tier 1.5 — Domestic pattern heuristic** (`DOMESTIC_PATTERNS`, 35 countries):
- Country-specific citation format regex (e.g., Brazil: `ADI|RE|STF|STJ`, USA: `U\.S\.|S\.Ct\.|F\.\dd`, UK: `\[20\d{2}\] UKSC|EWCA`)
- If citation format matches source country's patterns -> classify as domestic

**Tier 2 — Gemini LLM** (sent to LLM):
```
CASE NAME: {case_name}
RAW CITATION: {raw_text}
SOURCE COURT JURISDICTION: {source_jurisdiction}

Analyze citation format clues, court names, language patterns.
Respond in JSON: {origin_country, region, court, year, confidence, reasoning}
```
- Only accepts results with confidence >= 0.5
- Caches results with confidence >= 0.7

#### What is sent to the LLM (Tier 2)

Case name + raw citation text + source court context + analysis rules

#### What comes back from the LLM (Tier 2)

```json
{
  "origin_country": "Netherlands",
  "region": "Global North",
  "court": "Hague District Court",
  "year": 2015,
  "confidence": 0.95,
  "reasoning": "ECLI:NL prefix indicates Dutch court"
}
```

### 5.7 — Phase 4: Sixfold Classification

- **Input**: source_jurisdiction, source_region, case_origin, case_region (all from previous phases)
- **Algorithm**: Pure rule-based (no LLM)

| Condition | Citation Type | Cross-jurisdictional |
|-----------|--------------|---------------------|
| Same jurisdiction | Domestic | No |
| Different national courts | Foreign Citation | Yes |
| National -> International tribunal | International Citation | Yes |
| International -> International | Inter-System Citation | Yes |
| International -> National member | Member-State Citation | Yes |
| International -> National non-member | Non-Member Citation | Yes |
| Unknown origin | Unknown | No |

- **Binding jurisdictions**: `BINDING_JURISDICTIONS` in config.py maps IACtHR (22 countries), ECtHR (46 countries), ACHPR (55 countries) for member/non-member distinction
- **Cost**: $0

### 5.8 — Record Creation & Persistence

For each citation, a `CitationExtractionPhased` record is created combining all phase outputs:

| Field Group | Source Phase | Fields |
|-------------|------------|--------|
| Source court | Phase 1 | source_jurisdiction, source_region |
| Extraction | Phase 2A | case_name, raw_citation_text |
| Sabin match | Filter | sabin_case_id_cited, sabin_match_tier, sabin_match_confidence |
| Snippet | Snippet extraction | snippet_text, snippet_start_char, snippet_end_char |
| Functional | Phase 2B | location_in_document (opinion_type), manual_review_reason (JSON with functional metadata) |
| Origin | Phase 3 | case_law_origin, case_law_region, origin_identification_tier, origin_confidence |
| Classification | Phase 4 | citation_type, is_cross_jurisdictional |
| Quality | Aggregated | requires_manual_review (confidence < 0.7 or unknown), average_confidence |

A `CitationExtractionPhasedSummary` record aggregates per document:
- Total references, foreign/international/foreign-international counts
- Total API calls, tokens in/out, cost USD
- Timing (start, end, duration)
- Success flag, error text, average confidence, items needing review

### 5.9 — Statistics & Final Report

Counters tracked across all documents:

| Counter | What it counts |
|---------|---------------|
| `processed` | Documents successfully completed |
| `errors` | Documents that hit exceptions |
| `phase2_failures` | Documents where LLM extraction returned None |
| `no_citations` | Documents with zero citations (or all filtered out) |
| `total_references` | Sum of all kept citations |
| `domestic_citations` | Same-jurisdiction citations |
| `foreign_citations` | Cross-national citations |
| `international_citations` | National -> International tribunal |
| `foreign_international_citations` | Other international combinations |
| `unknown_citations` | Origin unidentified |
| `functional_parties` | "parties_argument" classification |
| `functional_dismissed` | "dismissed/distinguished" |
| `functional_contributed` | "contributed to decision" |
| `majority_citations` | In majority opinion |
| `dissent_citations` | In dissent/concurrence |
| `needs_review` | Low confidence or unknown |
| `sabin_kept` | Citations matching Sabin KB |
| `sabin_discarded` | Citations not in KB (saved to discarded table) |
| `snippets_found` | Snippets located in document text |

---

## Cost Summary

| Phase | Cost per Document | Cost per 2,924 Docs | Method |
|-------|------------------|---------------------|--------|
| Steps 0-3 | $0 | $0 | No LLM |
| Step 4 (classification) | ~$0.001 | ~$3 | Gemini Pro (Tier 2 only) |
| Step 5 Phase 2A (extraction) | ~$0.002 | ~$5.85 | Gemini Flash-Lite |
| Step 5 Phase 2B (functional) | ~$0.0005 | ~$1.46 | Gemini Flash-Lite |
| Step 5 Phase 3 Tier 2 (origin) | ~$0.001 (cached) | ~$2 (estimated) | Gemini Flash-Lite |
| **Total** | **~$0.004** | **~$12** | **6% of $200 budget** |

---

## Data Lineage Summary

```
SABIN_DB Excel (16,380 rows)
  |
  |--> cases table (2,924 rows)
  |      |-- case_id, case_name, jurisdiction, region, geographies
  |
  |--> documents table (~4,500 rows)
  |      |-- document_id, case_id (FK), is_decision, pdf_downloaded
  |
  |--> PDF files (pdfs/downloaded/*.pdf)
  |      |
  |      v
  |--> extracted_text table (~2,847 rows)
  |      |-- document_id (FK), raw_text, extraction_method, quality
  |
  |--> [classify] documents.is_decision = True/False
  |
  |--> [extract_citations] for each decision with text:
         |
         |-- Phase 1: geographies -> source_jurisdiction + source_region
         |
         |-- Phase 2A: raw_text + KB (4,741 cases) -> LLM -> references[]
         |      |
         |      |-- Sabin Filter: references[] -> kept[] + discarded[]
         |      |      |                              |
         |      |      v                              v
         |      |   (forward to Phase 2B+)   citation_extraction_discarded (audit)
         |      |
         |      |-- Snippet Extraction: kept[] + raw_text -> snippets[]
         |      |
         |      |-- Phase 2B: kept[] + snippets[] -> LLM -> functional classifications
         |
         |-- Phase 3: each citation -> Tier1/1.5/2 -> origin + region
         |
         |-- Phase 4: source + origin -> rule-based -> citation_type
         |
         |-- Save: citation_extraction_phased (per citation)
         |         citation_extraction_phased_summary (per document)
```
