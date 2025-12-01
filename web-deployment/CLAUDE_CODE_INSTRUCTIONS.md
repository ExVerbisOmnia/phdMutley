# Claude Code Deployment Instructions
## PhD Climate Litigation Project → Railway Deployment

**Last Updated:** December 01, 2025  
**Target Platform:** Railway  
**Estimated Time:** 1-2 hours

---

## 🎯 OBJECTIVE

Deploy the Sixfold Citation Analysis application to Railway, making it publicly accessible for the PhD thesis presentation in December.

---

## 📋 PRE-DEPLOYMENT CHECKLIST

Before starting, verify these prerequisites:

```bash
# 1. Check PostgreSQL is running locally
sudo systemctl status postgresql

# 2. Verify local database has data
psql -U phdmutley -d climate_litigation -c "SELECT COUNT(*) FROM cases;"
# Expected: 2924

# 3. Test local API
cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley/scripts/8-python_back_engine
python api_server.py &
curl http://127.0.0.1:5000/api/health
# Expected: {"status": "success", ...}

# 4. Check Node.js is installed (for Railway CLI)
node --version
# Expected: v18+ or similar

# 5. Verify npm is available
npm --version
```

---

## 📁 FILE STRUCTURE TO CREATE

```
/home/gusrodgs/Gus/cienciaDeDados/phdMutley/scripts/8-python_back_engine/
├── api_server.py              # ← MODIFY (add production config)
├── sixfold_analysis_engine.py # ← MODIFY (add production config)
├── config.py                  # No changes needed
├── requirements.txt           # ← CREATE
├── Procfile                   # ← CREATE
├── railway.toml               # ← CREATE
├── runtime.txt                # ← CREATE
├── migrate_to_railway.sh      # ← CREATE
├── db_backup/                 # ← CREATE (directory)
└── frontend/                  # ← CREATE (directory)
    └── index.html             # ← CREATE (copy from dashboard.html, modify)
```

---

## 🔧 STEP-BY-STEP INSTRUCTIONS

### STEP 1: Create Deployment Files

Navigate to the backend directory:

```bash
cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley/scripts/8-python_back_engine
```

#### 1.1 Create `requirements.txt`

```bash
cat > requirements.txt << 'EOF'
# Railway Deployment Dependencies
# PhD Climate Litigation Project
flask>=3.0.0
flask-cors>=4.0.0
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.9
gunicorn>=21.0.0
pandas>=2.0.0
python-dotenv>=1.0.0
EOF
```

#### 1.2 Create `Procfile`

```bash
cat > Procfile << 'EOF'
web: gunicorn --bind 0.0.0.0:$PORT --workers 4 --timeout 120 api_server:app
EOF
```

#### 1.3 Create `railway.toml`

```bash
cat > railway.toml << 'EOF'
[build]
builder = "nixpacks"

[deploy]
startCommand = "gunicorn --bind 0.0.0.0:$PORT --workers 4 --timeout 120 api_server:app"
healthcheckPath = "/api/health"
healthcheckTimeout = 30
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 3
EOF
```

#### 1.4 Create `runtime.txt`

```bash
echo "python-3.11.7" > runtime.txt
```

---

### STEP 2: Modify Python Files for Production

#### 2.1 Modify `api_server.py`

Open the file and make these changes:

**CHANGE A: Add after line 66 (after the imports from sixfold_analysis_engine)**

Insert this block:

```python
# =============================================================================
# PRODUCTION ENVIRONMENT CONFIGURATION
# =============================================================================

import logging

# Configure logging for production
if os.getenv('RAILWAY_ENVIRONMENT'):
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

# Handle Railway's DATABASE_URL format
# Railway provides postgres:// but SQLAlchemy 2.0+ requires postgresql://
_production_db_url = os.getenv('DATABASE_URL')
if _production_db_url:
    if _production_db_url.startswith('postgres://'):
        _production_db_url = _production_db_url.replace('postgres://', 'postgresql://', 1)
    DATABASE_URL = _production_db_url
# else: use the DATABASE_URL imported from sixfold_analysis_engine

# Determine environment
IS_PRODUCTION = os.getenv('RAILWAY_ENVIRONMENT') is not None
```

**CHANGE B: Replace CORS configuration (around lines 74-78)**

Replace:
```python
CORS(app, resources={r"/api/*": {"origins": "*"}})
```

With:
```python
# CORS Configuration - production vs development
if IS_PRODUCTION:
    frontend_url = os.getenv('FRONTEND_URL', '*')
    CORS(app, resources={r"/api/*": {"origins": frontend_url}})
else:
    CORS(app, resources={r"/api/*": {"origins": "*"}})
```

**CHANGE C: Update get_engine() function (around line 88)**

Replace the function with:
```python
def get_engine() -> SixfoldAnalysisEngine:
    """Get or create the analysis engine singleton."""
    global _engine
    if _engine is None:
        _engine = SixfoldAnalysisEngine(database_url=DATABASE_URL)
        if IS_PRODUCTION:
            app.logger.info("✓ Connected to PRODUCTION database (Railway)")
        else:
            app.logger.info("✓ Connected to LOCAL database")
    return _engine
```

#### 2.2 Modify `sixfold_analysis_engine.py`

**CHANGE A: Replace DATABASE_URL configuration (around lines 76-86)**

Replace the entire database configuration section with:

```python
# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================

_railway_url = os.getenv('DATABASE_URL')

if _railway_url:
    # Production: Railway's URL (convert postgres:// to postgresql://)
    if _railway_url.startswith('postgres://'):
        DATABASE_URL = _railway_url.replace('postgres://', 'postgresql://', 1)
    else:
        DATABASE_URL = _railway_url
else:
    # Development: Build from environment variables
    DB_USER = os.getenv('DB_USER', 'phdmutley')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_NAME = os.getenv('DB_NAME', 'climate_litigation')
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
```

**CHANGE B: Replace OUTPUT_DIR configuration (around lines 89-91)**

Replace:
```python
OUTPUT_DIR = Path('./analysis_output')
```

With:
```python
# Use /tmp on Railway (writable), local dir for development
if os.getenv('RAILWAY_ENVIRONMENT'):
    OUTPUT_DIR = Path('/tmp/analysis_output')
else:
    OUTPUT_DIR = Path('./analysis_output')
```

---

### STEP 3: Create Frontend Directory

```bash
# Create frontend directory
mkdir -p frontend

# Copy dashboard to frontend and rename
cp dashboard.html frontend/index.html
```

#### 3.1 Modify `frontend/index.html`

Open `frontend/index.html` and find the JavaScript configuration section (around line 763).

**Replace this:**
```javascript
const API_BASE = 'http://127.0.0.1:5000/api';
```

**With this:**
```javascript
// Auto-detect environment for API URL
const API_BASE = (() => {
    const hostname = window.location.hostname;
    
    // Production: Railway
    // TODO: Update this URL after deployment!
    const RAILWAY_API_URL = 'https://YOUR-API-SERVICE.up.railway.app/api';
    
    if (hostname.includes('railway.app')) {
        console.log('🚀 Production mode');
        return RAILWAY_API_URL;
    }
    
    // Development: localhost
    console.log('🔧 Development mode');
    return 'http://127.0.0.1:5000/api';
})();

console.log('📡 API Base URL:', API_BASE);
```

---

### STEP 4: Install Railway CLI

```bash
# Install Railway CLI globally
npm install -g @railway/cli

# Verify installation
railway --version

# Login to Railway (opens browser)
railway login
```

---

### STEP 5: Create Railway Project

```bash
cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley/scripts/8-python_back_engine

# Initialize new Railway project
railway init

# When prompted:
# - Select "Create new project"
# - Name: climate-litigation-api
```

---

### STEP 6: Add PostgreSQL Database

```bash
# Add PostgreSQL to the project
railway add

# Select: PostgreSQL

# View connection details
railway variables
```

Save the DATABASE_URL shown - you'll need it for migration.

---

### STEP 7: Migrate Local Database to Railway

```bash
# Create backup directory
mkdir -p db_backup

# Export local database
pg_dump \
    -h localhost \
    -U phdmutley \
    -d climate_litigation \
    --no-owner \
    --no-acl \
    --clean \
    --if-exists \
    -f db_backup/climate_litigation_backup.sql

# Get Railway's DATABASE_URL
railway variables | grep DATABASE_URL

# Import to Railway (replace with your actual URL)
psql "postgres://postgres:XXXXX@containers-us-west-XXX.railway.app:5432/railway" < db_backup/climate_litigation_backup.sql
```

---

### STEP 8: Verify Database Migration

```bash
# Connect to Railway PostgreSQL
railway connect postgres

# Once connected, run:
\dt
SELECT COUNT(*) FROM cases;
SELECT COUNT(*) FROM citation_sixfold_classification;
\q
```

---

### STEP 9: Deploy API to Railway

```bash
cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley/scripts/8-python_back_engine

# Deploy
railway up

# Wait for deployment to complete (1-3 minutes)

# Get the public URL
railway open
```

Note the URL (e.g., `https://climate-litigation-api-production.up.railway.app`)

---

### STEP 10: Test Deployed API

```bash
# Replace with your actual Railway URL
API_URL="https://climate-litigation-api-production.up.railway.app"

# Test health endpoint
curl "$API_URL/api/health"

# Test dashboard endpoint
curl "$API_URL/api/dashboard/summary_stats"
```

---

### STEP 11: Update Frontend API URL

Edit `frontend/index.html` and replace:
```javascript
const RAILWAY_API_URL = 'https://YOUR-API-SERVICE.up.railway.app/api';
```

With your actual API URL:
```javascript
const RAILWAY_API_URL = 'https://climate-litigation-api-production.up.railway.app/api';
```

---

### STEP 12: Deploy Frontend

```bash
cd frontend

# Initialize as separate Railway service
railway init

# Select: "Add to existing project"
# Name: climate-litigation-frontend

# Create minimal package.json for static hosting
cat > package.json << 'EOF'
{
  "name": "climate-litigation-frontend",
  "scripts": {
    "start": "npx serve ."
  }
}
EOF

# Deploy
railway up
```

---

### STEP 13: Final Verification

1. Open the frontend URL in browser
2. Check browser console (F12) for:
   - "🚀 Production mode" message
   - API Base URL logged correctly
   - No CORS errors
3. Verify all dashboard sections load:
   - Summary statistics
   - Charts render
   - Network visualization
   - Tables populate
   - Export buttons work

---

## 🔍 TROUBLESHOOTING

### "postgres://" vs "postgresql://" Error
- Already handled in code changes
- Verify the replacement code is in place

### CORS Errors
- Check `FRONTEND_URL` environment variable in Railway dashboard
- Temporarily set to `*` for debugging

### Database Connection Timeout
- Verify PostgreSQL service is running in Railway dashboard
- Check `DATABASE_URL` is correctly set
- Try redeploying the API service

### Gunicorn Worker Timeout
- Increase timeout in Procfile: `--timeout 300`

### Static Files Not Loading
- Ensure all CDN links use HTTPS
- Check browser console for 404 errors

---

## 📊 POST-DEPLOYMENT

### View Logs
```bash
railway logs
```

### Monitor Costs
- Railway dashboard → Usage
- Free tier: $5/month credit

### Update Code
```bash
# Make changes locally
# Then redeploy:
railway up
```

---

## ✅ DEPLOYMENT COMPLETE

When finished, you should have:

1. **API Service**: `https://climate-litigation-api-XXX.up.railway.app`
   - Health check: `/api/health`
   - Dashboard data: `/api/dashboard`
   - Network data: `/api/network`

2. **Frontend Service**: `https://climate-litigation-frontend-XXX.up.railway.app`
   - Full dashboard visualization
   - Interactive charts
   - Export functionality

3. **PostgreSQL Database**: Managed by Railway
   - All 2,924 cases migrated
   - Citation classifications intact
   - Analysis tables populated

---

**Share the frontend URL for your thesis presentation! 🎓**
