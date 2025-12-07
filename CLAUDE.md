# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**PhD Climate Litigation Citation Analysis Project**

This is a doctoral research project analyzing citation patterns between Global North and Global South courts in climate litigation decisions. The project processes 2,924 judicial decisions from the Climate Case Chart database to quantify transnational judicial dialogue and examine North-South citation asymmetries.

**Core Technology Stack:**
- PostgreSQL 18 (production database)
- Python 3.13.9
- Flask API + HTML/JS dashboard
- Anthropic Claude API (Haiku 4.5 for extraction, Sonnet 4.5 for classification)
- Railway for deployment

## Development Environment

### Database Configuration

**Local Development:**
```bash
# PostgreSQL 18 on localhost:5432
# Database name: climate_litigation
# Credentials in .env file
```

**Production (Railway):**
- Uses `DATABASE_URL` environment variable
- SQLAlchemy 2.0+ requires `postgresql://` (not `postgres://`)
- Code automatically handles conversion in `api_server.py` and `sixfold_analysis_engine.py`

### Python Environment

Activate the virtual environment before running any script:
```bash
source venv/bin/activate
# or
./activate.sh
```

### Environment Variables

Critical variables in `.env`:
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` - PostgreSQL connection
- `ANTHROPIC_API_KEY` - Claude API key
- `DATABASE_URL` - Railway production database (automatically provided)

## Common Commands

### Running the Backend API

**Development (local):**
```bash
cd railway
python api_server.py --host 127.0.0.1 --port 5000
```

**Production (Railway):**
```bash
# Railway automatically runs via Procfile:
gunicorn -w 4 -b 0.0.0.0:$PORT api_server:app
```

### Running Analysis Pipeline

```bash
cd scripts/8-python_back_engine
python sixfold_analysis_engine.py
```

### Database Operations

**Initialize database schema:**
```bash
cd scripts/0-initialize-database
python init_database.py
```

**Run SQL migrations:**
```bash
psql -U phdmutley -d climate_litigation -f scripts/5-extract-citations/citation_extraction_pipeline/migrate_citation_phased_schema.sql
```

**Create database backup:**
```bash
pg_dump -U phdmutley -d climate_litigation > backup_$(date +%Y%m%d_%H%M%S).dump
```

### Data Processing Scripts

Scripts are organized in numbered phases (0-8) and should generally be run in sequence:

```bash
# Phase 0: Initialize database
cd scripts/0-initialize-database && python init_database.py

# Phase 1: Download PDFs
cd scripts/1-download-decisions && python download_decisions.py

# Phase 2: Populate metadata from Excel
cd scripts/2-populate-metadata && python populate_metadata.py

# Phase 3: Extract text from PDFs
cd scripts/3-extract-texts && python extract_texts.py

# Phase 4: Classify documents (judicial decisions vs other)
cd scripts/4-classify-decisions && python classify_decisions.py

# Phase 5: Extract citations
cd scripts/5-extract-citations && python extract_citations.py

# Phase 6-7: Adjustments and queries (SQL files)
# Run SQL files manually via psql

# Phase 8: Analysis engine and API
cd scripts/8-python_back_engine && python sixfold_analysis_engine.py
```

## Code Architecture

### Project Structure

```
phdMutley/
├── railway/                    # Production deployment files
│   ├── api_server.py          # Flask REST API
│   ├── sixfold_analysis_engine.py  # Core analysis logic
│   ├── setup_analysis_db.py   # Analysis database setup
│   └── requirements.txt       # Production dependencies
├── scripts/                   # Data processing pipeline
│   ├── 0-initialize-database/ # Database schema creation
│   ├── 1-download-decisions/  # PDF download pipeline
│   ├── 2-populate-metadata/   # Excel → PostgreSQL import
│   ├── 3-extract-texts/       # PDF text extraction
│   ├── 4-classify-decisions/  # Document classification
│   ├── 5-extract-citations/   # Citation extraction v5
│   ├── 6-adjustments/         # Data corrections (SQL)
│   ├── 7-queries/            # Analytical queries (SQL)
│   ├── 8-python_back_engine/ # Analysis engine & API
│   └── config.py             # Centralized configuration
├── data/
│   ├── pdfs/                 # Downloaded PDF files
│   └── processed/            # Processed data files
├── documentation/            # Project documentation
├── logs/                     # Application logs
└── venv/                     # Python virtual environment
```

### Key Modules

**API Server (`railway/api_server.py`):**
- Flask REST API serving analysis results
- Endpoints: `/api/health`, `/api/dashboard`, `/api/network`, `/api/results/*`
- CORS configured for production deployment
- Lazy initialization of analysis engine singleton

**Analysis Engine (`railway/sixfold_analysis_engine.py`):**
- Executes 9 sections of analytical queries
- Generates network data for D3.js visualization
- Produces dashboard aggregates
- Stores results in `first_analysis` table

**Config (`scripts/config.py`):**
- Centralized configuration for all scripts
- Database connection settings
- API keys and model selection
- Trial batch and test mode toggles
- Jurisdiction mapping for binding courts

### Database Schema

**Core Tables:**
- `cases` - Case metadata (2,924 records)
- `documents` - Individual document records
- `extracted_text` - PDF text extraction results
- `citation_extraction_phased` - Individual citations (v5 schema)
- `citation_extraction_phased_summary` - Document-level stats
- `citation_sixfold_classification` - Sixfold classified citations
- `first_analysis` - Analysis query results

**Important: UUIDv7 Primary Keys**
All tables use UUIDv7 primary keys (time-ordered UUIDs) for efficient indexing and chronological ordering.

### Citation Extraction v5 Architecture

The citation extraction system uses a **4-phase pipeline**:

1. **Phase 1: Source Jurisdiction Identification** (Database lookup, $0 cost)
2. **Phase 2: Comprehensive Extraction** (Claude Haiku 4.5, ~$0.02/doc)
   - 12 citation format patterns
   - Captures context and location
3. **Phase 3: Origin Identification** (3-tier system)
   - Tier 1: Dictionary lookup (80+ courts, $0 cost)
   - Tier 2: Claude Sonnet analysis (~$0.01/citation)
   - Tier 3: Web search (placeholder, future)
4. **Phase 4: Classification** (Rule-based, $0 cost)
   - Foreign, International, Foreign International, etc.

**Quality Control:**
- Confidence scoring (0.0-1.0)
- Automatic flagging (<0.7 confidence)
- Manual review workflow

## Development Patterns

### Error Handling

All scripts follow this pattern:
```python
try:
    # Main logic
    result = process_data()
    session.commit()
    stats['processed'] += 1
    logging.info(f"✓ Success: {result}")
    return True

except SpecificException as e:
    session.rollback()
    logging.error(f"Specific error: {e}")
    stats['specific_errors'] += 1
    return False

except Exception as e:
    session.rollback()
    logging.error(f"General error: {e}")
    logging.error(traceback.format_exc())
    stats['errors'] += 1
    return False
```

### Documentation Standard

Every function must include INPUT→ALGORITHM→OUTPUT documentation:
```python
def function_name(param1: Type1, param2: Type2) -> ReturnType:
    """
    Brief description of function purpose.

    INPUT:
        - param1: Description
        - param2: Description
    ALGORITHM:
        1. First step
        2. Second step
    OUTPUT: Description of return value
    """
    pass
```

### Logging Conventions

```python
logging.info("="*70)
logging.info("MAJOR SECTION TITLE")
logging.info("="*70)
logging.info("Regular information message")
logging.warning("⚠️  Warning message")
logging.error("❌ Error message")
logging.info(f"✓ Success: {value}")
```

### Configuration Usage

Always use centralized config:
```python
from config import CONFIG, DB_CONFIG, TRIAL_BATCH_CONFIG

# API keys
api_key = CONFIG['ANTHROPIC_API_KEY']

# Database
engine = create_engine(DB_CONFIG)

# Trial batch filtering
if TRIAL_BATCH_CONFIG['ENABLED']:
    # Apply trial batch filter
```

## Working with LLMs

### Model Selection

- **Haiku 4.5** (`claude-haiku-4-5-20251001`): Bulk extraction, cost-effective
- **Sonnet 4.5** (`claude-sonnet-4-5-20250929`): Classification, intelligent analysis

### Best Practices

1. Always set `temperature=0.0` for reproducibility
2. Track token usage for cost analysis
3. Include retry logic for API failures
4. Log raw responses for debugging
5. Parse JSON carefully with fallback extraction
6. Use Haiku for extraction, Sonnet for analysis

### Cost Guidelines

- Document classification: ~$0.003/doc (Sonnet)
- Citation extraction: ~$0.015-0.025/doc (Haiku)
- Origin identification: $0 (Tier 1) or ~$0.01 (Tier 2 Sonnet)
- Target: <$0.10 per document total

## Deployment

### Railway Configuration

**Environment Variables (set in Railway dashboard):**
- `DATABASE_URL` - Provided automatically by Railway PostgreSQL
- `ANTHROPIC_API_KEY` - Add manually
- `PORT` - Provided automatically by Railway

**Key Files:**
- `railway/` directory contains all production code
- `requirements.txt` lists production dependencies
- Railway automatically detects Flask app and uses gunicorn

**Important Notes:**
- Railway's PostgreSQL uses `postgres://` but SQLAlchemy 2.0+ requires `postgresql://`
- Both `api_server.py` and `sixfold_analysis_engine.py` handle this conversion automatically
- Output files go to `/tmp/` in production (Railway's writable directory)

### Local Testing of Production Code

```bash
# Test the API locally with production-like settings
cd railway
export DATABASE_URL="postgresql://user:pass@localhost:5432/climate_litigation"
export ANTHROPIC_API_KEY="sk-ant-..."
python api_server.py
```

## Database Best Practices

### When Modifying Schema

1. Always use UUIDv7 for primary keys
2. Include foreign key constraints with CASCADE
3. Add indexes on frequently queried columns
4. Use TIMESTAMP for all time fields
5. Include `created_at` and `updated_at` on all tables
6. Add UNIQUE constraints where appropriate
7. Document columns with COMMENT ON statements

### When Writing Queries

1. Use parameterized queries (SQLAlchemy text() with params)
2. Always close connections/sessions
3. Use transactions for multi-statement operations
4. Index foreign keys and WHERE clause columns
5. EXPLAIN ANALYZE complex queries

## PDF Processing

**Hierarchical Extraction Pipeline:**
1. Try `pdfplumber` first (best for native PDFs, 94.1% success)
2. Fall back to `PyMuPDF` if pdfplumber fails
3. Use `PyPDF2` as last resort
4. Only use OCR (tesseract) if all else fails

**Always:**
- Log extraction method used
- Track extraction success rates
- Store file paths and metadata

## Testing

### Trial Batch Mode

Enable in `scripts/config.py`:
```python
TRIAL_BATCH_CONFIG = {
    'ENABLED': True,  # Set to True for trial batch
    'COLUMN_NAME': 'Trial batch',
    'TRUE_VALUES': [True, 'TRUE', 'true', 1, 'yes']
}
```

Marks specific documents in Excel/database for testing.

### Test Mode (Limited Rows)

```python
TEST_CONFIG = {
    'ENABLED': True,   # Enable test mode
    'LIMIT': 50,       # Process first 50 rows
    'STRATEGY': 'first'
}
```

Limits processing to first N rows for rapid iteration.

## Important Constraints

### Academic Rigor

This is PhD research - maintain:
- Transparent methodology
- Reproducible results
- Complete audit trails
- Documented decisions
- Confidence scoring
- Manual review for uncertain cases

### Budget

- Total project budget: <$200 for API calls
- Target: <$0.10 per document
- Prefer Tier 1 (dictionary) over Tier 2 (API) when possible

### Deadlines

- Production deadline was November 30, 2025
- System is in production use for thesis analysis

## Troubleshooting

### Database Connection Issues

```bash
# Test connection
psql -U phdmutley -d climate_litigation -c "SELECT COUNT(*) FROM cases;"

# Check DATABASE_URL format
echo $DATABASE_URL  # Should be postgresql:// not postgres://
```

### API Server Not Starting

```bash
# Check logs
cd railway
python api_server.py  # Will show startup errors

# Verify imports
python -c "from sixfold_analysis_engine import SixfoldAnalysisEngine"
```

### Analysis Not Generating Data

```bash
# Check if citation_sixfold_classification table exists
psql -U phdmutley -d climate_litigation -c "\d citation_sixfold_classification"

# Verify data exists
psql -U phdmutley -d climate_litigation -c "SELECT COUNT(*) FROM citation_sixfold_classification;"
```

### Citation Extraction Failures

1. Check API key: `echo $ANTHROPIC_API_KEY`
2. Verify model names in `config.py`
3. Check log files in `logs/` directory
4. Verify PDF exists and is readable
5. Check `is_decision` flag is True

## Research Context

**Global North vs Global South:**
- 96% of cases are Global North, 4% Global South (29:1 ratio)
- Research examines citation asymmetries and judicial dialogue patterns
- Quantifies transnational legal transplantation

**Maria Antonia Tigre's Definition:**
> "The phrase 'Global South' refers broadly to the regions of Latin America and the Caribbean, Asia, Africa and Oceania, and denotes regions that are mostly low-income and often politically or culturally marginalized."

**Sixfold Classification System:**
1. Foreign Citation (National → National)
2. International Citation (National → Int'l member court)
3. Foreign International Citation (National → Int'l non-member)
4. Inter-System Citation (Int'l → Int'l)
5. Member-State Citation (Int'l → National member)
6. Non-Member Citation (Int'l → National non-member)

## Additional Resources

- Full project context: `documentation/AI_AGENT_CONTEXT_PhD_Climate_Litigation.md`
- Database schema analysis: `documentation/DATABASE_SCHEMA_ANALYSIS.md`
- Citation extraction v5 guides: `scripts/5-extract-citations/citation_extraction_pipeline/`
- Export documentation: `scripts/EXPORT_README.md`
