#!/usr/bin/env python3
"""
Decision Classification Script (Phase 2a) - Version 1.0
======================================================================
Classifies documents as judicial decisions or non-decisions.

🏃 Run from: /home/gusrodgs/Gus/cienciaDeDados/phdMutley
Command: python scripts/phase2/classify_decisions.py

CLASSIFICATION STRATEGY:
1. First checks Document Title last word (from baseCompleta.xlsx)
   - If last word is "judgment" or "decision" → Direct classification (fast, no API cost)
2. If not clear from title → Uses Claude Sonnet 4.5 API for classification
   - Advanced LLM analysis with high accuracy
   - Costs ~$0.003 per document

STORES RESULTS IN:
- documents.is_decision (Boolean: True/False/NULL)
- documents.decision_classification_method ('document_title' or 'llm_sonnet')
- documents.decision_classification_confidence (Float: 0.0-1.0)
- documents.decision_classification_date (Timestamp)
- documents.decision_classification_reasoning (Text explanation)

Version 1.0 Features:
- Trial batch filtering support
- Document Title heuristic (fast path)
- LLM classification fallback (high accuracy)
- Comprehensive logging and statistics
- Rate limiting and error handling

Author: Lucas Biasetton & Assistant
Project: Doutorado PM
Version: 1.0
Date: November 2025
"""

import sys
import os
import time
import logging
import re
import pandas as pd
from tqdm import tqdm
from datetime import datetime
from uuid import uuid5
import anthropic
import json

# Database
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import URL

# ============================================================================
# CONFIGURATION & IMPORTS
# ============================================================================

sys.path.insert(0, '/home/gusrodgs/Gus/cienciaDeDados/phdMutley')
from config import (CONFIG, DB_CONFIG, LOGS_DIR, TRIAL_BATCH_CONFIG, 
                    DATABASE_FILE, UUID_NAMESPACE)

sys.path.insert(0, os.path.join('/home/gusrodgs/Gus/cienciaDeDados/phdMutley', 'scripts', 'phase0'))
from init_database import Document, ExtractedText

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / 'decision_classification.log'),
        logging.StreamHandler()
    ]
)
logging.getLogger('httpx').setLevel(logging.WARNING)

# ============================================================================
# API CLIENT SETUP
# ============================================================================

if not CONFIG['ANTHROPIC_API_KEY']:
    logging.error("CRITICAL: ANTHROPIC_API_KEY not found.")
    sys.exit(1)

client = anthropic.Anthropic(api_key=CONFIG['ANTHROPIC_API_KEY'])

# ============================================================================
# TRIAL BATCH FILTERING
# ============================================================================

def get_trial_batch_document_uuids():
    """
    Load Excel file and return set of Document UUIDs that are in the trial batch.
    Returns None if trial batch mode is disabled or if there's an error.
    
    INPUT: None (reads from config)
    ALGORITHM: 
        1. Check if trial batch mode is enabled
        2. Load Excel database
        3. Filter rows where trial batch column has TRUE values
        4. Convert Document IDs to UUIDs
        5. Return set of UUIDs
    OUTPUT: Set of UUIDs or None
    """
    if not TRIAL_BATCH_CONFIG['ENABLED']:
        logging.info("ℹ️  Trial batch mode DISABLED - will process all documents")
        return None
    
    try:
        df = pd.read_excel(DATABASE_FILE)
        logging.info(f"Loaded database with {len(df)} rows for trial batch filtering")
        
        col_name = TRIAL_BATCH_CONFIG['COLUMN_NAME']
        if col_name not in df.columns:
            logging.error(f"❌ Trial batch column '{col_name}' not found!")
            logging.error("   Proceeding without filtering")
            return None
        
        true_values = TRIAL_BATCH_CONFIG['TRUE_VALUES']
        trial_batch_df = df[df[col_name].isin(true_values)]
        
        # Convert Document IDs to UUIDs using same method as populate_metadata
        def generate_document_uuid(document_id_str):
            clean_id = str(document_id_str).strip().lower()
            return uuid5(UUID_NAMESPACE, f"document_{clean_id}")
        
        doc_uuids = set(trial_batch_df['Document ID'].apply(generate_document_uuid))
        
        logging.info("="*70)
        logging.info("TRIAL BATCH FILTERING FOR DECISION CLASSIFICATION")
        logging.info("="*70)
        logging.info(f"Total documents in database:  {len(df)}")
        logging.info(f"Trial batch documents:        {len(doc_uuids)}")
        logging.info(f"Will only classify these {len(doc_uuids)} documents")
        logging.info("="*70)
        
        return doc_uuids, trial_batch_df
        
    except Exception as e:
        logging.error(f"❌ Error loading trial batch filter: {e}")
        logging.error("   Proceeding without filtering")
        return None, None

# ============================================================================
# DOCUMENT TITLE ANALYSIS
# ============================================================================

def load_document_titles_mapping():
    """
    Load Document ID → Document Title mapping from Excel.
    
    INPUT: None (reads from DATABASE_FILE)
    ALGORITHM:
        1. Load Excel file
        2. Extract Document ID and Document Title columns
        3. Create UUID → Title mapping dictionary
    OUTPUT: Dictionary mapping UUID to Document Title string
    """
    try:
        df = pd.read_excel(DATABASE_FILE)
        
        if 'Document ID' not in df.columns or 'Document Title' not in df.columns:
            logging.error("❌ Required columns not found in Excel!")
            return {}
        
        # Create UUID mapping
        def generate_document_uuid(document_id_str):
            clean_id = str(document_id_str).strip().lower()
            return uuid5(UUID_NAMESPACE, f"document_{clean_id}")
        
        mapping = {}
        for _, row in df.iterrows():
            doc_uuid = generate_document_uuid(row['Document ID'])
            doc_title = str(row['Document Title']) if pd.notna(row['Document Title']) else ''
            mapping[doc_uuid] = doc_title
        
        logging.info(f"✓ Loaded {len(mapping)} document titles from Excel")
        return mapping
        
    except Exception as e:
        logging.error(f"❌ Error loading document titles: {e}")
        return {}

def check_title_last_word(document_title):
    """
    Check if the last word of Document Title positively indicates a decision.
    
    INPUT: document_title (string)
    ALGORITHM:
        1. Clean and normalize title (lowercase, strip)
        2. Split into words
        3. Extract last word
        4. Check if it's "judgment" or "decision"
    OUTPUT: 
        - (True, last_word) if DEFINITELY a decision (title match)
        - (None, last_word) if INCONCLUSIVE (defer to LLM)
    
    NOTE: This function only performs POSITIVE identification.
          If the title doesn't match, we cannot conclude it's NOT a decision.
          Non-matches should be analyzed by LLM.
    """
    if not document_title or pd.isna(document_title):
        return None, None
    
    # Clean and normalize
    title_clean = str(document_title).strip().lower()
    
    if not title_clean:
        return None, None
    
    # Extract last word (remove punctuation)
    words = re.findall(r'\b\w+\b', title_clean)
    
    if not words:
        return None, None
    
    last_word = words[-1]
    
    # Check against decision indicators
    decision_words = ['judgment', 'decision', 'judgement']  # Include both spellings
    
    if last_word in decision_words:
        # POSITIVE MATCH: Definitely a decision
        return True, last_word
    else:
        # NO MATCH: Inconclusive - need LLM analysis
        # We cannot conclude it's NOT a decision based on title alone
        return None, last_word

# ============================================================================
# LLM CLASSIFICATION
# ============================================================================

def classify_with_llm(document_text, metadata):
    """
    Use Claude Sonnet 4.5 to classify if document is a judicial decision.
    
    INPUT:
        - document_text: Full text of document
        - metadata: Document metadata dictionary
    
    ALGORITHM:
        1. Build structured prompt following Anthropic best practices
        2. Send to Claude Sonnet 4.5 API
        3. Parse JSON response
        4. Extract is_decision, confidence, and reasoning
    
    OUTPUT: 
        - (is_decision: bool, confidence: float, reasoning: str)
        - or (None, None, None) on error
    """
    doc_type = metadata.get('Document Type', 'Unknown')
    doc_title = metadata.get('Document Title', 'Unknown')
    
    # Limit text to first portion to save tokens
    classification_text_limit = CONFIG.get('CLASSIFICATION_TEXT_LIMIT', 8000)
    text_sample = document_text[:classification_text_limit]
    
    prompt = f"""You are an expert legal document classifier specializing in judicial decisions worldwide.

<task>
Analyze the provided document excerpt and determine whether it constitutes a JUDICIAL DECISION.
A judicial decision is a formal ruling, judgment, or order issued by a court or tribunal.
</task>

<document_metadata>
<document_type>{doc_type}</document_type>
<document_title>{doc_title}</document_title>
</document_metadata>

<classification_criteria>
<must_include>
- Issued by a court, tribunal, or judicial authority
- Contains legal reasoning and analysis
- Represents a binding determination on legal matters
- Authored or issued under judicial authority
</must_include>

<judicial_decision_indicators>
- Final or interim rulings on legal matters
- Appellate decisions reviewing lower court rulings
- Orders with legal reasoning (not purely procedural)
- Judgments resolving disputes
- Advisory opinions from judicial bodies
</judicial_decision_indicators>

<explicit_exclusions>
- Motions, petitions, or complaints filed by parties
- Legal briefs or memoranda submitted by counsel
- Administrative notices or regulatory announcements
- Press releases or media statements
- Settlement agreements
- Procedural orders without substantive legal analysis
- Legislative or executive branch documents
</explicit_exclusions>
</classification_criteria>

<instructions>
1. Carefully analyze the document excerpt below
2. Apply the classification criteria systematically
3. Provide clear reasoning for your determination
4. Assign a confidence score (0.0-1.0) based on the strength of evidence
5. Return your response ONLY as valid JSON in the exact format specified
</instructions>

<output_format>
Return ONLY valid JSON with no additional text or markdown:
{{
  "is_judicial_decision": true,
  "confidence_score": 0.95,
  "reasoning": "This document is a final appellate ruling issued by the Supreme Court. It contains comprehensive legal analysis, applies precedent, and renders a binding decision on the substantive legal issues presented. The document exhibits all characteristics of a judicial decision including formal court heading, case citation, detailed reasoning, and dispositive order."
}}

CRITICAL: Output ONLY the JSON object. No markdown, no code blocks, no explanatory text.
</output_format>

<document_excerpt>
{text_sample}
</document_excerpt>"""
    
    try:
        # API call with retry logic
        for attempt in range(3):
            try:
                time.sleep(1.5)  # Rate limiting
                
                message = client.messages.create(
                    model=CONFIG['CLASSIFICATION_MODEL'],  # claude-sonnet-4-20250514
                    max_tokens=1000,
                    temperature=0.0,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                response_text = message.content[0].text
                
                # Parse JSON
                # Remove any markdown code blocks if present
                response_clean = re.sub(r'```json\s*|\s*```', '', response_text).strip()
                
                data = json.loads(response_clean)
                
                is_decision = data.get('is_judicial_decision', False)
                confidence = data.get('confidence_score', 0.0)
                reasoning = data.get('reasoning', 'No reasoning provided')
                
                return is_decision, confidence, reasoning
                
            except json.JSONDecodeError as e:
                logging.error(f"JSON parse error (attempt {attempt + 1}/3): {e}")
                logging.error(f"Response was: {response_text[:500]}")
                if attempt == 2:
                    return None, None, f"JSON parse failed: {e}"
                time.sleep(2)
                
            except Exception as e:
                logging.error(f"API error (attempt {attempt + 1}/3): {e}")
                if attempt == 2:
                    return None, None, f"API error: {e}"
                time.sleep(5 * (attempt + 1))
        
    except Exception as e:
        logging.error(f"Unexpected error in LLM classification: {e}")
        return None, None, f"Unexpected error: {e}"

# ============================================================================
# MAIN CLASSIFICATION LOGIC
# ============================================================================

def classify_single_document(doc_uuid, extracted_text, document_titles, session, stats):
    """
    Classify a single document as decision or non-decision.
    
    INPUT:
        - doc_uuid: Document UUID
        - extracted_text: ExtractedText object with raw_text
        - document_titles: Dictionary mapping UUID to Document Title
        - session: SQLAlchemy session
        - stats: Statistics dictionary to update
    
    ALGORITHM:
        1. Get document from database
        2. Check if already classified (skip if yes)
        3. Try Document Title heuristic first
        4. If inconclusive, use LLM classification
        5. Store results in database
    
    OUTPUT: True if successful, False if error
    """
    try:
        # Get document record
        document = session.query(Document).filter(Document.document_id == doc_uuid).first()
        
        if not document:
            logging.warning(f"Document {doc_uuid} not found in database")
            stats['not_found'] += 1
            return False
        
        # Skip if already classified
        if document.is_decision is not None:
            logging.debug(f"Document {doc_uuid} already classified, skipping")
            stats['already_classified'] += 1
            return True
        
        # Get document title from Excel
        doc_title = document_titles.get(doc_uuid, '')
        
        # STRATEGY 1: Check Document Title last word (POSITIVE IDENTIFICATION ONLY)
        title_result, last_word = check_title_last_word(doc_title)
        
        if title_result is True:
            # POSITIVE MATCH: Title definitively indicates this is a decision
            document.is_decision = True
            document.decision_classification_method = 'document_title'
            document.decision_classification_confidence = 1.0  # Heuristic is definitive for positive matches
            document.decision_classification_date = datetime.now()
            document.decision_classification_reasoning = f"Last word of Document Title: '{last_word}'"
            
            session.commit()
            
            stats['decisions_title'] += 1
            logging.info(f"✓ Decision (Title): {doc_uuid} - '{last_word}'")
            
            return True
        
        # STRATEGY 2: LLM Classification (for all non-matching titles)
        # Note: We cannot conclude non-matching titles are NOT decisions
        # They could be decisions with different title formats, so we need LLM analysis
        logging.info(f"Using LLM for {doc_uuid} (title: '{last_word}' - inconclusive)")
        
        if not extracted_text.raw_text:
            logging.warning(f"No text available for {doc_uuid}")
            stats['no_text'] += 1
            return False
        
        metadata = document.metadata_json or {}
        is_decision, confidence, reasoning = classify_with_llm(extracted_text.raw_text, metadata)
        
        if is_decision is None:
            # LLM classification failed
            logging.error(f"LLM classification failed for {doc_uuid}: {reasoning}")
            stats['llm_errors'] += 1
            return False
        
        # Store LLM classification
        document.is_decision = is_decision
        document.decision_classification_method = 'llm_sonnet'
        document.decision_classification_confidence = confidence
        document.decision_classification_date = datetime.now()
        document.decision_classification_reasoning = reasoning
        
        session.commit()
        
        if is_decision:
            stats['decisions_llm'] += 1
            logging.info(f"✓ Decision (LLM): {doc_uuid} - confidence {confidence:.2f}")
        else:
            stats['non_decisions_llm'] += 1
            logging.info(f"✗ Non-Decision (LLM): {doc_uuid} - confidence {confidence:.2f}")
        
        return True
        
    except Exception as e:
        session.rollback()
        logging.error(f"Error classifying document {doc_uuid}: {e}")
        stats['errors'] += 1
        return False

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """
    Main execution function.
    
    INPUT: None
    ALGORITHM:
        1. Load trial batch filter (if enabled)
        2. Load document titles from Excel
        3. Query documents with extracted text
        4. Filter by trial batch
        5. Classify each document
        6. Report statistics
    OUTPUT: Statistics printed to log
    """
    logging.info("="*70)
    logging.info("DECISION CLASSIFICATION - VERSION 1.0")
    logging.info(f"Classification Model: {CONFIG['CLASSIFICATION_MODEL']}")
    logging.info("="*70)
    
    # Load trial batch filter
    trial_batch_result = get_trial_batch_document_uuids()
    if trial_batch_result:
        trial_batch_uuids, trial_batch_df = trial_batch_result
    else:
        trial_batch_uuids = None
        trial_batch_df = None
    
    # Load document titles
    logging.info("Loading document titles from Excel...")
    document_titles = load_document_titles_mapping()
    
    if not document_titles:
        logging.error("❌ Failed to load document titles. Exiting.")
        return
    
    # Connect to database
    engine = create_engine(URL.create(**DB_CONFIG))
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Query documents with extracted text
        query = session.query(
            Document.document_id,
            ExtractedText
        ).join(ExtractedText).filter(
            ExtractedText.raw_text != None
        )
        
        # Filter by trial batch if enabled
        if trial_batch_uuids is not None:
            query = query.filter(Document.document_id.in_(trial_batch_uuids))
            logging.info(f"Applied trial batch filter: {len(trial_batch_uuids)} documents")
        
        # Exclude already classified (optional - comment out to re-classify)
        # query = query.filter(Document.is_decision == None)
        
        results = query.all()
        
        logging.info(f"Found {len(results)} documents to classify")
        
        if len(results) == 0:
            logging.warning("⚠️  No documents to process!")
            return
        
        # Initialize statistics
        stats = {
            'decisions_title': 0,
            'decisions_llm': 0,
            'non_decisions_llm': 0,  # Note: Title-based never classifies as non-decision
            'already_classified': 0,
            'no_text': 0,
            'llm_errors': 0,
            'errors': 0,
            'not_found': 0
        }
        
        # Process each document
        for doc_uuid, extracted_text in tqdm(results, desc="Classifying"):
            classify_single_document(doc_uuid, extracted_text, document_titles, session, stats)
        
        # Report statistics
        logging.info("\n" + "="*70)
        logging.info("CLASSIFICATION SUMMARY")
        logging.info("="*70)
        logging.info(f"Documents classified as DECISIONS:")
        logging.info(f"  - Via Document Title:  {stats['decisions_title']}")
        logging.info(f"  - Via LLM Analysis:    {stats['decisions_llm']}")
        logging.info(f"  - TOTAL DECISIONS:     {stats['decisions_title'] + stats['decisions_llm']}")
        logging.info("")
        logging.info(f"Documents classified as NON-DECISIONS:")
        logging.info(f"  - Via LLM Analysis:    {stats['non_decisions_llm']}")
        logging.info(f"  - (Title-based classification only identifies decisions, not non-decisions)")
        logging.info("")
        logging.info(f"Already classified:      {stats['already_classified']}")
        logging.info(f"No text available:       {stats['no_text']}")
        logging.info(f"LLM errors:              {stats['llm_errors']}")
        logging.info(f"Other errors:            {stats['errors']}")
        
        if TRIAL_BATCH_CONFIG['ENABLED']:
            logging.info(f"\n✓ Trial batch mode was ENABLED")
            logging.info(f"  Only processed documents from trial batch")
        
        logging.info("="*70)
        
    finally:
        session.close()

if __name__ == "__main__":
    main()
