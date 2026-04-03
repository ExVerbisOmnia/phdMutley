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

import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, inspect, text

# Monkey-patch openpyxl to auto-strip illegal XML characters instead of raising.
# Necessary because OCR/garbled text in the DB contains control characters.
import openpyxl.cell.cell as _openpyxl_cell
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE as _ILLEGAL_RE
_orig_check_string = _openpyxl_cell.Cell.check_string.__func__ if hasattr(_openpyxl_cell.Cell.check_string, '__func__') else _openpyxl_cell.Cell.check_string

@staticmethod
def _safe_check_string(value):
    if isinstance(value, str):
        value = _ILLEGAL_RE.sub("", value)
        if len(value) > 32767:
            value = value[:32767]
    return value

_openpyxl_cell.Cell.check_string = _safe_check_string

# Add scripts dir to path for secrets module
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Setup logging
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_dir / "export_to_excel.log", encoding="utf-8"), logging.StreamHandler()],
)

logger = logging.getLogger(__name__)

# Database connection — centralized URL resolution
from gcp_secrets import get_database_url_auto

DATABASE_URL = get_database_url_auto()

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "exports"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _sanitize_string_for_excel(value, max_len=32767):
    """Remove characters that openpyxl/Excel rejects and enforce cell length limit."""
    if not isinstance(value, str):
        return value
    value = _ILLEGAL_RE.sub("", value)
    if len(value) > max_len:
        value = value[:max_len]
    return value


def _clean_df_for_excel(df):
    """
    Prepare a DataFrame for Excel export: flatten arrays, strip timezones,
    and remove characters illegal in XML/Excel worksheets.
    """
    for col in df.columns:
        non_null_values = df[col].dropna()
        if not non_null_values.empty and isinstance(non_null_values.iloc[0], (list, tuple)):
            try:
                df[col] = df[col].apply(
                    lambda x: ", ".join(map(str, x)) if isinstance(x, (list, tuple)) else x
                )
            except Exception:
                pass
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            try:
                df[col] = df[col].dt.tz_localize(None)
            except Exception:
                pass
    # Strip illegal characters and enforce Excel cell length limit on all string columns
    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].apply(_sanitize_string_for_excel)
    return df


def _export_data_quality_sheet(engine, writer):
    """
    Export a _data_quality sheet with download failures, extraction failures, and summary stats.
    """
    logger.info("\nGenerating _data_quality sheet...")

    with engine.connect() as conn:
        # Section A — Download Failures
        df_download = pd.read_sql_query(text("""
            SELECT d.document_id, c.case_name, c.case_url, d.document_url AS source_document_url, d.download_error
            FROM documents d
            JOIN cases c ON d.case_id = c.case_id
            WHERE d.pdf_downloaded = FALSE OR d.pdf_downloaded IS NULL
            ORDER BY c.case_name
        """), conn)

        # Section B — Extraction Failures
        df_extraction = pd.read_sql_query(text("""
            SELECT et.document_id, c.case_name, c.case_url, d.document_url AS source_document_url,
                   et.extraction_method, et.extraction_quality, et.extraction_notes
            FROM extracted_text et
            JOIN documents d ON et.document_id = d.document_id
            JOIN cases c ON d.case_id = c.case_id
            WHERE et.extraction_quality = 'failed'
            ORDER BY c.case_name
        """), conn)

        # Section C — Summary stats
        stats = {}
        stats["total_documents"] = conn.execute(text("SELECT COUNT(*) FROM documents")).scalar()
        stats["downloaded_ok"] = conn.execute(text("SELECT COUNT(*) FROM documents WHERE pdf_downloaded = TRUE")).scalar()
        stats["download_failures"] = conn.execute(text("SELECT COUNT(*) FROM documents WHERE pdf_downloaded = FALSE OR pdf_downloaded IS NULL")).scalar()
        stats["extraction_ok"] = conn.execute(text("SELECT COUNT(*) FROM extracted_text WHERE extraction_quality != 'failed'")).scalar()
        stats["extraction_failures"] = conn.execute(text("SELECT COUNT(*) FROM extracted_text WHERE extraction_quality = 'failed'")).scalar()

    # Build combined sheet: summary row at top, then two sections
    rows = []
    rows.append({"Section": "=== SUMMARY ==="})
    for k, v in stats.items():
        rows.append({"Section": k, "Value": v})
    rows.append({})
    rows.append({"Section": f"=== DOWNLOAD FAILURES ({len(df_download)} docs) ==="})
    df_summary_top = pd.DataFrame(rows)

    rows2 = []
    rows2.append({})
    rows2.append({"Section": f"=== EXTRACTION FAILURES ({len(df_extraction)} docs) ==="})
    df_mid = pd.DataFrame(rows2)

    # Write summary header
    start_row = 0
    df_summary_top.to_excel(writer, sheet_name="_data_quality", index=False, startrow=start_row)
    start_row += len(df_summary_top) + 1

    # Write download failures
    if not df_download.empty:
        _clean_df_for_excel(df_download).to_excel(
            writer, sheet_name="_data_quality", index=False, startrow=start_row
        )
        start_row += len(df_download) + 2
    else:
        start_row += 1

    # Write extraction failures header
    df_mid.to_excel(writer, sheet_name="_data_quality", index=False, startrow=start_row, header=False)
    start_row += len(df_mid) + 1

    # Write extraction failures
    if not df_extraction.empty:
        _clean_df_for_excel(df_extraction).to_excel(
            writer, sheet_name="_data_quality", index=False, startrow=start_row
        )

    logger.info(f"  ✓ _data_quality: {len(df_download)} download failures, {len(df_extraction)} extraction failures")


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
    engine = None
    try:
        logger.info("=" * 60)
        logger.info("DATABASE EXPORT TO EXCEL")
        logger.info("=" * 60)

        # Create database engine
        logger.info("Connecting to database: climate_litigation")
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
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = OUTPUT_DIR / f"climate_litigation_export_{timestamp}.xlsx"
        else:
            output_file = Path(output_file)

        logger.info(f"Output file: {output_file}")

        # Enriched queries for citation tables — join case_name and URLs for traceability
        ENRICHED_QUERIES = {
            "citation_extraction_phased": """
                SELECT
                    c.case_name AS source_case_name,
                    c.case_url AS source_case_url,
                    d.document_url AS source_document_url,
                    cep.*
                FROM citation_extraction_phased cep
                JOIN documents d ON cep.document_id = d.document_id
                JOIN cases c ON d.case_id = c.case_id
                ORDER BY c.case_name, cep.extraction_id
            """,
            "citation_extraction_phased_summary": """
                SELECT
                    c.case_name,
                    c.case_url,
                    d.document_url AS source_document_url,
                    ceps.*
                FROM citation_extraction_phased_summary ceps
                JOIN documents d ON ceps.document_id = d.document_id
                JOIN cases c ON d.case_id = c.case_id
                ORDER BY c.case_name, ceps.summary_id
            """,
        }

        # Tables with text columns that should be truncated (besides extracted_text which has special handling)
        TEXT_TRUNCATION = {
            "citation_extraction_discarded": ["raw_text"],
            "documents": ["document_summary", "download_error"],
        }

        # Create Excel writer
        with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
            # Export _data_quality sheet first (sorts first alphabetically due to _ prefix)
            try:
                _export_data_quality_sheet(engine, writer)
            except Exception as e:
                logger.error(f"  ✗ Error generating _data_quality sheet: {e}")

            for table_name in sorted(tables):
                logger.info(f"\nExporting table: {table_name}")

                try:
                    if table_name in ENRICHED_QUERIES:
                        # Enriched export with JOINed context columns
                        df = pd.read_sql_query(text(ENRICHED_QUERIES[table_name]), engine)
                        logger.info(f"  ℹ Enriched with case_name and document URLs")
                        # Apply truncation to enriched tables if needed
                        if table_name in TEXT_TRUNCATION and text_truncate_length:
                            for col in TEXT_TRUNCATION[table_name]:
                                if col in df.columns:
                                    df[col] = df[col].astype(str).str[:text_truncate_length]
                            logger.info(f"  ⚠️  Truncated {TEXT_TRUNCATION[table_name]} to {text_truncate_length} chars")
                    elif table_name in TEXT_TRUNCATION and text_truncate_length:
                        # Tables with specific text columns to truncate
                        df = pd.read_sql_table(table_name, engine)
                        for col in TEXT_TRUNCATION[table_name]:
                            if col in df.columns:
                                df[col] = df[col].astype(str).str[:text_truncate_length]
                        logger.info(f"  ⚠️  Truncated {TEXT_TRUNCATION[table_name]} to {text_truncate_length} chars")
                    elif table_name == "extracted_text" and text_truncate_length:
                        # Special handling for extracted_text table to truncate long text fields
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
                            LEFT(text_md, {text_truncate_length}) as text_md,
                            created_at,
                            updated_at
                        FROM {table_name}
                        """
                        df = pd.read_sql_query(query, engine)
                        logger.info(
                            f"  ⚠️  Truncated raw_text and processed_text to {text_truncate_length} characters"
                        )
                    else:
                        # Read entire table
                        df = pd.read_sql_table(table_name, engine)

                    # Get row count
                    row_count = len(df)
                    logger.info(f"  Rows: {row_count}")

                    if row_count == 0:
                        logger.info("  ⚠️  Table is empty")

                    # Clean sheet name (Excel has 31 char limit and doesn't allow certain chars)
                    sheet_name = table_name[:31].replace("/", "_").replace("\\", "_")

                    # Prepare DataFrame for Excel
                    _clean_df_for_excel(df)

                    # Write to Excel
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                    logger.info(f"  ✓ Exported to sheet: {sheet_name}")

                except Exception as e:
                    logger.error(f"  ✗ Error exporting table {table_name}: {e}")
                    continue

        logger.info("\n" + "=" * 60)
        logger.info("✓ Export completed successfully!")
        logger.info(f"Output file: {output_file}")
        logger.info(f"File size: {output_file.stat().st_size / 1024 / 1024:.2f} MB")
        logger.info("=" * 60)

        return output_file

    except Exception as e:
        logger.error(f"\n✗ Export failed: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return None
    finally:
        if engine is not None:
            engine.dispose()


def get_table_stats():
    """
    Get statistics about all tables in the database.

    Returns:
        Dictionary with table names and row counts
    """
    engine = None
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
    finally:
        if engine is not None:
            engine.dispose()


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

    print("\nDatabase: climate_litigation")
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

    parser = argparse.ArgumentParser(description="Export PostgreSQL database to Excel file")
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Output Excel file path (default: auto-generated with timestamp)",
    )
    parser.add_argument(
        "--full-text",
        action="store_true",
        help="Export full text without truncation (may create very large files)",
    )
    parser.add_argument(
        "--truncate-length",
        type=int,
        default=1000,
        help="Maximum length for text fields in extracted_text table (default: 1000)",
    )
    parser.add_argument(
        "--summary", action="store_true", help="Print database summary and exit (no export)"
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
        output_file=args.output, text_truncate_length=truncate_length
    )

    if output_file:
        print("\nSuccess! Excel file created at:")
        print(f"  {output_file}")
    else:
        print("\nExport failed. Check the log file for details.")
        sys.exit(1)
