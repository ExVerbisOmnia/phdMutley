#!/usr/bin/env python3
"""
Database Column Inspector
=========================
Inspects all tables and columns in the climate_litigation database
and shows which ones have data.

Run from: /home/gusrodgs/Gus/cienciaDeDados/phdMutley
Command: python inspect_database.py
"""

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import URL
from dotenv import load_dotenv
import os
import sys

# Add path to import database models
sys.path.insert(0, 'scripts/phase0')
from init_database_pg18 import Case, Document, ExtractedText, TextSection, KeywordTag, Base

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

# Connect to database
engine = create_engine(URL.create(**DB_CONFIG))
Session = sessionmaker(bind=engine)
session = Session()
inspector = inspect(engine)

print("="*80)
print("DATABASE COLUMN INSPECTION - CLIMATE LITIGATION DATABASE")
print("="*80)
print(f"Database: {DB_CONFIG['database']}")
print(f"Host: {DB_CONFIG['host']}")
print("="*80)

# Dictionary mapping table names to their SQLAlchemy models
table_models = {
    'cases': Case,
    'documents': Document,
    'extracted_text': ExtractedText,
    'text_sections': TextSection,
    'keywords_tags': KeywordTag
}

# Inspect each table
for table_name, model in table_models.items():
    print(f"\n{'='*80}")
    print(f"TABLE: {table_name.upper()}")
    print(f"{'='*80}")
    
    # Count total rows
    total_rows = session.query(model).count()
    print(f"Total rows: {total_rows}")
    
    if total_rows == 0:
        print("❌ Table is empty - no data to inspect")
        continue
    
    # Get all columns for this table
    columns = inspector.get_columns(table_name)
    
    print(f"\nColumn Analysis ({len(columns)} columns):")
    print(f"{'-'*80}")
    print(f"{'Column Name':<30} {'Type':<20} {'Populated':<12} {'Sample Data':<30}")
    print(f"{'-'*80}")
    
    # Get one sample row
    sample_row = session.query(model).first()
    
    for column in columns:
        col_name = column['name']
        col_type = str(column['type'])
        
        # Get the value from the sample row
        if hasattr(sample_row, col_name):
            value = getattr(sample_row, col_name)
            
            # Check if column has data (not null)
            is_populated = value is not None
            status = "✓ Yes" if is_populated else "✗ No (NULL)"
            
            # Format sample data for display
            if value is None:
                sample = "NULL"
            elif isinstance(value, str):
                # Truncate long strings
                sample = value[:27] + "..." if len(value) > 30 else value
                sample = sample.replace('\n', ' ')  # Remove newlines
            elif isinstance(value, (int, float, bool)):
                sample = str(value)
            else:
                sample = str(type(value).__name__)
            
            print(f"{col_name:<30} {col_type:<20} {status:<12} {sample:<30}")
        else:
            print(f"{col_name:<30} {col_type:<20} {'?':<12} {'N/A':<30}")
    
    # Show detailed sample for text columns
    if table_name == 'extracted_text':
        print(f"\n{'-'*80}")
        print("DETAILED TEXT SAMPLE:")
        print(f"{'-'*80}")
        
        if hasattr(sample_row, 'raw_text') and sample_row.raw_text:
            print(f"\nRaw Text (first 500 characters):")
            print(sample_row.raw_text[:500])
            print("...")
        
        if hasattr(sample_row, 'processed_text') and sample_row.processed_text:
            print(f"\nProcessed Text (first 500 characters):")
            print(sample_row.processed_text[:500])
            print("...")

# Generate summary statistics
print(f"\n{'='*80}")
print("SUMMARY STATISTICS")
print(f"{'='*80}")

# Cases summary
cases_count = session.query(Case).count()
print(f"\nCases Table:")
print(f"  Total cases: {cases_count}")
if cases_count > 0:
    # Count by country
    from sqlalchemy import func
    countries = session.query(Case.country, func.count(Case.case_id))\
        .group_by(Case.country)\
        .all()
    print(f"  Countries represented: {len(countries)}")
    for country, count in countries[:5]:  # Show top 5
        print(f"    - {country}: {count}")

# Documents summary
docs_count = session.query(Document).count()
print(f"\nDocuments Table:")
print(f"  Total documents: {docs_count}")
if docs_count > 0:
    downloaded = session.query(Document).filter(Document.pdf_downloaded == True).count()
    print(f"  Successfully downloaded: {downloaded}")
    
    # File size stats
    from sqlalchemy import func
    stats = session.query(
        func.sum(Document.file_size_bytes),
        func.avg(Document.file_size_bytes),
        func.min(Document.page_count),
        func.max(Document.page_count),
        func.avg(Document.page_count)
    ).first()
    
    if stats[0]:
        total_mb = stats[0] / 1048576
        avg_mb = stats[1] / 1048576 if stats[1] else 0
        print(f"  Total storage: {total_mb:.2f} MB")
        print(f"  Average file size: {avg_mb:.2f} MB")
        print(f"  Page count: {stats[2]} - {stats[3]} pages (avg: {stats[4]:.1f})")

# Extracted text summary
text_count = session.query(ExtractedText).count()
print(f"\nExtracted Text Table:")
print(f"  Total texts extracted: {text_count}")
if text_count > 0:
    # Quality distribution
    quality_dist = session.query(
        ExtractedText.extraction_quality,
        func.count(ExtractedText.text_id)
    ).group_by(ExtractedText.extraction_quality).all()
    
    print(f"  Quality distribution:")
    for quality, count in quality_dist:
        percentage = (count / text_count) * 100
        print(f"    - {quality}: {count} ({percentage:.1f}%)")
    
    # Method distribution
    method_dist = session.query(
        ExtractedText.extraction_method,
        func.count(ExtractedText.text_id)
    ).group_by(ExtractedText.extraction_method).all()
    
    print(f"  Extraction methods:")
    for method, count in method_dist:
        percentage = (count / text_count) * 100
        print(f"    - {method}: {count} ({percentage:.1f}%)")
    
    # Word count statistics
    word_stats = session.query(
        func.sum(ExtractedText.word_count),
        func.avg(ExtractedText.word_count),
        func.min(ExtractedText.word_count),
        func.max(ExtractedText.word_count)
    ).first()
    
    print(f"  Word statistics:")
    print(f"    - Total words: {word_stats[0]:,}")
    print(f"    - Average per document: {word_stats[1]:.0f}")
    print(f"    - Range: {word_stats[2]} - {word_stats[3]:,} words")

# Text sections summary
sections_count = session.query(TextSection).count()
print(f"\nText Sections Table:")
print(f"  Total sections: {sections_count}")
if sections_count == 0:
    print("  (Not yet populated - this table is for future use)")

# Keywords summary
keywords_count = session.query(KeywordTag).count()
print(f"\nKeywords/Tags Table:")
print(f"  Total keywords: {keywords_count}")
if keywords_count == 0:
    print("  (Not yet populated - this table is for future use)")

print(f"\n{'='*80}")
print("✓ Inspection complete!")
print(f"{'='*80}\n")

# Show example queries for common tasks
print("USEFUL QUERIES:")
print(f"{'-'*80}")
print("\n1. View all documents with their text info:")
print("   SELECT d.pdf_file_path, d.page_count, e.word_count, e.extraction_quality")
print("   FROM documents d JOIN extracted_text e ON d.document_id = e.document_id;")

print("\n2. Find documents with most words:")
print("   SELECT d.pdf_file_path, e.word_count")
print("   FROM documents d JOIN extracted_text e ON d.document_id = e.document_id")
print("   ORDER BY e.word_count DESC LIMIT 10;")

print("\n3. View full text of a specific document:")
print("   SELECT e.raw_text FROM extracted_text e")
print("   JOIN documents d ON e.document_id = d.document_id")
print("   WHERE d.pdf_file_path LIKE '%filename%';")

print(f"\n{'-'*80}\n")

session.close()
