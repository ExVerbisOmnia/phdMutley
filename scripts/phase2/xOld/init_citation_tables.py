#!/usr/bin/env python3
"""
Citation Tables Initialization Script
======================================
Creates citation_extractions and citations tables in PostgreSQL database.

📁 Run from: /home/gusrodgs/Gus/cienciaDeDados/phdMutley
Command: python scripts/phase2/init_citation_tables.py

This script adds two new tables to your existing climate_litigation database:
1. citation_extractions - Stores extraction metadata per document
2. citations - Stores individual citation records

Run this BEFORE running extract_citations.py for the first time.

Author: Gustavo (gusrodgs)
Project: Doutorado PM
Version: 1.0
Date: November 2025
"""

import os
import sys
from uuid import uuid4
from datetime import datetime
import logging

from sqlalchemy import create_engine, Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey, JSON, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.engine import URL
from dotenv import load_dotenv

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ============================================================================
# DATABASE SETUP
# ============================================================================

load_dotenv()

DB_CONFIG = {
    'drivername': 'postgresql+psycopg2',
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'climate_litigation'),
    'username': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
}

try:
    db_url = URL.create(**DB_CONFIG)
    engine = create_engine(db_url)
    logging.info("✓ Database connection established")
except Exception as e:
    logging.error(f"✗ Failed to connect to database: {e}")
    sys.exit(1)

# ============================================================================
# IMPORT EXISTING MODELS
# ============================================================================

# Import existing database models so SQLAlchemy knows about them
try:
    # Add scripts/phase0 to Python path
    sys.path.insert(0, os.path.join(os.getcwd(), 'scripts', 'phase0'))
    from init_database_pg18 import Base, Document
    logging.info("✓ Existing database models imported")
except ImportError as e:
    logging.error(f"✗ Failed to import existing models: {e}")
    logging.error("Make sure you're running from the project root directory")
    sys.exit(1)

# ============================================================================
# TABLE DEFINITIONS
# ============================================================================

# Note: Base is imported from init_database_pg18.py above, not created here

class CitationExtraction(Base):
    """Stores extraction metadata per document"""
    __tablename__ = 'citation_extractions'
    
    extraction_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.document_id', ondelete='CASCADE'), nullable=False, unique=True)
    extraction_date = Column(DateTime, default=datetime.now, nullable=False)
    model_used = Column(String(100), nullable=False)
    total_citations_found = Column(Integer, default=0)
    foreign_citations_count = Column(Integer, default=0)
    domestic_citations_excluded = Column(Integer, default=0)
    api_tokens_input = Column(Integer)
    api_tokens_output = Column(Integer)
    api_cost_usd = Column(Float)
    extraction_time_seconds = Column(Float)
    extraction_success = Column(Boolean, default=False, nullable=False)
    extraction_error = Column(Text)
    raw_llm_response = Column(JSON)
    
    citations = relationship('Citation', back_populates='extraction', cascade='all, delete-orphan')
    
    __table_args__ = (
        Index('idx_citation_extractions_document_id', 'document_id'),
        Index('idx_citation_extractions_success', 'extraction_success'),
        Index('idx_citation_extractions_date', 'extraction_date'),
    )


class Citation(Base):
    """Stores individual citations"""
    __tablename__ = 'citations'
    
    citation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    extraction_id = Column(UUID(as_uuid=True), ForeignKey('citation_extractions.extraction_id', ondelete='CASCADE'), nullable=False)
    
    # Minimum extraction fields
    cited_case_name = Column(Text, nullable=False)
    cited_court = Column(Text)
    cited_jurisdiction = Column(Text)
    cited_country = Column(String(100))
    cited_year = Column(Integer)
    
    # Extended extraction fields
    citation_context = Column(Text)
    citation_type = Column(String(100))
    
    # Metadata
    citation_string_raw = Column(Text)
    confidence_score = Column(Float)
    position_in_document = Column(Integer)
    
    # Audit
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    
    extraction = relationship('CitationExtraction', back_populates='citations')
    
    __table_args__ = (
        Index('idx_citations_extraction_id', 'extraction_id'),
        Index('idx_citations_country', 'cited_country'),
        Index('idx_citations_year', 'cited_year'),
        Index('idx_citations_confidence', 'confidence_score'),
    )


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    print("\n" + "="*70)
    print("  CITATION TABLES INITIALIZATION")
    print("="*70 + "\n")
    
    print("This script will create the following tables:")
    print("  1. citation_extractions")
    print("  2. citations")
    print()
    
    response = input("Proceed with table creation? (yes/no): ").strip().lower()
    
    if response not in ['yes', 'y']:
        print("\n✗ Cancelled by user.")
        return
    
    try:
        print("\nCreating tables...")
        
        # Create tables
        Base.metadata.create_all(engine)
        
        print("✓ Created table: citation_extractions")
        print("✓ Created table: citations")
        
        # Verify tables exist
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if 'citation_extractions' in tables and 'citations' in tables:
            print("\n" + "="*70)
            print("  SUCCESS - Citation tables created")
            print("="*70)
            print("\nYou can now run: python scripts/phase2/extract_citations.py")
        else:
            print("\n⚠️  Warning: Tables may not have been created properly")
            
    except Exception as e:
        print(f"\n✗ Error creating tables: {e}")
        logging.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
