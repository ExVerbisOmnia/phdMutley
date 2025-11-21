#!/usr/bin/env python3
"""
Citation Extraction Script for Climate Litigation Database
==========================================================
Extracts FOREIGN and INTERNATIONAL citations from judicial decisions using Claude API (Haiku).

📁 Run from: /home/gusrodgs/Gus/cienciaDeDados/phdMutley
Command: python scripts/phase2/extract_citations.py

This script processes extracted text from judicial decisions and identifies citations
to foreign courts and international tribunals. Domestic citations are explicitly excluded.

Pipeline Flow:
--------------
INPUT: Documents with extracted text (extracted_text table)
ALGORITHM: 
  1. Query documents that need citation extraction
  2. For each document:
     - Prepare structured prompt with source document context
     - Send to Claude Haiku API
     - Parse JSON response with citation data
     - Filter by confidence threshold
     - Store in citation_extractions and citations tables
  3. Generate cost and quality statistics
OUTPUT: Populated citations tables with foreign/international citations only

Key Features:
-------------
- Structured JSON output from LLM for reliable parsing
- Excludes domestic citations (same country as source document)
- Tracks API costs per document and overall
- Confidence scoring for quality assessment
- Comprehensive error handling with retry logic
- Test mode for validation before full dataset processing
- Progress tracking and detailed logging

Author: Gustavo (gusrodgs)
Project: Doutorado PM - Global South Climate Litigation Analysis
Version: 1.0
Date: November 2025
"""

import os
import sys
from pathlib import Path
import logging
from datetime import datetime
import json
from uuid import uuid4
import time

# Data processing libraries
import pandas as pd
import numpy as np

# Database libraries
from sqlalchemy import create_engine, text as sql_text, Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey, JSON, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.engine import URL
from dotenv import load_dotenv

# Anthropic API
import anthropic

# Progress tracking
from tqdm import tqdm

# ============================================================================
# CONFIGURATION SECTION
# ============================================================================

CONFIG = {
    # ========== Test Mode Settings ==========
    'TEST_MODE': True,  # Set to False to process all documents
    'TEST_N_DOCUMENTS': 13,  # Number of documents to process in test mode
    'TEST_SAMPLE_METHOD': 'first',  # Options: 'first', 'random', 'specific'
    'TEST_SPECIFIC_DOCS': [],  # List of document_ids (UUIDs) for 'specific' method
    
    # ========== API Settings ==========
    'ANTHROPIC_MODEL': 'claude-3-5-haiku-20241022',
    'MAX_TOKENS': 4096,  # Maximum tokens for LLM response
    'TEMPERATURE': 0.0,  # Deterministic output for reproducibility
    'API_TIMEOUT': 120,  # Seconds before timeout
    'RETRY_ATTEMPTS': 3,  # Number of retries on API failure
    'RETRY_DELAY': 5,  # Seconds to wait between retries
    
    # ========== Cost Tracking Settings ==========
    # Pricing as of November 2025 for Claude Haiku 3.5
    'COST_PER_MTK_INPUT': 0.00025,  # $0.25 per 1M input tokens
    'COST_PER_MTK_OUTPUT': 0.00125,  # $1.25 per 1M output tokens
    
    # ========== Citation Filtering Settings ==========
    'EXCLUDE_DOMESTIC': True,  # MUST be True - exclude same-country citations
    'MIN_CONFIDENCE_SCORE': 0.3,  # Minimum confidence to store citation (0.0-1.0)
    
    # ========== Processing Options ==========
    'SKIP_ALREADY_PROCESSED': True,  # Skip documents with existing extractions
    'SAVE_BATCH_SIZE': 10,  # Commit to database every N documents
    'MAX_TEXT_LENGTH': 100000,  # Maximum characters to send to API (cost control)
}

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Configure logging to track extraction progress and errors
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/citation_extraction.log'),
        logging.StreamHandler()
    ]
)

# Suppress verbose logging from external libraries
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.getLogger('anthropic').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)

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

# Import existing database models and Base
try:
    # Verify we're in correct directory
    if not os.path.exists('baseDecisions.xlsx'):
        raise FileNotFoundError(
            "baseDecisions.xlsx not found. Run this script from project root:\n"
            "   cd /home/gusrodgs/Gus/cienciaDeDados/phdMutley\n"
            "   python scripts/phase2/extract_citations.py"
        )
    
    # Add scripts/phase0 to Python path to import existing models
    sys.path.insert(0, os.path.join(os.getcwd(), 'scripts', 'phase0'))
    from init_database_pg18 import Base, Case, Document, ExtractedText
    logging.info("✓ Existing database models and Base imported")
    
except FileNotFoundError as e:
    logging.error(f"✗ Wrong directory: {e}")
    sys.exit(1)
except ImportError as e:
    logging.error(f"✗ Failed to import database models: {e}")
    sys.exit(1)

# ============================================================================
# NEW DATABASE MODELS FOR CITATIONS
# ============================================================================

# Note: Base is imported from init_database_pg18.py above
# This ensures foreign keys to existing tables work correctly

class CitationExtraction(Base):
    """
    CITATION_EXTRACTIONS Table - Stores extraction metadata per document
    
    One record per document processed. Tracks:
    - Which model was used (Haiku/Sonnet)
    - How many citations were found
    - API costs and timing
    - Success/failure status
    - Full LLM response for reproducibility
    
    Relationships:
    - One extraction has many citations (1:N relationship)
    """
    __tablename__ = 'citation_extractions'
    
    # PRIMARY KEY
    extraction_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment='Unique identifier for this extraction'
    )
    
    # FOREIGN KEY to documents table
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey('documents.document_id', ondelete='CASCADE'),
        nullable=False,
        unique=True,  # One extraction per document
        comment='References the source document'
    )
    
    # EXTRACTION METADATA
    extraction_date = Column(
        DateTime,
        default=datetime.now,
        nullable=False,
        comment='When extraction was performed'
    )
    
    model_used = Column(
        String(100),
        nullable=False,
        comment='Claude model used (e.g., claude-3-5-haiku-20241022)'
    )
    
    # CITATION COUNTS
    total_citations_found = Column(
        Integer,
        default=0,
        comment='Total citations found by LLM (including domestic)'
    )
    
    foreign_citations_count = Column(
        Integer,
        default=0,
        comment='Number of foreign/international citations stored'
    )
    
    domestic_citations_excluded = Column(
        Integer,
        default=0,
        comment='Number of domestic citations filtered out'
    )
    
    # API COST TRACKING
    api_tokens_input = Column(
        Integer,
        comment='Input tokens sent to API'
    )
    
    api_tokens_output = Column(
        Integer,
        comment='Output tokens received from API'
    )
    
    api_cost_usd = Column(
        Float,
        comment='Estimated cost in USD for this extraction'
    )
    
    extraction_time_seconds = Column(
        Float,
        comment='Time taken for API call and processing'
    )
    
    # STATUS TRACKING
    extraction_success = Column(
        Boolean,
        default=False,
        nullable=False,
        comment='True if extraction completed successfully'
    )
    
    extraction_error = Column(
        Text,
        comment='Error message if extraction failed'
    )
    
    # RAW RESPONSE STORAGE (for reproducibility)
    raw_llm_response = Column(
        JSON,
        comment='Complete JSON response from LLM'
    )
    
    # RELATIONSHIPS
    citations = relationship(
        'Citation',
        back_populates='extraction',
        cascade='all, delete-orphan'
    )
    
    # INDEXES
    __table_args__ = (
        Index('idx_citation_extractions_document_id', 'document_id'),
        Index('idx_citation_extractions_success', 'extraction_success'),
        Index('idx_citation_extractions_date', 'extraction_date'),
    )


class Citation(Base):
    """
    CITATIONS Table - Stores individual citations extracted from documents
    
    Multiple citations per extraction. Only foreign/international citations are stored.
    Each citation includes:
    - Basic identification (case name, court, country, year)
    - Context and type information
    - Confidence scoring
    - Raw citation text
    
    Relationships:
    - Many citations belong to one extraction (N:1 relationship)
    """
    __tablename__ = 'citations'
    
    # PRIMARY KEY
    citation_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment='Unique identifier for this citation'
    )
    
    # FOREIGN KEY to citation_extractions table
    extraction_id = Column(
        UUID(as_uuid=True),
        ForeignKey('citation_extractions.extraction_id', ondelete='CASCADE'),
        nullable=False,
        comment='References the parent extraction'
    )
    
    # ========== MINIMUM EXTRACTION FIELDS (Required) ==========
    
    cited_case_name = Column(
        Text,
        nullable=False,
        comment='Full name of the cited case'
    )
    
    cited_court = Column(
        Text,
        comment='Name of the court that decided the cited case'
    )
    
    cited_jurisdiction = Column(
        Text,
        comment='Jurisdiction of the cited court (can be broader than country)'
    )
    
    cited_country = Column(
        String(100),
        comment='Country of the cited court (for North/South classification)'
    )
    
    cited_year = Column(
        Integer,
        comment='Year the cited decision was issued'
    )
    
    # ========== EXTENDED EXTRACTION FIELDS (Optional) ==========
    
    citation_context = Column(
        Text,
        comment='Explanation of why this case was cited and how it was used'
    )
    
    citation_type = Column(
        String(100),
        comment='Type of citation: precedential, persuasive, distinguished, etc.'
    )
    
    # ========== METADATA FIELDS ==========
    
    citation_string_raw = Column(
        Text,
        comment='Original citation text as it appears in the source document'
    )
    
    confidence_score = Column(
        Float,
        comment='LLM confidence in this extraction (0.0 to 1.0)'
    )
    
    position_in_document = Column(
        Integer,
        comment='Ordinal position: 1st citation, 2nd citation, etc.'
    )
    
    # AUDIT FIELDS
    created_at = Column(
        DateTime,
        default=datetime.now,
        nullable=False,
        comment='Timestamp when this citation was stored'
    )
    
    # RELATIONSHIPS
    extraction = relationship('CitationExtraction', back_populates='citations')
    
    # INDEXES
    __table_args__ = (
        Index('idx_citations_extraction_id', 'extraction_id'),
        Index('idx_citations_country', 'cited_country'),
        Index('idx_citations_year', 'cited_year'),
        Index('idx_citations_confidence', 'confidence_score'),
    )


# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================

def initialize_citation_tables():
    """
    Create citation_extractions and citations tables if they don't exist.
    
    INPUT: None
    ALGORITHM: Use SQLAlchemy to create tables from model definitions
    OUTPUT: Tables created in PostgreSQL database
    """
    try:
        logging.info("Checking if citation tables exist...")
        
        # Create tables if they don't exist
        Base.metadata.create_all(engine, tables=[
            CitationExtraction.__table__,
            Citation.__table__
        ])
        
        logging.info("✓ Citation tables ready")
        return True
        
    except Exception as e:
        logging.error(f"✗ Failed to initialize citation tables: {e}")
        return False


# ============================================================================
# API SETUP
# ============================================================================

try:
    # Get API key from environment
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
    if not ANTHROPIC_API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY not found in environment variables.\n"
            "Add it to your .env file:\n"
            "   ANTHROPIC_API_KEY=your_api_key_here"
        )
    
    # Initialize Anthropic client
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    logging.info("✓ Anthropic API client initialized")
    
except Exception as e:
    logging.error(f"✗ Failed to initialize Anthropic API: {e}")
    sys.exit(1)


# ============================================================================
# PROMPT GENERATION
# ============================================================================

def generate_citation_extraction_prompt(document_text, source_court, source_country, source_jurisdiction):
    """
    Generate structured prompt for citation extraction.
    
    INPUT: 
        - document_text (str): Extracted text from judicial decision
        - source_court (str): Name of court that issued the document
        - source_country (str): Country of the source court
        - source_jurisdiction (str): Jurisdiction of the source court
    
    ALGORITHM:
        1. Create structured instructions for LLM
        2. Provide source document context for domestic citation filtering
        3. Define exact JSON schema for response
        4. Include examples and clarifications
    
    OUTPUT: Complete prompt string ready for API call
    """
    
    # Truncate text if too long (cost control)
    if len(document_text) > CONFIG['MAX_TEXT_LENGTH']:
        document_text = document_text[:CONFIG['MAX_TEXT_LENGTH']]
        document_text += "\n\n[... Text truncated for length ...]"
    
    prompt = f"""You are analyzing a judicial decision to extract ONLY foreign and international citations.

CRITICAL INSTRUCTION: 
Exclude ALL domestic citations. A domestic citation is any citation to a court from the same country as the source document.

SOURCE DOCUMENT INFORMATION:
- Court: {source_court}
- Country: {source_country}
- Jurisdiction: {source_jurisdiction}

EXTRACTION RULES:

1. INCLUDE these citations:
   - Citations to courts in OTHER countries (not {source_country})
   - Citations to international tribunals (ICJ, ECHR, IACHR, etc.)
   - Citations to regional courts (European Court of Justice, etc.)

2. EXCLUDE these citations:
   - Any citation to a court within {source_country}
   - Any citation to lower/higher courts in the same country
   - Any citation to administrative bodies in the same country

3. FOR EACH FOREIGN/INTERNATIONAL CITATION, EXTRACT:
   - cited_case_name: Full name of the cited case (e.g., "Brown v. Board of Education")
   - cited_court: Name of the court that decided it (e.g., "U.S. Supreme Court")
   - cited_jurisdiction: Legal jurisdiction (e.g., "United States Federal")
   - cited_country: Country of the court (e.g., "United States")
   - cited_year: Year of the decision (integer, e.g., 1954)
   - citation_context: Brief explanation of WHY this case was cited (1-2 sentences)
   - citation_type: How it was used (e.g., "precedential", "persuasive", "distinguished", "supportive")
   - citation_string_raw: The EXACT citation text as it appears in the document
   - confidence_score: Your confidence in this extraction (0.0 to 1.0)

4. RESPONSE FORMAT:
Return ONLY a valid JSON object with this exact structure (no other text):

{{
  "foreign_citations": [
    {{
      "cited_case_name": "string",
      "cited_court": "string",
      "cited_jurisdiction": "string",
      "cited_country": "string",
      "cited_year": 0,
      "citation_context": "string",
      "citation_type": "string",
      "citation_string_raw": "string",
      "confidence_score": 0.0
    }}
  ],
  "domestic_citations_excluded": 0,
  "total_citations_found": 0
}}

DOCUMENT TEXT TO ANALYZE:

{document_text}

Remember: Return ONLY the JSON object. No other text before or after."""

    return prompt


# ============================================================================
# API INTERACTION
# ============================================================================

def extract_citations_from_document(document_text, source_court, source_country, source_jurisdiction):
    """
    Call Claude API to extract citations from document text.
    
    INPUT:
        - document_text (str): Full text of judicial decision
        - source_court (str): Name of source court
        - source_country (str): Country of source court
        - source_jurisdiction (str): Jurisdiction of source court
    
    ALGORITHM:
        1. Generate structured prompt
        2. Call Claude Haiku API with retry logic
        3. Parse JSON response
        4. Calculate token usage and cost
        5. Handle errors gracefully
    
    OUTPUT: Dictionary with extraction results or error information
    """
    
    # Generate prompt
    prompt = generate_citation_extraction_prompt(
        document_text,
        source_court,
        source_country,
        source_jurisdiction
    )
    
    # Try API call with retry logic
    for attempt in range(CONFIG['RETRY_ATTEMPTS']):
        try:
            start_time = time.time()
            
            # Call Claude API
            response = client.messages.create(
                model=CONFIG['ANTHROPIC_MODEL'],
                max_tokens=CONFIG['MAX_TOKENS'],
                temperature=CONFIG['TEMPERATURE'],
                messages=[{
                    "role": "user",
                    "content": prompt
                }],
                timeout=CONFIG['API_TIMEOUT']
            )
            
            end_time = time.time()
            extraction_time = end_time - start_time
            
            # Extract response text
            response_text = response.content[0].text
            
            # Parse JSON response
            try:
                # Clean response text (remove markdown code blocks if present)
                cleaned_response = response_text.strip()
                if cleaned_response.startswith('```'):
                    # Remove markdown code blocks
                    cleaned_response = cleaned_response.split('```')[1]
                    if cleaned_response.startswith('json'):
                        cleaned_response = cleaned_response[4:]
                    cleaned_response = cleaned_response.strip()
                
                citation_data = json.loads(cleaned_response)
                
            except json.JSONDecodeError as e:
                logging.error(f"Failed to parse JSON response: {e}")
                logging.error(f"Response text: {response_text[:500]}")
                return {
                    'success': False,
                    'error': f'JSON parsing failed: {str(e)}',
                    'raw_response': response_text
                }
            
            # Calculate costs
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            
            cost_input = (input_tokens / 1_000_000) * CONFIG['COST_PER_MTK_INPUT']
            cost_output = (output_tokens / 1_000_000) * CONFIG['COST_PER_MTK_OUTPUT']
            total_cost = cost_input + cost_output
            
            # Return successful result
            return {
                'success': True,
                'citation_data': citation_data,
                'raw_response': response_text,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'cost_usd': total_cost,
                'extraction_time': extraction_time
            }
            
        except anthropic.APITimeoutError:
            logging.warning(f"API timeout on attempt {attempt + 1}/{CONFIG['RETRY_ATTEMPTS']}")
            if attempt < CONFIG['RETRY_ATTEMPTS'] - 1:
                time.sleep(CONFIG['RETRY_DELAY'])
                continue
            else:
                return {
                    'success': False,
                    'error': 'API timeout after all retry attempts'
                }
                
        except anthropic.APIError as e:
            logging.error(f"API error on attempt {attempt + 1}: {e}")
            if attempt < CONFIG['RETRY_ATTEMPTS'] - 1:
                time.sleep(CONFIG['RETRY_DELAY'])
                continue
            else:
                return {
                    'success': False,
                    'error': f'API error: {str(e)}'
                }
                
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}'
            }


# ============================================================================
# DATA PROCESSING
# ============================================================================

def get_documents_to_process(session):
    """
    Query database for documents that need citation extraction.
    
    INPUT: SQLAlchemy session
    ALGORITHM:
        1. Join extracted_text with documents and cases tables
        2. Filter to documents with extracted text
        3. Optionally skip already-processed documents
        4. Apply test mode sampling if enabled
    OUTPUT: List of document records with all needed information
    """
    
    # Base query: documents with extracted text
    query = session.query(
        Document.document_id,
        Document.document_url,
        ExtractedText.raw_text,
        ExtractedText.word_count,
        Case.case_name,
        Case.court_name,
        Case.country,
        Case.region,
        Case.metadata_json
    ).join(
        ExtractedText, Document.document_id == ExtractedText.document_id
    ).join(
        Case, Document.case_id == Case.case_id
    ).filter(
        ExtractedText.raw_text.isnot(None),
        ExtractedText.word_count > 0
    )
    
    # Skip already processed documents if configured
    if CONFIG['SKIP_ALREADY_PROCESSED']:
        # Subquery to get already-processed document_ids
        processed_docs = session.query(CitationExtraction.document_id)
        query = query.filter(~Document.document_id.in_(processed_docs))
    
    # Execute query
    all_documents = query.all()
    
    logging.info(f"Found {len(all_documents)} documents to process")
    
    # Apply test mode if enabled
    if CONFIG['TEST_MODE']:
        if CONFIG['TEST_SAMPLE_METHOD'] == 'first':
            documents = all_documents[:CONFIG['TEST_N_DOCUMENTS']]
        elif CONFIG['TEST_SAMPLE_METHOD'] == 'random':
            import random
            documents = random.sample(all_documents, min(CONFIG['TEST_N_DOCUMENTS'], len(all_documents)))
        elif CONFIG['TEST_SAMPLE_METHOD'] == 'specific':
            # Filter to specific document IDs
            specific_ids = set(CONFIG['TEST_SPECIFIC_DOCS'])
            documents = [doc for doc in all_documents if doc.document_id in specific_ids]
        else:
            documents = all_documents[:CONFIG['TEST_N_DOCUMENTS']]
        
        logging.info(f"⚠️  TEST MODE: Processing {len(documents)} documents")
    else:
        documents = all_documents
        logging.info(f"Processing all {len(documents)} documents")
    
    return documents


def process_single_document(doc, session, stats):
    """
    Process one document: extract citations and store in database.
    
    INPUT:
        - doc: Document record with text and metadata
        - session: SQLAlchemy session
        - stats: Statistics dictionary to update
    
    ALGORITHM:
        1. Prepare source document information
        2. Call API to extract citations
        3. Filter citations by confidence threshold
        4. Create CitationExtraction record
        5. Create Citation records for each foreign citation
        6. Update statistics
    
    OUTPUT: Success/failure status
    """
    
    try:
        # Prepare source document information for domestic filtering
        source_court = doc.court_name or "Unknown Court"
        source_country = doc.country or "Unknown Country"
        
        # Extract jurisdiction from metadata if available
        if doc.metadata_json and 'Jurisdictions' in doc.metadata_json:
            source_jurisdiction = doc.metadata_json['Jurisdictions']
        else:
            source_jurisdiction = f"{source_country} courts"
        
        # Call API to extract citations
        result = extract_citations_from_document(
            doc.raw_text,
            source_court,
            source_country,
            source_jurisdiction
        )
        
        if not result['success']:
            # Create failed extraction record
            extraction = CitationExtraction(
                document_id=doc.document_id,
                extraction_date=datetime.now(),
                model_used=CONFIG['ANTHROPIC_MODEL'],
                total_citations_found=0,
                foreign_citations_count=0,
                domestic_citations_excluded=0,
                extraction_success=False,
                extraction_error=result.get('error', 'Unknown error'),
                raw_llm_response=result.get('raw_response')
            )
            session.add(extraction)
            
            stats['errors'] += 1
            logging.error(f"Failed to extract from document {doc.document_id}: {result.get('error')}")
            return False
        
        # Parse citation data
        citation_data = result['citation_data']
        foreign_citations = citation_data.get('foreign_citations', [])
        domestic_excluded = citation_data.get('domestic_citations_excluded', 0)
        total_found = citation_data.get('total_citations_found', len(foreign_citations))
        
        # Filter citations by confidence threshold
        filtered_citations = [
            cit for cit in foreign_citations
            if cit.get('confidence_score', 0) >= CONFIG['MIN_CONFIDENCE_SCORE']
        ]
        
        # Create CitationExtraction record
        extraction = CitationExtraction(
            document_id=doc.document_id,
            extraction_date=datetime.now(),
            model_used=CONFIG['ANTHROPIC_MODEL'],
            total_citations_found=total_found,
            foreign_citations_count=len(filtered_citations),
            domestic_citations_excluded=domestic_excluded,
            api_tokens_input=result['input_tokens'],
            api_tokens_output=result['output_tokens'],
            api_cost_usd=result['cost_usd'],
            extraction_time_seconds=result['extraction_time'],
            extraction_success=True,
            raw_llm_response=citation_data
        )
        session.add(extraction)
        session.flush()  # Get extraction_id
        
        # Create Citation records
        for position, citation in enumerate(filtered_citations, start=1):
            citation_record = Citation(
                extraction_id=extraction.extraction_id,
                cited_case_name=citation.get('cited_case_name') or '[General Reference]',
                cited_court=citation.get('cited_court'),
                cited_jurisdiction=citation.get('cited_jurisdiction'),
                cited_country=citation.get('cited_country'),
                cited_year=citation.get('cited_year'),
                citation_context=citation.get('citation_context'),
                citation_type=citation.get('citation_type'),
                citation_string_raw=citation.get('citation_string_raw'),
                confidence_score=citation.get('confidence_score'),
                position_in_document=position
            )
            session.add(citation_record)
        
        # Update statistics
        stats['documents_processed'] += 1
        stats['total_citations_found'] += len(filtered_citations)
        stats['total_cost'] += result['cost_usd']
        stats['total_tokens_input'] += result['input_tokens']
        stats['total_tokens_output'] += result['output_tokens']
        
        logging.info(
            f"✓ Processed doc {doc.document_id}: "
            f"{len(filtered_citations)} foreign citations, "
            f"{domestic_excluded} domestic excluded, "
            f"${result['cost_usd']:.4f}"
        )
        
        return True
        
    except Exception as e:
        session.rollback()
        stats['errors'] += 1
        logging.error(f"Error processing document {doc.document_id}: {e}", exc_info=True)
        return False


# ============================================================================
# MAIN PROCESSING FUNCTION
# ============================================================================

def main():
    """
    Main execution function for citation extraction.
    
    INPUT: None (reads from database)
    ALGORITHM:
        1. Initialize citation tables if needed
        2. Get documents to process
        3. Process each document with progress tracking
        4. Commit in batches for efficiency
        5. Generate final statistics report
    OUTPUT: Populated citation_extractions and citations tables
    """
    
    print("\n" + "="*70)
    print("  CITATION EXTRACTION - CLIMATE LITIGATION DATABASE")
    print("  Foreign & International Citations Only")
    print("="*70 + "\n")
    
    # Display configuration
    print("Configuration:")
    print(f"  Model: {CONFIG['ANTHROPIC_MODEL']}")
    print(f"  Test Mode: {'YES - ' + str(CONFIG['TEST_N_DOCUMENTS']) + ' documents' if CONFIG['TEST_MODE'] else 'NO - Full dataset'}")
    print(f"  Exclude Domestic: {CONFIG['EXCLUDE_DOMESTIC']}")
    print(f"  Min Confidence: {CONFIG['MIN_CONFIDENCE_SCORE']}")
    print(f"  Skip Already Processed: {CONFIG['SKIP_ALREADY_PROCESSED']}")
    print()
    
    # Initialize statistics
    stats = {
        'documents_processed': 0,
        'total_citations_found': 0,
        'total_cost': 0.0,
        'total_tokens_input': 0,
        'total_tokens_output': 0,
        'errors': 0,
        'start_time': datetime.now()
    }
    
    # Initialize citation tables
    if not initialize_citation_tables():
        print("✗ Failed to initialize citation tables. Exiting.")
        return
    
    # Create database session
    session = SessionLocal()
    
    try:
        # Get documents to process
        documents = get_documents_to_process(session)
        
        if len(documents) == 0:
            print("\n✓ No documents need processing. All done!")
            return
        
        print(f"\nStarting extraction for {len(documents)} documents...\n")
        
        # Process documents with progress bar
        batch_count = 0
        for doc in tqdm(documents, desc="Extracting citations"):
            success = process_single_document(doc, session, stats)
            
            # Commit in batches
            batch_count += 1
            if batch_count >= CONFIG['SAVE_BATCH_SIZE']:
                session.commit()
                batch_count = 0
        
        # Final commit
        session.commit()
        
        # Calculate final statistics
        stats['end_time'] = datetime.now()
        stats['total_time'] = (stats['end_time'] - stats['start_time']).total_seconds()
        
        # Display results
        print("\n" + "="*70)
        print("  EXTRACTION COMPLETE")
        print("="*70)
        print(f"\nResults:")
        print(f"  Documents processed: {stats['documents_processed']}")
        print(f"  Foreign citations found: {stats['total_citations_found']}")
        print(f"  Errors: {stats['errors']}")
        print(f"\nAPI Usage:")
        print(f"  Input tokens: {stats['total_tokens_input']:,}")
        print(f"  Output tokens: {stats['total_tokens_output']:,}")
        print(f"  Total cost: ${stats['total_cost']:.2f}")
        print(f"\nPerformance:")
        print(f"  Total time: {stats['total_time']:.1f} seconds")
        print(f"  Avg time per document: {stats['total_time']/max(stats['documents_processed'],1):.1f} seconds")
        if stats['documents_processed'] > 0:
            print(f"  Avg citations per document: {stats['total_citations_found']/stats['documents_processed']:.1f}")
            print(f"  Avg cost per document: ${stats['total_cost']/stats['documents_processed']:.4f}")
        print("\n" + "="*70)
        
        # Save statistics to file
        stats_file = f"logs/citation_extraction_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(stats_file, 'w') as f:
            # Convert datetime objects to strings for JSON serialization
            stats_serializable = {
                k: str(v) if isinstance(v, datetime) else v
                for k, v in stats.items()
            }
            json.dump(stats_serializable, f, indent=2)
        
        print(f"\n✓ Statistics saved to: {stats_file}")
        
    except Exception as e:
        session.rollback()
        logging.error(f"Fatal error in main execution: {e}", exc_info=True)
        print(f"\n✗ Fatal error: {e}")
        
    finally:
        session.close()


# ============================================================================
# SCRIPT ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    """
    Execute when script is run directly.
    
    Usage:
        python scripts/phase2/extract_citations.py
    """
    main()
