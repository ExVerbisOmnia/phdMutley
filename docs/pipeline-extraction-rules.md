# Citation Extraction Pipeline — Rules & Logic Reference

**Version:** 7.0 (Anti-Hallucination Pipeline)
**Purpose:** Human-readable documentation of every rule, threshold, and decision encoded in the phdMutley citation extraction pipeline. Written for domain expert review — Lucas should annotate, correct, and add edge cases before rules are re-encoded into pipeline code.
**Generated:** 27 March 2026
**Decision:** D24 — Document extraction rules in human-readable format before coding

---

## Table of Contents

1. [Pipeline Overview](#1-pipeline-overview)
2. [Corpus & Scope](#2-corpus--scope)
3. [Phase 0 — Document Quality Pre-Check](#3-phase-0--document-quality-pre-check)
4. [Phase 1 — Source Jurisdiction Identification](#4-phase-1--source-jurisdiction-identification)
5. [Phase 2A — Citation Extraction](#5-phase-2a--citation-extraction)
6. [Phase 2A+ — Post-Extraction Filters](#6-phase-2a--post-extraction-filters)
7. [Phase 2B — Functional Classification](#7-phase-2b--functional-classification)
8. [Phase 3 — Origin Identification](#8-phase-3--origin-identification)
9. [Phase 4 — Geographic Classification (Sixfold)](#9-phase-4--geographic-classification-sixfold)
10. [Phase 5 — Inline Verification](#10-phase-5--inline-verification)
11. [Confidence Scoring & Manual Review](#11-confidence-scoring--manual-review)
12. [Counting Rules](#12-counting-rules)
13. [Known Edge Cases & Open Questions](#13-known-edge-cases--open-questions)
14. [Appendix A — Global North/South Classification](#appendix-a--global-northsouth-classification)
15. [Appendix B — Binding Court Jurisdiction Mappings](#appendix-b--binding-court-jurisdiction-mappings)
16. [Appendix C — Known Foreign Courts Dictionary](#appendix-c--known-foreign-courts-dictionary)
17. [Appendix D — LLM Configuration](#appendix-d--llm-configuration)

---

## 1. Pipeline Overview

The pipeline processes judicial decisions from the Climate Case Chart (Sabin Center) database, extracting and classifying cross-jurisdictional citations to quantify transnational judicial dialogue in climate litigation.

### Processing Flow (per document)

```
Document (PDF text)
  │
  ├─ Phase 0: Quality pre-check ──── SKIP if garbled or too long ($0)
  │
  ├─ Phase 1: Source jurisdiction ID ─ From database metadata ($0)
  │
  ├─ Phase 2A: Citation extraction ── Gemini 2.5 Flash (thinking=1024)
  │    │
  │    ├─ Hard filter: pipe-format detection ($0)
  │    ├─ Hard filter: anachronism detection ($0)
  │    ├─ Sabin filter: match against knowledge base ($0)
  │    └─ Snippet extraction: locate citation in text ($0)
  │
  ├─ Phase 2B: Functional classification ── Gemini 2.5 Flash (thinking=2048)
  │
  ├─ Phase 3: Origin identification
  │    ├─ Tier 1: Dictionary lookup ($0)
  │    ├─ Tier 1.5: Domestic pattern heuristic ($0)
  │    ├─ Tier 2: Gemini 2.5 Pro (thinking=1024) (~$0.001)
  │    └─ Tier 3: Web search (not implemented)
  │
  ├─ Phase 4: Geographic classification (sixfold) ($0)
  │
  └─ Phase 5: Inline verification ── Gemini 2.5 Flash (thinking=1024)
```

### Cost Per Document

Typical cost: **$0.005–$0.02** per document (depending on length and number of citations requiring Tier 2 origin identification).

---

## 2. Corpus & Scope

### Data Source

- **Database:** Climate Case Chart (Sabin Center for Climate Change Law, Columbia Law School)
- **Total records:** 4,739 cases → 16,352 documents
- **Documents classified as judicial decisions:** ~5,513 (only these are processed)

### What Counts as a "Document"

A document is a single PDF file associated with a case. One case may have multiple documents (e.g., trial court decision, appeal, amicus brief). **Only documents classified as judicial decisions (`is_decision = True`) are processed.**

### Document Classification (Phase 4 — classify_decisions)

Documents were classified in two stages:
1. **Title-based keyword classification** (D12): The text after the last " – " separator in the Document Title is matched against 84 known keywords mapped to decision/non-decision/ambiguous buckets.
2. **LLM classification for ambiguous documents** (D13): 4,084 documents without clear title keywords were classified using Gemini via partial text extraction (first + last 2,400 characters).

### PDF Text Extraction Hierarchy

Text is extracted from PDFs using a 4-tier fallback:

| Priority | Library | Notes |
|----------|---------|-------|
| 1 | pdfplumber | Best quality, highest memory usage. 94.1% success rate. |
| 2 | PyMuPDF (fitz) | Fast, low memory. Fallback if pdfplumber fails. |
| 3 | PyPDF2 | Last-resort text extraction. |
| 4 | Tesseract OCR | Only if all above fail. Rarely needed. |

Additionally, **pymupdf4llm** generates a Markdown-formatted version of the text (`text_md` column), used as the primary input for LLM prompts when available.

---

## 3. Phase 0 — Document Quality Pre-Check

Before any LLM call, the document text is assessed for quality. **Garbled or oversized documents are skipped entirely** to avoid wasting API budget on texts that would cause hallucinations.

### Garbled Text Detection

A document is flagged as **garbled** if any of these conditions are met:

| Check | Threshold | Rationale |
|-------|-----------|-----------|
| Text too short | < 100 characters | Not a real document |
| Alphabetic ratio too low | < 40% alphabetic characters | Garbled OCR produces many symbols/digits |
| Average word length too high | > 25 characters per word | Garbled OCR concatenates words |

**Sample size:** Only the first 5,000 characters are checked (efficiency).

**Result if garbled:** Document is marked as `SKIPPED_GARBLED` in the summary table. No API calls are made.

### Oversized Document Detection

| Check | Threshold | Rationale |
|-------|-----------|-----------|
| Estimated token count | > 900,000 tokens | Exceeds model's safe context window |

Token estimation: **1 token ≈ 4 characters** (conservative for legal text).

**Result if too long:** Document is marked as `SKIPPED_TOO_LONG`. No API calls are made.

> **📝 Review question for Lucas:** Are there known important cases in the corpus that might have very long decisions (>900K tokens ≈ 3.6M characters)? If so, we need a chunking strategy for those.

---

## 4. Phase 1 — Source Jurisdiction Identification

The source jurisdiction (where the citing court sits) is determined **from the database**, not from the document text.

### Data Source

1. **Primary:** `cases.geographies` column (populated from the Sabin database Excel file)
2. **Fallback:** `documents.metadata_data → "Geographies"` field (if cases.geographies is NULL)

### Parsing Logic

The `geographies` field is a semicolon-separated string like `"United States; California"` or `"European Union; France; Belgium"`. The pipeline:

1. Splits on `;`
2. Takes the **first segment** (country level only)
3. Normalizes common aliases (see table below)

### Jurisdiction Aliases

| Alias | Normalized To |
|-------|---------------|
| USA, U.S., U.S.A., United States of America | United States |
| UK, U.K., Great Britain, Britain | United Kingdom |
| The Netherlands, Holland | Netherlands |
| NZ, Aotearoa | New Zealand |
| Turkey, Turkiye | Türkiye |

### Region Classification

Each jurisdiction is then classified into a region:

- **"International"** if the jurisdiction string is "International", "INTL", or "World"
- **"Global North"** if the country is in the Global North list (see [Appendix A](#appendix-a--global-northsouth-classification))
- **"Global South"** for everything else (default)
- **"Unknown"** if the jurisdiction is empty or "Unknown"

> **📝 Review question for Lucas:** Is the "everything else = Global South" default correct? Are there edge cases where a jurisdiction should be classified differently?

---

## 5. Phase 2A — Citation Extraction

This is the core LLM call: extracting all case law references from the document text.

### Model & Settings

| Setting | Value | Rationale |
|---------|-------|-----------|
| Model | Gemini 2.5 Flash | Cost-effective for extraction tasks |
| Temperature | 0.0 | Reproducibility (academic research) |
| Thinking budget | 1,024 tokens | Enables chain-of-thought reasoning |
| Max output tokens | 65,536 | Model default |

### What IS Extracted (12 Citation Patterns)

The LLM is instructed to extract **every reference to a judicial decision**, regardless of format:

1. **Traditional citations** — Formal legal citations: `"Brown v. Board of Education, 347 U.S. 483 (1954)"`
2. **Narrative references** — Descriptive mentions: `"The Norwegian Supreme Court held in 2020..."`
3. **Shorthand references** — Abbreviated names: `"the Urgenda case"`, `"following Abraham"`
4. **Scholarly citations** — Academic references to cases: `"Professor X's analysis of the Urgenda case"`
5. **Procedural references** — Case history: `"On appeal from..."`, `"Affirmed by..."`
6. **Comparative references** — `"Unlike the approach in..."`, `"Similar to..."`
7. **Signal citations** — `"See also..."`, `"Cf..."`, `"Compare with..."`
8. **Footnote/endnote citations** — Including supra, infra, ibid., id. references
9. **Dissenting/concurring opinion citations** — Citations in non-majority opinions
10. **Advisory opinions** — ICJ advisory opinions, other tribunal advisory opinions

### What Is NOT Extracted (Negative Examples)

The prompt explicitly instructs the LLM to **skip**:

- Cases the LLM "knows about" but that are **not mentioned** in the document
- **Metadata-format strings** (e.g., "Case Name (2015) | Court; Jurisdiction")
- **Author names or book titles** that are not judicial decisions
- **Treaties, conventions, statutes, legislation, or procedural rules** (Paris Agreement, UNFCCC, Clean Air Act, etc.)
- **Generic court references** without a specific case (e.g., "the courts have held")

### Anti-Hallucination Rules (Critical)

The extraction prompt contains 6 strict rules to prevent false extractions:

1. Extract ONLY citations that appear as **VERBATIM text** in the document
2. Do NOT infer citations from **topical similarity** to known cases
3. The `raw_text` field MUST be a **direct copy-paste** from the document
4. Do NOT **fabricate or guess** case names
5. Do NOT add case names from **training data** not mentioned in this document
6. A case is "cited" only if the document **NAMES or REFERENCES** it — topical overlap is not a citation

### Self-Check Before Submitting

The LLM is instructed to verify each extracted citation against three checks before including it:
1. Can you point to the **exact passage** in the document? If not → REMOVE
2. Is the case name **actually written** in the document? If not → REMOVE
3. Is the `raw_text` a **verbatim substring** of the document? If not → FIX

### Document Year Context

If the document year is known, it is included in the prompt: `"Document Year: 2020 (this document CANNOT cite cases from after this year)"`. This enables the LLM's own anachronism self-check.

### Extraction Output Format

Each extracted citation produces:
```json
{
  "case_name": "Name as it appears in the document",
  "raw_text": "VERBATIM citation passage copied from the document",
  "confidence": 0.0-1.0
}
```

### Large Document Chunking

Documents exceeding **40,000 tokens** (~160K characters) are split into chunks:

| Parameter | Value |
|-----------|-------|
| Chunk threshold | 40,000 tokens |
| Target chunk size | 30,000 tokens |
| Overlap between chunks | 2,000 tokens |

Each chunk gets its own LLM call. Results are merged and deduplicated.

### Knowledge Base: REMOVED from Prompt (v7 Change)

**Critical decision (v7):** The Sabin knowledge base (4,741 case entries) was **removed from the extraction prompt**. In v6, it was included as a "KNOWN CASES" section. This caused a **49.3% hallucination rate** — the LLM would "find" citations to known cases even when they weren't in the document.

The KB is now used **only after extraction** via the Sabin Filter (see Phase 2A+).

---

## 6. Phase 2A+ — Post-Extraction Filters

After extraction, three filters are applied sequentially. These are deterministic (no LLM calls, $0 cost).

### Filter 1: Pipe-Format Detection (Hard Filter)

**Rule:** If `raw_text` contains a pipe character (`|`) AND matches the pattern `(YYYY) |`, it is discarded.

**Rationale:** This pattern matches the Sabin database metadata format: `"Case Name (2015) | Court; Jurisdiction"`. Its presence in the extraction output indicates **knowledge base contamination** — the LLM reproduced a KB entry format rather than extracting a real citation.

**Regex:** `\(\d{4}\)\s*\|`

### Filter 2: Anachronism Detection (Hard Filter)

**Rule:** If a citation references a year **more than 1 year after the document year**, it is discarded.

**Formula:** `cited_year > document_year + 1` → discard

**Tolerance:** +1 year, to account for cases decided near a year boundary (e.g., a Dec 2019 decision citing a Jan 2020 case).

**Year extraction from citation text:**
1. Prefer years in parentheses/brackets: `(2015)` or `[2015]`
2. Fallback: any 4-digit year matching `19xx` or `20xx`

> **📝 Review question for Lucas:** Is the +1 year tolerance appropriate? Should it be 0 (strict) or 2 (more lenient)?

### Filter 3: Sabin Filter (Knowledge Base Matching)

**Rule:** Only citations that match an entry in the Sabin knowledge base are kept. Unmatched citations are saved to a `citation_extraction_discarded` table for potential manual review.

**Rationale:** The Sabin database defines the universe of climate litigation cases. A citation that doesn't match any known case is either: (a) a non-climate case (out of scope), (b) a hallucination, or (c) a genuine citation to a case not yet in the database.

#### Matching Algorithm (2-Tier)

**Normalization (applied to all names before matching):**
- Unicode → ASCII transliteration
- Lowercase
- Strip case numbers: `No.`, `Nos.`, `Case No.`, `Docket No.` + reference number
- Strip bracketed years: `[2014]`
- Strip US reporter citations: `347 U.S. 483`, `138 S.Ct.`
- Strip "et al."
- Remove noise words: {the, of, and, in, for, on, v, vs, v., vs.}

**Tier 1: Exact Normalized Match**
- Normalize the extracted case name
- Look up in a pre-built index of normalized Sabin case names
- If multiple candidates match, prefer the one whose year matches
- **Confidence: 1.0**

**Tier 2: Fuzzy Match**
- Compute similarity using: `0.5 × token_jaccard + 0.5 × containment`
  - Token Jaccard: |A ∩ B| / |A ∪ B| (on word tokens)
  - Containment: |A ∩ B| / |A| (what fraction of the citation's words appear in the KB entry)
- If year also matches: +0.15 bonus to similarity score
- If year mismatches: confidence × 0.8 penalty
- **Threshold: ≥ 0.70** (or ≥ 0.60 if year matches)

**Unmatched citations** are saved to `citation_extraction_discarded` with:
- The closest Sabin match name
- The match score
- The discard reason

> **📝 Review question for Lucas:** The fuzzy threshold of 0.70 was set empirically. Should we review false positives/negatives at this threshold? Some legitimate citations may be discarded if they use very different names from the Sabin entry.

### Snippet Extraction

After filtering, each kept citation is **anchored** in the document text — finding the exact character position where the citation appears.

**3-Tier Location Strategy:**

| Tier | Method | Description |
|------|--------|-------------|
| 1 | Exact match | Direct substring search of `raw_text` in document |
| 2 | Normalized match | Collapse whitespace, case-insensitive search |
| 3 | Key phrase match | Extract distinctive phrase (e.g., "X v. Y" pattern), search ±500 chars around matches |

**Context window:** ±300 characters around the match point.

---

## 7. Phase 2B — Functional Classification

A separate LLM pass classifies **how** the court used each citation.

### Model & Settings

| Setting | Value |
|---------|-------|
| Model | Gemini 2.5 Flash |
| Temperature | 0.0 |
| Thinking budget | 2,048 tokens |
| Batch size | 30 citations per LLM call |

### Functional Use Categories

| Category | Meaning | Key Signals |
|----------|---------|-------------|
| `parties_argument` | Court is recounting what a party argued | "submitted", "argued", "contended", "relied on", "appellant/respondent" |
| `dismissed` | Court REJECTS or distinguishes this citation | "distinguish", "not applicable", "unlike", "differs from", "little transfer value" |
| `contributed` | Citation supports the court's own reasoning | "following", "applying", "as held in", "consistent with", "we adopt" |

### Opinion Type

| Category | Meaning |
|----------|---------|
| `majority` | Main/majority opinion |
| `dissent` | Dissenting opinion |
| `concurrence` | Concurring opinion |
| `unclear` | Cannot determine |

**Default:** If uncertain, the LLM uses `contributed` with low confidence.

> **📝 Review question for Lucas:** Are these three functional categories sufficient? Should we distinguish "obiter dictum" references from "ratio decidendi" citations? Should "scholarly/academic" context be a separate functional category?

---

## 8. Phase 3 — Origin Identification

Determines **where the cited case comes from** (country/court/region).

### 4-Tier Strategy

#### Tier 0: Cache Lookup ($0)
- Case names are cached (lowercased, trimmed) after first identification
- Avoids repeat LLM calls for cases cited by multiple documents

#### Tier 1: Dictionary Court Match ($0)
- Search `raw_text` and `case_name` for known court names using **word-boundary regex**
- Dictionary contains **80+ court entries** across all regions (see [Appendix C](#appendix-c--known-foreign-courts-dictionary))
- Handles ambiguity: e.g., "FCA" is listed as Australian but flagged as `ambiguous_for: ["Canada"]` — skipped if source jurisdiction is Canada
- **Confidence: 0.95**

#### Tier 1.5: Domestic Pattern Heuristic ($0)
- Tests citation FORMAT patterns specific to the source jurisdiction
- Only runs if `source_jurisdiction` is known
- **25 country-specific regex pattern sets** covering:

| Country | Patterns Recognized |
|---------|-------------------|
| Colombia | T-300, C-035, SU-217; "sentencia", "tutela" |
| Brazil | AC, RE, ADI, ADPF, HC, MS; STF, STJ, TRF; CNJ numbering |
| Australia | Medium neutral citations `[YYYY] FCA|HCA|FCAFC|NSWLEC|VSC|QSC`; FCR, ALR, CLR reporters |
| United States | U.S., S.Ct., F.Supp; state abbreviations (Cal., N.Y., Ill., Tex., Fla.) |
| Canada | SCC, SCR, FC, FCA; provincial abbreviations; "Reference re" pattern |
| United Kingdom | `[YYYY] UKSC|UKHL|EWCA|EWHC|UKPC` |
| Germany | BVerfG, BGH, Bundesverfassungsgericht |
| France | Conseil d'État, Conseil Constitutionnel, Cour de Cassation |
| Netherlands | ECLI:NL format |
| New Zealand | `[YYYY] NZSC|NZCA|NZHC` |
| India | AIR, SCC reporters |
| South Africa | ZACC, ZASCA; SA, BCLR reporters |
| Norway, Sweden, Ireland, Pakistan, Kenya, Philippines, Turkey | Various local patterns |

- **Confidence: 0.80**
- Returns: origin = source_jurisdiction (domestic citation)

#### Tier 2: Gemini LLM Analysis (~$0.001)
- Model: **Gemini 2.5 Pro** (thinking=1024)
- Only runs if Tiers 1 and 1.5 both fail
- Prompt instructs the LLM to:
  - Identify the court from citation text (including non-English names)
  - Use citation format clues ("U.S." → USA, "UKSC" → UK, "[2014] FCA" → Australia)
  - Analyze case name patterns and language
  - Special rule: "Reference re ..." in Canadian documents = Canadian constitutional reference
  - Set confidence < 0.5 if uncertain
- Response: JSON with `origin_country`, `region`, `court`, `year`, `confidence`, `reasoning`
- Results cached if confidence ≥ 0.7
- **Confidence: variable (0.0–1.0 from LLM)**

#### Tier 3: Web Search (Not Implemented)
- Placeholder for future use with obscure cases

#### Fallback Logic
- If all tiers fail AND source_jurisdiction is known → default to source_jurisdiction (most citations in a document are domestic). **Confidence: 0.60**
- If no source_jurisdiction → return "Unknown". **Confidence: 0.0**

> **📝 Review question for Lucas:** The domestic default fallback (confidence 0.60) assumes most unidentified citations are domestic. Is this a safe assumption for this corpus? Are there jurisdictions that cite foreign cases more often than domestic ones?

---

## 9. Phase 4 — Geographic Classification (Sixfold)

### Initial Classification (During Extraction — `classify_citation_type`)

During extraction (Phase 4), citations receive a **simplified geographic classification**:

| Condition | Classification |
|-----------|---------------|
| Origin = Unknown or Region = Unknown | "Unknown" |
| Source jurisdiction = case origin (normalized) | "Domestic" (not cross-jurisdictional) |
| Both International | "International Citation" |
| Source International, case National | "Foreign Citation" |
| Source National, case International | "International Citation" |
| Both National, different countries | "Foreign Citation" |

### Full Sixfold Classification (Post-Extraction — `classify_decisions_sixfold.py`)

The sixfold classification runs as a **separate batch process** after extraction, using the `international_court_jurisdiction` table for membership lookups.

| # | Type | Direction | Rule |
|---|------|-----------|------|
| 1 | **Foreign Citation** | National → National | Source and cited are both national courts, different countries |
| 2 | **International Citation** | National → Int'l member court | Source is national, cited is international, AND source country is a **member** of the cited court |
| 3 | **Foreign International Citation** | National → Int'l non-member court | Source is national, cited is international, AND source country is **NOT a member** of the cited court |
| 4 | **Inter-System Citation** | Int'l → Int'l | Both courts are international |
| 5 | **Member-State Citation** | Int'l → National member | Source is international, cited is national, AND cited country is a **member** of the source court |
| 6 | **Non-Member Citation** | Int'l → National non-member | Source is international, cited is national, AND cited country is **NOT a member** of the source court |

**Domestic citations** (same jurisdiction) are classified as "Unclassified" in the sixfold system — they are **outside the scope** of the research question (transnational dialogue).

### Court-Membership Matching

The sixfold classifier uses fuzzy matching between citation fields (`cited_court`, `case_law_origin`) and the `international_court_jurisdiction` table. Matching patterns include:

- Direct court abbreviation match (e.g., "IACtHR", "ECtHR")
- Full court name match
- Semantic patterns: "European Union" → CJEU/ECJ; "Council of Europe" → ECtHR/CoE; "Inter-American" → IACtHR; "African" → ACtHPR; "WTO" / "World Trade" → WTO; "ICSID" → ICSID; "United Nations" → ICJ

Membership is checked via: `source_jurisdiction = ANY(icj.member_jurisdictions)` or `'*ALL*' = ANY(icj.member_jurisdictions)` (for courts with universal jurisdiction like ICJ).

> **📝 Review question for Lucas:** The distinction between types 2/3 and 5/6 depends on court membership data. Is the `international_court_jurisdiction` table complete? Are there courts or membership changes we should add?

---

## 10. Phase 5 — Inline Verification

Each extracted citation is verified by a second LLM pass that checks whether the citation actually exists in the document.

### Model & Settings

| Setting | Value |
|---------|-------|
| Model | Gemini 2.5 Flash |
| Temperature | 0.0 |
| Thinking budget | 1,024 tokens |
| Batch size | 50 citations per LLM call |
| Identification | Case name only (no raw_text — avoids circular reliance) |

### Verification Prompt Rules

The verification LLM receives the full document text and a list of case names to verify. It follows these rules:

1. Search the document for **ANY** reference to each case
2. **CONFIRMED:** Found → provide a `verbatim_quote` (exact copy-paste, 1–3 sentences)
3. **NOT_FOUND:** Not found anywhere in the document
4. **MISATTRIBUTED:** A similarly-named but different case is referenced → provide `corrected_case_name`
5. Return the **FIRST occurrence** if cited multiple times
6. The `verbatim_quote` MUST be a **direct substring** of the source text
7. **Keyword alone is NOT sufficient** — e.g., "Wells" matching "exploratory wells" is NOT a citation to "R(Wells) v Secretary of State"
8. Citation context must be appropriate — footnotes, case law sections, "see also" references, party names

### Fuzzy Snippet Matching (4-Tier)

The verification quote is then matched back to the document text:

| Tier | Method | Description |
|------|--------|-------------|
| 1 | Exact/normalized/key phrase | Via `extract_snippet` (same as Phase 2A+) |
| 1.5 | Whitespace-normalized | Collapse all whitespace, case-insensitive |
| 2 | Sliding window fuzzy | SequenceMatcher with step=quote_len/4, refined with step=1 |

**Fuzzy match threshold: ≥ 0.95** (95% character-level similarity).

Minimum quote length for fuzzy matching: **20 characters**.

### Verification Outcomes

| Verdict | Action |
|---------|--------|
| CONFIRMED | Citation validated; snippet stored if fuzzy match found |
| NOT_FOUND | Flagged for manual review (`requires_manual_review = True`) |
| MISATTRIBUTED | Flagged for manual review; corrected name stored |
| UNVERIFIED | LLM omitted this citation from response; flagged for manual review |

### Skipped Documents

- **Garbled text:** All citations marked as `SKIPPED_GARBLED`
- **Token limit exceeded:** Batch skipped with warning (citations remain unverified)

> **📝 Review question for Lucas:** Should NOT_FOUND citations be automatically discarded, or kept with a flag? Currently they're kept but flagged for manual review.

---

## 11. Confidence Scoring & Manual Review

### Confidence Sources

| Phase | Confidence Range | Source |
|-------|-----------------|--------|
| Phase 2A (extraction) | 0.0–1.0 | LLM self-reported |
| Sabin Filter | 0.0–1.0 | Match algorithm (1.0 for exact, lower for fuzzy) |
| Phase 3 Tier 1 (dictionary) | 0.95 | Fixed |
| Phase 3 Tier 1.5 (domestic pattern) | 0.80 | Fixed |
| Phase 3 Tier 2 (LLM) | 0.0–1.0 | LLM self-reported |
| Phase 3 fallback (domestic default) | 0.60 | Fixed |
| Phase 3 fail | 0.0 | Fixed |

### Manual Review Trigger

A citation is flagged for manual review (`requires_manual_review = True`) if:

- **Origin confidence < 0.7**
- **Citation type = "Unknown"**
- **Verification verdict = NOT_FOUND or MISATTRIBUTED or UNVERIFIED**

### Minimum Confidence Threshold

Citations with confidence below **0.3** (`min_confidence` in config) may be treated with additional scrutiny. This threshold is configurable.

---

## 12. Counting Rules

### Citation Counting (D22)

**Rule:** If a document cites a foreign decision 15 times textually, count as **1 citation**. We count the **act of invoking** a case, not the number of textual references.

Implementation: `COUNT(DISTINCT case_name)` per document.

### Unique Citations Tracking

The sixfold classification engine computes two tracking metrics per case:

1. **unique_citations / citing_cases:** How many distinct OTHER cases cite THIS case
2. **unique_cited_count / cited_cases:** How many distinct cases are cited BY this case

Matching uses partial case-name matching (case-insensitive, first 50 characters).

### Reporting (D17)

Use **relative proportions** (percentages of identified citations), not raw counts, for public claims.

---

## 13. Known Edge Cases & Open Questions

### The Juliana Problem (Multi-Instance Litigation)

The same case can be litigated across multiple courts (domestic and international). Example: **Juliana v. United States** has been cited both as a US domestic case and in international contexts.

- **When systematic:** The citing court's text names the specific court → disambiguation is possible
- **When unsystematic:** The citation doesn't specify which proceeding → inference required

**Current handling:** The pipeline identifies the origin based on court name patterns and the cited_court field. If the citation text doesn't name a specific court, it may default to the wrong instance.

> **📝 Open question:** How should we handle ambiguous multi-instance cases? Options:
> 1. Default to the domestic instance (most commonly cited)
> 2. Flag for manual review
> 3. Use the context of the citing court to infer (e.g., IACtHR judge citing Juliana → likely the US instance)

### International Courts with Overlapping Jurisdiction

Some courts have overlapping subject-matter jurisdiction (e.g., ICJ and ITLOS for maritime issues). The classification depends on which court is identified, but citations may not always specify.

### Abbreviation Ambiguity

Some abbreviations are shared between courts:
- **FCA:** Federal Court of Australia vs. Federal Court of Appeal (Canada)
- **SC:** Supreme Court (multiple countries)

**Current handling:** The dictionary has an `ambiguous_for` field that prevents matching when the source jurisdiction is in the ambiguous list.

### Non-English Citations

Many citations are in languages other than English (Spanish, Portuguese, French, German, Dutch, Norwegian). The pipeline handles these through:
- Native-language court name entries in the dictionary (e.g., "Supremo Tribunal Federal", "Conseil d'État")
- Gemini's multilingual capabilities (Tier 2 origin identification)
- Country-specific citation format patterns in Tier 1.5

### Self-Citation

Currently, domestic citations (same jurisdiction) are classified as "Unclassified" in the sixfold system. Self-citations within the same court are not separately flagged.

> **📝 Open question:** Should we distinguish "same court" self-citations from "same jurisdiction, different court" citations? This matters for measuring horizontal vs. vertical judicial dialogue.

---

## Appendix A — Global North/South Classification

### Global North Countries (28)

United States, United Kingdom, Canada, Australia, New Zealand, Germany, France, Netherlands, Belgium, Switzerland, Austria, Sweden, Norway, Denmark, Finland, Iceland, Ireland, Italy, Spain, Portugal, Greece, Japan, South Korea, Singapore, European Union, Council of Europe

### Classification Rule

- If in the Global North list → "Global North"
- **Everything else → "Global South"** (default)
- International organizations (EU, Council of Europe, OAS, etc.) → "International" (handled before the North/South check)

> **📝 Review question for Lucas:** This list follows a conventional academic classification. Should we add or remove any countries? Notable edge cases:
> - **Israel** — currently Global South by default
> - **Türkiye** — currently Global South by default
> - **Russia** — currently Global South by default
> - **Taiwan** — not listed, would default to Global South
> - **Hong Kong SAR** — not listed, would default to Global South

---

## Appendix B — Binding Court Jurisdiction Mappings

These mappings determine whether a citation is "International" (member court) vs. "Foreign International" (non-member court) in the sixfold classification.

### Inter-American Court of Human Rights (IACtHR)

**20 member states:** Argentina, Barbados, Bolivia, Brazil, Chile, Colombia, Ecuador, Paraguay, Peru, Suriname, Uruguay, Costa Rica, El Salvador, Guatemala, Honduras, Nicaragua, Panama, Mexico, Haiti, Dominican Republic

### European Court of Human Rights (ECtHR)

**42 member states:** Albania, Germany, Andorra, Armenia, Austria, Azerbaijan, Belgium, Bosnia and Herzegovina, Bulgaria, Cyprus, Croatia, Denmark, Slovakia, Slovenia, Spain, Estonia, Finland, France, Georgia, Greece, Hungary, Ireland, Iceland, Italy, Latvia, Liechtenstein, Lithuania, Luxembourg, North Macedonia, Malta, Moldova, Monaco, Montenegro, Norway, Netherlands, Poland, Portugal, United Kingdom, Czech Republic, Romania, San Marino, Serbia, Sweden, Switzerland, Turkey, Ukraine

### African Court on Human and Peoples' Rights (ACHPR)

**34 member states:** Algeria, Benin, Burkina Faso, Burundi, Cameroon, Chad, Comoros, Congo, Ivory Coast, Gabon, Gambia, Ghana, Guinea-Bissau, Kenya, Lesotho, Libya, Malawi, Mali, Mauritania, Mozambique, Niger, Nigeria, Rwanda, Western Sahara, Senegal, South Africa, Tanzania, Togo, Tunisia, Uganda, Zambia, Zimbabwe

### Global Courts (Universal Jurisdiction)

- International Court of Justice (ICJ)
- International Tribunal for the Law of the Sea (ITLOS)

These are treated as binding on all countries (via `'*ALL*'` in member_jurisdictions).

> **📝 Review question for Lucas:** Are these membership lists current? Any countries that have withdrawn or joined since the database was compiled? Notable: UK withdrew from the EU but remains under ECtHR.

---

## Appendix C — Known Foreign Courts Dictionary

The origin identification dictionary contains **80+ court entries**. Below is a summary by region:

### International Courts
ICJ, ITLOS, IACtHR, ECtHR, CJEU/ECJ, African Court on Human and Peoples' Rights

### Global North — Europe
Netherlands: District Court of The Hague, Hoge Raad, Rechtbank Den Haag
UK: UK Supreme Court, Court of Appeal, High Court of Justice, High Court of Justiciary (Scotland), Court of Session
Germany: Bundesverfassungsgericht (Federal Constitutional Court)
France: Conseil Constitutionnel, Conseil d'État
Norway: Norwegian Supreme Court, Oslo District Court, Borgarting Court of Appeal
Sweden: Supreme Court of Sweden
Finland: Supreme Court of Finland

### Global North — Americas & Pacific
USA: (identified via reporter patterns, not dictionary)
Canada: Supreme Court of Canada, Federal Court of Canada, Ontario Superior Court
Australia: High Court, Federal Court, Land and Environment Court
New Zealand: Supreme Court, High Court, Court of Appeal

### Global South — Latin America
Brazil: Supremo Tribunal Federal (STF), Superior Tribunal de Justiça (STJ), Tribunal Regional Federal (TRF)
Colombia: Corte Constitucional, Corte Suprema de Justicia, Consejo de Estado
Argentina: Corte Suprema de Justicia de la Nación
Chile: Tribunal Constitucional

### Global South — Africa & Asia
South Africa: Constitutional Court, Supreme Court
Kenya: High Court
India: Supreme Court
Philippines: Supreme Court
Pakistan: Supreme Court
Bangladesh: Supreme Court

---

## Appendix D — LLM Configuration

### Models Used

| Model | Used For | Thinking Budget |
|-------|----------|-----------------|
| Gemini 2.5 Flash | Extraction (Phase 2A), Functional classification (Phase 2B), Verification (Phase 5) | 1,024–2,048 tokens |
| Gemini 2.5 Pro | Origin identification Tier 2 (Phase 3) | 1,024 tokens |

### API Call Settings

| Setting | Value |
|---------|-------|
| Temperature | 0.0 (all calls) |
| Max retries | 3 (sync), 5 (async) |
| Retry delay | 2.0 seconds (exponential backoff) |
| Key rotation | Multi-key pool with round-robin + cooldown |
| Key spacing | 0.5s minimum between reuses of same key |
| Rate limit cooldown | 60s default per key |

### JSON Response Handling

- Strip markdown code fences (`\`\`\`json ... \`\`\``)
- Try direct JSON parse → fallback to regex extraction of `{...}` or `[...]`
- Truncated JSON repair: trim from end, close open braces/brackets

### Cost Estimates (per 1K tokens)

| Model | Input | Output |
|-------|-------|--------|
| Gemini 2.5 Flash | $0.000150 | $0.000600 |
| Gemini 2.5 Pro | $0.00125 | $0.00500 |

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 27 Mar 2026 | Gustavo (via Claude) | Initial document — audit of v7 pipeline code |

---

*This document is intended for review by Lucas Biasetton. Please annotate directly: add edge cases, correct rules, flag questionable assumptions, and note domain-specific exceptions that should be encoded into the pipeline.*
