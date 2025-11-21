#!/usr/bin/env python3
"""
PDF Text Extraction Script (Version 3.0 - Trial Batch Support)
==============================================================
Optimized for systems with limited RAM (8GB).
Caps concurrency and enforces garbage collection.

📍 Run from: /home/gusrodgs/Gus/cienciaDeDados/phdMutley
Command: python scripts/phase1/extract_texts.py

Version 3.0 Changes:
- Added trial batch filtering support
- Only processes PDFs corresponding to trial batch documents
"""

import sys
import os
import logging
import concurrent.futures
import gc
from pathlib import Path
from datetime import datetime
from uuid import uuid5
from tqdm import tqdm
import pandas as pd

# PDF Libraries
import pdfplumber
import fitz  # PyMuPDF
import PyPDF2

# Database
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import URL

# ============================================================================
# CONFIGURATION & IMPORTS
# ============================================================================

# Add project root to path to import config
sys.path.insert(0, '/home/gusrodgs/Gus/cienciaDeDados/phdMutley')
from config import (CONFIG, DB_CONFIG, PDF_DOWNLOAD_DIR, UUID_NAMESPACE, 
                    LOGS_DIR, TRIAL_BATCH_CONFIG, DATABASE_FILE)

# Import database models
sys.path.insert(0, os.path.join('/home/gusrodgs/Gus/cienciaDeDados/phdMutley', 'scripts', 'phase0'))
from init_database import Document, ExtractedText, Base

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    force=True, 
    handlers=[
        logging.FileHandler(LOGS_DIR / 'extraction_memory_safe.log', mode='a'),
        logging.StreamHandler()
    ]
)

# ============================================================================
# SAFETY SETTINGS
# ============================================================================

SAFE_WORKERS = 2 

# ============================================================================
# TRIAL BATCH FILTERING
# ============================================================================

def get_trial_batch_document_ids():
    """
    Load Excel file and return set of Document IDs that are in the trial batch.
    Returns None if trial batch mode is disabled or if there's an error.
    """
    if not TRIAL_BATCH_CONFIG['ENABLED']:
        logging.info("ℹ️  Trial batch mode DISABLED - will process all PDFs")
        return None
    
    try:
        df = pd.read_excel(DATABASE_FILE)
        logging.info(f"Loaded database with {len(df)} rows for trial batch filtering")
        
        col_name = TRIAL_BATCH_CONFIG['COLUMN_NAME']
        if col_name not in df.columns:
            logging.error(f"❌ Trial batch column '{col_name}' not found!")
            logging.error("   Proceeding without filtering")
            return None
        
        true_values = TRIAL_BATCH_CONFIG['TRUE_VALUES']
        trial_batch_df = df[df[col_name].isin(true_values)]
        
        # Extract Document IDs as strings (they're stored in filenames as "doc_{id}.pdf")
        doc_ids = set(trial_batch_df['Document ID'].astype(str))
        
        logging.info("="*70)
        logging.info("TRIAL BATCH FILTERING FOR TEXT EXTRACTION")
        logging.info("="*70)
        logging.info(f"Total documents in database:  {len(df)}")
        logging.info(f"Trial batch documents:        {len(doc_ids)}")
        logging.info(f"Will only process PDFs matching these {len(doc_ids)} Document IDs")
        logging.info("="*70)
        
        return doc_ids
        
    except Exception as e:
        logging.error(f"❌ Error loading trial batch filter: {e}")
        logging.error("   Proceeding without filtering")
        return None

def should_process_pdf(pdf_filename, trial_batch_ids):
    """
    Determine if a PDF should be processed based on trial batch filter.
    
    Args:
        pdf_filename: Name of PDF file (e.g., "doc_12345.pdf")
        trial_batch_ids: Set of Document IDs in trial batch, or None if no filtering
    
    Returns:
        bool: True if should process, False otherwise
    """
    if trial_batch_ids is None:
        return True  # No filtering
    
    # Extract document ID from filename
    doc_id = extract_document_id_from_filename(pdf_filename)
    if doc_id is None:
        return False  # Invalid filename format
    
    return doc_id in trial_batch_ids

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def generate_document_uuid(document_id_str):
    clean_id = str(document_id_str).strip().lower()
    return uuid5(UUID_NAMESPACE, f"document_{clean_id}")

def extract_document_id_from_filename(filename):
    """
    Extract document ID from filename.
    Format: doc_{document_id}.pdf
    Note: The hash suffix (_XXXX) is part of the document ID, not separate.
    """
    if filename.startswith('doc_') and filename.endswith('.pdf'):
        # Remove 'doc_' prefix and '.pdf' suffix
        # The remaining string is the complete document ID (including hash if present)
        return filename[4:-4]
    return None

def assess_text_quality(text, page_count):
    notes = []
    words = text.split() if text else []
    word_count = len(words)
    char_count = len(text)
    
    avg_word_len = char_count / word_count if word_count > 0 else 0
    words_per_page = word_count / page_count if page_count > 0 else 0
    
    is_scanned = False
    if page_count >= 1 and word_count < CONFIG['SCANNED_PDF_THRESHOLD']:
        is_scanned = True
        notes.append(f"Likely scanned: {word_count} words in {page_count} pages")
    elif words_per_page < 10:
        is_scanned = True
        notes.append(f"Very low density: {words_per_page:.1f} words/page")

    if word_count == 0:
        quality = 'failed'
    elif is_scanned:
        quality = 'poor'
    elif not (2 <= avg_word_len <= 20):
        quality = 'fair'
        notes.append(f"Bad avg word length: {avg_word_len:.1f}")
    else:
        quality = 'excellent'
        
    return {
        'quality': quality,
        'is_scanned': is_scanned,
        'word_count': word_count,
        'character_count': char_count,
        'notes': '; '.join(notes)
    }

# ============================================================================
# EXTRACTION LOGIC
# ============================================================================

def extract_text_hierarchical(pdf_path):
    path_str = str(pdf_path)
    
    # 1. pdfplumber (Best quality, highest memory usage)
    try:
        with pdfplumber.open(path_str) as pdf:
            text_parts = []
            for p in pdf.pages:
                txt = p.extract_text() or ""
                text_parts.append(txt)
                
            full_text = '\n\n'.join(text_parts)
            del text_parts
            
            if full_text.strip():
                return {'text': full_text, 'pages': len(pdf.pages), 'method': 'pdfplumber', 'success': True}
    except Exception:
        pass

    # 2. PyMuPDF (Fast, low memory)
    try:
        with fitz.open(path_str) as doc:
            text_parts = [page.get_text() for page in doc]
            full_text = '\n\n'.join(text_parts)
            if full_text.strip():
                return {'text': full_text, 'pages': len(doc), 'method': 'pymupdf', 'success': True}
    except Exception:
        pass

    # 3. PyPDF2
    try:
        reader = PyPDF2.PdfReader(path_str)
        text_parts = [p.extract_text() or "" for p in reader.pages]
        full_text = '\n\n'.join(text_parts)
        if full_text.strip():
            return {'text': full_text, 'pages': len(reader.pages), 'method': 'pypdf2', 'success': True}
    except Exception:
        pass

    return {'text': '', 'pages': 0, 'method': 'failed', 'success': False}

# ============================================================================
# WORKER FUNCTION
# ============================================================================

def process_single_pdf_safe(pdf_path_str):
    """
    Worker function with aggressive memory cleanup.
    """
    pdf_path = Path(pdf_path_str)
    
    # Initialize DB connection
    try:
        local_engine = create_engine(URL.create(**DB_CONFIG))
        LocalSession = sessionmaker(bind=local_engine)
        session = LocalSession()
    except Exception as e:
        return {'status': 'db_error', 'file': pdf_path.name, 'error': str(e)}

    result_data = None

    try:
        # 1. Identify
        doc_id_str = extract_document_id_from_filename(pdf_path.name)
        if not doc_id_str:
            return {'status': 'skipped_invalid_name', 'file': pdf_path.name}

        doc_uuid = generate_document_uuid(doc_id_str)
        
        # 2. Check DB
        document = session.query(Document).filter(Document.document_id == doc_uuid).first()
        if not document:
            return {'status': 'skipped_not_in_db', 'file': pdf_path.name}
            
        if session.query(ExtractedText).filter(ExtractedText.document_id == doc_uuid).first():
            return {'status': 'skipped_exists', 'file': pdf_path.name}

        # 3. Extract
        extraction_result = extract_text_hierarchical(pdf_path)
        
        if not extraction_result['success']:
            extracted = ExtractedText(
                document_id=doc_uuid,
                raw_text="",
                extraction_quality='failed',
                extraction_date=datetime.now(),
                extraction_notes="All extraction methods failed"
            )
            session.add(extracted)
            session.commit()
            return {'status': 'failed', 'file': pdf_path.name}

        # 4. Assess
        quality = assess_text_quality(extraction_result['text'], extraction_result['pages'])

        # 5. Save
        document.page_count = extraction_result['pages']
        document.pdf_file_path = str(pdf_path)
        document.pdf_downloaded = True
        try:
            document.file_size_bytes = pdf_path.stat().st_size
        except:
            pass

        extracted = ExtractedText(
            document_id=doc_uuid,
            raw_text=extraction_result['text'],
            processed_text=extraction_result['text'], 
            word_count=quality['word_count'],
            character_count=quality['character_count'],
            extraction_date=datetime.now(),
            extraction_method=extraction_result['method'],
            extraction_quality=quality['quality'],
            extraction_notes=quality['notes']
        )
        
        session.add(extracted)
        session.commit()
        
        result_data = {
            'status': 'success', 
            'file': pdf_path.name, 
            'method': extraction_result['method'],
            'quality': quality['quality']
        }
        return result_data

    except Exception as e:
        session.rollback()
        return {'status': 'error', 'file': pdf_path.name, 'error': str(e)}
        
    finally:
        # 6. AGGRESSIVE CLEANUP
        session.close()
        local_engine.dispose()
        
        # Only delete variables if they were actually created
        if 'document' in locals(): del document
        if 'extracted' in locals(): del extracted
        if 'extraction_result' in locals(): del extraction_result
        
        gc.collect()

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def process_all_pdfs():
    logging.info("="*70)
    logging.info(f"PDF TEXT EXTRACTION (SAFE MODE) - Workers: {SAFE_WORKERS}")
    logging.info("="*70)
    
    if not PDF_DOWNLOAD_DIR.exists():
        logging.error(f"PDF Directory not found: {PDF_DOWNLOAD_DIR}")
        return

    # Get trial batch filter
    trial_batch_ids = get_trial_batch_document_ids()
    
    # Get all PDF files
    all_pdf_files = list(PDF_DOWNLOAD_DIR.glob('*.pdf'))
    logging.info(f"Found {len(all_pdf_files)} PDF files in download directory")
    
    # Filter by trial batch if enabled
    if trial_batch_ids is not None:
        pdf_files = [f for f in all_pdf_files if should_process_pdf(f.name, trial_batch_ids)]
        excluded = len(all_pdf_files) - len(pdf_files)
        logging.info(f"After trial batch filter: {len(pdf_files)} files to process ({excluded} excluded)")
    else:
        pdf_files = all_pdf_files

    if len(pdf_files) == 0:
        logging.error("❌ No PDF files to process!")
        return

    logging.info(f"Processing {len(pdf_files)} files...")

    stats = {
        'success': 0, 'failed': 0, 'skipped_exists': 0, 
        'skipped_invalid': 0, 'errors': 0
    }
    
    # Use limited workers
    with concurrent.futures.ProcessPoolExecutor(max_workers=SAFE_WORKERS) as executor:
        path_strings = [str(p) for p in pdf_files]
        
        results = list(tqdm(
            executor.map(process_single_pdf_safe, path_strings), 
            total=len(path_strings),
            desc="Extracting (MemSafe)"
        ))

    # Results
    for res in results:
        status = res['status']
        if status == 'success': stats['success'] += 1
        elif status == 'skipped_exists': stats['skipped_exists'] += 1
        elif status in ['skipped_invalid_name', 'skipped_not_in_db']: stats['skipped_invalid'] += 1
        elif status == 'failed': stats['failed'] += 1
        else: 
            stats['errors'] += 1
            logging.error(f"Error: {res.get('error')}")

    logging.info("\n" + "="*70)
    logging.info("EXTRACTION SUMMARY")
    logging.info("="*70)
    logging.info(f"Successful:        {stats['success']}")
    logging.info(f"Already extracted: {stats['skipped_exists']}")
    logging.info(f"Failed:            {stats['failed']}")
    logging.info(f"Errors:            {stats['errors']}")
    
    if TRIAL_BATCH_CONFIG['ENABLED']:
        logging.info(f"\n✓ Trial batch mode was ENABLED")
        logging.info(f"  Processed {len(pdf_files)} out of {len(all_pdf_files)} total PDFs")
    
    logging.info("="*70)

if __name__ == "__main__":
    process_all_pdfs()
