---
type: project_context
project: phdMutley
version: "2.0"
updated: 2026-03-04
scope: "Comprehensive project status after Phase D migration and 2nd Run kickoff"
audience: ["claude-code", "human-developer", "researcher"]
related_files:
  - documentation/meetings/summary-2ndRun-1st-meeting.md
  - specs/master-plan-v2.md
  - CLAUDE.md
  - PROGRESS.md
---

# phdMutley — Project Status v2.0

## Executive Summary

PhD research project analyzing **transnational judicial citation patterns** in climate litigation. Processes 2,924 decisions from the Sabin Center's Climate Case Chart to quantify North-South citation asymmetries. Key finding from v1.0: **96% Global North, 4% Global South** (29:1 ratio).

**Current phase:** Pipeline v2.0 preparation — methodology revision based on lessons from v1.0 and a corporate-cases side project. Railway hosting decommissioned in favor of static GitHub Pages deployment.

---

## 1. Architecture (post-Phase D, March 2026)

### Hosting
- **Railway decommissioned.** No more Flask API or gunicorn.
- **GitHub Pages** serves the dashboard as a static site from `docs/` on `main`.
- `scripts/export_static_site.py` generates all JSON data files for the dashboard.

### Canonical Code Locations

| Component | Location | Notes |
|-----------|----------|-------|
| Analysis engine | `scripts/8-python_back_engine/sixfold_analysis_engine.py` | Formerly in `railway/` |
| Sixfold classification | `scripts/8-python_back_engine/classify_decisions_sixfold.py` | Formerly in `railway/` |
| Pipeline config | `scripts/config.py` | Pydantic Settings, `_DictBridge` mixin |
| Secrets | `scripts/gcp_secrets.py` | GCP Secret Manager + Docker secrets |
| Gemini client | `scripts/gemini_client.py` | Singleton, retry, JSON parsing |
| Static site export | `scripts/export_static_site.py` | Runs engine + custom SQL → `docs/data/` |
| Dashboard | `docs/index.html` | Single HTML, inline JS/CSS, D3.js |
| Dashboard data | `docs/data/*.json` | Pre-computed, committed to git |
| Docker setup | `docker/` | db + pipeline + export services |
| Dependencies | `requirements.txt` (root) | No Flask/gunicorn |

### Pipeline Scripts (Phases 0-5)

| Phase | Script | What It Does |
|-------|--------|--------------|
| 0 | `scripts/0-initialize-database/init_database.py` | Schema creation. Flags: `--reset`, `--info`, `--quiet` |
| 1 | `scripts/1-download-decisions/download_decisions.py` | Async PDF download (aiohttp). Uses TRIAL_BATCH_CONFIG |
| 2 | `scripts/2-populate-metadata/populate_metadata.py` | Excel → PostgreSQL (cases + documents tables) |
| 3 | `scripts/3-extract-texts/extract_texts.py` | PDF → text. 3-tier: pdfplumber → PyMuPDF → PyPDF2 |
| 4 | `scripts/4-classify-decisions/classify_decisions.py` | Decision vs non-decision. Title heuristic → Gemini fallback |
| 5 | `scripts/5-extract-citations/extract_citations.py` | 4-phase citation extraction (v5.3). The critical phase. |
| 8 | `scripts/8-python_back_engine/sixfold_analysis_engine.py` | 9 query sections → network data + dashboard aggregates |

### Test/Filter Mechanism

- **TRIAL_BATCH_CONFIG** — Active across Phases 1-5. Filters to rows with "Trial batch" = TRUE in Excel.
- **TEST_CONFIG** — Defined (`enabled`, `limit`, `strategy`) but **orphaned** — never imported by any pipeline script.
- **No CLI `--test` or `--limit` flags** in any script. Configuration requires editing `config.py`.

---

## 2. Completed Phases (chronological)

| Phase | Date | Scope |
|-------|------|-------|
| v1.0 (1st Run) | Nov 2025 | Full pipeline: download, extract, classify, citation extraction, sixfold analysis. 2,924 decisions processed. Deployed on Railway. |
| Phase A | Mar 2026 | Data integrity fixes: duplicate columns, hardcoded paths, bare excepts, classification + dictionary tests |
| Phase B | Mar 2026 | Gemini LLM migration: all Anthropic SDK calls → google-genai |
| Phase B+ | Mar 2026 | Reproducibility: ruff linting, centralized DB URL, Pydantic config, pinned deps, pipeline models, Alembic migrations |
| Phase C | Mar 2026 | Docker integration: Dockerfile, docker-compose (db/api/pipeline), run-pipeline.sh, Docker secrets |
| Phase D | Mar 2026 | Railway → GitHub Pages: `railway/` deleted, static site at `docs/`, export script, Docker updated |

---

## 3. v2.0 Context — Meeting Decisions (3 March 2026)

### Deliverable
**For Joana & Kate's Global Trends Report (deadline: 9 March 2026):**
- Static map: top-5 jurisdictions citing foreign case law (where they cite + where they're cited)
- Aesthetic map: US is cited but rarely cites others
- 2-3 paragraphs: descriptions + reflection on US position + LLM methodology note

### Key Methodology Changes for v2.0

1. **Sabin-only filter (D1):** Only retain citations that match cases in the Sabin/Climate Case Chart database. Eliminates noise (e.g., Australia citing 1330 UK common law).

2. **Build Knowledge step (D6):** Before citation extraction, construct a knowledge base from the Columbia/Sabin database: case name, year, parties, description. Dramatically improved recall in the corporate-cases side project.

3. **Use Sabin IDs (D4):** Use existing Case ID and Document ID from the Sabin database. No custom IDs needed.

4. **Markdown extraction (D3):** Convert extracted texts to Markdown format instead of plain text. Better LLM processing.

5. **Gemini as primary LLM (D2):** Gemini 3.1 Pro matches/exceeds Claude 4.6 on benchmarks. Cheaper. Lucas has credits.

6. **Selective reclassification (D5):** Don't reclassify Sabin metadata wholesale. Only fix what's strictly needed.

7. **Snippets after filter (D7):** Extract exact citation snippets only for citations that survive the Sabin filter. Character-count bookmarking for anchoring.

8. **Error margin disclaimer (D10):** Include transparency about processing limitations and scope constraints.

### Revised Pipeline Architecture (v2.0)

```
Phase 0: Database Init (add Case ID / Document ID columns)
Phase 1: Download (updated Columbia Excel + PDFs)
Phase 2: Text Extraction → Markdown format
Phase 3: LLM Analysis (THE critical phase)
  ├── Task 1: Identify ALL jurisprudential citations
  ├── Task 2: Filter → is this a Sabin case? (YES → keep, NO → discard)
  ├── Task 3: Compare source jurisdiction vs cited jurisdiction
  └── Output: Validation table (Excel)
Phase 4: Export & Results (counts, top-5, static map, text)
```

### Preliminary Data (v1.0, to be updated)
- Top-5 citing: Australia, New Zealand, UK, Brazil, Canada
- **Australia data suspect** — dominated by ancient UK common law citations
- Expected to change significantly with Sabin-only filter

---

## 4. Data Sources

| Source | Description | Status |
|--------|-------------|--------|
| Sabin Center Climate Case Chart | Primary database of climate litigation cases | Need updated Excel from Lucas |
| Columbia Law School DB | Extended metadata (year, parties, description) for knowledge base | Available via Sabin Excel |
| Downloaded PDFs | 2,924 decision documents | Already downloaded (v1.0) |
| PostgreSQL (local) | `climate_litigation` DB, user `phdmutley` | Active, contains v1.0 data |

---

## 5. Budget & Cost Constraints

- **Total budget:** < $200 API costs
- **Per-document target:** < $0.10
- **v1.0 actual:** ~$0.003/doc for extraction (Gemini 2.5 Flash-Lite)
- **Cost strategy:** Minimize input tokens (biggest cost), combine analysis questions per document pass, use dictionary lookups before LLM calls

---

## 6. Team

| Person | Role | Focus |
|--------|------|-------|
| Gustavo Rodriguez | Technical Lead | Pipeline dev, LLM prompts, infrastructure |
| Lucas Biasetton | PhD Researcher | Methodology, validation, text writing, map design |
| Joana / Kate | Supervisors (Columbia) | Global Trends report, methodology article advocacy |

---

## 7. Upcoming

- **Trial run:** 100 random decision-documents through the full v2.0 pipeline
- **Methodology article:** Columbia Junior Scholars (deadline 15 March, early draft)
- **GitHub Pages activation:** Enable in repo settings after first export
- **Parquet/DuckDB export:** Archival format for committee sharing
