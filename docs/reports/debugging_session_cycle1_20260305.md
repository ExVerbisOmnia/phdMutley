# Debugging Session Report — 5 Mar 2026 (Evening)

## Scope
Post-v6 integration pipeline stabilization. Analyzing logs from trial runs 1-2 and fixing identified issues.

## Bugs Found & Fixed

### P1: `'list' object has no attribute 'get'` in Tier 2 Origin ID (2 occurrences in logs)
- **Root cause**: Gemini API sometimes wraps JSON response in `[{...}]` instead of `{...}`
- **Location**: `extract_citations.py` — `identify_origin_tier2_sonnet()` line ~1569
- **Fix**: Added `isinstance(data, list)` unwrap guard before `.get()` calls
- **Also applied**: Same guard in `classify_citations_functionally()` as preventive fix

### P2: Unicode encoding errors (~100 tracebacks in pipeline_rerun log)
- **Root cause**: `logging.FileHandler` on Windows defaults to cp1252, which can't encode emoji chars (check marks, arrows, info symbols)
- **Affected scripts**: 6 of 8 pipeline scripts missing `encoding="utf-8"`
- **Fix**: Added `encoding="utf-8"` to all FileHandler calls across:
  - `init_database.py`, `download_decisions.py`, `populate_metadata.py`
  - `extract_texts.py`, `build_knowledge_base.py`, `export_to_excel.py`
- **Already correct**: `extract_citations.py`, `classify_decisions.py`

### P3: Failed JSON parsing (4 docs across runs)
- **Docs**: `66dca36b` (3x), `3f4f79ce`, `c17c1eb1`, `af0d09e3`
- **Pattern**: Consistently fail Phase 2A extraction JSON parsing. Possibly large/complex documents.
- **Status**: Not fixed this session — tracked for investigation (may need output token increase)

### Known: Snippet miss rate ~35% (task #74)
- When snippet extraction fails, Phase 2B functional classification degrades (LLM asks for context)
- Pipeline handles gracefully — classification skipped, citation still saved
- Tracked as task #74 for future improvement

## New Feature: Discarded Citations Audit Table

### Table: `citation_extraction_discarded`
| Column | Type | Purpose |
|--------|------|---------|
| id | SERIAL PK | Auto-increment |
| document_id | UUID FK | Links to source document |
| case_name | VARCHAR(500) | Case name as extracted by LLM |
| raw_text | TEXT | Verbatim citation from document |
| confidence | DECIMAL(3,2) | LLM extraction confidence |
| sabin_closest_match | VARCHAR(500) | Nearest KB case (if any) |
| sabin_match_score | DECIMAL(3,2) | Similarity score from filter |
| discard_reason | VARCHAR(100) | Why discarded |
| extraction_run_id | VARCHAR(50) | Batch grouping |
| created_at | TIMESTAMP | Record creation time |

### Changes
- `init_database.py`: Added `CitationExtractionDiscarded` ORM model
- `sabin_filter.py`: Added `closest_name` and `closest_score` to no-match returns
- `extract_citations.py`: Save discarded after Sabin filter, auto-create table in migration

## Verification Test (6 docs, seed=42)
- 0 errors, 0 failures
- 8 kept / 17 discarded (all saved)
- 100% functional classification on snippeted citations
- Zero Unicode encoding errors in logs

## Files Modified
- `scripts/0-initialize-database/init_database.py` (model + encoding)
- `scripts/sabin_filter.py` (closest match fields)
- `scripts/5-extract-citations/extract_citations.py` (discarded save, list guards, run ID)
- `scripts/1-download-decisions/download_decisions.py` (encoding)
- `scripts/2-populate-metadata/populate_metadata.py` (encoding)
- `scripts/3-extract-texts/extract_texts.py` (encoding)
- `scripts/build_knowledge_base.py` (encoding)
- `scripts/export_to_excel.py` (encoding)
