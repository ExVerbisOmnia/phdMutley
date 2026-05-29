#!/usr/bin/env python3
"""
Database Setup Script for Sixfold Analysis Engine
Executes the required SQL scripts to prepare the database for the analysis engine.

Author: Gustavo (with Claude assistance)
Date: November 28, 2025
"""

import logging
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("SetupAnalysisDB")

# Database configuration — centralized URL resolution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gcp_secrets import get_database_url_auto

DATABASE_URL = get_database_url_auto()


def setup_database():
    """Execute the required SQL scripts."""
    try:
        logger.info("Connecting to database...")
        engine = create_engine(DATABASE_URL)

        # Define paths to SQL scripts
        scripts_dir = Path(__file__).resolve().parent.parent / "7-queries"
        sql_files = [
            scripts_dir / "international_court_jurisdiction.sql",
            scripts_dir / "sixfold_classification_complete.sql",
        ]

        with engine.begin() as conn:
            for sql_file in sql_files:
                if not sql_file.exists():
                    logger.error(f"SQL file not found: {sql_file}")
                    return False

                logger.info(f"Executing {sql_file.name}...")
                with open(sql_file, encoding="utf-8") as f:
                    sql_content = f.read()
                    # Split by command if necessary, but sqlalchemy execute can handle blocks
                    # However, psql specific commands like \echo need to be handled or removed
                    # For simplicity, we'll try executing the whole block, but we might need to strip psql commands

                    # Simple stripping of \echo commands which are psql specific
                    cleaned_sql = "\n".join(
                        [
                            line
                            for line in sql_content.splitlines()
                            if not line.strip().startswith("\\echo")
                        ]
                    )

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
