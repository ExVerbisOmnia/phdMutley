"""
Climate Litigation Database Initialization Script
==================================================

This script creates the PostgreSQL database structure for storing climate litigation
cases, documents, extracted text, and related metadata.

Author: Lucas Biasetton
Project: Doutorado PM - Global South Climate Litigation Analysis
Database: PostgreSQL with SQLAlchemy ORM

Prerequisites:
--------------
1. PostgreSQL installed and running
2. Python packages installed:
   pip install sqlalchemy psycopg2-binary python-dotenv

3. Create a .env file in the same directory with:
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=climate_litigation
   DB_USER=your_username
   DB_PASSWORD=your_password

Usage:
------
python init_database.py
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
    JSON,                    # JSON data type (stores flexible structured data)
    Float,                   # Decimal numbers
    ForeignKey,              # Links tables together
    Index,                   # Creates indexes for faster queries
    CheckConstraint,         # Validates data (e.g., status must be 'pending' or 'completed')
)
from sqlalchemy.ext.declarative import declarative_base  # Base class for table definitions
from sqlalchemy.orm import relationship, sessionmaker    # Handles relationships between tables
from sqlalchemy.engine import URL                        # Constructs database connection URL
from datetime import datetime
import os
from dotenv import load_dotenv  # Loads environment variables from .env file

# =============================================================================
# CONFIGURATION
# =============================================================================

# Load environment variables from .env file
# This keeps sensitive information (passwords) out of the code
load_dotenv()

# Database connection parameters
# These values come from your .env file
DB_CONFIG = {
    'drivername': 'postgresql+psycopg2',  # PostgreSQL driver
    'host': os.getenv('DB_HOST', 'localhost'),  # Database server address
    'port': os.getenv('DB_PORT', '5432'),       # PostgreSQL default port
    'database': os.getenv('DB_NAME', 'climate_litigation'),  # Database name
    'username': os.getenv('DB_USER'),           # Your PostgreSQL username
    'password': os.getenv('DB_PASSWORD'),       # Your PostgreSQL password
}

# Create the base class for all table models
# All table classes will inherit from this
Base = declarative_base()

# =============================================================================
# TABLE DEFINITIONS
# =============================================================================

class Case(Base):
    """
    CASES Table - Main table storing information about each litigation case
    
    This table stores the core metadata about climate litigation cases from
    the Global South, including case identification, location, dates, and status.
    
    Relationships:
    - One case can have many documents (1:N relationship)
    - One case can have many keywords/tags (1:N relationship)
    """
    
    __tablename__ = 'cases'  # Name of the table in PostgreSQL
    
    # PRIMARY KEY - Unique identifier for each case
    # auto-increment means PostgreSQL automatically generates sequential numbers
    case_id = Column(
        Integer, 
        primary_key=True,  # This is the unique identifier
        autoincrement=True,  # Automatically generates 1, 2, 3, etc.
        comment='Unique identifier for each case'
    )
    
    # CASE IDENTIFICATION
    case_name = Column(
        String(500),  # Maximum 500 characters
        nullable=False,  # This field is required (cannot be empty)
        comment='Full name of the case (e.g., "Silva vs. Government of Brazil")'
    )
    
    case_number = Column(
        String(200),  # Court-assigned case number
        nullable=True,  # Optional field
        comment='Official court case number if available'
    )
    
    # LOCATION INFORMATION
    court_name = Column(
        String(300),
        nullable=False,  # Required field
        comment='Name of the court (e.g., "Supreme Federal Court of Brazil")'
    )
    
    country = Column(
        String(100),
        nullable=False,  # Required field
        comment='Country where case was filed (e.g., "Brazil", "Argentina")'
    )
    
    region = Column(
        String(100),
        nullable=True,  # Optional field
        comment='Geographic region (e.g., "Latin America", "Africa", "Asia")'
    )
    
    # DATE INFORMATION
    filing_date = Column(
        Date,  # Stores date without time (YYYY-MM-DD)
        nullable=True,  # Optional - not all cases have this info
        comment='Date when the case was filed'
    )
    
    decision_date = Column(
        Date,
        nullable=True,
        comment='Date when the final decision was issued'
    )
    
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
    
    # METADATA - Flexible storage for additional information
    # JSON allows storing structured data without predefined schema
    metadata = Column(
        JSON,
        nullable=True,
        comment='Additional flexible metadata in JSON format'
    )
    
    # AUDIT FIELDS - Track when records are created/modified
    created_at = Column(
        DateTime,
        default=datetime.utcnow,  # Automatically set to current time when created
        nullable=False,
        comment='Timestamp when this record was created'
    )
    
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,  # Automatically update when record is modified
        nullable=False,
        comment='Timestamp when this record was last updated'
    )
    
    # RELATIONSHIPS - Define how this table connects to others
    # These create "virtual" attributes that let you access related data easily
    
    # One case → Many documents
    # Usage: case.documents returns all documents for this case
    documents = relationship(
        'Document',  # Links to Document table
        back_populates='case',  # Creates two-way relationship
        cascade='all, delete-orphan'  # If case is deleted, delete its documents too
    )
    
    # One case → Many keywords/tags
    # Usage: case.keywords returns all keywords for this case
    keywords = relationship(
        'KeywordTag',
        back_populates='case',
        cascade='all, delete-orphan'
    )
    
    def __repr__(self):
        """String representation for debugging"""
        return f"<Case(id={self.case_id}, name='{self.case_name}', country='{self.country}')>"


class Document(Base):
    """
    DOCUMENTS Table - Stores information about PDF files and other documents
    
    Each case can have multiple documents (e.g., initial petition, decision, appeal).
    This table tracks the files themselves and their processing status.
    
    Relationships:
    - Many documents belong to one case (N:1)
    - One document has one extracted text record (1:1)
    """
    
    __tablename__ = 'documents'
    
    # PRIMARY KEY
    document_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment='Unique identifier for each document'
    )
    
    # FOREIGN KEY - Links to the CASES table
    # This creates the "many-to-one" relationship: many documents → one case
    case_id = Column(
        Integer,
        ForeignKey('cases.case_id', ondelete='CASCADE'),  # If case is deleted, delete this document
        nullable=False,  # Every document must belong to a case
        comment='References the case this document belongs to'
    )
    
    # DOCUMENT IDENTIFICATION
    document_type = Column(
        String(100),
        nullable=False,
        comment='Type: "Decision", "Petition", "Brief", "Order", "Appeal", etc.'
    )
    
    document_title = Column(
        String(500),
        nullable=True,
        comment='Descriptive title of the document'
    )
    
    # FILE INFORMATION
    file_path = Column(
        String(1000),
        nullable=False,
        unique=True,  # Each file path must be unique (no duplicate files)
        comment='Full path to the PDF file on disk'
    )
    
    file_name = Column(
        String(500),
        nullable=False,
        comment='Original filename of the PDF'
    )
    
    file_hash = Column(
        String(64),  # SHA-256 hash is 64 characters
        nullable=True,
        unique=True,  # Each file hash must be unique (detects duplicate files)
        comment='SHA-256 hash of file for deduplication and integrity checking'
    )
    
    file_size_bytes = Column(
        Integer,
        nullable=True,
        comment='File size in bytes'
    )
    
    page_count = Column(
        Integer,
        nullable=True,
        comment='Number of pages in the document'
    )
    
    # PROCESSING STATUS
    # This helps track which documents have been processed
    extraction_status = Column(
        String(50),
        nullable=False,
        default='pending',
        comment='Status: "pending", "processing", "completed", "failed"'
    )
    
    # Add constraint to ensure extraction_status has valid values
    __table_args__ = (
        CheckConstraint(
            "extraction_status IN ('pending', 'processing', 'completed', 'failed')",
            name='valid_extraction_status'
        ),
    )
    
    # DATES
    upload_date = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        comment='When the document was added to the database'
    )
    
    last_processed_date = Column(
        DateTime,
        nullable=True,
        comment='When the document was last processed for text extraction'
    )
    
    # AUDIT FIELDS
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    
    # RELATIONSHIPS
    # Many documents → One case
    case = relationship(
        'Case',
        back_populates='documents'
    )
    
    # One document → One extracted text
    extracted_text = relationship(
        'ExtractedText',
        back_populates='document',
        uselist=False,  # This makes it 1:1 instead of 1:many
        cascade='all, delete-orphan'
    )
    
    def __repr__(self):
        return f"<Document(id={self.document_id}, type='{self.document_type}', case_id={self.case_id})>"


class ExtractedText(Base):
    """
    EXTRACTED_TEXT Table - Stores the full text extracted from PDF documents
    
    This table holds the actual text content extracted from PDFs, along with
    quality metrics and metadata about the extraction process.
    
    Relationships:
    - One extracted text belongs to one document (1:1)
    - One extracted text has many text sections (1:N)
    """
    
    __tablename__ = 'extracted_text'
    
    # PRIMARY KEY
    extraction_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment='Unique identifier for each extraction'
    )
    
    # FOREIGN KEY - Links to DOCUMENTS table
    # One-to-one relationship: each document has exactly one extracted text
    document_id = Column(
        Integer,
        ForeignKey('documents.document_id', ondelete='CASCADE'),
        nullable=False,
        unique=True,  # Ensures 1:1 relationship (one document → one extraction)
        comment='References the document this text was extracted from'
    )
    
    # EXTRACTED CONTENT
    # Text type can store very large amounts of text (up to ~1GB in PostgreSQL)
    full_text = Column(
        Text,
        nullable=False,
        comment='Complete extracted text from the document'
    )
    
    # CHARACTER AND WORD COUNTS - Useful for quality assessment
    character_count = Column(
        Integer,
        nullable=True,
        comment='Total number of characters in the extracted text'
    )
    
    word_count = Column(
        Integer,
        nullable=True,
        comment='Total number of words in the extracted text'
    )
    
    # EXTRACTION METADATA
    extraction_date = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        comment='When the text extraction was performed'
    )
    
    extraction_method = Column(
        String(100),
        nullable=False,
        default='pdfplumber',
        comment='Method used: "pdfplumber", "PyPDF2", "OCR", etc.'
    )
    
    extraction_version = Column(
        String(50),
        nullable=True,
        comment='Version of extraction tool used (for reproducibility)'
    )
    
    # QUALITY METRICS
    # These help identify extraction problems
    quality_score = Column(
        Float,  # Decimal number (e.g., 0.95 = 95% quality)
        nullable=True,
        comment='Overall quality score (0.0 to 1.0)'
    )
    
    quality_issues = Column(
        JSON,
        nullable=True,
        comment='JSON array of detected quality issues'
    )
    
    chars_per_page_avg = Column(
        Float,
        nullable=True,
        comment='Average characters per page (helps detect extraction failures)'
    )
    
    # PROCESSING FLAGS
    needs_ocr = Column(
        Integer,  # PostgreSQL doesn't have native boolean, use 0/1
        default=0,
        nullable=False,
        comment='Flag: 1 if document needs OCR processing, 0 otherwise'
    )
    
    is_scanned = Column(
        Integer,
        default=0,
        nullable=False,
        comment='Flag: 1 if document is a scanned image, 0 if native PDF'
    )
    
    # FLEXIBLE METADATA
    metadata = Column(
        JSON,
        nullable=True,
        comment='Additional extraction metadata in JSON format'
    )
    
    # AUDIT FIELDS
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    
    # RELATIONSHIPS
    # One extracted text → One document
    document = relationship(
        'Document',
        back_populates='extracted_text'
    )
    
    # One extracted text → Many sections
    sections = relationship(
        'TextSection',
        back_populates='extracted_text',
        cascade='all, delete-orphan'
    )
    
    def __repr__(self):
        return f"<ExtractedText(id={self.extraction_id}, doc_id={self.document_id}, words={self.word_count})>"


class TextSection(Base):
    """
    TEXT_SECTIONS Table - Breaks extracted text into structured sections
    
    Legal documents have structure (headers, body, tables, footnotes).
    This table preserves that structure by breaking text into sections.
    
    Relationships:
    - Many sections belong to one extracted text (N:1)
    """
    
    __tablename__ = 'text_sections'
    
    # PRIMARY KEY
    section_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment='Unique identifier for each section'
    )
    
    # FOREIGN KEY - Links to EXTRACTED_TEXT table
    extraction_id = Column(
        Integer,
        ForeignKey('extracted_text.extraction_id', ondelete='CASCADE'),
        nullable=False,
        comment='References the extracted text this section belongs to'
    )
    
    # SECTION CLASSIFICATION
    section_type = Column(
        String(100),
        nullable=False,
        comment='Type: "header", "body", "footer", "table", "footnote", "signature", etc.'
    )
    
    section_title = Column(
        String(500),
        nullable=True,
        comment='Title or heading of this section if available'
    )
    
    # SECTION POSITION
    # This preserves the original order of sections in the document
    section_order = Column(
        Integer,
        nullable=False,
        comment='Sequential order of this section in the document (1, 2, 3...)'
    )
    
    page_number = Column(
        Integer,
        nullable=True,
        comment='Page number where this section appears'
    )
    
    # SECTION CONTENT
    content = Column(
        Text,
        nullable=False,
        comment='The actual text content of this section'
    )
    
    content_length = Column(
        Integer,
        nullable=True,
        comment='Character count of this section'
    )
    
    # STRUCTURAL METADATA
    # For tables or structured data
    is_table = Column(
        Integer,
        default=0,
        nullable=False,
        comment='Flag: 1 if this section is a table, 0 otherwise'
    )
    
    table_data = Column(
        JSON,
        nullable=True,
        comment='If table: stores structured table data in JSON format'
    )
    
    # AUDIT FIELDS
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    
    # RELATIONSHIPS
    # Many sections → One extracted text
    extracted_text = relationship(
        'ExtractedText',
        back_populates='sections'
    )
    
    def __repr__(self):
        return f"<TextSection(id={self.section_id}, type='{self.section_type}', order={self.section_order})>"


class KeywordTag(Base):
    """
    KEYWORDS_TAGS Table - Stores keywords and tags for categorizing cases
    
    This table enables flexible tagging of cases with keywords related to
    legal issues, topics, outcomes, parties, etc.
    
    Relationships:
    - Many keywords belong to one case (N:1)
    """
    
    __tablename__ = 'keywords_tags'
    
    # PRIMARY KEY
    tag_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment='Unique identifier for each keyword/tag'
    )
    
    # FOREIGN KEY - Links to CASES table
    case_id = Column(
        Integer,
        ForeignKey('cases.case_id', ondelete='CASCADE'),
        nullable=False,
        comment='References the case this keyword applies to'
    )
    
    # KEYWORD INFORMATION
    keyword = Column(
        String(200),
        nullable=False,
        comment='The keyword or tag text (e.g., "climate change", "standing", "damages")'
    )
    
    tag_type = Column(
        String(100),
        nullable=False,
        comment='Category: "legal_issue", "outcome", "topic", "party_type", "remedy", etc.'
    )
    
    # TAG METADATA
    confidence_score = Column(
        Float,
        nullable=True,
        comment='Confidence score if keyword was auto-extracted (0.0 to 1.0)'
    )
    
    source = Column(
        String(100),
        nullable=True,
        default='manual',
        comment='How tag was added: "manual", "auto_extraction", "imported", etc.'
    )
    
    # AUDIT FIELDS
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    
    created_by = Column(
        String(100),
        nullable=True,
        comment='User or system that created this tag'
    )
    
    # RELATIONSHIPS
    # Many keywords → One case
    case = relationship(
        'Case',
        back_populates='keywords'
    )
    
    def __repr__(self):
        return f"<KeywordTag(id={self.tag_id}, keyword='{self.keyword}', type='{self.tag_type}')>"


# =============================================================================
# INDEXES FOR PERFORMANCE
# =============================================================================

# Indexes make queries faster by creating optimized lookup structures
# Create indexes on columns that will be frequently searched or filtered

# CASES table indexes
Index('idx_cases_country', Case.country)  # Fast filtering by country
Index('idx_cases_region', Case.region)    # Fast filtering by region
Index('idx_cases_filing_date', Case.filing_date)  # Fast date range queries
Index('idx_cases_decision_date', Case.decision_date)
Index('idx_cases_status', Case.case_status)  # Fast filtering by status

# DOCUMENTS table indexes
Index('idx_documents_case_id', Document.case_id)  # Fast lookup of case's documents
Index('idx_documents_type', Document.document_type)  # Fast filtering by type
Index('idx_documents_status', Document.extraction_status)  # Find pending documents
Index('idx_documents_hash', Document.file_hash)  # Fast duplicate detection

# EXTRACTED_TEXT table indexes
Index('idx_extracted_document_id', ExtractedText.document_id)  # Fast lookup by document
Index('idx_extracted_method', ExtractedText.extraction_method)  # Filter by method
Index('idx_extracted_date', ExtractedText.extraction_date)  # Date range queries

# TEXT_SECTIONS table indexes
Index('idx_sections_extraction_id', TextSection.extraction_id)  # Fast section lookup
Index('idx_sections_type', TextSection.section_type)  # Filter by section type
Index('idx_sections_order', TextSection.extraction_id, TextSection.section_order)  # Fast ordered retrieval

# KEYWORDS_TAGS table indexes
Index('idx_keywords_case_id', KeywordTag.case_id)  # Fast lookup of case's keywords
Index('idx_keywords_type', KeywordTag.tag_type)  # Filter by tag type
Index('idx_keywords_keyword', KeywordTag.keyword)  # Search for specific keywords

# Composite index for common query patterns
Index('idx_keywords_case_type', KeywordTag.case_id, KeywordTag.tag_type)  # Fast case+type lookup

# =============================================================================
# DATABASE INITIALIZATION FUNCTIONS
# =============================================================================

def create_database_url():
    """
    Creates the PostgreSQL connection URL from configuration
    
    Returns:
        sqlalchemy.engine.URL: Database connection URL
    
    Raises:
        ValueError: If required environment variables are missing
    """
    # Check that all required configuration is present
    required_fields = ['username', 'password', 'database']
    missing = [field for field in required_fields if not DB_CONFIG.get(field)]
    
    if missing:
        raise ValueError(
            f"Missing required database configuration: {', '.join(missing)}\n"
            f"Please check your .env file contains DB_USER, DB_PASSWORD, and DB_NAME"
        )
    
    # Construct the database URL
    # Format: postgresql+psycopg2://username:password@host:port/database
    db_url = URL.create(**DB_CONFIG)
    
    return db_url


def init_database(drop_existing=False):
    """
    Initialize the database: create all tables and indexes
    
    This function:
    1. Connects to PostgreSQL
    2. Optionally drops existing tables (BE CAREFUL!)
    3. Creates all tables defined above
    4. Creates all indexes for performance
    
    Args:
        drop_existing (bool): If True, drops all existing tables first.
                              WARNING: This deletes all data!
    
    Returns:
        sqlalchemy.engine.Engine: Database engine for further operations
    """
    print("=" * 70)
    print("Climate Litigation Database Initialization")
    print("=" * 70)
    
    # Create database connection
    print("\n1. Connecting to PostgreSQL...")
    try:
        db_url = create_database_url()
        engine = create_engine(
            db_url,
            echo=False,  # Set to True to see all SQL queries (useful for debugging)
            pool_pre_ping=True,  # Verify connections before using them
            future=True  # Use SQLAlchemy 2.0 style
        )
        print(f"   ✓ Connected to database: {DB_CONFIG['database']}")
        print(f"   ✓ Host: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
        
    except Exception as e:
        print(f"   ✗ ERROR: Could not connect to database")
        print(f"   Error details: {e}")
        print("\n   Troubleshooting:")
        print("   - Is PostgreSQL running?")
        print("   - Are your credentials in .env correct?")
        print("   - Does the database exist? (Create it first if needed)")
        return None
    
    # Drop existing tables if requested
    if drop_existing:
        print("\n2. Dropping existing tables...")
        print("   ⚠ WARNING: This will delete all existing data!")
        try:
            Base.metadata.drop_all(engine)
            print("   ✓ Existing tables dropped")
        except Exception as e:
            print(f"   ✗ ERROR dropping tables: {e}")
            return None
    else:
        print("\n2. Skipping table drop (drop_existing=False)")
    
    # Create all tables
    print("\n3. Creating database tables...")
    try:
        Base.metadata.create_all(engine)
        print("   ✓ Created table: cases")
        print("   ✓ Created table: documents")
        print("   ✓ Created table: extracted_text")
        print("   ✓ Created table: text_sections")
        print("   ✓ Created table: keywords_tags")
        
    except Exception as e:
        print(f"   ✗ ERROR creating tables: {e}")
        return None
    
    # Verify tables were created
    print("\n4. Verifying table creation...")
    try:
        # Get list of tables in the database
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
    print("\nNext steps:")
    print("1. Load case metadata from baseCompleta.xlsx")
    print("2. Add PDF documents to the database")
    print("3. Run text extraction pipeline")
    print("\nYou can now use this database with SQLAlchemy ORM in your scripts.")
    print("=" * 70)
    
    return engine


def get_session(engine):
    """
    Create a database session for performing operations
    
    A session is like a "workspace" where you can query and modify data.
    Changes are not permanent until you call session.commit()
    
    Args:
        engine: SQLAlchemy engine from init_database()
    
    Returns:
        sqlalchemy.orm.Session: Database session
    
    Example usage:
        engine = init_database()
        session = get_session(engine)
        
        # Add a new case
        new_case = Case(
            case_name="Test Case",
            country="Brazil",
            court_name="Supreme Court"
        )
        session.add(new_case)
        session.commit()
        
        # Query cases
        brazil_cases = session.query(Case).filter(Case.country == "Brazil").all()
    """
    Session = sessionmaker(bind=engine)
    return Session()


# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    """
    This runs when you execute: python init_database.py
    """
    
    print("\n")
    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║  Climate Litigation Database - PostgreSQL Initialization          ║")
    print("║  Global South Climate Litigation Analysis                         ║")
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
        print("\n✓ Setup complete! Your database is ready to use.")
        
        # Example: Create a test session
        print("\nTesting database connection...")
        try:
            session = get_session(engine)
            
            # Try a simple query (should return empty result if database is new)
            case_count = session.query(Case).count()
            print(f"✓ Current number of cases in database: {case_count}")
            
            session.close()
            print("✓ Database connection test successful!")
            
        except Exception as e:
            print(f"⚠ Warning: Could not test database connection: {e}")
    
    else:
        print("\n✗ Database initialization failed. Please check the errors above.")
        exit(1)
