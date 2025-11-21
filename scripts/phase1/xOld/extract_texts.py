#!/usr/bin/env python3
"""
PDF Text Extraction Script (Memory Safe Version)
================================================
Optimized for systems with limited RAM (8GB).
Caps concurrency and enforces garbage collection.

📁 Run from: /home/gusrodgs/Gus/cienciaDeDados/phdMutley
Command: python scripts/phase1/extract_texts.py
"""

import sys
import os
import logging
import concurrent.futures
import gc  # Garbage Collector
from pathlib import Path
from datetime import datetime
from uuid import uuid5
from tqdm import tqdm

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
from config import CONFIG, DB_CONFIG, PDF_DOWNLOAD_DIR, UUID_NAMESPACE, LOGS_DIR, TEST_CONFIG

# Import database models
sys.path.insert(0, os.path.join('/home/gusrodgs/Gus/cienciaDeDados/phdMutley', 'scripts', 'phase0'))
from init_database import Document, ExtractedText, Base

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

# Force logging to write immediately to disk
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

# CRITICAL: Override Max Workers for 8GB RAM
# We limit this to 2 workers. It is slower, but it will not crash your machine.
SAFE_WORKERS = 2 

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def generate_document_uuid(document_id_str):
    clean_id = str(document_id_str).strip().lower()
    return uuid5(UUID_NAMESPACE, f"document_{clean_id}")

def extract_document_id_from_filename(filename):
    if filename.startswith('doc_') and filename.endswith('.pdf'):
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
                # Extract text and immediately discard page object references
                txt = p.extract_text() or ""
                text_parts.append(txt)
                
            full_text = '\n\n'.join(text_parts)
            # Explicitly delete large list
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
            # Record failure
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
        local_engine.dispose() # Close connection pool
        
        # Clear local variables to help ref counting
        del document
        if 'extracted' in locals(): del extracted
        if 'extraction_result' in locals(): del extraction_result
        
        # Force Garbage Collection
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

    pdf_files = list(PDF_DOWNLOAD_DIR.glob('*.pdf'))
    
    # Apply Test Mode based on Config
    if TEST_CONFIG['ENABLED']:
        limit = TEST_CONFIG['LIMIT']
        logging.info(f"⚠️  TEST MODE: Processing first {limit} files.")
        pdf_files = pdf_files[:limit]

    logging.info(f"Found {len(pdf_files)} files to process.")

    stats = {
        'success': 0, 'failed': 0, 'skipped_exists': 0, 
        'skipped_invalid': 0, 'errors': 0
    }
    
    # Use limited workers
    with concurrent.futures.ProcessPoolExecutor(max_workers=SAFE_WORKERS) as executor:
        path_strings = [str(p) for p in pdf_files]
        
        # Process
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
    logging.info(f"Successful:        {stats['success']}")
    logging.info(f"Already extracted: {stats['skipped_exists']}")
    logging.info(f"Failed:            {stats['failed']}")
    logging.info(f"Errors:            {stats['errors']}")
    logging.info("="*70)

if __name__ == "__main__":
    process_all_pdfs()