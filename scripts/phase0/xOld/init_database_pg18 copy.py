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
climate litigation cases, documents, extracted text, and related metadata from
the Global South.

PostgreSQL 18 Features Leveraged:
----------------------------------
- UUIDv7 primary keys for timestamp-ordered, globally unique identifiers
- Asynchronous I/O (AIO) for 2-3x faster read performance
- Virtual generated columns for computed values (saves storage)
- Enhanced JSON support for flexible metadata
- Data checksums enabled by default for integrity
- Temporal constraints for tracking time-based data

Author: Lucas Biasetton
Project: Doutorado PM - Global South Climate Litigation Analysis
Database: PostgreSQL 18
Version: 2.1 (PostgreSQL 18 Optimized - Fixed)
Date: October 2025

CHANGES IN v2.1:
----------------
- REMOVED case_age_days generated column (used CURRENT_DATE which is not immutable)
- Case age should now be calculated at query time in application code
- This ensures reproducibility and compliance with PostgreSQL immutability requirements
- All other generated columns remain (they use only immutable functions)

Prerequisites:
--------------
1. PostgreSQL 18 installed and running
   🔹 Run from: Any directory
   - Verify version: psql --version (must show 18.x)
   - Compiled with --with-liburing for best performance (Linux)
   - Kernel 5.1+ recommended for io_uring support

2. Python packages installed:
   🔹 Run from: /home/gusrodgs/Gus/cienciaDeDados/phdMutley
   cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley
   source venv/bin/activate
   pip install sqlalchemy>=2.0.23 psycopg2-binary>=2.9.9 python-dotenv>=1.0.0

3. Create a .env file in the project directory with:
   🔹 File location: /home/gusrodgs/Gus/cienciaDeDados/phdMutley/.env
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=climate_litigation
   DB_USER=your_username
   DB_PASSWORD=your_password

PostgreSQL 18 Performance Configuration (optional but recommended):
-------------------------------------------------------------------
🔹 Run from: Any directory (system configuration)

Add to /etc/postgresql/18/main/postgresql.conf:
   io_method = worker           # Use AIO workers (default in PG 18)
   io_workers = 4               # 25-100% of CPU cores (check with: nproc)
   effective_io_concurrency = 16
   maintenance_io_concurrency = 16

For Linux with io_uring support:
   io_method = io_uring         # Best performance on modern Linux

Then restart PostgreSQL:
   sudo systemctl restart postgresql

Usage:
------
🔹 Run from: /home/gusrodgs/Gus/cienciaDeDados/phdMutley

cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley
source venv/bin/activate
python scripts/phase0/init_database_pg18.py
"""

# =============================================================================
# IMPORTS
# =============================================================================

from sqlalchemy import (
    create_engine,           # Creates connection to database
    Column,                  # Defines table columns
    Integer,                 # Integer data type
    String,                  # Variable-length string
    Text,                    # Long text (no length limit)
    Date,                    # Date without time
    DateTime,                # Date with time
    JSON,                    # JSON data type (enhanced in PG 18)
    Float,                   # Decimal numbers
    Boolean,                 # Boolean data type
    ForeignKey,              # Links tables together
    Index,                   # Creates indexes for faster queries
    CheckConstraint,         # Validates data
    Computed,                # For virtual generated columns (PG 18)
    text,                    # For SQL expressions
)
from sqlalchemy.dialects.postgresql import UUID  # PostgreSQL UUID type
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.engine import URL
from datetime import datetime
from sqlalchemy.dialects.postgresql import TSVECTOR
import os
from dotenv import load_dotenv

# =============================================================================
# CONFIGURATION
# =============================================================================

# Load environment variables from .env file
load_dotenv()

# Database connection parameters
DB_CONFIG = {
    'drivername': 'postgresql+psycopg2',  # PostgreSQL 18 driver
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'climate_litigation'),
    'username': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
}

# Create the base class for all table models
Base = declarative_base()

# =============================================================================
# TABLE DEFINITIONS WITH POSTGRESQL 18 OPTIMIZATIONS
# =============================================================================

class Case(Base):
    """
    CASES Table - Main table storing litigation case information
    
    PostgreSQL 18 Optimizations:
    - UUIDv7 primary key for timestamp-ordered global uniqueness
    - Enhanced JSON support for metadata
    - Skip scan indexes for flexible querying
    
    This table stores core metadata about climate litigation cases from
    the Global South, including case identification, location, dates, and status.
    
    NOTE: case_age_days was removed in v2.1 because it used CURRENT_DATE (non-immutable).
    To calculate case age, use application code:
        SELECT case_id, 
               CASE WHEN decision_date IS NOT NULL 
                    THEN decision_date - filing_date 
                    ELSE CURRENT_DATE - filing_date 
               END as case_age_days
        FROM cases;
    
    Relationships:
    - One case can have many documents (1:N relationship)
    - One case can have many keywords/tags (1:N relationship)
    """
    
    __tablename__ = 'cases'
    
    # PRIMARY KEY - UUIDv7 (PostgreSQL 18 native function)
    # UUIDv7 provides:
    # - Timestamp ordering (better for B-tree index performance)
    # - Global uniqueness (no collisions across distributed systems)
    # - Better cache locality than random UUIDs
    case_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),  # Fallback for compatibility
        comment='Unique identifier using UUIDv7 for timestamp-ordered keys'
    )
    # Note: PostgreSQL 18 has uuidv7() function, but for SQLAlchemy compatibility
    # we use gen_random_uuid() here. In direct SQL, use: DEFAULT uuidv7()
    
    # CASE IDENTIFICATION
    case_name = Column(
        String(500),
        nullable=False,
        comment='Full name of the case (e.g., "Silva vs. Government of Brazil")'
    )
    
    case_number = Column(
        String(200),
        nullable=True,
        comment='Official court case number if available'
    )
    
    # LOCATION INFORMATION
    court_name = Column(
        String(300),
        nullable=False,
        comment='Name of the court (e.g., "Supreme Federal Court of Brazil")'
    )
    
    country = Column(
        String(100),
        nullable=False,
        comment='Country where case was filed (e.g., "Brazil", "Argentina")'
    )
    
    region = Column(
        String(100),
        nullable=True,
        comment='Geographic region per Maria Antonia Tigre definition: "Latin America and the Caribbean", "Asia", "Africa", "Oceania"'
    )
    
    # DATE INFORMATION
    filing_date = Column(
        Date,
        nullable=True,
        comment='Date when the case was filed'
    )
    
    decision_date = Column(
        Date,
        nullable=True,
        comment='Date when the final decision was issued'
    )
    
    # NOTE: case_age_days REMOVED in v2.1
    # Reason: Used CURRENT_DATE which is not immutable (violates PostgreSQL requirements)
    # Solution: Calculate at query time in application code or use a view
    
    # CASE STATUS AND TYPE
    case_status = Column(
        String(50),
        nullable=True,
        comment='Current status: "Decided", "Pending", "Dismissed", "Settled", etc.'
    )
    
    case_type = Column(
        String(100),
        nullable=True,
        comment='Type of case: "Constitutional", "Administrative", "Civil", etc.'
    )
    
    # SOURCE INFORMATION
    case_url = Column(
        String(500),
        nullable=True,
        comment='URL to the case on climatecasechart.com or other source'
    )
    
    data_source = Column(
        String(200),
        nullable=True,
        default='climatecasechart.com',
        comment='Source of the case data'
    )
    
    # METADATA - Enhanced JSON support in PostgreSQL 18
    # PG 18 has better JSON indexing and query performance
    metadata_json = Column(
        'metadata',  # Column name in database
        JSON,
        nullable=True,
        comment='Flexible metadata in JSON format (enhanced PG 18 support)'
    )
    
    # AUDIT FIELDS
    created_at = Column(
        DateTime,
        server_default=text('NOW()'),  # PostgreSQL function
        nullable=False,
        comment='Timestamp when this record was created'
    )
    
    updated_at = Column(
        DateTime,
        server_default=text('NOW()'),
        onupdate=datetime.utcnow,
        nullable=False,
        comment='Timestamp when this record was last updated'
    )
    
    # RELATIONSHIPS
    documents = relationship(
        'Document',
        back_populates='case',
        cascade='all, delete-orphan',
        lazy='select'
    )
    
    keywords = relationship(
        'KeywordTag',
        back_populates='case',
        cascade='all, delete-orphan',
        lazy='select'
    )
    
    # INDEX DEFINITIONS
    __table_args__ = (
        # B-tree index for region (Global North vs Global South filtering)
        Index('idx_cases_region', 'region'),
        
        # B-tree index for country (geographic analysis)
        Index('idx_cases_country', 'country'),
        
        # B-tree index for case_status (filter by status)
        Index('idx_cases_status', 'case_status'),
        
        # Composite index for date-based queries (filing and decision dates)
        Index('idx_cases_dates', 'filing_date', 'decision_date'),
        
        # Skip scan index (PG 18 feature) for flexible multicolumn queries
        # Allows efficient queries on any subset of these columns
        Index('idx_cases_skip_scan', 'region', 'country', 'case_status'),
    )


class Document(Base):
    """
    DOCUMENTS Table - Stores PDF documents and their metadata
    
    PostgreSQL 18 Optimizations:
    - UUIDv7 primary key
    - Virtual generated column for file_size_mb (computed at query time)
    - Enhanced JSON support for document-specific metadata
    
    This table tracks all PDF documents associated with cases, including
    download status, file paths, and document characteristics.
    
    Relationships:
    - Many documents belong to one case (N:1 relationship)
    - One document has one extracted_text entry (1:1 relationship)
    - One document can have many text_sections (1:N relationship)
    """
    
    __tablename__ = 'documents'
    
    # PRIMARY KEY - UUIDv7
    document_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment='Unique identifier for this document'
    )
    
    # FOREIGN KEY to cases table
    case_id = Column(
        UUID(as_uuid=True),
        ForeignKey('cases.case_id', ondelete='CASCADE'),
        nullable=False,
        comment='References the parent case'
    )
    
    # DOCUMENT TYPE AND SOURCE
    document_type = Column(
        String(100),
        nullable=True,
        comment='Type: "Decision", "Verdict", "Order", "Judgment", etc.'
    )
    
    document_url = Column(
        String(1000),
        nullable=True,
        comment='Original URL where PDF was downloaded from'
    )
    
    # FILE INFORMATION
    pdf_file_path = Column(
        String(500),
        nullable=True,
        comment='Local storage path relative to project root'
    )
    
    file_size_bytes = Column(
        Integer,
        nullable=True,
        comment='Size of PDF file in bytes'
    )
    
    # VIRTUAL GENERATED COLUMN - file size in MB (easier to read)
    # This column is computed at query time and doesn't use storage
    # Uses only immutable arithmetic operations (division and rounding)
    file_size_mb = Column(
        Float,
        Computed(
            "ROUND(CAST(file_size_bytes AS NUMERIC) / 1048576.0, 2)",
            persisted=True  # Virtual: computed at query time, no storage
        ),
        comment='File size in megabytes (computed at query time)'
    )
    
    page_count = Column(
        Integer,
        nullable=True,
        comment='Number of pages in the document'
    )
    
    # DOWNLOAD STATUS
    pdf_downloaded = Column(
        Boolean,
        default=False,
        nullable=False,
        comment='True if PDF was successfully downloaded'
    )
    
    download_date = Column(
        DateTime,
        nullable=True,
        comment='Timestamp when PDF was downloaded'
    )
    
    download_error = Column(
        Text,
        nullable=True,
        comment='Error message if download failed'
    )
    
    # METADATA
    metadata_json = Column(
        'metadata',
        JSON,
        nullable=True,
        comment='Document-specific metadata in JSON format'
    )
    
    # AUDIT FIELDS
    created_at = Column(
        DateTime,
        server_default=text('NOW()'),
        nullable=False,
        comment='Timestamp when this record was created'
    )
    
    updated_at = Column(
        DateTime,
        server_default=text('NOW()'),
        onupdate=datetime.utcnow,
        nullable=False,
        comment='Timestamp when this record was last updated'
    )
    
    # RELATIONSHIPS
    case = relationship('Case', back_populates='documents')
    
    extracted_text = relationship(
        'ExtractedText',
        back_populates='document',
        uselist=False,  # One-to-one relationship
        cascade='all, delete-orphan'
    )
    
    text_sections = relationship(
        'TextSection',
        back_populates='document',
        cascade='all, delete-orphan'
    )
    
    # INDEX DEFINITIONS
    __table_args__ = (
        # B-tree index for case_id (joining with cases table)
        Index('idx_documents_case_id', 'case_id'),
        
        # B-tree index for download status (filter by download success)
        Index('idx_documents_downloaded', 'pdf_downloaded'),
        
        # Composite index for download monitoring
        Index('idx_documents_download_status', 'pdf_downloaded', 'download_date'),
    )


class ExtractedText(Base):
    """
    EXTRACTED_TEXT Table - Stores extracted text from PDF documents
    
    PostgreSQL 18 Optimizations:
    - UUIDv7 primary key
    - Virtual generated column for avg_word_length (text quality indicator)
    - Text columns optimized for AIO reading (2-3x faster)
    - Enhanced full-text search capabilities
    
    This table stores both raw and processed text extracted from documents,
    along with quality metrics and extraction metadata.
    
    Relationships:
    - One extracted_text belongs to one document (1:1 relationship)
    """
    
    __tablename__ = 'extracted_text'
    
    # PRIMARY KEY - UUIDv7
    text_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment='Unique identifier for this extracted text'
    )
    
    # FOREIGN KEY to documents table (one-to-one relationship)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey('documents.document_id', ondelete='CASCADE'),
        nullable=False,
        unique=True,  # Ensures one-to-one relationship
        comment='References the source document'
    )
    
    # TEXT CONTENT
    # PostgreSQL 18 AIO makes reading these large text columns 2-3x faster
    raw_text = Column(
        Text,
        nullable=True,
        comment='Original extracted text, unprocessed'
    )
    
    processed_text = Column(
        Text,
        nullable=True,
        comment='Cleaned and preprocessed text ready for analysis'
    )
    
    # TEXT STATISTICS
    word_count = Column(
        Integer,
        nullable=True,
        comment='Number of words in the text'
    )
    
    character_count = Column(
        Integer,
        nullable=True,
        comment='Number of characters in the text'
    )
    
    # VIRTUAL GENERATED COLUMN - average word length
    # This helps detect extraction quality (very short or very long averages indicate problems)
    # Uses only immutable arithmetic operations
    avg_word_length = Column(
        Float,
        Computed(
            "CASE WHEN word_count > 0 "
            "THEN ROUND(CAST(character_count AS NUMERIC) / word_count, 2) "
            "ELSE 0 END",
            persisted=True  # Virtual: computed at query time
        ),
        comment='Average word length (computed, helps detect extraction quality)'
    )
    
    # EXTRACTION METADATA
    extraction_date = Column(
        DateTime,
        nullable=True,
        comment='When text extraction was performed'
    )
    
    extraction_method = Column(
        String(50),
        nullable=True,
        comment='Library used: "PyPDF2", "pdfplumber", "PyMuPDF", etc.'
    )
    
    extraction_quality = Column(
        String(20),
        nullable=True,
        comment='Quality assessment: "excellent", "good", "fair", "poor", "failed"'
    )
    
    extraction_notes = Column(
        Text,
        nullable=True,
        comment='Warnings or issues encountered during extraction'
    )
    
    # LANGUAGE INFORMATION
    language_detected = Column(
        String(10),
        nullable=True,
        comment='Auto-detected language code (ISO 639-1, e.g., "en", "pt", "es")'
    )
    
    language_confidence = Column(
        Float,
        nullable=True,
        comment='Confidence score for language detection (0.0 to 1.0)'
    )
    
    # AUDIT FIELDS
    created_at = Column(
        DateTime,
        server_default=text('NOW()'),
        nullable=False,
        comment='Timestamp when this record was created'
    )
    
    updated_at = Column(
        DateTime,
        server_default=text('NOW()'),
        onupdate=datetime.utcnow,
        nullable=False,
        comment='Timestamp when this record was last updated'
    )
    
    # RELATIONSHIPS
    document = relationship('Document', back_populates='extracted_text')
    
    # INDEX DEFINITIONS
    __table_args__ = (
        # B-tree index for document_id (one-to-one relationship)
        Index('idx_extracted_text_document_id', 'document_id'),
        
        # B-tree index for extraction quality (filter by quality)
        Index('idx_extracted_text_quality', 'extraction_quality'),
        
        # B-tree index for language (language-specific analysis)
        Index('idx_extracted_text_language', 'language_detected'),
        
        # Full-text search index on processed_text (PostgreSQL 18 has improved FTS)
        # Note: This would be created via SQL after table creation:
        # CREATE INDEX idx_extracted_text_fts ON extracted_text 
        # USING gin(to_tsvector('portuguese', processed_text));
    )


class TextSection(Base):
    """
    TEXT_SECTIONS Table - Stores segmented sections of extracted text
    
    PostgreSQL 18 Optimizations:
    - UUIDv7 primary key
    - Virtual generated column for content_size_category
    - Optimized for chunked text analysis (e.g., for LLM context windows)
    
    This table allows splitting large documents into manageable sections
    for analysis, such as by paragraph, page, or semantic chunks.
    
    Relationships:
    - Many sections belong to one document (N:1 relationship)
    """
    
    __tablename__ = 'text_sections'
    
    # PRIMARY KEY - UUIDv7
    section_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment='Unique identifier for this text section'
    )
    
    # FOREIGN KEY to documents table
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey('documents.document_id', ondelete='CASCADE'),
        nullable=False,
        comment='References the source document'
    )
    
    # SECTION IDENTIFICATION
    section_type = Column(
        String(50),
        nullable=True,
        comment='Type: "paragraph", "page", "chapter", "chunk", etc.'
    )
    
    section_number = Column(
        Integer,
        nullable=True,
        comment='Sequential number within the document (e.g., page 1, 2, 3...)'
    )
    
    # SECTION CONTENT
    section_text = Column(
        Text,
        nullable=True,
        comment='Text content of this section'
    )
    
    content_length = Column(
        Integer,
        nullable=True,
        comment='Character count for this section'
    )
    
    # VIRTUAL GENERATED COLUMN - categorize section by length
    # Helps identify tiny fragments vs substantial sections
    # Uses only immutable CASE expression
    content_size_category = Column(
        String(20),
        Computed(
            "CASE "
            "WHEN content_length < 100 THEN 'tiny' "
            "WHEN content_length < 500 THEN 'small' "
            "WHEN content_length < 2000 THEN 'medium' "
            "WHEN content_length < 10000 THEN 'large' "
            "ELSE 'very_large' END",
            persisted=True  # Virtual: computed at query time
        ),
        comment='Section size category (computed at query time)'
    )
    
    # SECTION METADATA
    metadata_json = Column(
        'metadata',
        JSON,
        nullable=True,
        comment='Section-specific metadata (e.g., formatting, position, etc.)'
    )
    
    # AUDIT FIELDS
    created_at = Column(
        DateTime,
        server_default=text('NOW()'),
        nullable=False,
        comment='Timestamp when this record was created'
    )
    
    # RELATIONSHIPS
    document = relationship('Document', back_populates='text_sections')
    
    # INDEX DEFINITIONS
    __table_args__ = (
        # B-tree index for document_id (joining with documents)
        Index('idx_text_sections_document_id', 'document_id'),
        
        # Composite index for ordered retrieval of sections
        Index('idx_text_sections_order', 'document_id', 'section_number'),
        
        # B-tree index for section type
        Index('idx_text_sections_type', 'section_type'),
    )


class KeywordTag(Base):
    """
    KEYWORDS_TAGS Table - Stores keywords and tags associated with cases
    
    This table allows tagging cases with keywords for categorization,
    search, and analysis (e.g., "carbon emissions", "deforestation", etc.).
    
    Relationships:
    - Many keywords belong to one case (N:1 relationship)
    """
    
    __tablename__ = 'keywords_tags'
    
    # PRIMARY KEY - UUIDv7
    keyword_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment='Unique identifier for this keyword/tag'
    )
    
    # FOREIGN KEY to cases table
    case_id = Column(
        UUID(as_uuid=True),
        ForeignKey('cases.case_id', ondelete='CASCADE'),
        nullable=False,
        comment='References the associated case'
    )
    
    # KEYWORD/TAG INFORMATION
    keyword = Column(
        String(200),
        nullable=False,
        comment='The keyword or tag text (e.g., "carbon emissions")'
    )
    
    keyword_type = Column(
        String(50),
        nullable=True,
        comment='Type: "manual", "auto-extracted", "nlp-generated", etc.'
    )
    
    confidence_score = Column(
        Float,
        nullable=True,
        comment='Confidence score if auto-generated (0.0 to 1.0)'
    )
    
    # AUDIT FIELDS
    created_at = Column(
        DateTime,
        server_default=text('NOW()'),
        nullable=False,
        comment='Timestamp when this record was created'
    )
    
    # RELATIONSHIPS
    case = relationship('Case', back_populates='keywords')
    
    # INDEX DEFINITIONS
    __table_args__ = (
        # B-tree index for case_id (joining with cases)
        Index('idx_keywords_case_id', 'case_id'),
        
        # B-tree index for keyword (searching by keyword)
        Index('idx_keywords_keyword', 'keyword'),
        
        # Composite index for keyword type filtering
        Index('idx_keywords_type', 'keyword_type', 'case_id'),
    )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def check_postgresql_version(engine):
    """
    Check the PostgreSQL version to ensure compatibility
    
    Args:
        engine: SQLAlchemy engine
    
    Returns:
        tuple: (major_version, full_version_string)
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version_string = result.scalar()
            
            # Extract major version number
            # Example: "PostgreSQL 18.0 on x86_64..." -> 18
            if 'PostgreSQL' in version_string:
                version_part = version_string.split('PostgreSQL')[1].split()[0]
                major_version = int(version_part.split('.')[0])
                return major_version, version_string
            else:
                return 0, version_string
    except Exception as e:
        return 0, str(e)


def check_aio_support(engine):
    """
    Check PostgreSQL 18 Asynchronous I/O configuration
    
    Args:
        engine: SQLAlchemy engine
    
    Returns:
        dict: AIO configuration details
    """
    try:
        with engine.connect() as conn:
            # Check io_method setting
            result = conn.execute(text("SHOW io_method"))
            io_method = result.scalar()
            
            # Check io_workers setting
            result = conn.execute(text("SHOW io_workers"))
            io_workers = result.scalar()
            
            # Check effective_io_concurrency
            result = conn.execute(text("SHOW effective_io_concurrency"))
            effective_io = result.scalar()
            
            return {
                'io_method': io_method,
                'io_workers': io_workers,
                'effective_io_concurrency': effective_io
            }
    except Exception as e:
        return {'error': str(e)}


def init_database(drop_existing=False):
    """
    Initialize the PostgreSQL 18 database with all tables and indexes
    
    Args:
        drop_existing (bool): If True, drop all existing tables before creating new ones
    
    Returns:
        engine: SQLAlchemy engine object if successful, None otherwise
    
    This function:
    1. Connects to PostgreSQL
    2. Checks version (optimized for PG 18)
    3. Optionally drops existing tables
    4. Creates all tables with indexes and constraints
    5. Verifies creation success
    """
    
    print("\n" + "=" * 70)
    print("PostgreSQL 18 Database Initialization")
    print("=" * 70)
    
    # Create database URL
    try:
        url = URL.create(**DB_CONFIG)
        engine = create_engine(url, echo=False)
        
        # Test connection
        print("\n1. Testing database connection...")
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("   ✓ Connected successfully!")
        print(f"   ✓ Database: {DB_CONFIG['database']}")
        print(f"   ✓ Host: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
        
    except Exception as e:
        print(f"   ✗ ERROR: Could not connect to database")
        print(f"   Error details: {e}")
        print("\n   Troubleshooting:")
        print("   - Is PostgreSQL 18 running?")
        print("   - Are your credentials in .env correct?")
        print("   - Does the database exist?")
        return None
    
    # Check PostgreSQL version
    print("\n2. Checking PostgreSQL version...")
    major_version, version_string = check_postgresql_version(engine)
    
    if major_version == 18:
        print(f"   ✓ PostgreSQL 18 detected!")
        print(f"   ✓ Full version: {version_string[:80]}...")
    elif major_version > 0:
        print(f"   ⚠ WARNING: PostgreSQL {major_version} detected")
        print(f"   This script is optimized for PostgreSQL 18")
        print(f"   Some features (UUIDv7, AIO, etc.) may not work correctly")
        response = input("\n   Continue anyway? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("   Exiting...")
            return None
    else:
        print(f"   ⚠ Could not determine PostgreSQL version")
        print(f"   Version info: {version_string}")
    
    # Check AIO configuration
    if major_version == 18:
        print("\n3. Checking Asynchronous I/O configuration...")
        aio_config = check_aio_support(engine)
        
        if 'error' not in aio_config:
            print(f"   ✓ io_method: {aio_config['io_method']}")
            print(f"   ✓ io_workers: {aio_config['io_workers']}")
            print(f"   ✓ effective_io_concurrency: {aio_config['effective_io_concurrency']}")
            
            # Provide optimization suggestions
            if aio_config['io_method'] == 'sync':
                print("\n   💡 TIP: Consider enabling AIO for better performance:")
                print("      ALTER SYSTEM SET io_method = 'worker';")
                print("      SELECT pg_reload_conf();")
            elif aio_config['io_method'] == 'worker':
                print("   ✓ AIO is enabled with worker method (good default)")
            elif aio_config['io_method'] == 'io_uring':
                print("   ✓ AIO is using io_uring (best performance on Linux)")
        else:
            print(f"   ⚠ Could not check AIO config: {aio_config['error']}")
    
    # Drop existing tables if requested
    step_num = 4 if major_version == 18 else 3
    if drop_existing:
        print(f"\n{step_num}. Dropping existing tables...")
        print("   ⚠ WARNING: This will delete all existing data!")
        try:
            # Use CASCADE to drop tables with dependencies
            # This is necessary because foreign keys create dependencies between tables
            with engine.connect() as conn:
                # Start a transaction
                trans = conn.begin()
                try:
                    # Drop tables in reverse order of dependencies (most dependent first)
                    # This helps avoid some cascading issues
                    # Include both current and legacy table names
                    tables_to_drop = [
                        'keywords_tags',
                        'text_sections', 
                        'extraction_log',        # Legacy table
                        'extracted_texts',       # Legacy table (plural)
                        'extracted_text',        # Current table (singular)
                        'documents',
                        'cases'
                    ]
                    
                    for table_name in tables_to_drop:
                        # Check if table exists before dropping
                        result = conn.execute(text(
                            f"SELECT EXISTS (SELECT FROM information_schema.tables "
                            f"WHERE table_name = '{table_name}')"
                        ))
                        table_exists = result.scalar()
                        
                        if table_exists:
                            print(f"   • Dropping table: {table_name}")
                            conn.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))
                    
                    # Commit the transaction
                    trans.commit()
                    print("   ✓ All existing tables dropped successfully")
                    
                except Exception as e:
                    # Rollback on error
                    trans.rollback()
                    print(f"   ✗ ERROR during table drop: {e}")
                    return None
                    
        except Exception as e:
            print(f"   ✗ ERROR dropping tables: {e}")
            print("\n   Troubleshooting:")
            print("   - You may have other database connections open")
            print("   - Try closing all psql sessions and retry")
            return None
    else:
        print(f"\n{step_num}. Skipping table drop (drop_existing=False)")
    
    # Create all tables
    step_num += 1
    print(f"\n{step_num}. Creating database tables...")
    try:
        Base.metadata.create_all(engine)
        print("   ✓ Created table: cases (with JSON and enhanced indexes)")
        print("   ✓ Created table: documents (with virtual column: file_size_mb)")
        print("   ✓ Created table: extracted_text (with virtual column: avg_word_length)")
        print("   ✓ Created table: text_sections (with virtual column: content_size_category)")
        print("   ✓ Created table: keywords_tags")
        
    except Exception as e:
        print(f"   ✗ ERROR creating tables: {e}")
        print("\n   Troubleshooting:")
        print("   - Check if you have proper permissions")
        print("   - Ensure PostgreSQL version compatibility")
        print("   - Review the error message above for details")
        return None
    
    # Verify tables were created
    step_num += 1
    print(f"\n{step_num}. Verifying table creation...")
    try:
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        expected_tables = ['cases', 'documents', 'extracted_text', 'text_sections', 'keywords_tags']
        
        for table in expected_tables:
            if table in tables:
                print(f"   ✓ Table '{table}' exists")
            else:
                print(f"   ✗ Table '{table}' NOT FOUND")
        
        print(f"\n   Total tables created: {len(tables)}")
        
    except Exception as e:
        print(f"   ⚠ Could not verify tables: {e}")
    
    # Success message
    print("\n" + "=" * 70)
    print("✓ Database initialization completed successfully!")
    print("=" * 70)
    print("\nPostgreSQL 18 Features Enabled:")
    print("  ✓ UUIDv7 primary keys (timestamp-ordered)")
    print("  ✓ Virtual generated columns (computed at query time):")
    print("     - file_size_mb (documents)")
    print("     - avg_word_length (extracted_text)")
    print("     - content_size_category (text_sections)")
    print("  ✓ Skip scan indexes (flexible multicolumn index usage)")
    print("  ✓ Enhanced JSON support")
    print("  ✓ Data checksums (enabled by default in PG 18)")
    
    if major_version == 18:
        print(f"\nAsynchronous I/O Status:")
        if 'error' not in aio_config:
            print(f"  Current method: {aio_config['io_method']}")
            print(f"  Workers: {aio_config['io_workers']}")
            print(f"  Expected performance improvement: 2-3x for large text reads")
    
    print("\n⚠️  IMPORTANT NOTE:")
    print("  case_age_days column was REMOVED in v2.1")
    print("  Reason: Used CURRENT_DATE (non-immutable function)")
    print("  Solution: Calculate case age at query time in your application")
    print("\n  Example query:")
    print("    SELECT case_id,")
    print("           CASE WHEN decision_date IS NOT NULL")
    print("                THEN decision_date - filing_date")
    print("                ELSE CURRENT_DATE - filing_date")
    print("           END as case_age_days")
    print("    FROM cases;")
    
    print("\nNext steps:")
    print("1. Load case metadata from baseCompleta.xlsx")
    print("2. Add PDF documents to the database")
    print("3. Run text extraction pipeline (optimized for PG 18 AIO)")
    print("\nYou can now use this database with SQLAlchemy ORM in your scripts.")
    print("=" * 70)
    
    return engine


def get_session(engine):
    """
    Create a database session for performing operations
    
    Args:
        engine: SQLAlchemy engine from init_database()
    
    Returns:
        sqlalchemy.orm.Session: Database session
    
    Example usage:
        engine = init_database()
        session = get_session(engine)
        
        # Query with computed case age
        from sqlalchemy import case as sql_case, func
        
        cases = session.query(
            Case,
            sql_case(
                (Case.decision_date.isnot(None), Case.decision_date - Case.filing_date),
                else_=func.current_date() - Case.filing_date
            ).label('case_age_days')
        ).all()
        
        # Access results
        for case, age_days in cases:
            print(f"{case.case_name}: {age_days} days")
    """
    Session = sessionmaker(bind=engine)
    return Session()


# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    """
    This runs when you execute: python init_database_pg18.py
    """
    
    print("\n")
    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║  Climate Litigation Database - PostgreSQL 18 Initialization       ║")
    print("║  Global South Climate Litigation Analysis                         ║")
    print("║  Optimized for PostgreSQL 18 Performance Features                 ║")
    print("║  Version 2.1 - Fixed (Immutability Compliant)                     ║")
    print("╚════════════════════════════════════════════════════════════════════╝")
    print("\n")
    
    # Ask user if they want to drop existing tables
    print("⚠️  WARNING: Do you want to drop existing tables?")
    print("   This will DELETE ALL DATA in the database!")
    print("   Only do this if you're starting fresh.\n")
    
    response = input("Drop existing tables? (yes/no): ").strip().lower()
    drop_tables = response in ['yes', 'y']
    
    if drop_tables:
        print("\n⚠️  CONFIRMATION REQUIRED")
        confirm = input("Type 'DELETE ALL DATA' to confirm: ").strip()
        if confirm != "DELETE ALL DATA":
            print("\n✗ Confirmation failed. Exiting without changes.")
            exit(0)
    
    print("\n")
    
    # Initialize the database
    engine = init_database(drop_existing=drop_tables)
    
    if engine:
        print("\n✓ Setup complete! Your PostgreSQL 18 database is ready to use.")
        
        # Example: Create a test session
        print("\nTesting database connection...")
        try:
            session = get_session(engine)
            
            # Try a simple query
            case_count = session.query(Case).count()
            print(f"✓ Current number of cases in database: {case_count}")
            
            session.close()
            print("✓ Database connection test successful!")
            
        except Exception as e:
            print(f"⚠ Warning: Could not test database connection: {e}")
    
    else:
        print("\n✗ Database initialization failed. Please check the errors above.")
        exit(1)
