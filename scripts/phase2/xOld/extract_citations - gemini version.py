#!/usr/bin/env python3
"""
Citation Extraction Script (Phase 2) - Robust JSON & Rate Limit Fix
===================================================================
Extracts FOREIGN and INTERNATIONAL citations from judicial decisions using Claude API.
Populates the database with structured citation data, text locations, and full paragraphs.

Features:
- Rate Limiting: Sleeps 1.5s between requests to avoid API bans.
- Regex JSON Parsing: Ignores conversational filler from Claude.
- Retry Logic: Handles API timeouts gracefully.

📁 Run from: /home/gusrodgs/Gus/cienciaDeDados/phdMutley
Command: python scripts/phase2/extract_citations.py
"""

import sys
import os
import time
import json
import logging
import re  # Added for regex JSON extraction
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
from init_database import Case, Document, ExtractedText, Citation, CitationExtraction

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

def extract_json_from_text(text):
    """
    Robustly extracts JSON object from a string using Regex.
    Finds the first '{' and the last '}' and attempts to parse everything between.
    """
    try:
        # Regex to find the outermost JSON object
        # matches '{' followed by any character (including newlines) until the last '}'
        match = re.search(r'\{[\s\S]*\}', text)
        
        if match:
            json_str = match.group(0)
            return json.loads(json_str)
        
        # Fallback: Try standard load if no braces found (unlikely for valid JSON)
        return json.loads(text)
        
    except Exception:
        return None

def find_citation_indices(full_text, citation_string_raw):
    """Locates start/end indices of citation."""
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
    """Extracts the full paragraph containing the citation."""
    if not text or start_index is None or end_index is None:
        return None
    
    paragraph_start = text.rfind('\n\n', 0, start_index)
    paragraph_start = 0 if paragraph_start == -1 else paragraph_start + 2

    paragraph_end = text.find('\n\n', end_index)
    paragraph_end = len(text) if paragraph_end == -1 else paragraph_end

    return text[paragraph_start:paragraph_end].strip()

def generate_citation_extraction_prompt(document_text, source_court, source_country, source_jurisdiction):
    """Generate structured prompt."""
    # Truncate text if too long
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
- If you encounter 'Idem', 'Ibid', or 'supra', resolve it to the immediate previously cited foreign case.
- If it refers to a domestic case, ignore it.

REQUIRED OUTPUT JSON FORMAT:
Return ONLY a valid JSON object. Do not add preambles or markdown formatting.
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
                # ---------------------------------------------------------
                # RATE LIMIT FIX: Force a 1.5s delay between every request
                # This keeps you around 40 requests/min (safe for Tier 1)
                # ---------------------------------------------------------
                time.sleep(1.5) 
                
                message = client.messages.create(
                    model=CONFIG['ANTHROPIC_MODEL'],
                    max_tokens=CONFIG['MAX_LLM_TOKENS'],
                    temperature=0.0, 
                    messages=[{"role": "user", "content": prompt}]
                )
                response_text = message.content[0].text
                break
            except Exception as e:
                logging.warning(f"API Error (Attempt {attempt+1}): {e}")
                if attempt == 2:
                    # Don't crash script, just log error and skip doc
                    logging.error(f"Skipping document {doc.document_id} after 3 failed API attempts.")
                    stats['errors'] += 1
                    return False
                
                # Exponential Backoff: If we hit a limit, wait 5s, then 10s...
                wait_time = 5 * (attempt + 1)
                logging.info(f"Waiting {wait_time}s before retry...")
                time.sleep(wait_time)

        extraction_time = time.time() - start_time
        
        # 3. Parse JSON (Using Robust Function)
        data = extract_json_from_text(response_text)
        
        if data is None:
            logging.error(f"JSON Parse Error for {doc.document_id}")
            logging.error(f"Raw Response Snippet: {response_text[:100]}...") # Log what actually came back
            
            extraction = CitationExtraction(
                document_id=doc.document_id,
                extraction_success=False,
                extraction_error="JSON Parse Failed",
                raw_llm_response=response_text,
                model_used=CONFIG['ANTHROPIC_MODEL']
            )
            session.add(extraction)
            session.commit()
            stats['errors'] += 1
            return False

        # 4. Filter & Save to DB
        foreign_citations = data.get('foreign_citations', [])
        valid_citations = [c for c in foreign_citations if c.get('confidence_score', 0) >= CONFIG['MIN_CONFIDENCE']]
        
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
        session.flush()
        
        for i, c in enumerate(valid_citations):
            start_idx, end_idx = find_citation_indices(doc.raw_text, c.get('citation_string_raw'))
            paragraph = extract_citation_paragraph(doc.raw_text, start_idx, end_idx)
            
            cit_record = Citation(
                extraction_id=extraction.extraction_id,
                case_id=doc.case_id,
                cited_case_name=c.get('cited_case_name', 'Unknown'),
                cited_court=c.get('cited_court'),
                cited_jurisdiction=c.get('cited_jurisdiction'),
                cited_country=c.get('cited_country'),
                cited_year=c.get('cited_year'),
                citation_context=c.get('citation_context'),
                citation_type=c.get('citation_type'),
                citation_string_raw=c.get('citation_string_raw'),
                citation_paragraph=paragraph,
                confidence_score=c.get('confidence_score'),
                position_in_document=i+1,
                start_char_index=start_idx,
                end_char_index=end_idx
            )
            session.add(cit_record)
            
        session.commit()
        
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

    engine = create_engine(URL.create(**DB_CONFIG))
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        query = session.query(
            Document.document_id, 
            Document.metadata_json,
            ExtractedText.raw_text,
            Case.court_name, 
            Case.country,
            Case.case_id
        ).join(ExtractedText).join(Case).filter(ExtractedText.raw_text != None)

        # Exclude already processed
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