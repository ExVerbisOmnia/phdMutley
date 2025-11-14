#!/usr/bin/env python3
"""
PostgreSQL to Excel Exporter
=============================
Exports all tables from the climate_litigation database to an Excel file.
Each table becomes a separate sheet (tab) in the Excel file.

Run from: /home/gusrodgs/Gus/cienciaDeDados/phdMutley
Command: python export_to_excel.py
"""

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import URL
from dotenv import load_dotenv
import pandas as pd
import os
import sys
from datetime import datetime
from pathlib import Path

# Add path to import database models
sys.path.insert(0, 'scripts/phase0')
from init_database_pg18 import Case, Document, ExtractedText, TextSection, KeywordTag

# ============================================================================
# CONFIGURATION
# ============================================================================

# Output file name (will be created in project root)
OUTPUT_FILE = 'database_export.xlsx'

# Text truncation settings
# Set to None to include full text, or set a character limit
MAX_TEXT_LENGTH = 500  # Truncate long text fields to this many characters

# Option to exclude very long text columns entirely
# Set to False to include raw_text and processed_text in the export
INCLUDE_FULL_TEXT = False  # Change to True if you want the full text in Excel

# Option to create a separate text export file
EXPORT_TEXTS_SEPARATELY = True  # Creates a separate CSV with full texts

# ============================================================================
# DATABASE CONNECTION
# ============================================================================

# Load database config
load_dotenv()
DB_CONFIG = {
    'drivername': 'postgresql+psycopg2',
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'climate_litigation'),
    'username': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
}

print("="*80)
print("POSTGRESQL TO EXCEL EXPORTER")
print("="*80)
print(f"Database: {DB_CONFIG['database']}")
print(f"Output file: {OUTPUT_FILE}")
print(f"Text truncation: {MAX_TEXT_LENGTH if MAX_TEXT_LENGTH else 'None (full text)'}")
print(f"Include full text in Excel: {INCLUDE_FULL_TEXT}")
print(f"Export texts separately: {EXPORT_TEXTS_SEPARATELY}")
print("="*80 + "\n")

# Connect to database
try:
    engine = create_engine(URL.create(**DB_CONFIG))
    print("✓ Connected to database")
except Exception as e:
    print(f"✗ Failed to connect to database: {e}")
    sys.exit(1)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def truncate_text(text, max_length):
    """Truncate text to specified length with ellipsis."""
    if text is None:
        return None
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."

def prepare_dataframe(df, table_name):
    """
    Prepare DataFrame for Excel export.
    - Convert UUIDs to strings
    - Handle datetime objects
    - Truncate long text fields
    """
    # Create a copy to avoid modifying original
    df = df.copy()
    
    # Convert UUID columns to strings
    for col in df.columns:
        if df[col].dtype == 'object':
            # Check if column contains UUIDs
            if df[col].notna().any():
                first_value = df[col].dropna().iloc[0] if len(df[col].dropna()) > 0 else None
                if first_value is not None and hasattr(first_value, 'hex'):
                    df[col] = df[col].astype(str)
    
    # Handle text truncation for extracted_text table
    if table_name == 'extracted_text':
        if not INCLUDE_FULL_TEXT:
            # Remove or truncate text columns
            if 'raw_text' in df.columns:
                if MAX_TEXT_LENGTH:
                    df['raw_text_preview'] = df['raw_text'].apply(
                        lambda x: truncate_text(x, MAX_TEXT_LENGTH)
                    )
                df = df.drop('raw_text', axis=1)
            
            if 'processed_text' in df.columns:
                if MAX_TEXT_LENGTH:
                    df['processed_text_preview'] = df['processed_text'].apply(
                        lambda x: truncate_text(x, MAX_TEXT_LENGTH)
                    )
                df = df.drop('processed_text', axis=1)
        else:
            # Include full text but truncate if specified
            if MAX_TEXT_LENGTH:
                if 'raw_text' in df.columns:
                    df['raw_text'] = df['raw_text'].apply(
                        lambda x: truncate_text(x, MAX_TEXT_LENGTH)
                    )
                if 'processed_text' in df.columns:
                    df['processed_text'] = df['processed_text'].apply(
                        lambda x: truncate_text(x, MAX_TEXT_LENGTH)
                    )
    
    # Handle other text columns in different tables
    elif table_name in ['cases', 'documents', 'text_sections']:
        for col in df.columns:
            if df[col].dtype == 'object' and MAX_TEXT_LENGTH:
                # Check if column contains long text
                if df[col].notna().any():
                    avg_length = df[col].dropna().str.len().mean()
                    if avg_length > MAX_TEXT_LENGTH:
                        df[col] = df[col].apply(lambda x: truncate_text(x, MAX_TEXT_LENGTH))
    
    return df

def export_table_to_df(table_name, engine):
    """Export a table to a pandas DataFrame."""
    try:
        # Use pandas read_sql to get data directly
        query = f"SELECT * FROM {table_name}"
        df = pd.read_sql(query, engine)
        
        print(f"  ✓ {table_name}: {len(df)} rows, {len(df.columns)} columns")
        return df
    except Exception as e:
        print(f"  ✗ Error reading {table_name}: {e}")
        return None

# ============================================================================
# MAIN EXPORT LOGIC
# ============================================================================

# Dictionary to store all dataframes
dataframes = {}

# List of tables to export
tables = ['cases', 'documents', 'extracted_text', 'text_sections', 'keywords_tags']

print("\nExporting tables:")
print("-"*80)

for table_name in tables:
    df = export_table_to_df(table_name, engine)
    if df is not None and len(df) > 0:
        # Prepare DataFrame for Excel
        df = prepare_dataframe(df, table_name)
        dataframes[table_name] = df
    elif df is not None and len(df) == 0:
        print(f"  ⚠ {table_name} is empty")
        # Still add empty dataframe to Excel
        dataframes[table_name] = df
    else:
        print(f"  ⚠ Skipping {table_name}")

print("-"*80)

# ============================================================================
# EXPORT TO EXCEL
# ============================================================================

if not dataframes:
    print("\n✗ No data to export!")
    sys.exit(1)

print(f"\nWriting to Excel file: {OUTPUT_FILE}")

try:
    # Create Excel writer object
    with pd.ExcelWriter(OUTPUT_FILE, engine='openpyxl') as writer:
        
        # Write each table to a separate sheet
        for table_name, df in dataframes.items():
            # Truncate sheet name if needed (Excel has 31 char limit)
            sheet_name = table_name[:31]
            
            print(f"  ✓ Writing sheet: {sheet_name}")
            
            # Write DataFrame to sheet
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            # Get the worksheet to apply formatting
            worksheet = writer.sheets[sheet_name]
            
            # Auto-adjust column widths (up to a maximum)
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                
                # Set width (with minimum and maximum)
                adjusted_width = min(max(max_length + 2, 10), 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
    
    print(f"\n✓ Excel file created successfully: {OUTPUT_FILE}")
    
    # Show file size
    file_size = os.path.getsize(OUTPUT_FILE) / 1024  # KB
    if file_size > 1024:
        print(f"  File size: {file_size/1024:.2f} MB")
    else:
        print(f"  File size: {file_size:.2f} KB")

except Exception as e:
    print(f"\n✗ Error writing Excel file: {e}")
    sys.exit(1)

# ============================================================================
# EXPORT FULL TEXTS SEPARATELY (OPTIONAL)
# ============================================================================

if EXPORT_TEXTS_SEPARATELY and 'extracted_text' in dataframes:
    print("\n" + "-"*80)
    print("Exporting full texts to separate CSV file...")
    print("-"*80)
    
    try:
        # Get full text data (without truncation)
        query = """
        SELECT 
            e.text_id,
            d.pdf_file_path,
            c.case_name,
            e.word_count,
            e.extraction_quality,
            e.raw_text
        FROM extracted_text e
        JOIN documents d ON e.document_id = d.document_id
        JOIN cases c ON d.case_id = c.case_id
        """
        
        texts_df = pd.read_sql(query, engine)
        
        # Convert UUIDs to strings
        texts_df['text_id'] = texts_df['text_id'].astype(str)
        
        # Export to CSV
        texts_file = 'extracted_texts_full.csv'
        texts_df.to_csv(texts_file, index=False, encoding='utf-8')
        
        print(f"✓ Full texts exported to: {texts_file}")
        
        file_size = os.path.getsize(texts_file) / 1024  # KB
        if file_size > 1024:
            print(f"  File size: {file_size/1024:.2f} MB")
        else:
            print(f"  File size: {file_size:.2f} KB")
        
    except Exception as e:
        print(f"✗ Error exporting texts: {e}")

# ============================================================================
# CREATE SUMMARY SHEET
# ============================================================================

print("\n" + "-"*80)
print("Creating summary statistics...")
print("-"*80)

try:
    # Create summary DataFrame
    summary_data = {
        'Table': [],
        'Rows': [],
        'Columns': [],
        'Description': []
    }
    
    descriptions = {
        'cases': 'Climate litigation cases metadata',
        'documents': 'PDF documents associated with cases',
        'extracted_text': 'Text extracted from PDF documents',
        'text_sections': 'Segmented sections of documents (future use)',
        'keywords_tags': 'Keywords and tags for cases (future use)'
    }
    
    for table_name, df in dataframes.items():
        summary_data['Table'].append(table_name)
        summary_data['Rows'].append(len(df))
        summary_data['Columns'].append(len(df.columns))
        summary_data['Description'].append(descriptions.get(table_name, ''))
    
    summary_df = pd.DataFrame(summary_data)
    
    # Add summary to Excel file
    with pd.ExcelWriter(OUTPUT_FILE, engine='openpyxl', mode='a') as writer:
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        # Format the summary sheet
        worksheet = writer.sheets['Summary']
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max(max_length + 2, 15), 60)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    print("✓ Summary sheet added")
    
except Exception as e:
    print(f"⚠ Could not create summary sheet: {e}")

# ============================================================================
# FINAL SUMMARY
# ============================================================================

print("\n" + "="*80)
print("EXPORT COMPLETE!")
print("="*80)
print(f"\nFiles created:")
print(f"  📊 {OUTPUT_FILE} - Excel file with all tables")
if EXPORT_TEXTS_SEPARATELY and 'extracted_text' in dataframes:
    print(f"  📄 extracted_texts_full.csv - Full text content")

print(f"\nExcel sheets:")
for table_name in dataframes.keys():
    row_count = len(dataframes[table_name])
    print(f"  • {table_name}: {row_count} rows")

print("\n💡 Tips:")
print("  - Open the Excel file in Excel, LibreOffice, or Google Sheets")
print("  - Each table is in a separate tab/sheet")
print("  - Use the 'Summary' sheet for an overview")
if not INCLUDE_FULL_TEXT:
    print("  - Full text was truncated/excluded from Excel")
    print(f"  - Check 'extracted_texts_full.csv' for complete text content")

print("\n" + "="*80 + "\n")
