# Database Schema Analysis & Cleanup Recommendations

**Date:** November 25, 2025
**Project:** PhD Climate Litigation - Citation Extraction

## 1. Overview

This document presents an analysis of the current PostgreSQL database schema, comparing the actual tables in the database against the project's codebase and documentation. The goal is to identify "useless" (legacy, redundant, or orphaned) tables and columns to streamline the project.

## 2. Current Database State

The database currently contains **12 tables**. Below is the categorization based on usage analysis.

### ✅ Active & Critical Tables
These tables are essential for the current pipeline (v5 architecture).

| Table Name | Rows | Description | Usage |
|------------|------|-------------|-------|
| **`cases`** | 6 | Stores case metadata (from Excel). | Core metadata. Used by `populate_metadata.py`. |
| **`documents`** | 31 | Stores document metadata. | Core metadata. Linked to `cases`. |
| **`extracted_text`** | 31 | Stores raw/processed text from PDFs. | Output of `extract_texts.py`. **Note:** Uses singular name. |
| **`citation_extraction_phased`** | 0* | Stores individual citations (v5). | Output of `extract_citations.py`. (*Empty due to recent reset*) |
| **`citation_extraction_phased_summary`** | 15 | Document-level extraction stats (v5). | Output of `extract_citations.py`. |

### ⚠️ Legacy / Redundant / Orphaned Tables
These tables appear to be leftovers from previous versions (v4) or duplicate imports and are candidates for removal.

| Table Name | Rows | Status | Reason for Removal |
|------------|------|--------|--------------------|
| **`extracted_texts`** | 31 | **DUPLICATE** | Plural name. Duplicate of `extracted_text`. Has fewer columns (12 vs 16). Not used by current scripts. |
| **`citations`** | 0 | **LEGACY (v4)** | Old citation schema. Replaced by `citation_extraction_phased`. Defined in `init_database.py` but unused by v5 pipeline. |
| **`citation_extractions`** | 0 | **LEGACY (v4)** | Old metadata table. Replaced by `citation_extraction_phased_summary`. Not defined in current `init_database.py`. |
| **`extraction_log`** | 0 | **ORPHANED** | Old logging table. Not defined in current `init_database.py`. |
| **`keywords_tags`** | 0 | **UNUSED** | Empty. Not defined in current `init_database.py`. |

### ❓ Potentially Unused (Review Needed)
These tables are defined in the code but appear unused in the current data flow.

| Table Name | Rows | Status | Notes |
|------------|------|--------|-------|
| **`text_sections`** | 0 | **EMPTY** | Defined in `init_database.py`. Intended for section-level analysis? Currently not populated. |
| **`processing_log`** | 0 | **EMPTY** | Defined in `init_database.py`. Scripts currently use file-based logging (`logs/*.log`) instead of DB logging. |

## 3. Detailed Analysis

### 3.1. The Duplicate Text Table Issue
- **`extracted_text` (Singular)**: This is the **correct** table. It matches the SQLAlchemy model `ExtractedText` in `init_database.py`. It has 16 columns including `extraction_quality`, `word_count`, etc.
- **`extracted_texts` (Plural)**: This is an **incorrect/duplicate** table. It likely resulted from an older script version or a manual import. It should be dropped to avoid confusion.

### 3.2. The Citation Schema Transition (v4 -> v5)
- The project has moved to a "Phased" extraction approach (v5).
- **v5 Tables**: `citation_extraction_phased`, `citation_extraction_phased_summary`.
- **v4 Tables**: `citations`, `citation_extractions`.
- **Recommendation**: Fully deprecate v4. Remove `Citation` model from `init_database.py` and drop the `citations` and `citation_extractions` tables.

## 4. Cleanup Plan

To clean up the project and database schema, follow these steps:

### Step 1: Database Cleanup (SQL)
Execute the following SQL commands to remove useless tables:

```sql
-- 1. Drop duplicate/orphaned tables
DROP TABLE IF EXISTS extracted_texts CASCADE;
DROP TABLE IF EXISTS citation_extractions CASCADE;
DROP TABLE IF EXISTS extraction_log CASCADE;
DROP TABLE IF EXISTS keywords_tags CASCADE;

-- 2. Drop legacy v4 tables (if ready to fully commit to v5)
DROP TABLE IF EXISTS citations CASCADE;

-- 3. (Optional) Drop unused feature tables
-- DROP TABLE IF EXISTS text_sections CASCADE;
-- DROP TABLE IF EXISTS processing_log CASCADE;
```

### Step 2: Codebase Cleanup (Python)
Update `scripts/0-initialize-database/init_database.py` to reflect the active schema:

1.  **Remove `class Citation(Base)`**: Delete lines 298-346.
2.  **Remove `class TextSection(Base)`**: (Optional) Delete lines 257-296 if not planned for immediate use.
3.  **Remove `class ProcessingLog(Base)`**: (Optional) Delete lines 450-475 if file logging is preferred.

### Step 3: Verification
After cleanup, the database should contain only the 5 active tables + potentially `text_sections`/`processing_log` if kept.

## 5. Schema Optimization Suggestions

1.  **`cases` Table**:
    - `case_name_non_english`: Currently NULL for all checked rows. If not used, consider removing.
    - `geography_iso`: Check if this is redundant with `geographies`.

2.  **`documents` Table**:
    - `document_content_url`: Check if this is distinct from `document_url`.

3.  **Constraints**:
    - Ensure `document_id` in `extracted_text` has a `UNIQUE` constraint to enforce 1:1 relationship (one text per document).
