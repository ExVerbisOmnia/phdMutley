#!/usr/bin/env python3
"""
Database Export Script
======================
Exports all tables from the PostgreSQL database to a single Excel file.
Each table is saved as a separate worksheet.

📁 Run from: /home/gusrodgs/Gus/cienciaDeDados/phdMutley
Command: python scripts/utils/export_database_to_excel.py
"""

import sys
import os
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import URL
import logging

# ============================================================================
# CONFIGURATION & IMPORTS
# ============================================================================

# Add project root to path to import config
sys.path.insert(0, '/home/gusrodgs/Gus/cienciaDeDados/phdMutley')
from config import DB_CONFIG, PROJECT_ROOT

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def export_db_to_excel():
    logging.info("="*70)
    logging.info("DATABASE EXPORT TOOL")
    logging.info("="*70)

    # Create connection
    try:
        url = URL.create(**DB_CONFIG)
        engine = create_engine(url)
        logging.info("✓ Connected to database")
    except Exception as e:
        logging.error(f"Failed to connect: {e}")
        return

    # Get all table names
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    
    if not table_names:
        logging.warning("No tables found in database!")
        return

    logging.info(f"Found {len(table_names)} tables: {', '.join(table_names)}")

    # Generate output filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = PROJECT_ROOT / 'outputs' / 'exports'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / f"full_database_export_{timestamp}.xlsx"

    logging.info(f"Exporting to: {output_file}...")

    try:
        # Create Excel Writer
        # engine='openpyxl' is required for writing .xlsx files
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            for table in table_names:
                logging.info(f"  - Exporting table '{table}'...")
                
                # Read table into DataFrame
                df = pd.read_sql_table(table, engine)
                
                # Handle timezone-aware datetimes (Excel doesn't like them)
                for col in df.select_dtypes(include=['datetime64[ns, UTC]']).columns:
                    df[col] = df[col].dt.tz_localize(None)
                
                # Write to sheet
                # Excel sheet names max length is 31 chars
                sheet_name = table[:31]
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                
                logging.info(f"    ✓ Wrote {len(df)} rows to sheet '{sheet_name}'")

        logging.info("="*70)
        logging.info("✓ Export completed successfully!")
        logging.info(f"File saved at: {output_file}")
        logging.info("="*70)

    except Exception as e:
        logging.error(f"Export failed: {e}", exc_info=True)
    finally:
        engine.dispose()

if __name__ == "__main__":
    export_db_to_excel()
