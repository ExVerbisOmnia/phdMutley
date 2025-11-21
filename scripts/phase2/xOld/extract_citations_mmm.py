#!/usr/bin/env python3
"""
Citation Extraction Script (Phase 2) - WITH DOCUMENT CLASSIFICATION
=====================================================================
STEP 1: Verifies if document is a judicial decision using Claude API
STEP 2: If YES → Extracts FOREIGN and INTERNATIONAL citations
        If NO  → Flags document as NOT_A_DECISION and skips extraction

Populates the database with structured citation data and text locations.

🗂️ Run from: /home/gusrodgs/Gus/cienciaDeDados/phdMutley
Command: python scripts/phase2/extract_citations_with_classification.py

Features:
- Document Type Validation: Verifies document is actually a judicial decision
- "Smart" Prompting: Negative constraints for domestic courts & Idem/Ibid resolution
- Exact Text Location: Calculates start/end indices for highlighting
- Cost Tracking: logs token usage and estimated cost per document
- Non-Decision Flagging: Uses extraction_error='NOT_A_DECISION' to mark non-decisions
"""

import sys
import os
import time
import json
import logging
from datetime import datetime
from tqdm import tqdm
import anthropic

# Database
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import URL

# ============================================================================
# CONFIGURATION & IMPORTS
# ============================================================================

# Add project root to path to import config
sys.path.insert(0, '/home/gusrodgs/Gus/cienciaDeDados/phdMutley')
from config import CONFIG, DB_CONFIG, LOGS_DIR, TEST_CONFIG

# Import database models
sys.path.insert(0, os.path.join('/home/gusrodgs/Gus/cienciaDeDados/phdMutley', 'scripts', 'phase0'))
from init_database_pg18 import Case, Document, ExtractedText, Citation, CitationExtraction

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

# Suppress verbose API logs
logging.getLogger('httpx').setLevel(logging.WARNING)

# ============================================================================
# API CLIENT SETUP
# ============================================================================

if not CONFIG['ANTHROPIC_API_KEY']:
    logging.error("CRITICAL: ANTHROPIC_API_KEY not found in config/env.")
    sys.exit(1)

client = anthropic.Anthropic(api_key=CONFIG['ANTHROPIC_API_KEY'])

# ============================================================================
# NEW: DOCUMENT CLASSIFICATION FUNCTION
# ============================================================================

def check_if_judicial_decision(document_text, metadata):
    """
    Uses Claude API to determine if the document is a JUDICIAL DECISION.
    
    INPUT:
    - document_text: Full text of the document (truncated to first 3000 chars)
    - metadata: Document metadata dict containing Document Type, Title, etc.
    
    ALGORITHM:
    1. Constructs a classification prompt asking Claude to evaluate the document
    2. Sends first 3000 characters to Claude API with classification criteria
    3. Parses JSON response to determine if it's a judicial decision
    
    OUTPUT:
    - is_decision (bool): True if document is a judicial decision, False otherwise
    - classification_data (dict): Full LLM response with reasoning
    """
    
    # Prepare metadata context
    doc_type = metadata.get('Document Type', 'Unknown')
    doc_title = metadata.get('Document Title', 'Unknown')
    
    # Construct classification prompt
    prompt = f"""Analyze the following legal document and determine if it is a JUDICIAL DECISION (a court ruling/judgment/verdict/order).

DOCUMENT METADATA:
- Stated Document Type: {doc_type}
- Document Title: {doc_title}

CLASSIFICATION CRITERIA:
A document IS a JUDICIAL DECISION if it:
1. Is a final or interim ruling issued by a court or tribunal
2. Contains the court's reasoning and judgment on a legal matter
3. Includes elements like: findings of fact, legal analysis, and a ruling/order
4. Is authored by a judge or panel of judges

A document IS NOT a JUDICIAL DECISION if it is:
1. A procedural motion or filing
2. A complaint, petition, or brief filed by parties
3. An administrative document or correspondence
4. A transcript of oral arguments
5. A settlement agreement
6. Any document that does not contain a court's ruling

REQUIRED OUTPUT (JSON ONLY, NO OTHER TEXT):
{{
  "is_judicial_decision": true or false,
  "reasoning": "Brief explanation (1-2 sentences)",
  "document_type_detected": "decision|motion|complaint|brief|administrative|transcript|other",
  "confidence": 0.95
}}

DOCUMENT TEXT (First 3000 characters):
{document_text[:3000]}

...

[Text truncated for classification purposes]
"""
    
    # Call Claude API
    try:
        message = client.messages.create(
            model=CONFIG['ANTHROPIC_MODEL'],
            max_tokens=500,  # Small response expected for classification
            temperature=0.0,  # Deterministic classification
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = message.content[0].text
        
        # Parse JSON response (clean markdown if present)
        clean_json = response_text.strip()
        if clean_json.startswith('```'):
            clean_json = clean_json.split('```')[1]
            if clean_json.startswith('json'):
                clean_json = clean_json[4:]
            clean_json = clean_json.strip()
        
        data = json.loads(clean_json)
        
        is_decision = data.get('is_judicial_decision', False)
        
        # Add token usage to response data for cost tracking
        data['_classification_tokens'] = {
            'input': message.usage.input_tokens,
            'output': message.usage.output_tokens
        }
        
        return is_decision, data
        
    except json.JSONDecodeError as e:
        logging.error(f"JSON Parse Error in classification: {e}")
        logging.error(f"Raw response: {response_text}")
        # If we can't parse, assume it IS a decision to avoid false negatives
        return True, {
            "error": "JSON parse failed",
            "assumed_decision": True,
            "raw_response": response_text
        }
    except Exception as e:
        logging.error(f"Error in document classification: {e}")
        # On any error, assume it IS a decision (fail-safe approach)
        return True, {
            "error": str(e),
            "assumed_decision": True
        }

# ============================================================================
# HELPER FUNCTIONS (Citation Extraction)
# ============================================================================

def find_citation_indices(full_text, citation_string_raw):
    """
    Locates the start and end character indices of the citation in the text.
    Used for highlighting/UI purposes.
    """
    if not citation_string_raw or not full_text:
        return None, None
        
    try:
        # Simple first-match search
        start_index = full_text.find(citation_string_raw)
        if start_index != -1:
            return start_index, start_index + len(citation_string_raw)
    except Exception:
        pass
    return None, None

def generate_citation_extraction_prompt(document_text, source_court, source_country, source_jurisdiction):
    """
    Generate structured prompt with Negative Constraints and Idem resolution.
    """
    # Truncate text if too long (cost control)
    if len(document_text) > CONFIG['MAX_TEXT_CONTEXT']:
        document_text = document_text[:CONFIG['MAX_TEXT_CONTEXT']]
        document_text += "\n\n[... Text truncated for length ...]"
    
    prompt = f"""You are analyzing a judicial decision to extract ONLY foreign and international citations.

SOURCE CONTEXT:
- Source Country: {source_country}
- Source Court: {source_court}
- Jurisdiction: {source_jurisdiction}

NEGATIVE CONSTRAINTS (CRITICAL):
1. Explicitly IGNORE any citation to courts within {source_country}.
2. If the source country is Brazil, ignore STF, STJ, TRF, and TJ citations.
3. If the source country is Colombia, ignore Corte Constitucional, Consejo de Estado.
4. Do not cite the document itself.

IDEM/IBID RESOLUTION:
- If you encounter 'Idem', 'Ibid', or 'supra', attempt to resolve it to the immediate previously cited foreign case.
- If it refers to a domestic case, ignore it.
- If it refers to a foreign case, extract it as a new entry with the resolved name.

REQUIRED OUTPUT JSON FORMAT:
Return ONLY a valid JSON object. No other text.
{{
  "foreign_citations": [
    {{
      "cited_case_name": "Full case name",
      "cited_court": "Court name",
      "cited_jurisdiction": "Jurisdiction",
      "cited_country": "Country",
      "cited_year": 2023,
      "citation_context": "Brief context (1 sentence)",
      "citation_type": "precedential|persuasive|informational",
      "citation_string_raw": "Exact text snippet from document",
      "confidence_score": 0.95
    }}
  ],
  "domestic_citations_excluded": 0,
  "total_citations_found": 0
}}

TEXT TO ANALYZE:
{document_text}
"""
    return prompt

# ============================================================================
# PROCESSING LOGIC
# ============================================================================

def process_single_document(doc, session, stats):
    """
    Process one document in TWO STEPS:
    
    STEP 1: Check if document is a judicial decision
    - If NO  → Flag as NOT_A_DECISION, skip citation extraction
    - If YES → Proceed to Step 2
    
    STEP 2: Extract citations using Claude API
    - Parse JSON response
    - Save to database
    - Track costs and statistics
    
    INPUT: 
    - doc: Document object with metadata and raw_text
    - session: SQLAlchemy session
    - stats: Dictionary to accumulate processing statistics
    
    OUTPUT:
    - True if successfully processed (regardless of whether it's a decision)
    - False if an error occurred
    """
    try:
        # ========================================================================
        # STEP 1: DOCUMENT CLASSIFICATION
        # ========================================================================
        
        metadata = doc.metadata_json or {}
        
        logging.info(f"Checking if document {doc.document_id} is a judicial decision...")
        
        is_decision, classification_data = check_if_judicial_decision(
            doc.raw_text, 
            metadata
        )
        
        # Track classification API cost
        classification_tokens = classification_data.get('_classification_tokens', {})
        classification_cost = (
            classification_tokens.get('input', 0) / 1e6 * 0.25 +
            classification_tokens.get('output', 0) / 1e6 * 1.25
        )
        stats['classification_cost'] += classification_cost
        
        # If NOT a judicial decision, flag it and stop
        if not is_decision:
            logging.info(
                f"❌ Document {doc.document_id} classified as NON-DECISION. "
                f"Reason: {classification_data.get('reasoning', 'Unknown')}"
            )
            
            # Create extraction record with NOT_A_DECISION flag
            extraction = CitationExtraction(
                document_id=doc.document_id,
                extraction_success=False,
                extraction_error="NOT_A_DECISION",  # FLAG FOR NON-DECISIONS
                raw_llm_response=classification_data,  # Store classification reasoning
                model_used=CONFIG['ANTHROPIC_MODEL'],
                total_citations_found=0,
                foreign_citations_count=0,
                domestic_citations_excluded=0,
                api_tokens_input=classification_tokens.get('input', 0),
                api_tokens_output=classification_tokens.get('output', 0),
                api_cost_usd=classification_cost,
                extraction_time_seconds=0  # Classification was quick
            )
            session.add(extraction)
            session.commit()
            
            stats['non_decisions'] += 1
            return True  # Successfully processed (determined it's not a decision)
        
        # If it IS a decision, log and proceed
        logging.info(
            f"✅ Document {doc.document_id} confirmed as JUDICIAL DECISION. "
            f"Confidence: {classification_data.get('confidence', 'N/A')}"
        )
        stats['decisions'] += 1
        
        # ========================================================================
        # STEP 2: CITATION EXTRACTION (Existing code)
        # ========================================================================
        
        # Prepare context for citation extraction
        source_court = doc.court_name or "Unknown Court"
        source_country = doc.country or "Unknown Country"
        source_jurisdiction = metadata.get('Jurisdictions', f"{source_country} courts")
        
        prompt = generate_citation_extraction_prompt(
            doc.raw_text, source_court, source_country, source_jurisdiction
        )
        
        # Call API with retry for citation extraction
        response_text = None
        start_time = time.time()
        
        for attempt in range(3):
            try:
                message = client.messages.create(
                    model=CONFIG['ANTHROPIC_MODEL'],
                    max_tokens=CONFIG['MAX_LLM_TOKENS'],
                    temperature=0.0,  # Deterministic
                    messages=[{"role": "user", "content": prompt}]
                )
                response_text = message.content[0].text
                break
            except Exception as e:
                if attempt == 2:
                    raise e
                time.sleep(2)

        extraction_time = time.time() - start_time
        
        # Parse citation JSON
        try:
            # Clean markdown if present
            clean_json = response_text.strip()
            if clean_json.startswith('```'):
                clean_json = clean_json.split('```')[1]
                if clean_json.startswith('json'):
                    clean_json = clean_json[4:]
            
            data = json.loads(clean_json)
        except json.JSONDecodeError:
            logging.error(f"JSON Parse Error for {doc.document_id}")
            # Log failure in DB
            extraction = CitationExtraction(
                document_id=doc.document_id,
                extraction_success=False,
                extraction_error="JSON Parse Failed - Citation Extraction",
                raw_llm_response=response_text,
                model_used=CONFIG['ANTHROPIC_MODEL']
            )
            session.add(extraction)
            session.commit()
            stats['errors'] += 1
            return False

        # Filter & Save to DB
        foreign_citations = data.get('foreign_citations', [])
        valid_citations = [
            c for c in foreign_citations 
            if c.get('confidence_score', 0) >= CONFIG['MIN_CONFIDENCE']
        ]
        
        # Calculate citation extraction cost
        input_tokens = message.usage.input_tokens
        output_tokens = message.usage.output_tokens
        citation_cost = (input_tokens/1e6 * 0.25) + (output_tokens/1e6 * 1.25)
        
        # Total cost for this document (classification + extraction)
        total_cost = classification_cost + citation_cost
        
        extraction = CitationExtraction(
            document_id=doc.document_id,
            model_used=CONFIG['ANTHROPIC_MODEL'],
            total_citations_found=data.get('total_citations_found', 0),
            foreign_citations_count=len(valid_citations),
            domestic_citations_excluded=data.get('domestic_citations_excluded', 0),
            api_tokens_input=classification_tokens.get('input', 0) + input_tokens,
            api_tokens_output=classification_tokens.get('output', 0) + output_tokens,
            api_cost_usd=total_cost,
            extraction_time_seconds=extraction_time,
            extraction_success=True,
            raw_llm_response={
                'classification': classification_data,
                'citation_extraction': data
            }
        )
        session.add(extraction)
        session.flush()  # Generate ID
        
        # Add individual citations
        for i, c in enumerate(valid_citations):
            # Calculate text indices for highlighting
            start_idx, end_idx = find_citation_indices(doc.raw_text, c.get('citation_string_raw'))
            
            cit_record = Citation(
                extraction_id=extraction.extraction_id,
                cited_case_name=c.get('cited_case_name', 'Unknown'),
                cited_court=c.get('cited_court'),
                cited_jurisdiction=c.get('cited_jurisdiction'),
                cited_country=c.get('cited_country'),
                cited_year=c.get('cited_year'),
                citation_context=c.get('citation_context'),
                citation_type=c.get('citation_type'),
                citation_string_raw=c.get('citation_string_raw'),
                confidence_score=c.get('confidence_score'),
                position_in_document=i+1,
                start_char_index=start_idx,
                end_char_index=end_idx
            )
            session.add(cit_record)
            
        session.commit()
        
        # Update statistics
        stats['citation_extraction_cost'] += citation_cost
        stats['citations'] += len(valid_citations)
        return True

    except Exception as e:
        session.rollback()
        logging.error(f"Error processing {doc.document_id}: {e}")
        stats['errors'] += 1
        return False

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    logging.info("="*70)
    logging.info("CITATION EXTRACTION WITH DOCUMENT CLASSIFICATION (PHASE 2)")
    logging.info("Climate Litigation Database Analysis")
    logging.info("="*70)
    logging.info(f"Model: {CONFIG['ANTHROPIC_MODEL']}")
    logging.info(f"Max Context: {CONFIG['MAX_TEXT_CONTEXT']} chars")
    logging.info(f"Min Confidence: {CONFIG['MIN_CONFIDENCE']}")
    logging.info("="*70)

    # Connect to database
    engine = create_engine(URL.create(**DB_CONFIG))
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Fetch documents with extracted text (Inner Join)
        query = session.query(
            Document.document_id, 
            Document.metadata_json,
            ExtractedText.raw_text,
            Case.court_name, 
            Case.country
        ).join(ExtractedText).join(Case).filter(ExtractedText.raw_text != None)

        # Exclude already processed documents
        processed_ids = session.query(CitationExtraction.document_id).all()
        processed_ids = [id[0] for id in processed_ids]
        if processed_ids:
            query = query.filter(~Document.document_id.in_(processed_ids))

        documents = query.all()

        # Apply test mode limit if enabled
        if TEST_CONFIG['ENABLED']:
            limit = TEST_CONFIG['LIMIT']
            logging.info(f"⚠️  TEST MODE: Processing first {limit} documents.")
            documents = documents[:limit]

        total_docs = len(documents)
        logging.info(f"Found {total_docs} documents to process.\n")

        # Initialize statistics
        stats = {
            'classification_cost': 0.0,
            'citation_extraction_cost': 0.0,
            'citations': 0,
            'errors': 0,
            'decisions': 0,
            'non_decisions': 0
        }
        
        # Process all documents
        for doc in tqdm(documents, desc="Processing Documents"):
            process_single_document(doc, session, stats)

        # Print summary
        total_cost = stats['classification_cost'] + stats['citation_extraction_cost']
        
        logging.info("\n" + "="*70)
        logging.info("EXTRACTION SUMMARY")
        logging.info("="*70)
        logging.info(f"Total Documents Processed:     {total_docs}")
        logging.info(f"  ├─ Judicial Decisions:       {stats['decisions']}")
        logging.info(f"  ├─ Non-Decisions (Flagged):  {stats['non_decisions']}")
        logging.info(f"  └─ Errors:                   {stats['errors']}")
        logging.info(f"\nCitations Found:               {stats['citations']}")
        logging.info(f"\nCost Breakdown:")
        logging.info(f"  ├─ Classification:           ${stats['classification_cost']:.4f}")
        logging.info(f"  ├─ Citation Extraction:      ${stats['citation_extraction_cost']:.4f}")
        logging.info(f"  └─ Total Estimated Cost:     ${total_cost:.4f}")
        logging.info("="*70)
        
        # Query to show how to find non-decisions later
        logging.info("\n💡 To query non-decisions later:")
        logging.info("   SELECT * FROM citation_extractions")
        logging.info("   WHERE extraction_error = 'NOT_A_DECISION';")
        logging.info("="*70)

    finally:
        session.close()

if __name__ == "__main__":
    main()
