#!/usr/bin/env python3
"""
Database Schema Initialization for Climate Litigation Database
===============================================================
Creates PostgreSQL tables using SQLAlchemy ORM for climate litigation citation analysis.

ðŸ" Run from: /home/gusrodgs/Gus/cienciaDeDados/phdMutley
Command: python scripts/phase0/init_database.py

Tables Created:
- cases: Case metadata
- documents: PDF documents linked to cases
- extracted_texts: Text extracted from PDFs
- citations: Cross-jurisdictional citations extracted from decisions
- extraction_log: Processing audit trail

Author: Lucas Biasetton (Refactored by Assistant)
Project: Doutorado PM
Version: 3.0 (Added document_id to Citations)
Date: November 2025
"""

import sys
import os
from sqlalchemy import (
    create_engine, Column, String, Integer, Boolean, DateTime, Text, Float,
    ForeignKey, Index, JSON
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.engine import URL
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import logging

# ============================================================================
# CONFIGURATION & IMPORTS
# ============================================================================

# Add project root to path
sys.path.insert(0, '/home/gusrodgs/Gus/cienciaDeDados/phdMutley')
from config import DB_CONFIG, LOGS_DIR

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / 'database_init.log'),
        logging.StreamHandler()
    ]
)

# ============================================================================
# DATABASE BASE
# ============================================================================

Base = declarative_base()

# ============================================================================
# TABLE MODELS
# ============================================================================

class Case(Base):
    """
    Represents a climate litigation case with complete metadata.
    Primary entity linking to documents and citations.
    """
    __tablename__ = 'cases'
    
    # Primary Key (UUID generated deterministically from Case ID)
    case_id = Column(UUID(as_uuid=True), primary_key=True)
    
    # Core Identification
    case_name = Column(String, nullable=False, index=True)
    case_number = Column(String)
    
    # Jurisdictional Information
    court_name = Column(String, nullable=False)
    country = Column(String, nullable=False, index=True)
    region = Column(String, nullable=False, index=True)  # Global North/South/International
    
    # Temporal Information
    filing_date = Column(DateTime)
    decision_date = Column(DateTime, index=True)
    
    # Status and Metadata
    case_status = Column(String)
    case_url = Column(Text)
    data_source = Column(String, default='climatecasechart.com')

    # Extended Metadata (JSON)
    # Note: Python attribute is metadata_json, but database column is 'metadata'
    # This is because 'metadata' is reserved by SQLAlchemy's Declarative API
    metadata_json = Column('metadata', JSON)

    # Timestamps
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    
    # Relationships
    documents = relationship("Document", back_populates="case", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Case(id={self.case_id}, name='{self.case_name}', region='{self.region}')>"


class Document(Base):
    """
    Represents a PDF document (judicial decision) linked to a case.
    Tracks download status and metadata.
    """
    __tablename__ = 'documents'
    
    # Primary Key (UUID generated from Document ID)
    document_id = Column(UUID(as_uuid=True), primary_key=True)
    
    # Foreign Key to Case
    case_id = Column(UUID(as_uuid=True), ForeignKey('cases.case_id'), nullable=False, index=True)
    
    # Document Information
    document_type = Column(String, default='Decision')
    document_url = Column(Text)
    
    # Download Status
    pdf_file_path = Column(Text)
    pdf_downloaded = Column(Boolean, default=False, nullable=False)
    download_date = Column(DateTime)
    download_error = Column(Text)
    
    # File Metadata
    file_size_bytes = Column(Integer)
    page_count = Column(Integer)

    # Extended Metadata (JSON)
    # Note: Python attribute is metadata_json, but database column is 'metadata'
    # This is because 'metadata' is reserved by SQLAlchemy's Declarative API
    metadata_json = Column('metadata', JSON)

    # Timestamps
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    
    # Relationships
    case = relationship("Case", back_populates="documents")
    extracted_texts = relationship("ExtractedText", back_populates="document", cascade="all, delete-orphan")
    citations = relationship("Citation", back_populates="document", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Document(id={self.document_id}, case={self.case_id}, downloaded={self.pdf_downloaded})>"


class ExtractedText(Base):
    """
    Stores text extracted from PDF documents.
    Separates raw and processed versions.
    """
    __tablename__ = 'extracted_texts'
    
    # Primary Key
    text_id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign Key to Document
    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.document_id'), nullable=False, index=True)
    
    # Extraction Metadata
    extraction_method = Column(String)  # 'pdfplumber', 'PyMuPDF', 'PyPDF2'
    extraction_date = Column(DateTime, default=datetime.now)
    
    # Text Content
    raw_text = Column(Text)
    processed_text = Column(Text)
    
    # Quality Metrics
    word_count = Column(Integer)
    character_count = Column(Integer)  # Added to match extract_texts.py usage
    extraction_quality = Column(String)  # 'excellent', 'good', 'fair', 'poor', 'failed'
    extraction_notes = Column(Text)
    
    # Language Detection
    language_detected = Column(String)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    
    # Relationships
    document = relationship("Document", back_populates="extracted_texts")
    
    def __repr__(self):
        return f"<ExtractedText(id={self.text_id}, doc={self.document_id}, quality='{self.extraction_quality}')>"


class CitationExtraction(Base):
    """
    Tracks each citation extraction attempt with API usage metrics.
    One record per document processed for citation extraction.
    """
    __tablename__ = 'citation_extractions'
    
    # Primary Key
    extraction_id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign Key to Document
    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.document_id'), nullable=False, unique=True, index=True)
    
    # Extraction Metadata
    model_used = Column(String)
    extraction_success = Column(Boolean, default=False, nullable=False)
    extraction_error = Column(Text)
    extraction_time_seconds = Column(Float)
    
    # Citation Counts
    total_citations_found = Column(Integer, default=0)
    foreign_citations_count = Column(Integer, default=0)
    domestic_citations_excluded = Column(Integer, default=0)
    
    # API Usage Tracking
    api_tokens_input = Column(Integer)
    api_tokens_output = Column(Integer)
    api_cost_usd = Column(Float)
    
    # Raw LLM Response (JSON)
    raw_llm_response = Column(JSON)
    
    # Timestamp
    extraction_date = Column(DateTime, default=datetime.now, nullable=False)
    
    # Relationships
    citations = relationship("Citation", back_populates="extraction")
    
    def __repr__(self):
        return f"<CitationExtraction(id={self.extraction_id}, doc={self.document_id}, success={self.extraction_success})>"


class Citation(Base):
    """
    Represents a cross-jurisdictional citation extracted from a judicial decision.
    Links citing case to cited case with classification and confidence.
    
    VERSION 3.0: Added document_id to track which specific document contains the citation.
    """
    __tablename__ = 'citations'
    
    # Primary Key
    citation_id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign Keys
    extraction_id = Column(Integer, ForeignKey('citation_extractions.extraction_id'), nullable=False, index=True)
    case_id = Column(UUID(as_uuid=True), ForeignKey('cases.case_id'), nullable=False, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.document_id'), nullable=False, index=True)
    
    # Citation Information
    cited_case_name = Column(String, nullable=False)
    cited_court = Column(String)
    cited_jurisdiction = Column(String, index=True)
    cited_country = Column(String)
    cited_year = Column(Integer)
    cited_case_number = Column(String)
    
    # Classification
    citation_type = Column(String, nullable=False, index=True)  # 'Foreign Citation', 'International Citation', 'Foreign International Citation'
    confidence_score = Column(Float)
    
    # Citation Location in Document
    citation_string_raw = Column(Text)  # Exact citation text as found
    citation_paragraph = Column(Text)  # Full paragraph containing citation
    position_in_document = Column(Integer)  # Order of appearance
    start_char_index = Column(Integer)  # Character position start
    end_char_index = Column(Integer)  # Character position end
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    
    # Relationships
    case = relationship("Case")
    document = relationship("Document", back_populates="citations")
    extraction = relationship("CitationExtraction", back_populates="citations")
    
    def __repr__(self):
        return f"<Citation(id={self.citation_id}, case={self.case_id}, cited='{self.cited_case_name}', type='{self.citation_type}')>"


class ExtractionLog(Base):
    """
    Audit trail for all processing operations.
    Tracks downloads, extractions, and citation detection.
    """
    __tablename__ = 'extraction_log'
    
    # Primary Key
    log_id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign Key to Document
    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.document_id'), index=True)
    
    # Log Information
    stage = Column(String, nullable=False, index=True)  # 'download', 'extraction', 'citation_detection', 'preprocessing'
    status = Column(String, nullable=False, index=True)  # 'success', 'failure', 'warning'
    message = Column(Text)
    
    # Error Details
    error_type = Column(String)
    error_traceback = Column(Text)
    
    # Timestamp
    timestamp = Column(DateTime, default=datetime.now, nullable=False, index=True)
    
    def __repr__(self):
        return f"<ExtractionLog(id={self.log_id}, doc={self.document_id}, stage='{self.stage}', status='{self.status}')>"


# ============================================================================
# INDEXES
# ============================================================================

# Create indexes for common queries
Index('idx_cases_region_country', Case.region, Case.country)
Index('idx_citations_type_jurisdiction', Citation.citation_type, Citation.cited_jurisdiction)
Index('idx_citations_case_document', Citation.case_id, Citation.document_id)
Index('idx_log_document_stage', ExtractionLog.document_id, ExtractionLog.stage)

# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================

def init_database(drop_existing=False):
    """
    Initialize database schema.
    
    INPUT: 
        - drop_existing: Boolean, if True drops all tables before creating
    
    ALGORITHM:
        1. Connect to PostgreSQL
        2. Optionally drop existing tables
        3. Create all tables from SQLAlchemy models
        4. Create indexes
    
    OUTPUT: Success or error message
    """
    try:
        # Create database connection
        db_url = URL.create(**DB_CONFIG)
        engine = create_engine(db_url)
        
        logging.info("="*60)
        logging.info("DATABASE INITIALIZATION")
        logging.info("="*60)
        
        # Drop existing tables if requested
        if drop_existing:
            logging.warning("⚠ Dropping existing tables...")
            Base.metadata.drop_all(engine)
            logging.info("✓ Existing tables dropped")
        
        # Create all tables
        logging.info("Creating tables...")
        Base.metadata.create_all(engine)
        logging.info("✓ All tables created successfully")
        
        # Verify tables
        logging.info("\nVerifying table creation...")
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        expected_tables = ['cases', 'documents', 'extracted_texts', 'citations', 'citation_extractions', 'extraction_log']
        for table in expected_tables:
            if table in tables:
                logging.info(f"  ✓ {table}")
            else:
                logging.error(f"  ✗ {table} NOT FOUND")
        
        logging.info("\n" + "="*60)
        logging.info("✓ DATABASE INITIALIZATION COMPLETED")
        logging.info("="*60)
        
        return True
        
    except Exception as e:
        logging.error(f"\n✗ Database initialization failed: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return False


def reset_database():
    """
    Complete database reset - drops and recreates all tables.
    USE WITH CAUTION - destroys all data.
    """
    logging.warning("="*60)
    logging.warning("⚠⚠⚠ DATABASE RESET - ALL DATA WILL BE LOST ⚠⚠⚠")
    logging.warning("="*60)
    
    response = input("Are you sure you want to reset the database? Type 'yes' to confirm: ")
    
    if response.lower() == 'yes':
        return init_database(drop_existing=True)
    else:
        logging.info("Database reset cancelled")
        return False


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--reset':
        reset_database()
    else:
        init_database(drop_existing=False)
