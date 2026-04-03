---
type: meeting_summary
project: phdMutley
meeting_id: 2ndRun-meeting-01
title: "Pipeline v2.0 Kickoff — Methodology Revision & Joana Deliverable"
date: 2026-03-03
duration_minutes: 101
participants:
  - name: Gustavo Rodriguez
    role: Technical Lead / Pipeline Developer
    email: gustavo.rodriguez@kria.vc
  - name: Lucas Biasetton
    role: Researcher / PhD Candidate
    email: lucasbiasetton@gmail.com
deliverable_deadline: 2026-03-09
status: planning_complete
source_files:
  - documentation/meetings/transcript-2ndRun-1st-meeting.md
  - documentation/meetings/notion_summary-2ndRun-1st-meeting.md
tags:
  - methodology
  - pipeline-v2
  - sabin-center
  - citation-extraction
  - gemini
  - deliverable
  - global-trends-report
---

# Meeting Summary — 2nd Run, 1st Meeting

**Date:** 3 March 2026 | **Duration:** ~1h41m | **Participants:** Gustavo Rodriguez, Lucas Biasetton

---

## 1. Goal Statement

Produce a **static map** showing foreign citation patterns between jurisdictions in climate litigation, plus **2-3 paragraphs** of descriptive/reflective text, for Joana and Kate's Global Trends report. **Deadline: 9 March 2026.** Secondary goal: refine the pipeline methodology for a potential methodology article submission (Columbia Junior Scholars, deadline 15 March).

### Joana's Deliverable (verbatim from email)

1. High-resolution static maps for the **top 5 jurisdictions** that cite foreign case law — showing both where they cite and where they are cited.
2. An "aesthetic version" of the map highlighting that **the US is regularly cited but almost never cites anyone else.**
3. Short text: (a) descriptions of the maps starting with the country with the highest foreign citations, (b) short reflection on US standing apart from the global phenomenon, (c) explanation that figures were generated using LLM trained on Sabin Center data, with link to the dashboard.
4. Deadline: end of March (for edits), incorporation into draft report.

**Agreed scope for 9 March:** Items 1 and 2 only. Dashboard link deferred.

---

## 2. Key Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | **Limit citations to Sabin/Climate Case Chart cases only** | Australia data showed citations to 1330 UK common law decisions — noise from non-climate cases makes data unreliable without this filter. |
| D2 | **Use Gemini (not Anthropic)** as the LLM | Gemini 3.1 Pro matches/exceeds Claude 4.6 on benchmarks, is cheaper, and Lucas has existing credits. |
| D3 | **Convert extracted texts to Markdown** | MD is better optimized for LLM processing than plain text stored in the DB. |
| D4 | **Use existing Sabin Center IDs** (Case ID + Document ID) | No need to create custom IDs — the Sabin database already provides both. |
| D5 | **Do NOT reclassify Sabin metadata wholesale** | Too expensive and time-consuming. Only reclassify what is strictly necessary for the deliverable. Trust Sabin's climate-case scope. |
| D6 | **Add "build knowledge" step** before citation extraction | Learned from Lucas's corporate-cases project: providing contextual info (year, parties, description) from Columbia DB dramatically improved citation recall. |
| D7 | **Snippets only for kept citations** | Extract exact snippets only after filtering — don't waste LLM tokens on citations that will be discarded. Use character-count bookmarking for anchoring. |
| D8 | **Gustavo handles all pipeline work** | Pipeline is highly iterative and each step depends on the previous. Dividing would create more review overhead than it saves. |
| D9 | **Top-5 format preferred over raw numbers** | Both are more comfortable presenting ranked jurisdictions than absolute counts, given known data imperfections. Include disclaimer about margin of error. |
| D10 | **Include error margin disclaimer** | Publication quality demands transparency about LLM processing limitations and Sabin scope constraints. |

---

## 3. Pipeline v2.0 — Revised Architecture

### Phase 0: Database Initialization
- Add Case ID and Document ID columns to tables
- Adapt downstream scripts to propagate IDs

### Phase 1: Download & Preparation
- Acquire **updated Columbia/Sabin Excel** (latest cases)
- Download PDFs (existing script, no changes)

### Phase 2: Text Extraction
- New script: extract to **Markdown format** (replacing plain text in DB)
- Better structure for LLM consumption

### Phase 3: LLM Analysis (the critical phase)
Three tasks within this phase:

| Task | Description |
|------|-------------|
| **Task 1** | Identify ALL jurisprudential citations in each document |
| **Task 2** | Filter: is this citation a Sabin Center case? If NO → discard. If YES → extract origin metadata (country, court) from the Sabin table itself. |
| **Task 3** | Compare source document jurisdiction with cited case jurisdiction → classify as foreign/domestic citation. Generate validation table (Excel). |

### Phase 4: Export & Results
- Count citations per country
- Identify top-5 citing and top-5 cited jurisdictions
- Generate static map
- Produce text for Joana

### Deferred / Optional Steps
- Summarization & indexing of documents (knowledge base enrichment)
- Country/decision reclassification from Sabin metadata (only if strictly needed)
- Snippet extraction via character-count anchoring for validation
- Dashboard link for the report

---

## 4. Process & Progress Commentary

### Motivation for the Rerun
Lucas applied the v1.0 methodology to a side project (corporate climate cases for Joana/Kate) and found **significant citation recall failures** — the model was missing many citations. This triggered the methodology review.

### Data Quality Concerns
- **Australia anomaly:** Appeared as #1 citing jurisdiction, but most citations were to ancient UK common law (1330, 1466, 1600s) — completely outside climate litigation scope.
- **Sabin metadata errors:** Document type, document year, and summary fields had manual classification errors. Team decided to work around this rather than attempt full correction.
- **Preliminary top-5:** Australia, New Zealand, UK, Brazil, Canada (from v1.0 data — expected to change with v2.0).

### Technical Insights
- **Knowledge base approach** (from Lucas's corporate-cases project): feeding the LLM contextual info about target cases (year, parties, description from Columbia DB) dramatically improved citation capture vs. just using case names.
- **Gemini's self-assessment:** When Lucas explored using reference dictionaries for citation formats, Gemini argued it was unnecessary — the model is capable of recognizing legal citations natively. This worked in the smaller project (~25 cases) but needs validation at scale (~2,000 cases).
- **Context window limitation:** The knowledge base for ~2,000 Sabin cases won't fit in a single context window. Solution: batch processing with indexed knowledge base for efficient retrieval.
- **Token cost optimization:** The biggest cost is input tokens (reading documents). Multiple analysis questions can be answered in a single pass to minimize re-reading.

### Aegis Learnings Applied
Gustavo referenced improvements from the Aegis project:
- Sub-agent architecture with scoped context
- Indexed documentation with navigation indices
- Progress tracking in database (not just markdown)
- Structured entity cataloguing (cases → decisions → citations → countries)

---

## 5. Division of Labor

| Person | Responsibilities |
|--------|-----------------|
| **Gustavo** | All pipeline development and execution (Phases 0-3). Pipeline refinement, algorithm design, LLM prompt engineering, data processing, validation infrastructure. |
| **Lucas** | Text writing for the deliverable. Map presentation design (colors, aesthetics). Validation of results. Domain expertise for methodology decisions. Acquire updated Columbia Excel. |

---

## 6. Communication Plan

| Channel | Purpose |
|---------|---------|
| **Daily morning sync** | Quick alignment, status update, validate direction |
| **End-of-day review** | Assess progress, review outputs |
| **Open Discord/Teams channel** | Always-on during work hours. Lucas stays online when not in meetings. No formal scheduling needed — just jump in. |

**Start:** Next morning (4 March 2026). Lucas creates the room.

---

## 7. Potential Article Submission

- **Venue:** Columbia Junior Scholars call for papers
- **Deadline:** 15 March 2026 (early draft / idea submission)
- **Scope:** Methodology article on LLM-assisted citation extraction in climate litigation
- **Authors:** Lucas, Gustavo, potentially Joana and Kate
- **Status:** Aspirational — depends on pipeline refinement quality. Not blocking the Joana deliverable.

---

## 8. Open Questions / Risks

| # | Item | Status |
|---|------|--------|
| Q1 | Exact token budget for the full pipeline run | Needs estimation — tokens are predictable but total volume uncertain |
| Q2 | Whether Gemini can handle ~2,000 case knowledge base in batches effectively | Validated at 25-case scale, not yet at full scale |
| Q3 | Which Sabin metadata fields need reclassification (if any) | Deferred — only address if blocking |
| Q4 | Optimal batching strategy for LLM processing | To be designed during implementation |
| Q5 | Margin of error methodology for the disclaimer | To be defined in final days of sprint |
| Q6 | RAM upgrade for Gustavo's laptop (8GB → 16-20GB) | Planned this week — current hardware is a bottleneck |

---

## 9. Action Items

| # | Owner | Action | Deadline |
|---|-------|--------|----------|
| A1 | Lucas | Acquire updated Columbia/Sabin Excel with latest cases | ASAP |
| A2 | Gustavo | Pipeline v2.0 development and execution (all phases) | 8 Mar |
| A3 | Lucas | Develop map presentation (text, colors, aesthetics) | 8 Mar |
| A4 | Lucas | Write descriptive/reflective paragraphs (pending data) | 9 Mar |
| A5 | Both | Daily touchpoints (morning sync + end-of-day review) | Ongoing |
| A6 | Lucas | Create Discord/Teams room for always-on communication | 4 Mar AM |
| A7 | Gustavo | Estimate token costs for full pipeline run | 4-5 Mar |
| A8 | Both | Consider Columbia Junior Scholars submission (15 Mar deadline) | 10 Mar |
