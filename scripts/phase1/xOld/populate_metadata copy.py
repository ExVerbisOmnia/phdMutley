#!/usr/bin/env python3
"""
Database Metadata Population Script for Climate Litigation Database
====================================================================
Imports case and document metadata from Excel into PostgreSQL database.

📁 Run from: /home/gusrodgs/Gus/cienciaDeDados/phdMutley
Command: python scripts/phase1/populate_metadata.py

This script reads the filtered Excel database (baseDecisions.xlsx) containing
2,924 climate litigation decisions and populates the PostgreSQL database with
complete metadata for both cases and documents.

Key Features:
-------------
- Deterministic UUID generation (ensures consistency across runs)
- Intelligent parsing of complex fields (jurisdictions, geographies, dates)
- Rich metadata storage in JSON format
- Comprehensive error handling and logging
- Test mode for safe validation
- Upsert logic (update existing records or insert new ones)

Author: Lucas Biasetton (Gus)
Project: Doutorado PM - Global South Climate Litigation Analysis
Version: 1.0
Date: November 2025
"""

import os
import sys
from pathlib import Path
import logging
from datetime import datetime
import json
import re
from uuid import uuid5, NAMESPACE_DNS

# Data processing libraries
import pandas as pd
import numpy as np

# Database libraries
from sqlalchemy import create_engine, text as sql_text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import URL
from dotenv import load_dotenv

# Progress bar for visual feedback
from tqdm import tqdm

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

# Configure logging to track population progress and errors
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/metadata_population.log'),  # Save logs to file
        logging.StreamHandler()  # Also display in terminal
    ]
)

# Suppress verbose logging from external libraries
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

# ============================================================================
# CONFIGURATION SECTION
# ============================================================================

# Path to the filtered Excel database (decisions only)
# This file should contain only the 2,924 Decision-type documents
DATABASE_FILE = 'baseDecisions.xlsx'

# Test mode configuration
# Set to True to process only the first N rows for validation
TEST_MODE = True  # Set to False to process all rows
TEST_N_ROWS = 15  # Number of rows to process in test mode

# UUID generation namespace (ensures deterministic UUIDs)
# Using a project-specific namespace for consistent UUID generation
UUID_NAMESPACE = uuid5(NAMESPACE_DNS, 'climatecasechart.com.phdmutley')

# ============================================================================
# DATABASE SETUP
# ============================================================================

# Load environment variables from .env file
load_dotenv()

# Database connection configuration
DB_CONFIG = {
    'drivername': 'postgresql+psycopg2',
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'climate_litigation'),
    'username': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
}

# Create database engine
try:
    db_url = URL.create(**DB_CONFIG)
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    logging.info("✓ Database connection established")
except Exception as e:
    logging.error(f"✗ Failed to connect to database: {e}")
    sys.exit(1)

# Import database models
try:
    # Check if we're in the correct directory
    if not os.path.exists(DATABASE_FILE):
        raise FileNotFoundError(
            f"{DATABASE_FILE} not found. You must run this script from the project root:\n"
            "   cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley\n"
            "   python scripts/phase1/populate_metadata.py"
        )
    
    # Add the scripts/phase0 directory to Python path
    sys.path.insert(0, os.path.join(os.getcwd(), 'scripts', 'phase0'))
    
    # Import database models
    from init_database_pg18 import Case, Document, Base
    logging.info("✓ Database models imported successfully")
except FileNotFoundError as e:
    logging.error(f"✗ Wrong directory: {e}")
    sys.exit(1)
except ImportError as e:
    logging.error(f"✗ Failed to import database models: {e}")
    sys.exit(1)

# ============================================================================
# HELPER FUNCTIONS - FIELD PARSING
# ============================================================================

def parse_jurisdiction(jurisdiction_str):
    """
    Parse the complex Jurisdictions field to extract court name.
    
    Format: "International;IACHR;International;International;World"
    or "State Courts;N.C. Super. Ct.;United States"
    
    Strategy: Take the second element if it looks like a court name,
    otherwise construct from available parts.
    
    Args:
        jurisdiction_str (str): Raw jurisdiction string from Excel
        
    Returns:
        str: Parsed court name
    """
    if pd.isna(jurisdiction_str):
        return "Unknown Court"
    
    # Split by semicolon
    parts = [p.strip() for p in str(jurisdiction_str).split(';')]
    
    if len(parts) >= 2:
        # If second part contains "Ct." or "Court" or looks like a court, use it
        second_part = parts[1]
        if any(indicator in second_part for indicator in ['Ct.', 'Court', 'Tribunal', 'Commission']):
            return second_part
        # Otherwise, combine first and second parts
        return f"{parts[0]} - {parts[1]}"
    
    # Fallback: use the whole string
    return jurisdiction_str


def parse_country_from_geographies(geographies_str):
    """
    Extract primary country from Geographies field.
    
    Format: "United States;North Carolina"
    Strategy: First element is usually the country
    
    Args:
        geographies_str (str): Raw geographies string from Excel
        
    Returns:
        str: Country name
    """
    if pd.isna(geographies_str):
        return "Unknown"
    
    # Split by semicolon and take first element (usually country)
    parts = [p.strip() for p in str(geographies_str).split(';')]
    return parts[0] if parts else "Unknown"


def parse_region(geography_isos_str):
    """
    Determine Global North/South region from Geography ISOs.
    
    Uses Maria Antonia Tigre's definition:
    - Global South: Latin America, Caribbean, Asia, Africa, Oceania
    - Global North: North America, Europe, Australia
    
    Args:
        geography_isos_str (str): ISO codes like "USA;US-NC"
        
    Returns:
        str: "Global North", "Global South", or "International"
    """
    if pd.isna(geography_isos_str):
        return "Unknown"
    
    # Extract country code (first part before any hyphen)
    isos = str(geography_isos_str).split(';')
    primary_iso = isos[0].split('-')[0] if isos else ""
    
    # Global North countries (ISO codes)
    global_north = {
        'USA', 'CAN',  # North America
        'GBR', 'FRA', 'DEU', 'ITA', 'ESP', 'NLD', 'BEL', 'AUT', 'CHE', 'SWE',
        'NOR', 'DNK', 'FIN', 'IRL', 'PRT', 'GRC', 'POL', 'CZE', 'HUN', 'ROU',
        'AUS', 'NZL',  # Oceania (developed)
        'JPN', 'KOR', 'SGP',  # Asia (developed)
        'ISR'  # Middle East (developed)
    }
    
    # Check if it's international (no specific country)
    if primary_iso in ['INT', 'INTL', 'WORLD']:
        return "International"
    
    # Classify based on ISO code
    if primary_iso in global_north:
        return "Global North"
    elif primary_iso:
        return "Global South"
    else:
        return "Unknown"


def parse_date(date_value):
    """
    Parse various date formats from Excel.
    
    Handles:
    - Excel datetime objects
    - String dates in various formats
    - Year-only values (converted to January 1 of that year)
    
    Args:
        date_value: Date value from Excel (could be datetime, str, or float)
        
    Returns:
        datetime.date or None: Parsed date object or None if parsing fails
    """
    if pd.isna(date_value):
        return None
    
    # If it's already a datetime object, return its date
    if isinstance(date_value, datetime):
        return date_value.date()
    
    # If it's a Timestamp (pandas), convert to datetime
    if isinstance(date_value, pd.Timestamp):
        return date_value.date()
    
    # If it's a year only (float or int like 2024.0)
    if isinstance(date_value, (int, float)):
        try:
            year = int(date_value)
            return datetime(year, 1, 1).date()
        except:
            return None
    
    # If it's a string, try to parse it
    if isinstance(date_value, str):
        # Try common date formats
        for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%d/%m/%Y', '%m/%d/%Y', '%Y']:
            try:
                return datetime.strptime(date_value, fmt).date()
            except:
                continue
    
    return None


def extract_timeline_dates(first_event, last_event):
    """
    Extract filing and decision dates from timeline events.
    
    Strategy:
    - First event is usually filing date
    - Last event is usually decision/judgment date
    
    Args:
        first_event: First event in timeline (from Excel)
        last_event: Last event in timeline (from Excel)
        
    Returns:
        tuple: (filing_date, decision_date) as date objects or None
    """
    filing_date = parse_date(first_event)
    decision_date = parse_date(last_event)
    
    return filing_date, decision_date


def create_metadata_json(row, metadata_type='case'):
    """
    Create JSON metadata from Excel row.
    
    Stores additional fields that don't have dedicated columns in the schema.
    This preserves all information from the source data.
    
    Args:
        row (pd.Series): Row from the Excel dataframe
        metadata_type (str): 'case' or 'document' to determine which fields to include
        
    Returns:
        dict: JSON-serializable dictionary with metadata
    """
    metadata = {}
    
    if metadata_type == 'case':
        # Case-level metadata
        if pd.notna(row.get('Case Summary')):
            metadata['case_summary'] = str(row['Case Summary'])
        
        if pd.notna(row.get('Case Categories')):
            metadata['case_categories'] = str(row['Case Categories'])
        
        if pd.notna(row.get('Principal Laws')):
            metadata['principal_laws'] = str(row['Principal Laws'])
        
        if pd.notna(row.get('Bundle Name(s)')):
            metadata['bundles'] = str(row['Bundle Name(s)'])
        
        if pd.notna(row.get('Full timeline of events (types)')):
            metadata['timeline_types'] = str(row['Full timeline of events (types)'])
        
        if pd.notna(row.get('Full timeline of events (dates)')):
            metadata['timeline_dates'] = str(row['Full timeline of events (dates)'])
        
        if pd.notna(row.get('At Issue')):
            metadata['at_issue'] = str(row['At Issue'])
        
        # Store raw ISO codes for reference
        if pd.notna(row.get('Geography ISOs')):
            metadata['geography_isos'] = str(row['Geography ISOs'])
        
        # Store full geographies string
        if pd.notna(row.get('Geographies')):
            metadata['geographies_full'] = str(row['Geographies'])
    
    elif metadata_type == 'document':
        # Document-level metadata
        if pd.notna(row.get('Document Title')):
            metadata['document_title'] = str(row['Document Title'])
        
        if pd.notna(row.get('Document Summary')):
            metadata['document_summary'] = str(row['Document Summary'])
        
        if pd.notna(row.get('Language(s)')):
            metadata['languages'] = str(row['Language(s)'])
        
        if pd.notna(row.get('Document Variant')):
            metadata['document_variant'] = str(row['Document Variant'])
        
        if pd.notna(row.get('Bundle Name(s)')):
            metadata['bundle_names'] = str(row['Bundle Name(s)'])
        
        # Store original IDs for reference
        if pd.notna(row.get('Internal Document ID')):
            metadata['internal_document_id'] = str(row['Internal Document ID'])
        
        if pd.notna(row.get('Document ID')):
            metadata['original_document_id'] = str(row['Document ID'])
    
    return metadata if metadata else None


def generate_case_uuid(case_id_str):
    """
    Generate deterministic UUID for a case.
    
    Uses UUID5 (SHA-1 based) with a project namespace to ensure:
    - Same case_id always generates same UUID
    - UUIDs are globally unique
    - Consistent across multiple script runs
    
    Args:
        case_id_str (str): Original Case ID from Excel
        
    Returns:
        UUID: Deterministic UUID object
    """
    # Clean the case_id string
    clean_id = str(case_id_str).strip().lower()
    
    # Generate UUID5 using project namespace
    return uuid5(UUID_NAMESPACE, f"case_{clean_id}")


def generate_document_uuid(document_id_str):
    """
    Generate deterministic UUID for a document.
    
    Similar to case UUID generation but uses document_id.
    
    Args:
        document_id_str (str): Original Document ID from Excel
        
    Returns:
        UUID: Deterministic UUID object
    """
    # Clean the document_id string
    clean_id = str(document_id_str).strip().lower()
    
    # Generate UUID5 using project namespace
    return uuid5(UUID_NAMESPACE, f"document_{clean_id}")


# ============================================================================
# DATABASE POPULATION FUNCTIONS
# ============================================================================

def process_case(row, session):
    """
    Process a single case row from Excel and upsert to database.
    
    Upsert logic: If case_id exists, update it; if not, create new.
    This allows the script to be run multiple times safely.
    
    Args:
        row (pd.Series): Row from Excel dataframe
        session: SQLAlchemy session
        
    Returns:
        Case: The created or updated Case object
    """
    # Generate deterministic UUID from Case ID
    case_uuid = generate_case_uuid(row['Case ID'])
    
    # Check if case already exists
    existing_case = session.query(Case).filter(Case.case_id == case_uuid).first()
    
    # Parse complex fields
    court_name = parse_jurisdiction(row.get('Jurisdictions'))
    country = parse_country_from_geographies(row.get('Geographies'))
    region = parse_region(row.get('Geography ISOs'))
    
    # Extract dates from timeline
    filing_date, decision_date = extract_timeline_dates(
        row.get('First event in timeline'),
        row.get('Last event in timeline')
    )
    
    # Create metadata JSON
    metadata = create_metadata_json(row, metadata_type='case')
    
    # Prepare case data
    case_data = {
        'case_name': str(row['Case Name']),
        'case_number': str(row['Case Number']) if pd.notna(row.get('Case Number')) else None,
        'court_name': court_name,
        'country': country,
        'region': region,
        'filing_date': filing_date,
        'decision_date': decision_date,
        'case_status': str(row['Status']) if pd.notna(row.get('Status')) else None,
        'case_type': None,  # Not directly available in Excel, could be derived from Categories
        'case_url': str(row['Case URL']) if pd.notna(row.get('Case URL')) else None,
        'data_source': 'climatecasechart.com',
        'metadata_json': metadata
    }
    
    if existing_case:
        # Update existing case
        for key, value in case_data.items():
            setattr(existing_case, key, value)
        existing_case.updated_at = datetime.now()
        case = existing_case
    else:
        # Create new case
        case = Case(
            case_id=case_uuid,
            **case_data
        )
        session.add(case)
    
    return case


def process_document(row, case, session):
    """
    Process a single document row and upsert to database.
    
    Links the document to its parent case.
    
    Args:
        row (pd.Series): Row from Excel dataframe
        case (Case): Parent case object
        session: SQLAlchemy session
        
    Returns:
        Document: The created or updated Document object
    """
    # Generate deterministic UUID from Document ID
    doc_uuid = generate_document_uuid(row['Document ID'])
    
    # Check if document already exists
    existing_doc = session.query(Document).filter(Document.document_id == doc_uuid).first()
    
    # Parse document date
    doc_date = parse_date(row.get('Document Filing Date'))
    
    # Create metadata JSON
    metadata = create_metadata_json(row, metadata_type='document')
    
    # Prepare document data
    doc_data = {
        'case_id': case.case_id,
        'document_type': str(row['Document Type']) if pd.notna(row.get('Document Type')) else 'Decision',
        'document_url': str(row['Document Content URL']) if pd.notna(row.get('Document Content URL')) else None,
        'pdf_file_path': None,  # Will be filled by download script
        'file_size_bytes': None,  # Will be filled by download script
        'page_count': None,  # Will be filled by extraction script
        'pdf_downloaded': False,  # Not yet downloaded
        'download_date': None,
        'download_error': None,
        'metadata_json': metadata
    }
    
    if existing_doc:
        # Update existing document
        for key, value in doc_data.items():
            # Don't overwrite pdf_file_path, file_size_bytes, etc. if they already exist
            # (they were set by download/extraction scripts)
            if key in ['pdf_file_path', 'file_size_bytes', 'page_count', 'pdf_downloaded', 
                      'download_date', 'download_error']:
                if getattr(existing_doc, key) is None or getattr(existing_doc, key) == False:
                    setattr(existing_doc, key, value)
            else:
                setattr(existing_doc, key, value)
        existing_doc.updated_at = datetime.now()
        doc = existing_doc
    else:
        # Create new document
        doc = Document(
            document_id=doc_uuid,
            **doc_data
        )
        session.add(doc)
    
    return doc


# ============================================================================
# MAIN PROCESSING FUNCTION
# ============================================================================

def populate_database():
    """
    Main function to populate database from Excel file.
    
    Process:
    1. Load Excel file
    2. Group by Case ID (handle multiple documents per case)
    3. For each case:
       - Create/update Case record
       - Create/update Document records
    4. Generate statistics
    """
    # Initialize statistics
    stats = {
        'total_rows': 0,
        'unique_cases': 0,
        'cases_created': 0,
        'cases_updated': 0,
        'documents_created': 0,
        'documents_updated': 0,
        'errors': 0,
        'error_details': []
    }
    
    # Load Excel file
    logging.info("Loading Excel database...")
    try:
        df = pd.read_excel(DATABASE_FILE)
        
        # Apply test mode if enabled
        if TEST_MODE:
            df = df.head(TEST_N_ROWS)
            logging.info(f"\n⚠️  TEST MODE: Processing only {len(df)} rows\n")
        
        stats['total_rows'] = len(df)
        logging.info(f"✓ Loaded {len(df)} rows from {DATABASE_FILE}")
        
        # Count unique cases
        unique_cases = df['Case ID'].nunique()
        stats['unique_cases'] = unique_cases
        logging.info(f"✓ Found {unique_cases} unique cases\n")
        
    except Exception as e:
        logging.error(f"✗ Failed to load Excel file: {e}")
        return
    
    # Create database session
    session = SessionLocal()
    
    try:
        # Group by Case ID (one case can have multiple documents)
        case_groups = df.groupby('Case ID')
        
        # Process each case
        for case_id, case_rows in tqdm(case_groups, desc="Processing cases"):
            try:
                # Get the first row for case-level data
                # (all rows in this group have the same case data)
                case_row = case_rows.iloc[0]
                
                # Check if case exists
                case_uuid = generate_case_uuid(case_id)
                existing_case = session.query(Case).filter(Case.case_id == case_uuid).first()
                
                # Process case
                case = process_case(case_row, session)
                
                if existing_case:
                    stats['cases_updated'] += 1
                else:
                    stats['cases_created'] += 1
                
                # Process all documents for this case
                for _, doc_row in case_rows.iterrows():
                    doc_uuid = generate_document_uuid(doc_row['Document ID'])
                    existing_doc = session.query(Document).filter(
                        Document.document_id == doc_uuid
                    ).first()
                    
                    # Process document
                    doc = process_document(doc_row, case, session)
                    
                    if existing_doc:
                        stats['documents_updated'] += 1
                    else:
                        stats['documents_created'] += 1
                
                # Commit after each case (safer for large datasets)
                session.commit()
                
            except Exception as e:
                # Roll back this case's changes
                session.rollback()
                stats['errors'] += 1
                error_msg = f"Case {case_id}: {str(e)}"
                stats['error_details'].append(error_msg)
                logging.error(f"✗ Error processing case {case_id}: {e}")
    
    finally:
        # Always close the session
        session.close()
    
    # Print summary
    print_population_summary(stats)


def print_population_summary(stats):
    """
    Print comprehensive summary of population results.
    
    Args:
        stats (dict): Dictionary with population statistics
    """
    logging.info("\n" + "="*70)
    logging.info("DATABASE POPULATION SUMMARY")
    logging.info("="*70)
    logging.info(f"Total rows processed:         {stats['total_rows']}")
    logging.info(f"Unique cases:                 {stats['unique_cases']}")
    logging.info("")
    logging.info(f"Cases created:                {stats['cases_created']}")
    logging.info(f"Cases updated:                {stats['cases_updated']}")
    logging.info(f"Documents created:            {stats['documents_created']}")
    logging.info(f"Documents updated:            {stats['documents_updated']}")
    logging.info("")
    logging.info(f"Errors encountered:           {stats['errors']}")
    
    if stats['error_details']:
        logging.info("\nError details:")
        for error in stats['error_details'][:10]:  # Show first 10 errors
            logging.info(f"  - {error}")
        if len(stats['error_details']) > 10:
            logging.info(f"  ... and {len(stats['error_details']) - 10} more errors")
    
    # Calculate success rate
    if stats['total_rows'] > 0:
        success_rate = ((stats['total_rows'] - stats['errors']) / stats['total_rows']) * 100
        logging.info(f"\nSuccess rate:                 {success_rate:.1f}%")
    
    logging.info("="*70)


# ============================================================================
# VALIDATION FUNCTION
# ============================================================================

def validate_population():
    """
    Validate that the database was populated correctly.
    
    Checks:
    - Row counts match expectations
    - No NULL values in required fields
    - Foreign key relationships are intact
    - Sample data looks correct
    """
    logging.info("\n" + "="*70)
    logging.info("VALIDATING DATABASE POPULATION")
    logging.info("="*70)
    
    session = SessionLocal()
    
    try:
        # Count records
        case_count = session.query(Case).count()
        doc_count = session.query(Document).count()
        
        logging.info(f"\nRecord counts:")
        logging.info(f"  Cases:     {case_count}")
        logging.info(f"  Documents: {doc_count}")
        
        # Check for NULL values in required fields
        logging.info(f"\nChecking data quality...")
        
        # Cases with missing required fields
        cases_no_name = session.query(Case).filter(Case.case_name == None).count()
        cases_no_court = session.query(Case).filter(Case.court_name == None).count()
        cases_no_country = session.query(Case).filter(Case.country == None).count()
        
        logging.info(f"  Cases missing name:    {cases_no_name}")
        logging.info(f"  Cases missing court:   {cases_no_court}")
        logging.info(f"  Cases missing country: {cases_no_country}")
        
        # Documents with missing URLs
        docs_no_url = session.query(Document).filter(Document.document_url == None).count()
        logging.info(f"  Documents missing URL: {docs_no_url}")
        
        # Sample records
        logging.info(f"\nSample case record:")
        sample_case = session.query(Case).first()
        if sample_case:
            logging.info(f"  ID:      {sample_case.case_id}")
            logging.info(f"  Name:    {sample_case.case_name[:60]}...")
            logging.info(f"  Court:   {sample_case.court_name}")
            logging.info(f"  Country: {sample_case.country}")
            logging.info(f"  Region:  {sample_case.region}")
            logging.info(f"  Status:  {sample_case.case_status}")
        
        logging.info(f"\nSample document record:")
        sample_doc = session.query(Document).first()
        if sample_doc:
            logging.info(f"  ID:   {sample_doc.document_id}")
            logging.info(f"  Type: {sample_doc.document_type}")
            logging.info(f"  URL:  {sample_doc.document_url[:60] if sample_doc.document_url else 'None'}...")
        
        logging.info("\n✓ Validation complete")
        
    except Exception as e:
        logging.error(f"✗ Validation failed: {e}")
    
    finally:
        session.close()
    
    logging.info("="*70)


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    """
    This block runs when you execute the script directly:
    python populate_metadata.py
    """
    
    logging.info("="*70)
    logging.info("DATABASE METADATA POPULATION - CLIMATE LITIGATION DATABASE")
    logging.info("="*70)
    logging.info(f"Source file: {DATABASE_FILE}")
    logging.info(f"Database: {DB_CONFIG['database']}")
    
    if TEST_MODE:
        logging.info(f"\n⚠️  TEST MODE: Processing only {TEST_N_ROWS} rows")
    else:
        logging.info("\n✅ FULL MODE: Processing all rows")
    
    logging.info("="*70 + "\n")
    
    # Create logs directory if needed
    Path('logs').mkdir(exist_ok=True)
    
    # Run the population process
    populate_database()
    
    # Validate the results
    validate_population()
    
    if TEST_MODE:
        logging.info("\n⚠️  TEST MODE was enabled. To process all rows:")
        logging.info("   Set TEST_MODE = False in the configuration section")
    
    logging.info("\nDatabase population completed!")
