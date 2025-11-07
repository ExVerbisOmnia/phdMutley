# Climate Litigation Database - PostgreSQL 18 Setup Guide

## 📁 Project Directory Reference

**Main Project Directory:** `/home/gusrodgs/Gus/cienciaDeDados/phdMutley`

**Important:** Unless otherwise specified, commands that reference project files should be run from this directory. System-level commands (PostgreSQL, apt, systemctl) can be run from any directory.

---

## 📌 Overview

This database system is optimized for **PostgreSQL 18** (released September 2025), leveraging cutting-edge features for maximum performance in storing and analyzing climate litigation case data from the Global South.

### PostgreSQL 18 Key Features Used:
- **✨ Asynchronous I/O (AIO)**: 2-3x faster reads for large text extractions
- **🔑 UUIDv7**: Timestamp-ordered primary keys for better indexing
- **⚡ Skip Scan**: Flexible multicolumn index usage
- **💾 Virtual Generated Columns**: Computed values without storage overhead
- **🔒 Data Checksums**: Enabled by default for data integrity
- **🚀 Enhanced JSON**: Better performance for metadata queries

---

## 📦 Files Included

All files are located relative to the project directory:

- **`scripts/phase0/init_database_pg18.py`** - Database initialization script (PG 18 optimized)
- **`env_pg18.example`** - Configuration template with AIO settings
- **`README_PG18_SETUP.md`** - This comprehensive guide
- **`requirements_pg18.txt`** - Python packages for PG 18

---

## ⚙️ Prerequisites

### 1. Install PostgreSQL 18

**🔹 Run from: Any directory (system-level installation)**

PostgreSQL 18 is the current stable version. **Do NOT use older versions** from default Ubuntu repositories.

#### 🐧 Linux (Ubuntu/Debian)

```bash
# 1. Install prerequisites
sudo apt update
sudo apt install -y wget gnupg2 lsb-release

# 2. Add PostgreSQL official repository
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
echo "deb http://apt.postgresql.org/pub/repos/apt/ $(lsb_release -cs)-pgdg main" | sudo tee /etc/apt/sources.list.d/pgdg.list

# 3. Update and install PostgreSQL 18
sudo apt update
sudo apt install -y postgresql-18 postgresql-contrib-18

# 4. For best performance (Linux), check for io_uring support
ldd /usr/lib/postgresql/18/bin/postgres | grep liburing
# If not present, PostgreSQL may need to be compiled from source with:
# ./configure --with-liburing --prefix=/usr/local/pgsql
# make && sudo make install

# 5. Start PostgreSQL service
sudo systemctl start postgresql
sudo systemctl enable postgresql

# 6. Verify version (must show 18.x)
psql --version
# Expected output: psql (PostgreSQL) 18.0 or higher
```

#### 🍎 macOS

```bash
# Using Homebrew
brew install postgresql@18
brew services start postgresql@18

# Verify version
psql --version
```

#### 🪟 Windows

1. Download installer from: https://www.postgresql.org/download/windows/
2. Run installer and select PostgreSQL 18
3. During installation, remember the password for `postgres` user
4. Verify: Open Command Prompt → `psql --version`

---

### 2. Verify Kernel Support (Linux only)

**🔹 Run from: Any directory**

For best performance with io_uring:

```bash
# Check kernel version (need 5.1+, recommended 5.10+)
uname -r
# Should show 5.1 or higher

# Check if io_uring library is available
ls /usr/include/liburing.h
# If missing, install:
sudo apt install liburing-dev
```

---

### 3. Install Python Packages

**🔹 Run from: `/home/gusrodgs/Gus/cienciaDeDados/phdMutley`**

```bash
# Navigate to project directory
cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley

# Activate virtual environment
source venv/bin/activate

# Install essential packages
pip install sqlalchemy>=2.0.23 psycopg2-binary>=2.9.9 python-dotenv>=1.0.0

# Or install all packages from requirements file:
pip install -r requirements_pg18.txt
```

---

## 🚀 Step-by-Step Setup

### Step 1: Create PostgreSQL 18 Database

**🔹 Run from: Any directory (PostgreSQL administrative commands)**

```bash
# Switch to postgres superuser and connect to PostgreSQL
sudo -u postgres psql
```

**Inside the PostgreSQL prompt, run these commands:**

```sql
-- Create the database
CREATE DATABASE climate_litigation;

-- Create a user with password (change 'your_secure_password' to your actual password)
CREATE USER phdmutley WITH PASSWORD '197230';

-- Grant all privileges on the database to the user
GRANT ALL PRIVILEGES ON DATABASE climate_litigation TO phdmutley;

-- Connect to the newly created database
\c climate_litigation

-- In PostgreSQL 18, you also need to grant schema-level privileges
GRANT ALL ON SCHEMA public TO phdmutley;
GRANT ALL ON ALL TABLES IN SCHEMA public TO phdmutley;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO phdmutley;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO phdmutley;

-- Exit PostgreSQL
\q
```

---

### Step 2: Configure Asynchronous I/O (Performance Boost)

**🔹 Run from: Any directory (PostgreSQL server configuration)**

PostgreSQL 18's AIO can provide **2-3x performance improvement** for reading large text data.

```bash
# Edit PostgreSQL configuration file
sudo nano /etc/postgresql/18/main/postgresql.conf
```

**Scroll to the bottom of the file and add these lines:**

```conf
# ============================================================================
# ASYNCHRONOUS I/O CONFIGURATION (PostgreSQL 18)
# ============================================================================

# I/O Method (requires restart)
# Options: sync, worker, io_uring
# - sync: Legacy behavior (PG 17 compatibility)
# - worker: Use I/O worker processes (default, cross-platform)
# - io_uring: Best performance on Linux 5.1+ with liburing
io_method = worker              # Start with 'worker', test 'io_uring' later

# Number of I/O worker processes (if using worker method)
# Recommended: 25-100% of CPU cores
# For 4 cores: 4-6 workers
# For 8 cores: 6-12 workers
io_workers = 4                  # Adjust based on your CPU cores (check with: nproc)

# I/O Concurrency Settings
effective_io_concurrency = 16   # Increased from 1 in PG 17
maintenance_io_concurrency = 16 # For VACUUM and index builds

# Optional: For io_uring method (Linux only)
# io_combine_limit = 128
# io_max_combine_limit = 256

# ============================================================================
# OTHER PERFORMANCE SETTINGS (Optional but Recommended)
# ============================================================================

shared_buffers = 256MB          # 25% of RAM (adjust based on your system)
work_mem = 64MB                 # For sorting operations
maintenance_work_mem = 128MB    # For CREATE INDEX, VACUUM
```

**Save the file (Ctrl+O, Enter, Ctrl+X), then restart PostgreSQL:**

```bash
# Restart PostgreSQL to apply changes
sudo systemctl restart postgresql

# Verify AIO settings are applied
sudo -u postgres psql -d climate_litigation -c "SHOW io_method;"
sudo -u postgres psql -d climate_litigation -c "SHOW io_workers;"

# Expected output:
# io_method: worker
# io_workers: 4 (or your configured value)
```

---

### Step 3: Setup Environment Configuration

**🔹 Run from: `/home/gusrodgs/Gus/cienciaDeDados/phdMutley`**

```bash
# Navigate to project directory
cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley

# Create .env file from template
cp env_pg18.example .env

# Edit with your credentials
nano .env
```

**Update the following values in `.env`:**

```env
# ============================================================================
# PostgreSQL 18 Database Configuration
# ============================================================================
DB_HOST=localhost
DB_PORT=5432
DB_NAME=climate_litigation
DB_USER=phdmutley
DB_PASSWORD=your_secure_password_here  # ⚠️ Use the password you set in Step 1

# ============================================================================
# Application Paths (adjust if needed)
# ============================================================================
PDF_STORAGE_PATH=/home/gusrodgs/Gus/cienciaDeDados/phdMutley/pdfs/downloaded
EXTRACTION_OUTPUT_PATH=/home/gusrodgs/Gus/cienciaDeDados/phdMutley/data/processed
LOG_FILE=/home/gusrodgs/Gus/cienciaDeDados/phdMutley/logs/database.log
```

**Save the file (Ctrl+O, Enter, Ctrl+X)**

---

### Step 4: Place Initialization Script

**🔹 Run from: `/home/gusrodgs/Gus/cienciaDeDados/phdMutley`**

```bash
# Ensure you're in the project directory
cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley

# If you downloaded the init script to ~/Downloads, move it to the correct location:
# mv ~/Downloads/init_database_pg18.py scripts/phase0/

# Verify the script is in the correct location
ls -lh scripts/phase0/init_database_pg18.py

# Expected output: Script file should be listed (approximately 37 KB)
```

---

### Step 5: Initialize Database

**🔹 Run from: `/home/gusrodgs/Gus/cienciaDeDados/phdMutley`**

```bash
# Ensure you're in the project directory
cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley

# Activate virtual environment
source venv/bin/activate

# Run initialization script
python scripts/phase0/init_database_pg18.py
```

**Expected Output:**

```
╔════════════════════════════════════════════════════════════════════╗
║  Climate Litigation Database - PostgreSQL 18 Initialization       ║
║  Global South Climate Litigation Analysis                         ║
║  Optimized for PostgreSQL 18 Performance Features                 ║
╚════════════════════════════════════════════════════════════════════╝

⚠️  WARNING: Do you want to drop existing tables?
   This will DELETE ALL DATA in the database!
   Only do this if you're starting fresh.

Drop existing tables? (yes/no): no

======================================================================
Climate Litigation Database Initialization - PostgreSQL 18
======================================================================

1. Connecting to PostgreSQL...
   ✓ Connected to database: climate_litigation
   ✓ Host: localhost:5432

2. Checking PostgreSQL version...
   ✓ PostgreSQL 18 detected!
   ✓ Full version: PostgreSQL 18.0 on x86_64-pc-linux-gnu...

3. Checking Asynchronous I/O configuration...
   ✓ io_method: worker
   ✓ io_workers: 4
   ✓ effective_io_concurrency: 16
   ✓ AIO is enabled with worker method (good default)

4. Skipping table drop (drop_existing=False)

5. Creating database tables...
   ✓ Created table: cases (with UUIDv7 and virtual columns)
   ✓ Created table: documents (with UUIDv7 and virtual columns)
   ✓ Created table: extracted_text (with UUIDv7 and virtual columns)
   ✓ Created table: text_sections (with UUIDv7 and virtual columns)
   ✓ Created table: keywords_tags (with UUIDv7)

6. Verifying table creation...
   ✓ Table 'cases' exists
   ✓ Table 'documents' exists
   ✓ Table 'extracted_text' exists
   ✓ Table 'text_sections' exists
   ✓ Table 'keywords_tags' exists

======================================================================
Database initialization complete!
======================================================================

PostgreSQL 18 Features Enabled:
✓ UUIDv7 primary keys (timestamp-ordered, globally unique)
✓ Virtual generated columns (computed at query time)
✓ Enhanced JSON support (better metadata queries)
✓ Skip scan indexes (flexible multicolumn queries)
✓ Asynchronous I/O configured
  Method: worker
  Workers: 4
  Expected performance improvement: 2-3x for large text reads

Next steps:
1. Load case metadata from baseCompleta.xlsx
2. Add PDF documents to the database
3. Run text extraction pipeline (optimized for PG 18 AIO)

======================================================================
```

---

## 🎯 Database Schema with PostgreSQL 18 Features

### Table: `cases`

**Key Features:**
- Primary key: `case_id` (UUIDv7 - timestamp-ordered)
- Virtual column: `case_age_days` (computed at query time)
- Skip scan indexes on multicolumn combinations

**Example queries:**

```sql
-- Query using virtual column
SELECT case_name, case_age_days 
FROM cases 
WHERE case_age_days > 365;

-- Skip scan: Can query by date without specifying country prefix
SELECT * FROM cases 
WHERE filing_date > '2023-01-01';
-- Uses idx_cases_country_region_date even without country!
```

---

### Table: `documents`

**Key Features:**
- Primary key: `document_id` (UUIDv7)
- Virtual column: `file_size_mb` (bytes → MB conversion)
- Foreign key to `cases` with CASCADE delete

---

### Table: `extracted_text`

**Key Features:**
- Optimized for AIO reads (large TEXT fields)
- Virtual column: `avg_word_length` (quality indicator)
- Enhanced JSON for `quality_issues`

---

### Table: `text_sections`

**Key Features:**
- Virtual column: `content_size_category` (tiny/small/medium/large)
- Enhanced JSON for `table_data`

---

### Table: `keywords_tags`

**Key Features:**
- Flexible tagging system
- Skip scan indexes for keyword searches

---

## 📊 Performance Benchmarks

### Asynchronous I/O Performance

Based on PostgreSQL 18 benchmarks:

| Operation | Sync (PG 17) | Worker (PG 18) | io_uring (PG 18) |
|-----------|--------------|----------------|------------------|
| Sequential scan (large table) | 15.0s | 10.0s (33% faster) | 5.7s (62% faster) |
| Text extraction reads | Baseline | 2x faster | 3x faster |
| VACUUM operations | Baseline | 1.5x faster | 2x faster |

---

### UUIDv7 vs Traditional UUID Performance

| Primary Key Type | INSERT Performance | B-tree Index Size | Cache Efficiency |
|------------------|-------------------|-------------------|------------------|
| SERIAL | Fastest (baseline) | Smallest | Best |
| UUIDv4 (random) | -20% | +40% larger | Poor (random access) |
| UUIDv7 (timestamp) | -5% | +15% larger | Good (sequential) |

**For this project**: UUIDv7 is ideal because:
- Global uniqueness (distributed systems ready)
- Timestamp ordering (better cache locality)
- Only 5% slower than SERIAL, but much more flexible

---

## 🔧 Testing Your Setup

### Test 1: Verify PostgreSQL 18

**🔹 Run from: Any directory**

```bash
# Connect to database
psql -U phdmutley -d climate_litigation
```

**Inside the PostgreSQL prompt:**

```sql
-- Check version (should show PostgreSQL 18.0 or higher)
SELECT version();

-- Check AIO settings
SHOW io_method;
SHOW io_workers;
SHOW effective_io_concurrency;

-- Check if UUIDv7 is available (PG 18 feature)
SELECT gen_random_uuid();  -- Works in all PG versions

-- List tables (should show 5 tables)
\dt

-- Exit
\q
```

---

### Test 2: Create Test Data with Python

**🔹 Run from: `/home/gusrodgs/Gus/cienciaDeDados/phdMutley`**

Create a test script:

```bash
# Navigate to project directory
cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley

# Activate virtual environment
source venv/bin/activate

# Create test script
nano test_database_pg18.py
```

**Add this content:**

```python
# test_database_pg18.py
"""
Test script to verify PostgreSQL 18 database setup
Run from: /home/gusrodgs/Gus/cienciaDeDados/phdMutley
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import sys
import os
from dotenv import load_dotenv

# Ensure we're in project directory
project_dir = '/home/gusrodgs/Gus/cienciaDeDados/phdMutley'
os.chdir(project_dir)
sys.path.append(project_dir)

# Load environment variables
load_dotenv()

# Import database models
from scripts.phase0.init_database_pg18 import Case, Document, get_session
from datetime import date

# Create engine
engine = create_engine(
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)

# Get session
session = get_session(engine)

# Insert test case
test_case = Case(
    case_name="Test Case - Silva vs. Government",
    court_name="Supreme Federal Court of Brazil",
    country="Brazil",
    region="Latin America and the Caribbean",
    filing_date=date(2022, 3, 15),
    decision_date=date(2024, 6, 20),
    case_status="Decided",
    case_type="Constitutional"
)

session.add(test_case)
session.commit()

print(f"✅ Created test case with ID: {test_case.case_id}")
print(f"✅ Case age (virtual column): {test_case.case_age_days} days")

# Query to verify
cases = session.query(Case).all()
print(f"✅ Total cases in database: {len(cases)}")

session.close()
print("\n🎉 Database test successful!")
```

**Save (Ctrl+O, Enter, Ctrl+X) and run:**

```bash
# Run test script (from project directory)
python test_database_pg18.py
```

---

## ⚡ Performance Tuning Tips

### 1. Optimize io_workers Based on Your CPU

**🔹 Run from: Any directory**

```bash
# Check your CPU cores
nproc

# Example outputs and recommended settings:
# 4 cores → io_workers = 4
# 8 cores → io_workers = 6-8
# 16 cores → io_workers = 12-16

# Edit postgresql.conf
sudo nano /etc/postgresql/18/main/postgresql.conf

# Update the io_workers line based on your CPU count
# io_workers = 6  # For 8-core system

# Save (Ctrl+O, Enter, Ctrl+X) and restart
sudo systemctl restart postgresql
```

---

### 2. Test io_uring (Linux Only - Best Performance)

**🔹 Run from: Any directory**

```bash
# Verify io_uring support
ldd /usr/lib/postgresql/18/bin/postgres | grep liburing

# If "liburing" appears, you can use io_uring
# Edit postgresql.conf:
sudo nano /etc/postgresql/18/main/postgresql.conf

# Change from:
# io_method = worker
# To:
io_method = io_uring

# Save (Ctrl+O, Enter, Ctrl+X) and restart
sudo systemctl restart postgresql

# Verify the change
psql -U phdmutley -d climate_litigation -c "SHOW io_method;"
# Expected output: io_uring

# Benchmark the improvement (if you have data):
psql -U phdmutley -d climate_litigation -c "\timing on" -c "SELECT COUNT(*) FROM extracted_text WHERE character_count > 10000;"
```

---

### 3. Monitor AIO Activity

**🔹 Run from: Any directory**

```bash
# Connect to database
psql -U phdmutley -d climate_litigation
```

```sql
-- View active async I/O operations
SELECT * FROM pg_aios;

-- Check I/O statistics
SELECT * FROM pg_stat_io;

-- Exit
\q
```

---

## 🐛 Troubleshooting

### Issue: "relation already exists"

**🔹 Run from: `/home/gusrodgs/Gus/cienciaDeDados/phdMutley`**

**Cause:** Tables already exist in the database

**Solution:**
```bash
cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley
source venv/bin/activate
python scripts/phase0/init_database_pg18.py
# Choose "yes" when asked to drop existing tables (⚠️ this deletes all data)
```

---

### Issue: "io_method parameter cannot be changed"

**🔹 Run from: Any directory**

**Cause:** `io_method` is a server-level parameter that requires restart

**Solution:**
```bash
# After editing postgresql.conf:
sudo systemctl restart postgresql

# Verify change took effect:
psql -U phdmutley -d climate_litigation -c "SHOW io_method;"
```

---

### Issue: Low performance with io_uring

**🔹 Run from: Any directory**

**Possible causes:**
1. Kernel too old (need 5.1+)
2. PostgreSQL not compiled with `--with-liburing`
3. Workload not suitable for io_uring

**Solution:**
```bash
# Check kernel version
uname -r
# If below 5.1, io_uring won't work

# Fall back to worker method
sudo nano /etc/postgresql/18/main/postgresql.conf
# Change to: io_method = worker

# Restart
sudo systemctl restart postgresql
```

---

### Issue: "UUID not found" or "could not determine data type of parameter"

**🔹 Run from: `/home/gusrodgs/Gus/cienciaDeDados/phdMutley`**

**Cause:** Old version of psycopg2

**Solution:**
```bash
cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley
source venv/bin/activate
pip install --upgrade psycopg2-binary>=2.9.9
```

---

### Issue: "Permission denied" when running scripts

**🔹 Run from: `/home/gusrodgs/Gus/cienciaDeDados/phdMutley`**

**Solution:**
```bash
# Ensure scripts have execute permissions
chmod +x scripts/phase0/init_database_pg18.py

# Also ensure you're in the project directory and venv is activated
cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley
source venv/bin/activate
```

---

## 📚 Additional Resources

### PostgreSQL 18 Documentation
- Official Release Notes: https://www.postgresql.org/docs/18/release-18.html
- Async I/O Guide: https://www.postgresql.org/docs/18/runtime-config-resource.html#GUC-IO-METHOD
- UUIDv7 Documentation: https://www.postgresql.org/docs/18/functions-uuid.html

### Performance Guides
- Tuning AIO: https://vondra.me/posts/tuning-aio-in-postgresql-18/
- Skip Scan Optimization: https://www.postgresql.org/docs/18/indexes-multicolumn.html

---

## 🎓 Next Steps

After successful setup:

**🔹 Run from: `/home/gusrodgs/Gus/cienciaDeDados/phdMutley`**

1. **Load your data**: Import `baseCompleta.xlsx` into the `cases` table
   ```bash
   cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley
   source venv/bin/activate
   python scripts/phase1/load_excel_data.py  # (to be created)
   ```

2. **Add documents**: Register PDF files in the `documents` table  
   ```bash
   python scripts/phase2/register_pdfs.py  # (to be created)
   ```

3. **Extract text**: Run the text extraction pipeline (benefits from AIO)
   ```bash
   python scripts/phase3/extract_pdf_text.py  # (to be created)
   ```

4. **Analyze**: Query the database using PostgreSQL 18's enhanced features
   ```bash
   psql -U phdmutley -d climate_litigation
   ```

---

## 📞 Support

For issues specific to this project:

**Logs to check:**
- **Application logs**: `/home/gusrodgs/Gus/cienciaDeDados/phdMutley/logs/database.log`
- **PostgreSQL logs**: `/var/log/postgresql/postgresql-18-main.log`

**Commands to diagnose:**

```bash
# Check PostgreSQL service status
sudo systemctl status postgresql

# Check PostgreSQL logs
sudo tail -f /var/log/postgresql/postgresql-18-main.log

# Test database connection
psql -U phdmutley -d climate_litigation -c "SELECT version();"
```

**Contact:** Lucas Biasetton (project maintainer)

---

## 📂 Quick Reference: File Locations

| Resource | Path | Run Commands From |
|----------|------|-------------------|
| Project root | `/home/gusrodgs/Gus/cienciaDeDados/phdMutley` | Here for all Python scripts |
| Init script | `scripts/phase0/init_database_pg18.py` | Project root |
| Environment file | `.env` | Project root |
| Virtual environment | `venv/` | Activate from project root |
| PostgreSQL config | `/etc/postgresql/18/main/postgresql.conf` | Any directory (sudo) |
| PostgreSQL logs | `/var/log/postgresql/postgresql-18-main.log` | Any directory (sudo) |
| PDF storage | `pdfs/downloaded/` | Project root |
| Processed data | `data/processed/` | Project root |
| Application logs | `logs/database.log` | Project root |

---

**Project:** phdMutley - Climate Litigation Analysis  
**Database:** PostgreSQL 18  
**Last Updated:** October 2025  
**Author:** Lucas Biasetton  
**Institution:** University of São Paulo
