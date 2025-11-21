#!/usr/bin/env python3
"""
Database to Excel Export Script
================================
Exports the entire climate_litigation database to Excel format.

📁 Run from: /home/gusrodgs/Gus/cienciaDeDados/phdMutley
Command: python scripts/phase2/export_database_to_excel.py

This script exports all tables to a single Excel file with multiple sheets:
- Cases (complete)
- Documents (complete)
- Extracted Text (with truncated text content)
- Citation Extractions (complete)
- Citations (complete)
- Citations with Source Info (joined view for analysis)

Author: Gustavo (gusrodgs)
Project: Doutorado PM
Version: 1.0
Date: November 2025
"""

import os
import sys
from datetime import datetime
import logging

# Data processing libraries
import pandas as pd
import numpy as np

# Database libraries
from sqlalchemy import create_engine, text as sql_text
from sqlalchemy.engine import URL
from dotenv import load_dotenv

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ============================================================================
# CONFIGURATION
# ============================================================================

# Output file configuration
OUTPUT_FILENAME = f'climate_litigation_database_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
OUTPUT_PATH = OUTPUT_FILENAME  # Saves in current directory

# Text truncation settings (to keep Excel file manageable)
MAX_TEXT_LENGTH = 1000  # Characters to include from extracted text
TRUNCATION_MESSAGE = "... [TRUNCATED - Full text available in database]"

# ============================================================================
# DATABASE SETUP
# ============================================================================

load_dotenv()

DB_CONFIG = {
    'drivername': 'postgresql+psycopg2',
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'climate_litigation'),
    'username': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
}

try:
    db_url = URL.create(**DB_CONFIG)
    engine = create_engine(db_url)
    logging.info("✓ Database connection established")
except Exception as e:
    logging.error(f"✗ Failed to connect to database: {e}")
    sys.exit(1)

# ============================================================================
# EXPORT FUNCTIONS
# ============================================================================

def truncate_text(text, max_length=MAX_TEXT_LENGTH):
    """
    Truncate long text fields for Excel export.
    
    INPUT: text (str), max_length (int)
    ALGORITHM: Return first max_length characters with truncation notice if needed
    OUTPUT: Truncated string
    """
    if text is None:
        return None
    if len(text) <= max_length:
        return text
    return text[:max_length] + TRUNCATION_MESSAGE


def export_cases(engine):
    """
    Export cases table.
    
    INPUT: SQLAlchemy engine
    ALGORITHM: Query all cases with clean column names
    OUTPUT: pandas DataFrame
    """
    logging.info("Exporting cases table...")
    
    query = """
    SELECT 
        case_id,
        case_name,
        case_number,
        court_name,
        country,
        region,
        filing_date,
        decision_date,
        case_status,
        case_type,
        case_url,
        data_source,
        created_at,
        updated_at
    FROM cases
    ORDER BY case_name;
    """
    
    df = pd.read_sql(query, engine)
    logging.info(f"  ✓ Exported {len(df)} cases")
    return df


def export_documents(engine):
    """
    Export documents table with case names for context.
    
    INPUT: SQLAlchemy engine
    ALGORITHM: Join documents with cases for readable export
    OUTPUT: pandas DataFrame
    """
    logging.info("Exporting documents table...")
    
    query = """
    SELECT 
        d.document_id,
        c.case_name,
        c.country,
        d.document_type,
        d.document_url,
        d.pdf_file_path,
        d.file_size_bytes,
        ROUND(d.file_size_bytes::numeric / 1048576.0, 2) as file_size_mb,
        d.page_count,
        d.pdf_downloaded,
        d.download_date,
        d.download_error,
        d.created_at,
        d.updated_at
    FROM documents d
    JOIN cases c ON d.case_id = c.case_id
    ORDER BY c.case_name;
    """
    
    df = pd.read_sql(query, engine)
    logging.info(f"  ✓ Exported {len(df)} documents")
    return df


def export_extracted_text(engine):
    """
    Export extracted_text table with TRUNCATED text content.
    
    INPUT: SQLAlchemy engine
    ALGORITHM: 
        1. Query extracted text with case/document context
        2. Truncate raw_text and processed_text to MAX_TEXT_LENGTH
        3. Add truncation notices
    OUTPUT: pandas DataFrame with truncated text
    """
    logging.info("Exporting extracted_text table (with truncated content)...")
    
    query = """
    SELECT 
        e.text_id,
        c.case_name,
        c.country,
        e.raw_text,
        e.processed_text,
        e.word_count,
        e.character_count,
        e.extraction_date,
        e.extraction_method,
        e.extraction_quality,
        e.extraction_notes,
        e.language_detected,
        e.language_confidence,
        e.created_at
    FROM extracted_text e
    JOIN documents d ON e.document_id = d.document_id
    JOIN cases c ON d.case_id = c.case_id
    ORDER BY c.case_name;
    """
    
    df = pd.read_sql(query, engine)
    
    # Truncate text columns
    if 'raw_text' in df.columns:
        df['raw_text'] = df['raw_text'].apply(truncate_text)
    if 'processed_text' in df.columns:
        df['processed_text'] = df['processed_text'].apply(truncate_text)
    
    logging.info(f"  ✓ Exported {len(df)} extracted texts (truncated)")
    return df


def export_citation_extractions(engine):
    """
    Export citation_extractions table with case context.
    
    INPUT: SQLAlchemy engine
    ALGORITHM: Join with cases for readable context
    OUTPUT: pandas DataFrame
    """
    logging.info("Exporting citation_extractions table...")
    
    query = """
    SELECT 
        ce.extraction_id,
        c.case_name,
        c.country as source_country,
        ce.extraction_date,
        ce.model_used,
        ce.total_citations_found,
        ce.foreign_citations_count,
        ce.domestic_citations_excluded,
        ce.api_tokens_input,
        ce.api_tokens_output,
        ce.api_cost_usd,
        ce.extraction_time_seconds,
        ce.extraction_success,
        ce.extraction_error
    FROM citation_extractions ce
    JOIN documents d ON ce.document_id = d.document_id
    JOIN cases c ON d.case_id = c.case_id
    ORDER BY ce.extraction_date DESC;
    """
    
    df = pd.read_sql(query, engine)
    logging.info(f"  ✓ Exported {len(df)} citation extractions")
    return df


def export_citations(engine):
    """
    Export citations table (basic).
    
    INPUT: SQLAlchemy engine
    ALGORITHM: Query all citations
    OUTPUT: pandas DataFrame
    """
    logging.info("Exporting citations table...")
    
    query = """
    SELECT 
        citation_id,
        extraction_id,
        cited_case_name,
        cited_court,
        cited_jurisdiction,
        cited_country,
        cited_year,
        citation_context,
        citation_type,
        citation_string_raw,
        confidence_score,
        position_in_document,
        created_at
    FROM citations
    ORDER BY confidence_score DESC;
    """
    
    df = pd.read_sql(query, engine)
    logging.info(f"  ✓ Exported {len(df)} citations")
    return df


def export_citations_with_source(engine):
    """
    Export citations with full source case information (for analysis).
    
    INPUT: SQLAlchemy engine
    ALGORITHM: Join citations with source cases for complete context
    OUTPUT: pandas DataFrame with rich context
    """
    logging.info("Exporting citations with source information...")
    
    query = """
    SELECT 
        -- Source case information
        c_source.case_name as source_case_name,
        c_source.court_name as source_court,
        c_source.country as source_country,
        c_source.region as source_region,
        c_source.decision_date as source_decision_date,
        
        -- Cited case information
        cit.cited_case_name,
        cit.cited_court,
        cit.cited_jurisdiction,
        cit.cited_country,
        cit.cited_year,
        
        -- Citation details
        cit.citation_type,
        cit.citation_context,
        cit.citation_string_raw,
        cit.confidence_score,
        
        -- Metadata
        ce.model_used,
        cit.created_at
    FROM citations cit
    JOIN citation_extractions ce ON cit.extraction_id = ce.extraction_id
    JOIN documents d ON ce.document_id = d.document_id
    JOIN cases c_source ON d.case_id = c_source.case_id
    ORDER BY c_source.case_name, cit.confidence_score DESC;
    """
    
    df = pd.read_sql(query, engine)
    logging.info(f"  ✓ Exported {len(df)} citations with source info")
    return df


def export_summary_statistics(engine):
    """
    Export summary statistics for quick overview.
    
    INPUT: SQLAlchemy engine
    ALGORITHM: Generate summary statistics from all tables
    OUTPUT: pandas DataFrame with key metrics
    """
    logging.info("Generating summary statistics...")
    
    query = """
    SELECT 
        'Total Cases' as metric,
        COUNT(*)::text as value
    FROM cases
    
    UNION ALL
    SELECT 'Total Documents', COUNT(*)::text FROM documents
    
    UNION ALL
    SELECT 'Documents with Text', COUNT(*)::text FROM extracted_text
    
    UNION ALL
    SELECT 'Citation Extractions', COUNT(*)::text FROM citation_extractions
    
    UNION ALL
    SELECT 'Successful Extractions', 
           COUNT(*)::text 
    FROM citation_extractions 
    WHERE extraction_success = true
    
    UNION ALL
    SELECT 'Total Foreign Citations', COUNT(*)::text FROM citations
    
    UNION ALL
    SELECT 'Unique Cited Countries', 
           COUNT(DISTINCT cited_country)::text 
    FROM citations
    
    UNION ALL
    SELECT 'Global North Cases', 
           COUNT(*)::text 
    FROM cases 
    WHERE region = 'Global North'
    
    UNION ALL
    SELECT 'Global South Cases', 
           COUNT(*)::text 
    FROM cases 
    WHERE region = 'Global South'
    
    UNION ALL
    SELECT 'Total API Cost (USD)', 
           '$' || ROUND(SUM(api_cost_usd)::numeric, 2)::text 
    FROM citation_extractions;
    """
    
    df = pd.read_sql(query, engine)
    logging.info(f"  ✓ Generated summary statistics")
    return df


# ============================================================================
# MAIN EXPORT FUNCTION
# ============================================================================

def main():
    """
    Main function to export all database tables to Excel.
    
    INPUT: None (reads from database)
    ALGORITHM:
        1. Export each table to a pandas DataFrame
        2. Create Excel writer with multiple sheets
        3. Write each DataFrame to a separate sheet
        4. Apply basic formatting
        5. Save file
    OUTPUT: Excel file with all database tables
    """
    
    print("\n" + "="*70)
    print("  DATABASE TO EXCEL EXPORT")
    print("  Climate Litigation Database")
    print("="*70 + "\n")
    
    print(f"Output file: {OUTPUT_PATH}")
    print(f"Text truncation: {MAX_TEXT_LENGTH} characters\n")
    
    try:
        # Export all tables
        logging.info("Starting export process...\n")
        
        df_summary = export_summary_statistics(engine)
        df_cases = export_cases(engine)
        df_documents = export_documents(engine)
        df_extracted_text = export_extracted_text(engine)
        df_citation_extractions = export_citation_extractions(engine)
        df_citations = export_citations(engine)
        df_citations_with_source = export_citations_with_source(engine)
        
        # Create Excel writer
        logging.info(f"\nWriting to Excel file: {OUTPUT_PATH}")
        
        with pd.ExcelWriter(OUTPUT_PATH, engine='openpyxl') as writer:
            # Write each DataFrame to a separate sheet
            df_summary.to_excel(writer, sheet_name='Summary', index=False)
            df_cases.to_excel(writer, sheet_name='Cases', index=False)
            df_documents.to_excel(writer, sheet_name='Documents', index=False)
            df_extracted_text.to_excel(writer, sheet_name='Extracted Text', index=False)
            df_citation_extractions.to_excel(writer, sheet_name='Citation Extractions', index=False)
            df_citations.to_excel(writer, sheet_name='Citations', index=False)
            df_citations_with_source.to_excel(writer, sheet_name='Citations with Source', index=False)
            
            # Auto-adjust column widths for readability
            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    
                    # Set column width (max 50 for readability)
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
        
        # Success message
        print("\n" + "="*70)
        print("  EXPORT COMPLETE")
        print("="*70)
        print(f"\n✓ Excel file created: {OUTPUT_PATH}\n")
        
        # Display summary
        print("Sheets included:")
        print(f"  1. Summary - Key database statistics")
        print(f"  2. Cases - {len(df_cases)} cases")
        print(f"  3. Documents - {len(df_documents)} documents")
        print(f"  4. Extracted Text - {len(df_extracted_text)} texts (truncated)")
        print(f"  5. Citation Extractions - {len(df_citation_extractions)} extractions")
        print(f"  6. Citations - {len(df_citations)} citations")
        print(f"  7. Citations with Source - {len(df_citations_with_source)} citations (with context)")
        
        print(f"\n📊 The file is ready to open in Excel or LibreOffice Calc.")
        print(f"📁 Location: {os.path.abspath(OUTPUT_PATH)}")
        print("\n" + "="*70 + "\n")
        
    except Exception as e:
        logging.error(f"\n✗ Export failed: {e}", exc_info=True)
        print(f"\n✗ Error: {e}")
        sys.exit(1)


# ============================================================================
# SCRIPT ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    """
    Execute when script is run directly.
    
    Usage:
        python scripts/phase2/export_database_to_excel.py
    """
    main()
