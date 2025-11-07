# PostgreSQL 18 Database - Quick Start Guide

## 📁 Project Directory Reference

**Main Project Directory:** `/home/gusrodgs/Gus/cienciaDeDados/phdMutley`

All file paths in this guide are relative to this directory unless otherwise specified.

---

## 🚀 Fast Setup (5 Steps)

### Step 1: Install PostgreSQL 18 (NOT older versions!)

**🔹 Run from: Any directory (system-level commands)**

```bash
# Add PostgreSQL official repository
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
echo "deb http://apt.postgresql.org/pub/repos/apt/ $(lsb_release -cs)-pgdg main" | sudo tee /etc/apt/sources.list.d/pgdg.list

# Install PostgreSQL 18
sudo apt update
sudo apt install -y postgresql-18 postgresql-contrib-18

# Start service
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Verify version (MUST show 18.x)
psql --version
```

---

### Step 2: Create Database

**🔹 Run from: Any directory (PostgreSQL commands)**

```bash
# Connect to PostgreSQL as postgres superuser
sudo -u postgres psql
```

**Then inside the PostgreSQL prompt, run these SQL commands:**

```sql
-- Create database
CREATE DATABASE climate_litigation;

-- Create user with password
CREATE USER phdmutley WITH PASSWORD 'your_secure_password';

-- Grant database-level privileges
GRANT ALL PRIVILEGES ON DATABASE climate_litigation TO phdmutley;

-- Connect to the database
\c climate_litigation

-- Grant schema-level privileges (PostgreSQL 18 requirement)
GRANT ALL ON SCHEMA public TO phdmutley;
GRANT ALL ON ALL TABLES IN SCHEMA public TO phdmutley;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO phdmutley;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO phdmutley;

-- Exit PostgreSQL
\q
```

---

### Step 3: Configure Asynchronous I/O (Performance Boost!)

**🔹 Run from: Any directory (system configuration)**

```bash
# Edit PostgreSQL configuration file
sudo nano /etc/postgresql/18/main/postgresql.conf
```

**Add these lines at the end of the file:**

```conf
# ============================================================================
# PostgreSQL 18 Async I/O (2-3x faster reads)
# ============================================================================
io_method = worker              # Start with 'worker' (cross-platform)
io_workers = 4                  # 25-50% of CPU cores (adjust for your system)
effective_io_concurrency = 16   # Default in PG 18
maintenance_io_concurrency = 16 # For VACUUM, CREATE INDEX
```

**Save the file (Ctrl+O, Enter, Ctrl+X), then restart PostgreSQL:**

```bash
sudo systemctl restart postgresql
```

---

### Step 4: Setup Project Environment

**🔹 Run from: `/home/gusrodgs/Gus/cienciaDeDados/phdMutley`**

```bash
# Navigate to project directory
cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley

# Activate virtual environment
source venv/bin/activate

# Install required Python packages
pip install sqlalchemy>=2.0.23 psycopg2-binary>=2.9.9 python-dotenv>=1.0.0

# Alternative: Install from requirements file
# pip install -r requirements_pg18.txt

# Create .env file from template
cp env_pg18.example .env

# Edit .env file with your credentials
nano .env
```

**In the `.env` file, update these values:**

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=climate_litigation
DB_USER=phdmutley
DB_PASSWORD=your_secure_password  # ⚠️ Use the password you set in Step 2
```

**Save the file (Ctrl+O, Enter, Ctrl+X)**

---

### Step 5: Initialize Database

**🔹 Run from: `/home/gusrodgs/Gus/cienciaDeDados/phdMutley`**

```bash
# Ensure you're in the project directory
cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley

# Ensure virtual environment is activated
source venv/bin/activate

# Place the initialization script in the correct location (if not already there)
# If you downloaded it, move it:
# mv ~/Downloads/init_database_pg18.py scripts/phase0/

# Run the database initialization script
python scripts/phase0/init_database_pg18.py
```

**When prompted:** 
- Type `no` to keep existing data (if any)
- Type `yes` to start fresh (⚠️ this will delete all existing data)

---

## ✅ Verification

**🔹 Run from: Any directory (PostgreSQL commands)**

### Test 1: Check PostgreSQL Connection and Version

```bash
# Connect to database
psql -U phdmutley -d climate_litigation
```

**Inside the PostgreSQL prompt:**

```sql
-- Check PostgreSQL version (should show 18.0 or higher)
SELECT version();

-- Check AIO settings
SHOW io_method;      -- Should show: worker
SHOW io_workers;     -- Should show: 4 (or your configured value)

-- List all tables (should show 5 tables)
\dt

-- Exit
\q
```

**Expected output:**
- PostgreSQL 18.0 or higher
- io_method: worker
- 5 tables: `cases`, `documents`, `extracted_text`, `text_sections`, `keywords_tags`

---

### Test 2: Test with Python

**🔹 Run from: `/home/gusrodgs/Gus/cienciaDeDados/phdMutley`**

Create a test script:

```bash
# Navigate to project directory
cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley

# Activate virtual environment
source venv/bin/activate

# Create test file
nano test_pg18_connection.py
```

**Add this content:**

```python
# test_pg18_connection.py
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create database connection
engine = create_engine(
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)

# Test queries
with engine.connect() as conn:
    # Check version
    result = conn.execute(text("SELECT version()"))
    print("✅ Connected to:", result.scalar()[:60])
    
    # Check AIO method
    result = conn.execute(text("SHOW io_method"))
    print("✅ AIO Method:", result.scalar())
    
    # Count tables
    result = conn.execute(text(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"
    ))
    print("✅ Number of tables:", result.scalar())
    
    # Count cases
    result = conn.execute(text("SELECT COUNT(*) FROM cases"))
    print("✅ Cases in database:", result.scalar())

print("\n🎉 Database is ready!")
```

**Save the file (Ctrl+O, Enter, Ctrl+X), then run it:**

```bash
# Run test script
python test_pg18_connection.py
```

---

## 🎯 What You Get

### PostgreSQL 18 Features Enabled:

✅ **UUIDv7 Primary Keys**: Timestamp-ordered, globally unique  
✅ **Virtual Columns**: Computed values (`case_age_days`, `file_size_mb`, etc.)  
✅ **Async I/O**: 2-3x faster reads for large text extraction  
✅ **Skip Scan Indexes**: Flexible multicolumn queries  
✅ **Enhanced JSON**: Better performance for metadata  
✅ **Data Checksums**: Integrity validation (default in PG 18)

### Performance Expectations:

| Operation | Before (PG 17) | After (PG 18) |
|-----------|----------------|---------------|
| Large text reads | Baseline | 2-3x faster |
| PDF extraction | Baseline | 2x faster |
| Sequential scans | Baseline | 2-3x faster |

---

## 🔧 Performance Tuning (Optional)

### Try io_uring for 3x speed (Linux only):

**🔹 Run from: Any directory (system configuration)**

```bash
# Check kernel version (need 5.1+)
uname -r

# Check if PostgreSQL is compiled with liburing
ldd /usr/lib/postgresql/18/bin/postgres | grep liburing

# If available, edit postgresql.conf:
sudo nano /etc/postgresql/18/main/postgresql.conf

# Change this line:
# io_method = worker
# To:
io_method = io_uring

# Save (Ctrl+O, Enter, Ctrl+X) and restart
sudo systemctl restart postgresql
```

---

### Adjust workers based on CPU:

**🔹 Run from: Any directory**

```bash
# Check CPU cores
nproc

# For 8 cores, set io_workers = 6-8
# Edit postgresql.conf
sudo nano /etc/postgresql/18/main/postgresql.conf

# Update this line based on your CPU count:
io_workers = 6  # For 8-core system

# Save and restart
sudo systemctl restart postgresql
```

---

## 🛠 Common Issues

### Issue: "Could not connect to server"

**🔹 Run from: Any directory**

```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Start PostgreSQL if stopped
sudo systemctl start postgresql
```

---

### Issue: "Password authentication failed"

**🔹 Run from: Any directory**

```bash
# Test connection manually
psql -U phdmutley -d climate_litigation

# If fails, verify credentials in .env match PostgreSQL user
```

**🔹 To reset password (if needed):**

```bash
sudo -u postgres psql
```

```sql
ALTER USER phdmutley WITH PASSWORD 'new_password';
\q
```

Then update your `.env` file with the new password.

---

### Issue: "Permission denied for schema public"

**🔹 Run from: Any directory**

```bash
sudo -u postgres psql -d climate_litigation
```

```sql
GRANT ALL ON SCHEMA public TO phdmutley;
GRANT ALL ON ALL TABLES IN SCHEMA public TO phdmutley;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO phdmutley;
\q
```

---

### Issue: "io_method parameter cannot be changed"

**🔹 Run from: Any directory**

```bash
# io_method requires PostgreSQL restart
sudo systemctl restart postgresql

# Verify the change
psql -U phdmutley -d climate_litigation -c "SHOW io_method;"
```

---

## 📂 File Locations Reference

| File/Directory | Full Path | Purpose |
|----------------|-----------|---------|
| Project root | `/home/gusrodgs/Gus/cienciaDeDados/phdMutley` | Main working directory |
| Init script | `/home/gusrodgs/Gus/cienciaDeDados/phdMutley/scripts/phase0/init_database_pg18.py` | Database setup script |
| Environment config | `/home/gusrodgs/Gus/cienciaDeDados/phdMutley/.env` | Database credentials |
| Virtual environment | `/home/gusrodgs/Gus/cienciaDeDados/phdMutley/venv` | Python packages |
| PostgreSQL config | `/etc/postgresql/18/main/postgresql.conf` | Server settings |
| PostgreSQL logs | `/var/log/postgresql/postgresql-18-main.log` | Error logs |

---

## 📚 Next Steps

**🔹 Run from: `/home/gusrodgs/Gus/cienciaDeDados/phdMutley`**

1. **Load your data**: Import `baseCompleta.xlsx` into `cases` table
   ```bash
   cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley
   source venv/bin/activate
   python scripts/phase1/load_excel_data.py  # (to be created)
   ```

2. **Add PDFs**: Register files in `documents` table
   ```bash
   python scripts/phase2/register_pdfs.py  # (to be created)
   ```

3. **Extract text**: Run extraction pipeline (benefits from AIO)
   ```bash
   python scripts/phase3/extract_pdf_text.py  # (to be created)
   ```

4. **Analyze**: Query with PostgreSQL 18 features
   ```bash
   psql -U phdmutley -d climate_litigation
   ```

---

## 🆘 Need Help?

- **Full guide**: Read `README_PG18_SETUP.md`
- **PostgreSQL 18 docs**: https://www.postgresql.org/docs/18/
- **Project logs**: Check `/home/gusrodgs/Gus/cienciaDeDados/phdMutley/logs`
- **PostgreSQL logs**: Check `/var/log/postgresql/postgresql-18-main.log`

---

## ✅ Success Checklist

After completing this guide, verify:

- [ ] PostgreSQL 18.x is installed (`psql --version`)
- [ ] Database `climate_litigation` exists
- [ ] User `phdmutley` can connect
- [ ] AIO is configured (`io_method = worker` or `io_uring`)
- [ ] 5 tables created (cases, documents, extracted_text, text_sections, keywords_tags)
- [ ] Virtual columns work (query `case_age_days`)
- [ ] UUIDv7 primary keys are generated
- [ ] Python packages installed (SQLAlchemy 2.0+, psycopg2 2.9.9+)
- [ ] `.env` file configured with correct credentials
- [ ] Test script runs successfully

---

**Project:** phdMutley - Climate Litigation Analysis  
**Database:** PostgreSQL 18  
**Author:** Lucas Biasetton  
**Date:** October 2025
