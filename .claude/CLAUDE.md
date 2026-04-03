# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**PhD Climate Litigation Citation Analysis** — doctoral research analyzing citation patterns between Global North and Global South courts in climate litigation decisions. Processes 2,924 judicial decisions from the Climate Case Chart database to quantify transnational judicial dialogue and North-South citation asymmetries.

**Stack:** PostgreSQL 18 · Python 3.14 · HTML/JS dashboard (D3.js) · Google Gemini API (`google-genai` SDK) · GitHub Pages static hosting

**Status:** Analysis complete for thesis (migrated from Railway to static site, Mar 2026). Budget constraint: <$200 total API costs, <$0.10/document.

## Development Environment

```bash
# Activate venv (required before any Python command)
source venv/bin/activate    # or: ./activate.sh

# Local database: PostgreSQL 18 NATIVE (Windows service) on localhost:5433, db=climate_litigation, user=phdmutley
# Port 5433 to avoid conflict with Aegis's Docker PostgreSQL on 5432
# Credentials via GCP Secret Manager (DB password, Gemini API key)
```

## Common Commands

```bash
# Run analysis engine
cd scripts/8-python_back_engine && python sixfold_analysis_engine.py

# Export static site data (runs engine + generates docs/data/ JSON files)
python scripts/export_static_site.py

# Preview dashboard locally
cd docs && python -m http.server 8080

# Database (native PG on port 5433)
psql -U phdmutley -p 5433 -d climate_litigation                                    # interactive shell
pg_dump -U phdmutley -p 5433 -d climate_litigation > backup_$(date +%Y%m%d).dump   # backup

# Pipeline phases (run in sequence, each from project root)
cd scripts/0-initialize-database && python init_database.py     # schema creation
cd scripts/1-download-decisions && python download_decisions.py  # PDF download
cd scripts/2-populate-metadata && python populate_metadata.py    # Excel → DB
cd scripts/3-extract-texts && python extract_texts.py            # PDF text extraction
cd scripts/4-classify-decisions && python classify_decisions.py  # judicial vs other
cd scripts/5-extract-citations && python extract_citations.py    # citation extraction v5
# Phase 6-7: SQL files run manually via psql
cd scripts/8-python_back_engine && python sixfold_analysis_engine.py  # analysis engine

# Export
cd scripts && python export_to_excel.py
```

## Architecture

### Key Modules

| File | Role |
|------|------|
| `scripts/8-python_back_engine/sixfold_analysis_engine.py` | Core analysis: 9 query sections, network data for D3.js, dashboard aggregates → `first_analysis` table. |
| `scripts/8-python_back_engine/classify_decisions_sixfold.py` | Sixfold classification logic (imported by analysis engine). |
| `scripts/export_static_site.py` | Runs analysis engine + exports all JSON data to `docs/data/` for static site. |
| `docs/index.html` | Single-file dashboard (inline JS/CSS, D3.js visualizations). Loads static JSON from `docs/data/`. |
| `scripts/config.py` | **Single source of truth** for all pipeline config: DB credentials, API keys, model IDs, jurisdiction mappings, trial batch / test mode toggles. |

### Configuration (`scripts/config.py`)

```python
from config import CONFIG, DB_CONFIG, TRIAL_BATCH_CONFIG, TEST_CONFIG

# Models (Gemini via google-genai SDK, thinking enabled)
# gemini-2.5-flash: extraction + verification (w/ thinking_budget=1024)
# gemini-2.5-pro: classification & origin ID (w/ thinking_budget=1024-2048)

# Test mode: limits processing to first N rows
TEST_CONFIG = { 'ENABLED': True, 'LIMIT': 50, 'STRATEGY': 'first' }

# Trial batch: filters to Excel-marked documents
TRIAL_BATCH_CONFIG = { 'ENABLED': True, 'COLUMN_NAME': 'Trial batch', ... }
```

### Database Schema

Core tables (all use **UUIDv7 primary keys**):

| Table | Purpose |
|-------|---------|
| `cases` | Case metadata (2,924 records) |
| `documents` | Individual document records |
| `extracted_text` | PDF text extraction results |
| `citation_extraction_phased` | Individual citations (v5 schema) |
| `citation_extraction_phased_summary` | Document-level citation stats |
| `citation_sixfold_classification` | Sixfold classified citations |
| `first_analysis` | Analysis query results (engine output) |

Schema conventions: UUIDv7 PKs, FK with CASCADE, `created_at`/`updated_at` timestamps, COMMENT ON for documentation.

### Citation Extraction v7 Pipeline

6-phase pipeline with anti-hallucination hardening:

0. **Quality Pre-check** — Skip garbled/corrupted documents ($0)
1. **Source Jurisdiction ID** — Database lookup ($0)
2. **Extraction** — Gemini 2.5 Flash (thinking=1024), 12 citation format patterns, NO KB in prompt + hard filters (pipe-format, anachronism)
3. **Origin ID** — Tier 1: dictionary (80+ courts, $0) → Tier 2: Gemini 2.5 Pro (thinking=1024) → Tier 3: web search (future)
4. **Classification** — Rule-based sixfold classification ($0)
5. **Inline Verification** — Gemini 2.5 Flash (thinking=1024) verifies each citation against source text, fuzzy snippet matching

Quality: confidence scoring 0.0-1.0, auto-flag <0.7, manual review workflow.

Documentation: `scripts/5-extract-citations/citation_extraction_pipeline/` (INDEX_v5.md, QUICK_REFERENCE_v5.md, full implementation guide).

## Research Context

### Sixfold Classification System

| # | Type | Direction |
|---|------|-----------|
| 1 | Foreign Citation | National → National |
| 2 | International Citation | National → Int'l member court |
| 3 | Foreign International Citation | National → Int'l non-member |
| 4 | Inter-System Citation | Int'l → Int'l |
| 5 | Member-State Citation | Int'l → National member |
| 6 | Non-Member Citation | Int'l → National non-member |

**Key finding:** 96% Global North, 4% Global South (29:1 ratio). Research quantifies transnational legal transplantation and citation asymmetries.

Binding court jurisdiction mappings (IACtHR, ECtHR, ACHPR with country lists) are defined in `scripts/config.py`.

## Development Conventions

### Docstring Format

```python
def function_name(param1: Type1, param2: Type2) -> ReturnType:
    """
    Brief description.

    INPUT:
        - param1: Description
        - param2: Description
    ALGORITHM:
        1. Step one
        2. Step two
    OUTPUT: Description of return value
    """
```

### Error Handling Pattern

All pipeline scripts: try/commit/log success → except specific/rollback → except general/rollback with traceback. Track stats dict (`processed`, `errors`, `specific_errors`).

### Logging

```python
logging.info("="*70)           # section separator
logging.info("SECTION TITLE")  # section header
logging.info(f"✓ Success: {v}")
logging.warning("⚠️  Warning")
logging.error("❌ Error")
```

### LLM API Usage

- `temperature=0.0` always (reproducibility for academic research)
- Gemini 2.5 Flash for extraction + verification, Gemini 2.5 Pro for classification/origin ID
- Thinking enabled via `thinking_budget` parameter (1024-2048 tokens)
- Shared client helper: `scripts/gemini_client.py` (singleton client, retry logic, JSON parsing, thinking support)
- Track token usage for cost reporting
- JSON parsing with fallback extraction
- Retry logic for API failures

### PDF Extraction Hierarchy

1. `pdfplumber` (94.1% success rate, preferred)
2. `PyMuPDF` fallback
3. `PyPDF2` last resort
4. OCR (tesseract) only if all above fail

## GitHub Pages

The dashboard is a static site served from `docs/` on the `main` branch. To update:

1. Run `python scripts/export_static_site.py` (requires local PostgreSQL)
2. Commit changes to `docs/data/`
3. Push to `main` — GitHub Pages auto-deploys

Enable in repo settings: Settings → Pages → Source: "Deploy from a branch" → Branch: `main`, folder: `/docs`

Dependencies: `requirements.txt` at project root (SQLAlchemy, pandas, google-genai — no Flask/gunicorn).

## Database Setup (Native PostgreSQL)

PostgreSQL 18 runs as a native Windows service on port **5433** (not Docker).
Port 5433 avoids conflict with Aegis's Docker PostgreSQL on 5432.

```bash
# Service management (Windows)
# Auto-starts on boot as "postgresql-x64-18" service

# Connection
psql -U phdmutley -p 5433 -d climate_litigation

# Backup
pg_dump -U phdmutley -p 5433 -d climate_litigation -Fc > backup.dump

# Restore
pg_restore -U phdmutley -h 127.0.0.1 -p 5433 -d climate_litigation --no-owner backup.dump
```

Docker is not used for this project. The `docker/` directory was removed on 5 Mar 2026. All infrastructure is native PostgreSQL + GitHub Pages static site.

## Troubleshooting

```bash
# DB connection test
psql -U phdmutley -p 5433 -d climate_litigation -c "SELECT COUNT(*) FROM cases;"

# Verify analysis data exists
psql -U phdmutley -p 5433 -d climate_litigation -c "SELECT COUNT(*) FROM citation_sixfold_classification;"

# Test analysis engine imports
cd scripts/8-python_back_engine && python -c "from sixfold_analysis_engine import SixfoldAnalysisEngine"

# Check logs
ls logs/
```

## Additional Resources

- `documentation/AI_AGENT_CONTEXT_PhD_Climate_Litigation.md` — comprehensive project context
- `documentation/DATABASE_SCHEMA_ANALYSIS.md` — full schema documentation
- `scripts/5-extract-citations/citation_extraction_pipeline/` — v5 extraction guides
- `scripts/EXPORT_README.md` — export documentation
