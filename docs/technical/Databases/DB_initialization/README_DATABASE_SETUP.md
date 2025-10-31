# Climate Litigation Database - Setup Guide

## Overview

This database system stores and organizes climate litigation case data from the Global South, including case metadata, PDF documents, extracted text, and analytical tags.

## Files Included

- **`init_database.py`** - Database initialization script
- **`.env.example`** - Configuration template
- **`README.md`** - This file

---

## Prerequisites

### 1. Install PostgreSQL

**Windows:**
- Download from: https://www.postgresql.org/download/windows/
- Use the installer (includes pgAdmin GUI tool)
- Default port: 5432

**macOS:**
```bash
# Using Homebrew
brew install postgresql@15
brew services start postgresql@15
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
```

### 2. Install Python Packages

```bash
pip install sqlalchemy psycopg2-binary python-dotenv pandas
```

**Package explanation:**
- `sqlalchemy` - ORM framework for database operations
- `psycopg2-binary` - PostgreSQL adapter for Python
- `python-dotenv` - Loads configuration from .env files
- `pandas` - For data manipulation (will use later)

---

## Setup Instructions

### Step 1: Create PostgreSQL Database

Connect to PostgreSQL and create the database:

**Option A: Using psql (command line)**
```bash
# Connect to PostgreSQL
psql -U postgres

# Create database
CREATE DATABASE climate_litigation;

# Verify
\l

# Exit
\q
```

**Option B: Using pgAdmin (GUI)**
1. Open pgAdmin
2. Right-click "Databases" → "Create" → "Database"
3. Name: `climate_litigation`
4. Click "Save"

### Step 2: Configure Database Connection

1. **Copy the template:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` file** with your credentials:
   ```env
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=climate_litigation
   DB_USER=your_username
   DB_PASSWORD=your_password
   ```

3. **Security note:** Add `.env` to your `.gitignore`:
   ```bash
   echo ".env" >> .gitignore
   ```

### Step 3: Initialize Database

Run the initialization script:

```bash
python init_database.py
```

**The script will:**
1. Connect to PostgreSQL
2. Ask if you want to drop existing tables (choose 'no' on first run)
3. Create all tables and indexes
4. Verify the setup

**Expected output:**
```
======================================================================
Climate Litigation Database Initialization
======================================================================

1. Connecting to PostgreSQL...
   ✓ Connected to database: climate_litigation
   ✓ Host: localhost:5432

2. Skipping table drop (drop_existing=False)

3. Creating database tables...
   ✓ Created table: cases
   ✓ Created table: documents
   ✓ Created table: extracted_text
   ✓ Created table: text_sections
   ✓ Created table: keywords_tags

4. Verifying table creation...
   ✓ Table 'cases' exists
   ✓ Table 'documents' exists
   ✓ Table 'extracted_text' exists
   ✓ Table 'text_sections' exists
   ✓ Table 'keywords_tags' exists

   Total tables created: 5

======================================================================
✓ Database initialization completed successfully!
======================================================================
```

---

## Database Schema

### Table Structure

```
CASES
├── case_id (PK)
├── case_name
├── court_name
├── country
├── region
├── filing_date
├── decision_date
├── case_status
└── ...

DOCUMENTS
├── document_id (PK)
├── case_id (FK → cases)
├── document_type
├── file_path
├── file_hash
├── extraction_status
└── ...

EXTRACTED_TEXT
├── extraction_id (PK)
├── document_id (FK → documents)
├── full_text
├── extraction_method
├── quality_score
└── ...

TEXT_SECTIONS
├── section_id (PK)
├── extraction_id (FK → extracted_text)
├── section_type
├── section_order
├── content
└── ...

KEYWORDS_TAGS
├── tag_id (PK)
├── case_id (FK → cases)
├── keyword
├── tag_type
└── ...
```

### Relationships

- **Cases** (1) ↔ (N) **Documents** - One case can have many documents
- **Documents** (1) ↔ (1) **Extracted Text** - Each document has one extraction
- **Extracted Text** (1) ↔ (N) **Text Sections** - Text divided into sections
- **Cases** (1) ↔ (N) **Keywords** - Cases can have multiple tags

---

## Usage Examples

### Basic Operations with SQLAlchemy

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from init_database import Case, Document, ExtractedText

# Create engine and session
engine = create_engine('postgresql://user:pass@localhost/climate_litigation')
Session = sessionmaker(bind=engine)
session = Session()

# Example 1: Add a new case
new_case = Case(
    case_name="Silva vs. Government of Brazil",
    court_name="Supreme Federal Court",
    country="Brazil",
    region="Latin America",
    filing_date=date(2023, 5, 15)
)
session.add(new_case)
session.commit()

# Example 2: Query cases
brazil_cases = session.query(Case).filter(Case.country == "Brazil").all()
for case in brazil_cases:
    print(f"{case.case_name} - {case.filing_date}")

# Example 3: Get case with all documents
case = session.query(Case).filter(Case.case_id == 1).first()
print(f"Case: {case.case_name}")
for doc in case.documents:
    print(f"  - Document: {doc.document_type}")

# Example 4: Add document to existing case
new_doc = Document(
    case_id=case.case_id,
    document_type="Decision",
    file_path="/data/pdfs/case_001_decision.pdf",
    file_name="case_001_decision.pdf",
    extraction_status="pending"
)
session.add(new_doc)
session.commit()

# Example 5: Complex query - cases from 2023 with decisions
from sqlalchemy import and_, extract

cases_2023 = session.query(Case).filter(
    and_(
        extract('year', Case.filing_date) == 2023,
        Case.case_status == 'Decided'
    )
).all()

# Always close session when done
session.close()
```

### Working with Extracted Text

```python
# Add extracted text to a document
extraction = ExtractedText(
    document_id=doc.document_id,
    full_text="The court hereby decides...",
    extraction_method="pdfplumber",
    word_count=5420,
    character_count=32400,
    quality_score=0.95
)
session.add(extraction)
session.commit()

# Query extracted text
extraction = session.query(ExtractedText).filter(
    ExtractedText.document_id == doc.document_id
).first()

print(f"Text length: {extraction.word_count} words")
print(f"Quality: {extraction.quality_score}")
```

---

## Troubleshooting

### Connection Issues

**Error: "could not connect to server"**
```bash
# Check if PostgreSQL is running
# Windows
pg_ctl status

# macOS
brew services list

# Linux
sudo systemctl status postgresql
```

**Error: "password authentication failed"**
- Verify credentials in `.env` file
- Try connecting with psql: `psql -U your_user -d climate_litigation`

**Error: "database does not exist"**
```sql
-- Create it first
CREATE DATABASE climate_litigation;
```

### Import Issues

**Error: "No module named 'psycopg2'"**
```bash
pip install psycopg2-binary
```

**Error: "cannot import name 'Case'"**
- Ensure you're importing from the correct file: `from init_database import Case`

---

## Next Steps

After successful initialization:

1. **Load case metadata** from your Excel file (`baseCompleta.xlsx`)
2. **Add PDF documents** to the database
3. **Run text extraction** pipeline (to be developed)
4. **Analyze data** using queries and reports

---

## Database Maintenance

### Backup Database

```bash
# Backup to file
pg_dump -U your_user climate_litigation > backup.sql

# Restore from backup
psql -U your_user climate_litigation < backup.sql
```

### View Database Size

```sql
SELECT pg_size_pretty(pg_database_size('climate_litigation'));
```

### Reset Database (DANGER)

```bash
# This deletes ALL data!
python init_database.py
# Choose "yes" when prompted to drop tables
```

---

## Support

For issues or questions about:
- **PostgreSQL**: https://www.postgresql.org/docs/
- **SQLAlchemy**: https://docs.sqlalchemy.org/
- **This project**: Contact Lucas Biasetton

---

## Project Information

**Author:** Lucas Biasetton  
**Project:** Doutorado PM - Global South Climate Litigation Analysis  
**Database:** PostgreSQL + SQLAlchemy ORM  
**Date:** October 2025
