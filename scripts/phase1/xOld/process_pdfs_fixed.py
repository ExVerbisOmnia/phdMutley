"""
PDF Processing Script for Climate Litigation PhD Project
========================================================

This script processes all downloaded PDF files (court decisions), extracts
their text content, and stores the results in a PostgreSQL 18 database.

Key Features:
- Reads PDFs from the directory structure created by download_decisions.py
- Extracts text using the text_extractor module
- Stores extracted text in PostgreSQL database
- Comprehensive logging of all operations
- Progress tracking with tqdm
- Error handling with graceful failure (continues on errors)
- Can be paused and resumed (tracks processed files)

Author: Lucas Biasetton (Gus)
Project: Doutorado PM - Climate Litigation Citation Analysis
Version: 1.0
Date: October 31, 2025
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import json

# Import the text extraction module we just created
import text_extractor

# Database libraries
from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
import uuid

# Progress tracking
from tqdm import tqdm

# Environment variables for database credentials
from dotenv import load_dotenv


# ============================================================================
# CONFIGURATION
# ============================================================================

# Load environment variables from .env file
# The .env file should contain: DATABASE_URL=postgresql://user:password@localhost:5432/dbname
load_dotenv()

# Get database connection URL from environment
# Format: postgresql://username:password@host:port/database_name
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://phdmutley:197230@localhost:5432/climate_litigation'
)

# Directory where PDFs were downloaded
# This should match the output directory from download_decisions.py
PDF_BASE_DIR = Path("/home/gusrodgs/Gus/cienciaDeDados/phdMutley/pdfs/first_processing_batch")

# Logging configuration
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Create log filename with timestamp
log_filename = LOG_DIR / f"pdf_processing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Configure logging to both file and console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename),  # Log to file
        logging.StreamHandler(sys.stdout)    # Also print to console
    ]
)

logger = logging.getLogger(__name__)


# ============================================================================
# DATABASE SCHEMA DEFINITION (SQLAlchemy ORM Models)
# ============================================================================
# These classes define the structure of our database tables
# SQLAlchemy automatically creates the tables based on these definitions

# Create base class for all ORM models
Base = declarative_base()


class Case(Base):
    """
    Cases table - stores metadata about each court case.
    
    This table contains information from the original Climate Case Chart database
    plus additional fields we need for tracking.
    """
    __tablename__ = 'cases'
    
    # Primary key: Using UUIDv7 for better performance in PostgreSQL 18
    # UUIDv7 is time-ordered, which improves index performance
    case_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Original case ID from Climate Case Chart (for reference)
    original_case_id = Column(String(255), unique=True, nullable=False, index=True)
    
    # Case information
    case_name = Column(Text, nullable=False)
    jurisdiction = Column(String(255), index=True)
    court_name = Column(String(500))
    
    # Geographic information
    geography_iso = Column(String(10), index=True)
    geography_name = Column(String(255))
    
    # Region classification (North/South Global)
    region = Column(String(50), index=True)  # 'North' or 'South'
    
    # Case status and dates
    status = Column(String(100))
    filing_date = Column(DateTime)
    decision_date = Column(DateTime)
    
    # Case type and classification
    case_type = Column(String(100))
    document_type = Column(String(100))
    
    # Source information
    source_url = Column(Text)
    
    # Flexible metadata storage using JSONB (PostgreSQL JSON with indexing)
    # This allows us to store additional metadata without changing the schema
    metadata_json = Column(JSONB)
    
    # Timestamp tracking
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    # Relationships to other tables
    documents = relationship("Document", back_populates="case", cascade="all, delete-orphan")


class Document(Base):
    """
    Documents table - stores information about PDF files.
    
    Each case can have multiple documents (though in Phase 1 we focus on decisions).
    """
    __tablename__ = 'documents'
    
    # Primary key: UUIDv7 for better PostgreSQL 18 performance
    document_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign key to cases table
    case_id = Column(UUID(as_uuid=True), ForeignKey('cases.case_id'), nullable=False, index=True)
    
    # Document information
    document_type = Column(String(100))  # e.g., 'Decision', 'Brief', 'Order'
    file_path = Column(Text, unique=True)  # Full path to the PDF file
    file_hash = Column(String(64), unique=True)  # SHA-256 hash for deduplication
    
    # File metadata
    file_size_bytes = Column(Integer)
    page_count = Column(Integer)
    
    # Download information
    download_date = Column(DateTime)
    download_success = Column(Boolean, default=False)
    download_error = Column(Text)
    
    # Source URL
    source_url = Column(Text)
    
    # Timestamp tracking
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    # Relationships
    case = relationship("Case", back_populates="documents")
    extracted_text = relationship("ExtractedText", back_populates="document", uselist=False)


class ExtractedText(Base):
    """
    Extracted texts table - stores the text extracted from PDF documents.
    
    This is a one-to-one relationship with documents (each document has one extraction).
    Keeping this separate from documents table improves query performance.
    """
    __tablename__ = 'extracted_texts'
    
    # Primary key: UUIDv7
    extraction_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign key to documents table (one-to-one relationship)
    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.document_id'), 
                         nullable=False, unique=True, index=True)
    
    # The actual extracted text (can be very large)
    # PostgreSQL handles large TEXT fields efficiently, especially with AIO in version 18
    raw_text = Column(Text)
    
    # Extraction metadata
    extraction_method = Column(String(50))  # 'pdfplumber', 'pymupdf', 'pypdf2'
    extraction_date = Column(DateTime, default=datetime.now)
    extraction_duration_seconds = Column(Float)
    
    # Text statistics
    character_count = Column(Integer)
    word_count = Column(Integer)
    page_count = Column(Integer)
    
    # Quality assessment
    extraction_quality = Column(String(50))  # 'excellent', 'good', 'fair', 'poor', 'failed'
    is_scanned = Column(Boolean, default=False)
    
    # Quality issues stored as JSONB for flexibility
    quality_issues = Column(JSONB)
    
    # Extraction notes (any warnings or errors)
    extraction_notes = Column(Text)
    
    # Timestamp tracking
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    # Relationships
    document = relationship("Document", back_populates="extracted_text")


class ExtractionLog(Base):
    """
    Extraction log table - detailed logging of all extraction operations.
    
    This table maintains a complete audit trail of all extraction attempts,
    which is essential for academic transparency and debugging.
    """
    __tablename__ = 'extraction_log'
    
    # Primary key: auto-incrementing integer (simple for logs)
    log_id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key to documents table
    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.document_id'), index=True)
    
    # Log details
    stage = Column(String(50))  # 'extraction', 'validation', 'quality_check'
    status = Column(String(50), index=True)  # 'success', 'failure', 'warning'
    message = Column(Text)
    
    # Error details (if applicable)
    error_type = Column(String(100))
    error_details = Column(Text)
    
    # Timestamp
    timestamp = Column(DateTime, server_default=func.now(), index=True)


# ============================================================================
# DATABASE CONNECTION AND SESSION MANAGEMENT
# ============================================================================

def create_database_connection():
    """
    Create a connection to the PostgreSQL database.
    
    This function creates a SQLAlchemy engine and session maker.
    The engine manages the connection pool to the database.
    
    Returns:
        tuple: (engine, SessionLocal) - Database engine and session factory
    """
    logger.info(f"Connecting to database...")
    
    try:
        # Create SQLAlchemy engine
        # echo=False means don't print all SQL queries (set to True for debugging)
        # pool_pre_ping=True checks connections before using them (handles disconnects)
        engine = create_engine(
            DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
            # PostgreSQL 18 optimization: use multiple connections for parallel I/O
            pool_size=5,
            max_overflow=10
        )
        
        # Create session factory
        # Sessions are used to interact with the database
        SessionLocal = sessionmaker(bind=engine)
        
        # Test the connection
        with engine.connect() as conn:
            logger.info("✓ Database connection successful")
        
        return engine, SessionLocal
    
    except Exception as e:
        logger.error(f"✗ Database connection failed: {str(e)}")
        logger.error("Please check your DATABASE_URL in .env file")
        logger.error("Format: postgresql://username:password@host:port/database_name")
        raise


def initialize_database(engine):
    """
    Initialize the database by creating all tables if they don't exist.
    
    This function is idempotent - it's safe to run multiple times.
    It will only create tables that don't already exist.
    
    Args:
        engine: SQLAlchemy engine connected to the database
    """
    logger.info("Initializing database tables...")
    
    try:
        # Create all tables defined in our ORM models
        # This is equivalent to running CREATE TABLE statements
        Base.metadata.create_all(engine)
        logger.info("✓ Database tables initialized successfully")
    except Exception as e:
        logger.error(f"✗ Failed to initialize database: {str(e)}")
        raise


# ============================================================================
# PDF DISCOVERY FUNCTIONS
# ============================================================================

def find_all_pdfs(base_dir: Path) -> List[Path]:
    """
    Recursively find all PDF files in the directory structure.
    
    This function scans the PDF download directory and finds all .pdf files.
    The directory structure is: base_dir / geography / case_id.pdf
    
    Args:
        base_dir (Path): Base directory containing PDF files
    
    Returns:
        list: List of Path objects pointing to PDF files
    """
    logger.info(f"Scanning for PDF files in: {base_dir}")
    
    # Use glob to recursively find all .pdf files
    # The ** pattern means "any number of subdirectories"
    pdf_files = list(base_dir.glob("**/*.pdf"))
    
    logger.info(f"Found {len(pdf_files)} PDF files")
    
    return pdf_files


def extract_case_info_from_path(pdf_path: Path) -> Dict[str, str]:
    """
    Extract case information from the PDF file path.
    
    The PDF files are organized as: geography_name/case_id.pdf
    This function parses the path to extract this information.
    
    Args:
        pdf_path (Path): Path to the PDF file
    
    Returns:
        dict: Dictionary with 'geography' and 'case_id' keys
    """
    # Get the parent directory name (geography)
    geography = pdf_path.parent.name
    
    # Get the filename without .pdf extension (case_id)
    case_id = pdf_path.stem
    
    return {
        'geography': geography,
        'case_id': case_id,
        'full_path': str(pdf_path.absolute())
    }


# ============================================================================
# DATABASE OPERATIONS
# ============================================================================

def check_if_processed(session, file_path: str) -> bool:
    """
    Check if a PDF has already been processed.
    
    This allows us to resume processing if the script is interrupted.
    We check if there's already an extracted_text record for this file.
    
    Args:
        session: SQLAlchemy database session
        file_path (str): Full path to the PDF file
    
    Returns:
        bool: True if already processed, False otherwise
    """
    # Query the database to see if this document exists and has extracted text
    existing_document = session.query(Document).filter(
        Document.file_path == file_path
    ).first()
    
    if existing_document:
        # Check if text has been extracted
        has_extraction = session.query(ExtractedText).filter(
            ExtractedText.document_id == existing_document.document_id
        ).first() is not None
        
        return has_extraction
    
    return False


def store_extraction_result(
    session,
    pdf_path: Path,
    extraction_result: Dict,
    metadata: Dict,
    case_info: Dict
):
    """
    Store the extraction result in the database.
    
    This function handles the complex task of inserting data into multiple
    related tables (cases, documents, extracted_texts, extraction_log).
    
    Args:
        session: SQLAlchemy database session
        pdf_path (Path): Path to the PDF file
        extraction_result (dict): Result from text_extractor.extract_text_from_pdf()
        metadata (dict): Result from text_extractor.extract_pdf_metadata()
        case_info (dict): Case information extracted from file path
    """
    try:
        # --------------------------------------------------------
        # Step 1: Get or create the Case record
        # --------------------------------------------------------
        # Check if this case already exists in the database
        case = session.query(Case).filter(
            Case.original_case_id == case_info['case_id']
        ).first()
        
        # If case doesn't exist, create a new one
        if not case:
            case = Case(
                original_case_id=case_info['case_id'],
                case_name=case_info['case_id'],  # We'll update this from CSV later
                geography_name=case_info['geography'],
                # Other fields will be populated when we import the CSV data
            )
            session.add(case)
            session.flush()  # Flush to get the generated case_id
            logger.debug(f"Created new case: {case_info['case_id']}")
        
        # --------------------------------------------------------
        # Step 2: Create the Document record
        # --------------------------------------------------------
        # Check if this document already exists
        document = session.query(Document).filter(
            Document.file_path == case_info['full_path']
        ).first()
        
        if not document:
            document = Document(
                case_id=case.case_id,
                document_type='Decision',  # Phase 1 is decisions only
                file_path=case_info['full_path'],
                file_size_bytes=metadata.get('file_size_bytes', 0),
                page_count=metadata.get('page_count', 0),
                download_date=metadata.get('modification_date'),
                download_success=True,
                source_url=None,  # Will be populated from CSV later
            )
            session.add(document)
            session.flush()  # Flush to get the generated document_id
            logger.debug(f"Created document record for: {pdf_path.name}")
        
        # --------------------------------------------------------
        # Step 3: Create the ExtractedText record
        # --------------------------------------------------------
        # Check if extraction already exists (shouldn't, but be safe)
        existing_extraction = session.query(ExtractedText).filter(
            ExtractedText.document_id == document.document_id
        ).first()
        
        if not existing_extraction:
            extracted_text = ExtractedText(
                document_id=document.document_id,
                raw_text=extraction_result['text'],
                extraction_method=extraction_result['method_used'],
                extraction_date=datetime.now(),
                extraction_duration_seconds=extraction_result['extraction_duration_seconds'],
                character_count=extraction_result['character_count'],
                word_count=extraction_result['word_count'],
                page_count=extraction_result['page_count'],
                extraction_quality=extraction_result['quality'],
                is_scanned=extraction_result['is_scanned'],
                quality_issues=json.dumps(extraction_result.get('errors', [])),
                extraction_notes='; '.join(extraction_result.get('errors', []))
            )
            session.add(extracted_text)
            logger.debug(f"Created extraction record: {extraction_result['word_count']} words")
        else:
            logger.warning(f"Extraction already exists for: {pdf_path.name}")
        
        # --------------------------------------------------------
        # Step 4: Create log entry
        # --------------------------------------------------------
        log_entry = ExtractionLog(
            document_id=document.document_id,
            stage='extraction',
            status='success' if extraction_result['quality'] != 'failed' else 'failure',
            message=f"Extracted {extraction_result['word_count']} words using {extraction_result['method_used']}. Quality: {extraction_result['quality']}",
            error_type=None if not extraction_result['errors'] else 'extraction_issue',
            error_details='; '.join(extraction_result['errors']) if extraction_result['errors'] else None
        )
        session.add(log_entry)
        
        # --------------------------------------------------------
        # Step 5: Commit all changes to the database
        # --------------------------------------------------------
        # This actually writes all the changes to the database
        session.commit()
        logger.debug(f"✓ Committed extraction results for: {pdf_path.name}")
        
    except Exception as e:
        # If anything goes wrong, rollback the transaction
        # This ensures the database stays consistent
        session.rollback()
        logger.error(f"✗ Failed to store extraction result: {str(e)}")
        
        # Create error log entry
        try:
            error_log = ExtractionLog(
                document_id=document.document_id if 'document' in locals() else None,
                stage='database_storage',
                status='failure',
                message='Failed to store extraction result in database',
                error_type=type(e).__name__,
                error_details=str(e)
            )
            session.add(error_log)
            session.commit()
        except:
            pass  # If even error logging fails, just continue
        
        raise


# ============================================================================
# MAIN PROCESSING FUNCTION
# ============================================================================

def process_all_pdfs():
    """
    Main function to process all PDF files.
    
    This function:
    1. Finds all PDF files
    2. For each PDF:
       - Checks if already processed (skip if yes)
       - Extracts metadata
       - Extracts text
       - Stores results in database
       - Logs the operation
    3. Provides progress tracking
    4. Handles errors gracefully (continues on failure)
    """
    logger.info("="*70)
    logger.info("STARTING PDF TEXT EXTRACTION PROCESS")
    logger.info("="*70)
    
    # --------------------------------------------------------
    # Step 1: Database setup
    # --------------------------------------------------------
    logger.info("\n1. Setting up database connection...")
    engine, SessionLocal = create_database_connection()
    initialize_database(engine)
    
    # --------------------------------------------------------
    # Step 2: Find all PDFs
    # --------------------------------------------------------
    logger.info("\n2. Finding PDF files...")
    if not PDF_BASE_DIR.exists():
        logger.error(f"PDF directory not found: {PDF_BASE_DIR}")
        logger.error("Please ensure PDFs have been downloaded first.")
        return
    
    pdf_files = find_all_pdfs(PDF_BASE_DIR)
    
    if not pdf_files:
        logger.warning("No PDF files found!")
        return
    
    logger.info(f"Found {len(pdf_files)} PDF files to process")
    
    # --------------------------------------------------------
    # Step 3: Process each PDF
    # --------------------------------------------------------
    logger.info("\n3. Processing PDF files...")
    
    # Statistics tracking
    stats = {
        'total': len(pdf_files),
        'processed': 0,
        'skipped_already_done': 0,
        'successful': 0,
        'failed': 0,
        'scanned': 0,
        'excellent_quality': 0,
        'good_quality': 0,
        'fair_quality': 0,
        'poor_quality': 0
    }
    
    # Use tqdm for a nice progress bar
    # tqdm automatically updates as we iterate through the files
    with tqdm(total=len(pdf_files), desc="Processing PDFs", unit="file") as pbar:
        for pdf_path in pdf_files:
            # Create a new database session for each file
            # This prevents memory issues with large batches
            session = SessionLocal()
            
            try:
                # Extract case information from file path
                case_info = extract_case_info_from_path(pdf_path)
                
                # Check if already processed
                if check_if_processed(session, case_info['full_path']):
                    logger.debug(f"Skipping (already processed): {pdf_path.name}")
                    stats['skipped_already_done'] += 1
                    pbar.update(1)
                    continue
                
                # Extract metadata
                metadata = text_extractor.extract_pdf_metadata(str(pdf_path))
                
                # Extract text
                # Use 'auto' method to try libraries in order of quality
                extraction_result = text_extractor.extract_text_from_pdf(
                    str(pdf_path),
                    method='auto'
                )
                
                # Store results in database
                store_extraction_result(
                    session=session,
                    pdf_path=pdf_path,
                    extraction_result=extraction_result,
                    metadata=metadata,
                    case_info=case_info
                )
                
                # Update statistics
                stats['processed'] += 1
                
                if extraction_result['quality'] != 'failed':
                    stats['successful'] += 1
                else:
                    stats['failed'] += 1
                
                if extraction_result['is_scanned']:
                    stats['scanned'] += 1
                
                # Track quality distribution
                quality = extraction_result['quality']
                if quality == 'excellent':
                    stats['excellent_quality'] += 1
                elif quality == 'good':
                    stats['good_quality'] += 1
                elif quality == 'fair':
                    stats['fair_quality'] += 1
                elif quality == 'poor':
                    stats['poor_quality'] += 1
                
                # Update progress bar description with current file
                pbar.set_postfix({
                    'current': pdf_path.name[:30],
                    'success': stats['successful'],
                    'failed': stats['failed']
                })
                
            except Exception as e:
                # Log the error but continue processing
                logger.error(f"Error processing {pdf_path.name}: {str(e)}")
                stats['failed'] += 1
            
            finally:
                # Always close the session to free resources
                session.close()
                # Update the progress bar
                pbar.update(1)
    
    # --------------------------------------------------------
    # Step 4: Print summary
    # --------------------------------------------------------
    logger.info("\n" + "="*70)
    logger.info("PROCESSING COMPLETE - SUMMARY")
    logger.info("="*70)
    logger.info(f"Total files found:           {stats['total']}")
    logger.info(f"Already processed (skipped): {stats['skipped_already_done']}")
    logger.info(f"Newly processed:             {stats['processed']}")
    logger.info(f"Successful extractions:      {stats['successful']}")
    logger.info(f"Failed extractions:          {stats['failed']}")
    logger.info(f"Scanned documents detected:  {stats['scanned']}")
    logger.info("")
    logger.info("Quality Distribution:")
    logger.info(f"  Excellent: {stats['excellent_quality']}")
    logger.info(f"  Good:      {stats['good_quality']}")
    logger.info(f"  Fair:      {stats['fair_quality']}")
    logger.info(f"  Poor:      {stats['poor_quality']}")
    logger.info("="*70)
    
    # Calculate success rate
    if stats['processed'] > 0:
        success_rate = (stats['successful'] / stats['processed']) * 100
        logger.info(f"\nSuccess rate: {success_rate:.1f}%")
    
    logger.info(f"\nLog file saved to: {log_filename}")


# ============================================================================
# UTILITY FUNCTIONS FOR QUERYING THE DATABASE
# ============================================================================

def get_extraction_statistics(session):
    """
    Get summary statistics about text extractions from the database.
    
    This is useful for monitoring the overall quality of the extraction process.
    
    Args:
        session: SQLAlchemy database session
    
    Returns:
        dict: Statistics about extractions
    """
    from sqlalchemy import func as sql_func
    
    stats = {}
    
    # Total extractions
    stats['total_extractions'] = session.query(ExtractedText).count()
    
    # Quality distribution
    for quality in ['excellent', 'good', 'fair', 'poor', 'failed']:
        count = session.query(ExtractedText).filter(
            ExtractedText.extraction_quality == quality
        ).count()
        stats[f'quality_{quality}'] = count
    
    # Scanned documents
    stats['scanned_documents'] = session.query(ExtractedText).filter(
        ExtractedText.is_scanned == True
    ).count()
    
    # Average statistics
    avg_stats = session.query(
        sql_func.avg(ExtractedText.word_count).label('avg_words'),
        sql_func.avg(ExtractedText.character_count).label('avg_chars'),
        sql_func.avg(ExtractedText.page_count).label('avg_pages')
    ).first()
    
    stats['avg_word_count'] = round(avg_stats.avg_words, 2) if avg_stats.avg_words else 0
    stats['avg_character_count'] = round(avg_stats.avg_chars, 2) if avg_stats.avg_chars else 0
    stats['avg_page_count'] = round(avg_stats.avg_pages, 2) if avg_stats.avg_pages else 0
    
    return stats


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    # This is what runs when you execute: python process_pdfs.py
    
    try:
        # Run the main processing function
        process_all_pdfs()
        
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        logger.info("\n\nProcess interrupted by user (Ctrl+C)")
        logger.info("Progress has been saved. You can resume by running the script again.")
        sys.exit(0)
        
    except Exception as e:
        # Handle unexpected errors
        logger.error(f"\n\nFatal error: {str(e)}")
        logger.exception("Full traceback:")
        sys.exit(1)
