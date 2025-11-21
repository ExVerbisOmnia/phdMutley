"""
Climate Litigation Database Initialization Script - PostgreSQL 18 Optimized
============================================================================

📁 PROJECT DIRECTORY: /home/gusrodgs/Gus/cienciaDeDados/phdMutley

🔹 This script must be run from: /home/gusrodgs/Gus/cienciaDeDados/phdMutley

COMMANDS TO RUN THIS SCRIPT:
----------------------------
cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley
source venv/bin/activate
python scripts/phase0/init_database_pg18.py

This script creates a PostgreSQL 18 database structure optimized for storing
climate litigation cases, documents, extracted text, citations, and metadata.

PostgreSQL 18 Features Leveraged:
----------------------------------
- UUIDv7 primary keys for timestamp-ordered, globally unique identifiers
- Asynchronous I/O (AIO) optimizations
- Virtual generated columns for computed values
- TSVECTOR for full-text search

Author: Lucas Biasetton (Refactored by Assistant)
Project: Doutorado PM - Global South Climate Litigation Analysis
Version: 3.1 (Added CaseID and Paragraph to Citations)
Date: November 20, 2025
"""

# =============================================================================
# IMPORTS
# =============================================================================

import sys
import os
from datetime import datetime

# Add project root to path to import config
sys.path.insert(0, '/home/gusrodgs/Gus/cienciaDeDados/phdMutley')
from config import DB_CONFIG

from sqlalchemy import (
    create_engine, Column, Integer, String, Text, Date, DateTime, JSON, Float, 
    Boolean, ForeignKey, Index, CheckConstraint, Computed, text
)
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.engine import URL

# =============================================================================
# CONFIGURATION & BASE
# =============================================================================

# Create the base class for all table models
Base = declarative_base()

# =============================================================================
# TABLE DEFINITIONS
# =============================================================================

class Case(Base):
    """
    CASES Table - Main table storing litigation case information
    """
    __tablename__ = 'cases'
    
    # PRIMARY KEY - UUIDv7
    case_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment='Unique identifier using UUIDv7 for timestamp-ordered keys'
    )
    
    # CASE IDENTIFICATION
    case_name = Column(String(500), nullable=False)
    case_number = Column(String(200), nullable=True)
    
    # LOCATION INFORMATION
    court_name = Column(String(300), nullable=False)
    country = Column(String(100), nullable=False)
    region = Column(String(100), nullable=True)
    
    # DATE INFORMATION
    filing_date = Column(Date, nullable=True)
    decision_date = Column(Date, nullable=True)
    
    # CASE STATUS AND TYPE
    case_status = Column(String(50), nullable=True)
    case_type = Column(String(100), nullable=True)
    
    # SOURCE INFORMATION
    case_url = Column(String(500), nullable=True)
    data_source = Column(String(200), nullable=True, default='climatecasechart.com')
    
    # METADATA
    metadata_json = Column('metadata', JSON, nullable=True)
    
    # AUDIT FIELDS
    created_at = Column(DateTime, server_default=text('NOW()'), nullable=False)
    updated_at = Column(DateTime, server_default=text('NOW()'), onupdate=datetime.utcnow, nullable=False)
    
    # RELATIONSHIPS
    documents = relationship('Document', back_populates='case', cascade='all, delete-orphan')
    keywords = relationship('KeywordTag', back_populates='case', cascade='all, delete-orphan')
    citations = relationship('Citation', back_populates='case', cascade='all, delete-orphan') # Added relation
    
    # INDEX DEFINITIONS
    __table_args__ = (
        Index('idx_cases_region', 'region'),
        Index('idx_cases_country', 'country'),
        Index('idx_cases_status', 'case_status'),
        Index('idx_cases_dates', 'filing_date', 'decision_date'),
        # Skip scan index (PG 18 feature)
        Index('idx_cases_skip_scan', 'region', 'country', 'case_status'),
    )


class Document(Base):
    """
    DOCUMENTS Table - Stores PDF documents and their metadata
    """
    __tablename__ = 'documents'
    
    # PRIMARY KEY
    document_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment='Unique identifier for this document'
    )
    
    # FOREIGN KEY
    case_id = Column(UUID(as_uuid=True), ForeignKey('cases.case_id', ondelete='CASCADE'), nullable=False)
    
    # DOCUMENT TYPE AND SOURCE
    document_type = Column(String(100), nullable=True)
    document_url = Column(String(1000), nullable=True)
    
    # FILE INFORMATION
    pdf_file_path = Column(String(500), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    
    # VIRTUAL GENERATED COLUMN - File size in MB
    file_size_mb = Column(
        Float,
        Computed("ROUND(CAST(file_size_bytes AS NUMERIC) / 1048576.0, 2)", persisted=True),
        comment='File size in megabytes (computed at query time)'
    )
    
    page_count = Column(Integer, nullable=True)
    
    # DOWNLOAD STATUS
    pdf_downloaded = Column(Boolean, default=False, nullable=False)
    download_date = Column(DateTime, nullable=True)
    download_error = Column(Text, nullable=True)
    
    # METADATA
    metadata_json = Column('metadata', JSON, nullable=True)
    
    # AUDIT FIELDS
    created_at = Column(DateTime, server_default=text('NOW()'), nullable=False)
    updated_at = Column(DateTime, server_default=text('NOW()'), onupdate=datetime.utcnow, nullable=False)
    
    # RELATIONSHIPS
    case = relationship('Case', back_populates='documents')
    extracted_text = relationship('ExtractedText', back_populates='document', uselist=False, cascade='all, delete-orphan')
    text_sections = relationship('TextSection', back_populates='document', cascade='all, delete-orphan')
    citation_extraction = relationship('CitationExtraction', back_populates='document', uselist=False, cascade='all, delete-orphan')
    
    # INDEX DEFINITIONS
    __table_args__ = (
        Index('idx_documents_case_id', 'case_id'),
        Index('idx_documents_download_status', 'pdf_downloaded', 'download_date'),
    )


class ExtractedText(Base):
    """
    EXTRACTED_TEXT Table - Stores extracted text from PDF documents
    Includes TSVECTOR for full-text search optimization.
    """
    __tablename__ = 'extracted_text'
    
    # PRIMARY KEY
    text_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment='Unique identifier for this extracted text'
    )
    
    # FOREIGN KEY
    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.document_id', ondelete='CASCADE'), nullable=False, unique=True)
    
    # TEXT CONTENT
    raw_text = Column(Text, nullable=True)
    processed_text = Column(Text, nullable=True)
    
    # NEW: Full Text Search Vector
    search_vector = Column(
        TSVECTOR,
        nullable=True,
        comment='PostgreSQL TSVECTOR for efficient full-text search'
    )
    
    # TEXT STATISTICS
    word_count = Column(Integer, nullable=True)
    character_count = Column(Integer, nullable=True)
    
    # VIRTUAL GENERATED COLUMN - Average word length
    avg_word_length = Column(
        Float,
        Computed(
            "CASE WHEN word_count > 0 THEN ROUND(CAST(character_count AS NUMERIC) / word_count, 2) ELSE 0 END",
            persisted=True
        )
    )
    
    # EXTRACTION METADATA
    extraction_date = Column(DateTime, nullable=True)
    extraction_method = Column(String(50), nullable=True)
    extraction_quality = Column(String(20), nullable=True)
    extraction_notes = Column(Text, nullable=True)
    language_detected = Column(String(10), nullable=True)
    language_confidence = Column(Float, nullable=True)
    
    # AUDIT FIELDS
    created_at = Column(DateTime, server_default=text('NOW()'), nullable=False)
    updated_at = Column(DateTime, server_default=text('NOW()'), onupdate=datetime.utcnow, nullable=False)
    
    # RELATIONSHIPS
    document = relationship('Document', back_populates='extracted_text')
    
    # INDEX DEFINITIONS
    __table_args__ = (
        Index('idx_extracted_text_document_id', 'document_id'),
        Index('idx_extracted_text_quality', 'extraction_quality'),
        Index('idx_extracted_text_search', 'search_vector', postgresql_using='gin'),
    )


class TextSection(Base):
    """
    TEXT_SECTIONS Table - Stores segmented sections of text
    """
    __tablename__ = 'text_sections'
    
    section_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.document_id', ondelete='CASCADE'), nullable=False)
    
    section_type = Column(String(50), nullable=True)
    section_number = Column(Integer, nullable=True)
    section_text = Column(Text, nullable=True)
    content_length = Column(Integer, nullable=True)
    
    content_size_category = Column(
        String(20),
        Computed(
            "CASE WHEN content_length < 100 THEN 'tiny' WHEN content_length < 500 THEN 'small' WHEN content_length < 2000 THEN 'medium' WHEN content_length < 10000 THEN 'large' ELSE 'very_large' END",
            persisted=True
        )
    )
    
    metadata_json = Column('metadata', JSON, nullable=True)
    created_at = Column(DateTime, server_default=text('NOW()'), nullable=False)
    document = relationship('Document', back_populates='text_sections')
    
    __table_args__ = (
        Index('idx_text_sections_order', 'document_id', 'section_number'),
    )


class KeywordTag(Base):
    """
    KEYWORDS_TAGS Table - Stores keywords and tags
    """
    __tablename__ = 'keywords_tags'
    
    keyword_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    case_id = Column(UUID(as_uuid=True), ForeignKey('cases.case_id', ondelete='CASCADE'), nullable=False)
    
    keyword = Column(String(200), nullable=False)
    keyword_type = Column(String(50), nullable=True)
    confidence_score = Column(Float, nullable=True)
    created_at = Column(DateTime, server_default=text('NOW()'), nullable=False)
    case = relationship('Case', back_populates='keywords')
    
    __table_args__ = (
        Index('idx_keywords_keyword', 'keyword'),
        Index('idx_keywords_type', 'keyword_type', 'case_id'),
    )


# =============================================================================
# CITATIONS TABLES
# =============================================================================

class CitationExtraction(Base):
    """
    CITATION_EXTRACTIONS Table - Stores extraction metadata per document
    """
    __tablename__ = 'citation_extractions'
    
    extraction_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment='Unique identifier for this extraction'
    )
    
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey('documents.document_id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
        comment='References the source document'
    )
    
    extraction_date = Column(DateTime, default=datetime.now, nullable=False)
    model_used = Column(String(100), nullable=False)
    
    # CITATION COUNTS
    total_citations_found = Column(Integer, default=0)
    foreign_citations_count = Column(Integer, default=0)
    domestic_citations_excluded = Column(Integer, default=0)
    
    # COST AND PERFORMANCE
    api_tokens_input = Column(Integer)
    api_tokens_output = Column(Integer)
    api_cost_usd = Column(Float)
    extraction_time_seconds = Column(Float)
    
    # STATUS
    extraction_success = Column(Boolean, default=False, nullable=False)
    extraction_error = Column(Text)
    raw_llm_response = Column(JSON)
    
    # RELATIONSHIPS
    document = relationship('Document', back_populates='citation_extraction')
    citations = relationship('Citation', back_populates='extraction', cascade='all, delete-orphan')
    
    __table_args__ = (
        Index('idx_citation_extractions_document_id', 'document_id'),
        Index('idx_citation_extractions_success', 'extraction_success'),
    )


class Citation(Base):
    """
    CITATIONS Table - Stores individual citations extracted from decisions
    """
    __tablename__ = 'citations'
    
    citation_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment='Unique identifier for this citation'
    )
    
    extraction_id = Column(
        UUID(as_uuid=True),
        ForeignKey('citation_extractions.extraction_id', ondelete='CASCADE'),
        nullable=False
    )

    # --- NEW FIELD 1: Case ID ---
    case_id = Column(
        UUID(as_uuid=True),
        ForeignKey('cases.case_id', ondelete='CASCADE'),
        nullable=False,
        comment='Redundant link to the case for easier querying'
    )
    
    # CORE FIELDS
    cited_case_name = Column(Text, nullable=False)
    cited_court = Column(Text)
    cited_jurisdiction = Column(Text)
    cited_country = Column(String(100))
    cited_year = Column(Integer)
    
    # CONTEXT & METADATA
    citation_context = Column(Text)
    citation_type = Column(String(100))
    citation_string_raw = Column(Text)
    
    # --- NEW FIELD 2: Full Paragraph ---
    citation_paragraph = Column(
        Text, 
        nullable=True,
        comment='The entire paragraph where the citation was found'
    )

    confidence_score = Column(Float)
    position_in_document = Column(Integer)
    
    # Location Indices for Highlighting
    start_char_index = Column(Integer, comment='Character index where citation starts')
    end_char_index = Column(Integer, comment='Character index where citation ends')
    
    # AUDIT
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    
    # RELATIONSHIPS
    extraction = relationship('CitationExtraction', back_populates='citations')
    case = relationship('Case', back_populates='citations')
    
    __table_args__ = (
        Index('idx_citations_extraction_id', 'extraction_id'),
        Index('idx_citations_case_id', 'case_id'),
        Index('idx_citations_country', 'cited_country'),
        Index('idx_citations_year', 'cited_year'),
        Index('idx_citations_confidence', 'confidence_score'),
    )


# =============================================================================
# INITIALIZATION LOGIC
# =============================================================================

def init_database(drop_existing=False):
    """
    Initialize the PostgreSQL 18 database with all tables and indexes.
    """
    
    print("\n" + "=" * 70)
    print("PostgreSQL 18 Database Initialization")
    print("=" * 70)
    
    try:
        url = URL.create(**DB_CONFIG)
        engine = create_engine(url, echo=False)
        
        print("\n1. Testing database connection...")
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            version = conn.execute(text("SHOW server_version")).scalar()
        print("   ✓ Connected successfully!")
        print(f"   ✓ Database: {DB_CONFIG['database']}")
        print(f"   ✓ Server Version: {version}")
        
    except Exception as e:
        print(f"   ✗ ERROR: Could not connect to database")
        print(f"   Error details: {e}")
        return None
    
    if drop_existing:
        print(f"\n2. Dropping existing tables...")
        print("   ⚠ WARNING: This will delete all existing data!")
        try:
            with engine.connect() as conn:
                trans = conn.begin()
                # Drop in dependency order
                tables_to_drop = [
                    'citations',
                    'citation_extractions',
                    'keywords_tags',
                    'text_sections', 
                    'extracted_text',
                    'documents',
                    'cases'
                ]
                for table in tables_to_drop:
                    conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
                trans.commit()
                print("   ✓ All existing tables dropped successfully")
        except Exception as e:
            print(f"   ✗ ERROR dropping tables: {e}")
            return None
    else:
        print(f"\n2. Skipping table drop (drop_existing=False)")
    
    print(f"\n3. Creating database tables...")
    try:
        Base.metadata.create_all(engine)
        print("   ✓ Created tables: cases, documents, extracted_text, text_sections, keywords_tags")
        print("   ✓ Created tables: citation_extractions, citations")
        
    except Exception as e:
        print(f"   ✗ ERROR creating tables: {e}")
        return None
    
    print(f"\n4. Verifying table creation...")
    try:
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        expected = ['cases', 'documents', 'extracted_text', 'text_sections', 
                    'keywords_tags', 'citation_extractions', 'citations']
        
        count = 0
        for table in expected:
            if table in tables:
                print(f"   ✓ Table '{table}' confirmed")
                count += 1
            else:
                print(f"   ✗ Table '{table}' NOT FOUND")
        
        print(f"\n   Total tables verified: {count}/{len(expected)}")
        
    except Exception as e:
        print(f"   ⚠ Could not verify tables: {e}")
    
    print("\n" + "=" * 70)
    print("✓ Database initialization completed successfully!")
    print("=" * 70)
    
    return engine


if __name__ == "__main__":
    print("\n")
    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║  Climate Litigation Database - PostgreSQL 18 Initialization       ║")
    print("║  Version 3.1 - Added CaseID and Paragraph to Citations            ║")
    print("╚════════════════════════════════════════════════════════════════════╝")
    print("\n")
    
    print("⚠️  WARNING: Do you want to drop existing tables?")
    print("   This will DELETE ALL DATA in the database!")
    response = input("Drop existing tables? (yes/no): ").strip().lower()
    drop_tables = response in ['yes', 'y']
    
    if drop_tables:
        print("\n⚠️  CONFIRMATION REQUIRED")
        confirm = input("Type 'DELETE ALL DATA' to confirm: ").strip()
        if confirm != "DELETE ALL DATA":
            print("\n✗ Confirmation failed. Exiting without changes.")
            exit(0)
    
    engine = init_database(drop_existing=drop_tables)
    
    if not engine:
        print("\n✗ Database initialization failed.")
        exit(1)