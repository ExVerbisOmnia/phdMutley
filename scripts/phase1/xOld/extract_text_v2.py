#!/usr/bin/env python3
"""
PDF Text Extraction Script for Climate Litigation Database (Version 2.0)
==========================================================================
Extracts text from downloaded PDF files and populates the PostgreSQL database.
Uses Document ID matching with deterministic UUIDs for robust linking.

📁 Run from: /home/gusrodgs/Gus/cienciaDeDados/phdMutley
Command: python scripts/phase1/extract_text_v2.py

This script implements hierarchical PDF extraction using:
1. pdfplumber (primary - best quality)
2. PyMuPDF (fallback - fast and reliable)
3. PyPDF2 (last resort - most compatible)

KEY CHANGES FROM V1:
- Matches PDFs by Document ID (not Case ID)
- Uses deterministic UUIDs (same as populate_metadata.py)
- Queries existing documents table instead of creating new records
- More robust matching logic
"""

import os
import sys
from pathlib import Path
import logging
from datetime import datetime
import json
from uuid import uuid5, NAMESPACE_DNS

# PDF extraction libraries (hierarchical fallback approach)
import pdfplumber  # Primary method - excellent quality
import fitz  # PyMuPDF - fast fallback
import PyPDF2  # Last resort - most compatible

# Database libraries
from sqlalchemy import create_engine, text as sql_text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import URL
from dotenv import load_dotenv
import pandas as pd

# Progress bar for visual feedback
from tqdm import tqdm

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

# Configure logging to track extraction progress and errors
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/extraction_log.txt'),  # Save logs to file
        logging.StreamHandler()  # Also display in terminal
    ]
)

# ============================================================================
# CONFIGURATION SECTION
# ============================================================================

# Path to the folder containing PDF files to be processed
# This should match the BASE_OUTPUT_DIR from download_decisions_v2.py
PDF_FOLDER_PATH = '/home/gusrodgs/Gus/cienciaDeDados/phdMutley/scripts/phase1/pdfs/downloaded'

# Path to the Excel database (needed to map document_id to document data)
DATABASE_FILE = '/home/gusrodgs/Gus/cienciaDeDados/phdMutley/baseDecisions.xlsx'

# Test mode configuration
TEST_MODE = True  # Set to False to process all PDFs
TEST_N_FILES = 15  # Number of files to process in test mode

# Quality assessment thresholds
# These help determine if text extraction was successful
MIN_WORDS_PER_PAGE = 10  # Fewer words suggests scanned PDF
SCANNED_PDF_THRESHOLD = 100  # Total words below this = likely scanned
MIN_AVG_WORD_LENGTH = 2  # Very short words suggest extraction problems
MAX_AVG_WORD_LENGTH = 20  # Very long "words" suggest extraction problems

# UUID generation namespace (MUST match populate_metadata.py)
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

# Import database models (from init_database script)
try:
    # Check if we're in the correct directory
    if not os.path.exists('baseDecisions.xlsx'):
        raise FileNotFoundError(
            "baseDecisions.xlsx not found. You must run this script from the project root:\n"
            "   cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley\n"
            "   python scripts/phase1/extract_text_v2.py"
        )

    # Add the scripts/phase0 directory to Python path
    sys.path.insert(0, os.path.join(os.getcwd(), 'scripts', 'phase0'))

    # Import database models
    from init_database_pg18 import Case, Document, ExtractedText, Base
    logging.info("✓ Database models imported successfully")
except FileNotFoundError as e:
    logging.error(f"✗ Wrong directory: {e}")
    sys.exit(1)
except ImportError as e:
    logging.error(f"✗ Failed to import database models: {e}")
    sys.exit(1)
except Exception as e:
    logging.error(f"✗ Unexpected error: {e}")
    sys.exit(1)

# ============================================================================
# UUID GENERATION FUNCTIONS (MUST MATCH populate_metadata.py)
# ============================================================================

def generate_document_uuid(document_id_str):
    """
    Generate deterministic UUID for a document.

    IMPORTANT: This MUST match the implementation in populate_metadata.py

    Args:
        document_id_str (str): Original Document ID from Excel

    Returns:
        UUID: Deterministic UUID object
    """
    clean_id = str(document_id_str).strip().lower()
    return uuid5(UUID_NAMESPACE, f"document_{clean_id}")

# ============================================================================
# PDF TEXT EXTRACTION FUNCTIONS
# ============================================================================

def extract_text_pdfplumber(pdf_path):
    """Extract text from PDF using pdfplumber (primary method)."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text_parts = []
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

            full_text = '\n\n'.join(text_parts)

            return {
                'text': full_text,
                'page_count': len(pdf.pages),
                'success': True,
                'error': None
            }
    except Exception as e:
        return {
            'text': '',
            'page_count': 0,
            'success': False,
            'error': str(e)
        }


def extract_text_pymupdf(pdf_path):
    """Extract text from PDF using PyMuPDF/fitz (fallback method)."""
    try:
        doc = fitz.open(pdf_path)
        text_parts = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            page_text = page.get_text()
            if page_text:
                text_parts.append(page_text)

        full_text = '\n\n'.join(text_parts)
        page_count = len(doc)
        doc.close()

        return {
            'text': full_text,
            'page_count': page_count,
            'success': True,
            'error': None
        }
    except Exception as e:
        return {
            'text': '',
            'page_count': 0,
            'success': False,
            'error': str(e)
        }


def extract_text_pypdf2(pdf_path):
    """Extract text from PDF using PyPDF2 (last resort method)."""
    try:
        text_parts = []

        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            page_count = len(reader.pages)

            for page_num in range(page_count):
                page = reader.pages[page_num]
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

        full_text = '\n\n'.join(text_parts)

        return {
            'text': full_text,
            'page_count': page_count,
            'success': True,
            'error': None
        }
    except Exception as e:
        return {
            'text': '',
            'page_count': 0,
            'success': False,
            'error': str(e)
        }


def extract_text_hierarchical(pdf_path):
    """
    Extract text using hierarchical fallback approach.

    Tries methods in order of quality:
    1. pdfplumber (best quality)
    2. PyMuPDF (good quality, faster)
    3. PyPDF2 (most compatible)
    """
    errors = []

    # Try pdfplumber first
    logging.debug(f"Attempting pdfplumber extraction: {pdf_path.name}")
    result = extract_text_pdfplumber(pdf_path)
    if result['success'] and result['text'].strip():
        result['method_used'] = 'pdfplumber'
        result['errors'] = []
        return result
    else:
        errors.append(f"pdfplumber: {result['error']}")

    # Try PyMuPDF as fallback
    logging.debug(f"pdfplumber failed, trying PyMuPDF: {pdf_path.name}")
    result = extract_text_pymupdf(pdf_path)
    if result['success'] and result['text'].strip():
        result['method_used'] = 'PyMuPDF'
        result['errors'] = errors
        return result
    else:
        errors.append(f"PyMuPDF: {result['error']}")

    # Try PyPDF2 as last resort
    logging.debug(f"PyMuPDF failed, trying PyPDF2: {pdf_path.name}")
    result = extract_text_pypdf2(pdf_path)
    if result['success'] and result['text'].strip():
        result['method_used'] = 'PyPDF2'
        result['errors'] = errors
        return result
    else:
        errors.append(f"PyPDF2: {result['error']}")

    # All methods failed
    return {
        'text': '',
        'page_count': 0,
        'method_used': None,
        'success': False,
        'errors': errors
    }


def assess_text_quality(text, page_count):
    """Assess the quality of extracted text."""
    notes = []

    words = text.split() if text else []
    word_count = len(words)
    character_count = len(text)

    if word_count > 0:
        avg_word_length = character_count / word_count
    else:
        avg_word_length = 0

    if page_count > 0:
        words_per_page = word_count / page_count
    else:
        words_per_page = 0

    # Detect scanned PDFs
    is_scanned = False
    if page_count >= 10 and word_count < SCANNED_PDF_THRESHOLD:
        is_scanned = True
        notes.append(f"Likely scanned PDF: only {word_count} words for {page_count} pages")
    elif words_per_page < MIN_WORDS_PER_PAGE:
        is_scanned = True
        notes.append(f"Very low word density: {words_per_page:.1f} words/page")

    # Assess quality
    if word_count == 0:
        quality = 'failed'
        notes.append("No text extracted")
    elif is_scanned:
        quality = 'poor'
    elif avg_word_length < MIN_AVG_WORD_LENGTH or avg_word_length > MAX_AVG_WORD_LENGTH:
        quality = 'fair'
        notes.append(f"Unusual average word length: {avg_word_length:.1f} characters")
    elif words_per_page < 50:
        quality = 'fair'
        notes.append(f"Low text density: {words_per_page:.1f} words/page")
    elif words_per_page > 500:
        quality = 'good'
        notes.append(f"High text density: {words_per_page:.1f} words/page")
    else:
        quality = 'excellent'

    return {
        'quality': quality,
        'is_scanned': is_scanned,
        'word_count': word_count,
        'character_count': character_count,
        'avg_word_length': round(avg_word_length, 2),
        'words_per_page': round(words_per_page, 1),
        'notes': notes
    }


def get_pdf_metadata(pdf_path):
    """Extract metadata from PDF file (file size, etc.)."""
    try:
        file_stats = pdf_path.stat()
        return {
            'file_size_bytes': file_stats.st_size,
            'file_modified': datetime.fromtimestamp(file_stats.st_mtime)
        }
    except Exception as e:
        logging.warning(f"Could not get metadata for {pdf_path.name}: {e}")
        return {
            'file_size_bytes': None,
            'file_modified': None
        }


# ============================================================================
# DATABASE MATCHING FUNCTIONS
# ============================================================================

def extract_document_id_from_filename(filename):
    """
    Extract the document ID from a PDF filename.

    Filenames follow the pattern: "doc_{document_id}.pdf"
    Example: "doc_12345.pdf" → "12345"

    Args:
        filename (str): Name of the PDF file

    Returns:
        str: Extracted document ID, or None if pattern doesn't match
    """
    # Remove "doc_" prefix and ".pdf" suffix
    if filename.startswith('doc_') and filename.endswith('.pdf'):
        return filename[4:-4]  # Extract middle part

    return None


def find_document_in_database(session, document_id_str):
    """
    Find an existing document in the database using deterministic UUID.

    This function uses the same UUID generation logic as populate_metadata.py
    to ensure we find the document that was created during metadata population.

    Args:
        session: SQLAlchemy session
        document_id_str (str): Document ID from filename

    Returns:
        Document: Document object if found, None otherwise
    """
    # Generate deterministic UUID (same as populate_metadata.py)
    document_uuid = generate_document_uuid(document_id_str)

    # Query document by UUID
    document = session.query(Document).filter(
        Document.document_id == document_uuid
    ).first()

    return document


def process_single_pdf(pdf_path, session, stats_dict):
    """
    Process a single PDF file: extract text and save to database.

    NEW LOGIC:
    1. Extract document_id from filename
    2. Find existing document record using deterministic UUID
    3. Check if text already extracted
    4. Extract text from PDF
    5. Create extracted_text record linked to document

    Args:
        pdf_path (Path): Path to the PDF file
        session: SQLAlchemy database session
        stats_dict (dict): Dictionary to track statistics

    Returns:
        dict: Processing results with success status and statistics
    """
    try:
        # Extract document ID from filename
        document_id_str = extract_document_id_from_filename(pdf_path.name)
        if not document_id_str:
            logging.warning(f"Skipping {pdf_path.name}: Invalid filename format (expected 'doc_XXXXX.pdf')")
            return {
                'success': False,
                'error': 'Invalid filename format',
                'filename': pdf_path.name
            }

        # Find document in database
        document = find_document_in_database(session, document_id_str)

        if not document:
            logging.warning(f"Skipping {pdf_path.name}: Document ID '{document_id_str}' not found in database")
            return {
                'success': False,
                'error': 'Document not found in database',
                'filename': pdf_path.name
            }

        # Check if text already extracted for this document
        existing_text = session.query(ExtractedText).filter(
            ExtractedText.document_id == document.document_id
        ).first()

        if existing_text:
            logging.info(f"Skipping {pdf_path.name}: Text already extracted")
            return {
                'success': True,
                'skipped': True,
                'filename': pdf_path.name
            }

        # Extract text using hierarchical approach
        extraction_result = extract_text_hierarchical(pdf_path)

        if not extraction_result['success']:
            # Log extraction failure but don't crash
            logging.error(f"Failed to extract text from {pdf_path.name}: {extraction_result['errors']}")
            return {
                'success': False,
                'error': 'All extraction methods failed',
                'details': extraction_result['errors'],
                'filename': pdf_path.name
            }

        # Assess text quality
        quality_assessment = assess_text_quality(
            extraction_result['text'],
            extraction_result['page_count']
        )

        # Update document record with extraction info
        document.page_count = extraction_result['page_count']
        document.pdf_file_path = str(pdf_path)
        document.pdf_downloaded = True
        document.download_date = datetime.now()
        document.file_size_bytes = get_pdf_metadata(pdf_path).get('file_size_bytes')

        # Create extracted text record
        extracted_text = ExtractedText(
            document_id=document.document_id,
            raw_text=extraction_result['text'],
            processed_text=extraction_result['text'],  # TODO: Add preprocessing later
            word_count=quality_assessment['word_count'],
            character_count=quality_assessment['character_count'],
            extraction_date=datetime.now(),
            extraction_method=extraction_result['method_used'],
            extraction_quality=quality_assessment['quality'],
            extraction_notes='; '.join(quality_assessment['notes']) if quality_assessment['notes'] else None,
            language_detected=None  # TODO: Add language detection
        )
        session.add(extracted_text)

        # Commit the transaction
        session.commit()

        logging.info(
            f"✓ Processed {pdf_path.name}: "
            f"{quality_assessment['word_count']} words, "
            f"{extraction_result['page_count']} pages, "
            f"quality: {quality_assessment['quality']}, "
            f"method: {extraction_result['method_used']}"
        )

        return {
            'success': True,
            'filename': pdf_path.name,
            'method': extraction_result['method_used'],
            'quality': quality_assessment['quality'],
            'word_count': quality_assessment['word_count'],
            'page_count': extraction_result['page_count'],
            'is_scanned': quality_assessment['is_scanned']
        }

    except Exception as e:
        # Roll back transaction on error
        session.rollback()
        logging.error(f"Error processing {pdf_path.name}: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'filename': pdf_path.name
        }


# ============================================================================
# MAIN PROCESSING FUNCTION
# ============================================================================

def process_all_pdfs():
    """
    Main function to process all PDFs in the folder.

    This function:
    1. Gets the list of PDF files to process
    2. Processes each PDF with progress tracking
    3. Generates summary statistics
    """
    # Initialize statistics
    stats = {
        'total_files': 0,
        'successful': 0,
        'failed': 0,
        'skipped': 0,
        'by_method': {},
        'by_quality': {},
        'scanned_pdfs': 0
    }

    # Get list of PDF files
    pdf_folder = Path(PDF_FOLDER_PATH)
    if not pdf_folder.exists():
        logging.error(f"PDF folder not found: {PDF_FOLDER_PATH}")
        return

    pdf_files = list(pdf_folder.glob('*.pdf'))

    # Apply test mode if enabled
    if TEST_MODE:
        pdf_files = pdf_files[:TEST_N_FILES]
        logging.info(f"\n⚠️  TEST MODE: Processing only {len(pdf_files)} files")

    stats['total_files'] = len(pdf_files)
    logging.info(f"\nFound {len(pdf_files)} PDF files to process\n")

    # Create database session
    session = SessionLocal()

    try:
        # Process each PDF with progress bar
        for pdf_path in tqdm(pdf_files, desc="Extracting text"):
            result = process_single_pdf(pdf_path, session, stats)

            if result.get('skipped'):
                stats['skipped'] += 1
            elif result['success']:
                stats['successful'] += 1

                # Track statistics
                method = result.get('method', 'unknown')
                quality = result.get('quality', 'unknown')

                stats['by_method'][method] = stats['by_method'].get(method, 0) + 1
                stats['by_quality'][quality] = stats['by_quality'].get(quality, 0) + 1

                if result.get('is_scanned'):
                    stats['scanned_pdfs'] += 1
            else:
                stats['failed'] += 1

    finally:
        # Always close the session
        session.close()

    # Print summary
    print_processing_summary(stats)


def print_processing_summary(stats):
    """Print a comprehensive summary of the processing results."""
    logging.info("\n" + "="*70)
    logging.info("TEXT EXTRACTION SUMMARY")
    logging.info("="*70)
    logging.info(f"Total files:              {stats['total_files']}")
    logging.info(f"Successfully processed:   {stats['successful']}")
    logging.info(f"Failed:                   {stats['failed']}")
    logging.info(f"Skipped (already done):   {stats['skipped']}")
    logging.info(f"Scanned PDFs detected:    {stats['scanned_pdfs']}")

    if stats['by_method']:
        logging.info("\nExtraction methods used:")
        for method, count in sorted(stats['by_method'].items()):
            percentage = (count / stats['successful']) * 100 if stats['successful'] > 0 else 0
            logging.info(f"  {method:15s} : {count:4d} ({percentage:5.1f}%)")

    if stats['by_quality']:
        logging.info("\nExtraction quality distribution:")
        for quality, count in sorted(stats['by_quality'].items()):
            percentage = (count / stats['successful']) * 100 if stats['successful'] > 0 else 0
            logging.info(f"  {quality:15s} : {count:4d} ({percentage:5.1f}%)")

    # Calculate success rate
    if stats['total_files'] > 0:
        success_rate = (stats['successful'] / stats['total_files']) * 100
        logging.info(f"\nOverall success rate:     {success_rate:.1f}%")

    logging.info("="*70)


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    """
    This block runs when you execute the script directly:
    python extract_text_v2.py
    """

    logging.info("="*70)
    logging.info("PDF TEXT EXTRACTION - CLIMATE LITIGATION DATABASE (V2.0)")
    logging.info("="*70)
    logging.info(f"PDF folder: {PDF_FOLDER_PATH}")
    logging.info(f"Database: {DB_CONFIG['database']}")

    if TEST_MODE:
        logging.info(f"\n⚠️  TEST MODE: Processing only {TEST_N_FILES} files")
    else:
        logging.info("\n✅ FULL MODE: Processing all PDF files")

    logging.info("="*70 + "\n")

    # Create logs directory if needed
    Path('logs').mkdir(exist_ok=True)

    # Run the extraction process
    process_all_pdfs()

    if TEST_MODE:
        logging.info("\n⚠️  TEST MODE was enabled. To process all files:")
        logging.info("   Set TEST_MODE = False in the configuration section")

    logging.info("\nText extraction completed!")
