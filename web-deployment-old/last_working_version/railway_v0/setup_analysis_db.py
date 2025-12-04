#!/usr/bin/env python3
"""
Database Setup Script for Sixfold Analysis Engine
Executes the required SQL scripts to prepare the database for the analysis engine.

Author: Gustavo (with Claude assistance)
Date: November 28, 2025
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
env_path = Path(__file__).resolve().parent.parent.parent / '.env'
load_dotenv(env_path)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('SetupAnalysisDB')

# Database configuration
DB_USER = os.getenv('DB_USER', 'phdmutley')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'climate_litigation')

DATABASE_URL = os.getenv(
    'DATABASE_URL',
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

def setup_database():
    """Execute the required SQL scripts."""
    try:
        logger.info("Connecting to database...")
        engine = create_engine(DATABASE_URL)
        
        # Define paths to SQL scripts
        scripts_dir = Path(__file__).resolve().parent.parent / '7-queries'
        sql_files = [
            scripts_dir / 'international_court_jurisdiction.sql',
            scripts_dir / 'sixfold_classification_complete.sql'
        ]
        
        with engine.begin() as conn:
            for sql_file in sql_files:
                if not sql_file.exists():
                    logger.error(f"SQL file not found: {sql_file}")
                    return False
                
                logger.info(f"Executing {sql_file.name}...")
                with open(sql_file, 'r', encoding='utf-8') as f:
                    sql_content = f.read()
                    # Split by command if necessary, but sqlalchemy execute can handle blocks
                    # However, psql specific commands like \echo need to be handled or removed
                    # For simplicity, we'll try executing the whole block, but we might need to strip psql commands
                    
                    # Simple stripping of \echo commands which are psql specific
                    cleaned_sql = '\n'.join([
                        line for line in sql_content.splitlines() 
                        if not line.strip().startswith('\\echo')
                    ])
                    
                    conn.execute(text(cleaned_sql))
                    logger.info(f"✓ {sql_file.name} executed successfully")
        
        logger.info("Database setup completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Database setup failed: {e}")
        return False

if __name__ == "__main__":
    success = setup_database()
    sys.exit(0 if success else 1)
