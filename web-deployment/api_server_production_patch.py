#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================================
API SERVER - PRODUCTION PATCH FILE
============================================================================

This file contains the code blocks that need to be INSERTED or REPLACED
in api_server.py for production deployment on Railway.

INSTRUCTIONS FOR CLAUDE CODE:
1. Open api_server.py
2. Apply each change block below in order
3. Test locally before deploying

============================================================================
"""

# =============================================================================
# CHANGE 1: ADD AFTER LINE 66 (after imports from sixfold_analysis_engine)
# =============================================================================
# INSERT THIS BLOCK:

"""
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
    # Override the imported DATABASE_URL with production version
    DATABASE_URL = _production_db_url

# Determine environment for logging and CORS
IS_PRODUCTION = os.getenv('RAILWAY_ENVIRONMENT') is not None
"""

# =============================================================================
# CHANGE 2: REPLACE CORS CONFIGURATION (lines 74-78)
# =============================================================================
# REPLACE THIS:
"""
# Enable CORS for frontend access
# In production, restrict origins to your frontend domain
# Enable CORS for frontend access
# Allow all origins to support file:// access during development
CORS(app, resources={r"/api/*": {"origins": "*"}})
"""

# WITH THIS:
"""
# =============================================================================
# CORS CONFIGURATION
# =============================================================================
# In production, restrict to Railway frontend domain
# In development, allow all origins for flexibility

if IS_PRODUCTION:
    # Get frontend URL from environment variable, or allow all Railway domains
    frontend_url = os.getenv('FRONTEND_URL', '*')
    CORS(app, resources={r"/api/*": {"origins": frontend_url}})
    app.logger.info(f"CORS configured for production: {frontend_url}")
else:
    # Development: allow all origins (localhost, file://, etc.)
    CORS(app, resources={r"/api/*": {"origins": "*"}})
"""

# =============================================================================
# CHANGE 3: REPLACE get_engine() FUNCTION (lines 88-100)
# =============================================================================
# REPLACE THE ENTIRE get_engine() FUNCTION WITH:
"""
def get_engine() -> SixfoldAnalysisEngine:
    '''
    Get or create the analysis engine singleton.
    Uses production DATABASE_URL if available, otherwise falls back to local.
    
    Returns:
    --------
    SixfoldAnalysisEngine : Initialized engine instance
    '''
    global _engine
    if _engine is None:
        # DATABASE_URL is already processed above (postgres:// → postgresql://)
        _engine = SixfoldAnalysisEngine(database_url=DATABASE_URL)
        
        if IS_PRODUCTION:
            app.logger.info("✓ Connected to PRODUCTION database (Railway)")
        else:
            app.logger.info("✓ Connected to LOCAL database")
    return _engine
"""

# =============================================================================
# COMPLETE MODIFIED HEADER SECTION (lines 1-100)
# =============================================================================
# For convenience, here is the complete modified header that replaces lines 1-100:

COMPLETE_MODIFIED_HEADER = '''
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================================
SIXFOLD CITATION CLASSIFICATION - REST API SERVER
============================================================================

Climate Litigation PhD Research Project
Author: Gustavo (with Claude assistance)
Date: November 28, 2025
Updated: December 01, 2025 - Production deployment support

Purpose:
--------
This module provides a REST API for the sixfold analysis engine, enabling:
- Frontend (HTML/JS) to query analysis results
- Data visualization endpoints for charts and networks
- Export functionality for custom data exports
- Real-time analysis refresh capabilities

Tech Stack:
-----------
- Flask (lightweight web framework)
- Flask-CORS (cross-origin support for frontend)
- SQLAlchemy (via sixfold_analysis_engine)

Usage:
------
    # Development server:
    python api_server.py
    
    # Production (with gunicorn on Railway):
    gunicorn -w 4 -b 0.0.0.0:$PORT api_server:app

Endpoints:
----------
    GET  /api/health              - Health check
    GET  /api/analysis/run        - Run full analysis
    GET  /api/results/<query_id>  - Get specific query result
    GET  /api/sections/<section>  - Get all results for a section
    GET  /api/dashboard           - Get dashboard aggregates
    GET  /api/network             - Get network visualization data
    GET  /api/export/<format>     - Export data in various formats

============================================================================
"""

import os
import json
import io
import csv
import logging
from datetime import datetime
from functools import wraps
from typing import Dict, Any, Optional

# Flask imports
from flask import Flask, jsonify, request, send_file, Response
from flask_cors import CORS

# Import our analysis engine
from sixfold_analysis_engine import (
    SixfoldAnalysisEngine,
    OUTPUT_DIR,
    NETWORK_DIR,
    DASHBOARD_DIR,
    DATABASE_URL as _LOCAL_DATABASE_URL  # Renamed to avoid confusion
)

# =============================================================================
# PRODUCTION ENVIRONMENT CONFIGURATION
# =============================================================================

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
        DATABASE_URL = _production_db_url.replace('postgres://', 'postgresql://', 1)
    else:
        DATABASE_URL = _production_db_url
else:
    # Use local database URL from sixfold_analysis_engine
    DATABASE_URL = _LOCAL_DATABASE_URL

# Determine environment for logging and CORS
IS_PRODUCTION = os.getenv('RAILWAY_ENVIRONMENT') is not None

# =============================================================================
# FLASK APPLICATION SETUP
# =============================================================================

app = Flask(__name__)

# =============================================================================
# CORS CONFIGURATION
# =============================================================================
# In production, we can restrict to specific origins
# In development, allow all origins for flexibility

if IS_PRODUCTION:
    # Get frontend URL from environment variable, or allow all origins
    frontend_url = os.getenv('FRONTEND_URL', '*')
    CORS(app, resources={r"/api/*": {"origins": frontend_url}})
else:
    # Development: allow all origins (localhost, file://, etc.)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

# Configuration
app.config['JSON_SORT_KEYS'] = False  # Preserve order in JSON responses
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

# Global engine instance (lazy initialization)
_engine: Optional[SixfoldAnalysisEngine] = None


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
        # DATABASE_URL is already processed above (postgres:// → postgresql://)
        _engine = SixfoldAnalysisEngine(database_url=DATABASE_URL)
        
        if IS_PRODUCTION:
            app.logger.info("✓ Connected to PRODUCTION database (Railway)")
        else:
            app.logger.info("✓ Connected to LOCAL database")
    return _engine
'''

# =============================================================================
# END OF PATCH FILE
# =============================================================================
