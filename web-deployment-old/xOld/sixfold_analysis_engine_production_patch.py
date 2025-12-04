#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================================
SIXFOLD ANALYSIS ENGINE - PRODUCTION PATCH FILE
============================================================================

This file contains the code blocks that need to be INSERTED or REPLACED
in sixfold_analysis_engine.py for production deployment on Railway.

INSTRUCTIONS FOR CLAUDE CODE:
1. Open sixfold_analysis_engine.py
2. Apply each change block below in order
3. Test locally before deploying

============================================================================
"""

# =============================================================================
# CHANGE 1: REPLACE DATABASE CONFIGURATION (lines 76-86)
# =============================================================================
# FIND THIS BLOCK:
"""
DB_USER = os.getenv('DB_USER', 'phdmutley')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'climate_litigation')

DATABASE_URL = os.getenv(
    'DATABASE_URL',
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)
"""

# REPLACE WITH:
"""
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
    logger.info("Database: PRODUCTION (Railway)")
else:
    # Development: Build from individual components
    DB_USER = os.getenv('DB_USER', 'phdmutley')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_NAME = os.getenv('DB_NAME', 'climate_litigation')
    
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    logger.info("Database: LOCAL (development)")
"""

# =============================================================================
# CHANGE 2: REPLACE OUTPUT DIRECTORIES (lines 88-91)
# =============================================================================
# FIND THIS BLOCK:
"""
# Output directories for external data storage
OUTPUT_DIR = Path('./analysis_output')
NETWORK_DIR = OUTPUT_DIR / 'network_data'
DASHBOARD_DIR = OUTPUT_DIR / 'dashboard_data'
"""

# REPLACE WITH:
"""
# Output directories for external data storage
# In production (Railway), use /tmp which is writable
# In development, use local directory
if os.getenv('RAILWAY_ENVIRONMENT'):
    OUTPUT_DIR = Path('/tmp/analysis_output')
    logger.info("Output directory: /tmp/analysis_output (Railway)")
else:
    OUTPUT_DIR = Path('./analysis_output')
    logger.info(f"Output directory: {OUTPUT_DIR.absolute()}")

NETWORK_DIR = OUTPUT_DIR / 'network_data'
DASHBOARD_DIR = OUTPUT_DIR / 'dashboard_data'
"""

# =============================================================================
# COMPLETE MODIFIED CONFIGURATION SECTION (lines 71-98)
# =============================================================================
# For convenience, here is the complete modified configuration section:

COMPLETE_MODIFIED_CONFIG = '''
# =============================================================================
# CONFIGURATION
# =============================================================================

# --- Database Configuration ---
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

# --- Output Directories ---
# In production (Railway), use /tmp which is writable
# In development, use local directory
if os.getenv('RAILWAY_ENVIRONMENT'):
    OUTPUT_DIR = Path('/tmp/analysis_output')
else:
    OUTPUT_DIR = Path('./analysis_output')

NETWORK_DIR = OUTPUT_DIR / 'network_data'
DASHBOARD_DIR = OUTPUT_DIR / 'dashboard_data'

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('SixfoldAnalysisEngine')

# Log environment info
if os.getenv('RAILWAY_ENVIRONMENT'):
    logger.info("Environment: PRODUCTION (Railway)")
    logger.info(f"Output directory: {OUTPUT_DIR}")
else:
    logger.info("Environment: DEVELOPMENT (local)")
    logger.info(f"Output directory: {OUTPUT_DIR.absolute()}")
'''

# =============================================================================
# END OF PATCH FILE
# =============================================================================
