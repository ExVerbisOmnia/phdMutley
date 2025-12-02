# PhD Climate Litigation Project - AI Agent Context File
## Complete Project Documentation for IDE AI Integration

**Last Updated:** December 01, 2025  
**Project:** Doutorado PM - Climate Litigation Citation Analysis  
**Researcher:** Gustavo Rodrigues  
**Academic Collaborator:** Lucas Biasetton  
**Current Phase:** Phase 3 - Web Deployment via Railway

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
  - `citation_sixfold_classification` - Sixfold classification results
  - `first_analysis` - Analysis query results

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

#### **Phase 2b: Citation Extraction v5** (COMPLETE)
- ✅ Complete 4-phase architecture implemented
- ✅ Enhanced dictionaries: 80+ foreign courts, 20+ landmark cases
- ✅ 3-tier origin identification system
- ✅ Comprehensive extraction: 12 citation format patterns
- ✅ Caching system for repeated citations
- ✅ Automatic quality control with confidence-based flagging
- ✅ Production-ready code: 1,650+ lines, fully documented

#### **Phase 2c: Sixfold Classification Analysis** (COMPLETE)
- ✅ sixfold_analysis_engine.py - Complete analysis logic (2,164 lines)
- ✅ api_server.py - Flask REST API (987 lines)
- ✅ dashboard.html - Frontend visualization (1,495 lines)
- ✅ All analytical queries implemented
- ✅ Network visualization data generation
- ✅ Dashboard aggregates ready

### ⏳ CURRENT PHASE: Web Deployment

#### **Phase 3: Railway Deployment** (IN PROGRESS)
- ⏳ Prepare production-ready files
- ⏳ Configure Railway services
- ⏳ Migrate PostgreSQL database
- ⏳ Deploy Flask API
- ⏳ Deploy static frontend
- ⏳ Test and verify

---

## 🚀 RAILWAY DEPLOYMENT GUIDE

### Overview

This section provides **complete, step-by-step instructions** for deploying the application to Railway. The deployment consists of three services:

1. **PostgreSQL Database** - Managed database service
2. **Flask API** - Python web service running api_server.py
3. **Static Frontend** - dashboard.html served as static site

### Target Architecture

```
┌─────────────────────────── Railway Project ────────────────────────────┐
│                                                                         │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    │
│  │                 │    │                 │    │                 │    │
│  │  Static Site    │───▶│  Flask API      │───▶│  PostgreSQL     │    │
│  │  dashboard.html │    │  api_server.py  │    │  (Managed)      │    │
│  │                 │    │                 │    │                 │    │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘    │
│         │                       │                      │               │
│   Public URL             Internal Network         DATABASE_URL        │
│   (*.up.railway.app)     (auto-configured)       (auto-injected)      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 FILES TO CREATE FOR DEPLOYMENT

### File 1: `requirements.txt`

**Location:** `/home/gusrodgs/Gus/cienciaDeDados/phdMutley/scripts/8-python_back_engine/requirements.txt`

**Purpose:** Declares all Python dependencies for Railway to install.

```txt
# =============================================================================
# REQUIREMENTS.TXT - Railway Deployment Dependencies
# =============================================================================
# PhD Climate Litigation Project - Sixfold Citation Analysis API
# Last Updated: December 01, 2025
# =============================================================================

# --- Web Framework ---
flask>=3.0.0
flask-cors>=4.0.0

# --- Database ---
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.9

# --- Production Server ---
gunicorn>=21.0.0

# --- Data Processing ---
pandas>=2.0.0

# --- Environment ---
python-dotenv>=1.0.0

# --- Utilities ---
# Note: These are used by sixfold_analysis_engine.py
```

---

### File 2: `Procfile`

**Location:** `/home/gusrodgs/Gus/cienciaDeDados/phdMutley/scripts/8-python_back_engine/Procfile`

**Purpose:** Tells Railway how to start the application.

```
web: gunicorn --bind 0.0.0.0:$PORT --workers 4 --timeout 120 api_server:app
```

**Notes:**
- `$PORT` is automatically injected by Railway
- 4 workers handle concurrent requests
- 120s timeout for long-running analysis queries

---

### File 3: `railway.toml`

**Location:** `/home/gusrodgs/Gus/cienciaDeDados/phdMutley/scripts/8-python_back_engine/railway.toml`

**Purpose:** Railway-specific configuration.

```toml
# =============================================================================
# RAILWAY.TOML - Railway Platform Configuration
# =============================================================================
# PhD Climate Litigation Project - Sixfold Citation Analysis API
# =============================================================================

[build]
builder = "nixpacks"

[deploy]
startCommand = "gunicorn --bind 0.0.0.0:$PORT --workers 4 --timeout 120 api_server:app"
healthcheckPath = "/api/health"
healthcheckTimeout = 30
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 3
```

---

### File 4: `runtime.txt`

**Location:** `/home/gusrodgs/Gus/cienciaDeDados/phdMutley/scripts/8-python_back_engine/runtime.txt`

**Purpose:** Specifies Python version.

```
python-3.11.7
```

**Note:** Using 3.11 for stability. Railway's nixpacks supports it well.

---

### File 5: Updated `api_server.py`

**Location:** `/home/gusrodgs/Gus/cienciaDeDados/phdMutley/scripts/8-python_back_engine/api_server.py`

**Purpose:** Modified Flask API with production environment support.

**CRITICAL CHANGES TO MAKE:**

#### Change 1: Add Production Database URL Handling (after imports, before Flask app)

Add this block after line 66 (after the imports from sixfold_analysis_engine):

```python
# =============================================================================
# PRODUCTION ENVIRONMENT CONFIGURATION
# =============================================================================

import os

# Handle Railway's DATABASE_URL format
# Railway provides postgres:// but SQLAlchemy 2.0+ requires postgresql://
_database_url = os.getenv('DATABASE_URL')
if _database_url:
    if _database_url.startswith('postgres://'):
        _database_url = _database_url.replace('postgres://', 'postgresql://', 1)
    DATABASE_URL = _database_url
# else: use the DATABASE_URL imported from sixfold_analysis_engine (local dev)

# Determine environment
IS_PRODUCTION = os.getenv('RAILWAY_ENVIRONMENT') is not None
```

#### Change 2: Update CORS Configuration (around line 78)

Replace the CORS configuration:

```python
# Enable CORS for frontend access
# In production, we allow the Railway frontend domain
# In development, we allow localhost and file:// access
if IS_PRODUCTION:
    # Get the frontend URL from environment or allow all Railway domains
    frontend_url = os.getenv('FRONTEND_URL', '*')
    CORS(app, resources={r"/api/*": {"origins": frontend_url}})
else:
    # Development: allow all origins
    CORS(app, resources={r"/api/*": {"origins": "*"}})
```

#### Change 3: Update get_engine() function (around line 88)

Modify to use the production DATABASE_URL:

```python
def get_engine() -> SixfoldAnalysisEngine:
    """
    Get or create the analysis engine singleton.
    Uses production DATABASE_URL if available, otherwise falls back to local.
    
    Returns:
    --------
    SixfoldAnalysisEngine : Initialized engine instance
    """
    global _engine
    if _engine is None:
        # Use our processed DATABASE_URL (handles postgres:// → postgresql://)
        db_url = DATABASE_URL
        _engine = SixfoldAnalysisEngine(database_url=db_url)
        
        if IS_PRODUCTION:
            app.logger.info("Connected to PRODUCTION database")
        else:
            app.logger.info("Connected to LOCAL database")
    return _engine
```

#### Change 4: Add Production Logging (at the top of the file, after imports)

```python
# Configure logging for production
if os.getenv('RAILWAY_ENVIRONMENT'):
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
```

---

### File 6: Updated `sixfold_analysis_engine.py`

**Location:** `/home/gusrodgs/Gus/cienciaDeDados/phdMutley/scripts/8-python_back_engine/sixfold_analysis_engine.py`

**Purpose:** Modified analysis engine with production database support.

**CRITICAL CHANGES TO MAKE:**

#### Change 1: Update Database URL Handling (around line 76-86)

Replace the existing DATABASE_URL construction:

```python
# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================

# Check for Railway's DATABASE_URL first (production)
_railway_url = os.getenv('DATABASE_URL')

if _railway_url:
    # Production: Use Railway's provided URL
    # Handle postgres:// vs postgresql:// (SQLAlchemy 2.0+ requires postgresql://)
    if _railway_url.startswith('postgres://'):
        DATABASE_URL = _railway_url.replace('postgres://', 'postgresql://', 1)
    else:
        DATABASE_URL = _railway_url
else:
    # Development: Build from individual components
    DB_USER = os.getenv('DB_USER', 'phdmutley')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_NAME = os.getenv('DB_NAME', 'climate_litigation')
    
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Log which environment we're using
logger.info(f"Database: {'PRODUCTION (Railway)' if _railway_url else 'LOCAL'}")
```

#### Change 2: Update Output Directories for Production (around line 89-91)

Replace:

```python
# Output directories for external data storage
# In production (Railway), use /tmp which is writable
# In development, use local directory
if os.getenv('RAILWAY_ENVIRONMENT'):
    OUTPUT_DIR = Path('/tmp/analysis_output')
else:
    OUTPUT_DIR = Path('./analysis_output')

NETWORK_DIR = OUTPUT_DIR / 'network_data'
DASHBOARD_DIR = OUTPUT_DIR / 'dashboard_data'
```

---

### File 7: Updated `dashboard.html`

**Location:** `/home/gusrodgs/Gus/cienciaDeDados/phdMutley/scripts/8-python_back_engine/frontend/dashboard.html`

**Purpose:** Frontend with dynamic API URL detection.

**CRITICAL CHANGES TO MAKE:**

#### Change 1: Update API Base URL Configuration (around line 763)

Replace:

```javascript
const API_BASE = 'http://127.0.0.1:5000/api';
```

With:

```javascript
// ================================================================
// API CONFIGURATION - Auto-detect environment
// ================================================================

// Determine API base URL based on current environment
// Production: Use Railway API URL
// Development: Use localhost
const API_BASE = (() => {
    const hostname = window.location.hostname;
    
    // Production: If we're on Railway (*.up.railway.app)
    if (hostname.includes('railway.app')) {
        // Replace with your actual Railway API service URL
        // This will be updated after deployment
        return 'https://YOUR-API-SERVICE.up.railway.app/api';
    }
    
    // Production: If served from a custom domain
    if (hostname !== 'localhost' && hostname !== '127.0.0.1' && !hostname.includes('file://')) {
        // Assume API is at same domain with /api path
        return `${window.location.origin}/api`;
    }
    
    // Development: localhost
    return 'http://127.0.0.1:5000/api';
})();

console.log('API Base URL:', API_BASE);
```

**Note:** After deployment, you'll need to replace `YOUR-API-SERVICE.up.railway.app` with the actual Railway URL.

---

### File 8: Frontend Directory Structure

Create a `frontend/` subdirectory for static deployment:

```
scripts/8-python_back_engine/
├── api_server.py
├── sixfold_analysis_engine.py
├── requirements.txt
├── Procfile
├── railway.toml
├── runtime.txt
└── frontend/                    # NEW DIRECTORY
    ├── index.html              # Copy of dashboard.html (renamed)
    └── _redirects              # Optional: for SPA routing
```

**File: `frontend/_redirects`**

```
# Redirect all requests to index.html for SPA behavior
/*    /index.html   200
```

---

## 🔧 DATABASE MIGRATION SCRIPT

### File 9: `migrate_to_railway.sh`

**Location:** `/home/gusrodgs/Gus/cienciaDeDados/phdMutley/scripts/8-python_back_engine/migrate_to_railway.sh`

**Purpose:** Script to export local database and prepare for Railway import.

```bash
#!/bin/bash
# =============================================================================
# DATABASE MIGRATION SCRIPT - Local PostgreSQL to Railway
# =============================================================================
# PhD Climate Litigation Project
# Last Updated: December 01, 2025
# =============================================================================

set -e  # Exit on any error

# --- Configuration ---
LOCAL_DB_HOST="localhost"
LOCAL_DB_PORT="5432"
LOCAL_DB_NAME="climate_litigation"
LOCAL_DB_USER="phdmutley"

BACKUP_DIR="./db_backup"
BACKUP_FILE="${BACKUP_DIR}/climate_litigation_$(date +%Y%m%d_%H%M%S).sql"

# --- Create backup directory ---
mkdir -p "$BACKUP_DIR"

echo "=============================================="
echo "  DATABASE MIGRATION: Local → Railway"
echo "=============================================="
echo ""
echo "Step 1: Exporting local database..."
echo "----------------------------------------------"

# Export database (schema + data)
# --no-owner: Don't set ownership (Railway manages this)
# --no-acl: Don't include access privileges
# --clean: Include DROP statements before CREATE
pg_dump \
    -h "$LOCAL_DB_HOST" \
    -p "$LOCAL_DB_PORT" \
    -U "$LOCAL_DB_USER" \
    -d "$LOCAL_DB_NAME" \
    --no-owner \
    --no-acl \
    --clean \
    --if-exists \
    -f "$BACKUP_FILE"

echo "✓ Database exported to: $BACKUP_FILE"
echo "  Size: $(du -h "$BACKUP_FILE" | cut -f1)"
echo ""

echo "Step 2: Checking export..."
echo "----------------------------------------------"

# Count tables in export
TABLE_COUNT=$(grep -c "CREATE TABLE" "$BACKUP_FILE" || echo "0")
echo "✓ Tables found: $TABLE_COUNT"

# Show first few table names
echo "  Tables:"
grep "CREATE TABLE" "$BACKUP_FILE" | head -10 | sed 's/CREATE TABLE /    - /g' | sed 's/ (.*//g'
echo ""

echo "=============================================="
echo "  NEXT STEPS (Manual)"
echo "=============================================="
echo ""
echo "1. Create PostgreSQL on Railway:"
echo "   railway add --plugin postgresql"
echo ""
echo "2. Get Railway DATABASE_URL:"
echo "   railway variables"
echo ""
echo "3. Import to Railway:"
echo "   psql \"\$DATABASE_URL\" < $BACKUP_FILE"
echo ""
echo "   Or use Railway's web interface to import."
echo ""
echo "=============================================="
```

Make executable: `chmod +x migrate_to_railway.sh`

---

## 📋 STEP-BY-STEP DEPLOYMENT INSTRUCTIONS

### Prerequisites Checklist

Before starting deployment, ensure:

- [ ] Local PostgreSQL is running with data
- [ ] All Python scripts work locally
- [ ] dashboard.html loads correctly from localhost
- [ ] GitHub account available (for Railway deployment)
- [ ] Node.js installed (for Railway CLI)

---

### STEP 1: Install Railway CLI

```bash
# Install Railway CLI globally
npm install -g @railway/cli

# Verify installation
railway --version

# Login to Railway (opens browser)
railway login
```

---

### STEP 2: Create Railway Project

```bash
# Navigate to the backend directory
cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley/scripts/8-python_back_engine

# Initialize a new Railway project
railway init

# When prompted:
# - Choose "Create new project"
# - Name it: "climate-litigation-api" (or similar)
```

---

### STEP 3: Create PostgreSQL Database on Railway

```bash
# Add PostgreSQL plugin to the project
railway add

# When prompted, select: "PostgreSQL"
# This creates a managed PostgreSQL instance

# View the connection variables
railway variables

# You'll see something like:
# DATABASE_URL=postgres://postgres:xxxxx@containers-us-west-xxx.railway.app:5432/railway
# PGDATABASE=railway
# PGHOST=containers-us-west-xxx.railway.app
# PGPASSWORD=xxxxx
# PGPORT=5432
# PGUSER=postgres
```

---

### STEP 4: Migrate Local Database to Railway

```bash
# Option A: Using the migration script
./migrate_to_railway.sh

# Then import to Railway:
# Get the DATABASE_URL from railway variables
railway variables | grep DATABASE_URL

# Import the backup
psql "YOUR_DATABASE_URL_FROM_ABOVE" < ./db_backup/climate_litigation_*.sql
```

**Option B: Direct pipe (faster but no backup file)**

```bash
# Get Railway's DATABASE_URL
RAILWAY_URL=$(railway variables | grep DATABASE_URL | cut -d'=' -f2)

# Pipe directly
pg_dump -h localhost -U phdmutley -d climate_litigation --no-owner --no-acl | psql "$RAILWAY_URL"
```

---

### STEP 5: Verify Database Migration

```bash
# Connect to Railway database
railway connect postgres

# Or use psql directly:
psql "$RAILWAY_URL"

# Check tables exist
\dt

# Check row counts
SELECT 'cases' as table_name, COUNT(*) FROM cases
UNION ALL
SELECT 'documents', COUNT(*) FROM documents
UNION ALL
SELECT 'citation_sixfold_classification', COUNT(*) FROM citation_sixfold_classification;

# Expected output:
#            table_name           | count
# --------------------------------+-------
#  cases                          |  2924
#  documents                      |  2924
#  citation_sixfold_classification|  XXXX

\q  # Exit
```

---

### STEP 6: Create Deployment Files

Create all the files listed in the "FILES TO CREATE" section above:

```bash
cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley/scripts/8-python_back_engine

# Create requirements.txt
# (use content from File 1 above)

# Create Procfile
echo 'web: gunicorn --bind 0.0.0.0:$PORT --workers 4 --timeout 120 api_server:app' > Procfile

# Create railway.toml
# (use content from File 3 above)

# Create runtime.txt
echo 'python-3.11.7' > runtime.txt

# Create frontend directory
mkdir -p frontend

# Copy and rename dashboard
cp dashboard.html frontend/index.html

# Update API URL in frontend/index.html (see File 7 changes)
```

---

### STEP 7: Update Python Files for Production

Apply all changes specified in Files 5 and 6 above to:

- `api_server.py`
- `sixfold_analysis_engine.py`

---

### STEP 8: Deploy the API Service

```bash
cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley/scripts/8-python_back_engine

# Deploy to Railway
railway up

# This will:
# 1. Detect Python project (via requirements.txt)
# 2. Install dependencies
# 3. Run Procfile command
# 4. Assign a public URL

# Get the deployed URL
railway open

# Note the URL, something like:
# https://climate-litigation-api-production.up.railway.app
```

---

### STEP 9: Test the API

```bash
# Test health endpoint
curl https://YOUR-API-URL.up.railway.app/api/health

# Expected response:
# {
#   "status": "success",
#   "timestamp": "2025-12-01T...",
#   "data": {
#     "server": "running",
#     "version": "1.0.0",
#     "database": "connected"
#   }
# }

# Test dashboard endpoint
curl https://YOUR-API-URL.up.railway.app/api/dashboard/summary_stats
```

---

### STEP 10: Deploy Frontend

**Option A: Deploy as separate Railway service**

```bash
cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley/scripts/8-python_back_engine/frontend

# Initialize as new service in same project
railway init

# Select: "Add to existing project" → your project
# Name it: "climate-litigation-frontend"

# Create a simple static server config
echo '{"scripts":{"start":"npx serve ."}}' > package.json

# Deploy
railway up

# Get the frontend URL
railway open
```

**Option B: Use Railway's static hosting (simpler)**

In Railway dashboard:
1. Go to your project
2. Click "+ New" → "Empty Service"
3. Name it "frontend"
4. In Settings → Build → set build command to: `echo 'Static site'`
5. In Settings → Deploy → set start command to: `npx serve .`
6. Upload or connect frontend directory

---

### STEP 11: Update Frontend API URL

After you have both URLs:

1. Edit `frontend/index.html`
2. Find the `API_BASE` configuration
3. Replace `YOUR-API-SERVICE.up.railway.app` with actual API URL

```javascript
if (hostname.includes('railway.app')) {
    return 'https://climate-litigation-api-production.up.railway.app/api';
}
```

4. Redeploy frontend: `railway up`

---

### STEP 12: Final Verification

```bash
# 1. Open frontend in browser
# https://climate-litigation-frontend-production.up.railway.app

# 2. Check browser console for:
#    - "API Base URL: https://climate-litigation-api-..."
#    - No CORS errors
#    - Data loading correctly

# 3. Test all dashboard features:
#    - Summary stats loading
#    - Charts rendering
#    - Network visualization
#    - Table data
#    - Export functions
```

---

## 🔍 TROUBLESHOOTING

### Common Issues and Solutions

#### Issue: "postgres://" vs "postgresql://" Error

**Symptom:** SQLAlchemy throws error about invalid database URL

**Solution:** Already handled in code changes. Verify `DATABASE_URL` replacement is working:

```python
if _database_url.startswith('postgres://'):
    _database_url = _database_url.replace('postgres://', 'postgresql://', 1)
```

---

#### Issue: CORS Errors in Browser

**Symptom:** Console shows "Access-Control-Allow-Origin" errors

**Solution:** 
1. Check `FRONTEND_URL` environment variable in Railway
2. Or temporarily set CORS to allow all origins:
   ```python
   CORS(app, resources={r"/api/*": {"origins": "*"}})
   ```

---

#### Issue: Database Connection Timeout

**Symptom:** API returns 500 error, logs show connection timeout

**Solution:** Railway internal networking should auto-connect. Check:
1. PostgreSQL service is running (green in Railway dashboard)
2. DATABASE_URL variable is set correctly
3. Try restarting the API service

---

#### Issue: Gunicorn Worker Timeout

**Symptom:** Requests timeout after 30 seconds

**Solution:** Increase timeout in Procfile:
```
web: gunicorn --bind 0.0.0.0:$PORT --workers 4 --timeout 300 api_server:app
```

---

#### Issue: Static Files Not Loading

**Symptom:** Frontend shows but no styles/scripts

**Solution:** Ensure all CDN links use HTTPS:
```html
<script src="https://cdnjs.cloudflare.com/..."></script>
```

---

## 📊 MONITORING & LOGS

### View Logs in Railway

```bash
# Stream live logs
railway logs

# Or view in Railway dashboard:
# Project → Service → Deployments → View Logs
```

### Add Health Monitoring

The `/api/health` endpoint is configured as the healthcheck. Railway will:
- Check this endpoint every 30 seconds
- Restart service if it fails 3 times
- Show health status in dashboard

---

## 💰 COST MANAGEMENT

### Railway Free Tier Limits

| Resource | Free Tier |
|----------|-----------|
| Execution | $5 credit/month |
| PostgreSQL | Included in credit |
| Bandwidth | Included in credit |

### Expected Usage (PhD Presentation)

| Service | Est. Monthly Cost |
|---------|-------------------|
| API (light traffic) | ~$2-3 |
| PostgreSQL (small DB) | ~$1-2 |
| Frontend (static) | ~$0.50 |
| **Total** | **~$3-5 (within free tier)** |

---

## 🔐 ENVIRONMENT VARIABLES

### Required Variables (Set in Railway Dashboard)

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | Auto-set by Railway PostgreSQL | postgres://... |
| `FRONTEND_URL` | Your frontend URL (for CORS) | https://frontend.up.railway.app |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `RAILWAY_ENVIRONMENT` | Auto-set by Railway | production |
| `PORT` | Auto-set by Railway | 8080 |

---

## 📁 FINAL PROJECT STRUCTURE

After deployment setup:

```
/home/gusrodgs/Gus/cienciaDeDados/phdMutley/scripts/8-python_back_engine/
├── api_server.py              # Updated for production
├── sixfold_analysis_engine.py # Updated for production
├── config.py                  # Unchanged
├── requirements.txt           # NEW - Python dependencies
├── Procfile                   # NEW - Railway start command
├── railway.toml               # NEW - Railway configuration
├── runtime.txt                # NEW - Python version
├── migrate_to_railway.sh      # NEW - Database migration script
├── db_backup/                 # NEW - Database backups
│   └── climate_litigation_*.sql
└── frontend/                  # NEW - Static frontend
    ├── index.html             # Renamed from dashboard.html
    └── _redirects             # Optional SPA routing
```

---

## 🏗️ TECHNICAL ARCHITECTURE (Remainder unchanged from original)

[... Rest of original context file continues here ...]

---

## 💡 TIPS FOR AI AGENTS WORKING ON THIS PROJECT

### Understanding the Context

1. **This is PhD research:** Academic rigor and reproducibility are paramount
2. **Deadline is firm:** November 30, 2025 for December presentation
3. **Budget constraints:** Keep API costs reasonable (<$200 total)
4. **Collaborator Lucas:** Academic focus, I handle all technical implementation
5. **Documentation matters:** Everything must be thesis-worthy

### When Working on Deployment

- **Test locally first:** Verify api_server.py works before deploying
- **Check environment variables:** Ensure DATABASE_URL handling is correct
- **Monitor logs:** Railway provides real-time logs for debugging
- **Use incremental deployment:** Deploy API first, then frontend
- **Keep backups:** Always backup database before migration

### When Generating Code

- **Always test incrementally:** Don't write 500 lines without testing
- **Use existing patterns:** Follow established conventions in codebase
- **Think about costs:** Prefer Tier 1 (dictionary) over Tier 2 (API calls)
- **Consider the thesis:** Can this methodology be clearly explained?
- **Plan for errors:** Assume PDFs are messy, APIs fail, JSON is malformed

### What Not to Do

❌ **Don't deploy without testing locally first**
❌ **Don't skip database backup before migration**
❌ **Don't hardcode production URLs**
❌ **Don't ignore CORS configuration**
❌ **Don't forget to update frontend API URL after deployment**
❌ **Don't commit sensitive credentials to git**

### What Always to Do

✅ **Always test API endpoints after deployment**
✅ **Always verify database connection in production**
✅ **Always check browser console for errors**
✅ **Always use environment variables for configuration**
✅ **Always monitor Railway logs during initial deployment**
✅ **Always backup before making changes**

---

## 🎉 DEPLOYMENT CHECKLIST

### Pre-Deployment

- [ ] Local API works correctly
- [ ] Local dashboard loads and shows data
- [ ] All analytical queries return expected results
- [ ] Database has all required tables and data

### Deployment Files

- [ ] `requirements.txt` created with all dependencies
- [ ] `Procfile` created with gunicorn command
- [ ] `railway.toml` created with configuration
- [ ] `runtime.txt` specifies Python 3.11
- [ ] `api_server.py` updated for production
- [ ] `sixfold_analysis_engine.py` updated for production
- [ ] `frontend/index.html` created from dashboard.html
- [ ] API URL in frontend updated (placeholder initially)

### Railway Setup

- [ ] Railway CLI installed and logged in
- [ ] Railway project created
- [ ] PostgreSQL database added
- [ ] Database migrated from local
- [ ] API service deployed
- [ ] API health endpoint returns success
- [ ] Frontend service deployed
- [ ] Frontend API URL updated with actual API URL
- [ ] All dashboard features working

### Post-Deployment

- [ ] Public URL shared for thesis presentation
- [ ] Monitoring in place
- [ ] Backup strategy documented

---

## 🏁 CONCLUSION FOR AI AGENTS

You are working on a **PhD research project** that now needs to be **deployed to the web** for the December presentation.

**Your current role:** Help prepare and deploy the application to Railway following the step-by-step guide above.

**Key principle:** Test locally → Deploy API → Verify → Deploy Frontend → Verify

**Current status:** All code complete, ready for deployment configuration.

**Next critical step:** Create deployment files and deploy to Railway.

**Success = Public URL working** for the thesis presentation with all visualizations loading correctly.

---

**Context File Version:** 2.0  
**Last Updated:** December 01, 2025  
**Status:** Ready for Railway Deployment  
**Optimized for:** Claude Code, Gemini, GPT-4, and other IDE-integrated AI assistants

---

**Let's get this deployed! 🚀**
