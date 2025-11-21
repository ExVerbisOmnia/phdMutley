#!/usr/bin/env python3
"""
Citation Extraction Script (Phase 2) - Dynamic Context & 3-Category Classification
==================================================================================
VERSION 3.1 - MERGED FEATURES
- Haiku 4.5 Model (No truncation)
- Dynamic Context Injection (Binding Courts)
- 3-Category Classification (Foreign / International / Foreign International)
- Robust JSON & Rate Limiting
"""

import sys
import os
import time
import json
import logging
import re
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
# Import get_binding_courts from the updated config
from config import CONFIG, DB_CONFIG, LOGS_DIR, TEST_CONFIG, get_binding_courts

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
logging.getLogger('httpx').setLevel(logging.WARNING)

# ============================================================================
# API CLIENT SETUP
# ============================================================================

if not CONFIG['ANTHROPIC_API_KEY']:
    logging.error("CRITICAL: ANTHROPIC_API_KEY not found.")
    sys.exit(1)

client = anthropic.Anthropic(api_key=CONFIG['ANTHROPIC_API_KEY'])

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def extract_json_from_text(text):
    """Robust regex-based JSON extraction."""
    try:
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            return json.loads(match.group(0))
        return json.loads(text)
    except Exception:
        return None

def find_citation_indices(full_text, citation_string_raw):
    """Locates citation indices."""
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
    """Extracts full paragraph."""
    if not text or start_index is None or end_index is None:
        return None
    
    # Find start (previous double newline)
    paragraph_start = text.rfind('\n\n', 0, start_index)
    paragraph_start = 0 if paragraph_start == -1 else paragraph_start + 2

    # Find end (next double newline)
    paragraph_end = text.find('\n\n', end_index)
    paragraph_end = len(text) if paragraph_end == -1 else paragraph_end

    return text[paragraph_start:paragraph_end].strip()

def check_if_judicial_decision(document_text, metadata):
    """
    Uses Claude API to determine if the document is a JUDICIAL DECISION.
    Uses truncated text (3000 chars) for efficiency.
    """
    doc_type = metadata.get('Document Type', 'Unknown')
    doc_title = metadata.get('Document Title', 'Unknown')
    classification_text_limit = CONFIG['CLASSIFICATION_TEXT_LIMIT']
    
    prompt = f"""You are a legal document classifier.

<task>
Determine if this document is a JUDICIAL DECISION (ruling/judgment/order by a court).
</task>

<metadata>
Type: {doc_type}
Title: {doc_title}
</metadata>

<criteria>
YES if: Final/interim ruling, legal analysis, authored by judge.
NO if: Motion, complaint, brief, administrative notice, press release, settlement.
</criteria>

<output_format>
JSON ONLY:
{{
  "is_judicial_decision": true/false,
  "reasoning": "string",
  "confidence": 0.95
}}
</output_format>

<text_excerpt>
{document_text[:classification_text_limit]}
</text_excerpt>
"""
    try:
        message = client.messages.create(
            model=CONFIG['ANTHROPIC_MODEL'],
            max_tokens=1000,
            temperature=0.0,
            messages=[{"role": "user", "content": prompt}]
        )
        data = extract_json_from_text(message.content[0].text)
        return data.get('is_judicial_decision', False), data
    except Exception as e:
        logging.error(f"Classification Error: {e}")
        return True, {"error": str(e), "assumed_decision": True}


def generate_citation_extraction_prompt(document_text, source_court, source_country, source_jurisdiction, binding_courts_str):
    """
    Generates the prompt with DYNAMIC CONTEXT INJECTION and 3-CATEGORY LABELING.
    Uses XML structure as per best practices.
    """
    # No truncation logic here, as requested by user (processed full text)
    
    prompt = f"""You are a legal citation extraction specialist.

<task>
Extract citations to FOREIGN and INTERNATIONAL courts. 
Classify them strictly into one of 3 categories: 'Foreign Citation', 'International Citation', or 'Foreign International Citation'.
</task>

<source_context>
<country>{source_country}</country>
<court>{source_court}</court>
<jurisdiction>{source_jurisdiction}</jurisdiction>
<binding_international_courts>
{binding_courts_str}
</binding_international_courts>
</source_context>

<definitions>
Use these definitions for the 'citation_type' field:

1. **Foreign Citation**: 
   Citing a national court of a DIFFERENT country (e.g., Brazil citing USA Supreme Court).

2. **International Citation**: 
   Citing an international tribunal that has JURISDICTION over the source country.
   *CHECK THE <binding_international_courts> LIST ABOVE.* If the cited court is listed there (or is the ICJ), use this category.

3. **Foreign International Citation**: 
   Citing an international tribunal that does NOT have jurisdiction over the source country.
   (e.g., A South American court citing the European Court of Human Rights).
</definitions>

<critical_exclusions>
1. IGNORE all citations to courts within {source_country} (Domestic).
2. IGNORE citations to the document's own court.
</critical_exclusions>

<special_handling>
- **Idem/Ibid**: Resolve these to the immediately preceding extracted citation. If it refers to a domestic case, ignore it.
</special_handling>

<output_format>
Return ONLY a valid JSON object.
{{
  "foreign_citations": [
    {{
      "cited_case_name": "Case Name",
      "cited_court": "Court Name",
      "cited_country": "Country",
      "citation_type": "Foreign Citation",
      "citation_string_raw": "exact text snippet",
      "confidence_score": 0.95
    }}
  ],
  "domestic_citations_excluded": 0,
  "total_citations_found": 0
}}
</output_format>

<document_full_text>
{document_text}
</document_full_text>
"""
    return prompt

# ============================================================================
# PROCESSING LOGIC
# ============================================================================

def process_single_document(doc, session, stats):
    try:
        metadata = doc.metadata_json or {}
        
        # 1. Classification
        logging.info(f"Classifying Document {doc.document_id}...")
        is_decision, class_data = check_if_judicial_decision(doc.raw_text, metadata)
        
        if not is_decision:
            logging.info(f"❌ Non-Decision flagged: {class_data.get('reasoning')}")
            extraction = CitationExtraction(
                document_id=doc.document_id,
                extraction_success=False,
                extraction_error="NOT_A_DECISION",
                raw_llm_response=class_data,
                model_used=CONFIG['ANTHROPIC_MODEL']
            )
            session.add(extraction)
            session.commit()
            stats['non_decisions'] += 1
            return True

        # 2. Citation Extraction
        source_court = doc.court_name or "Unknown Court"
        source_country = doc.country or "Unknown Country"
        source_jurisdiction = metadata.get('Jurisdictions', f"{source_country} courts")
        
        # DYNAMIC INJECTION
        binding_courts = get_binding_courts(source_country)
        
        prompt = generate_citation_extraction_prompt(
            doc.raw_text, source_court, source_country, source_jurisdiction, binding_courts
        )
        
        # Call API (Rate Limit Safe)
        response_text = None
        start_time = time.time()
        
        for attempt in range(3):
            try:
                time.sleep(1.5) 
                message = client.messages.create(
                    model=CONFIG['ANTHROPIC_MODEL'],
                    max_tokens=CONFIG['MODEL_MAX_OUTPUT'],
                    temperature=0.0, 
                    messages=[{"role": "user", "content": prompt}]
                )
                response_text = message.content[0].text
                break
            except Exception as e:
                if attempt == 2:
                    stats['errors'] += 1
                    return False
                time.sleep(5 * (attempt + 1))

        extraction_time = time.time() - start_time
        
        # Parse
        data = extract_json_from_text(response_text)
        if not data:
            logging.error("JSON Parse Failed")
            return False

        # Save
        citations_list = data.get('foreign_citations', [])
        valid_citations = [c for c in citations_list if c.get('confidence_score', 0) >= CONFIG['MIN_CONFIDENCE']]
        
        input_tokens = message.usage.input_tokens
        output_tokens = message.usage.output_tokens
        cost = (input_tokens/1e6 * 0.25) + (output_tokens/1e6 * 1.25) # Haiku Pricing (approx)

        extraction = CitationExtraction(
            document_id=doc.document_id,
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
                citation_type=c.get('citation_type'), # Now contains one of the 3 categories
                citation_string_raw=c.get('citation_string_raw'),
                citation_paragraph=paragraph,
                confidence_score=c.get('confidence_score'),
                position_in_document=i+1,
                start_char_index=start_idx,
                end_char_index=end_idx
            )
            session.add(cit_record)
            
        session.commit()
        stats['citations'] += len(valid_citations)
        return True

    except Exception as e:
        session.rollback()
        logging.error(f"Error: {e}")
        stats['errors'] += 1
        return False

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    logging.info("="*70)
    logging.info("CITATION EXTRACTION (PHASE 2) - DYNAMIC CONTEXT & 3-CATEGORY")
    logging.info(f"Model: {CONFIG['ANTHROPIC_MODEL']} (No Truncation)")
    logging.info("="*70)

    engine = create_engine(URL.create(**DB_CONFIG))
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Query with Case ID
        query = session.query(
            Document.document_id, 
            Document.metadata_json,
            ExtractedText.raw_text,
            Case.court_name, 
            Case.country,
            Case.case_id
        ).join(ExtractedText).join(Case).filter(ExtractedText.raw_text != None)

        processed_ids = [id[0] for id in session.query(CitationExtraction.document_id).all()]
        if processed_ids:
            query = query.filter(~Document.document_id.in_(processed_ids))

        documents = query.all()

        if TEST_CONFIG['ENABLED']:
            limit = TEST_CONFIG['LIMIT']
            logging.info(f"⚠️  TEST MODE: Processing first {limit} documents.")
            documents = documents[:limit]

        logging.info(f"Found {len(documents)} documents.")
        
        stats = {'citations': 0, 'non_decisions': 0, 'errors': 0}
        for doc in tqdm(documents, desc="Extracting"):
            process_single_document(doc, session, stats)

    finally:
        session.close()

if __name__ == "__main__":
    main()