#!/usr/bin/env python3
"""
Citation Extraction Script (Phase 2b) - Version 4.0
======================================================================
Extracts cross-jurisdictional citations from documents CLASSIFIED AS DECISIONS.

🏃 Run from: /home/gusrodgs/Gus/cienciaDeDados/phdMutley
Command: python scripts/phase2/extract_citations.py

VERSION 4.0 - DECISION-ONLY PROCESSING
- ONLY processes documents where is_decision = True
- Uses Claude Haiku 4.5 for citation extraction
- Trial batch filtering support
- Dynamic Context Injection (Binding Courts)
- 3-Category Classification (Foreign / International / Foreign International)

CRITICAL REQUIREMENT:
- Documents MUST be classified first using classify_decisions.py
- This script will skip any document where is_decision is NULL or False

Version 4.0 Changes:
- Added filtering by is_decision = True
- Removed LLM classification (now handled by classify_decisions.py)
- Simplified to focus only on citation extraction
- Enhanced logging to show decision filter statistics

Author: Lucas Biasetton & Assistant
Project: Doutorado PM
Version: 4.0
Date: November 2025
"""

import sys
import os
import time
import json
import logging
import re
import pandas as pd
from tqdm import tqdm
import anthropic

# Database
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import URL

# ============================================================================
# CONFIGURATION & IMPORTS
# ============================================================================

sys.path.insert(0, '/home/gusrodgs/Gus/cienciaDeDados/phdMutley')
from config import (CONFIG, DB_CONFIG, LOGS_DIR, TRIAL_BATCH_CONFIG, 
                    DATABASE_FILE, UUID_NAMESPACE, get_binding_courts)

sys.path.insert(0, os.path.join('/home/gusrodgs/Gus/cienciaDeDados/phdMutley', 'scripts', 'phase0'))
from init_database import Case, Document, ExtractedText, Citation, CitationExtraction

from uuid import uuid5

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / 'citation_extraction.log'),
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
        logging.info("ℹ️  Trial batch mode DISABLED - will process all classified decisions")
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
        logging.info("TRIAL BATCH FILTERING FOR CITATION EXTRACTION")
        logging.info("="*70)
        logging.info(f"Total documents in database:  {len(df)}")
        logging.info(f"Trial batch documents:        {len(doc_uuids)}")
        logging.info(f"Will only extract citations from these {len(doc_uuids)} documents")
        logging.info("="*70)
        
        return doc_uuids
        
    except Exception as e:
        logging.error(f"❌ Error loading trial batch filter: {e}")
        logging.error("   Proceeding without filtering")
        return None

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def extract_json_from_text(text):
    """
    Robust regex-based JSON extraction.
    
    INPUT: text (string containing JSON)
    ALGORITHM:
        1. Try to find JSON object pattern in text
        2. Remove markdown code blocks if present
        3. Parse as JSON
    OUTPUT: Parsed JSON dict or None on error
    """
    try:
        # Remove markdown code blocks
        text_clean = re.sub(r'```json\s*|\s*```', '', text).strip()
        
        # Try to find JSON object
        match = re.search(r'\{[\s\S]*\}', text_clean)
        if match:
            return json.loads(match.group(0))
        return json.loads(text_clean)
    except Exception:
        return None

def find_citation_indices(full_text, citation_string_raw):
    """
    Locates citation character indices in full text.
    
    INPUT:
        - full_text: Complete document text
        - citation_string_raw: Citation string to find
    ALGORITHM:
        1. Search for exact match of citation string
        2. Calculate start and end indices
    OUTPUT: (start_index, end_index) or (None, None)
    """
    if not citation_string_raw or not full_text:
        return None, None
    try:
        start_index = full_text.find(citation_string_raw)
        if start_index != -1:
            return start_index, start_index + len(citation_string_raw)
    except Exception:
        pass
    return None, None

def extract_citation_paragraph(text, start_index, end_index):
    """
    Extracts full paragraph containing the citation.
    
    INPUT:
        - text: Full document text
        - start_index: Citation start position
        - end_index: Citation end position
    ALGORITHM:
        1. Find previous paragraph break (double newline)
        2. Find next paragraph break
        3. Extract text between breaks
    OUTPUT: Paragraph text or None
    """
    if not text or start_index is None or end_index is None:
        return None
    
    # Find start (previous double newline)
    paragraph_start = text.rfind('\n\n', 0, start_index)
    paragraph_start = 0 if paragraph_start == -1 else paragraph_start + 2

    # Find end (next double newline)
    paragraph_end = text.find('\n\n', end_index)
    paragraph_end = len(text) if paragraph_end == -1 else paragraph_end

    return text[paragraph_start:paragraph_end].strip()

def generate_citation_extraction_prompt(document_text, source_court, source_country, source_jurisdiction, binding_courts):
    """
    Generate structured prompt for citation extraction using Claude Haiku.
    
    INPUT:
        - document_text: Full text of decision
        - source_court: Name of court that issued decision
        - source_country: Country of court
        - source_jurisdiction: Jurisdiction details
        - binding_courts: List of courts that bind this court
    
    ALGORITHM:
        1. Build XML-structured prompt with metadata
        2. Include binding courts context
        3. Specify JSON output format
        4. Define citation categories
    
    OUTPUT: Formatted prompt string
    """
    
    prompt = f"""You are an expert legal citation extractor specializing in cross-jurisdictional judicial citations.

<task>
Extract ALL citations to FOREIGN or INTERNATIONAL courts/tribunals from this judicial decision.
Focus ONLY on citations where the decision explicitly references another court's ruling.
</task>

<source_document_context>
<court>{source_court}</court>
<country>{source_country}</country>
<jurisdiction>{source_jurisdiction}</jurisdiction>
</source_document_context>

<binding_courts_context>
The following courts/tribunals have binding or persuasive authority over this court:
{binding_courts}

IMPORTANT: Citations to these binding courts should be included if they meet citation criteria.
</binding_courts_context>

<citation_categories>
1. FOREIGN CITATION
   - Citation to a court from a DIFFERENT country
   - Example: A Brazilian court citing a US Supreme Court decision
   - Example: A French court citing a German Constitutional Court ruling

2. INTERNATIONAL CITATION  
   - Citation to an INTERNATIONAL court or tribunal
   - Examples: European Court of Human Rights, International Court of Justice, 
     Inter-American Court of Human Rights, etc.
   - These courts have jurisdiction across multiple countries

3. FOREIGN INTERNATIONAL CITATION
   - Citation to an international court that does NOT have direct jurisdiction over the source country
   - Example: A US court citing the European Court of Human Rights
   - Example: A Brazilian court citing the African Court on Human and Peoples' Rights
</citation_categories>

<extraction_rules>
INCLUDE:
- Citations to judicial decisions from other countries
- Citations to international court/tribunal decisions
- Citations referencing specific case names, docket numbers, or decisions
- Both primary citations (direct case references) and secondary citations (cited in other sources)

EXCLUDE:
- Citations to DOMESTIC precedent (same country as source court)
- References to statutes, regulations, or treaties (not judicial decisions)
- Citations to legal scholars or academic writings
- General references to foreign legal systems without citing specific decisions
- Citations to non-judicial bodies (legislatures, administrative agencies, etc.)

CRITICAL: Carefully distinguish between:
- Domestic courts (EXCLUDE even if lower/higher in hierarchy)
- Foreign courts from other countries (INCLUDE)
- International courts (INCLUDE)
</extraction_rules>

<output_format>
Return ONLY valid JSON with no additional text:
{{
  "foreign_citations": [
    {{
      "cited_case_name": "Brown v. Board of Education",
      "cited_court": "United States Supreme Court",
      "cited_jurisdiction": "United States federal courts",
      "cited_country": "United States",
      "cited_year": 1954,
      "cited_case_number": "347 U.S. 483",
      "citation_type": "Foreign Citation",
      "citation_string_raw": "Brown v. Board of Education, 347 U.S. 483 (1954)",
      "confidence_score": 0.95
    }}
  ],
  "domestic_citations_excluded": 5,
  "total_citations_found": 6
}}

CRITICAL: Output ONLY the JSON object. No markdown, no code blocks, no explanatory text.
</output_format>

<document_full_text>
{document_text}
</document_full_text>"""
    
    return prompt

# ============================================================================
# PROCESSING LOGIC
# ============================================================================

def process_single_document(doc, session, stats):
    """
    Process a single DECISION document for citation extraction.
    
    INPUT:
        - doc: Query result tuple (document_id, metadata_json, raw_text, court_name, country, case_id)
        - session: SQLAlchemy session
        - stats: Statistics dictionary to update
    
    ALGORITHM:
        1. Verify document is classified as decision (should already be filtered)
        2. Build citation extraction prompt with context
        3. Call Claude Haiku API
        4. Parse JSON response
        5. Save citations to database
        6. Update statistics
    
    OUTPUT: True if successful, False if error
    """
    try:
        # Unpack document tuple
        document_id, metadata_json, raw_text, court_name, country, case_id = doc
        
        # Get full document record to check is_decision
        document = session.query(Document).filter(Document.document_id == document_id).first()
        
        if not document:
            logging.warning(f"Document {document_id} not found")
            stats['errors'] += 1
            return False
        
        # Verify it's a decision (defensive check - should already be filtered)
        if not document.is_decision:
            logging.warning(f"Document {document_id} is not a decision! Skipping.")
            stats['not_decisions'] += 1
            return False
        
        # Check if already processed
        existing = session.query(CitationExtraction).filter(
            CitationExtraction.document_id == document_id
        ).first()
        
        if existing:
            logging.debug(f"Document {document_id} already processed")
            stats['already_processed'] += 1
            return True
        
        # Prepare extraction
        logging.info(f"Extracting citations from Document {document_id} with Haiku...")
        
        metadata = metadata_json or {}
        source_court = court_name or "Unknown Court"
        source_country = country or "Unknown Country"
        source_jurisdiction = metadata.get('Jurisdictions', f"{source_country} courts")
        
        # Get binding courts for this jurisdiction
        binding_courts = get_binding_courts(source_country)
        
        # Generate prompt
        prompt = generate_citation_extraction_prompt(
            raw_text, source_court, source_country, source_jurisdiction, binding_courts
        )
        
        # Call Claude Haiku API with retry logic
        response_text = None
        start_time = time.time()
        
        for attempt in range(3):
            try:
                time.sleep(1.5)  # Rate limiting
                
                message = client.messages.create(
                    model=CONFIG['ANTHROPIC_MODEL'],  # claude-haiku-4-5-20251001
                    max_tokens=CONFIG['MODEL_MAX_OUTPUT'],
                    temperature=0.0,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                response_text = message.content[0].text
                break
                
            except Exception as e:
                if attempt == 2:
                    logging.error(f"Extraction failed after 3 attempts: {e}")
                    stats['errors'] += 1
                    
                    # Log failure to database
                    extraction = CitationExtraction(
                        document_id=document_id,
                        model_used=CONFIG['ANTHROPIC_MODEL'],
                        extraction_success=False,
                        extraction_error=f"API error: {str(e)}"
                    )
                    session.add(extraction)
                    session.commit()
                    
                    return False
                time.sleep(5 * (attempt + 1))
        
        extraction_time = time.time() - start_time
        
        # Parse JSON response
        data = extract_json_from_text(response_text)
        if not data:
            logging.error(f"JSON Parse Failed for {document_id}")
            logging.error(f"Response was: {response_text[:500]}")
            stats['parse_errors'] += 1
            
            # Log failure
            extraction = CitationExtraction(
                document_id=document_id,
                model_used=CONFIG['ANTHROPIC_MODEL'],
                extraction_success=False,
                extraction_error="JSON parse failure",
                raw_llm_response={"raw_response": response_text[:1000]}
            )
            session.add(extraction)
            session.commit()
            
            return False
        
        # Extract citations
        citations_list = data.get('foreign_citations', [])
        valid_citations = [
            c for c in citations_list 
            if c.get('confidence_score', 0) >= CONFIG['MIN_CONFIDENCE']
        ]
        
        # Calculate API cost
        input_tokens = message.usage.input_tokens
        output_tokens = message.usage.output_tokens
        # Haiku 4.5 pricing: $0.25/M input, $1.25/M output
        cost = (input_tokens/1e6 * 0.25) + (output_tokens/1e6 * 1.25)
        
        # Create extraction record
        extraction = CitationExtraction(
            document_id=document_id,
            model_used=CONFIG['ANTHROPIC_MODEL'],
            total_citations_found=len(citations_list),
            foreign_citations_count=len(valid_citations),
            domestic_citations_excluded=data.get('domestic_citations_excluded', 0),
            api_tokens_input=input_tokens,
            api_tokens_output=output_tokens,
            api_cost_usd=cost,
            extraction_time_seconds=extraction_time,
            extraction_success=True,
            raw_llm_response=data
        )
        session.add(extraction)
        session.flush()  # Get extraction_id
        
        # Create citation records
        for i, citation_data in enumerate(valid_citations):
            # Find citation location in text
            start_idx, end_idx = find_citation_indices(
                raw_text, 
                citation_data.get('citation_string_raw')
            )
            paragraph = extract_citation_paragraph(raw_text, start_idx, end_idx)
            
            # Create citation record
            citation = Citation(
                extraction_id=extraction.extraction_id,
                case_id=case_id,
                document_id=document_id,
                cited_case_name=citation_data.get('cited_case_name', 'Unknown'),
                cited_court=citation_data.get('cited_court'),
                cited_jurisdiction=citation_data.get('cited_jurisdiction'),
                cited_country=citation_data.get('cited_country'),
                cited_year=citation_data.get('cited_year'),
                citation_type=citation_data.get('citation_type'),
                citation_string_raw=citation_data.get('citation_string_raw'),
                citation_paragraph=paragraph,
                confidence_score=citation_data.get('confidence_score'),
                position_in_document=i+1,
                start_char_index=start_idx,
                end_char_index=end_idx
            )
            session.add(citation)
        
        session.commit()
        
        stats['processed'] += 1
        stats['citations'] += len(valid_citations)
        
        logging.info(f"✓ Extracted {len(valid_citations)} citations from {document_id}")
        
        return True
        
    except Exception as e:
        session.rollback()
        logging.error(f"Error processing document: {e}")
        import traceback
        logging.error(traceback.format_exc())
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
        2. Query documents classified as decisions (is_decision = True)
        3. Filter by trial batch if enabled
        4. Exclude already processed documents
        5. Process each document for citation extraction
        6. Report statistics
    OUTPUT: Statistics printed to log
    """
    logging.info("="*70)
    logging.info("CITATION EXTRACTION (PHASE 2b) - VERSION 4.0")
    logging.info(f"Extraction Model: {CONFIG['ANTHROPIC_MODEL']} (Haiku 4.5)")
    logging.info("ONLY processes documents with is_decision = True")
    logging.info("="*70)

    # Get trial batch filter
    trial_batch_uuids = get_trial_batch_document_uuids()

    # Connect to database
    engine = create_engine(URL.create(**DB_CONFIG))
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Query documents that are DECISIONS with extracted text
        logging.info("Querying documents classified as decisions...")
        
        query = session.query(
            Document.document_id,
            Document.metadata_json,
            ExtractedText.raw_text,
            Case.court_name,
            Case.country,
            Case.case_id
        ).join(
            ExtractedText, Document.document_id == ExtractedText.document_id
        ).join(
            Case, Document.case_id == Case.case_id
        ).filter(
            ExtractedText.raw_text != None,
            Document.is_decision == True  # CRITICAL: Only process decisions
        )

        # Count total decisions before other filters
        total_decisions = query.count()
        logging.info(f"Found {total_decisions} documents classified as decisions")

        # Filter by trial batch if enabled
        if trial_batch_uuids is not None:
            query = query.filter(Document.document_id.in_(trial_batch_uuids))
            trial_filtered_count = query.count()
            logging.info(f"After trial batch filter: {trial_filtered_count} documents")

        # Exclude already processed
        processed_ids = [
            id[0] for id in 
            session.query(CitationExtraction.document_id).all()
        ]
        if processed_ids:
            query = query.filter(~Document.document_id.in_(processed_ids))
            logging.info(f"Excluding {len(processed_ids)} already processed documents")

        # Get final list
        documents = query.all()

        logging.info(f"Documents to process: {len(documents)}")
        
        if len(documents) == 0:
            logging.warning("⚠️  No documents to process!")
            logging.info("\nPossible reasons:")
            logging.info("1. All decisions have already been processed")
            logging.info("2. No documents have been classified yet - run classify_decisions.py first")
            logging.info("3. Trial batch filter excluded all documents")
            return
        
        # Initialize statistics
        stats = {
            'processed': 0,
            'citations': 0,
            'already_processed': 0,
            'not_decisions': 0,
            'parse_errors': 0,
            'errors': 0
        }
        
        # Process each document
        for doc in tqdm(documents, desc="Extracting Citations"):
            process_single_document(doc, session, stats)

        # Report statistics
        logging.info("\n" + "="*70)
        logging.info("CITATION EXTRACTION SUMMARY")
        logging.info("="*70)
        logging.info(f"Total decisions in database:  {total_decisions}")
        logging.info(f"Documents processed:          {stats['processed']}")
        logging.info(f"Total citations extracted:    {stats['citations']}")
        logging.info(f"Already processed (skipped):  {stats['already_processed']}")
        logging.info(f"JSON parse errors:            {stats['parse_errors']}")
        logging.info(f"Other errors:                 {stats['errors']}")
        
        if stats['not_decisions'] > 0:
            logging.warning(f"⚠️  Documents that were not decisions: {stats['not_decisions']}")
            logging.warning("   This should not happen - check classification process")
        
        if TRIAL_BATCH_CONFIG['ENABLED']:
            logging.info(f"\n✓ Trial batch mode was ENABLED")
            logging.info(f"  Only processed documents from trial batch")
        
        logging.info("="*70)

    finally:
        session.close()

if __name__ == "__main__":
    main()
