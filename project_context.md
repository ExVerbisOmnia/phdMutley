# phdMutley Project - Claude Code Context Documentation

**Version:** 4.0
**Last Updated:** November 20, 2025
**Project Deadline:** November 30, 2025 (for December presentation)
**Working Directory:** `/home/gusrodgs/Gus/cienciaDeDados/phdMutley`
**Repository:** https://github.com/ExVerbisOmnia/phdMutley

**Major Update:** Phase 2 (Citation Extraction) implementation using Claude Haiku API for cost-effective, high-quality citation extraction

---

## Table of Contents
1. [Project Overview](#project-overview)
2. [Team Structure & Collaboration](#team-structure--collaboration)
3. [Current Project State](#current-project-state)
4. [Database Architecture](#database-architecture)
5. [Code Standards & Conventions](#code-standards--conventions)
6. [Key Methodological Decisions](#key-methodological-decisions)
7. [Development Environment](#development-environment)
8. [File Structure & Organization](#file-structure--organization)
9. [Next Steps & Roadmap](#next-steps--roadmap)
10. [Important Context & Constraints](#important-context--constraints)

---

## 1. Project Overview

### Academic Objectives
**phdMutley** is a doctoral thesis project analyzing citation patterns in climate litigation cases between Global North and Global South jurisdictions. The research aims to quantify how courts reference decisions from other jurisdictions, with particular focus on understanding citation flows across different legal systems.

### Research Questions
- How frequently do Global North courts cite other Global North courts?
- How frequently do Global South courts cite Global North courts?
- How frequently (if at all) do Global North courts cite Global South courts?
- What patterns emerge in transnational judicial citation networks?

### Global South Definition
Following Maria Antonia Tigre (Columbia University) in the UN Global Climate Litigation Report 2023:

> "The phrase 'Global South' refers broadly to the regions of Latin America and the Caribbean, Asia, Africa and Oceania, and denotes regions that are mostly low-income and often politically or culturally marginalized. However, it must be noted that the Global South is not a homogeneous group of countries, and that legal development and legal capacity vary by country."

### Data Source
- **Primary Database:** Climate Case Chart (Columbia University & LSE)
- **Methodology Documentation:** https://www.climatecasechart.com/methodology
- **Original Dataset:** 15,180 documents
- **Filtered Dataset:** 2,924 judicial decisions (court decisions only, no procedural documents)
- **Access:** Notion workspace "Doutorado PM" shared by Lucas Biasetton

---

## 2. Team Structure & Collaboration

### Roles & Responsibilities

**Gustavo (Gus)**
- **Focus:** All technical implementation
- **Responsibilities:**
  - Data processing and cleaning
  - Environment setup and configuration
  - PDF extraction and text processing
  - Database design and management
  - Script development and testing
  - Code documentation
  - Repository management

**Lucas Biasetton (Mutley)**
- **Focus:** Academic research and analysis
- **Responsibilities:**
  - Jurisdictional taxonomy development
  - Citation pattern research methodology
  - Academic documentation
  - Thesis writing
  - Validation of findings
  - Research literature review

### Collaboration Principles
1. **Strict Separation:** Gus handles ALL tech; Lucas handles ALL academic analysis
2. **No Crossover:** Lucas does not code; Gus does not make methodological academic decisions
3. **Communication:** Technical findings are reported to Lucas for academic interpretation
4. **Documentation:** Both maintain separate documentation streams (technical vs. methodological)

---

## 3. Current Project State

### ✅ Completed Phases

#### Phase 0: Foundation (COMPLETE)
- ✅ Environment setup with Python 3.13.9
- ✅ Virtual environment with 80+ specialized libraries
- ✅ Git repository configured and connected to GitHub
- ✅ PostgreSQL 18 database installed and configured
- ✅ Directory structure established
- ✅ Exploratory data analysis completed

#### Phase 1: Data Processing (COMPLETE)
- ✅ CSV data cleaning and filtering
- ✅ Jurisdictional taxonomy classification (North/South Global)
- ✅ 2,924 judicial decisions identified and isolated
- ✅ North-South asymmetry discovered: 96% North vs 3.3% South (29:1 ratio)
- ✅ Data quality assessment: 99.9% URL availability

#### Phase 2: PDF Processing & Database Integration (COMPLETE - ROBUST VERSION 2.0)
- ✅ Hierarchical PDF extraction pipeline implemented (pdfplumber → PyMuPDF → PyPDF2)
- ✅ **ROBUST PIPELINE ARCHITECTURE** implemented (November 14, 2025)
  - ✅ Single source of truth: All scripts use `baseDecisions.xlsx`
  - ✅ Document ID matching: Unique identifiers for each document
  - ✅ Deterministic UUIDs: Consistent across all scripts
  - ✅ Database-first approach: Query existing records instead of creating duplicates
  - ✅ Zero data inconsistencies: No "Unknown" values, no duplicate records
- ✅ **Pipeline validated with test run:**
  - 8 cases with complete metadata (100%)
  - 15 documents with complete metadata (100%)
  - 13 PDFs downloaded (86.7% - 2 unavailable at source)
  - 13 texts extracted (100% success on available PDFs)
- ✅ Automatic scanned PDF detection
- ✅ Quality metrics and assessment (92.3% excellent, 7.7% good quality)
- ✅ Comprehensive error handling and retry logic
- ✅ Progress tracking and logging
- ✅ PostgreSQL 18 schema with proper relationships
- ✅ Deterministic UUID generation for consistency
- ✅ CASCADE rules for dependency management
- ✅ Text extraction records integrated with quality metrics

#### Phase 3: Citation Extraction (IN PROGRESS - November 2025)
**Objective:** Extract foreign and international court citations from judicial decisions using LLM-powered analysis

**Key Methodological Decisions:**
- ✅ **Model Selection:** Claude Haiku (claude-3-5-haiku-20241022)
  - Cost-effective: $0.25/1M input tokens, $1.25/1M output tokens
  - Estimated total cost: ~$29 for full dataset (vs $346 with Sonnet)
  - High-quality output with structured JSON responses
  
- ✅ **Citation Scope:** Foreign and international citations only
  - Excludes domestic citations (e.g., US court citing another US court)
  - Focuses on transnational judicial dialogue
  - Captures international tribunal and court citations
  
- ✅ **Database Schema:** Citations table with flexible structure
  ```sql
  CREATE TABLE citations (
      citation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      document_id UUID NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
      citation_text TEXT NOT NULL,              -- Full citation as it appears in text
      cited_jurisdiction TEXT,                  -- Jurisdiction of cited court
      cited_court_name TEXT,                    -- Name of cited court
      cited_case_name TEXT,                     -- Case name (may be NULL)
      cited_year INTEGER,                       -- Year of cited decision
      citation_type TEXT,                       -- 'foreign' or 'international'
      context_snippet TEXT,                     -- Surrounding text for context
      extraction_confidence TEXT,               -- 'high', 'medium', 'low'
      raw_llm_response JSONB,                  -- Complete LLM response for audit
      extraction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      notes TEXT                               -- Any additional observations
  );
  ```
  - **Key Design Decision:** `cited_case_name` can be NULL
  - Many citations reference courts without specific case names
  - Captures citations like "Brazilian Supreme Court", "European Court of Human Rights"
  
- ✅ **Extraction Pipeline:** Structured JSON prompt with Claude API
  - Comprehensive schema definition
  - Examples demonstrating both case-specific and general citations
  - Emphasis on foreign/international distinction
  - Context preservation for analysis
  - Full response storage for reproducibility

**Implementation Status:**
- ✅ Citations table initialized with proper constraints
- ✅ Extraction script (`extract_citations_phase2.py`) developed
  - Batch processing with progress tracking
  - Comprehensive error handling and retry logic
  - Cost tracking for budget monitoring
  - JSON validation and data quality checks
- ✅ Integration with existing pipeline
- 🔄 Testing phase with sample documents
- ⏳ Full dataset processing pending validation

**Scripts Created:**
- `scripts/phase2/initialize_citations_table.py` - Database schema creation
- `scripts/phase2/extract_citations_phase2.py` - Citation extraction pipeline

### 🔄 Current Phase: Phase 2 - Citation Extraction (IN PROGRESS)

**Status:** Implementing LLM-powered citation extraction using Claude Haiku
**Current Progress:**
- ✅ Citations database schema designed and implemented
- ✅ Claude API integration configured (Haiku model)
- ✅ Citation extraction pipeline with structured JSON prompts
- ✅ Cost-effective approach: ~$29 for full dataset (vs $346 with Sonnet)
- ✅ Comprehensive error handling and retry logic
- 🔄 Initial testing on sample documents
- ⏳ Full dataset processing pending

**Next Immediate Steps:**
1. Complete initial testing with 15-20 sample documents
2. Validate citation extraction quality and accuracy
3. Process full dataset (~2,900 documents)
4. Analyze extracted citations for North-South patterns
5. Generate visualizations and statistical reports

### Key Finding Requiring Methodological Adjustment
**North-South Asymmetry:** The dataset contains a 29:1 ratio of North to South decisions (2,800 North vs 96 South). This significant imbalance requires careful methodological consideration:
- Cannot perform simple statistical comparisons
- Must adjust research questions to account for asymmetry
- May need qualitative analysis to supplement quantitative findings
- Lucas is responsible for determining adjusted methodology

---

## 4. Database Architecture

### PostgreSQL 18 Configuration

**Database Name:** `climate_litigation` (updated from `climate_litigation_phd`)
**Owner:** `phdmutley`
**Port:** 5432 (default)
**Character Encoding:** UTF8
**Authentication:** Password-based (host: localhost)

### Modern PostgreSQL 18 Features in Use
1. **UUIDv7 Primary Keys:** Chronologically sortable UUIDs for better performance
2. **AIO Subsystem:** Asynchronous I/O for improved query performance
3. **Advanced Indexing:** Optimized indexes for citation analysis queries
4. **JSON Support:** Flexible storage for metadata and extracted sections

### Schema Overview

```sql
-- Core tables with relationships
cases → documents → extracted_texts → text_sections
                 ↓           ↓
           keywords_tags  citations (NEW - Phase 3)
```

#### Table: `cases`
**Purpose:** Store case-level information from Climate Case Chart

```sql
CREATE TABLE cases (
    case_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_name TEXT NOT NULL,
    jurisdiction TEXT,
    jurisdiction_classification TEXT, -- 'Global North' or 'Global South'
    court_level TEXT,
    date_filed DATE,
    date_decided DATE,
    case_status TEXT,
    case_category TEXT,
    climate_change_laws_url TEXT UNIQUE,
    climate_case_chart_url TEXT,
    sabin_center_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_cases_jurisdiction ON cases(jurisdiction);
CREATE INDEX idx_cases_classification ON cases(jurisdiction_classification);
CREATE INDEX idx_cases_date_decided ON cases(date_decided);
```

#### Table: `documents`
**Purpose:** Store document-level information for each case

```sql
CREATE TABLE documents (
    document_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    document_type TEXT NOT NULL, -- 'Decision', 'Order', 'Opinion', etc.
    document_title TEXT,
    document_date DATE,
    document_url TEXT,
    pdf_filename TEXT,
    pdf_download_status TEXT, -- 'success', 'failed', 'pending'
    pdf_download_date TIMESTAMP,
    pdf_file_size_kb INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(case_id, document_url)
);

-- Indexes
CREATE INDEX idx_documents_case_id ON documents(case_id);
CREATE INDEX idx_documents_type ON documents(document_type);
CREATE INDEX idx_documents_download_status ON documents(pdf_download_status);
```

#### Table: `extracted_texts`
**Purpose:** Store extracted text content and quality metrics from PDFs

```sql
CREATE TABLE extracted_texts (
    extraction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    full_text TEXT,
    extraction_method TEXT, -- 'pdfplumber', 'pymupdf', 'pypdf2'
    extraction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Quality Metrics
    total_pages INTEGER,
    total_characters INTEGER,
    is_scanned_pdf BOOLEAN,
    avg_chars_per_page DECIMAL(10,2),
    quality_score DECIMAL(3,2), -- 0.00 to 1.00
    
    -- Processing Status
    processing_status TEXT DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    error_message TEXT,
    
    -- Metadata
    language_detected TEXT,
    metadata_json JSONB, -- Flexible storage for PDF metadata
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(document_id)
);

-- Indexes
CREATE INDEX idx_extracted_texts_document_id ON extracted_texts(document_id);
CREATE INDEX idx_extracted_texts_quality ON extracted_texts(quality_score);
CREATE INDEX idx_extracted_texts_status ON extracted_texts(processing_status);
CREATE INDEX idx_extracted_texts_scanned ON extracted_texts(is_scanned_pdf);
```

#### Table: `text_sections`
**Purpose:** Store hierarchical sections of extracted text for structured analysis

```sql
CREATE TABLE text_sections (
    section_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extraction_id UUID NOT NULL REFERENCES extracted_texts(extraction_id) ON DELETE CASCADE,
    section_type TEXT, -- 'header', 'introduction', 'facts', 'analysis', 'conclusion', 'citation'
    section_order INTEGER,
    section_text TEXT,
    page_number INTEGER,
    confidence_score DECIMAL(3,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_text_sections_extraction_id ON text_sections(extraction_id);
CREATE INDEX idx_text_sections_type ON text_sections(section_type);
CREATE INDEX idx_text_sections_order ON text_sections(section_order);
```

#### Table: `citations` (NEW - Phase 3)
**Purpose:** Store extracted citations to foreign and international courts from judicial decisions

```sql
CREATE TABLE citations (
    citation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    
    -- Citation Content
    citation_text TEXT NOT NULL,              -- Full citation as it appears in text
    cited_jurisdiction TEXT,                  -- Jurisdiction of cited court (e.g., "Brazil", "European Union")
    cited_court_name TEXT,                    -- Name of cited court (e.g., "Supreme Federal Court")
    cited_case_name TEXT,                     -- Case name if available (CAN BE NULL)
    cited_year INTEGER,                       -- Year of cited decision
    
    -- Classification
    citation_type TEXT CHECK (citation_type IN ('foreign', 'international')),
    
    -- Context and Quality
    context_snippet TEXT,                     -- Surrounding text for analysis
    extraction_confidence TEXT CHECK (extraction_confidence IN ('high', 'medium', 'low')),
    
    -- Audit Trail
    raw_llm_response JSONB,                  -- Complete LLM response for reproducibility
    extraction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,                               -- Any additional observations
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for citation analysis
CREATE INDEX idx_citations_document_id ON citations(document_id);
CREATE INDEX idx_citations_jurisdiction ON citations(cited_jurisdiction);
CREATE INDEX idx_citations_type ON citations(citation_type);
CREATE INDEX idx_citations_year ON citations(cited_year);
CREATE INDEX idx_citations_confidence ON citations(extraction_confidence);
```

**Design Notes:**
- `cited_case_name` is nullable because many citations reference courts without specific cases
  - Example: "Brazilian Supreme Court" or "European Court of Human Rights"
  - Captures both case-specific and general court citations
- `raw_llm_response` stores complete API response for audit and reproducibility
- Extraction confidence helps identify citations requiring validation
- Context snippet preserved for qualitative analysis

#### Table: `keywords_tags`
**Purpose:** Store extracted keywords and tags for analysis

```sql
CREATE TABLE keywords_tags (
    keyword_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    keyword TEXT NOT NULL,
    keyword_type TEXT, -- 'legal_concept', 'statute', 'case_citation', 'entity', etc.
    frequency INTEGER DEFAULT 1,
    relevance_score DECIMAL(3,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_keywords_document_id ON keywords_tags(document_id);
CREATE INDEX idx_keywords_keyword ON keywords_tags(keyword);
CREATE INDEX idx_keywords_type ON keywords_tags(keyword_type);
```

### Key Database Conventions

1. **UUID Generation:** All primary keys use `gen_random_uuid()` for UUIDv7 compatibility
2. **Timestamps:** All tables include `created_at` and `updated_at` timestamps
3. **ON DELETE CASCADE:** Ensures referential integrity when parent records are deleted
4. **UNIQUE Constraints:** Prevent duplicate entries (e.g., same document URL for a case)
5. **Indexes:** Strategic indexing on foreign keys and frequently queried columns
6. **JSONB for Flexibility:** Use JSONB for metadata that may evolve

### Database Connection Pattern

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Connection string format
DATABASE_URL = "postgresql://gusrodgs:password@localhost:5432/climate_litigation_phd"

# Create engine
engine = create_engine(DATABASE_URL, echo=False)

# Create session factory
SessionLocal = sessionmaker(bind=engine)

# Usage in scripts
with SessionLocal() as session:
    # Your database operations here
    session.commit()
```

---

## 5. Code Standards & Conventions

### General Principles

1. **Academic Reproducibility First:** Transparent algorithms over AI black-box processing
2. **Comprehensive Documentation:** Every methodology decision must be documented
3. **Incremental Testing:** Small samples (15 test cases) before full dataset processing
4. **Error Handling:** All scripts include retry logic and comprehensive error handling
5. **Beginner-Friendly:** Explicit working directory contexts in all instructions

### Code Comment Standards

**CRITICAL:** Every script must include block or inline comments before every relevant piece of code explaining:
- **Input:** What data/parameters the code receives
- **Algorithm:** What the code does and how it does it
- **Output:** What the code produces or returns

```python
# Example of proper commenting style:

# INPUT: List of PDF file paths
# ALGORITHM: Iterates through each PDF and attempts extraction with pdfplumber
# OUTPUT: Dictionary with extracted text and quality metrics
def extract_text_from_pdfs(pdf_paths):
    results = {}
    
    for pdf_path in pdf_paths:
        # Check if file exists before processing
        if not os.path.exists(pdf_path):
            continue
            
        # Try extraction with pdfplumber (primary method)
        try:
            with pdfplumber.open(pdf_path) as pdf:
                # Extract text from all pages
                text = ""
                for page in pdf.pages:
                    text += page.extract_text() or ""
                    
                results[pdf_path] = {
                    'text': text,
                    'pages': len(pdf.pages),
                    'method': 'pdfplumber'
                }
        except Exception as e:
            # Log error and try fallback method
            logging.error(f"pdfplumber failed for {pdf_path}: {e}")
            results[pdf_path] = extract_with_fallback(pdf_path)
    
    return results
```

### Script Organization Standards

#### File Naming Convention
```
phase[X]_[sequential_number]_[descriptive_name].py

Examples:
- phase0_01_environment_check.py
- phase1_02_data_cleaning.py
- phase2_01_pdf_extraction_pipeline.py
```

#### Script Header Template

```python
"""
Script: phase[X]_[number]_[name].py
Purpose: [Clear description of what this script does]
Author: Gustavo (gusrodgs)
Created: [Date]
Last Modified: [Date]

Input:
- [Describe input files, database tables, or parameters]

Process:
- [High-level overview of the algorithm/steps]

Output:
- [Describe what files/data are created]

Dependencies:
- [List key libraries and their purpose]

Usage:
    python phase[X]_[number]_[name].py [arguments]
    
Notes:
- [Any important considerations or limitations]
"""
```

#### Logging Standards

All scripts must include comprehensive logging:

```python
import logging
from datetime import datetime

# Configure logging
log_filename = f"phase[X]_[name]_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/{log_filename}'),
        logging.StreamHandler()  # Also print to console
    ]
)

# Use throughout script
logging.info("Starting processing...")
logging.warning("Potential issue detected...")
logging.error("Error occurred...")
logging.debug("Detailed debug information...")
```

### Error Handling Pattern

```python
import time

def process_with_retry(item, max_retries=3):
    """
    Process item with automatic retry logic
    
    INPUT: Item to process, maximum retry attempts
    ALGORITHM: Try processing, retry on failure with exponential backoff
    OUTPUT: Processed result or None on total failure
    """
    for attempt in range(max_retries):
        try:
            # Attempt processing
            result = process_item(item)
            logging.info(f"Successfully processed {item}")
            return result
            
        except Exception as e:
            wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
            logging.warning(f"Attempt {attempt + 1} failed for {item}: {e}")
            
            if attempt < max_retries - 1:
                logging.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                logging.error(f"All {max_retries} attempts failed for {item}")
                return None
```

### Progress Tracking Pattern

```python
from tqdm import tqdm

def process_batch(items):
    """
    Process items with progress tracking
    
    INPUT: List of items to process
    ALGORITHM: Iterate through items with visual progress bar
    OUTPUT: List of results
    """
    results = []
    
    # Use tqdm for progress tracking
    for item in tqdm(items, desc="Processing items", unit="item"):
        result = process_item(item)
        results.append(result)
        
        # Optional: Save intermediate results every 100 items
        if len(results) % 100 == 0:
            save_checkpoint(results)
            logging.info(f"Checkpoint: {len(results)} items processed")
    
    return results
```

---

## 6. Robust Pipeline Architecture (Version 2.0 - November 14, 2025)

### Overview

The robust pipeline implementation solved critical data consistency issues discovered during initial testing. The new architecture ensures zero data inconsistencies through deterministic UUID matching and a single source of truth.

### Problem Identified (Original Implementation)

**Issue:** Inconsistent data in PostgreSQL database when running test with 15 documents
- Scripts used different data sources (`baseCompleta.xlsx` vs `baseDecisions.xlsx`)
- PDFs named by Case ID (not unique - one case can have multiple documents)
- Matching by case name (fragile and error-prone)
- Created "Unknown" cases when matching failed
- Result: 16 cases instead of 8, with incomplete metadata

### Solution: Robust Pipeline Architecture

#### Core Principles

1. **Single Source of Truth**
   - All scripts use `baseDecisions.xlsx` exclusively
   - No mixing of data sources
   - Consistent field names and structure

2. **Unique Document Identification**
   - PDFs named by Document ID: `doc_{document_id}.pdf`
   - Document ID is unique per document (unlike Case ID)
   - Prevents filename collisions

3. **Deterministic UUID Generation**
   - Same UUID generation logic across all scripts
   - UUID5 with project namespace: `uuid5(NAMESPACE_DNS, 'climatecasechart.com.phdmutley')`
   - Guarantees consistent UUIDs across multiple runs

4. **Database-First Approach**
   - Query existing records instead of creating new ones
   - No duplicate or "Unknown" records
   - Referential integrity maintained

#### Pipeline Flow

```
baseDecisions.xlsx (Single Source of Truth)
    ↓
Step 1: populate_metadata.py
    │   - Reads first 15 rows (TEST_MODE=True)
    │   - Generates deterministic UUIDs: uuid5(namespace, f"case_{case_id}")
    │   - Creates 8 cases with complete metadata
    │   - Creates 15 documents with complete metadata
    │   - Result: All fields populated, zero "Unknown" values
    ↓
Step 2: download_decisions_v2.py
    │   - Reads same 15 rows from baseDecisions.xlsx
    │   - Creates filename: doc_{document_id}.pdf (unique per document)
    │   - Downloads 13 PDFs successfully (2 unavailable at source - 404 errors)
    │   - Result: 13 PDFs with predictable, unique filenames
    ↓
Step 3: extract_text_v2.py
    │   - Finds PDFs in folder
    │   - Extracts document_id from filename
    │   - Generates same deterministic UUID: uuid5(namespace, f"document_{doc_id}")
    │   - Queries existing document record by UUID
    │   - Adds extracted_text record linked to document
    │   - Result: 13 extracted texts, all properly linked
    ↓
Result: Clean Database
    - 8 cases (100% complete metadata)
    - 15 documents (100% complete metadata)
    - 13 extracted_text records (100% success on available PDFs)
    - 0 "Unknown" values
    - 0 duplicate records
```

#### UUID Generation (Consistent Across All Scripts)

```python
from uuid import uuid5, NAMESPACE_DNS

# Project namespace (shared by all scripts)
UUID_NAMESPACE = uuid5(NAMESPACE_DNS, 'climatecasechart.com.phdmutley')

def generate_case_uuid(case_id_str):
    """Generate deterministic UUID for a case."""
    clean_id = str(case_id_str).strip().lower()
    return uuid5(UUID_NAMESPACE, f"case_{clean_id}")

def generate_document_uuid(document_id_str):
    """Generate deterministic UUID for a document."""
    clean_id = str(document_id_str).strip().lower()
    return uuid5(UUID_NAMESPACE, f"document_{clean_id}")
```

### Validation Results

**Test Run (November 14, 2025 - 15 entries):**
- Metadata population: 100% success (8 cases, 15 documents)
- PDF downloads: 86.7% success (13/15 - limited by source availability)
- Text extraction: 100% success (13/13 PDFs processed)
- Data quality: 92.3% excellent, 7.7% good
- Inconsistencies: 0 (zero "Unknown" values, zero duplicates)

**Key Metrics:**
- Total words extracted: ~430,000 words
- Total pages processed: ~1,067 pages
- Processing time: ~200 seconds for complete pipeline
- Estimated full dataset time: ~14 hours (2,924 documents)

### Scripts Modified/Created

1. **download_decisions_v2.py** (modified)
   - Changed data source to `baseDecisions.xlsx`
   - Changed filename format to `doc_{document_id}.pdf`
   - Added Document ID column validation

2. **extract_text_v2.py** (new)
   - Complete rewrite with robust matching logic
   - Uses deterministic UUIDs matching `populate_metadata.py`
   - Queries existing documents instead of creating new ones
   - Better error handling and logging

3. **populate_metadata.py** (no changes)
   - Already using correct deterministic UUID generation
   - Already using `baseDecisions.xlsx`

### Documentation Generated

1. **TEST_PIPELINE_VALIDATION_REPORT.md**
   - Initial analysis of data inconsistency issue
   - Root cause identification
   - Proposed solutions

2. **ROBUST_PIPELINE_SUCCESS_REPORT.md**
   - Complete validation of robust pipeline
   - Performance metrics
   - Success criteria verification
   - Production readiness assessment

### Production Ready Status

✅ **Pipeline validated and ready for full dataset processing**
- All scripts aligned with single source of truth
- Zero data inconsistencies
- 100% text extraction success rate (on available PDFs)
- Deterministic and reproducible
- Ready to scale to 2,924 documents

---

## 7. Key Methodological Decisions

### PDF Processing Strategy

**Decision:** Hierarchical extraction pipeline with automatic fallback
**Rationale:** Different PDFs require different extraction methods for optimal quality

```
Primary: pdfplumber (best for text-based PDFs)
    ↓ (if fails)
Fallback 1: PyMuPDF (faster, handles some edge cases)
    ↓ (if fails)
Fallback 2: PyPDF2 (most robust, handles damaged PDFs)
```

**Quality Assessment Criteria:**
- Characters per page (threshold: >100 chars/page = high quality)
- Total pages extracted
- Automatic scanned PDF detection (triggers warning, not OCR)
- Quality score: 0.00 to 1.00 based on multiple factors

### OCR Decision

**Decision:** NO automatic OCR processing
**Rationale:**
- Only ~6% of documents are scanned PDFs (much lower than initial 20% estimate)
- OCR is expensive (time and potentially cost)
- Manual review required for academic rigor
- Scanned PDFs are flagged for potential manual processing later

**Implementation:**
```python
# Flag scanned PDFs but do not process
if avg_chars_per_page < 50:  # Threshold indicating scanned PDF
    is_scanned = True
    quality_score = 0.0
    logging.warning(f"Scanned PDF detected: {filename}")
```

### North-South Asymmetry Approach

**Problem:** 96% North vs 3.3% South (29:1 ratio)
**Impact:** Cannot perform standard statistical comparisons

**Adapted Research Focus:**
1. **Descriptive Analysis:** Focus on describing patterns rather than testing hypotheses
2. **Network Analysis:** Visualize citation flows to identify patterns
3. **Qualitative Depth:** Supplement quantitative findings with detailed case analysis
4. **Expectation Management:** Clearly communicate limitations in thesis

**Lucas's Responsibility:** Final determination of adjusted methodology

### Citation Detection Strategy (IMPLEMENTED - Phase 3)

**Approach:** LLM-powered citation extraction using Claude Haiku API

**Method Selection Rationale:**
- Traditional regex patterns insufficient for diverse international citation formats
- Named Entity Recognition (NER) struggles with legal citation complexity
- LLM approach provides:
  - Contextual understanding of citations
  - Flexibility across different legal traditions
  - Ability to distinguish between mere mentions and actual citations
  - Cost-effective processing with Haiku model

**Implementation Details:**

1. **Model:** Claude 3.5 Haiku (claude-3-5-haiku-20241022)
   - Cost: $0.25/1M input tokens, $1.25/1M output tokens
   - Estimated total cost for full dataset: ~$29 (vs $346 with Sonnet)
   - High-quality structured output with JSON responses

2. **Structured JSON Prompt:**
   ```json
   {
     "citations": [
       {
         "citation_text": "...",
         "cited_jurisdiction": "...",
         "cited_court_name": "...",
         "cited_case_name": "...",  // Can be null
         "cited_year": ...,
         "citation_type": "foreign" | "international",
         "context_snippet": "...",
         "extraction_confidence": "high" | "medium" | "low"
       }
     ]
   }
   ```

3. **Citation Scope:**
   - **Includes:** Foreign court citations (e.g., US court citing Brazilian court)
   - **Includes:** International tribunal/court citations (ICJ, ECHR, etc.)
   - **Excludes:** Domestic citations (e.g., US court citing another US court)
   - **Rationale:** Focus on transnational judicial dialogue

4. **Quality Assurance:**
   - Confidence scoring for each citation
   - Context preservation for validation
   - Full LLM response stored for audit trail
   - Batch processing with error handling
   - Cost tracking for budget monitoring

5. **Processing Pipeline:**
   ```
   extracted_text → Claude API (Haiku) → JSON response → Parse & Validate → Store in citations table
   ```

**Test → Validate → Scale Pattern:**
- ✅ Test on 15-20 sample documents
- 🔄 Validate extraction quality and accuracy
- ⏳ Refine prompts based on edge cases
- ⏳ Scale to full dataset (2,924 documents)

---

## 7. Development Environment

### System Specifications

**Operating System:** Ubuntu/Linux  
**Python Version:** 3.13.9  
**PostgreSQL Version:** 18  
**IDE:** VSCode with Claude Code integration  
**Working Directory:** `/home/gusrodgs/Gus/cienciaDeDados/phdMutley`

### Virtual Environment Activation

```bash
# Method 1: Standard activation
cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley
source venv/bin/activate

# Method 2: Quick activation script
./activate.sh

# Verify activation
which python  # Should show path in venv
python --version  # Should show 3.13.9
```

### Key Libraries Installed (80+ total)

**Data Processing:**
- pandas, numpy, openpyxl
- sqlalchemy, psycopg2-binary

**PDF Processing:**
- PyPDF2, pdfplumber, pymupdf (fitz)

**Text Analysis:**
- spacy (models: en_core_web_sm, en_core_web_lg)
- langdetect, textblob
- nltk

**Network Analysis:**
- networkx, python-louvain
- scipy, statsmodels, scikit-learn

**Visualization:**
- matplotlib, seaborn, plotly, pyvis

**Development:**
- jupyterlab, notebook
- requests, beautifulsoup4
- tqdm, rich (progress bars)

**Utilities:**
- python-dotenv (environment variables)
- logging, json, csv

### Environment Variables (.env file)

```bash
# Database Configuration (UPDATED November 14, 2025)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=climate_litigation
DB_USER=phdmutley
DB_PASSWORD=197230

# API Keys
ANTHROPIC_API_KEY=your_anthropic_key_here  # Required for Phase 2 citation extraction
# OPENAI_API_KEY=your_key_here  # Optional, not currently used

# Paths
PROJECT_ROOT=/home/gusrodgs/Gus/cienciaDeDados/phdMutley
PDF_DOWNLOAD_DIR=/home/gusrodgs/Gus/cienciaDeDados/phdMutley/scripts/phase1/pdfs/downloaded
EXTRACTION_OUTPUT_PATH=/home/gusrodgs/Gus/cienciaDeDados/phdMutley/data/processed

# Logging
LOG_LEVEL=INFO
LOG_FILE=/home/gusrodgs/Gus/cienciaDeDados/phdMutley/logs/database.log
```

### Database Connection Verification

```bash
# Test PostgreSQL connection (use -h localhost for password auth)
PGPASSWORD=197230 psql -h localhost -U phdmutley -d climate_litigation -c "\dt"

# Should show all tables:
# - cases
# - documents  
# - extracted_text (note: singular, not plural)
# - citations (NEW - Phase 2)
# - text_sections
# - keywords_tags

# Quick validation queries
PGPASSWORD=197230 psql -h localhost -U phdmutley -d climate_litigation -c "
SELECT 'cases' as table, COUNT(*) FROM cases
UNION ALL SELECT 'documents', COUNT(*) FROM documents
UNION ALL SELECT 'extracted_text', COUNT(*) FROM extracted_text;"
```

---

## 8. File Structure & Organization

### Current Directory Structure

```
phdMutley/
├── data/
│   ├── raw/                    # Original Climate Case Chart CSV
│   ├── processed/              # Cleaned and filtered data
│   ├── cleaned/                # Final filtered dataset (2,924 cases)
│   └── samples/                # Test samples for validation
│
├── pdfs/
│   ├── downloaded/             # Downloaded PDF files
│   └── failed/                 # Failed download logs
│
├── scripts/
│   ├── phase0/                 # Foundation scripts
│   │   ├── init_database_pg18.py  # PostgreSQL 18 database schema
│   │   └── [other setup scripts]
│   │
│   ├── phase1/                 # Data processing & pipeline scripts
│   │   ├── populate_metadata.py         # Step 1: Populate cases & documents from Excel
│   │   ├── download_decisions_v2.py     # Step 2: Download PDFs by Document ID
│   │   ├── extract_text_v2.py           # Step 3: Extract text with UUID matching
│   │   ├── extract_text.py              # (Legacy - v1, not recommended)
│   │   ├── pdfs/                        # Downloaded PDFs storage
│   │   │   └── downloaded/              # doc_{document_id}.pdf files
│   │   └── logs/                        # Script execution logs
│   │
│   ├── phase2/                 # Citation extraction (CURRENT PHASE)
│   │   ├── initialize_citations_table.py   # Create citations table schema
│   │   ├── extract_citations_phase2.py     # Extract citations using Claude Haiku
│   │   └── logs/                           # Citation extraction logs
│   │
│   ├── phase3/                 # Analysis (next phase)
│   │   └── [Future analysis scripts]
│   │
│   ├── phase4/                 # Visualization & reporting (future)
│   │   └── [Future visualization scripts]
│   │
│   └── utils/                  # Utility functions (if needed)
│       └── [helper scripts]
│
├── notebooks/                  # Jupyter notebooks
│   ├── exploratory_analysis.ipynb
│   └── data_visualization.ipynb
│
├── outputs/
│   ├── reports/                # Analysis reports
│   ├── visualizations/         # Charts and graphs
│   ├── databases/              # Database exports
│   └── exports/                # CSV/Excel exports
│
├── docs/
│   ├── methodology/            # Academic methodology docs
│   └── technical/              # Technical documentation
│
├── logs/                       # Log files from all scripts
│
├── config/
│   └── database_schema.sql    # SQL schema definitions
│
├── venv/                       # Python virtual environment
│
├── .env                        # Environment variables (not in git)
├── .env.template               # Template for .env file
├── .gitignore                  # Git ignore rules
├── README.md                   # Project overview
├── requirements.txt            # Python dependencies
├── activate.sh                 # Quick venv activation script
├── baseDecisions.xlsx          # Filtered dataset (2,924 decisions) - SINGLE SOURCE OF TRUTH
├── CLAUDE_CODE_CONTEXT.md      # This file - comprehensive project documentation
├── TEST_PIPELINE_VALIDATION_REPORT.md     # Initial pipeline analysis report
└── ROBUST_PIPELINE_SUCCESS_REPORT.md      # Robust pipeline validation report
```

### File Naming Conventions

**Python Scripts:**
```
phase[X]_[number]_[descriptive_name].py
```

**Data Files:**
```
[source]_[status]_[date].csv
Examples:
- climate_case_chart_raw_20251029.csv
- climate_case_chart_filtered_20251030.csv
```

**Log Files:**
```
phase[X]_[script_name]_[timestamp].log
Examples:
- phase2_pdf_extraction_20251110_143022.log
```

**Output Files:**
```
[type]_[description]_[date].[ext]
Examples:
- report_exploratory_analysis_20251030.html
- export_extracted_texts_20251110.csv
```

---

## 9. Next Steps & Roadmap

### Current Status (November 14, 2025 - 16:15)

✅ **Phase 2 Complete:** Robust pipeline validated with 15-document test
🔄 **Ready for:** Either full dataset processing OR citation extraction with test data

### Two Parallel Options

#### **Option A: Process Full Dataset (2,924 documents)**

**Recommendation:** Run this before citation extraction to have complete data

**Steps:**
1. Set `TEST_MODE = False` in all three scripts:
   - `populate_metadata.py`
   - `download_decisions_v2.py`
   - `extract_text_v2.py`

2. Run pipeline in order:
   ```bash
   cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley
   source venv/bin/activate

   python scripts/phase1/populate_metadata.py
   python scripts/phase1/download_decisions_v2.py
   python scripts/phase1/extract_text_v2.py
   ```

3. **Estimated Time:** ~14 hours
   - Metadata: ~3 minutes
   - Downloads: ~9 hours (network dependent)
   - Extraction: ~5 hours

4. **Expected Results:**
   - ~2,900 cases with complete metadata
   - ~2,924 documents with complete metadata
   - ~2,500-2,600 extracted texts (85-90% based on PDF availability)

**Timeline:** 1-2 days

#### **Option B: Begin Citation Extraction (with test data)**

**Recommendation:** Start this while waiting for full dataset, test with existing 13 documents

**Phase 3: Citation Extraction**

**Status:** Ready to begin
**Timeline:** November 15-20, 2025 (5 days)

##### Step 1: Design Citation Detection Algorithms (Nov 15)
- [ ] Research standard legal citation formats (US, EU, etc.)
- [ ] Create regex patterns for common citation structures
- [ ] Design NER-based entity extraction
- [ ] Plan multi-method validation approach

##### Step 2: Implement & Test on 13 Documents (Nov 16-17)
- [x] Test set ready: 13 documents with extracted text
- [ ] Implement regex citation extraction
- [ ] Implement NER citation extraction
- [ ] Manual validation of results on sample
- [ ] Calculate accuracy metrics

##### Step 3: Refine & Optimize (Nov 18)
- [ ] Analyze false positives/negatives
- [ ] Refine regex patterns
- [ ] Adjust NER parameters
- [ ] Re-test on validation set

##### Step 4: Scale to Full Dataset (Nov 19-20)
- [ ] Process all ~2,500 documents (after Option A completes)
- [ ] Store citations in database (new table: citations)
- [ ] Generate quality metrics
- [ ] Create export for Lucas

**Timeline:** 5 days

### Phase 4: Quantitative Analysis (Nov 21-25)

- [ ] Calculate citation frequencies by jurisdiction
- [ ] Build citation network graph
- [ ] Identify citation patterns (North→North, South→North, North→South)
- [ ] Generate descriptive statistics
- [ ] Create preliminary visualizations

**Timeline:** 5 days

### Phase 5: Visualization & Reporting (Nov 26-29)

- [ ] Create interactive network visualizations
- [ ] Generate summary statistics dashboard
- [ ] Export data for Lucas's thesis inclusion
- [ ] Document methodology for reproducibility
- [ ] Create final technical report

**Timeline:** 4 days

### Phase 6: Finalization (Nov 30)

- [ ] Final code review and cleanup
- [ ] Complete technical documentation
- [ ] Prepare presentation materials
- [ ] Archive all outputs
- [ ] Git commit and push final version

**Timeline:** 1 day

### Recommended Execution Strategy

**Days 1-2 (Nov 15-16):**
- Run full dataset processing (Option A) in background
- Begin citation algorithm design (Option B - Step 1)
- Test citation extraction on 13 available documents

**Days 3-5 (Nov 17-19):**
- Complete citation extraction testing
- Full dataset extraction completes
- Scale citation extraction to full dataset

**Days 6-10 (Nov 20-24):**
- Quantitative analysis

**Days 11-15 (Nov 25-29):**
- Visualization & reporting

**Day 16 (Nov 30):**
- Finalization

**Total:** 16 days (on schedule for November 30 deadline)

---

## 10. Important Context & Constraints

### Academic Requirements

1. **Reproducibility:** All processing must be transparent and reproducible
2. **Documentation:** Every methodological decision must be documented
3. **No Black Boxes:** Avoid AI processing that can't be explained/reproduced
4. **Quality Over Speed:** Accuracy is more important than processing speed
5. **Ethical Considerations:** Respect copyright, cite all sources properly

### Technical Constraints

1. **Deadline:** November 30, 2025 (FIRM - for December presentation)
2. **Resources:** Local processing only (no cloud computing)
3. **Database:** PostgreSQL 18 on localhost
4. **Dataset Size:** 2,924 documents (manageable but requires optimization)
5. **PDF Quality:** ~6% scanned PDFs (flagged but not OCR'd)

### Data Constraints

1. **North-South Imbalance:** 29:1 ratio requires methodological adaptation
2. **Document Focus:** Only judicial decisions, no procedural documents
3. **Language:** Primarily English (some Spanish/Portuguese)
4. **URL Availability:** 99.9% availability (exceptional)
5. **Metadata Quality:** High quality, comprehensive coverage

### Collaboration Constraints

1. **Separation of Duties:** Gus = tech; Lucas = academic
2. **No Overlap:** Each stays in their lane
3. **Communication:** Technical findings reported for academic interpretation
4. **Decision Authority:** Lucas has final say on research methodology
5. **Timeline:** Both accountable to November 30th deadline

### Development Constraints

1. **Learning Curve:** Gus is transitioning to full-stack development
2. **Documentation Level:** Intermediate explanations, hands-on learning
3. **Code Comments:** Comprehensive commenting required for understanding
4. **Testing First:** Always test on small samples before scaling
5. **Error Handling:** Robust error handling and retry logic essential

---

## Appendices

### A. Quick Command Reference

```bash
# Activate environment
cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley
source venv/bin/activate

# Check database (UPDATED)
PGPASSWORD=197230 psql -h localhost -U phdmutley -d climate_litigation -c "\dt"

# Run robust pipeline (in order)
python scripts/phase1/populate_metadata.py
python scripts/phase1/download_decisions_v2.py
python scripts/phase1/extract_text_v2.py

# Run Phase 2: Citation Extraction (NEW)
python scripts/phase2/initialize_citations_table.py
python scripts/phase2/extract_citations_phase2.py

# View logs
tail -f logs/[log_filename].log
tail -f logs/metadata_population.log
tail -f logs/download_log.txt
tail -f logs/extraction_log.txt
tail -f scripts/phase2/logs/citations_extraction.log  # Phase 2 log

# Quick database check (UPDATED - includes citations)
PGPASSWORD=197230 psql -h localhost -U phdmutley -d climate_litigation -c "
SELECT 'cases' as table, COUNT(*) FROM cases
UNION ALL SELECT 'documents', COUNT(*) FROM documents
UNION ALL SELECT 'extracted_text', COUNT(*) FROM extracted_text
UNION ALL SELECT 'citations', COUNT(*) FROM citations;"

# Git operations
git status
git add .
git commit -m "Description"
git push origin main
```

### B. Common Database Queries (UPDATED)

```sql
-- Check record counts
SELECT COUNT(*) FROM cases;
SELECT COUNT(*) FROM documents;
SELECT COUNT(*) FROM extracted_text;  -- Note: singular, not plural

-- Check extraction quality distribution
SELECT extraction_quality, COUNT(*)
FROM extracted_text
GROUP BY extraction_quality
ORDER BY extraction_quality;

-- Check extraction methods used
SELECT extraction_method, COUNT(*)
FROM extracted_text
GROUP BY extraction_method;

-- Check North-South distribution
SELECT region, COUNT(*)
FROM cases
GROUP BY region
ORDER BY COUNT(*) DESC;

-- View recent extractions with quality
SELECT d.document_url, e.extraction_method, e.extraction_quality,
       e.word_count, c.case_name
FROM extracted_text e
JOIN documents d ON e.document_id = d.document_id
JOIN cases c ON d.case_id = c.case_id
ORDER BY e.extraction_date DESC
LIMIT 10;

-- **NEW Phase 2: Citation Queries**

-- Check total citations extracted
SELECT COUNT(*) FROM citations;

-- Citations by type (foreign vs international)
SELECT citation_type, COUNT(*)
FROM citations
GROUP BY citation_type;

-- Citations by confidence level
SELECT extraction_confidence, COUNT(*)
FROM citations
GROUP BY extraction_confidence
ORDER BY 
  CASE extraction_confidence
    WHEN 'high' THEN 1
    WHEN 'medium' THEN 2
    WHEN 'low' THEN 3
  END;

-- Top cited jurisdictions
SELECT cited_jurisdiction, COUNT(*) as citation_count
FROM citations
WHERE cited_jurisdiction IS NOT NULL
GROUP BY cited_jurisdiction
ORDER BY citation_count DESC
LIMIT 10;

-- Top cited courts
SELECT cited_court_name, COUNT(*) as citation_count
FROM citations
WHERE cited_court_name IS NOT NULL
GROUP BY cited_court_name
ORDER BY citation_count DESC
LIMIT 10;

-- Citations by year (temporal analysis)
SELECT cited_year, COUNT(*) as citation_count
FROM citations
WHERE cited_year IS NOT NULL
GROUP BY cited_year
ORDER BY cited_year DESC;

-- Documents with most citations
SELECT d.document_id, c.case_name, COUNT(cit.citation_id) as citation_count
FROM documents d
JOIN cases c ON d.case_id = c.case_id
LEFT JOIN citations cit ON d.document_id = cit.document_id
WHERE cit.citation_id IS NOT NULL
GROUP BY d.document_id, c.case_name
ORDER BY citation_count DESC
LIMIT 10;

-- North-South citation flow analysis
SELECT 
  c_citing.region as citing_region,
  cit.citation_type,
  COUNT(*) as citation_count
FROM citations cit
JOIN documents d ON cit.document_id = d.document_id
JOIN cases c_citing ON d.case_id = c_citing.case_id
GROUP BY c_citing.region, cit.citation_type
ORDER BY citing_region, cit.citation_type;

-- Check for data completeness
SELECT
  COUNT(*) as total_cases,
  COUNT(*) FILTER (WHERE court_name IS NOT NULL AND court_name != 'Unknown') as cases_with_court,
  COUNT(*) FILTER (WHERE country IS NOT NULL AND country != 'Unknown') as cases_with_country
FROM cases;

-- Validate referential integrity
SELECT
  (SELECT COUNT(*) FROM cases) as cases,
  (SELECT COUNT(*) FROM documents) as documents,
  (SELECT COUNT(*) FROM extracted_text) as extracted_texts,
  (SELECT COUNT(*) FROM documents d
   LEFT JOIN extracted_text e ON d.document_id = e.document_id
   WHERE e.text_id IS NOT NULL) as docs_with_text;
```

### C. Contact & Resources

**Primary Developer:** Gustavo (gusrodgs)
**Academic Supervisor:** Lucas Biasetton (Mutley)
**Repository:** https://github.com/ExVerbisOmnia/phdMutley
**Climate Case Chart:** https://www.climatecasechart.com
**Notion Workspace:** "Doutorado PM" (shared by Lucas)

### D. Key Lessons Learned (November 14, 2025)

**From Robust Pipeline Implementation:**

1. **Single Source of Truth is Critical**
   - Mixing data sources (baseCompleta vs baseDecisions) creates inconsistencies
   - All scripts must reference the same Excel file
   - Document this explicitly in script headers

2. **Use Unique Identifiers**
   - Document ID is superior to Case ID for file naming
   - One case can have multiple documents, making Case ID non-unique
   - Unique identifiers prevent filename collisions and matching errors

3. **Deterministic UUIDs Enable Reproducibility**
   - UUID5 with consistent namespace ensures same UUIDs across runs
   - Critical for matching records across different scripts
   - Must be implemented identically in all scripts

4. **Database-First Approach Prevents Duplicates**
   - Query existing records instead of creating new ones
   - Validate existence before insertion
   - Use proper foreign key relationships with CASCADE

5. **Test Early, Test Small**
   - 15-document test revealed critical architecture issues
   - Would have been catastrophic to discover after processing 2,924 documents
   - TEST_MODE in all scripts is essential

6. **Comprehensive Logging is Essential**
   - Detailed logs enabled quick root cause identification
   - Timestamp-based log files for each run
   - Log both successes and failures with context

7. **Documentation Prevents Future Issues**
   - Clear pipeline flow diagrams
   - Explicit execution order
   - Validation criteria and success metrics

---

## Document Maintenance

**This document should be updated whenever:**
- Major methodological decisions are made
- New phases are completed
- Database schema changes
- New constraints or requirements emerge
- Key findings require methodology adjustments
- Pipeline architecture changes
- Scripts are modified or created

**Version History:**
- **v1.0** (Nov 10, 2025): Initial documentation
- **v2.0** (Nov 14, 2025 AM): Updated for Claude Code integration with complete project state
- **v3.0** (Nov 14, 2025 PM - 16:15): **MAJOR UPDATE** - Robust Pipeline Implementation
  - Added Section 6: Robust Pipeline Architecture
  - Updated Phase 2 status to "COMPLETE - ROBUST VERSION 2.0"
  - Updated database configuration (climate_litigation, phdmutley user)
  - Updated file structure to reflect new scripts (extract_text_v2.py)
  - Added documentation files (TEST_PIPELINE_VALIDATION_REPORT, ROBUST_PIPELINE_SUCCESS_REPORT)
  - Updated Next Steps & Roadmap with two parallel options
  - Updated database queries and command references
  - Added Key Lessons Learned appendix
  - Current state: 8 cases, 15 documents, 13 extracted texts validated
  - Pipeline ready for full dataset (2,924 documents)
- **v4.0** (Nov 20, 2025): **MAJOR UPDATE** - Phase 2 Citation Extraction Implementation
  - **NEW: Phase 3 section** documenting citation extraction implementation
  - **NEW: Citations database table** with flexible schema allowing NULL case names
  - **Model Selection:** Claude Haiku API for cost-effective processing (~$29 vs $346)
  - **Methodology:** Foreign and international citations only (excludes domestic)
  - **Scripts Added:**
    - `initialize_citations_table.py` - Database schema creation
    - `extract_citations_phase2.py` - LLM-powered citation extraction pipeline
  - Updated database schema overview to include citations table
  - Updated citation detection strategy from "pending" to "implemented"
  - Added comprehensive citation-specific database queries
  - Updated file structure to show phase2/ directory
  - Updated environment variables to include ANTHROPIC_API_KEY
  - Updated command reference with Phase 2 scripts
  - Current status: Citation extraction pipeline ready for testing
  - Cost estimates: ~$29 for full dataset with Haiku model

---

**END OF CLAUDE CODE CONTEXT DOCUMENTATION**
