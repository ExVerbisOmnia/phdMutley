#!/usr/bin/env python3
"""
Database Metadata Population Script for Climate Litigation Database (Version 3.0)
==================================================================================
Imports case and document metadata from Excel into PostgreSQL database.

📍 Run from: /home/gusrodgs/Gus/cienciaDeDados/phdMutley
Command: python scripts/phase1/populate_metadata.py

This script reads the filtered Excel database (baseDecisions.xlsx) containing
2,924 climate litigation decisions and populates the PostgreSQL database with
complete metadata for both cases and documents.

Version 3.0 Changes:
- Added trial batch filtering support
- Improved logging to show filtering statistics

Key Features:
-------------
- Centralized Config (config.py)
- Deterministic UUID generation
- Smart JSON parsing (Stores lists as actual Arrays)
- Upsert logic
- Trial batch mode support

Author: Lucas Biasetton (Refactored by Assistant)
Project: Doutorado PM
Version: 3.0 (Trial Batch Support)
Date: November 2025
"""

import sys
import os
from datetime import datetime
import pandas as pd
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import URL
from tqdm import tqdm

# ============================================================================
# CONFIGURATION & IMPORTS
# ============================================================================

# Add project root and scripts directory to path
PROJECT_ROOT = '/home/gusrodgs/Gus/cienciaDeDados/phdMutley'
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'scripts'))

# Import config
from config import CONFIG, DB_CONFIG, DATABASE_FILE, UUID_NAMESPACE, LOGS_DIR, TRIAL_BATCH_CONFIG

# Import database models
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'scripts', '0-initialize-database'))
from init_database import Case, Document, Base

from uuid import uuid5

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / 'metadata_population.log'),
        logging.StreamHandler()
    ]
)

# Suppress verbose logging from external libraries
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)


# ============================================================================
# DATABASE SETUP
# ============================================================================

try:
    db_url = URL.create(**DB_CONFIG)
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    logging.info("✓ Database connection established")
except Exception as e:
    logging.error(f"✗ Failed to connect to database: {e}")
    sys.exit(1)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def parse_jurisdiction(jurisdiction_str):
    """Parse the complex Jurisdictions field to extract court name."""
    if pd.isna(jurisdiction_str):
        return "Unknown Court"
    
    parts = [p.strip() for p in str(jurisdiction_str).split(';')]
    
    if len(parts) >= 2:
        second_part = parts[1]
        if any(indicator in second_part for indicator in ['Ct.', 'Court', 'Tribunal', 'Commission']):
            return second_part
        return f"{parts[0]} - {parts[1]}"
    
    return jurisdiction_str

def parse_country_from_geographies(geographies_str):
    """Extract primary country from Geographies field."""
    if pd.isna(geographies_str):
        return "Unknown"
    parts = [p.strip() for p in str(geographies_str).split(';')]
    return parts[0] if parts else "Unknown"

def parse_region(geography_isos_str):
    """Determine Global North/South region from Geography ISOs."""
    if pd.isna(geography_isos_str):
        return "Unknown"
    
    isos = str(geography_isos_str).split(';')
    primary_iso = isos[0].split('-')[0] if isos else ""
    
    global_north = {
        'USA', 'CAN', 'GBR', 'FRA', 'DEU', 'ITA', 'ESP', 'NLD', 'BEL', 'AUT', 
        'CHE', 'SWE', 'NOR', 'DNK', 'FIN', 'IRL', 'PRT', 'GRC', 'POL', 'CZE', 
        'HUN', 'ROU', 'AUS', 'NZL', 'JPN', 'KOR', 'SGP', 'ISR'
    }
    
    if primary_iso in ['INT', 'INTL', 'WORLD']:
        return "International"
    elif primary_iso in global_north:
        return "Global North"
    elif primary_iso:
        return "Global South"
    else:
        return "Unknown"

def parse_date(date_value):
    """Parse various date formats from Excel."""
    if pd.isna(date_value):
        return None
    if isinstance(date_value, datetime):
        return date_value.date()
    if isinstance(date_value, pd.Timestamp):
        return date_value.date()
    if isinstance(date_value, (int, float)):
        try:
            return datetime(int(date_value), 1, 1).date()
        except:
            return None
    if isinstance(date_value, str):
        for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%d/%m/%Y', '%m/%d/%Y', '%Y']:
            try:
                return datetime.strptime(date_value, fmt).date()
            except:
                continue
    return None

def extract_timeline_dates(first_event, last_event):
    return parse_date(first_event), parse_date(last_event)

def generate_case_uuid(case_id_str):
    """Generate deterministic UUID using project namespace."""
    clean_id = str(case_id_str).strip().lower()
    return uuid5(UUID_NAMESPACE, f"case_{clean_id}")

def generate_document_uuid(document_id_str):
    """Generate deterministic UUID for a document."""
    clean_id = str(document_id_str).strip().lower()
    return uuid5(UUID_NAMESPACE, f"document_{clean_id}")

def create_metadata_json(row, metadata_type='case'):
    """
    Create JSON metadata from Excel row.
    Splits list-like strings into actual JSON arrays.
    """
    metadata = {}
    
    if metadata_type == 'case':
        # Simple text fields
        text_mappings = {
            'case_summary': 'Case Summary',
            'principal_laws': 'Principal Laws',
            'at_issue': 'At Issue',
            'bundles': 'Bundle Name(s)',
            'Geographies': 'Geographies'  # FIX: Add for backward compatibility with v5 citation extraction
        }
        for key, col in text_mappings.items():
            if pd.notna(row.get(col)):
                metadata[key] = str(row[col])

        # List fields (Split by semicolon)
        list_mappings = {
            'case_categories': 'Case Categories',
            'timeline_types': 'Full timeline of events (types)',
            'timeline_dates': 'Full timeline of events (dates)',
            'geography_isos': 'Geography ISOs',
            'geographies_full': 'Geographies'
        }
        
        for key, col in list_mappings.items():
            if pd.notna(row.get(col)):
                metadata[key] = [x.strip() for x in str(row[col]).split(';') if x.strip()]
    
    elif metadata_type == 'document':
        text_mappings = {
            'document_title': 'Document Title',
            'document_summary': 'Document Summary',
            'document_variant': 'Document Variant',
            'internal_document_id': 'Internal Document ID',
            'original_document_id': 'Document ID'
        }
        for key, col in text_mappings.items():
            if pd.notna(row.get(col)):
                metadata[key] = str(row[col])

        # List fields
        list_mappings = {
            'languages': 'Language(s)',
            'bundle_names': 'Bundle Name(s)'
        }
        for key, col in list_mappings.items():
            if pd.notna(row.get(col)):
                metadata[key] = [x.strip() for x in str(row[col]).split(';') if x.strip()]
    
    return metadata if metadata else None

# ============================================================================
# TRIAL BATCH FILTERING
# ============================================================================

def apply_trial_batch_filter(df):
    """
    Filter DataFrame to only include trial batch documents if enabled.
    
    Returns:
        tuple: (filtered_df, stats_dict)
    """
    original_count = len(df)
    
    if not TRIAL_BATCH_CONFIG['ENABLED']:
        logging.info("ℹ️  Trial batch mode DISABLED - processing all documents")
        return df, {'original': original_count, 'filtered': original_count, 'excluded': 0}
    
    # Check if trial batch column exists
    col_name = TRIAL_BATCH_CONFIG['COLUMN_NAME']
    if col_name not in df.columns:
        logging.error(f"❌ Trial batch column '{col_name}' not found in database!")
        logging.error(f"   Available columns: {', '.join(df.columns)}")
        logging.error("   Proceeding without filtering (all documents will be processed)")
        return df, {'original': original_count, 'filtered': original_count, 'excluded': 0, 'error': True}
    
    # Filter by trial batch
    true_values = TRIAL_BATCH_CONFIG['TRUE_VALUES']
    trial_batch_df = df[df[col_name].isin(true_values)].copy()
    
    filtered_count = len(trial_batch_df)
    excluded_count = original_count - filtered_count
    
    logging.info("="*70)
    logging.info("TRIAL BATCH FILTERING")
    logging.info("="*70)
    logging.info(f"Original documents:  {original_count}")
    logging.info(f"Trial batch docs:    {filtered_count}")
    logging.info(f"Excluded:            {excluded_count}")
    logging.info(f"Filter column:       '{col_name}'")
    logging.info(f"True values:         {true_values}")
    logging.info("="*70)
    
    if filtered_count == 0:
        logging.warning("⚠️  WARNING: No documents matched trial batch filter!")
        logging.warning("   Check that the 'Trial batch' column has correct values")
    
    return trial_batch_df, {
        'original': original_count,
        'filtered': filtered_count,
        'excluded': excluded_count
    }

# ============================================================================
# DATABASE POPULATION LOGIC
# ============================================================================

def process_case(row, session):
    case_uuid = str(generate_case_uuid(row['Case ID']))
    existing_case = session.query(Case).filter(Case.case_id == case_uuid).first()
    
    court_name = parse_jurisdiction(row.get('Jurisdictions'))
    country = parse_country_from_geographies(row.get('Geographies'))
    region = parse_region(row.get('Geography ISOs'))
    filing_date, decision_date = extract_timeline_dates(
        row.get('First event in timeline'),
        row.get('Last event in timeline')
    )
    
    metadata = create_metadata_json(row, metadata_type='case')
    
    case_data = {
        'case_name': str(row['Case Name']),
        'case_number': str(row['Case Number']) if pd.notna(row.get('Case Number')) else None,
        'jurisdiction': court_name,
        'geographies': str(row['Geographies']) if pd.notna(row.get('Geographies')) else None,  # FIX: Populate geographies column
        'region': region,
        'case_filing_year': filing_date.year if filing_date else None,
        'last_event_date': decision_date,
        'case_status': str(row['Status']) if pd.notna(row.get('Status')) else None,
        'case_url': str(row['Case URL']) if pd.notna(row.get('Case URL')) else None,
        # 'data_source': 'climatecasechart.com', # Removed as it's not in the model
        'metadata_data': metadata  # Maps to DB column 'metadata_data'
    }
    
    if existing_case:
        for key, value in case_data.items():
            setattr(existing_case, key, value)
        existing_case.updated_at = datetime.now()
        return existing_case, 'updated'
    else:
        case = Case(case_id=case_uuid, **case_data)
        session.add(case)
        return case, 'created'

def process_document(row, case, session):
    doc_uuid = generate_document_uuid(row['Document ID'])
    existing_doc = session.query(Document).filter(Document.document_id == doc_uuid).first()
    metadata = create_metadata_json(row, metadata_type='document')
    
    doc_data = {
        'case_id': case.case_id,
        'document_type': str(row['Document Type']) if pd.notna(row.get('Document Type')) else 'Decision',
        'document_url': str(row['Document Content URL']) if pd.notna(row.get('Document Content URL')) else None,
        'metadata_data': metadata  # Maps to DB column 'metadata_data'
    }
    
    if existing_doc:
        for key, value in doc_data.items():
            # Don't overwrite download/extraction fields
            if key not in ['pdf_file_path', 'file_size_bytes', 'page_count', 
                           'pdf_downloaded', 'download_date', 'download_error']:
                setattr(existing_doc, key, value)
        existing_doc.updated_at = datetime.now()
        return existing_doc, 'updated'
    else:
        doc = Document(document_id=doc_uuid, pdf_downloaded=False, **doc_data)
        session.add(doc)
        return doc, 'created'

def populate_database():
    stats = {
        'total_rows': 0, 'cases_created': 0, 'cases_updated': 0,
        'docs_created': 0, 'docs_updated': 0, 'errors': 0
    }
    
    logging.info("Loading Excel database...")
    try:
        df = pd.read_excel(DATABASE_FILE)
        original_count = len(df)
        logging.info(f"Loaded database with {original_count} rows.")
        
    except Exception as e:
        logging.error(f"✗ Failed to load Excel file: {e}")
        return

    # Apply Trial Batch Filter
    df, filter_stats = apply_trial_batch_filter(df)
    
    if len(df) == 0:
        logging.error("❌ No documents to process after filtering!")
        return
        
    stats['total_rows'] = len(df)

    session = SessionLocal()
    
    try:
        case_groups = df.groupby('Case ID')
        
        for case_id, case_rows in tqdm(case_groups, desc="Processing cases"):
            try:
                case_row = case_rows.iloc[0]
                case, c_status = process_case(case_row, session)
                
                if c_status == 'created': stats['cases_created'] += 1
                else: stats['cases_updated'] += 1
                
                for _, doc_row in case_rows.iterrows():
                    doc, d_status = process_document(doc_row, case, session)
                    if d_status == 'created': stats['docs_created'] += 1
                    else: stats['docs_updated'] += 1
                
                session.commit()
                
            except Exception as e:
                session.rollback()
                stats['errors'] += 1
                logging.error(f"Error processing case {case_id}: {e}")
                
    finally:
        session.close()
        
    logging.info("\n" + "="*70)
    logging.info(f"POPULATION SUMMARY")
    logging.info("="*70)
    logging.info(f"Documents processed: {stats['total_rows']}")
    logging.info(f"Cases: {stats['cases_created']} created, {stats['cases_updated']} updated")
    logging.info(f"Docs:  {stats['docs_created']} created, {stats['docs_updated']} updated")
    logging.info(f"Errors: {stats['errors']}")
    
    if TRIAL_BATCH_CONFIG['ENABLED']:
        logging.info("\n✓ Trial batch mode was ENABLED")
        logging.info(f"  Processed {filter_stats['filtered']} out of {filter_stats['original']} total documents")
    
    logging.info("="*70)

if __name__ == "__main__":
    populate_database()
