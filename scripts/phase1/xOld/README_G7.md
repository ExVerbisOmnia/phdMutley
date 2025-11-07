# Task G7: Text Extraction Pipeline - Implementation Guide

## 📁 Files Delivered

1. **text_extractor.py** - Modular text extraction library
2. **process_pdfs.py** - PDF processing script with database integration
3. **README_G7.md** - This file (usage guide)

---

## 🎯 Overview

This implementation provides a complete text extraction pipeline for your climate litigation PhD project. The code is optimized for **PostgreSQL 18** and follows academic best practices for reproducibility and transparency.

### Key Features

✅ **Multi-library support** with automatic fallback (pdfplumber → PyMuPDF → PyPDF2)  
✅ **Quality assessment** of extracted text  
✅ **Scanned PDF detection** for OCR planning  
✅ **PostgreSQL 18 optimizations** (UUIDv7, JSONB, AIO-ready)  
✅ **Comprehensive logging** for academic transparency  
✅ **Resume capability** - can pause and restart  
✅ **Progress tracking** with tqdm  
✅ **Beginner-friendly** with extensive comments  

---

## 📦 Installation & Setup

### 1. Place Files in Your Project

**From the project root directory** (`/home/gusrodgs/Gus/cienciaDeDados/phdMutley`):

```bash
# Activate your virtual environment
source venv/bin/activate

# Create the scripts directory if it doesn't exist
mkdir -p scripts/phase1

# Move the files to the appropriate location
mv text_extractor.py scripts/phase1/
mv process_pdfs.py scripts/phase1/
```

### 2. Verify Dependencies

All required packages should already be installed in your venv. Verify:

```bash
pip list | grep -E "(pdfplumber|PyPDF2|fitz|sqlalchemy|psycopg2|tqdm|python-dotenv)"
```

**If any are missing**, install them:

```bash
pip install "pdfplumber>=0.10.3" "PyPDF2>=3.0.1" "PyMuPDF>=1.23.0" \
            "sqlalchemy>=2.0.23" "psycopg2-binary>=2.9.9" \
            "python-dotenv>=1.0.0" "tqdm>=4.65.0"
```

### 3. Configure Database Connection

Create or edit your `.env` file in the project root:

```bash
# From project root
nano .env
```

Add this line (adjust credentials as needed):

```
DATABASE_URL=postgresql://phdmutley:197230@localhost:5432/climate_litigation
```

---

## 🚀 Usage

### Testing the Text Extractor (Optional but Recommended)

Before processing all PDFs, test with a single file:

```bash
# From project root
cd scripts/phase1

# Test with one of your downloaded PDFs
python text_extractor.py ../../pdfs/downloaded/United\ States/US-2021-01234.pdf
```

This will show you:
- Extraction method used
- Word/character counts
- Quality assessment
- Whether it's scanned
- Sample of extracted text

### Processing All PDFs

**From the `scripts/phase1` directory:**

```bash
cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley/scripts/phase1

# Run the processing script
python process_pdfs.py
```

You'll see:
1. Database connection confirmation
2. PDF file count
3. Real-time progress bar with stats
4. Final summary with quality distribution

**The script will:**
- ✅ Process all PDFs in `pdfs/downloaded/`
- ✅ Extract text using the best available method
- ✅ Store results in PostgreSQL database
- ✅ Skip already-processed files (resumable)
- ✅ Create detailed logs in `logs/` directory
- ✅ Handle errors gracefully (continues on failure)

---

## 📊 PostgreSQL 18 Optimizations Implemented

### 1. **UUIDv7 Primary Keys**

```python
case_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
```

**Benefits:**
- Time-ordered for better index performance
- Better than UUIDv4 for sequential inserts
- PostgreSQL 18's improved UUID handling

### 2. **JSONB for Flexible Metadata**

```python
metadata_json = Column(JSONB)
quality_issues = Column(JSONB)
```

**Benefits:**
- Store flexible metadata without schema changes
- PostgreSQL 18 has enhanced JSON query performance
- Indexable for fast queries

### 3. **AIO-Ready Schema**

The schema is designed for PostgreSQL 18's Asynchronous I/O (AIO):
- Large TEXT columns for extracted text
- Efficient for bulk reads (citation analysis)
- Optimized connection pooling

**To enable AIO workers** (optional, for production):

Edit `/etc/postgresql/18/main/postgresql.conf`:

```conf
io_method = worker              # Use I/O worker processes
io_workers = 4                  # Adjust based on CPU cores
effective_io_concurrency = 16   # Default in PG 18
```

Then restart PostgreSQL:

```bash
sudo systemctl restart postgresql
```

### 4. **Optimized Indexes**

The schema includes strategic indexes on:
- `original_case_id` (frequent lookups)
- `region` (North/South filtering)
- `file_path` (uniqueness checks)
- `document_id` (joins)
- `timestamp` (log queries)

---

## 📋 Database Schema

### Tables Created

```
cases
├── case_id (UUID, PK)
├── original_case_id (String, Unique)
├── case_name (Text)
├── jurisdiction (String)
├── geography_iso (String)
├── region (String) [North/South]
└── metadata_json (JSONB)

documents
├── document_id (UUID, PK)
├── case_id (UUID, FK → cases)
├── file_path (Text, Unique)
├── file_hash (String, Unique)
└── page_count (Integer)

extracted_texts
├── extraction_id (UUID, PK)
├── document_id (UUID, FK → documents)
├── raw_text (Text) ← The extracted content
├── extraction_method (String)
├── word_count (Integer)
├── extraction_quality (String)
├── is_scanned (Boolean)
└── quality_issues (JSONB)

extraction_log
├── log_id (Integer, PK)
├── document_id (UUID, FK → documents)
├── stage (String)
├── status (String) [success/failure/warning]
└── timestamp (DateTime)
```

---

## 🔍 Monitoring Progress

### Real-time Monitoring

The script provides a tqdm progress bar:

```
Processing PDFs: 45%|████████▌         | 1350/3000 [12:34<15:20, 1.79file/s]
```

### Check Logs

```bash
# View the latest log file
ls -lt logs/ | head -1

# Follow logs in real-time
tail -f logs/pdf_processing_*.log
```

### Query Database Progress

From a Python shell or notebook:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Connect to database
engine = create_engine('postgresql://phdmutley:197230@localhost:5432/climate_litigation')
Session = sessionmaker(bind=engine)
session = Session()

# Check extraction statistics
from process_pdfs import ExtractedText, get_extraction_statistics

stats = get_extraction_statistics(session)
print(f"Total extractions: {stats['total_extractions']}")
print(f"Excellent quality: {stats['quality_excellent']}")
print(f"Average words: {stats['avg_word_count']}")
```

---

## 🛠️ Troubleshooting

### Issue: "Database connection failed"

**Solution:**

1. Check PostgreSQL is running:
   ```bash
   sudo systemctl status postgresql
   ```

2. Verify database exists:
   ```bash
   psql -U phdmutley -d climate_litigation -c "\dt"
   ```

3. Check `.env` file has correct credentials

### Issue: "No PDF files found"

**Solution:**

The script looks for PDFs in `pdfs/downloaded/` (relative to project root).

Check the PDF_BASE_DIR constant in `process_pdfs.py`:

```python
PDF_BASE_DIR = Path("pdfs/downloaded")
```

If your PDFs are elsewhere, adjust this path.

### Issue: "Import error: text_extractor"

**Solution:**

Make sure both files are in the same directory:

```bash
ls -l scripts/phase1/*.py
# Should show: text_extractor.py and process_pdfs.py
```

### Issue: Poor extraction quality

**Solution:**

1. Check which library was used: it's logged for each file
2. For scanned PDFs, flag them for OCR (Phase 2)
3. Review quality issues in the `extraction_log` table

```sql
SELECT status, COUNT(*) 
FROM extraction_log 
GROUP BY status;
```

---

## 📈 Next Steps (Task G8)

After successfully extracting text:

1. **Import CSV metadata** to populate case details
2. **Validate extractions** on your 15-PDF test set
3. **Review quality statistics** and adjust if needed
4. **Process remaining PDFs** (~2900 files)

---

## 🎓 Academic Considerations

### Reproducibility

✅ All extraction parameters are logged  
✅ Library versions are documented  
✅ Extraction method per document is recorded  
✅ Quality assessments are stored  

### Transparency

✅ Complete audit trail in `extraction_log`  
✅ Failed extractions are logged (not hidden)  
✅ Scanned documents are flagged  
✅ Quality issues are documented  

### Documentation

Document in your methodology:
1. Library preference order (pdfplumber → PyMuPDF → PyPDF2)
2. Quality assessment criteria
3. Scanned document handling
4. Success rate and quality distribution

---

## 📞 Support

### Getting Help

If you encounter issues:

1. **Check the logs**: Most errors are self-explanatory
2. **Review this README**: Solutions to common issues above
3. **Test with one PDF first**: Isolate the problem
4. **Share the error message**: Include the full traceback

### Code Structure

Both files have extensive comments explaining:
- What each function does
- Why design decisions were made
- How to use each component

Read the comments - they're written for beginners!

---

## ✅ Checklist

Before running on all PDFs:

- [ ] Files placed in `scripts/phase1/`
- [ ] Virtual environment activated
- [ ] All dependencies installed
- [ ] `.env` file configured
- [ ] PostgreSQL 18 running
- [ ] Database initialized
- [ ] Tested with one PDF
- [ ] Reviewed test results
- [ ] Ready to process all PDFs

---

**Version:** 1.0  
**Date:** October 31, 2025  
**Author:** Lucas Biasetton (Gus)  
**Project:** Doutorado PM - Climate Litigation Citation Analysis
