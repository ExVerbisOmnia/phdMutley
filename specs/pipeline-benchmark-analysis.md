# Deep Comparative Analysis: phdMutley vs Aegis — Data Pipeline & Architecture Benchmark

**Date**: 2026-03-03
**Authors**: Claude Code analysis (requested by Gustavo & Lucas)
**Purpose**: Broad review of phdMutley's data pipeline and algorithms using Aegis (DECOM Monitor) as a benchmark

---

## Executive Summary

This analysis compares phdMutley (PhD climate litigation citation analysis, 2,924 judicial decisions) against Aegis (production legal-tech SaaS, 153+ tests, FastAPI + async SQLAlchemy, GCP deployment) across 10 engineering dimensions.

**Key findings:**
- **2 critical bugs**: duplicate DB column, hardcoded Linux paths in 12+ files
- **1 critical gap**: zero automated tests for the classification algorithm that drives thesis conclusions
- **Several strengths**: deterministic UUIDs, LLM cost optimization, confidence scoring, INPUT/ALGORITHM/OUTPUT docstrings
- **Appropriate trade-offs**: Flask monolith, sync SQLAlchemy, no auth — all fine for a research tool

**Framing**: phdMutley doesn't need to become a SaaS. For each gap we ask: *"Does this affect data integrity, reproducibility, or analytical correctness of the PhD thesis?"*

---

## Technology Stack Comparison

| Aspect | Aegis (Benchmark) | phdMutley (Subject) |
|--------|-------------------|---------------------|
| **Web Framework** | FastAPI (async) | Flask (sync) |
| **ORM** | SQLAlchemy 2.0 async + asyncpg | SQLAlchemy 2.0 sync + psycopg2 |
| **Database** | PostgreSQL 15 | PostgreSQL 18 |
| **LLM Provider** | Google Gemini (2.5 Flash + embedding-001) | Anthropic Claude (Haiku 4.5 + Sonnet 4.5) |
| **Config** | Pydantic BaseSettings + GCP Secret Manager | Plain dict + os.getenv() + .env |
| **Deployment** | GCP Cloud Run + Docker | Railway + Procfile |
| **Testing** | pytest + pytest-asyncio (153+ tests) | None (trial batch mode + manual review) |
| **Linting** | Ruff (E, F, I, N, W, UP) | None |
| **Auth** | JWT RS256 + RBAC hierarchy | None (appropriate) |

---

## Dimension 1: Pipeline Architecture

### Aegis
Async orchestrator pattern (`backend/etl/ingest.py`). A single `run_ingestion()` coroutine discovers `.md` files, parses them through specialized parsers (`resolution_parser.py`, `circular_parser.py`), and persists entities via async sessions. Per-document transactions. Flat loop over files.

### phdMutley
9-phase sequential pipeline (`scripts/0-*` through `scripts/8-*`). Each phase is an independent Python script in its own directory, run manually in order. Phase 5 (citation extraction) is itself a 4-sub-phase pipeline. Phases share config via `scripts/config.py` and ORM models via imports from `init_database.py`.

### Assessment: Nice-to-have
The sequential phase design is *well-suited for PhD research*. Each phase can be re-run independently, aiding debugging and methodological transparency. Async provides no benefit for batch processing. The numbered-phase convention is clear and directly documentable in the thesis.

### Recommendations
- Consider adding a lightweight `run_pipeline.py` orchestrator that can execute phases 0-8 (or a subset) from a single command for full reproducibility

---

## Dimension 2: Data Ingestion & Transformation

### Aegis
- Specialized parsers return **Pydantic models** (`ParsedResolution`, `ParsedCircular`) with typed fields, Field descriptions, and validation at parse time
- Entity resolution: get-or-create pattern with `session.flush()` for ID generation before linking junction tables
- Deduplication: `fonte_url` UNIQUE constraint; idempotent re-runs skip existing documents
- Text chunking for RAG: 2000-char chunks with 200-char overlap, smart split at paragraph/sentence boundaries

### phdMutley
- Parsers return **plain dictionaries** (e.g., `{'text': ..., 'pages': ..., 'method': ..., 'success': ...}`)
- Phase 2 (metadata import) uses **deterministic UUID5** generation (`UUID_NAMESPACE = uuid5(NAMESPACE_DNS, 'climatecasechart.com.phdmutley')`) for reproducible IDs
- Deduplication via query-before-insert: `session.query(X).filter(...).first()`
- Citation extraction uses extensive **hardcoded domain dictionaries**: 200+ courts in `KNOWN_FOREIGN_COURTS`, 30+ landmark cases, jurisdiction aliases, 100+ countries — all inside `extract_citations_v5.2.py`

### Assessment: Important
Plain dicts risk silent key typos (`'succes'` instead of `'success'` passes silently). The deterministic UUID5 approach is *excellent* for research reproducibility — superior to Aegis's random UUID4. The hardcoded dictionaries are a research strength but a maintenance/review liability.

### Recommendations
1. **Add dataclass or Pydantic models** for pipeline return types — prevents silent data corruption
2. **Move domain dictionaries to external JSON files** in `data/reference/` — easier to version, review with advisor, cite in methodology, and validate with tests
3. **Keep the UUID5 approach** — genuine advantage for reproducibility

---

## Dimension 3: Database Design & Schema Management

### Aegis
- SQLAlchemy 2.0 with `Mapped[]` type annotations and `DeclarativeBase` with naming conventions
- UUID4 primary keys
- Explicit relationship loading strategies (`selectin` for common, `noload` for heavy)
- Connection pool: `pool_size=20, max_overflow=40, pool_pre_ping=True`
- Async sessions via asyncpg

### phdMutley
- SQLAlchemy 2.0 with legacy `Column()` syntax and `declarative_base()`
- UUIDv7 PKs (time-ordered) + deterministic UUID5 for reproducibility
- No migration tool — schema via `Base.metadata.create_all(engine)` with manual SQL for changes
- Connection pool: `pool_size=5, max_overflow=10, pool_pre_ping=True`
- **BUG: Duplicate column** `raw_citation_text` defined twice at `init_database.py:274-275`

### Assessment: CRITICAL (duplicate column) / Important (no migrations)

The duplicate `raw_citation_text` column — SQLAlchemy silently uses the last definition, but this masks intent. The absence of Alembic means schema changes are manual SQL scripts with no audit trail.

### Recommendations
1. **Fix duplicate column immediately** — remove line 275 in `init_database.py`
2. **Add Alembic** for schema migration tracking — creates auditable, reproducible schema history for thesis methodology
3. Sync SQLAlchemy approach is appropriate — no changes needed

---

## Dimension 4: Configuration Management

### Aegis
- Pydantic `BaseSettings` with `@lru_cache` singleton — all settings typed and validated at startup
- `@model_validator` strips Windows `\r` from PEM keys
- Google Secret Manager in production
- Single source for all config

### phdMutley
- Plain dict config (`scripts/config.py`) with `os.getenv()` calls, no type validation
- `ANTHROPIC_API_KEY` could be `None` and would only fail at API call time
- **`PROJECT_ROOT` hardcoded to `/home/gusrodgs/Gus/cienciaDeDados/phdMutley`** (line 25)
- Database URL constructed independently in **3 places** (`config.py`, `init_database.py`, `sixfold_analysis_engine.py`) with different defaults

### Assessment: CRITICAL (hardcoded paths) / Important (duplicated DB URL)

**Hardcoded Linux paths appear in 12+ Python files** — the code cannot run on any other machine:

| File | Lines |
|------|-------|
| `scripts/config.py` | 25 |
| `scripts/1-download-decisions/download_decisions.py` | 33 |
| `scripts/2-populate-metadata/populate_metadata.py` | 47-55 |
| `scripts/3-extract-texts/extract_texts.py` | 42-47 |
| `scripts/4-classify-decisions/classify_decisions.py` | 58-62 |
| `scripts/5-extract-citations/extract_citations.py` | 76-80 |
| `scripts/5-extract-citations/.../extract_citations_v5.py` | 65-69 |
| `scripts/5-extract-citations/.../extract_citations_v5.2.py` | 72-76 |
| `scripts/5-extract-citations/.../extract_citations.py` | 65-69 |
| `scripts/inspect_excel.py` | 6-7 |

### Recommendations
1. **Fix `config.py`**: Replace with `PROJECT_ROOT = Path(__file__).resolve().parent.parent`
2. **Fix all scripts**: Replace hardcoded `sys.path.insert()` with relative-to-file computation
3. **Centralize DB URL construction** in `config.py` only — other files should import it
4. Add `validate_config()` with fail-fast assertions for critical settings

---

## Dimension 5: Error Handling & Resilience

### Aegis
- Per-document transactions with typed exception hierarchy: `FileNotFoundError` → `IntegrityError` → `SQLAlchemyError` → catch-all `Exception`
- Stats counters for processed/created/skipped/failed
- `exc_info=True` for full tracebacks

### phdMutley
- Same per-document transaction pattern with stats tracking
- Retry logic for LLM calls: 3-attempt loop with backoff (`5 * (attempt + 1)`)
- JSON parse fallback: regex strips markdown code blocks — pragmatic and correct
- **7 bare `except:` clauses** that can swallow `MemoryError`, `KeyboardInterrupt`, `PermissionError`

### Assessment: Important (bare excepts can mask bugs)

**Bare `except:` locations:**

| File | Line |
|------|------|
| `scripts/2-populate-metadata/populate_metadata.py` | 150, 156 |
| `scripts/3-extract-texts/extract_texts.py` | 295 |
| `scripts/5-extract-citations/extract_citations.py` | 1753 |
| `scripts/5-extract-citations/.../extract_citations_v5.py` | 1288 |
| `scripts/5-extract-citations/.../extract_citations_v5.2.py` | 1421 |
| `scripts/5-extract-citations/.../extract_citations.py` | 1389 |

In a 2,924-document pipeline, silent failures in even 1% of cases could skew thesis results.

### Recommendations
1. Replace all `except:` with `except Exception as e:` and log the exception
2. Add post-processing verification comparing expected vs actual document counts
3. Retry logic and JSON fallback are adequate — no changes needed

---

## Dimension 6: API Design

### Aegis
- FastAPI with layered architecture: Router → Service → Repository (10+ router files)
- Dependency injection via `Depends()` for auth, DB, rate limiting
- Middleware stack: RequestId → Logging → CORS → SecurityHeaders
- Pydantic schemas for all request/response models
- RBAC with role hierarchy, rate limiting via slowapi

### phdMutley
- Flask monolith (`railway/api_server.py`, 1,080 lines) with all endpoints in single file
- Lazy singleton engine pattern for database
- `@handle_exceptions` decorator + `api_response()` helper
- CORS configured differently for prod/dev
- No authentication (appropriate for research tool)
- **4 debug print statements in production code** (lines 48, 54, 64, 72):
  ```python
  print("DEBUG: Starting api_server.py...", file=sys.stdout, flush=True)
  print("DEBUG: Imports complete...", file=sys.stdout, flush=True)
  print("DEBUG: Importing SixfoldAnalysisEngine...", file=sys.stdout, flush=True)
  print("DEBUG: SixfoldAnalysisEngine imported.", file=sys.stdout, flush=True)
  ```

### Assessment: Nice-to-have
Flask monolith is perfectly adequate for a PhD dashboard API. Auth is unnecessary.

### Recommendations
1. **Remove the 4 debug print statements** before thesis submission
2. Minor: split into 2-3 route modules for maintainability (optional)
3. The dynamic SQL construction uses parameterized queries (`text(sql), params`) — no injection risk

---

## Dimension 7: Testing & Quality Assurance

### Aegis
- **153+ tests** with pytest + pytest-asyncio
- Organized by layer: `test_api/`, `test_services/`, `test_repositories/`, `test_etl/`
- Factory fixtures: `sample_documento_dict()`, `make_auth_user()`
- `httpx.AsyncClient` with `ASGITransport` for integration tests
- `dependency_overrides` for mocking auth/DB
- Security test coverage (401, 403 enforcement)

### phdMutley
- **No formal test suite** — zero test files found in entire project
- Quality control via:
  - Trial batch mode (process known subset first)
  - Confidence scoring (0.0-1.0, flag <0.7)
  - Stats tracking dicts across all scripts
  - Manual log review
  - Text quality assessment function

### Assessment: CRITICAL for data integrity

The absence of tests is the **single most impactful gap**. The sixfold classification system is rule-based and deterministic — a misclassification bug could invalidate an entire thesis section. The court dictionary (200+ entries) has no automated validation.

### Recommendations
1. **Unit tests for sixfold classification logic** (highest priority):
   - Australia (National) citing Netherlands (National) → "Foreign Citation"
   - Germany (ECtHR member) citing ECtHR → "International Citation"
   - USA (non-member) citing ECtHR → "Foreign International Citation"
   - ECtHR citing IACtHR → "Inter-System Citation"
   - ECtHR citing Germany (member) → "Member-State Citation"
   - IACtHR citing USA (non-member) → "Non-Member Citation"
2. **Dictionary validation tests**:
   - Every entry in `KNOWN_FOREIGN_COURTS` has valid `country`, `region`, `type`
   - No duplicate keys
   - Region values are exactly "Global North", "Global South", or "International"
   - All countries in `BINDING_JURISDICTIONS` are recognized
3. **Snapshot tests for analysis engine** — run 9-section analysis, save JSON, compare on re-runs
4. Framework: simple `pytest` with `conftest.py` — no async needed

---

## Dimension 8: LLM Integration

### Aegis
- Google Gemini REST API for LLM and embeddings
- `httpx.AsyncClient` with async/await
- Exponential backoff for 429 rate limits (5s × 2^attempt, max 3 retries)
- Batch embedding: 50 texts/request, incremental commits every 500 chunks
- Idempotent re-runs (skip items with existing embeddings)
- **No cost tracking** implemented

### phdMutley
- Anthropic Claude API (sync client)
- **Two-tier model strategy**: Haiku 4.5 for cheap bulk extraction (~$0.02/doc), Sonnet 4.5 for intelligent classification (~$0.003/doc)
- `temperature=0.0` always for reproducibility
- Retry logic: 3-attempt loop with linear/exponential backoff
- JSON parsing with markdown code block stripping fallback
- **Confidence scoring**: 0.0-1.0 with auto-flag <0.7 for manual review
- **Token tracking** per document for cost analysis
- **Budget constraint**: <$200 total, <$0.10/doc
- **3-tier origin identification**: dictionary ($0) → Sonnet (~$0.01) → web search (future)

### Assessment: Adequate — actually strong in several areas

phdMutley's LLM integration is more sophisticated than Aegis's for its use case. The temperature=0.0 policy, confidence scoring, token tracking, cost budgeting, and tiered model selection are research-appropriate best practices that Aegis lacks.

### Recommendations
1. **Document exact model versions** in thesis methodology (`claude-haiku-4-5-20251001`, `claude-sonnet-4-5-20250929`) — models may be deprecated
2. **Save raw LLM responses** to a DB column — enables reprocessing without re-incurring API costs
3. **Add `--dry-run` mode** for prompt verification without spending budget

---

## Dimension 9: Code Organization & Documentation

### Aegis
- Layered package structure: `api/`, `core/`, `models/`, `repositories/`, `services/`, `etl/`
- Pydantic schemas for all I/O boundaries
- Ruff linter with E, F, I, N, W, UP rules
- `pyproject.toml` with Poetry for dependency management

### phdMutley
- Numbered phase directories (`scripts/0-*` through `scripts/8-*`) — clear chronological structure
- **INPUT/ALGORITHM/OUTPUT docstring standard** used consistently — academic strength
- Stats tracking dict pattern used consistently across all pipeline scripts
- Hierarchical logging with emoji markers
- **No linter configured**
- **No `pyproject.toml`** — only `railway/requirements.txt`

### Assessment: Important (no linter) / Nice-to-have (pyproject.toml)

### Recommendations
1. Add `ruff` with minimal rules (`ruff check . --select E,F,W`) — catches unused imports, undefined names, bare excepts
2. Add `pyproject.toml` for project metadata and tool config
3. **Keep the INPUT/ALGORITHM/OUTPUT convention** — it is a genuine documentation strength worth citing in the thesis

---

## Dimension 10: Deployment & Operations

### Aegis
- Multi-stage Dockerfile: builder (Poetry export) → runtime (non-root user, HEALTHCHECK)
- `docker-compose.yml` for local development
- GCP Cloud Run with structured JSON logging
- Request ID propagation across middleware
- Append-only audit_log table

### phdMutley
- No Docker — Railway builds from `requirements.txt`
- Railway deployment via Procfile: `gunicorn --bind 0.0.0.0:$PORT --workers 4 --timeout 120 api_server:app`
- `postgres://` → `postgresql://` URL conversion in code
- Output files to `/tmp/` in production (Railway's writable directory)
- **Unpinned dependencies** (`flask>=3.0.0` etc.)
- No audit logging

### Assessment: Nice-to-have except dependency pinning

### Recommendations
1. **Pin dependency versions** for reproducibility (e.g., `flask==3.1.0` not `flask>=3.0.0`)
2. Docker, audit logging, structured logging are unnecessary for this project

---

## What phdMutley Does Better Than Aegis

Not everything is a gap — these are areas where phdMutley is **superior** for its research context:

| Strength | Why It Matters |
|----------|----------------|
| **Deterministic UUID5 generation** | Same input always produces same UUID; Aegis uses random UUID4 |
| **LLM cost optimization** | 3-tier origin ID (dictionary $0 → Sonnet ~$0.01 → web), Haiku/Sonnet tiering |
| **Confidence scoring** | 0.0-1.0 scale with auto-flagging and manual review workflow |
| **Temperature=0.0 policy** | Ensures reproducible LLM outputs for academic rigor |
| **INPUT/ALGORITHM/OUTPUT docstrings** | Self-documenting methodology, directly citable in thesis |
| **Trial batch mode** | Systematic subset testing before full pipeline runs |
| **Sequential phase architecture** | Each phase independently re-runnable; ideal for debugging and methodology documentation |
| **Token/cost tracking** | Per-document API cost accounting with budget constraints |

---

## Prioritized Action Plan

### Phase A — Data Integrity (Do First)

| # | Action | Files | Severity |
|---|--------|-------|----------|
| 1 | Fix duplicate `raw_citation_text` column | `scripts/0-initialize-database/init_database.py:274-275` | **Critical** |
| 2 | Fix all hardcoded Linux paths (12+ files) | `scripts/config.py:25` + all `sys.path.insert` calls (see Dimension 4) | **Critical** |
| 3 | Replace 7 bare `except:` with `except Exception as e:` + logging | See Dimension 5 table | **Important** |
| 4 | Write pytest tests for sixfold classification logic | New: `tests/test_classification.py` | **Critical** |
| 5 | Write validation tests for court/case dictionaries | New: `tests/test_dictionaries.py` | **Critical** |

### Phase B — Reproducibility (Before Thesis Submission)

| # | Action | Files | Severity |
|---|--------|-------|----------|
| 6 | Centralize DB URL construction to `config.py` only | `config.py`, `init_database.py`, `sixfold_analysis_engine.py` | Important |
| 7 | Add fail-fast config validation | `scripts/config.py` | Important |
| 8 | Pin dependency versions | `railway/requirements.txt` | Important |
| 9 | Add Alembic for schema migrations | New: `alembic/`, `alembic.ini` | Important |
| 10 | Add dataclass/Pydantic models for pipeline data structures | Pipeline scripts (phases 3, 5) | Important |
| 11 | Externalize domain dictionaries to `data/reference/*.json` | `extract_citations_v5.2.py` | Important |

### Phase C — Code Quality (If Time Permits)

| # | Action | Files | Severity |
|---|--------|-------|----------|
| 12 | Remove 4 debug print statements | `railway/api_server.py:48,54,64,72` | Nice-to-have |
| 13 | Add `ruff` linter with basic rules | New: `pyproject.toml` | Nice-to-have |
| 14 | Add snapshot tests for analysis engine | New: `tests/test_analysis_engine.py` | Nice-to-have |
| 15 | Add `run_pipeline.py` orchestrator | New: `scripts/run_pipeline.py` | Nice-to-have |
| 16 | Document exact LLM model versions in thesis methodology | Thesis document (external) | Nice-to-have |
| 17 | Save raw LLM responses to DB column | Citation extraction scripts | Nice-to-have |

---

## Appendix A: Aegis Architecture Deep-Dive (Reference)

### ETL Pipeline
- Entry: `backend/etl/ingest.py` → `run_ingestion()` async coroutine
- Parsers: `resolution_parser.py`, `circular_parser.py` → Pydantic models (`ParsedResolution`, `ParsedCircular`)
- Entity resolution: get-or-create for Pais, Produto, Parte with `session.flush()`
- Statistics: processed/created/skipped/failed counters per document type

### RAG Pipeline (4 phases)
1. Document embeddings: `resumo + first 8000 chars of texto_completo`
2. Section embeddings: `titulo + texto` from `SecaoResolucao`
3. Chunk creation: 2000-char chunks, 200-char overlap, smart split (paragraph → sentence → hard break)
4. Chunk embeddings: batch of 50, incremental commits every 500

### Database Models
- `Documento` (core), `SecaoResolucao` (sections), `ChunkDocumento` (RAG chunks)
- `Pais`, `Produto`, `Parte` (entities) with M2M junction tables
- `AuditLog` (append-only security log)
- Vector(768) columns for pgvector, TSVECTOR for PostgreSQL full-text search

### API Architecture
- FastAPI with Router → Service → Repository layering
- Dependency injection: `get_db()`, `get_current_user()`, `require_role()`
- Middleware: RequestId → RequestLogging → CORS → SecurityHeaders
- Error handling: RequestValidationError (422), HTTPException (structured), Exception (500 with request ID)
- Rate limiting: slowapi per-user/per-IP

### Testing Pattern
```python
# conftest.py fixture pattern
@pytest_asyncio.fixture
async def client(mock_user):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

# Factory pattern
def sample_documento_dict(**overrides) -> dict:
    defaults = {"id": uuid4(), "tipo_ato": TipoAto.RESOLUCAO_GECEX, ...}
    defaults.update(overrides)
    return defaults
```

### Security
- JWT RS256 (asymmetric signing)
- RBAC: USER < ADMIN < SUPERADMIN hierarchy
- tsquery escaping for FTS (prevents injection)
- SecurityHeaders middleware (HSTS, CSP, X-Frame-Options)
- Non-root Docker user

---

## Appendix B: phdMutley Architecture Deep-Dive (Reference)

### 9-Phase Pipeline
| Phase | Script | Operation | Cost |
|-------|--------|-----------|------|
| 0 | `init_database.py` | Schema creation | $0 |
| 1 | `download_decisions.py` | PDF download (concurrent) | $0 |
| 2 | `populate_metadata.py` | Excel→DB import (deterministic UUIDs) | $0 |
| 3 | `extract_texts.py` | PDF text extraction (pdfplumber → PyMuPDF → PyPDF2) | $0 |
| 4 | `classify_decisions.py` | is_decision classification (heuristic + Sonnet) | ~$0.003/doc |
| 5 | `extract_citations_v5.2.py` | Citation extraction (4-sub-phase pipeline) | ~$0.02/doc |
| 6-7 | SQL scripts | Data adjustments & analytical queries | $0 |
| 8 | `sixfold_analysis_engine.py` + `api_server.py` | Analysis (9 sections) & REST API | $0 |

### Citation Extraction v5 Sub-Pipeline
1. **Source Jurisdiction**: DB lookup ($0)
2. **Extraction**: Haiku, 12 citation formats, captures context/location (~$0.02/doc)
3. **Origin ID**: Tier 1 dictionary (200+ courts, $0) → Tier 2 Sonnet (~$0.01) → Tier 3 web (future)
4. **Classification**: Rule-based sixfold system ($0)

### Sixfold Classification System
| # | Type | Direction | Example |
|---|------|-----------|---------|
| 1 | Foreign | National → National | Australia cites Netherlands |
| 2 | International | National → Int'l member court | Germany cites ECtHR |
| 3 | Foreign International | National → Int'l non-member | USA cites ECtHR |
| 4 | Inter-System | Int'l → Int'l | ECtHR cites IACtHR |
| 5 | Member-State | Int'l → National member | ECtHR cites Germany |
| 6 | Non-Member | Int'l → National non-member | IACtHR cites USA |

### Analysis Engine
- `SixfoldAnalysisEngine` class (~2,368 lines)
- 9 query sections with multiple queries each
- Results stored as JSONB in `first_analysis` table (UPSERT on query_id)
- Generates: network data (D3.js), dashboard aggregates, CSV exports
- Decimal encoder for JSON compatibility

### Dashboard
- Single HTML file (`railway/templates/dashboard.html`, ~166KB)
- Inline JS/CSS with D3.js visualizations
- Served by Flask via `render_template()`
- Separate static variant at `scripts/8-python_back_engine/frontend/index.html`

### Key Data Points
- 2,924 judicial decisions from Climate Case Chart
- 96% Global North, 4% Global South (29:1 ratio)
- UUIDv7 time-ordered PKs for all tables
- Deterministic UUID5 for document IDs (reproducible from source data)
- Binding court jurisdictions: IACtHR, ECtHR, ACHPR with country lists in `config.py`
