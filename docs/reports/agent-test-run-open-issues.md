# Agent Pipeline — Open Issues & Decisions

**Date:** 9 April 2026
**Context:** Following 5 test runs of the 2-agent citation extraction pipeline (citation-extractor + citation-verifier) on documents from the exported `data/decisions_md/` corpus.
**Status:** All items require review/decision before full-scale execution.

---

## Table of Contents

1. [Classification Rules — Sixfold Refinements](#1-classification-rules--sixfold-refinements)
2. [Metadata Quality — Sabin Database Issues](#2-metadata-quality--sabin-database-issues)
3. [Text Extraction Quality — Truncated Footnotes](#3-text-extraction-quality--truncated-footnotes)
4. [Document Size — Chunking Strategy](#4-document-size--chunking-strategy)
5. [Functional Use — Dual-Role Citations](#5-functional-use--dual-role-citations)
6. [Agent Performance — Findings from Test Runs](#6-agent-performance--findings-from-test-runs)
7. [Agent Rules — Updates Needed](#7-agent-rules--updates-needed)

---

## 1. Classification Rules — Sixfold Refinements

### ISSUE 1.1: Same-court self-citation = Domestic

**Status:** Decided by Gus — confirmed as Domestic.

**Rule:** When the source court and cited court are the same institution or part of the same court system (e.g., CJEU citing CJEU, CJEU citing General Court, IACtHR citing its own prior advisory opinions), classify as **Domestic**. These are NOT counted in the transnational dialogue analysis.

**Examples:**

- CJEU judgment citing prior CJEU judgment → Domestic
- CJEU AG Opinion citing prior CJEU ruling → Domestic
- IACtHR advisory opinion citing prior IACtHR advisory opinion → Domestic
- US 9th Circuit citing US Supreme Court → Domestic (same national jurisdiction)

**Impact:** The pipeline's prior classification of CJEU→CJEU as "Inter-System Citation" (Type 4) was incorrect. Affects all CJEU, ECtHR, IACtHR documents that cite their own prior case law.

**Affected test documents:**

- Saint-Gobain: 3 citations reclassified from Inter-System → Domestic
- ExxonMobil: 18 citations reclassified from Inter-System → Domestic

**Action required:** Update agent rules (both extractor and verifier) + working document.

---

### ISSUE 1.2: National court citing member international court = Type 2 (flag for Lucas)

**Status:** Decided by Gus — keep as Type 2: International Citation AND flag for Lucas.

**Rule:** When a national court cites an international court to which its jurisdiction pertains (i.e., it is a member state), this IS transnational dialogue and should be classified as **Type 2: International Citation**. Lucas needs this data.

**Examples:**

- Germany (national) citing ECtHR → Type 2 (Germany is ECtHR member)
- Colombia (national) citing IACtHR → Type 2 (Colombia is IACtHR member)
- Australia (national) citing ICJ → Type 2 (ICJ has universal jurisdiction)
- Netherlands citing CJEU → Type 2 (Netherlands is EU member)

**Distinction from Issue 1.1:** Issue 1.1 covers an *international court citing itself*. Issue 1.2 covers a *national court citing an international court it belongs to*. These are different — 1.2 represents genuine vertical judicial dialogue between national and international levels.

**Action required:** Ensure the sixfold classification algorithm in the verifier correctly identifies these and does NOT classify them as Domestic. The court-membership tables in Appendix B are needed for this lookup.

---

### ISSUE 1.3: National court citing international court it does NOT belong to = Type 3

**Status:** No change needed — already in the rules.

**Rule:** When a national court cites an international court of which it is NOT a member (e.g., a US court citing ECtHR — the US is not an ECtHR member), classify as **Type 3: Foreign International Citation**.

**No action required** — already correctly specified in the agent rules.

---

## 2. Metadata Quality — Sabin Database Issues

### ISSUE 2.1: Juliana document misattributed to IACommHR (CRITICAL)

**Status:** Discovered during test run. Requires investigation.

**Problem:** Document `4da6a9cf-9d3c-518f-a0d9-ebb49f771db7` has frontmatter:

- `jurisdiction: "Inter-American Commission on Human Rights - Inter-American System of Human Rights"`
- `region: "Global South"`

But the document content is unambiguously the **US Ninth Circuit Court of Appeals opinion** in Juliana v. United States (No. 18-36082, filed January 17, 2020), plus subsequent orders (en banc denial, mandamus order).

**Impact:** The pipeline classified all 30 extracted citations as "Inter-System" or "Non-Member Citation" — all wrong. The actual classification for all 100 citations the agent found is **Domestic** (US court citing US courts).

**Root cause:** The Sabin Center database likely has multiple documents per case, and this document may have been associated with the IACommHR petition related to Juliana, even though the document itself is the US federal court opinion.

**Recommendation:** Run a systematic check for documents where the frontmatter jurisdiction doesn't match the document content. A heuristic: if a document attributed to an international court contains only domestic citations in a specific national format (e.g., all US reporter citations), it's likely misattributed.

— Claude = save this recommendation as a task, highest priority.

**Proposed query to investigate scope:**

```sql
-- Find documents attributed to international courts that may be misattributed
SELECT d.document_id, c.case_name, c.jurisdiction, c.geographies,
       COUNT(cep.extraction_id) AS total_citations,
       COUNT(CASE WHEN cep.case_law_origin = SPLIT_PART(c.geographies, ';', 1) THEN 1 END) AS domestic_citations
FROM documents d
JOIN cases c ON c.case_id = d.case_id
LEFT JOIN citation_extraction_phased cep ON cep.document_id = d.document_id
WHERE c.jurisdiction ILIKE '%international%' OR c.jurisdiction ILIKE '%inter-american%'
   OR c.jurisdiction ILIKE '%european court%'
GROUP BY d.document_id, c.case_name, c.jurisdiction, c.geographies
HAVING COUNT(cep.extraction_id) > 5
   AND COUNT(CASE WHEN cep.case_law_origin = SPLIT_PART(c.geographies, ';', 1) THEN 1 END)::float
       / NULLIF(COUNT(cep.extraction_id), 0) > 0.8
ORDER BY total_citations DESC;
```

**Action required:** Investigate scope of misattribution. Decide whether to correct in DB or handle in post-processing.

**Status update (Gus, 9 Apr):** Saved as highest-priority task — see [T1 in Open Tasks](#open-tasks).

---

### ISSUE 2.2: EU courts classified as "Global South" in region field

**Status:** Discovered during test runs. Systematic data issue.

**Problem:** The `region` field for CJEU/ECJ documents defaults to "Global South" because the classification rule is: "if not in Global North list → Global South." International organizations (EU, Council of Europe, IACtHR, etc.) should be classified as **"International"**, not "Global South."

**Affected documents:** All documents from:

- European Court of Justice / CJEU
- European Court of Human Rights / ECtHR
- Inter-American Court / IACtHR / IACommHR
- African Court / ACHPR
- ICJ, ITLOS
- Arbitral tribunals (ICSID, PCA, WTO)

**Impact:** Sixfold classification uses `source_region` from the frontmatter. If the source is misclassified as "Global South" when it should be "International", the classification algorithm takes the wrong branch.

**Recommendation:** Fix in the export script (`extract_year` already parses frontmatter — add a `fix_region` function):

```python
INTERNATIONAL_KEYWORDS = [
    "international", "inter-american", "european court", "ecthr", "echr",
    "cjeu", "ecj", "african court", "achpr", "icj", "itlos", "icsid",
    "arbitral", "wto", "pca", "tribunal"
]

def fix_region(jurisdiction: str, region: str) -> str:
    """Override region to International for international courts."""
    j = (jurisdiction or "").lower()
    if any(kw in j for kw in INTERNATIONAL_KEYWORDS):
        return "International"
    return region
```

**Action required:** Apply fix in export script + re-export affected documents. Consider also fixing in the source DB.

— Claude = I accept your suggestion, note a task to apply it.

**Status update (Gus, 9 Apr):** Approved — see [T2 in Open Tasks](#open-tasks).

---

### ISSUE 2.3: Frontmatter `year` may not reflect the document's actual date

**Status:** Partially fixed. Export script now parses `[YYYY]` and `(YYYY)` from `case_number`.

**Problem:** The `document_date` column is NULL for all 4,755 decisions. The `case_filing_year` reflects when the case was filed, not when the specific document (judgment, opinion, order) was issued. For Sharma, this gave 2020 (filing year) instead of 2022 (latest proceeding). For Saint-Gobain, it gave 2012 (General Court filing) instead of 2016 (AG Opinion delivery).

**Current fix:** The export script now parses `[YYYY]` and `(YYYY)` from the `case_number` field and takes the latest year. This is better but not perfect — the `case_number` field sometimes contains years from multiple proceedings.

**Impact:** Incorrect year can trigger false anachronism flags (e.g., a 2016 opinion citing a 2014 judgment flagged as anachronistic because the frontmatter says 2012). The Saint-Gobain extractor correctly noted this discrepancy.

**Recommendation:** Accept as "good enough" for now. The agents are instructed to note anachronism discrepancies rather than hard-discard. A future improvement would be to extract the actual document date from the document text header (most decisions state their date prominently).

**Action required:** None immediately. Note as a known limitation.

— Claude = not good enough for now, note a task to fix this.

**Status update (Gus, 9 Apr):** Rejected as "good enough." Saved as task to extract actual document date from the document text header — see [T3 in Open Tasks](#open-tasks).

---

## 3. Text Extraction Quality — Truncated Footnotes

### ISSUE 3.1: pymupdf4llm truncates footnote pages in some documents

**Status:** Discovered during Saint-Gobain test run. Requires investigation.

**Problem:** The Saint-Gobain document (AG Opinion, CJEU) has 38 footnotes referenced in the text body, but pages 8-11 (containing the footnote text) were blank/truncated in the markdown extraction. The footnotes likely contain additional case references with full citation details (case numbers, ECLI identifiers, years).

**Impact:** The extractor could only find 4 citations from the body text. The full footnotes would likely reveal the complete case details for Flachglas Torgau (case number, year), Sweden v MyTravel (case number, year), and the Bundesverwaltungsgericht ruling (specific case reference).

**Scope unknown.** This may affect other documents with footnote-heavy formats (common in CJEU AG Opinions, ECtHR judgments, and academic-style judicial decisions).

**Recommendation:** For documents where the agent notes missing footnotes:

1. Check if `raw_text` or `processed_text` (non-markdown columns) contain the footnotes
2. If yes, provide a fallback: the agent can request the raw_text version for footnote-heavy documents
3. If no, this is a pymupdf4llm extraction limitation — consider re-extracting problematic PDFs with a different tool

**Proposed investigation:**

```sql
-- Sample documents to check if raw_text has footnotes that text_md is missing
SELECT d.document_id, c.case_name,
       LENGTH(et.text_md) AS md_len,
       LENGTH(et.raw_text) AS raw_len,
       LENGTH(et.raw_text) - LENGTH(et.text_md) AS delta
FROM documents d
JOIN cases c ON c.case_id = d.case_id
JOIN extracted_text et ON et.document_id = d.document_id
WHERE et.text_md IS NOT NULL AND et.raw_text IS NOT NULL
ORDER BY (LENGTH(et.raw_text) - LENGTH(et.text_md)) DESC
LIMIT 20;
```

**Action required:** Investigate scope. Decide whether to provide raw_text fallback for agents.

— Note a task to invesetigate this. My guess for now is to provide the agents with the raw text as default, if that doesn't trigger any downside to the text proccessing by the agent.

**Status update (Gus, 9 Apr):** Saved as task. Investigation needed before deciding raw_text vs text_md as default — see [T4 in Open Tasks](#open-tasks).

**Trade-offs to evaluate during investigation:**

| Aspect             | `text_md` (markdown, current)                        | `raw_text` (plain)                              |
| ------------------ | ---------------------------------------------------- | ----------------------------------------------- |
| Footnote retention | Truncates in some docs (see Saint-Gobain pp. 8–11)   | Likely preserves (hypothesis — needs verifying) |
| Document structure | Headers, lists, tables preserved → helps agent parse | Flat — agent must infer structure from layout   |
| Page boundaries    | Cleaner — pymupdf4llm strips headers/footers         | May contain page-header/footer noise            |
| OCR artifacts      | Mostly cleaned                                       | More likely to leak                             |
| Agent prompt fit   | Markdown-friendly (matches what we've been training) | Needs new instructions on parsing flat text     |
| Storage            | Already exported to `data/decisions_md/`             | Would need re-export with `et.raw_text`         |

**Suggested investigation plan:** Run the proposed SQL above to find docs where `LENGTH(raw_text) - LENGTH(text_md)` is large, then sample 5 (small/medium/large, citation-heavy and footnote-heavy) and dual-extract both versions to compare recall.

---

## 4. Document Size — Chunking Strategy

### ISSUE 4.1: Large documents exceed practical single-agent processing limits

**Status:** Discussed. Strategy proposed, pending approval.

**Problem:** The corpus has 318 documents (7%) over 25K words, including 47 documents over 100K words (max: 521K words). These are too large for a single agent pass.

**Document size distribution:**

| Bracket       | Docs  | %    | Strategy                              |
| ------------- | ----- | ---- | ------------------------------------- |
| 0–10K words   | 3,331 | 74%  | Single pass — no chunking             |
| 10–25K words  | 848   | 19%  | Single pass — comfortable             |
| 25–50K words  | 192   | 4.3% | Single agent, progressive file output |
| 50–100K words | 79    | 1.8% | Single agent, progressive file output |
| 100K+ words   | 47    | 1.0% | Pre-split + parallel agents + merge   |

**Proposed tiered approach:**

#### Tier 1 (93% of docs, < 25K words): Single Pass

No changes needed. Current agent design handles these perfectly. Test runs confirmed performance on documents up to 19.5K words (Juliana).

#### Tier 2 (6% of docs, 25K–100K words): Progressive File Output

The agent reads the document in chunks using the `Read` tool's offset/limit parameters. After processing each chunk, it appends found citations to a JSON file on disk (`data/extraction_results/{document_id}_partial.json`). After all chunks are processed, the agent reads back the partial file, deduplicates, and produces the final output.

The **JSON file on disk is the persistent memory** between chunks — no inter-agent state passing needed.

Key instruction additions for the agent:

```
For documents over 500 lines:
1. Read in chunks of 300 lines using Read(offset=N, limit=300)
2. After each chunk, append found citations to data/extraction_results/{document_id}_partial.json
3. After all chunks, read back the partial file → deduplicate → produce final JSON output
```

#### Tier 3 (1% of docs, 100K+ words): Pre-Split + Parallel Agents + Merge

A Python script pre-splits the document into overlapping chunks (~20K words each, 2K word overlap at boundaries to avoid splitting citations). Each chunk becomes its own extraction job.

```
Python splits doc → chunk_1.md, chunk_2.md, chunk_3.md (with overlap)
Agent A extracts from chunk_1 → chunk_1_citations.json
Agent B extracts from chunk_2 → chunk_2_citations.json  (parallel)
Agent C extracts from chunk_3 → chunk_3_citations.json  (parallel)
Python merge script → deduplicates across chunks → final.json
```

**Scripts needed:**

- `scripts/chunk_large_docs.py` — splits documents into overlapping chunks
- `scripts/merge_chunk_results.py` — merges and deduplicates chunk outputs

**Recommendation:** Implement Tier 2 first (covers 271 docs). Implement Tier 3 only if/when we process the 47 largest documents.

**Action required:** Approve tiered approach. Decide on chunk size (300 lines suggested) and overlap (2K words suggested for Tier 3).

— Claude = I accept your suggestions.

**Status update (Gus, 9 Apr):** Approved — Tier 1 single pass / Tier 2 progressive file output / Tier 3 pre-split + parallel + merge. Chunk size 300 lines, Tier 3 overlap 2K words. See [T5 in Open Tasks](#open-tasks).

---

## 5. Functional Use — Dual-Role Citations

### ISSUE 5.1: Citations that are both "invoked" by a party and "aligned" by the court

**Status:** Discovered during Leghari test run. Needs a rule decision.

**Problem:** In Leghari v. Federation of Pakistan, both cited cases (Imrana Tiwana, Shehla Zia) appeared in two contexts:

1. Paragraph 3: "Reliance is placed on..." — counsel for the petitioner cites them → `invoked`
2. Paragraph 22: "Our environmental jurisprudence from Shehla Zia case to Imrana Tiwana case has weaved our constitutional values..." — the court itself endorses them → `aligned`

Agent 1 classified as `invoked` (primary citation site). Agent 2 upgraded to `aligned` (court's own endorsement is the higher-authority signal). Both are defensible.

**Recommendation:** When a citation serves dual roles, classify by the **court's own use** (the higher-authority signal). The court's treatment of a citation matters more than how a party introduced it. If the court merely reports a party's argument without endorsing it, it stays `invoked`. If the court later adopts or relies on the same case, upgrade to `aligned`.

**Proposed rule text:**

> When a case is both invoked by a party and later aligned/contested/avoided by the court itself, the court's own treatment takes precedence for classification. The primary functional_use reflects how the court engages with the cited case, not how a party introduced it. Note the dual usage in `verification_notes`.

**Action required:** Decide on the rule. Update agent instructions if approved.

— Claude = the citations that matter are made by the courts, judges. If only invoked by the parts and referenced by the judge with no consideration (accept, reject), only aknowledgement, dismiss.

**Status update (Gus, 9 Apr):** Decided — court engagement is the criterion for inclusion. The rule is now stricter than my original proposal: citations only invoked by parties and merely acknowledged by the judge (no acceptance/rejection/distinction) must be **DISMISSED** from the dataset, not just relabelled.

**Revised rule for the agents:**

> A citation is included in the dataset only if the court itself engages with it — by aligning, contesting, distinguishing, applying, or actively avoiding the cited case. Citations that appear *only* in summaries of party arguments, with no subsequent engagement by the court (mere acknowledgement of "petitioner cited X"), are **excluded from extraction**.
> 
> Allowed `functional_use` values become: `aligned`, `contested`, `avoided`. The `invoked` category is retained ONLY when a party invoked the case AND the court subsequently engaged with it (in which case it should usually be re-tagged with the court's actual treatment — `aligned`/`contested`/`avoided`).

**Open question for Gus (please clarify):** There are two possible encodings for this rule, with different research-data implications:

1. **Hard exclusion at extraction time** — the extractor agent silently drops "mere acknowledgement" citations. The dataset only contains court-engaged citations. *Cleaner dataset, but loses count of how often parties cite vs. how often courts engage.*
2. **Soft tagging** — extract everything, but tag mere-acknowledgement citations with `functional_use: dismissed` (or `excluded_from_analysis: true`). The default analysis pipeline filters them out, but Lucas can still see the distribution. *Slightly more data engineering, but preserves a useful research signal: the gap between what parties cite and what courts engage with.*

Which encoding do you want? My recommendation is **#2 (soft tagging)** — it costs little extra and the "what parties cite vs. what courts engage" gap is itself a finding worth quantifying.

— Claude = Lets go with option 2.

— See [T6 in Open Tasks](#open-tasks).

---

## 6. Agent Performance — Findings from Test Runs

### Test Run Summary (5 documents)

| #   | Document                         | Words  | Region         | Agent unique | Pipeline unique | Recall         | Precision      |
| --- | -------------------------------- | ------ | -------------- | ------------ | --------------- | -------------- | -------------- |
| 1   | Sharma v Minister (Australia)    | 6,651  | Global North   | 17           | —               | 17/17 (100%)   | 17/17 (100%)   |
| 2   | Leghari v Pakistan (Pakistan)    | 7,208  | Global South   | 2            | —               | 2/2 (100%)     | 2/2 (100%)     |
| 3   | Saint-Gobain v Commission (CJEU) | 7,269  | International  | 4            | 3*              | 4/4 (100%)     | 4/4 (100%)     |
| 4   | ExxonMobil v Germany (CJEU)      | 12,631 | International  | 18           | 7*              | 18/18 (100%)   | 18/18 (100%)   |
| 5   | Juliana Youth v USA (9th Cir)    | 19,538 | Global North** | 100          | 9*              | 100/100 (100%) | 100/100 (100%) |

*Pipeline count uses D22 deduplication (unique cases), not raw citation mentions.
**Frontmatter says "Global South" / IACommHR — incorrect metadata.

### Key Performance Observations

**6.1 — Zero hallucinations across all 5 test runs.** No false positives. The anti-hallucination protocol is working: no fabricated case names, no topical-overlap false matches, no metadata-format contamination.

**6.2 — Agents found substantially more citations than the Gemini pipeline.** ExxonMobil: 18 unique vs 7 in pipeline. Juliana: 100 unique vs 9 in pipeline. The Gemini pipeline appears to have been under-extracting.

**6.3 — Noise rejection is robust.** Leghari had 8 non-judicial references (IPCC reports, UNFCCC glossary, academic articles, policy documents, the "writ of kalikasan" concept). All 8 correctly skipped. Juliana had 2 borderline items (Cardozo book, Dred Scott passing mention in a quote) — both correctly identified as NOT_A_CASE.

**6.4 — Deduplication works correctly.** Leghari: 2 shorthand back-references correctly marked as DUPLICATE. ExxonMobil: 8 repeat mentions correctly deduplicated (Trinseo 3x, Evonik 3x, PPC Power 2x). Juliana: ~10 duplicates merged.

**6.5 — Origin identification is accurate.** 141/141 citations across all 5 test runs had correct origin identification. Pakistani PLD format, Australian CLR/FCR format, CJEU ECLI format, US reporter format — all correctly parsed.

**6.6 — Functional use has good variety.** Across the 5 runs: `aligned` (dominant), `contested` (8 instances in Juliana, 2 in Saint-Gobain), `invoked` (2 in Leghari, 1 in Juliana), `avoided` (0 — no test case exercised this category yet).

**6.7 — Processing time scales linearly with document size.** ~1 minute per 5K words for extraction, ~1.5 minutes per 5K words for verification. Juliana (19.5K words) took ~13 minutes total. Extrapolating: a full corpus run of 4,497 documents (median 4.4K words) would take roughly 15–20 hours of agent time, parallelizable.

---

## 7. Agent Rules — Updates Needed

Summary of all rule changes required based on test findings:

| #   | Change                                                                                                                                                                                                                                                                                                                                                   | Affected Files                                               | Priority |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ | -------- |
| 7.1 | **Same-court = Domestic** — add explicit rule that CJEU→CJEU, ECtHR→ECtHR etc. is Domestic                                                                                                                                                                                                                                                               | `citation-verifier.md`, `agent-citation-extraction-rules.md` | High     |
| 7.2 | **National→member international = Type 2 + `is_vertical_dialogue: true`** — output schema gains a boolean field; verifier sets it to `true` when source is a national court that is a member of the cited international court (e.g., Germany→ECtHR, Colombia→IACtHR, NL→CJEU, any country→ICJ/ITLOS); `false` otherwise. Type 2 sixfold tag is preserved | `citation-verifier.md`, `agent-citation-extraction-rules.md` | High     |
| 7.3 | **Dual functional use rule** — court's own treatment takes precedence over party invocation                                                                                                                                                                                                                                                              | `citation-verifier.md`, `agent-citation-extraction-rules.md` | Medium   |
| 7.4 | **Progressive file output for large docs** — add chunking instructions for > 500 line documents                                                                                                                                                                                                                                                          | `citation-extractor.md`                                      | Medium   |
| 7.5 | **Fix region for international courts in export** — add `fix_region()` to export script                                                                                                                                                                                                                                                                  | `scripts/export_decisions_md.py`                             | High     |
| 7.6 | **Truncated footnotes awareness** — instruct agents to note when footnotes appear truncated                                                                                                                                                                                                                                                              | `citation-extractor.md`                                      | Low      |
| 7.7 | **raw_text clarification** — must be the passage containing the case name, not a quote from the case (already applied after test 1)                                                                                                                                                                                                                      | Already done                                                 | Done     |

---

## Decision Log

| #   | Decision                                                                                                                                                                                                                                                | Date       | By  |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | --- |
| D29 | CJEU citing CJEU = Domestic (not Inter-System)                                                                                                                                                                                                          | 9 Apr 2026 | Gus |
| D30 | National court citing member international court = Type 2 + `is_vertical_dialogue: true` boolean (Rule 7.2 updated)                                                                                                                                     | 9 Apr 2026 | Gus |
| D31 | Court engagement is the criterion for inclusion — mere-acknowledgement citations are **soft-tagged** `functional_use: dismissed` (encoding #2 chosen)                                                                                                   | 9 Apr 2026 | Gus |
| D32 | Tiered chunking approved: T1 single pass / T2 progressive file / T3 pre-split + parallel. 300-line chunks, 2K-word overlap (T3)                                                                                                                         | 9 Apr 2026 | Gus |
| D33 | Footnote truncation — **A: Global switch to `raw_text`**. Markdown structure not load-bearing for extraction (per T4 test on 5 docs); 0 false positives, 0 lost citations, +12 citations on Saint-Gobain. Rule 7.6 (footnote awareness) is now obsolete | 3 May 2026 | Gus |
| D34 | Metadata misattribution — **patch source `cases` table** (local fork, full DB ownership). Highest-priority task                                                                                                                                         | 9 Apr 2026 | Gus |
| D35 | Frontmatter year extraction — current `case_number` parsing is not good enough, must extract from doc text                                                                                                                                              | 9 Apr 2026 | Gus |
| D36 | Region misclassification (international courts → "Global South") — apply `fix_region()` to export script                                                                                                                                                | 9 Apr 2026 | Gus |
| D37 | **Agent-pipeline output goes to NEW tables** (`citation_agent_v1*`) in same DB. v7 tables frozen as methodological baseline. Fresh extraction, no retro-reclassification                                                                                | 9 Apr 2026 | Gus |

---

## Open Tasks

Tasks resulting from the decisions above, ordered by priority.

| ID  | Task                                                                                                                                                                                        | Priority | Blocking?                                 |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ----------------------------------------- |
| T1  | **Investigate metadata misattribution scope** — run the SQL in Issue 2.1, manually sample N misattributed candidates, decide whether to fix in source DB or in post-processing              | HIGHEST  | Yes — affects classification correctness  |
| T2  | **Apply `fix_region()` in `scripts/export_decisions_md.py`** + re-export the affected international-court documents                                                                         | High     | Yes — affects classification              |
| T3  | **Extract document date from doc text header** — most decisions state their date in the first ~500 chars; replace `case_number` parsing with header parsing, fallback to current logic      | High     | No (anachronism flag is soft)             |
| T4  | **Investigate `raw_text` vs `text_md` recall** — sample 5 docs (mix of sizes & footnote density), dual-extract, compare recall and noise. Decide on default text source and update exporter | High     | Partially — affects citation completeness |
| T5  | **Implement Tier 2 chunking** in `citation-extractor.md` — add progressive file output instructions for docs > 500 lines (covers 271 docs)                                                  | Medium   | Yes — for full-corpus run                 |
| T6  | **Encode D31 dismissal rule** — depends on Gus's choice of encoding (hard exclusion vs. soft tagging). Update both agents accordingly                                                       | Medium   | Yes — for full-corpus run                 |
| T7  | **Implement Tier 3 chunking** — `chunk_large_docs.py` + `merge_chunk_results.py` (covers 47 docs, 1% of corpus). Defer until T5 proves out                                                  | Low      | No — only blocks 47 docs                  |
| T8  | **Update agent rules per Section 7** — apply rule changes 7.1, 7.2, 7.3, 7.4, 7.5, 7.6 to `citation-extractor.md`, `citation-verifier.md`, and `agent-citation-extraction-rules.md`         | Medium   | Yes — for full-corpus run                 |
| T9  | **Re-run test on Saint-Gobain after T4** — confirm whether raw_text recovers the missing footnote citations                                                                                 | Low      | No                                        |

### Suggested execution order

1. **T1** (parallel investigation — DB-only, can run in background while implementing other tasks)
2. **T2** (quick — single function + re-export)
3. **T8** for rules 7.1, 7.2, 7.5 (high-priority rule changes that unblock correctness)
4. **T4** (investigation; informs T9 and any text_md → raw_text switch)
5. **T6** (after Gus picks encoding for D31)
6. **T5** (chunking, after T6 — extractor instructions consolidated in one update)
7. **T3** (year extraction — improves anachronism flag, not a blocker)
8. **T7** (Tier 3) and **T9** (re-run) — last

---

## Items Awaiting Gus's Input

*All decisions resolved. T4 completed 3 May 2026 — outcome was **A: global switch to `raw_text`**. See `docs/reports/raw-vs-md-test.md` for full data and rationale, and D33 above for the locked decision.*

---

## Cross-cutting decisions added in second review (9 Apr, late)

- **D37 — Fresh agent-extraction dataset, v7 frozen as baseline.** Same Postgres DB (`climate_litigation`), new tables `citation_agent_v1` / `citation_agent_v1_summary` / `citation_sixfold_agent_v1`. v7 tables (`citation_extraction_phased`, `citation_extraction_phased_summary`, `citation_sixfold_classification`) stay under their current names — frozen, untouched. Reasoning: v7 has 50–90% recall miss rate on test docs (Juliana 9 vs 100, ExxonMobil 7 vs 18), so retro-reclassification of corrected rules onto an under-extracted dataset would be patching a sample not the population. Fresh agent extraction with corrections baked in at extraction time gives Lucas a methodologically clean dataset and preserves v7 as a comparison baseline for the thesis methodology section. Tracked as task **T10**.
- **Rule 7.2 → boolean.** `is_vertical_dialogue: bool` added to citation output schema. Set `true` when source = national court that is a member of the cited international court (Germany→ECtHR, Colombia→IACtHR, NL→CJEU, any country→ICJ/ITLOS). Set `false` everywhere else, including international→international and foreign-international.
- **D31 encoding = soft tagging.** Allowed `functional_use` values: `aligned`, `contested`, `avoided`, `invoked` (only when court engaged), `dismissed` (mere-acknowledgement). Default analysis filters `dismissed` out, but the data is preserved for "what parties cite vs. what courts engage" gap quantification. T6 unblocked.
- **D34 fix location = source DB patch.** `cases` table will be patched directly for misattributed documents (Juliana and any others T1 surfaces). Justification: local Postgres on `:5433`, full DB ownership, fork-style workflow.

---

*This document was reviewed by Gus on 9 Apr 2026 (two review sessions). All decisions logged D29–D37. T4 (raw_text vs text_md) running in background; outcome will be appended.*
