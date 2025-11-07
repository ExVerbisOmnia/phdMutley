#!/usr/bin/env python3
"""
PDF Text Extraction Script for Climate Litigation Database
===========================================================
Extracts text from downloaded PDF files and populates the PostgreSQL database.

📁 Run from: /home/gusrodgs/Gus/cienciaDeDados/phdMutley
Command: python scripts/phase1/extract_text.py

This script implements hierarchical PDF extraction using:
1. pdfplumber (primary - best quality)
2. PyMuPDF (fallback - fast and reliable)
3. PyPDF2 (last resort - most compatible)

The script also detects scanned PDFs and assesses extraction quality.
"""

import os
import sys
from pathlib import Path
import logging
from datetime import datetime
import json

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
PDF_FOLDER_PATH = 'pdfs/first_processing_batch'

# Path to the Excel database (needed to map case_id to case data)
DATABASE_FILE = 'baseCompleta.xlsx'

# Test mode configuration
TEST_MODE = False  # Set to False to process all PDFs
TEST_N_FILES = 10  # Number of files to process in test mode

# Quality assessment thresholds
# These help determine if text extraction was successful
MIN_WORDS_PER_PAGE = 10  # Fewer words suggests scanned PDF
SCANNED_PDF_THRESHOLD = 100  # Total words below this = likely scanned
MIN_AVG_WORD_LENGTH = 2  # Very short words suggest extraction problems
MAX_AVG_WORD_LENGTH = 20  # Very long "words" suggest extraction problems

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
# We need these to interact with the database tables
try:
    # Assuming the init_database script is in scripts/phase0/
    sys.path.insert(0, 'scripts/phase0')
    from init_database_pg18 import Case, Document, ExtractedText, Base
    logging.info("✓ Database models imported successfully")
except Exception as e:
    logging.error(f"✗ Failed to import database models: {e}")
    logging.error("   Make sure init_database_pg18.py is in scripts/phase0/")
    sys.exit(1)

# ============================================================================
# PDF TEXT EXTRACTION FUNCTIONS
# ============================================================================

def extract_text_pdfplumber(pdf_path):
    """
    Extract text from PDF using pdfplumber (primary method).
    
    pdfplumber is the most accurate but can be slower.
    Best for: complex layouts, tables, multi-column text
    
    Args:
        pdf_path (Path): Path to the PDF file
        
    Returns:
        dict: Dictionary with keys:
              - 'text': Extracted text as string
              - 'page_count': Number of pages
              - 'success': True if extraction succeeded
              - 'error': Error message if extraction failed
    """
    try:
        # Open the PDF file
        with pdfplumber.open(pdf_path) as pdf:
            text_parts = []
            
            # Extract text from each page
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            
            # Combine all pages into one text string
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
    """
    Extract text from PDF using PyMuPDF/fitz (fallback method).
    
    PyMuPDF is faster than pdfplumber and handles most PDFs well.
    Best for: simple layouts, single-column text
    
    Args:
        pdf_path (Path): Path to the PDF file
        
    Returns:
        dict: Dictionary with extraction results (same structure as pdfplumber)
    """
    try:
        # Open the PDF file
        doc = fitz.open(pdf_path)
        text_parts = []
        
        # Extract text from each page
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_text = page.get_text()
            if page_text:
                text_parts.append(page_text)
        
        # Combine all pages
        full_text = '\n\n'.join(text_parts)
        page_count = len(doc)
        
        # Close the document
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
    """
    Extract text from PDF using PyPDF2 (last resort method).
    
    PyPDF2 is the most compatible but often produces lower quality text.
    Best for: PDFs that fail with other methods
    
    Args:
        pdf_path (Path): Path to the PDF file
        
    Returns:
        dict: Dictionary with extraction results (same structure as pdfplumber)
    """
    try:
        text_parts = []
        
        # Open the PDF file
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            page_count = len(reader.pages)
            
            # Extract text from each page
            for page_num in range(page_count):
                page = reader.pages[page_num]
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        
        # Combine all pages
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
    
    This function tries extraction methods in order of quality:
    1. pdfplumber (best quality)
    2. PyMuPDF (good quality, faster)
    3. PyPDF2 (most compatible)
    
    Args:
        pdf_path (Path): Path to the PDF file
        
    Returns:
        dict: Dictionary with keys:
              - 'text': Extracted text
              - 'page_count': Number of pages
              - 'method_used': Which extraction method succeeded
              - 'success': True if any method succeeded
              - 'errors': List of errors from failed methods
    """
    # List to track errors from each method
    errors = []
    
    # Try pdfplumber first (best quality)
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
    """
    Assess the quality of extracted text.
    
    This function evaluates text extraction quality using several heuristics:
    - Word count (too few words suggests scanned PDF or failure)
    - Average word length (abnormal lengths suggest extraction problems)
    - Words per page (low ratio suggests scanned PDF)
    
    Args:
        text (str): The extracted text to assess
        page_count (int): Number of pages in the document
        
    Returns:
        dict: Dictionary with keys:
              - 'quality': Quality rating ('excellent', 'good', 'fair', 'poor', 'failed')
              - 'is_scanned': True if document appears to be scanned
              - 'word_count': Total number of words
              - 'character_count': Total number of characters
              - 'avg_word_length': Average length of words
              - 'words_per_page': Average words per page
              - 'notes': List of quality issues detected
    """
    notes = []
    
    # Basic text statistics
    words = text.split() if text else []
    word_count = len(words)
    character_count = len(text)
    
    # Calculate average word length
    if word_count > 0:
        avg_word_length = character_count / word_count
    else:
        avg_word_length = 0
    
    # Calculate words per page
    if page_count > 0:
        words_per_page = word_count / page_count
    else:
        words_per_page = 0
    
    # Detect scanned PDFs
    # Heuristic: if a 10+ page document has very few words, it's probably scanned
    is_scanned = False
    if page_count >= 10 and word_count < SCANNED_PDF_THRESHOLD:
        is_scanned = True
        notes.append(f"Likely scanned PDF: only {word_count} words for {page_count} pages")
    elif words_per_page < MIN_WORDS_PER_PAGE:
        is_scanned = True
        notes.append(f"Very low word density: {words_per_page:.1f} words/page")
    
    # Assess quality based on various factors
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
    """
    Extract metadata from PDF file (file size, etc.).
    
    Args:
        pdf_path (Path): Path to the PDF file
        
    Returns:
        dict: Dictionary with metadata including file_size_bytes
    """
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
# DATABASE POPULATION FUNCTIONS
# ============================================================================

def extract_case_id_from_filename(filename):
    """
    Extract the case ID from a PDF filename.
    
    Filenames follow the pattern: "case_{case_id}.pdf"
    Example: "case_BR-2021-1234.pdf" → "BR-2021-1234"
    
    Args:
        filename (str): Name of the PDF file
        
    Returns:
        str: Extracted case ID, or None if pattern doesn't match
    """
    # Remove "case_" prefix and ".pdf" suffix
    if filename.startswith('case_') and filename.endswith('.pdf'):
        return filename[5:-4]  # Extract middle part
    return None


def get_or_create_case(session, case_id_str, case_data_df):
    """
    Get an existing case from database or create a new one.
    
    Args:
        session: SQLAlchemy session
        case_id_str (str): Case ID as string (from filename)
        case_data_df (DataFrame): DataFrame with case data from baseCompleta.xlsx
        
    Returns:
        Case: Case object (existing or newly created)
    """
    # Try to find the case in the DataFrame
    case_row = case_data_df[case_data_df['Case ID'] == case_id_str]
    
    if case_row.empty:
        logging.warning(f"Case ID '{case_id_str}' not found in database. Creating minimal entry.")
        # Create a minimal case entry
        case = Case(
            case_name=f"Case {case_id_str}",
            court_name="Unknown",
            country="Unknown",
            region="Unknown"
        )
        session.add(case)
        session.flush()  # Get the UUID assigned to this case
        return case
    
    # Extract case data from DataFrame
    row = case_row.iloc[0]
    
    # Check if case already exists in database
    # Note: We need to query by case_name since we don't have the UUID yet
    existing_case = session.query(Case).filter(
        Case.case_name == str(row.get('Case Name', case_id_str))
    ).first()
    
    if existing_case:
        return existing_case
    
    # Create new case with data from Excel
    case = Case(
        case_name=str(row.get('Case Name', case_id_str)),
        court_name=str(row.get('Court', 'Unknown')),
        country=str(row.get('Geography ISOs', 'Unknown')),
        region=str(row.get('Region', 'Unknown')),
        case_url=str(row.get('Document Content URL', '')),
        data_source='climatecasechart.com'
    )
    
    session.add(case)
    session.flush()  # Get the UUID assigned to this case
    
    return case


def process_single_pdf(pdf_path, session, case_data_df):
    """
    Process a single PDF file: extract text and save to database.
    
    This is the main processing function that:
    1. Extracts text from the PDF
    2. Assesses text quality
    3. Creates/updates database records
    
    Args:
        pdf_path (Path): Path to the PDF file
        session: SQLAlchemy database session
        case_data_df (DataFrame): DataFrame with case data from Excel
        
    Returns:
        dict: Processing results with success status and statistics
    """
    try:
        # Extract case ID from filename
        case_id_str = extract_case_id_from_filename(pdf_path.name)
        if not case_id_str:
            return {
                'success': False,
                'error': 'Invalid filename format',
                'filename': pdf_path.name
            }
        
        # Get or create the case in the database
        case = get_or_create_case(session, case_id_str, case_data_df)
        
        # Get PDF metadata (file size, etc.)
        metadata = get_pdf_metadata(pdf_path)
        
        # Check if document already exists for this case
        existing_doc = session.query(Document).filter(
            Document.case_id == case.case_id,
            Document.pdf_file_path == str(pdf_path)
        ).first()
        
        if existing_doc:
            logging.info(f"Document already processed: {pdf_path.name}")
            return {
                'success': True,
                'skipped': True,
                'filename': pdf_path.name
            }
        
        # Extract text using hierarchical approach
        extraction_result = extract_text_hierarchical(pdf_path)
        
        if not extraction_result['success']:
            # Extraction failed with all methods
            # Still create document record to track the failure
            doc = Document(
                case_id=case.case_id,
                document_type='Decision',
                pdf_file_path=str(pdf_path),
                file_size_bytes=metadata.get('file_size_bytes'),
                page_count=0,
                pdf_downloaded=True,
                download_date=datetime.now(),
                download_error='; '.join(extraction_result['errors'])
            )
            session.add(doc)
            session.commit()
            
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
        
        # Create document record
        doc = Document(
            case_id=case.case_id,
            document_type='Decision',
            pdf_file_path=str(pdf_path),
            file_size_bytes=metadata.get('file_size_bytes'),
            page_count=extraction_result['page_count'],
            pdf_downloaded=True,
            download_date=datetime.now()
        )
        session.add(doc)
        session.flush()  # Get the UUID assigned to this document
        
        # Create extracted text record
        extracted_text = ExtractedText(
            document_id=doc.document_id,
            raw_text=extraction_result['text'],
            processed_text=extraction_result['text'],  # TODO: Add preprocessing later
            word_count=quality_assessment['word_count'],
            character_count=quality_assessment['character_count'],
            extraction_date=datetime.now(),
            extraction_method=extraction_result['method_used'],
            extraction_quality=quality_assessment['quality'],
            extraction_notes='; '.join(quality_assessment['notes']) if quality_assessment['notes'] else None
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
        logging.error(f"Error processing {pdf_path.name}: {e}")
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
    1. Loads the case data from Excel
    2. Gets the list of PDF files to process
    3. Processes each PDF with progress tracking
    4. Generates summary statistics
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
    
    # Load case data from Excel
    logging.info("Loading case data from Excel...")
    try:
        case_data_df = pd.read_excel(DATABASE_FILE)
        logging.info(f"✓ Loaded {len(case_data_df)} cases from database")
    except Exception as e:
        logging.error(f"✗ Failed to load Excel database: {e}")
        return
    
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
            result = process_single_pdf(pdf_path, session, case_data_df)
            
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
    """
    Print a comprehensive summary of the processing results.
    
    Args:
        stats (dict): Dictionary with processing statistics
    """
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
            percentage = (count / stats['successful']) * 100
            logging.info(f"  {method:15s} : {count:4d} ({percentage:5.1f}%)")
    
    if stats['by_quality']:
        logging.info("\nExtraction quality distribution:")
        for quality, count in sorted(stats['by_quality'].items()):
            percentage = (count / stats['successful']) * 100
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
    python extract_text.py
    """
    
    logging.info("="*70)
    logging.info("PDF TEXT EXTRACTION - CLIMATE LITIGATION DATABASE")
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
