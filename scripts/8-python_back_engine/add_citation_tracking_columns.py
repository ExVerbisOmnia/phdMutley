#!/usr/bin/env python3
"""
============================================================================
NON-DESTRUCTIVE SCHEMA MIGRATION - Citation Tracking Columns
============================================================================

Climate Litigation PhD Research Project
Author: Gustavo (with Claude assistance)
Date: December 7, 2025

Purpose:
--------
Adds new columns to the `cases` table for tracking citation relationships:
- unique_citations: Count of unique cases that cite this case
- citing_cases: Array of case_ids that cite this case
- unique_cited_count: Count of unique cases cited BY this case
- cited_cases: Array of case_ids cited by this case

This migration is NON-DESTRUCTIVE:
- Checks if columns exist before adding
- Does not drop or modify existing data
- Safe to run multiple times

Usage:
------
    python add_citation_tracking_columns.py

============================================================================
"""

import logging
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("SchemaMigration")

# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gcp_secrets import get_database_url_auto

DATABASE_URL = get_database_url_auto()


# =============================================================================
# MIGRATION DEFINITIONS
# =============================================================================

NEW_COLUMNS = [
    {
        "table": "cases",
        "column": "unique_citations",
        "type": "INTEGER",
        "default": "0",
        "comment": "Count of unique cases that cite this case (one per citing case)",
    },
    {
        "table": "cases",
        "column": "citing_cases",
        "type": "TEXT[]",
        "default": None,
        "comment": "Array of case_ids that cite this case",
    },
    {
        "table": "cases",
        "column": "unique_cited_count",
        "type": "INTEGER",
        "default": "0",
        "comment": "Count of unique cases cited BY this case (excluding duplicates)",
    },
    {
        "table": "cases",
        "column": "cited_cases",
        "type": "TEXT[]",
        "default": None,
        "comment": "Array of case_ids cited by this case",
    },
]


def column_exists(engine, table_name: str, column_name: str) -> bool:
    """
    Check if a column exists in a table.

    INPUT:
        - engine: SQLAlchemy engine
        - table_name: Name of the table
        - column_name: Name of the column

    OUTPUT:
        - bool: True if column exists, False otherwise
    """
    inspector = inspect(engine)
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def add_column(
    engine, table: str, column: str, col_type: str, default: str = None, comment: str = None
) -> bool:
    """
    Add a column to a table if it doesn't exist.

    INPUT:
        - engine: SQLAlchemy engine
        - table: Table name
        - column: Column name
        - col_type: PostgreSQL column type
        - default: Default value (optional)
        - comment: Column comment (optional)

    ALGORITHM:
        1. Check if column exists
        2. If not, add column with ALTER TABLE
        3. Add comment if provided

    OUTPUT:
        - bool: True if column was added, False if already existed
    """
    if column_exists(engine, table, column):
        logger.info(f"  ✓ Column '{column}' already exists in '{table}'")
        return False

    # Build ALTER TABLE statement
    default_clause = f" DEFAULT {default}" if default else ""
    sql = f"ALTER TABLE {table} ADD COLUMN {column} {col_type}{default_clause}"

    with engine.begin() as conn:
        conn.execute(text(sql))
        logger.info(f"  ✓ Added column '{column}' to '{table}'")

        # Add comment if provided
        if comment:
            comment_sql = f"COMMENT ON COLUMN {table}.{column} IS :comment"
            conn.execute(text(comment_sql), {"comment": comment})

    return True


def run_migration():
    """
    Run the migration to add citation tracking columns.

    ALGORITHM:
        1. Connect to database
        2. For each column definition, check if exists and add if not
        3. Report results

    OUTPUT:
        - bool: True if migration completed successfully
    """
    logger.info("=" * 70)
    logger.info("SCHEMA MIGRATION: Citation Tracking Columns")
    logger.info("=" * 70)

    try:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)

        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✓ Database connection successful")

        # Track results
        added = 0
        existed = 0

        logger.info("\nMigrating columns:")
        for col_def in NEW_COLUMNS:
            result = add_column(
                engine,
                table=col_def["table"],
                column=col_def["column"],
                col_type=col_def["type"],
                default=col_def["default"],
                comment=col_def["comment"],
            )
            if result:
                added += 1
            else:
                existed += 1

        # Summary
        logger.info("\n" + "-" * 50)
        logger.info("MIGRATION SUMMARY")
        logger.info("-" * 50)
        logger.info(f"  Columns added:          {added}")
        logger.info(f"  Columns already existed: {existed}")
        logger.info(f"  Total columns checked:   {len(NEW_COLUMNS)}")
        logger.info("-" * 50)
        logger.info("✓ Migration completed successfully!")
        logger.info("=" * 70)

        return True

    except Exception as e:
        logger.error(f"✗ Migration failed: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return False


# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
