#!/usr/bin/env python3
"""
Database Migration Script - Add character_count column to extracted_texts table
================================================================================
This script adds the character_count column that extract_texts.py expects.

📍 Run from: /home/gusrodgs/Gus/cienciaDeDados/phdMutley
Command: python scripts/migrate_add_character_count.py

INPUT: Existing PostgreSQL database connection
ALGORITHM: Execute ALTER TABLE to add character_count column
OUTPUT: Updated extracted_texts table schema
"""

import sys
import os
import logging
import psycopg2

# Add project root to path
sys.path.insert(0, '/home/gusrodgs/Gus/cienciaDeDados/phdMutley')
from config import DB_CONFIG, LOGS_DIR

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / 'migration_character_count.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def check_column_exists(cursor):
    """
    Check if character_count column already exists.

    OUTPUT: Boolean indicating if column exists
    """
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'extracted_texts'
            AND column_name = 'character_count'
        );
    """)
    return cursor.fetchone()[0]


def execute_migration(cursor):
    """
    Add character_count column to extracted_texts table.

    ALGORITHM:
        1. Add character_count INTEGER column
        2. Update existing rows to calculate character_count from raw_text
        3. Verify the column was added

    OUTPUT: Success or error message
    """
    try:
        # Add character_count column
        logger.info("Adding character_count column...")
        cursor.execute("""
            ALTER TABLE extracted_texts
            ADD COLUMN character_count INTEGER;
        """)
        logger.info("✓ Column added successfully")

        # Update existing rows with calculated values
        logger.info("Updating existing rows with calculated character counts...")
        cursor.execute("""
            UPDATE extracted_texts
            SET character_count = LENGTH(raw_text)
            WHERE raw_text IS NOT NULL;
        """)
        rows_updated = cursor.rowcount
        logger.info(f"✓ Updated {rows_updated} existing rows")

        # Verify the changes
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'extracted_texts'
            AND column_name = 'character_count';
        """)

        result = cursor.fetchone()
        if result:
            logger.info(f"\n✓ Verification: Column 'character_count' exists")
            logger.info(f"  - Type: {result[1]}")
            logger.info(f"  - Nullable: {result[2]}")

        return True

    except Exception as e:
        logger.error(f"Migration error: {e}")
        raise


def main():
    logger.info("="*70)
    logger.info("DATABASE MIGRATION - Add character_count to extracted_texts")
    logger.info("="*70)

    # Build connection parameters
    conn_params = {
        'host': DB_CONFIG['host'],
        'port': DB_CONFIG['port'],
        'database': DB_CONFIG['database'],
        'user': DB_CONFIG['username'],
        'password': DB_CONFIG['password']
    }

    conn = None

    try:
        # Connect to database
        logger.info("\nConnecting to database...")
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()
        logger.info("✓ Connected successfully")

        # Check if column already exists
        logger.info("\nChecking if character_count column already exists...")
        if check_column_exists(cursor):
            logger.warning("⚠️  Column 'character_count' already exists!")
            logger.warning("   No migration needed.")
            return True

        logger.info("Column does not exist. Proceeding with migration...")

        # Execute migration
        success = execute_migration(cursor)

        # Commit changes
        conn.commit()
        logger.info("\n✓ Migration committed successfully!")

        logger.info("\n" + "="*70)
        logger.info("✓ MIGRATION COMPLETED SUCCESSFULLY")
        logger.info("="*70)

        return True

    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"\n✗ Migration failed: {e}")
        logger.error(f"Error code: {e.pgcode}")
        if hasattr(e, 'pgerror'):
            logger.error(f"Error message: {e.pgerror}")

        logger.error("\n" + "="*70)
        logger.error("✗ MIGRATION FAILED")
        logger.error("="*70)
        return False

    finally:
        if conn:
            cursor.close()
            conn.close()
            logger.info("\nDatabase connection closed")


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
