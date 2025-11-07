"""
Climate Litigation PDF Text Extraction Script - Phase 1 (Updated)
==================================================================

📁 PROJECT DIRECTORY: /home/gusrodgs/Gus/cienciaDeDados/phdMutley

🔹 Run from: /home/gusrodgs/Gus/cienciaDeDados/phdMutley

COMMANDS TO RUN THIS SCRIPT:
----------------------------
cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley
source venv/bin/activate

# Default run (uses PDFS_FOLDER_PATH global variable):
python scripts/phase1/extract_pdf_text.py

# Override with custom path:
python scripts/phase1/extract_pdf_text.py --pdf-dir pdfs/other_folder

# Test mode with limit:
python scripts/phase1/extract_pdf_text.py --test --limit 15

IMPORTANT: This script now accepts TWO filename patterns:
1. ID_XXXX_filename.pdf (for manual test files, e.g., ID_0001_test.pdf)
2. decision-CaseID.pdf (for production files, e.g., decision-BR-2020-1234.pdf)

The script automatically extracts the identifier and generates a deterministic UUID.

Author: Gustavo
Project: Doutorado PM - Global South Climate Litigation Analysis
Version: 2.0 - Flexible ID extraction
Date: November 2025
"""

# =============================================================================
# IMPORTS
# =============================================================================

import os
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple, Optional, List
import json
import time
import re

# PDF extraction libraries (hierarchical preference)
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    print("⚠ pdfplumber not available")

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    print("⚠ PyMuPDF not available")

try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False
    print("⚠ PyPDF2 not available")

# Database imports
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import URL
from dotenv import load_dotenv
import uuid

# =============================================================================
# ⚙️ GLOBAL CONFIGURATION - EDIT THIS PATH FOR YOUR PDFS
# =============================================================================

# 📁 Path to folder containing PDFs to extract
# EDIT THIS VARIABLE to point to your PDF folder
# This path is relative to the project root directory
PDFS_FOLDER_PATH = "/home/gusrodgs/Gus/cienciaDeDados/phdMutley/pdfs/first_processing_batch"

# Alternative: You can use an absolute path
# PDFS_FOLDER_PATH = "/home/gusrodgs/Gus/cienciaDeDados/phdMutley/tests/extraction_test"

# UUID Namespace for deterministic UUID generation
# This is a fixed UUID that ensures the same identifier always generates the same UUID
PROJECT_UUID_NAMESPACE = uuid.UUID('a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d')

# =============================================================================
# CONFIGURATION
# =============================================================================

# Load environment variables
load_dotenv()

# Database connection parameters
DB_CONFIG = {
    'drivername': 'postgresql+psycopg2',
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'climate_litigation'),
    'username': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
}

# Extraction parameters
SCANNED_PDF_THRESHOLD = 50  # words per page - below this, PDF is considered scanned
MIN_CHARS_PER_PAGE = 1000   # typical legal documents have 2000-4000 chars/page
MAX_SPECIAL_CHAR_RATIO = 0.15  # if > 15% special chars, extraction may have failed
MIN_AVG_WORD_LENGTH = 3     # if avg word length < 3, text may be fragmented

# Library versions (for reproducibility)
LIBRARY_VERSIONS = {
    'pdfplumber': getattr(pdfplumber, '__version__', 'unknown') if PDFPLUMBER_AVAILABLE else 'not installed',
    'PyMuPDF': fitz.VersionBind if PYMUPDF_AVAILABLE else 'not installed',
    'PyPDF2': PyPDF2.__version__ if PYPDF2_AVAILABLE else 'not installed'
}

# =============================================================================
# LOGGING SETUP
# =============================================================================

def setup_logging(log_dir: Path = Path('logs'), test_mode: bool = False):
    """
    Configure logging for the extraction process
    
    Args:
        log_dir: Directory to store log files
        test_mode: If True, uses more verbose logging
    """
    # Create log directory if it doesn't exist
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create log filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    mode_prefix = 'test_' if test_mode else 'full_'
    log_file = log_dir / f'{mode_prefix}extraction_{timestamp}.log'
    
    # Configure logging format
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    log_level = logging.DEBUG if test_mode else logging.INFO
    
    # Setup logging to both file and console
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized. Log file: {log_file}")
    logger.info(f"Test mode: {test_mode}")
    logger.info(f"PDFs folder path: {PDFS_FOLDER_PATH}")
    logger.info(f"Library versions: {json.dumps(LIBRARY_VERSIONS, indent=2)}")
    
    return logger

# =============================================================================
# DATABASE CONNECTION
# =============================================================================

def create_db_session():
    """
    Create SQLAlchemy session for database operations
    
    Returns:
        session: SQLAlchemy session object
        engine: SQLAlchemy engine object
    """
    # Create database URL
    db_url = URL.create(**DB_CONFIG)
    
    # Create engine
    engine = create_engine(db_url, echo=False)
    
    # Create session factory
    Session = sessionmaker(bind=engine)
    session = Session()
    
    return session, engine

# =============================================================================
# FILE IDENTIFICATION AND UUID GENERATION
# =============================================================================

def extract_identifier_from_filename(filename: str) -> Optional[str]:
    """
    Extract identifier from PDF filename using multiple patterns
    
    This function supports two filename patterns:
    1. ID_XXXX_filename.pdf → extracts "XXXX" (for manual test files)
    2. decision-CaseID.pdf → extracts "CaseID" (for production files)
    
    Args:
        filename: Name of the PDF file
        
    Returns:
        str: Extracted identifier, or None if no pattern matches
        
    Examples:
        >>> extract_identifier_from_filename("ID_0001_silva_vs_brazil.pdf")
        "0001"
        
        >>> extract_identifier_from_filename("decision-BR-2020-1234.pdf")
        "BR-2020-1234"
        
        >>> extract_identifier_from_filename("random_file.pdf")
        None
    """
    # Pattern 1: ID_XXXX_rest.pdf (test files)
    # Matches: ID_0001_test.pdf, ID_0015_decision.pdf, etc.
    pattern1 = r'ID_(\d+)_'
    match1 = re.search(pattern1, filename)
    if match1:
        identifier = match1.group(1)
        return identifier
    
    # Pattern 2: decision-CaseID.pdf (production files)
    # Matches: decision-BR-2020-1234.pdf, decision-ABC123.pdf, etc.
    pattern2 = r'decision-([^\.]+)\.pdf'
    match2 = re.search(pattern2, filename, re.IGNORECASE)
    if match2:
        identifier = match2.group(1)
        return identifier
    
    # No pattern matched
    return None


def generate_deterministic_uuid(identifier: str) -> uuid.UUID:
    """
    Generate a deterministic UUID from an identifier
    
    This ensures that the same identifier always generates the same UUID,
    which is crucial for:
    - Checking if a document has already been processed
    - Maintaining consistency across multiple runs
    - Linking extracted text to source documents
    
    Uses UUID version 5 (SHA-1 hash) with a project-specific namespace.
    
    Args:
        identifier: The identifier extracted from the filename
        
    Returns:
        uuid.UUID: A deterministic UUID
        
    Example:
        >>> generate_deterministic_uuid("0001")
        UUID('...')  # Always the same UUID for "0001"
        
        >>> generate_deterministic_uuid("BR-2020-1234")
        UUID('...')  # Always the same UUID for "BR-2020-1234"
    """
    # Generate UUID using SHA-1 hash of namespace + identifier
    # This ensures reproducibility: same input → same UUID
    deterministic_uuid = uuid.uuid5(PROJECT_UUID_NAMESPACE, identifier)
    return deterministic_uuid


def identify_pdf_file(pdf_path: Path, logger) -> Optional[Tuple[str, uuid.UUID]]:
    """
    Identify a PDF file and generate its deterministic UUID
    
    This function:
    1. Extracts the identifier from the filename
    2. Generates a deterministic UUID
    3. Logs the identification process
    
    Args:
        pdf_path: Path to the PDF file
        logger: Logger instance
        
    Returns:
        tuple: (identifier, document_uuid) or None if identification fails
    """
    # Extract identifier from filename
    identifier = extract_identifier_from_filename(pdf_path.name)
    
    if identifier is None:
        logger.error(f"✗ Cannot extract identifier from filename: {pdf_path.name}")
        logger.error(f"  Expected patterns:")
        logger.error(f"    - ID_XXXX_filename.pdf (e.g., ID_0001_test.pdf)")
        logger.error(f"    - decision-CaseID.pdf (e.g., decision-BR-2020-1234.pdf)")
        return None
    
    # Generate deterministic UUID
    document_uuid = generate_deterministic_uuid(identifier)
    
    logger.debug(f"Identified: {pdf_path.name}")
    logger.debug(f"  Identifier: {identifier}")
    logger.debug(f"  UUID: {document_uuid}")
    
    return (identifier, document_uuid)

# =============================================================================
# PDF TEXT EXTRACTION FUNCTIONS
# =============================================================================

def extract_with_pdfplumber(pdf_path: Path) -> Dict:
    """
    Extract text using pdfplumber (highest quality, best for tables)
    
    pdfplumber provides the best quality extraction, especially for:
    - Documents with tables
    - Multi-column layouts
    - Complex formatting
    - Headers and footers
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        dict: {
            'text': extracted text,
            'page_count': number of pages,
            'method': 'pdfplumber',
            'success': True/False,
            'error': error message if failed,
            'extraction_time': time taken in seconds
        }
    """
    start_time = time.time()
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Extract text from all pages
            text_parts = []
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            
            # Join all pages with double newline separator
            full_text = '\n\n'.join(text_parts)
            page_count = len(pdf.pages)
            
            extraction_time = time.time() - start_time
            
            return {
                'text': full_text,
                'page_count': page_count,
                'method': 'pdfplumber',
                'success': True,
                'error': None,
                'extraction_time': extraction_time
            }
            
    except Exception as e:
        extraction_time = time.time() - start_time
        return {
            'text': '',
            'page_count': 0,
            'method': 'pdfplumber',
            'success': False,
            'error': str(e),
            'extraction_time': extraction_time
        }


def extract_with_pymupdf(pdf_path: Path) -> Dict:
    """
    Extract text using PyMuPDF (good balance of speed and quality)
    
    PyMuPDF is faster than pdfplumber and provides good quality extraction.
    Used as fallback when pdfplumber fails or is unavailable.
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        dict: Same structure as extract_with_pdfplumber
    """
    start_time = time.time()
    
    try:
        doc = fitz.open(pdf_path)
        
        # Extract text from all pages
        text_parts = []
        for page in doc:
            page_text = page.get_text()
            if page_text:
                text_parts.append(page_text)
        
        # Join all pages
        full_text = '\n\n'.join(text_parts)
        page_count = len(doc)
        
        doc.close()
        
        extraction_time = time.time() - start_time
        
        return {
            'text': full_text,
            'page_count': page_count,
            'method': 'PyMuPDF',
            'success': True,
            'error': None,
            'extraction_time': extraction_time
        }
        
    except Exception as e:
        extraction_time = time.time() - start_time
        return {
            'text': '',
            'page_count': 0,
            'method': 'PyMuPDF',
            'success': False,
            'error': str(e),
            'extraction_time': extraction_time
        }


def extract_with_pypdf2(pdf_path: Path) -> Dict:
    """
    Extract text using PyPDF2 (fastest, basic extraction)
    
    PyPDF2 is the fastest option but provides basic text extraction only.
    Used as last resort when other methods fail.
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        dict: Same structure as extract_with_pdfplumber
    """
    start_time = time.time()
    
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            # Extract text from all pages
            text_parts = []
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            
            # Join all pages
            full_text = '\n\n'.join(text_parts)
            page_count = len(pdf_reader.pages)
            
            extraction_time = time.time() - start_time
            
            return {
                'text': full_text,
                'page_count': page_count,
                'method': 'PyPDF2',
                'success': True,
                'error': None,
                'extraction_time': extraction_time
            }
            
    except Exception as e:
        extraction_time = time.time() - start_time
        return {
            'text': '',
            'page_count': 0,
            'method': 'PyPDF2',
            'success': False,
            'error': str(e),
            'extraction_time': extraction_time
        }


def extract_text_hierarchical(pdf_path: Path, logger) -> Dict:
    """
    Extract text using hierarchical approach: pdfplumber → PyMuPDF → PyPDF2
    
    This function tries extraction methods in order of quality, falling back
    to the next method if the current one fails or produces poor results.
    
    Args:
        pdf_path: Path to PDF file
        logger: Logger instance for logging operations
        
    Returns:
        dict: Extraction result with text and metadata
    """
    logger.info(f"Starting hierarchical extraction for: {pdf_path.name}")
    
    # Try pdfplumber first (best quality)
    if PDFPLUMBER_AVAILABLE:
        logger.debug("Attempting extraction with pdfplumber...")
        result = extract_with_pdfplumber(pdf_path)
        if result['success'] and len(result['text'].strip()) > 100:
            logger.info(f"✓ pdfplumber succeeded: {len(result['text'])} chars, "
                       f"{result['page_count']} pages, {result['extraction_time']:.2f}s")
            return result
        else:
            logger.warning(f"pdfplumber failed or produced minimal text: {result.get('error', 'unknown')}")
    
    # Fallback to PyMuPDF
    if PYMUPDF_AVAILABLE:
        logger.debug("Attempting extraction with PyMuPDF...")
        result = extract_with_pymupdf(pdf_path)
        if result['success'] and len(result['text'].strip()) > 100:
            logger.info(f"✓ PyMuPDF succeeded: {len(result['text'])} chars, "
                       f"{result['page_count']} pages, {result['extraction_time']:.2f}s")
            return result
        else:
            logger.warning(f"PyMuPDF failed or produced minimal text: {result.get('error', 'unknown')}")
    
    # Last resort: PyPDF2
    if PYPDF2_AVAILABLE:
        logger.debug("Attempting extraction with PyPDF2...")
        result = extract_with_pypdf2(pdf_path)
        if result['success']:
            logger.info(f"✓ PyPDF2 succeeded: {len(result['text'])} chars, "
                       f"{result['page_count']} pages, {result['extraction_time']:.2f}s")
            return result
        else:
            logger.warning(f"PyPDF2 failed: {result.get('error', 'unknown')}")
    
    # All methods failed
    logger.error(f"✗ All extraction methods failed for: {pdf_path.name}")
    return {
        'text': '',
        'page_count': 0,
        'method': 'none',
        'success': False,
        'error': 'All extraction methods failed',
        'extraction_time': 0
    }

# =============================================================================
# QUALITY ASSESSMENT FUNCTIONS
# =============================================================================

def detect_scanned_pdf(text: str, page_count: int) -> bool:
    """
    Detect if PDF is scanned (image-based) using word density heuristic
    
    Scanned PDFs contain images of text rather than actual text. They require
    OCR (Optical Character Recognition) to extract text. This function uses
    the heuristic that text-based PDFs have hundreds of words per page,
    while scanned PDFs extract very little or no text.
    
    Args:
        text: Extracted text to analyze
        page_count: Number of pages in the PDF
        
    Returns:
        bool: True if PDF appears to be scanned, False otherwise
    """
    # Handle edge cases
    if page_count == 0:
        return True  # No pages means something is wrong
    
    # Count words (any sequence of non-whitespace characters)
    word_count = len(text.split())
    
    # Calculate words per page
    words_per_page = word_count / page_count
    
    # Legal documents typically have 300-600 words per page
    # If less than 50 words/page, it's likely scanned
    is_scanned = words_per_page < SCANNED_PDF_THRESHOLD
    
    return is_scanned


def assess_extraction_quality(text: str, page_count: int) -> Tuple[str, List[str], Dict]:
    """
    Assess the quality of extracted text using multiple heuristics
    
    This function analyzes the extracted text to determine if the extraction
    was successful and of good quality. It checks for:
    - Text completeness (characters per page)
    - Text coherence (special character ratio)
    - Word integrity (average word length)
    - Line break patterns
    
    Args:
        text: Extracted text to analyze
        page_count: Number of pages in the PDF
        
    Returns:
        tuple: (quality_level, issues_list, metrics_dict)
            - quality_level: 'high', 'medium', 'low', or 'failed'
            - issues_list: List of detected quality issues
            - metrics_dict: Dictionary with detailed metrics
    """
    issues = []
    metrics = {}
    
    # Handle edge cases
    if not text or page_count == 0:
        return 'failed', ['no_text_extracted'], {'chars_per_page': 0}
    
    # Metric 1: Characters per page (completeness indicator)
    char_count = len(text)
    chars_per_page = char_count / page_count
    metrics['chars_per_page'] = chars_per_page
    
    if chars_per_page < MIN_CHARS_PER_PAGE:
        issues.append('low_char_density')
    
    # Metric 2: Special character ratio (coherence indicator)
    # Count non-standard characters (excluding letters, numbers, common punctuation)
    special_chars = len(re.findall(r'[^a-zA-ZÀ-ÿ0-9\s\.,;:\-\(\)\[\]\'\"!?]', text))
    special_char_ratio = special_chars / len(text) if len(text) > 0 else 0
    metrics['special_char_ratio'] = special_char_ratio
    
    if special_char_ratio > MAX_SPECIAL_CHAR_RATIO:
        issues.append('high_special_char_ratio')
    
    # Metric 3: Word statistics (integrity indicator)
    words = text.split()
    word_count = len(words)
    metrics['word_count'] = word_count
    
    if word_count > 0:
        avg_word_length = sum(len(word) for word in words) / word_count
        metrics['avg_word_length'] = avg_word_length
        
        if avg_word_length < MIN_AVG_WORD_LENGTH:
            issues.append('word_fragmentation')
    else:
        metrics['avg_word_length'] = 0
        issues.append('no_words_found')
    
    # Metric 4: Excessive line breaks (formatting issue indicator)
    excessive_breaks = text.count('\n\n\n')
    metrics['excessive_line_breaks'] = excessive_breaks
    
    if excessive_breaks > 10:
        issues.append('excessive_line_breaks')
    
    # Determine overall quality level
    if not issues:
        quality_level = 'high'
    elif len(issues) == 1 and 'low_char_density' not in issues:
        quality_level = 'medium'
    elif 'no_text_extracted' in issues or 'no_words_found' in issues:
        quality_level = 'failed'
    else:
        quality_level = 'low'
    
    return quality_level, issues, metrics

# =============================================================================
# DATABASE OPERATIONS
# =============================================================================

def check_if_already_processed(session, document_uuid: uuid.UUID, logger) -> bool:
    """
    Check if a document has already been processed
    
    Args:
        session: SQLAlchemy session
        document_uuid: UUID of the document to check
        logger: Logger instance
        
    Returns:
        bool: True if already processed, False otherwise
    """
    try:
        # Check if document exists in extracted_texts table
        check_stmt = text("""
            SELECT COUNT(*) FROM extracted_texts WHERE document_id = :doc_id
        """)
        
        result = session.execute(check_stmt, {'doc_id': str(document_uuid)}).scalar()
        
        if result > 0:
            logger.info(f"✓ Document already processed (UUID: {document_uuid})")
            return True
        else:
            logger.debug(f"Document not yet processed (UUID: {document_uuid})")
            return False
            
    except Exception as e:
        logger.error(f"Error checking if document already processed: {e}")
        # In case of error, assume not processed to avoid skipping
        return False


def create_or_update_document_record(
    session,
    document_uuid: uuid.UUID,
    identifier: str,
    pdf_path: Path,
    page_count: int,
    logger
) -> bool:
    """
    Create or update a record in the documents table
    
    This function ensures there's a corresponding record in the documents table
    for the extracted text.
    
    Args:
        session: SQLAlchemy session
        document_uuid: UUID of the document
        identifier: Identifier extracted from filename
        pdf_path: Path to PDF file
        page_count: Number of pages in the document
        logger: Logger instance
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get file size
        file_size = pdf_path.stat().st_size
        
        # Generate a placeholder case_id (you'll need to update this later with actual case data)
        # For now, we'll use a deterministic UUID based on the identifier
        case_uuid = uuid.uuid5(PROJECT_UUID_NAMESPACE, f"case_{identifier}")
        
        # Prepare metadata
        metadata = {
            'identifier': identifier,
            'original_filename': pdf_path.name,
            'extraction_date': datetime.now().isoformat()
        }
        
        # Insert or update document record
        upsert_stmt = text("""
            INSERT INTO documents (
                document_id,
                case_id,
                document_type,
                document_url,
                pdf_file_path,
                file_size_bytes,
                page_count,
                pdf_downloaded,
                download_date,
                metadata,
                created_at,
                updated_at
            ) VALUES (
                :document_id,
                :case_id,
                :document_type,
                :document_url,
                :pdf_file_path,
                :file_size_bytes,
                :page_count,
                :pdf_downloaded,
                :download_date,
                :metadata::json,
                NOW(),
                NOW()
            )
            ON CONFLICT (document_id) DO UPDATE SET
                page_count = EXCLUDED.page_count,
                file_size_bytes = EXCLUDED.file_size_bytes,
                metadata = EXCLUDED.metadata,
                updated_at = NOW()
        """)
        
        session.execute(upsert_stmt, {
            'document_id': str(document_uuid),
            'case_id': str(case_uuid),
            'document_type': 'Decision',
            'document_url': None,  # Not available from filename
            'pdf_file_path': str(pdf_path),
            'file_size_bytes': file_size,
            'page_count': page_count,
            'pdf_downloaded': True,
            'download_date': datetime.now(),
            'metadata': json.dumps(metadata)
        })
        
        session.commit()
        logger.debug(f"✓ Created/updated document record for UUID: {document_uuid}")
        return True
        
    except Exception as e:
        session.rollback()
        logger.error(f"✗ Failed to create/update document record: {e}")
        return False


def store_extraction_result(
    session,
    document_uuid: uuid.UUID,
    extraction_result: Dict,
    quality_assessment: Tuple,
    is_scanned: bool,
    json_backup_path: Optional[Path],
    logger
) -> bool:
    """
    Store extraction result in database (extracted_texts table)
    
    This function stores the extracted text and all associated metadata
    in the PostgreSQL database for subsequent analysis.
    
    Args:
        session: SQLAlchemy session
        document_uuid: UUID of the document
        extraction_result: Dict from extract_text_hierarchical
        quality_assessment: Tuple from assess_extraction_quality
        is_scanned: Boolean indicating if PDF is scanned
        json_backup_path: Path to JSON backup file (or None)
        logger: Logger instance
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        quality_level, issues, metrics = quality_assessment
        
        # Prepare data for insertion
        extraction_id = str(uuid.uuid4())
        
        # Build quality_issues JSON
        quality_issues_json = {
            'issues': issues,
            'metrics': metrics
        }
        
        # Prepare SQL statement
        insert_stmt = text("""
            INSERT INTO extracted_texts (
                extraction_id,
                document_id,
                raw_text,
                extraction_method,
                extraction_date,
                extraction_duration_seconds,
                character_count,
                word_count,
                page_count,
                extraction_quality,
                is_scanned,
                quality_issues,
                extraction_notes,
                created_at
            ) VALUES (
                :extraction_id,
                :document_id,
                :raw_text,
                :extraction_method,
                :extraction_date,
                :extraction_duration_seconds,
                :character_count,
                :word_count,
                :page_count,
                :extraction_quality,
                :is_scanned,
                :quality_issues::jsonb,
                :extraction_notes,
                NOW()
            )
            ON CONFLICT (document_id) DO UPDATE SET
                raw_text = EXCLUDED.raw_text,
                extraction_method = EXCLUDED.extraction_method,
                extraction_date = EXCLUDED.extraction_date,
                extraction_duration_seconds = EXCLUDED.extraction_duration_seconds,
                character_count = EXCLUDED.character_count,
                word_count = EXCLUDED.word_count,
                page_count = EXCLUDED.page_count,
                extraction_quality = EXCLUDED.extraction_quality,
                is_scanned = EXCLUDED.is_scanned,
                quality_issues = EXCLUDED.quality_issues,
                extraction_notes = EXCLUDED.extraction_notes,
                updated_at = NOW()
        """)
        
        # Prepare extraction notes
        notes = []
        if json_backup_path:
            notes.append(f"JSON backup: {json_backup_path}")
        if extraction_result.get('error'):
            notes.append(f"Error: {extraction_result['error']}")
        notes.append(f"Library versions: {json.dumps(LIBRARY_VERSIONS)}")
        
        # Execute insertion
        session.execute(insert_stmt, {
            'extraction_id': extraction_id,
            'document_id': str(document_uuid),
            'raw_text': extraction_result['text'],
            'extraction_method': extraction_result['method'],
            'extraction_date': datetime.now(),
            'extraction_duration_seconds': extraction_result['extraction_time'],
            'character_count': len(extraction_result['text']),
            'word_count': metrics.get('word_count', 0),
            'page_count': extraction_result['page_count'],
            'extraction_quality': quality_level,
            'is_scanned': is_scanned,
            'quality_issues': json.dumps(quality_issues_json),
            'extraction_notes': ' | '.join(notes) if notes else None
        })
        
        session.commit()
        logger.info(f"✓ Stored extraction result in database for UUID {document_uuid}")
        return True
        
    except Exception as e:
        session.rollback()
        logger.error(f"✗ Failed to store extraction result: {e}")
        return False


def create_json_backup(
    pdf_path: Path,
    identifier: str,
    document_uuid: uuid.UUID,
    extraction_result: Dict,
    quality_assessment: Tuple,
    is_scanned: bool,
    backup_dir: Path
) -> Optional[Path]:
    """
    Create JSON backup of extraction for audit trail
    
    This backup ensures that the extraction results can be independently
    verified and provides a human-readable audit trail for academic work.
    
    Args:
        pdf_path: Path to original PDF
        identifier: Identifier extracted from filename
        document_uuid: UUID of the document
        extraction_result: Dict from extract_text_hierarchical
        quality_assessment: Tuple from assess_extraction_quality
        is_scanned: Boolean indicating if PDF is scanned
        backup_dir: Directory to store JSON backups
        
    Returns:
        Path: Path to created JSON file, or None if failed
    """
    try:
        # Create backup directory if it doesn't exist
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Create JSON filename based on identifier
        json_filename = f"extraction_{identifier}.json"
        json_path = backup_dir / json_filename
        
        # Prepare backup data
        quality_level, issues, metrics = quality_assessment
        
        backup_data = {
            'identifier': identifier,
            'document_uuid': str(document_uuid),
            'pdf_filename': pdf_path.name,
            'pdf_path': str(pdf_path),
            'extraction_timestamp': datetime.now().isoformat(),
            'extraction_method': extraction_result['method'],
            'extraction_time_seconds': extraction_result['extraction_time'],
            'success': extraction_result['success'],
            'error': extraction_result['error'],
            'text': extraction_result['text'],
            'page_count': extraction_result['page_count'],
            'character_count': len(extraction_result['text']),
            'word_count': metrics.get('word_count', 0),
            'is_scanned': is_scanned,
            'quality_level': quality_level,
            'quality_issues': issues,
            'quality_metrics': metrics,
            'library_versions': LIBRARY_VERSIONS
        }
        
        # Write JSON file
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        
        return json_path
        
    except Exception as e:
        logging.error(f"Failed to create JSON backup: {e}")
        return None

# =============================================================================
# MAIN PROCESSING FUNCTIONS
# =============================================================================

def get_documents_to_process(pdf_dir: Path, session, limit: Optional[int] = None, logger=None) -> List[Tuple]:
    """
    Get list of PDF files to process
    
    This function:
    1. Scans the PDF directory for .pdf files
    2. Extracts identifier from each filename
    3. Generates deterministic UUID
    4. Checks if already processed in database
    5. Returns list of files that need processing
    
    Args:
        pdf_dir: Directory containing PDF files
        session: SQLAlchemy session
        limit: Optional limit on number of documents to process
        logger: Logger instance
        
    Returns:
        list: List of tuples (pdf_path, identifier, document_uuid)
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    # Get all PDF files in directory
    pdf_files = sorted(list(pdf_dir.glob('*.pdf')))
    
    if not pdf_files:
        logger.warning(f"No PDF files found in {pdf_dir}")
        return []
    
    logger.info(f"Found {len(pdf_files)} PDF files in directory")
    
    # Process each PDF file
    documents_to_process = []
    skipped_count = 0
    already_processed_count = 0
    
    for pdf_path in pdf_files:
        # Identify the PDF file (extract identifier and generate UUID)
        identification = identify_pdf_file(pdf_path, logger)
        
        if identification is None:
            logger.warning(f"Skipping {pdf_path.name} - cannot extract identifier")
            skipped_count += 1
            continue
        
        identifier, document_uuid = identification
        
        # Check if already processed
        if check_if_already_processed(session, document_uuid, logger):
            already_processed_count += 1
            continue
        
        # Add to processing list
        documents_to_process.append((pdf_path, identifier, document_uuid))
        
        # Stop if we've reached the limit
        if limit and len(documents_to_process) >= limit:
            logger.info(f"Reached limit of {limit} documents")
            break
    
    # Summary
    logger.info(f"\nProcessing summary:")
    logger.info(f"  Total PDF files found: {len(pdf_files)}")
    logger.info(f"  Already processed: {already_processed_count}")
    logger.info(f"  Skipped (no identifier): {skipped_count}")
    logger.info(f"  To process: {len(documents_to_process)}")
    
    return documents_to_process


def process_single_pdf(
    pdf_path: Path,
    identifier: str,
    document_uuid: uuid.UUID,
    session,
    backup_dir: Path,
    logger
) -> Dict:
    """
    Process a single PDF file: extract text, assess quality, store in database
    
    This is the main processing function that orchestrates all steps for
    extracting text from a single PDF document.
    
    Args:
        pdf_path: Path to PDF file
        identifier: Identifier extracted from filename
        document_uuid: Deterministic UUID of the document
        session: SQLAlchemy session
        backup_dir: Directory for JSON backups
        logger: Logger instance
        
    Returns:
        dict: Processing result summary
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"Processing: {pdf_path.name}")
    logger.info(f"Identifier: {identifier}")
    logger.info(f"UUID: {document_uuid}")
    logger.info(f"{'='*70}")
    
    start_time = time.time()
    
    # Step 1: Extract text using hierarchical approach
    extraction_result = extract_text_hierarchical(pdf_path, logger)
    
    # Step 2: Detect if PDF is scanned
    is_scanned = detect_scanned_pdf(
        extraction_result['text'],
        extraction_result['page_count']
    )
    
    if is_scanned:
        logger.warning(f"⚠ PDF appears to be scanned - will need OCR processing")
    
    # Step 3: Assess extraction quality
    quality_assessment = assess_extraction_quality(
        extraction_result['text'],
        extraction_result['page_count']
    )
    
    quality_level, issues, metrics = quality_assessment
    logger.info(f"Quality assessment: {quality_level}")
    if issues:
        logger.info(f"Quality issues detected: {', '.join(issues)}")
    logger.info(f"Metrics: {json.dumps(metrics, indent=2)}")
    
    # Step 4: Create or update document record
    doc_success = create_or_update_document_record(
        session,
        document_uuid,
        identifier,
        pdf_path,
        extraction_result['page_count'],
        logger
    )
    
    # Step 5: Create JSON backup
    json_backup_path = create_json_backup(
        pdf_path,
        identifier,
        document_uuid,
        extraction_result,
        quality_assessment,
        is_scanned,
        backup_dir
    )
    
    if json_backup_path:
        logger.info(f"✓ JSON backup created: {json_backup_path}")
    
    # Step 6: Store extraction in database
    extraction_success = store_extraction_result(
        session,
        document_uuid,
        extraction_result,
        quality_assessment,
        is_scanned,
        json_backup_path,
        logger
    )
    
    # Calculate total processing time
    total_time = time.time() - start_time
    
    # Prepare result summary
    result = {
        'pdf_name': pdf_path.name,
        'identifier': identifier,
        'document_uuid': str(document_uuid),
        'success': extraction_result['success'] and doc_success and extraction_success,
        'extraction_method': extraction_result['method'],
        'quality_level': quality_level,
        'is_scanned': is_scanned,
        'char_count': len(extraction_result['text']),
        'word_count': metrics.get('word_count', 0),
        'page_count': extraction_result['page_count'],
        'processing_time': total_time,
        'issues': issues
    }
    
    logger.info(f"\nProcessing completed in {total_time:.2f}s")
    logger.info(f"Overall success: {result['success']}")
    
    return result


def process_pdf_batch(
    pdf_dir: Path,
    backup_dir: Path,
    test_mode: bool = False,
    limit: Optional[int] = None
) -> Dict:
    """
    Process a batch of PDF files
    
    This function processes multiple PDFs and generates a summary report.
    
    Args:
        pdf_dir: Directory containing PDF files
        backup_dir: Directory for JSON backups
        test_mode: If True, runs in test mode with verbose logging
        limit: Optional limit on number of PDFs to process
        
    Returns:
        dict: Batch processing summary
    """
    # Setup logging
    logger = setup_logging(test_mode=test_mode)
    
    # Validate PDF directory
    if not pdf_dir.exists():
        logger.error(f"PDF directory does not exist: {pdf_dir}")
        return {'success': False, 'error': f'Directory not found: {pdf_dir}'}
    
    # Create database session
    logger.info("Connecting to database...")
    try:
        session, engine = create_db_session()
        logger.info("✓ Database connection established")
    except Exception as e:
        logger.error(f"✗ Failed to connect to database: {e}")
        return {'success': False, 'error': str(e)}
    
    # Get documents to process
    logger.info(f"\nScanning for PDFs in: {pdf_dir}")
    documents = get_documents_to_process(pdf_dir, session, limit, logger)
    
    if not documents:
        logger.warning("No documents to process. Exiting.")
        session.close()
        return {'success': False, 'error': 'No documents found to process'}
    
    # Process each document
    results = []
    success_count = 0
    failed_count = 0
    scanned_count = 0
    
    for i, (pdf_path, identifier, doc_uuid) in enumerate(documents, 1):
        logger.info(f"\n{'='*70}")
        logger.info(f"Processing PDF {i}/{len(documents)}")
        logger.info(f"{'='*70}")
        
        try:
            result = process_single_pdf(
                pdf_path,
                identifier,
                doc_uuid,
                session,
                backup_dir,
                logger
            )
            
            results.append(result)
            
            if result['success']:
                success_count += 1
            else:
                failed_count += 1
            
            if result['is_scanned']:
                scanned_count += 1
                
        except Exception as e:
            logger.error(f"✗ Unexpected error processing {pdf_path.name}: {e}")
            failed_count += 1
            results.append({
                'pdf_name': pdf_path.name,
                'identifier': identifier,
                'document_uuid': str(doc_uuid),
                'success': False,
                'error': str(e)
            })
    
    # Close database connection
    session.close()
    logger.info("\nDatabase connection closed")
    
    # Generate summary report
    logger.info(f"\n{'='*70}")
    logger.info("PROCESSING SUMMARY")
    logger.info(f"{'='*70}")
    logger.info(f"Total PDFs processed: {len(documents)}")
    logger.info(f"Successful extractions: {success_count}")
    logger.info(f"Failed extractions: {failed_count}")
    logger.info(f"Scanned PDFs detected: {scanned_count} ({scanned_count/len(documents)*100:.1f}%)")
    
    # Quality distribution
    quality_dist = {}
    for result in results:
        if result.get('quality_level'):
            quality = result['quality_level']
            quality_dist[quality] = quality_dist.get(quality, 0) + 1
    
    logger.info(f"\nQuality distribution:")
    for quality, count in sorted(quality_dist.items()):
        logger.info(f"  {quality}: {count} ({count/len(results)*100:.1f}%)")
    
    # Method distribution
    method_dist = {}
    for result in results:
        if result.get('extraction_method'):
            method = result['extraction_method']
            method_dist[method] = method_dist.get(method, 0) + 1
    
    logger.info(f"\nExtraction method distribution:")
    for method, count in sorted(method_dist.items()):
        logger.info(f"  {method}: {count} ({count/len(results)*100:.1f}%)")
    
    # Average statistics
    total_chars = sum(r.get('char_count', 0) for r in results if r.get('success'))
    total_words = sum(r.get('word_count', 0) for r in results if r.get('success'))
    total_pages = sum(r.get('page_count', 0) for r in results if r.get('success'))
    total_time = sum(r.get('processing_time', 0) for r in results)
    
    if success_count > 0:
        logger.info(f"\nAverage statistics (successful extractions only):")
        logger.info(f"  Characters per document: {total_chars/success_count:.0f}")
        logger.info(f"  Words per document: {total_words/success_count:.0f}")
        logger.info(f"  Pages per document: {total_pages/success_count:.1f}")
        logger.info(f"  Processing time per document: {total_time/len(results):.2f}s")
    
    # Projection for full database
    if len(documents) < 2924:  # Total decision documents in database
        remaining = 2924 - len(documents)
        avg_time_per_doc = total_time / len(results)
        estimated_time = remaining * avg_time_per_doc
        estimated_hours = estimated_time / 3600
        
        logger.info(f"\nProjection for full database:")
        logger.info(f"  Remaining documents: {remaining}")
        logger.info(f"  Estimated time: {estimated_hours:.1f} hours")
    
    logger.info(f"\n{'='*70}")
    logger.info("Processing completed!")
    logger.info(f"{'='*70}\n")
    
    summary = {
        'success': True,
        'total_processed': len(documents),
        'successful': success_count,
        'failed': failed_count,
        'scanned': scanned_count,
        'quality_distribution': quality_dist,
        'method_distribution': method_dist,
        'total_processing_time': total_time,
        'results': results
    }
    
    return summary

# =============================================================================
# COMMAND LINE INTERFACE
# =============================================================================

def main():
    """
    Main function for command line execution
    """
    parser = argparse.ArgumentParser(
        description='Extract text from PDF documents for climate litigation analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Default run (uses global PDFS_FOLDER_PATH variable):
  python extract_pdf_text.py
  
  # Test mode with limit:
  python extract_pdf_text.py --test --limit 15
  
  # Override PDF directory:
  python extract_pdf_text.py --pdf-dir pdfs/other_folder
  
  # Custom backup location:
  python extract_pdf_text.py --backup-dir backups/extractions

Filename Patterns Supported:
  - ID_XXXX_filename.pdf (e.g., ID_0001_test.pdf)
  - decision-CaseID.pdf (e.g., decision-BR-2020-1234.pdf)
        """
    )
    
    parser.add_argument(
        '--pdf-dir',
        type=Path,
        default=None,
        help=f'Directory containing PDF files (default: {PDFS_FOLDER_PATH})'
    )
    
    parser.add_argument(
        '--backup-dir',
        type=Path,
        default=Path('data/extraction_backups'),
        help='Directory to store JSON backups (default: data/extraction_backups)'
    )
    
    parser.add_argument(
        '--test',
        action='store_true',
        help='Run in test mode with verbose logging'
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Limit number of PDFs to process (useful for testing)'
    )
    
    args = parser.parse_args()
    
    # Use global PDFS_FOLDER_PATH if --pdf-dir not provided
    if args.pdf_dir is None:
        pdf_dir = Path(PDFS_FOLDER_PATH)
    else:
        pdf_dir = args.pdf_dir
    
    # Validate PDF directory exists
    if not pdf_dir.exists():
        print(f"✗ Error: PDF directory does not exist: {pdf_dir}")
        print(f"\nTo create the directory, run:")
        print(f"  mkdir -p {pdf_dir}")
        sys.exit(1)
    
    # Check if any PDF extraction library is available
    if not (PDFPLUMBER_AVAILABLE or PYMUPDF_AVAILABLE or PYPDF2_AVAILABLE):
        print("✗ Error: No PDF extraction library available!")
        print("  Please install at least one of:")
        print("    pip install pdfplumber")
        print("    pip install PyMuPDF")
        print("    pip install PyPDF2")
        sys.exit(1)
    
    # Display configuration
    print("\n" + "="*70)
    print("PDF TEXT EXTRACTION - PHASE 1 (v2.0)")
    print("Climate Litigation Analysis Project")
    print("="*70)
    print(f"\nConfiguration:")
    print(f"  PDF directory: {pdf_dir}")
    print(f"  Backup directory: {args.backup_dir}")
    print(f"  Test mode: {args.test}")
    print(f"  Limit: {args.limit if args.limit else 'None (process all)'}")
    print(f"\nSupported filename patterns:")
    print(f"  - ID_XXXX_filename.pdf (test files)")
    print(f"  - decision-CaseID.pdf (production files)")
    print(f"\nAvailable libraries:")
    print(f"  pdfplumber: {'✓' if PDFPLUMBER_AVAILABLE else '✗'}")
    print(f"  PyMuPDF: {'✓' if PYMUPDF_AVAILABLE else '✗'}")
    print(f"  PyPDF2: {'✓' if PYPDF2_AVAILABLE else '✗'}")
    print("="*70 + "\n")
    
    # Confirm before proceeding (unless in test mode with limit)
    if not args.test or not args.limit:
        response = input("Proceed with extraction? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("Extraction cancelled.")
            sys.exit(0)
    
    # Run batch processing
    summary = process_pdf_batch(
        pdf_dir=pdf_dir,
        backup_dir=args.backup_dir,
        test_mode=args.test,
        limit=args.limit
    )
    
    # Exit with appropriate code
    if summary.get('success'):
        print("\n✓ Extraction completed successfully!")
        sys.exit(0)
    else:
        print(f"\n✗ Extraction failed: {summary.get('error', 'Unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
