---
type: master_plan
project: phdMutley
version: "2.0"
created: 2026-03-04
updated: 2026-03-04
scope: "Full pipeline v2.0 implementation — from meeting decisions to deliverable"
deliverable_deadline: 2026-03-09
article_deadline: 2026-03-15
audience: ["claude-code", "human-developer"]
dependencies:
  - documentation/meetings/summary-2ndRun-1st-meeting.md
  - documentation/specs-context/PROJECT_STATUS_v2.md
tags:
  - pipeline-v2
  - implementation
  - methodology
---

# Master Plan v2.0 — Pipeline Reimplementation

## Overview

Implements the 10 key decisions (D1–D10) from the 3 March 2026 meeting. Each phase begins with a **planning step** (Claude Code plan mode) before any code is written. The final deliverable for Joana/Kate is due **9 March 2026**.

**Trial run:** After all phases are implemented, execute a trial run with 100 random decision-documents through the full v2.0 pipeline. This validates methodology before full-scale execution.

**Prerequisite:** Lucas provides updated Columbia/Sabin Excel (Action A1).

---

## Phase 1: Database Schema Evolution

**Decisions implemented:** D4 (Sabin IDs)
**Estimated effort:** 1 session

### Planning Step
- Inspect current schema (`cases`, `documents`, `extracted_text`, `citation_extraction_phased`)
- Map Sabin Excel columns → DB columns (Case ID, Document ID)
- Determine Alembic migration strategy vs. `init_database.py` modification
- Identify downstream scripts that need ID propagation

### Implementation Tasks
1. Add `sabin_case_id` and `sabin_document_id` columns to `cases` and `documents` tables
2. Create Alembic migration for the schema change
3. Update `init_database.py` Phase 0 to include new columns
4. Update `populate_metadata.py` (Phase 2) to read and store Sabin IDs from Excel
5. Propagate Sabin IDs through downstream joins (citation tables, classification)

### Acceptance Criteria
- [ ] New columns exist with proper types and indices
- [ ] `populate_metadata.py` populates Sabin IDs from Excel
- [ ] Downstream queries can join on Sabin IDs
- [ ] Alembic migration applies cleanly

---

## Phase 2: Seed Data & Download Pipeline Update

**Decisions implemented:** D4 (Sabin IDs), prerequisite for all others
**Estimated effort:** 1 session
**Blocked by:** Updated Columbia/Sabin Excel from Lucas (A1)

### Planning Step
- Inspect the new Excel file structure (column names, row count, ID format)
- Compare with v1.0 Excel to identify schema differences
- Plan `--test-run N` CLI flag for random sampling across all pipeline scripts
- Design the random sampling mechanism (reproducible seed for academic rigor)

### Implementation Tasks
1. Add `--test-run N` CLI flag to `download_decisions.py` — randomly samples N documents
2. Add same flag to all Phase 2–5 scripts for consistent filtering
3. Update `config.py` with `TestRunSettings` (enabled, sample_size, random_seed)
4. Adapt `populate_metadata.py` for new Excel column names/structure
5. Verify PDF download works for sampled documents

### Acceptance Criteria
- [ ] `--test-run 100` flag works across all pipeline scripts
- [ ] Random sampling uses a fixed seed (reproducibility)
- [ ] New Excel loads without errors
- [ ] 100 documents download successfully in test mode

---

## Phase 3: Markdown Text Extraction

**Decisions implemented:** D3 (Markdown extraction)
**Estimated effort:** 1 session

### Planning Step
- Evaluate Markdown conversion libraries (markdownify, pdfplumber + custom, pymupdf4llm)
- Decide on storage: new `extracted_text_md` column vs. replace `extracted_text` content
- Benchmark extraction quality on 5–10 sample PDFs
- Define quality metrics (structure preservation, heading detection, table handling)

### Implementation Tasks
1. Choose and integrate Markdown conversion library
2. Modify `extract_texts.py` (Phase 3) to output Markdown instead of plain text
3. Store Markdown in `extracted_text` table (new column `text_md` alongside existing `text_content`)
4. Add `--format markdown|plain` flag (default: markdown for v2.0)
5. Validate on sample set: legal headings, paragraphs, footnotes preserved

### Acceptance Criteria
- [ ] Extracted Markdown preserves document structure (headings, lists, paragraphs)
- [ ] Legal citation patterns remain intact (not mangled by Markdown formatting)
- [ ] Storage column added without breaking existing queries
- [ ] 3-tier extraction hierarchy (pdfplumber → PyMuPDF → PyPDF2) still works

---

## Phase 4: Knowledge Base Construction

**Decisions implemented:** D6 (Build Knowledge step)
**Estimated effort:** 1–2 sessions
**Critical path:** This is the key innovation from Lucas's corporate-cases project

### Planning Step
- Define knowledge base schema: what fields per case (name, year, parties, description, jurisdiction, court)
- Source: Sabin Excel metadata + Columbia DB fields
- Design batching strategy for ~2,000 cases (context window limitation)
- Decide storage: JSON file, SQLite table, or in-memory dict
- Plan indexing for efficient retrieval during LLM analysis

### Implementation Tasks
1. Create `scripts/build_knowledge_base.py` — extracts case metadata from DB/Excel
2. Structure as searchable index: case name → {year, parties, description, jurisdiction, Sabin ID}
3. Implement batching: split knowledge base into chunks that fit context window
4. Create retrieval function: given a potential citation, find matching Sabin cases
5. Export knowledge base as JSON for inspection/validation

### Acceptance Criteria
- [ ] Knowledge base covers all ~2,000+ Sabin cases with decision documents
- [ ] Each entry has: case name, year, parties (when available), jurisdiction, Sabin ID
- [ ] Batch retrieval returns relevant candidates for a given citation text
- [ ] JSON export is human-readable for Lucas's validation

---

## Phase 5: Citation Extraction v6 — Sabin-Filtered

**Decisions implemented:** D1 (Sabin-only filter), D6 (Knowledge base), D7 (Snippets after filter)
**Estimated effort:** 2–3 sessions
**Critical path:** THE most important phase — determines data quality

### Planning Step
- Review v5.3 extraction pipeline architecture (4-phase)
- Design v6 pipeline integrating knowledge base and Sabin filter
- Plan LLM prompt for Task 1 (identify all citations) with knowledge base context
- Design Task 2 (Sabin filter) — matching algorithm: fuzzy case name + year + jurisdiction
- Design Task 3 (jurisdiction comparison) — reuse sixfold classification logic
- Cost estimation: tokens per document × number of documents × price per token

### Implementation Tasks

#### Task 1: Citation Identification
1. Modify extraction prompt to include knowledge base context (batched)
2. Ask LLM: "Identify ALL jurisprudential citations in this document"
3. Return structured list: {cited_text, potential_case_name, potential_year, confidence}

#### Task 2: Sabin Filter
4. For each identified citation, check against knowledge base: is this a Sabin case?
5. Matching strategy: exact name → fuzzy name + year → LLM confirmation
6. If YES → keep, extract Sabin ID and origin metadata from DB (not from LLM)
7. If NO → discard (log for audit trail)

#### Task 3: Classification & Snippets
8. Compare source document jurisdiction vs. cited case jurisdiction
9. Apply sixfold classification (reuse existing logic from `classify_decisions_sixfold.py`)
10. For kept citations only (D7): extract exact text snippet with character-count anchoring
11. Generate validation table (Excel) for Lucas review

### Acceptance Criteria
- [ ] Citations filtered to Sabin-only cases (D1)
- [ ] Knowledge base improves recall vs. v5.3 (D6)
- [ ] Snippets extracted only for kept citations (D7)
- [ ] Validation Excel generated with: source doc, cited case, Sabin ID, snippet, confidence
- [ ] Cost per document remains < $0.10

---

## Phase 6: Analysis Engine v2 & Static Export

**Decisions implemented:** D9 (Top-5 format), D10 (Error margin disclaimer)
**Estimated effort:** 1 session

### Planning Step
- Review `sixfold_analysis_engine.py` queries — which need updating for v2.0 schema?
- Design top-5 output format for the deliverable
- Plan static map generation (what library? matplotlib basemap, geopandas, or D3.js?)
- Draft error margin disclaimer text with Lucas

### Implementation Tasks
1. Update analysis engine queries for v2.0 citation data (Sabin-filtered)
2. Add top-5 citing and top-5 cited jurisdiction queries
3. Update `export_static_site.py` for new data format
4. Generate high-resolution static map (top-5 jurisdictions, citation flows)
5. Generate "aesthetic" US map (cited but rarely cites)
6. Add error margin disclaimer to dashboard and export

### Acceptance Criteria
- [ ] Top-5 jurisdictions computed from Sabin-filtered data
- [ ] Static maps generated at publication quality
- [ ] Error disclaimer included in all outputs
- [ ] Dashboard updated with v2.0 data
- [ ] `docs/data/` JSON files regenerated

---

## Phase 7: Trial Run (100 Documents)

**Validates:** All phases above
**Estimated effort:** 1 session (execution) + review time

### Planning Step
- Select 100 random documents (fixed seed for reproducibility)
- Prepare validation checklist for Lucas
- Set up cost monitoring (token usage tracking)

### Execution Tasks
1. Run `--test-run 100` through full pipeline (Phases 0–5, then Phase 6 export)
2. Monitor: cost per document, error rate, processing time
3. Generate validation Excel for Lucas review
4. Compare v2.0 results with v1.0 for same 100 documents (if overlap exists)
5. Document: total cost, processing time, error count, edge cases

### Success Criteria
- [ ] 100 documents processed end-to-end without fatal errors
- [ ] Cost per document < $0.10
- [ ] Validation Excel shows plausible citation patterns
- [ ] Lucas validates sample of results (spot-check ~20 documents)
- [ ] Australia anomaly is resolved (no ancient common law citations)

---

## Phase 8: Full Run & Deliverable Production

**Blocked by:** Phase 7 validation + Lucas approval
**Estimated effort:** 1–2 sessions (mostly waiting for LLM processing)

### Tasks
1. Execute full pipeline on all ~2,000+ decision-documents
2. Generate final static maps for Joana
3. Lucas writes 2–3 descriptive paragraphs
4. Package deliverable (maps + text) by 9 March deadline

---

## Execution Timeline

| Day | Phase | Deliverable |
|-----|-------|-------------|
| 4 Mar (today) | Phase 1 (DB schema) + Phase 2 (seed data) | Schema ready, Excel loaded |
| 4–5 Mar | Phase 3 (Markdown) + Phase 4 (Knowledge base) | Extraction + KB ready |
| 5–6 Mar | Phase 5 (Citation extraction v6) | Core pipeline complete |
| 6–7 Mar | Phase 6 (Analysis + export) + Phase 7 (Trial run) | 100-doc validation |
| 7–8 Mar | Phase 7 review + Phase 8 (Full run) | Complete data |
| 8–9 Mar | Phase 8 (Maps + text) | Deliverable to Joana |

---

## Dependencies Graph

```
Phase 1 (DB Schema) ──┐
                       ├── Phase 2 (Seed Data) ── Phase 3 (Markdown) ──┐
Excel from Lucas ──────┘                                                │
                                                                        ├── Phase 5 (Citation v6)
                                                Phase 4 (Knowledge) ────┘         │
                                                                                  │
                                                                          Phase 6 (Analysis)
                                                                                  │
                                                                          Phase 7 (Trial Run)
                                                                                  │
                                                                          Phase 8 (Full Run)
```

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Excel from Lucas delayed | Blocks Phase 2+ | Start Phase 1 (schema) and Phase 3 (Markdown extraction from existing data) while waiting |
| Gemini context window insufficient for knowledge base batches | Reduced recall | Pre-filter knowledge base by jurisdiction before each batch |
| Citation extraction cost exceeds budget | Budget overrun | Monitor cost per doc in trial run; abort and adjust if >$0.10/doc |
| Trial run reveals fundamental methodology issues | Timeline slip | Budget 1 day for methodology adjustment before full run |
| RAM limitation (8GB) causes processing failures | Slow/crash | Process in smaller batches; prioritize RAM upgrade (Q6) |

---

## Decisions Log

| ID | Decision | Source | Status |
|----|----------|--------|--------|
| D1 | Sabin-only citation filter | Meeting 3 Mar | Pending (Phase 5) |
| D2 | Gemini as primary LLM | Meeting 3 Mar | Done (Phase B) |
| D3 | Markdown text extraction | Meeting 3 Mar | Pending (Phase 3) |
| D4 | Use Sabin Case/Document IDs | Meeting 3 Mar | Pending (Phase 1) |
| D5 | No wholesale reclassification | Meeting 3 Mar | Policy — no action needed |
| D6 | Build Knowledge step | Meeting 3 Mar | Pending (Phase 4) |
| D7 | Snippets after filter only | Meeting 3 Mar | Pending (Phase 5) |
| D8 | Gustavo handles all pipeline | Meeting 3 Mar | Active |
| D9 | Top-5 format for deliverable | Meeting 3 Mar | Pending (Phase 6) |
| D10 | Error margin disclaimer | Meeting 3 Mar | Pending (Phase 6) |
| D11 | Test run: 100 random docs | Session 4 Mar | Pending (Phase 7) |
