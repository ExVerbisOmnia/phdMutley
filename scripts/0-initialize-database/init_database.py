#!/usr/bin/env python3
"""
Database Initialization Script for Climate Litigation Citation Analysis
Creates PostgreSQL database schema with all required tables and indexes.

Author: Gustavo (Gus)
Project: PhD Climate Litigation Research (Lucas "Mutley")
Phase: Phase 0 & Phase 1
Date: October/November 2025
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import traceback
from typing import Optional
import argparse
from dotenv import load_dotenv

# Load environment variables from project root .env
env_path = Path(__file__).resolve().parent.parent.parent / '.env'
load_dotenv(env_path)

# SQLAlchemy imports - SQLAlchemy 2.0 compatible
from sqlalchemy import (
    create_engine, Column, String, Integer, Float, Boolean, 
    DateTime, Text, ForeignKey, Index, inspect, text, DECIMAL, TIMESTAMP, JSON
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.dialects.postgresql import UUID
import uuid

# Logging configuration
import logging

# ============================================================
# LOGGING CONFIGURATION
# ============================================================

# Create logs directory if it doesn't exist
log_dir = Path(__file__).parent.parent.parent / 'logs'
log_dir.mkdir(exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'database_init.log'),
        logging.StreamHandler()
    ]
)

# Create logger instance
logger = logging.getLogger(__name__)

# ============================================================
# DATABASE CONFIGURATION
# ============================================================

# Database connection parameters
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'climate_litigation')
DB_USER = os.getenv('DB_USER', 'gusrodgs')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')

# Construct database URL
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# ============================================================
# SQLALCHEMY BASE AND MODELS
# ============================================================

# Create declarative base
Base = declarative_base()

# ============================================================
# TABLE DEFINITIONS
# ============================================================

class Case(Base):
    """
    Stores metadata about climate litigation cases.
    
    INPUT: Case metadata from Climate Case Chart database
    STORAGE: One record per unique case
    OUTPUT: Case information for analysis and citation linking
    """
    __tablename__ = 'cases'
    
    # Primary key
    case_id = Column(String(100), primary_key=True, comment="Unique case identifier from Climate Case Chart")
    
    # Basic case information
    case_name = Column(String(500), nullable=False, comment="Official case name")
    case_name_non_english = Column(String(500), comment="Case name in original language if non-English")
    case_number = Column(String(200), comment="Official court docket/reference number")
    
    # Jurisdictional information
    jurisdiction = Column(String(300), nullable=False, comment="Court jurisdiction")
    geographies = Column(String(300), comment="Geographic locations")
    geography_iso = Column(String(100), comment="ISO country codes")
    region = Column(String(50), comment="Global North or Global South classification")
    
    # Temporal information
    case_filing_year = Column(Float, comment="Year case was initially filed")
    document_filing_date = Column(DateTime, comment="Date decision was issued")
    last_event_date = Column(DateTime, comment="Most recent case activity date")
    
    # Case characteristics
    case_summary = Column(Text, comment="Brief description of case context")
    case_status = Column(String(500), comment="Current status of the case")
    case_outcome = Column(String(500), comment="Outcome/disposition")
    case_categories = Column(Text, comment="Thematic classification")
    
    # Language information
    language = Column(String(100), comment="Primary language of case documents")
    
    # Legal framework
    principal_laws = Column(Text, comment="Key legal provisions cited")
    at_issue = Column(Text, comment="Main legal issues")
    
    # Links and references
    case_url = Column(String(500), comment="Link to Climate Case Chart page")
    
    # Extra Metadata
    metadata_data = Column(JSON, comment="Additional metadata from Excel")

    # System metadata
    created_at = Column(DateTime, default=datetime.utcnow, comment="Record creation timestamp")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="Record last update timestamp")
    
    # Relationships
    documents = relationship("Document", back_populates="case", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Case(case_id='{self.case_id}', name='{self.case_name[:50]}...')>"


class Document(Base):
    """
    Stores information about PDF documents and extraction metadata.
    
    INPUT: PDF documents linked to cases
    STORAGE: One record per document (multiple documents possible per case)
    OUTPUT: Document metadata and extraction status for processing pipeline
    """
    __tablename__ = 'documents'
    
    # Primary key
    document_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, 
                        comment="Auto-generated unique identifier")
    
    # Foreign key to cases
    case_id = Column(String(100), ForeignKey('cases.case_id', ondelete='CASCADE'), 
                    nullable=False, comment="Links to parent case")
    
    # Document information
    document_title = Column(String(500), comment="Title of the decision document")
    document_type = Column(String(100), comment="Type of document (Decision, Verdict, etc.)")
    document_date = Column(DateTime, comment="Date of the decision")
    document_summary = Column(Text, comment="Summary of specific decision")
    
    # URL and file information
    document_url = Column(String(500), comment="Link to Climate Case Chart document page")
    document_content_url = Column(String(500), comment="Direct link to PDF")
    pdf_file_path = Column(String(500), comment="Local storage path for downloaded PDF")
    
    # Download status
    pdf_downloaded = Column(Boolean, default=False, comment="Download success flag")
    download_date = Column(DateTime, comment="When PDF was downloaded")
    download_error = Column(Text, comment="Error message if download failed")
    
    # PDF metadata
    file_size_bytes = Column(Integer, comment="PDF file size in bytes")
    page_count = Column(Integer, comment="Number of pages in PDF")
    is_scanned = Column(Boolean, comment="Flag for scanned PDFs (require OCR)")
    
    # Classification
    is_decision = Column(Boolean, default=None, comment="True if document is a decision, False otherwise")
    classification_confidence = Column(Float, comment="Confidence score of classification")
    decision_classification_method = Column(String(50), comment="Method used for classification (document_title or llm_sonnet)")
    decision_classification_confidence = Column(Float, comment="Confidence score of decision classification")
    decision_classification_date = Column(DateTime, comment="When classification was performed")
    
    # Extra Metadata
    metadata_data = Column(JSON, comment="Additional metadata from Excel")
    
    # System metadata
    created_at = Column(DateTime, default=datetime.utcnow, comment="Record creation timestamp")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, 
                       comment="Record last update timestamp")
    
    # Relationships
    case = relationship("Case", back_populates="documents")
    extracted_texts = relationship("ExtractedText", back_populates="document", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Document(document_id='{self.document_id}', case_id='{self.case_id}')>"


class ExtractedText(Base):
    """
    Stores extracted text content from PDFs.
    
    INPUT: Raw text extracted from PDF documents
    ALGORITHM: Stores both raw and processed versions
    OUTPUT: Text content for citation analysis
    """
    __tablename__ = 'extracted_text'
    
    # Primary key
    text_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
                    comment="Auto-generated unique identifier")
    
    # Foreign key to documents
    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.document_id', ondelete='CASCADE'),
                        nullable=False, comment="Links to parent document")
    
    # Extraction metadata
    extraction_method = Column(String(50), comment="Library used: PyPDF2, pdfplumber, or PyMuPDF")
    extraction_date = Column(DateTime, default=datetime.utcnow, comment="When extraction was performed")
    extraction_quality = Column(String(20), comment="Quality assessment: excellent/good/fair/poor/failed")
    extraction_notes = Column(Text, comment="Any warnings or issues during extraction")
    
    # Text content
    raw_text = Column(Text, comment="Original extracted text, unprocessed")
    processed_text = Column(Text, comment="Cleaned and preprocessed text")
    
    # Text statistics
    word_count = Column(Integer, comment="Number of words in text")
    character_count = Column(Integer, comment="Number of characters")
    paragraph_count = Column(Integer, comment="Number of paragraphs")
    sentence_count = Column(Integer, comment="Number of sentences")
    
    # Language detection
    language_detected = Column(String(10), comment="Auto-detected language code (ISO 639-1)")
    language_confidence = Column(Float, comment="Confidence score for language detection")
    
    # System metadata
    created_at = Column(DateTime, default=datetime.utcnow, comment="Record creation timestamp")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
                       comment="Record last update timestamp")
    
    # Relationships
    document = relationship("Document", back_populates="extracted_texts")
    
    def __repr__(self):
        return f"<ExtractedText(text_id='{self.text_id}', document_id='{self.document_id}', quality='{self.extraction_quality}')>"


# Legacy tables (Citation, TextSection, ProcessingLog) removed as per cleanup plan


class CitationExtractionPhased(Base):
    """
    Model for phased citation extraction results (v5).
    Stores individual citations with full phase tracking.
    """
    __tablename__ = 'citation_extraction_phased'
    
    extraction_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.document_id', ondelete='CASCADE'), nullable=False)
    case_id = Column(String(100), ForeignKey('cases.case_id', ondelete='CASCADE'))
    
    # Phase 1: Source Jurisdiction
    source_jurisdiction = Column(String(200))
    source_region = Column(String(50))
    
    # Phase 2: Extraction Results
    case_name = Column(String(500))
    raw_citation_text = Column(Text)
    raw_citation_text = Column(Text)
    section_heading = Column(String(500))
    location_in_document = Column(String(50))
    
    # Phase 3: Origin Identification
    case_law_origin = Column(String(200))
    case_law_region = Column(String(50))
    origin_identification_tier = Column(Integer)
    origin_confidence = Column(DECIMAL(3,2))
    
    # Phase 4: Classification
    citation_type = Column(String(50))
    is_cross_jurisdictional = Column(Boolean)
    
    # Extended Metadata
    cited_court = Column(String(500))
    cited_year = Column(Integer)
    cited_case_citation = Column(String(500))
    
    # Citation Context
    # Citation Context
    # full_paragraph, position_in_document, start/end_char_index removed in v5.4
    
    # Processing Metadata
    phase_2_model = Column(String(50), default='claude-haiku-4.5')
    phase_3_model = Column(String(50))
    phase_4_model = Column(String(50), default='claude-haiku-4.5')
    processing_time_seconds = Column(DECIMAL(10,2))
    api_calls_used = Column(Integer)
    
    # Quality Control
    requires_manual_review = Column(Boolean, default=False)
    manual_review_reason = Column(Text)
    reviewed_by = Column(String(100))
    reviewed_at = Column(TIMESTAMP)
    
    # Timestamps
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)


class CitationExtractionPhasedSummary(Base):
    """
    Model for document-level extraction summary (v5).
    Stores aggregate metrics per document.
    """
    __tablename__ = 'citation_extraction_phased_summary'
    
    summary_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.document_id', ondelete='CASCADE'), nullable=False, unique=True)
    
    # Processing Results
    total_references_extracted = Column(Integer, default=0)
    foreign_citations_count = Column(Integer, default=0)
    international_citations_count = Column(Integer, default=0)
    foreign_international_citations_count = Column(Integer, default=0)
    
    # API Usage
    total_api_calls = Column(Integer, default=0)
    total_tokens_input = Column(Integer, default=0)
    total_tokens_output = Column(Integer, default=0)
    total_cost_usd = Column(DECIMAL(10,4), default=0.0000)
    
    # Processing Metadata
    extraction_started_at = Column(TIMESTAMP)
    extraction_completed_at = Column(TIMESTAMP)
    total_processing_time_seconds = Column(DECIMAL(10,2))
    extraction_success = Column(Boolean, default=False)
    extraction_error = Column(Text)
    
    # Quality Metrics
    average_confidence = Column(DECIMAL(3,2))
    items_requiring_review = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============================================================
# DATABASE INITIALIZATION FUNCTIONS
# ============================================================

def init_database(reset: bool = False, verbose: bool = True) -> bool:
    """
    Initialize or reset the PostgreSQL database with proper schema.
    
    INPUT:
    - reset (bool): If True, drops all existing tables before creating new ones
    - verbose (bool): If True, prints detailed progress messages
    
    ALGORITHM:
    1. Connects to PostgreSQL database
    2. If reset=True, drops all existing tables using CASCADE
    3. Creates all tables defined in Base.metadata
    4. Creates indexes for optimization
    5. Verifies table creation
    
    OUTPUT:
    - bool: True if successful, False otherwise
    """
    try:
        logger.info("=" * 60)
        if verbose:
            print("\n" + "=" * 60)
            print("DATABASE INITIALIZATION")
            print("=" * 60)
        
        # Create engine
        engine = create_engine(DATABASE_URL, echo=False)
        
        # Reset database if requested
        if reset:
            logger.warning("⚠️  Dropping existing tables...")
            if verbose:
                print("\n⚠️  WARNING: Dropping all existing tables...")
            
            # Drop all tables with CASCADE to handle foreign key dependencies
            with engine.begin() as conn:
                # Drop tables manually in correct order (children first)
                logger.info("Dropping tables with CASCADE...")
                conn.execute(text("DROP TABLE IF EXISTS citation_extraction_phased_summary CASCADE;"))
                conn.execute(text("DROP TABLE IF EXISTS citation_extraction_phased CASCADE;"))
                conn.execute(text("DROP TABLE IF EXISTS citations CASCADE;")) # Legacy
                conn.execute(text("DROP TABLE IF EXISTS citation_extractions CASCADE;")) # Legacy
                conn.execute(text("DROP TABLE IF EXISTS text_sections CASCADE;")) # Legacy
                conn.execute(text("DROP TABLE IF EXISTS extracted_text CASCADE;"))
                conn.execute(text("DROP TABLE IF EXISTS extracted_texts CASCADE;")) # Duplicate
                conn.execute(text("DROP TABLE IF EXISTS documents CASCADE;"))
                conn.execute(text("DROP TABLE IF EXISTS cases CASCADE;"))
                conn.execute(text("DROP TABLE IF EXISTS processing_log CASCADE;")) # Legacy
                conn.execute(text("DROP TABLE IF EXISTS extraction_log CASCADE;")) # Legacy
                conn.execute(text("DROP TABLE IF EXISTS keywords_tags CASCADE;")) # Legacy
                
            logger.info("✓ All tables dropped successfully")
            if verbose:
                print("✓ All tables dropped successfully")
        
        # Create all tables
        logger.info("Creating tables...")
        if verbose:
            print("\n📊 Creating database tables...")
        
        Base.metadata.create_all(engine)
        
        logger.info("✓ All tables created successfully")
        if verbose:
            print("✓ All tables created successfully")
        
        # Create additional indexes
        logger.info("Creating indexes...")
        if verbose:
            print("\n🔍 Creating indexes for query optimization...")
        
        with engine.begin() as conn:
            # Indexes for cases table
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_cases_region 
                ON cases(region);
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_cases_jurisdiction 
                ON cases(jurisdiction);
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_cases_geography_iso 
                ON cases(geography_iso);
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_cases_filing_year 
                ON cases(case_filing_year);
            """))
            
            # Indexes for documents table
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_documents_case_id 
                ON documents(case_id);
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_documents_is_scanned 
                ON documents(is_scanned);
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_documents_downloaded 
                ON documents(pdf_downloaded);
            """))
            
            # Indexes for extracted_text table
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_extracted_text_document_id 
                ON extracted_text(document_id);
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_extracted_text_quality 
                ON extracted_text(extraction_quality);
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_extracted_text_language 
                ON extracted_text(language_detected);
            """))
            
            # Indexes for citation_extraction_phased table
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_citation_phased_document_id 
                ON citation_extraction_phased(document_id);
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_citation_phased_case_id 
                ON citation_extraction_phased(case_id);
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_citation_phased_type 
                ON citation_extraction_phased(citation_type);
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_citation_phased_origin 
                ON citation_extraction_phased(case_law_origin);
            """))
        
        logger.info("✓ All indexes created successfully")
        if verbose:
            print("✓ All indexes created successfully")
        
        # Verify tables were created
        logger.info("Verifying table creation...")
        if verbose:
            print("\n✓ Verifying database structure...")
        
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        expected_tables = ['cases', 'documents', 'extracted_text', 
                          'citation_extraction_phased', 'citation_extraction_phased_summary']
        
        missing_tables = set(expected_tables) - set(tables)
        
        if missing_tables:
            logger.error(f"✗ Missing tables: {missing_tables}")
            if verbose:
                print(f"\n✗ ERROR: Missing tables: {missing_tables}")
            return False
        
        logger.info(f"✓ All {len(expected_tables)} tables verified")
        if verbose:
            print(f"✓ All {len(expected_tables)} tables created and verified:")
            for table in expected_tables:
                print(f"  • {table}")
        
        # Display summary
        if verbose:
            print("\n📋 Database Summary:")
            print(f"  • Database: {DB_NAME}")
            print(f"  • Host: {DB_HOST}:{DB_PORT}")
            print(f"  • Tables: {len(expected_tables)}")
            print(f"  • Status: ✓ Ready for data import")
        
        logger.info("=" * 60)
        logger.info("✓ Database initialization completed successfully!")
        if verbose:
            print("\n" + "=" * 60)
            print("✓ DATABASE INITIALIZATION COMPLETED SUCCESSFULLY!")
            print("=" * 60 + "\n")
        
        return True
        
    except Exception as e:
        logger.error(f"\n✗ Database initialization failed: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        if verbose:
            print(f"\n✗ ERROR: Database initialization failed!")
            print(f"Error: {e}")
            print("\nPlease check the log file for details:")
            print(f"  {log_dir / 'database_init.log'}")
        return False


def reset_database() -> bool:
    """
    Reset database with user confirmation.
    
    ALGORITHM:
    1. Prompts user for confirmation
    2. If confirmed, calls init_database with reset=True
    3. If cancelled, returns False
    
    OUTPUT:
    - bool: True if reset successful, False if cancelled or failed
    """
    response = input("Are you sure you want to reset the database? Type 'yes' to confirm: ")
    if response.lower() == 'yes':
        return init_database(reset=True)
    else:
        print("Database reset cancelled.")
        return False


def get_database_info(verbose: bool = True) -> dict:
    """
    Get information about current database state.
    
    ALGORITHM:
    1. Connects to database
    2. Queries table existence and row counts
    3. Returns summary information
    
    OUTPUT:
    - dict: Database information including table names and row counts
    """
    try:
        engine = create_engine(DATABASE_URL, echo=False)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        info = {
            'database': DB_NAME,
            'host': f"{DB_HOST}:{DB_PORT}",
            'tables': tables,
            'table_count': len(tables)
        }
        
        if verbose:
            print("\n" + "=" * 60)
            print("DATABASE INFORMATION")
            print("=" * 60)
            print(f"\nDatabase: {info['database']}")
            print(f"Host: {info['host']}")
            print(f"Tables: {info['table_count']}")
            
            if tables:
                print("\nExisting tables:")
                for table in tables:
                    print(f"  • {table}")
            else:
                print("\nNo tables found. Database may need initialization.")
            
            print("=" * 60 + "\n")
        
        return info
        
    except Exception as e:
        logger.error(f"Failed to get database info: {e}")
        if verbose:
            print(f"\n✗ ERROR: Failed to connect to database")
            print(f"Error: {e}")
        return {}


# ============================================================
# MAIN EXECUTION
# ============================================================

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Initialize or reset the Climate Litigation database"
    )
    parser.add_argument(
        '--reset',
        action='store_true',
        help='Reset database (drops all existing tables)'
    )
    parser.add_argument(
        '--info',
        action='store_true',
        help='Display database information'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress verbose output'
    )
    
    args = parser.parse_args()
    
    verbose = not args.quiet
    
    if args.info:
        # Display database information
        get_database_info(verbose=verbose)
    elif args.reset:
        # Reset database with confirmation
        reset_database()
    else:
        # Initialize database (create tables if they don't exist)
        init_database(reset=False, verbose=verbose)