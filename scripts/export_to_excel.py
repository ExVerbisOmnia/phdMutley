#!/usr/bin/env python3
"""
Export PostgreSQL Database to Excel
====================================
Exports all tables from the climate_litigation database to an Excel file.
Each table becomes a separate tab in the Excel file.

Author: Gustavo (Gus)
Project: PhD Climate Litigation Research (Lucas "Mutley")
Date: November 2025
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
from sqlalchemy import create_engine, inspect, text
from dotenv import load_dotenv
import logging

# Load environment variables
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(env_path)

# Setup logging
log_dir = Path(__file__).parent.parent / 'logs'
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'export_to_excel.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Database connection parameters
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'climate_litigation')
DB_USER = os.getenv('DB_USER', 'phdmutley')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')

# Construct database URL
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent / 'data' / 'exports'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def export_database_to_excel(output_file: str = None, text_truncate_length: int = 1000):
    """
    Export all tables from the PostgreSQL database to an Excel file.
    
    Args:
        output_file: Path to output Excel file. If None, generates timestamped filename.
        text_truncate_length: Maximum length for text fields in extracted_text table.
                            Set to None to export full text (may create very large files).
    
    Returns:
        Path to created Excel file
    """
    try:
        logger.info("=" * 60)
        logger.info("DATABASE EXPORT TO EXCEL")
        logger.info("=" * 60)
        
        # Create database engine
        logger.info(f"Connecting to database: {DB_NAME}")
        engine = create_engine(DATABASE_URL, echo=False)
        
        # Get list of all tables
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if not tables:
            logger.error("No tables found in database!")
            return None
        
        logger.info(f"Found {len(tables)} tables: {', '.join(tables)}")
        
        # Generate output filename if not provided
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = OUTPUT_DIR / f'climate_litigation_export_{timestamp}.xlsx'
        else:
            output_file = Path(output_file)
        
        logger.info(f"Output file: {output_file}")
        
        # Create Excel writer
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            
            for table_name in sorted(tables):
                logger.info(f"\nExporting table: {table_name}")
                
                try:
                    # Special handling for extracted_text table to truncate long text fields
                    if table_name == 'extracted_text' and text_truncate_length:
                        query = f"""
                        SELECT 
                            text_id,
                            document_id,
                            extraction_method,
                            extraction_date,
                            extraction_quality,
                            extraction_notes,
                            LEFT(raw_text, {text_truncate_length}) as raw_text,
                            LEFT(processed_text, {text_truncate_length}) as processed_text,
                            word_count,
                            character_count,
                            paragraph_count,
                            sentence_count,
                            language_detected,
                            language_confidence,
                            created_at,
                            updated_at
                        FROM {table_name}
                        """
                        df = pd.read_sql_query(query, engine)
                        logger.info(f"  ⚠️  Truncated raw_text and processed_text to {text_truncate_length} characters")
                    else:
                        # Read entire table
                        df = pd.read_sql_table(table_name, engine)
                    
                    # Get row count
                    row_count = len(df)
                    logger.info(f"  Rows: {row_count}")
                    
                    if row_count == 0:
                        logger.info(f"  ⚠️  Table is empty")
                    
                    # Clean sheet name (Excel has 31 char limit and doesn't allow certain chars)
                    sheet_name = table_name[:31].replace('/', '_').replace('\\', '_')
                    
                    # Remove timezone information from datetime columns (Excel doesn't support it)
                    for col in df.columns:
                        if pd.api.types.is_datetime64_any_dtype(df[col]):
                            try:
                                df[col] = df[col].dt.tz_localize(None)
                            except Exception:
                                pass  # Already naive or other issue
                    
                    # Write to Excel
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                    logger.info(f"  ✓ Exported to sheet: {sheet_name}")
                    
                except Exception as e:
                    logger.error(f"  ✗ Error exporting table {table_name}: {e}")
                    continue
        
        logger.info("\n" + "=" * 60)
        logger.info(f"✓ Export completed successfully!")
        logger.info(f"Output file: {output_file}")
        logger.info(f"File size: {output_file.stat().st_size / 1024 / 1024:.2f} MB")
        logger.info("=" * 60)
        
        return output_file
        
    except Exception as e:
        logger.error(f"\n✗ Export failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def get_table_stats():
    """
    Get statistics about all tables in the database.
    
    Returns:
        Dictionary with table names and row counts
    """
    try:
        engine = create_engine(DATABASE_URL, echo=False)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        stats = {}
        
        with engine.connect() as conn:
            for table_name in tables:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                count = result.scalar()
                stats[table_name] = count
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting table stats: {e}")
        return {}


def print_database_summary():
    """
    Print a summary of the database contents.
    """
    print("\n" + "=" * 60)
    print("DATABASE SUMMARY")
    print("=" * 60)
    
    stats = get_table_stats()
    
    if not stats:
        print("Unable to retrieve database statistics")
        return
    
    print(f"\nDatabase: {DB_NAME}")
    print(f"Total tables: {len(stats)}\n")
    
    # Sort tables by row count (descending)
    sorted_stats = sorted(stats.items(), key=lambda x: x[1], reverse=True)
    
    print("Table Statistics:")
    print("-" * 60)
    print(f"{'Table Name':<40} {'Row Count':>15}")
    print("-" * 60)
    
    total_rows = 0
    for table_name, row_count in sorted_stats:
        print(f"{table_name:<40} {row_count:>15,}")
        total_rows += row_count
    
    print("-" * 60)
    print(f"{'TOTAL':<40} {total_rows:>15,}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Export PostgreSQL database to Excel file"
    )
    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Output Excel file path (default: auto-generated with timestamp)'
    )
    parser.add_argument(
        '--full-text',
        action='store_true',
        help='Export full text without truncation (may create very large files)'
    )
    parser.add_argument(
        '--truncate-length',
        type=int,
        default=1000,
        help='Maximum length for text fields in extracted_text table (default: 1000)'
    )
    parser.add_argument(
        '--summary',
        action='store_true',
        help='Print database summary and exit (no export)'
    )
    
    args = parser.parse_args()
    
    # Print summary if requested
    if args.summary:
        print_database_summary()
        sys.exit(0)
    
    # Determine truncation length
    truncate_length = None if args.full_text else args.truncate_length
    
    # Print database summary first
    print_database_summary()
    
    # Perform export
    output_file = export_database_to_excel(
        output_file=args.output,
        text_truncate_length=truncate_length
    )
    
    if output_file:
        print(f"\n✓ Success! Excel file created at:")
        print(f"  {output_file}")
    else:
        print("\n✗ Export failed. Check the log file for details.")
        sys.exit(1)
