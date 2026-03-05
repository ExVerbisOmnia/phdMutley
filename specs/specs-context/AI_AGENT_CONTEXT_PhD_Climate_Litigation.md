# PhD Climate Litigation Project - AI Agent Context File
## Complete Project Documentation for IDE AI Integration

**Last Updated:** December 01, 2025  
**Project:** Doutorado PM - Climate Litigation Citation Analysis  
**Researcher:** Gustavo Rodrigues  
**Academic Collaborator:** Lucas Biasetton  
**Current Phase:** Phase 2 - Citation Extraction v5 Implementation Complete

---

## 📋 PROJECT OVERVIEW

### Research Objective
Analyze citation patterns between Global North and Global South courts in climate litigation decisions, specifically quantifying transnational judicial dialogue and examining North-South citation asymmetries.

### Core Research Question
How do courts cite foreign and international decisions in climate cases, and what are the patterns of cross-jurisdictional citation flows between Global North and Global South?

### Dataset
- **Source:** Climate Case Chart database (Columbia University/LSE)
- **Total Cases:** 2,924 judicial decisions
- **Geographic Distribution:** 96% Global North, 4% Global South (29:1 ratio)
- **Document Types:** Judicial decisions, orders, procedural documents
- **Languages:** Primarily English, some multilingual documents

### Success Metrics
- **Recall Rate:** 75-85% for foreign citation extraction
- **Precision Rate:** 85-90% classification accuracy
- **Academic Rigor:** Reproducible algorithms with transparent documentation
- **Deadline:** November 30, 2025 for December presentation

---

## 🎯 CURRENT PROJECT STATE

### ✅ COMPLETED PHASES

#### **Phase 0: Infrastructure Setup** (COMPLETE)
- ✅ PostgreSQL 18 database with optimized schema
- ✅ UUIDv7 primary keys for all tables
- ✅ Advanced features: virtual generated columns, AIO optimization
- ✅ Comprehensive table structure:
  - `cases` - Case-level metadata
  - `documents` - Individual document records
  - `extracted_text` - PDF text extraction results
  - `citations` - Citation records (legacy v4)
  - `citation_extraction` - Extraction metadata (legacy v4)
  - `citation_extraction_phased` - NEW v5 individual citations
  - `citation_extraction_phased_summary` - NEW v5 document summaries

#### **Phase 1: Data Processing** (COMPLETE)
- ✅ Metadata population from Excel (baseCompleta.xlsx)
- ✅ 2,924 cases + documents imported
- ✅ 99.9% URL availability for PDF downloads
- ✅ PDF download pipeline with hierarchical fallback
- ✅ Text extraction with 94.1% direct PDF success rate
- ✅ Hierarchical extraction: pdfplumber → PyMuPDF → PyPDF2
- ✅ Only 5.9% require OCR (better than expected 20%)

#### **Phase 2a: Document Classification** (COMPLETE)
- ✅ Claude Sonnet 4.5 classification
- ✅ is_decision boolean field populated
- ✅ 97-99% accuracy achieved
- ✅ Cost-effective: $0.003 per document
- ✅ Ready for citation extraction

#### **Phase 2b: Citation Extraction v5** (JUST COMPLETED - November 22, 2025)
- ✅ **Complete 4-phase architecture implemented**
- ✅ **Enhanced dictionaries:** 80+ foreign courts, 20+ landmark cases
- ✅ **3-tier origin identification system**
- ✅ **Comprehensive extraction:** 12 citation format patterns
- ✅ **Caching system** for repeated citations
- ✅ **Automatic quality control** with confidence-based flagging
- ✅ **Production-ready code:** 1,650+ lines, fully documented
- ✅ **Database schema:** New tables created and optimized
- ✅ **Expected improvement:** 40-50% → 75-85% recall

---

## 🏗️ TECHNICAL ARCHITECTURE

### Technology Stack

#### **Database**
- **PostgreSQL 18** (latest stable)
- **Key Features Used:**
  - UUIDv7 primary keys (time-ordered)
  - Virtual generated columns
  - AIO (Asynchronous I/O) optimization
  - Full-text search capabilities (future use)
  - JSONB for flexible metadata storage
  
#### **Python Environment**
- **Version:** Python 3.13.9
- **Key Libraries:**
  - `anthropic` - Claude API integration
  - `sqlalchemy` - Database ORM
  - `pandas` - Data manipulation
  - `pdfplumber` - Primary PDF extraction
  - `PyMuPDF` (fitz) - Fallback PDF extraction
  - `PyPDF2` - Secondary fallback
  - `pytesseract` - OCR for scanned documents
  - `tqdm` - Progress bars
  - `networkx` - Future network analysis
  - `plotly` - Visualization
  - `streamlit` - Dashboard (planned)

#### **AI Models**
- **Claude Sonnet 4.5** (`claude-sonnet-4-20250514`)
  - Document classification: $0.003/doc
  - Origin identification (Tier 2): ~$0.01/citation
  - High accuracy: 97-99%
  
- **Claude Haiku 4.5** (`claude-haiku-4-20250514`)
  - Citation extraction: $0.015-0.025/doc
  - Cost-effective for bulk processing
  - Fast response times

### Project Directory Structure

```
phdMutley/
├── .claude/
│   └── CLAUDE.md                      # Project instructions for Claude Code
├── scripts/
│   ├── config.py                      # Central configuration (Pydantic Settings)
│   ├── gcp_secrets.py                 # GCP Secret Manager + DB URL helper
│   ├── gemini_client.py               # Shared Gemini API client (singleton, retry)
│   ├── pipeline_models.py             # Shared enums & Pydantic data models
│   ├── progress_tracker.py            # CLI progress/task tracker (SQLite)
│   ├── export_static_site.py          # Runs engine + exports JSON → docs/data/
│   ├── export_to_excel.py             # Export to Excel
│   ├── alembic.ini                    # Alembic config
│   ├── alembic/                       # Database migrations
│   ├── 0-initialize-database/
│   │   └── init_database.py           # Database schema definitions
│   ├── 1-download-decisions/
│   │   └── download_decisions.py      # PDF download pipeline
│   ├── 2-populate-metadata/
│   │   └── populate_metadata.py       # Excel → PostgreSQL import
│   ├── 3-extract-texts/
│   │   └── extract_texts.py           # Text extraction pipeline
│   ├── 4-classify-decisions/
│   │   └── classify_decisions.py      # Document classification
│   ├── 5-extract-citations/
│   │   ├── extract_citations.py       # Citation extraction v5
│   │   └── citation_extraction_pipeline/ # Pipeline modules & docs
│   └── 8-python_back_engine/
│       ├── sixfold_analysis_engine.py  # Core analysis engine (9 queries)
│       ├── api_server.py              # API server (legacy, static site replaced)
│       ├── setup_analysis_db.py       # Analysis DB setup
│       └── classify_decisions_sixfold.py # Sixfold classification logic
├── docs/                               # GitHub Pages static site
│   ├── index.html                     # Dashboard (D3.js, inline JS/CSS)
│   ├── progress.html                  # Progress tracker dashboard
│   └── data/                          # Pre-computed JSON for dashboard
├── docker/                             # Local dev Docker setup
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── run-pipeline.sh
├── tests/                              # pytest test suite
├── specs/                              # Project specifications & meeting notes
│   ├── master-plan-v2.md
│   ├── meetings/
│   └── specs-context/
├── data/                               # Data files (gitignored contents)
├── logs/                               # Log files (gitignored contents)
├── dev_tools/                          # Development utilities
├── requirements.txt                    # Pinned production dependencies
├── requirements-dev.txt                # Dev dependencies (pytest, ruff, etc.)
├── pyproject.toml                      # Ruff & pytest config
└── xOld/                               # Archived files (gitignored)
```

---

## 🔧 KEY IMPLEMENTATION DETAILS

### Citation Extraction v5 Architecture (LATEST)

#### **Phase 1: Source Jurisdiction Identification**
```python
INPUT: Document metadata (Geographies field from database)
ALGORITHM:
  1. Split by semicolon
  2. Take first value (country level)
  3. Handle international tribunals
  4. Classify region: Global North/South/International
OUTPUT: 
  - source_jurisdiction (string)
  - source_region (string)
COST: Zero (database lookup)
TIME: Instant
```

#### **Phase 2: Comprehensive Extraction**
```python
INPUT: Full document text + source jurisdiction
ALGORITHM:
  1. Generate comprehensive extraction prompt
  2. Call Claude Haiku 4.5 with 12 citation format patterns:
     - Traditional citations (Brown v. Board)
     - Narrative references (The Norwegian Court held...)
     - Shorthand references (the Urgenda case)
     - Scholarly citations (Professor X analyzed...)
     - Procedural references (on appeal from...)
     - Comparative references (unlike the approach in...)
     - Signal citations (see also, cf., compare)
     - Footnote/endnote citations
     - Dissenting/concurring opinion citations
     - Doctrine references (European precautionary principle)
     - Advisory opinions (ICJ Advisory Opinion)
     - Pending/ongoing cases
  3. Capture context: 2-3 sentences before/after each citation
  4. Extract section headings and location (main text/footnote/dissent)
OUTPUT: List of ALL case law references with full context
COST: ~$0.02 per document
TIME: 5-15 seconds
```

#### **Phase 3: Origin Identification (3-Tier)**
```python
INPUT: Case name, raw citation text, context before/after
ALGORITHM:
  Tier 1 (Dictionary Lookup):
    - Check CITATION_ORIGIN_CACHE first
    - Search KNOWN_FOREIGN_COURTS (80+ courts)
    - Search LANDMARK_CLIMATE_CASES (20+ cases)
    - If found: confidence = 0.95, cost = $0
    
  Tier 2 (Claude Sonnet Analysis):
    - Build prompt with full context
    - Call Sonnet 4.5 for intelligent analysis
    - Parse signals: court name, citation format, case name patterns
    - If confidence ≥ 0.5: accept result
    - Cost: ~$0.01 per citation
    
  Tier 3 (Web Search - Placeholder):
    - Future implementation using search tools
    - For obscure or uncertain cases
    - Expected confidence: 0.6-0.8
    
OUTPUT:
  - origin_country (string)
  - origin_region (Global North/South/International)
  - court_name (string)
  - year (integer)
  - tier_used (1, 2, or 3)
  - confidence_score (0.0-1.0)
  - method (dictionary_match/sonnet_analysis/web_search)
```

#### **Phase 4: Classification**
```python
INPUT: source_jurisdiction, source_region, case_origin, case_region
ALGORITHM:
  1. Normalize jurisdictions (handle aliases)
  2. Compare source vs. cited jurisdiction
  3. Apply classification logic:
     IF source == case_origin:
       RETURN "Domestic" (excluded from results)
     ELIF source_region == "International" OR case_region == "International":
       IF both are International:
         RETURN "International Citation"
       ELSE:
         RETURN "International Citation"
     ELSE:
       RETURN "Foreign Citation"
OUTPUT:
  - citation_type (Foreign/International/Foreign International/Domestic)
  - is_cross_jurisdictional (boolean)
COST: Zero (rule-based)
TIME: Instant
```

### Enhanced Dictionaries (v5)

#### **KNOWN_FOREIGN_COURTS** (80+ entries)
```python
{
    "Court of Session": {
        "country": "Scotland",
        "region": "Global North",
        "type": "Appellate"
    },
    "District Court of The Hague": {
        "country": "Netherlands",
        "region": "Global North",
        "type": "Trial"
    },
    "Norwegian Supreme Court": {
        "country": "Norway",
        "region": "Global North",
        "type": "Supreme"
    },
    "Supreme Court of Colombia": {
        "country": "Colombia",
        "region": "Global South",
        "type": "Supreme"
    },
    "International Court of Justice": {
        "country": "United Nations",
        "region": "International",
        "type": "International"
    },
    # ... 75+ more courts
}
```

**Coverage:**
- European Courts: Netherlands, Norway, UK, Scotland, Ireland, Belgium, Germany, France, Sweden, Finland
- Commonwealth: Canada, New Zealand, Australia, India
- Latin America: Colombia, Brazil, Argentina, Chile
- Africa: South Africa, Kenya
- Asia-Pacific: Philippines, Pakistan, Bangladesh
- International: ICJ, ECtHR, CJEU, IACtHR, ITLOS

#### **LANDMARK_CLIMATE_CASES** (20+ entries)
```python
{
    "Urgenda": {
        "full_name": "Urgenda Foundation v. State of the Netherlands",
        "country": "Netherlands",
        "region": "Global North",
        "year": 2019,
        "court": "Dutch Supreme Court"
    },
    "Massachusetts v. EPA": {
        "full_name": "Massachusetts v. Environmental Protection Agency",
        "country": "United States",
        "region": "Global North",
        "year": 2007,
        "court": "Supreme Court of the United States"
    },
    # ... 18+ more landmark cases
}
```

**Notable Cases:**
- Urgenda (Netherlands)
- Massachusetts v. EPA (USA)
- Juliana v. United States (USA)
- Plan B Earth (UK)
- Mathur v. Ontario (Canada)
- Thomson v Minister (New Zealand)
- Friends of Irish Environment (Ireland)
- Greenpeace Nordic (Norway)
- Neubauer (Germany)
- Klimaatzaak (Belgium)
- Future Generations (Colombia)
- Ashgar Leghari (Pakistan)

### Database Schema (Latest)

#### **citation_extraction_phased** (Individual Citations)
```sql
CREATE TABLE citation_extraction_phased (
    -- Primary Key
    extraction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Foreign Keys
    document_id UUID NOT NULL REFERENCES documents(document_id),
    case_id UUID REFERENCES cases(case_id),
    
    -- Phase 1: Source Jurisdiction
    source_jurisdiction VARCHAR(200),
    source_region VARCHAR(50),  -- Global North/South/International
    
    -- Phase 2: Extraction Results
    case_name VARCHAR(500),
    raw_citation_text TEXT,
    citation_format VARCHAR(100),
    context_before TEXT,
    context_after TEXT,
    section_heading VARCHAR(500),
    location_in_document VARCHAR(50),
    
    -- Phase 3: Origin Identification
    case_law_origin VARCHAR(200),
    case_law_region VARCHAR(50),
    origin_identification_tier INTEGER,
    origin_confidence DECIMAL(3,2),
    
    -- Phase 4: Classification
    citation_type VARCHAR(50),
    is_cross_jurisdictional BOOLEAN,
    
    -- Extended Metadata
    cited_court VARCHAR(500),
    cited_year INTEGER,
    cited_case_citation VARCHAR(500),
    full_paragraph TEXT,
    position_in_document INTEGER,
    start_char_index INTEGER,
    end_char_index INTEGER,
    
    -- Processing Metadata
    phase_2_model VARCHAR(50) DEFAULT 'claude-haiku-4.5',
    phase_3_model VARCHAR(50),
    processing_time_seconds DECIMAL(10,2),
    api_calls_used INTEGER,
    
    -- Quality Control
    requires_manual_review BOOLEAN DEFAULT FALSE,
    manual_review_reason TEXT,
    reviewed_by VARCHAR(100),
    reviewed_at TIMESTAMP,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### **citation_extraction_phased_summary** (Document-Level Stats)
```sql
CREATE TABLE citation_extraction_phased_summary (
    summary_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL UNIQUE REFERENCES documents(document_id),
    
    -- Processing Results
    total_references_extracted INTEGER DEFAULT 0,
    foreign_citations_count INTEGER DEFAULT 0,
    international_citations_count INTEGER DEFAULT 0,
    foreign_international_citations_count INTEGER DEFAULT 0,
    
    -- API Usage
    total_api_calls INTEGER DEFAULT 0,
    total_tokens_input INTEGER DEFAULT 0,
    total_tokens_output INTEGER DEFAULT 0,
    total_cost_usd DECIMAL(10,4) DEFAULT 0.0000,
    
    -- Processing Metadata
    extraction_started_at TIMESTAMP,
    extraction_completed_at TIMESTAMP,
    total_processing_time_seconds DECIMAL(10,2),
    extraction_success BOOLEAN DEFAULT FALSE,
    extraction_error TEXT,
    
    -- Quality Metrics
    average_confidence DECIMAL(3,2),
    items_requiring_review INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 📊 PERFORMANCE METRICS & ACHIEVEMENTS

### Recent Achievements (November 22, 2025)

#### **Citation Extraction v5 Implementation**
- ✅ **Complete 4-phase architecture** designed and implemented
- ✅ **1,650+ lines** of production-ready Python code
- ✅ **80+ foreign courts** in dictionary (massive expansion)
- ✅ **20+ landmark climate cases** tracked
- ✅ **3-tier origin identification** with confidence scoring
- ✅ **12 citation format patterns** supported
- ✅ **Caching system** for repeated lookups
- ✅ **Automatic quality control** with <0.7 confidence flagging
- ✅ **Comprehensive documentation** (6 files, 1,000+ lines)

#### **Expected Performance Improvements**

| Metric | v4 (Old) | v5 (New) | Improvement |
|--------|----------|----------|-------------|
| **Recall** | 40-50% | 75-85% | **+75%** |
| **Precision** | 95% | 85-90% | -5% (acceptable) |
| **Cost/doc** | $0.02-0.05 | $0.02-0.05 | Same |
| **Coverage** | Limited | 80+ courts | Massive |
| **Confidence** | Binary | Granular | Per-tier |

### Cost Analysis

#### **Per Document Costs**
- Phase 1 (Jurisdiction): $0.00 (database lookup)
- Phase 2 (Extraction): $0.015-0.025 (Haiku)
- Phase 3 Tier 1 (Dictionary): $0.00
- Phase 3 Tier 2 (Sonnet): $0.005-0.015 (if needed)
- **Total Average: $0.02-0.05 per document**

#### **Full Dataset Projection (2,924 documents)**
- **Conservative:** $146 (all Tier 2)
- **Realistic:** $88 (60% Tier 1, 40% Tier 2)
- **Optimistic:** $58 (80% Tier 1, 20% Tier 2)
- **Processing Time:** 2-5 hours total

### Data Quality Achievements

- **PDF Downloads:** 99.9% success rate
- **Text Extraction:** 94.1% direct PDF success (no OCR)
- **Classification:** 97-99% accuracy
- **Expected Recall:** 75-85% (vs 40-50% in v4)
- **Expected Precision:** 85-90%

---

## 🎓 ACADEMIC CONTEXT

### Maria Antonia Tigre's Definition (UN Report)
> "The phrase 'Global South' refers broadly to the regions of Latin America and the Caribbean, Asia, Africa and Oceania, and denotes regions that are mostly low-income and often politically or culturally marginalized. However, it must be noted that the Global South is not a homogeneous group of countries, and that legal development and legal capacity vary by country."

### Research Significance

1. **Judicial Dialogue:** Understanding how courts learn from each other across borders
2. **North-South Asymmetries:** Quantifying citation imbalances (29:1 ratio)
3. **Legal Transplantation:** Tracking how legal concepts travel between jurisdictions
4. **Climate Justice:** Examining how Global South voices influence litigation
5. **Methodological Innovation:** Transparent, reproducible AI-assisted analysis

### Thesis Integration

The methodology provides:
- **Transparent 4-phase process** for thesis documentation
- **Reproducible algorithms** with confidence scores
- **Complete audit trail** of all processing decisions
- **Manual review integration** for academic rigor
- **Quantitative metrics** for statistical analysis

---

## 🔑 KEY CONFIGURATION

### config.py Structure

```python
# Database Configuration (Loaded from .env)
DB_CONFIG = {
    'drivername': 'postgresql+psycopg2',
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'climate_litigation'),
    'username': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
}

# Anthropic API
CONFIG = {
    'ANTHROPIC_API_KEY': 'sk-ant-...',
    'ANTHROPIC_MODEL': 'claude-haiku-4-20250514',
    'ANTHROPIC_MODEL_SONNET': 'claude-sonnet-4-20250514',
    'MIN_CONFIDENCE': 0.7
}

# Trial Batch Configuration
TRIAL_BATCH_CONFIG = {
    'ENABLED': True,  # Set to False for full dataset
    'COLUMN_NAME': 'Trial Batch Phase 2',
    'TRUE_VALUES': ['x', 'X', True, 'TRUE', 'true']
}

# File Paths
DATABASE_FILE = Path(__file__).parent / 'baseCompleta.xlsx'
LOGS_DIR = Path(__file__).parent / 'logs'
PDF_DOWNLOAD_DIR = Path(__file__).parent / 'data' / 'pdfs'

# UUID Namespace (for deterministic UUIDs)
UUID_NAMESPACE = uuid.UUID('12345678-1234-5678-1234-567812345678')
```

### Binding Courts Function (International Recognition)

```python
def get_binding_courts(country: str, region: str) -> List[str]:
    """
    Returns list of binding international courts for a jurisdiction.
    
    Used to determine if citations to international tribunals
    should be considered as International Citations.
    """
    binding = ["International Court of Justice"]
    
    if region in ["Europe", "European Union"]:
        binding.extend([
            "Court of Justice of the European Union",
            "European Court of Human Rights"
        ])
    elif region in ["Americas", "Latin America"]:
        binding.append("Inter-American Court of Human Rights")
    elif region == "Africa":
        binding.append("African Court on Human and Peoples' Rights")
    
    return binding
```

---

## 🚦 WORKFLOW & PROCESSING STAGES

### Current Status: Ready for Trial Batch Testing

#### **Completed Workflow:**
1. ✅ Metadata import (baseCompleta.xlsx → PostgreSQL)
2. ✅ PDF downloads (99.9% success)
3. ✅ Text extraction (94.1% direct success)
4. ✅ Document classification (97-99% accuracy)
5. ✅ Citation extraction v5 implementation (code complete)
6. ✅ Database schema v5 (ready to deploy)

#### **Next Steps:**
1. ⏳ Run trial batch (5-10 test documents)
2. ⏳ Verify control group results:
   - Thomson v Minister (should find Urgenda)
   - Plan B Earth (should find Massachusetts v. EPA)
   - Mathur v Ontario (multiple international refs)
   - Friends of Irish Environment (European cases)
   - Greenpeace Nordic (comparative law)
3. ⏳ Full dataset processing (2,924 documents)
4. ⏳ Manual review of flagged citations (confidence <0.7)
5. ⏳ Export for statistical analysis
6. ⏳ Network analysis (Phase 3) - **IN PROGRESS** (Sixfold Analysis Engine)
7. ⏳ Visualization & dashboard (Phase 4) - **IN PROGRESS** (Dashboard & API Server)

### Trial Batch Testing Protocol

**Control Group Documents (5 test cases):**

1. **Thomson v Minister for Climate Change Issues (New Zealand)**
   - File: `thomsonvministerforclimatechangeissues_d2d9bebac91a8d4459fe50ee6b7083b8.pdf`
   - Expected: Urgenda citation (Netherlands)
   - Test: Tier 1 dictionary match, high confidence

2. **R (Plan B Earth) v Prime Minister (United Kingdom)**
   - File: `planbearthandothersvprimeminister_c6834502d9f262036de6b22123356f6e.pdf`
   - Expected: Massachusetts v. EPA citation (USA)
   - Test: Foreign Citation classification

3. **Mathur et al. v Her Majesty the Queen (Canada)**
   - File: `mathuretalvhermajestythequeeninrightofontario_b43295fec7c3835706eff71f4cd83db9_1.pdf`
   - Expected: Multiple international references
   - Test: Mix of Tier 1 and Tier 2

4. **Friends of the Irish Environment CLG (Ireland)**
   - File: `FRIENDS_OF_THE_IRISH_ENVIRONMENT_CLG.pdf`
   - Expected: European case citations
   - Test: International Citation classification

5. **Greenpeace Nordic v Ministry of Petroleum (Norway)**
   - File: `greenpeacenordicassnvministryofpetroleumandenergypeoplevarcticoil_c4546edcd30d144ba35805a6ce08fe26_1.pdf`
   - Expected: Comparative law references
   - Test: Foreign Citation classification

**Success Criteria:**
- ✅ 100% of known citations found
- ✅ <5% false positives
- ✅ Correct classification (Foreign vs International)
- ✅ Average confidence ≥0.85 for dictionary matches
- ✅ Processing time <60 seconds per document
- ✅ Cost <$0.10 per document

---

## 💻 CODE PATTERNS & CONVENTIONS

### Documentation Standard

Every function follows this pattern:
```python
def function_name(param1: Type1, param2: Type2) -> ReturnType:
    """
    Brief description of function purpose.
    
    INPUT:
        - param1: Description of first parameter
        - param2: Description of second parameter
    ALGORITHM:
        1. First step
        2. Second step
        3. Third step
    OUTPUT: Description of return value
    """
    # Implementation
    pass
```

### Error Handling Pattern

```python
try:
    # Main logic
    result = process_data()
    
    # Database operations
    session.add(record)
    session.commit()
    
    # Update statistics
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
    import traceback
    logging.error(traceback.format_exc())
    stats['errors'] += 1
    return False
```

### Logging Standards

```python
logging.info("="*70)
logging.info("MAJOR SECTION TITLE")
logging.info("="*70)
logging.info("Regular information message")
logging.warning("⚠️  Warning message with emoji")
logging.error("❌ Error message with emoji")
logging.info(f"✓ Success message with variable: {value}")
```

### Progress Bars

```python
from tqdm import tqdm

for item in tqdm(items, desc="Processing Items"):
    process_item(item)
```

---

## 📊 ESSENTIAL QUERIES

### Quick Status Check
```sql
SELECT 
    COUNT(*) as total_processed,
    SUM(CASE WHEN extraction_success THEN 1 ELSE 0 END) as successful,
    SUM(foreign_citations_count) as foreign,
    SUM(international_citations_count) as international,
    ROUND(AVG(total_cost_usd), 4) as avg_cost,
    ROUND(SUM(total_cost_usd), 2) as total_cost
FROM citation_extraction_phased_summary;
```

### Tier Performance
```sql
SELECT 
    origin_identification_tier,
    CASE origin_identification_tier
        WHEN 1 THEN 'Dictionary'
        WHEN 2 THEN 'Sonnet'
        WHEN 3 THEN 'Web Search'
        ELSE 'Failed'
    END as tier_name,
    COUNT(*) as citations,
    ROUND(AVG(origin_confidence), 3) as avg_confidence,
    COUNT(*) FILTER (WHERE requires_manual_review) as needs_review
FROM citation_extraction_phased
GROUP BY origin_identification_tier
ORDER BY origin_identification_tier;
```

### Items for Manual Review
```sql
SELECT 
    case_name,
    case_law_origin,
    citation_type,
    origin_confidence,
    origin_identification_tier,
    manual_review_reason
FROM citation_extraction_phased
WHERE requires_manual_review = TRUE
ORDER BY origin_confidence ASC
LIMIT 20;
```

---

## 🚨 CRITICAL REMINDERS FOR AI AGENTS

### When Helping with Code

1. **Always follow INPUT→ALGORITHM→OUTPUT documentation pattern**
2. **Use comprehensive error handling with session.rollback()**
3. **Include detailed logging at all stages**
4. **Update statistics dictionaries consistently**
5. **Use type hints for function parameters and returns**
6. **Follow the established naming conventions**
7. **Test on trial batch before full dataset**
8. **Never skip the control group validation**

### When Modifying Database

1. **Always use UUIDv7 for primary keys**
2. **Include foreign key constraints with CASCADE**
3. **Add indexes on frequently queried columns**
4. **Use TIMESTAMP for all time fields**
5. **Include created_at and updated_at on all tables**
6. **Add UNIQUE constraints where appropriate**
7. **Document all columns with COMMENT ON statements**

### When Working with PDFs

1. **Try pdfplumber first (best for native PDFs)**
2. **Fall back to PyMuPDF if pdfplumber fails**
3. **Use PyPDF2 as last resort**
4. **Only use OCR if all else fails**
5. **Always log extraction method used**
6. **Track extraction success rates**

### When Using LLMs

1. **Haiku for bulk extraction** (cost-effective)
2. **Sonnet for intelligent analysis** (higher accuracy)
3. **Always set temperature=0.0** for reproducibility
4. **Track token usage** for cost analysis
5. **Include retry logic** for API failures
6. **Log raw responses** for debugging
7. **Parse JSON carefully** with fallback extraction

---

## 📂 FILE LOCATIONS FOR AI AGENTS

### Source Files to Reference

**Core Configuration:**
- `/home/gusrodgs/Gus/cienciaDeDados/phdMutley/config.py`

**Database Schema:**
- `/home/gusrodgs/Gus/cienciaDeDados/phdMutley/scripts/phase0/init_database.py`

**Latest Citation Extraction:**
- `/home/gusrodgs/Gus/cienciaDeDados/phdMutley/scripts/5-extract-citations/extract_citations.py`
- `/home/gusrodgs/Gus/cienciaDeDados/phdMutley/scripts/5-extract-citations/citation_extraction_pipeline/migrate_citation_phased_schema.sql`

**Documentation:**
- Available in outputs directory (see recent implementation)
- All documentation files end with _v5.md

### Data Files

**Source Database:**
- `/home/gusrodgs/Gus/cienciaDeDados/phdMutley/data/processed/baseDecisions.xlsx`

**Downloaded PDFs:**
- `/home/gusrodgs/Gus/cienciaDeDados/phdMutley/data/pdfs/`

**Control Group:**
- Files listed in Trial Batch Testing Protocol section above

### Log Files

**All logs in:**
- `/home/gusrodgs/Gus/cienciaDeDados/phdMutley/logs/`

**Key log files:**
- `citation_extraction_v5.log` - Latest extraction results
- `classification.log` - Document classification
- `text_extraction.log` - PDF extraction
- `pdf_download.log` - Download pipeline

---

## 🎯 PRIORITY TASKS

### Immediate (This Week)

1. **Deploy v5 Schema**
   - Run migrate_citation_phased_schema.sql
   - Verify tables and indexes created
   - Test with sample inserts

2. **Trial Batch Testing**
   - Enable trial batch in config.py
   - Mark 5 control documents
   - Run extract_citations_v5_phased.py
   - Verify all known citations found

3. **Validation**
   - Check citation counts match expectations
   - Verify confidence scores reasonable
   - Review tier distribution (target: 60%+ Tier 1)
   - Confirm cost per document <$0.10

### Short-term (Next 2 Weeks)

4. **Full Dataset Processing**
   - Disable trial batch
   - Run on all 2,924 documents
   - Monitor costs and performance
   - Track processing time

5. **Manual Review Workflow**
   - Query citations with confidence <0.7
   - Create review spreadsheet
   - Document patterns in uncertain cases
   - Update dictionaries based on findings

6. **Dictionary Optimization**
   - Find frequently cited courts not in Tier 1
   - Add to KNOWN_FOREIGN_COURTS
   - Expand LANDMARK_CLIMATE_CASES
   - Rerun uncertain cases through Tier 1

### Medium-term (Before December Presentation)

7. **Data Export for Analysis**
   - Export cross-jurisdictional citation network
   - Generate North-South flow matrices
   - Create citation frequency tables
   - Prepare visualization data

8. **Statistical Analysis**
   - Citation patterns by region
   - Network centrality measures
   - Temporal trends (if applicable)
   - North-South asymmetry quantification

9. **Documentation for Thesis**
   - Methodology chapter draft
   - Performance metrics summary
   - Error analysis and handling
   - Limitations and future work

---

## 🔬 RESEARCH INSIGHTS

### Key Findings So Far

1. **Geographic Imbalance:** 96% Global North vs 4% Global South cases
2. **High PDF Quality:** 94.1% directly extractable (better than expected)
3. **Classification Success:** 97-99% accuracy with Sonnet
4. **Cost Efficiency:** Achieved under $0.005/document for classification
5. **v4 Limitations:** Only 40-50% recall highlighted need for v5

### Methodological Innovations

1. **4-Phase Architecture:** Separates extraction from classification
2. **3-Tier Identification:** Balances cost, speed, and accuracy
3. **Confidence Scoring:** Enables quality control and manual review
4. **Caching System:** Reduces redundant API calls
5. **Comprehensive Patterns:** 12 citation formats vs. traditional regex

### Academic Contributions

1. **Transparent AI-Assisted Analysis:** Full audit trail
2. **Reproducible Methodology:** Version-controlled, documented
3. **Quantitative Rigor:** Confidence scores, success rates
4. **Scalable Approach:** Applicable to other legal domains
5. **North-South Focus:** Addresses underrepresented perspective

---

## 💡 TIPS FOR AI AGENTS WORKING ON THIS PROJECT

### Understanding the Context

1. **This is PhD research:** Academic rigor and reproducibility are paramount
2. **Deadline is firm:** November 30, 2025 for December presentation
3. **Budget constraints:** Keep API costs reasonable (<$200 total)
4. **Collaborator Lucas:** Academic focus, I handle all technical implementation
5. **Documentation matters:** Everything must be thesis-worthy

### When Generating Code

- **Always test incrementally:** Don't write 500 lines without testing
- **Use existing patterns:** Follow established conventions in codebase
- **Think about costs:** Prefer Tier 1 (dictionary) over Tier 2 (API calls)
- **Consider the thesis:** Can this methodology be clearly explained?
- **Plan for errors:** Assume PDFs are messy, APIs fail, JSON is malformed

### When Analyzing Results

- **Compare to baselines:** Is v5 better than v4?
- **Check control group:** Do we find known citations?
- **Look at confidence:** Are we sure about our identifications?
- **Consider review burden:** How many need manual inspection?
- **Think about costs:** Is this sustainable for the full dataset?

### When Debugging

- **Check logs first:** Most answers are in log files
- **Query the database:** Verify what actually got saved
- **Test on one document:** Don't debug on the full dataset
- **Simplify the problem:** Isolate which phase is failing
- **Verify assumptions:** Is is_decision actually True?

---

## 🎓 ACADEMIC STANDARDS

### Reproducibility Requirements

1. **Version Everything:** Code, data, models all tracked
2. **Document Decisions:** Why this approach vs. alternatives?
3. **Track Confidence:** How sure are we about each result?
4. **Enable Auditing:** Full processing history in database
5. **Provide Transparency:** Clear methodology for thesis

### Quality Control

1. **Control Group Testing:** Known cases must be found
2. **Manual Review:** Uncertain cases flagged automatically
3. **Error Analysis:** Document what fails and why
4. **Performance Metrics:** Recall, precision, F1 tracked
5. **Cost Accounting:** Every API call logged

### Thesis Integration

The system provides:
- **Methodology Chapter:** 4-phase process fully documented
- **Results Chapter:** Performance metrics, statistics
- **Discussion Chapter:** Error patterns, limitations
- **Appendix:** Technical details, code documentation

---

## 🔐 SECURITY & PRIVACY

### API Keys
- Never commit API keys to version control
- Store in config.py (gitignored)
- Rotate keys if exposed

### Database Credentials
- Use environment variables when possible
- Restrict database access to localhost
- Regular backups to secure location

### PDF Content
- Some documents may contain sensitive information
- Do not expose extracted text publicly
- Respect copyright and fair use

---

## 📈 SUCCESS METRICS TRACKING

### Current Targets

| Metric | Target | Status |
|--------|--------|--------|
| Recall | ≥75% | ⏳ Testing |
| Precision | ≥85% | ⏳ Testing |
| Cost/doc | <$0.10 | ✅ Expected |
| Processing time | <60s/doc | ✅ Expected |
| Tier 1 % | ≥60% | ⏳ TBD |
| Manual review | <20% | ⏳ TBD |

### How to Measure

**Recall:** (Known citations found) / (Total known citations)
- Test on control group with known foreign citations
- Manually verify sample of results

**Precision:** (Correct citations) / (Total extracted)
- Manually review sample of extractions
- Check for false positives

**Cost:** Track from API usage in database
```sql
SELECT AVG(total_cost_usd) FROM citation_extraction_phased_summary;
```

**Tier Distribution:** Query Phase 3 results
```sql
SELECT origin_identification_tier, COUNT(*) 
FROM citation_extraction_phased 
GROUP BY origin_identification_tier;
```

---

## 🎉 PROJECT MILESTONES

### Completed ✅

- [x] Infrastructure setup (PostgreSQL 18, Python 3.13)
- [x] Metadata import (2,924 cases)
- [x] PDF download pipeline (99.9% success)
- [x] Text extraction pipeline (94.1% direct success)
- [x] Document classification (97-99% accuracy)
- [x] Citation extraction v4 (baseline established)
- [x] Citation extraction v5 design
- [x] V5 implementation (complete 4-phase system)
- [x] Enhanced dictionaries (80+ courts, 20+ cases)
- [x] Database schema v5
- [x] Comprehensive documentation

### In Progress ⏳

- [ ] V5 trial batch testing
- [ ] Control group validation
- [ ] Dictionary optimization based on results

### Upcoming 📅

- [ ] Full dataset processing (2,924 documents)
- [ ] Manual review workflow
- [ ] Citation network analysis
- [ ] Statistical analysis for thesis
- [ ] Visualization and dashboard
- [ ] Final thesis integration

---

## 📞 SUPPORT FOR AI AGENTS

### When You Need Help

**Technical Questions:**
- Reference the code in scripts/phase2/
- Check logs in logs/ directory
- Query database for actual state

**Academic Questions:**
- This is doctoral research in law
- Focus: climate litigation, judicial dialogue
- Geographic: Global North vs. Global South
- Approach: Quantitative citation analysis

**Project Questions:**
- Everything is in this context file
- All code follows established patterns
- Documentation is comprehensive
- When in doubt, ask before coding

### What Not to Do

❌ **Don't skip trial batch testing**
❌ **Don't ignore confidence scores**
❌ **Don't forget to update statistics**
❌ **Don't commit sensitive data**
❌ **Don't break the database schema**
❌ **Don't ignore the academic context**
❌ **Don't sacrifice reproducibility for speed**

### What Always to Do

✅ **Always test on trial batch first**
✅ **Always log everything**
✅ **Always handle errors gracefully**
✅ **Always document your reasoning**
✅ **Always update statistics tracking**
✅ **Always consider the thesis**
✅ **Always check the control group**

---

## 🏁 CONCLUSION FOR AI AGENTS

You are working on a **PhD research project** analyzing **cross-border judicial citations in climate litigation**. The technical implementation is complete and ready for testing.

**Your role:** Help deploy, test, debug, optimize, and analyze the citation extraction system while maintaining academic rigor and reproducibility.

**Key principle:** Transparent, reproducible, thesis-worthy methodology above all else.

**Current status:** Citation Extraction v5 complete, ready for trial batch testing.

**Next critical step:** Deploy schema, run trial batch on 5 control documents, verify known citations found.

**Success = PhD success:** This research contributes to understanding how legal knowledge flows between Global North and South in climate litigation.

---

**Context File Version:** 1.0  
**Last Updated:** November 22, 2025  
**Status:** Complete and Ready for AI Agent Use  
**Optimized for:** Gemini, GPT-4, Claude, and other IDE-integrated AI assistants

---

**Good luck helping Gustavo complete his PhD! 🎓✨**
