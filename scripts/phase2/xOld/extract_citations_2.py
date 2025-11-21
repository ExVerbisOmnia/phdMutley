#!/usr/bin/env python3
"""
Citation Extraction Script (Phase 2)
====================================
Extracts FOREIGN and INTERNATIONAL citations from judicial decisions using Claude API.
Populates the database with structured citation data and text locations.

📁 Run from: /home/gusrodgs/Gus/cienciaDeDados/phdMutley
Command: python scripts/phase2/extract_citations_phase2.py

Features:
- "Smart" Prompting: Negative constraints for domestic courts & Idem/Ibid resolution.
- Exact Text Location: Calculates start/end indices for highlighting.
- Cost Tracking: logs token usage and estimated cost per document.
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

# Import database models (Now including Citation models from the merged init script)
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
# HELPER FUNCTIONS
# ============================================================================

def find_citation_indices(full_text, citation_string_raw):
    """
    Locates the start and end character indices of the citation in the text.
    Used for highlighting/UI purposes.
    """
    if not citation_string_raw or not full_text:
        return None, None
        
    try:
        # Simple first-match search. 
        # Improvement: Could use regex or fuzzy search if exact match fails.
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
    Process one document: Call API, parse JSON, save to DB.
    """
    try:
        # 1. Prepare Context
        source_court = doc.court_name or "Unknown Court"
        source_country = doc.country or "Unknown Country"
        source_jurisdiction = doc.metadata_json.get('Jurisdictions', f"{source_country} courts") if doc.metadata_json else f"{source_country} courts"
        
        prompt = generate_citation_extraction_prompt(
            doc.raw_text, source_court, source_country, source_jurisdiction
        )
        
        # 2. Call API with Retry
        response_text = None
        start_time = time.time()
        
        for attempt in range(3):
            try:
                message = client.messages.create(
                    model=CONFIG['ANTHROPIC_MODEL'],
                    max_tokens=CONFIG['MAX_LLM_TOKENS'],
                    temperature=0.0, # Deterministic
                    messages=[{"role": "user", "content": prompt}]
                )
                response_text = message.content[0].text
                break
            except Exception as e:
                if attempt == 2:
                    raise e
                time.sleep(2)

        extraction_time = time.time() - start_time
        
        # 3. Parse JSON
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
                extraction_error="JSON Parse Failed",
                raw_llm_response=response_text, # Save raw text for debugging
                model_used=CONFIG['ANTHROPIC_MODEL']
            )
            session.add(extraction)
            session.commit()
            return False

        # 4. Filter & Save to DB
        foreign_citations = data.get('foreign_citations', [])
        valid_citations = [c for c in foreign_citations if c.get('confidence_score', 0) >= CONFIG['MIN_CONFIDENCE']]
        
        # Calculate Cost (Estimate)
        input_tokens = message.usage.input_tokens
        output_tokens = message.usage.output_tokens
        cost = (input_tokens/1e6 * 0.25) + (output_tokens/1e6 * 1.25)
        
        extraction = CitationExtraction(
            document_id=doc.document_id,
            model_used=CONFIG['ANTHROPIC_MODEL'],
            total_citations_found=data.get('total_citations_found', 0),
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
        session.flush() # Generate ID
        
        # Add Citations
        for i, c in enumerate(valid_citations):
            # NEW: Calculate text indices
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
                # NEW Fields
                start_char_index=start_idx,
                end_char_index=end_idx
            )
            session.add(cit_record)
            
        session.commit()
        
        # Update Stats
        stats['cost'] += cost
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
    logging.info("CITATION EXTRACTION (PHASE 2) - CLIMATE LITIGATION DATABASE")
    logging.info(f"Model: {CONFIG['ANTHROPIC_MODEL']} | Max Context: {CONFIG['MAX_TEXT_CONTEXT']} chars")
    logging.info("="*70)

    # Connect DB
    engine = create_engine(URL.create(**DB_CONFIG))
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # 1. Fetch Documents (Inner Join to get those with extracted text)
        query = session.query(
            Document.document_id, 
            Document.metadata_json,
            ExtractedText.raw_text,
            Case.court_name, 
            Case.country
        ).join(ExtractedText).join(Case).filter(ExtractedText.raw_text != None)

        # 2. Exclude Already Processed
        processed_ids = session.query(CitationExtraction.document_id).all()
        processed_ids = [id[0] for id in processed_ids]
        if processed_ids:
            query = query.filter(~Document.document_id.in_(processed_ids))

        documents = query.all()

        if TEST_CONFIG['ENABLED']:
            limit = TEST_CONFIG['LIMIT']
            logging.info(f"⚠️  TEST MODE: Processing first {limit} documents.")
            documents = documents[:limit]

        logging.info(f"Found {len(documents)} documents to process.")

        # 3. Process Loop
        stats = {'cost': 0.0, 'citations': 0, 'errors': 0}
        
        for doc in tqdm(documents, desc="Extracting Citations"):
            process_single_document(doc, session, stats)

        logging.info("\n" + "="*70)
        logging.info("EXTRACTION SUMMARY")
        logging.info("="*70)
        logging.info(f"Documents Processed: {len(documents)}")
        logging.info(f"Citations Found:     {stats['citations']}")
        logging.info(f"Total Est. Cost:     ${stats['cost']:.4f}")
        logging.info(f"Errors:              {stats['errors']}")
        logging.info("="*70)

    finally:
        session.close()

if __name__ == "__main__":
    main()