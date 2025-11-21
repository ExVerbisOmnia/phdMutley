#!/usr/bin/env python3
"""
Citation Extraction Script (Phase 2) - Version 3.4 Trial Batch Support
======================================================================
VERSION 3.4 - TRIAL BATCH FILTERING
- Sonnet 4.5 for judicial decision classification
- Haiku 4.5 for citation extraction
- Trial batch filtering support
- Dynamic Context Injection (Binding Courts)
- 3-Category Classification (Foreign / International / Foreign International)

Version 3.4 Changes:
- Added trial batch filtering
- Only processes documents flagged in Excel "Trial batch" column
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
    Uses Claude Sonnet API to determine if the document is a JUDICIAL DECISION.
    Enhanced prompt structure following best practices.
    """
    doc_type = metadata.get('Document Type', 'Unknown')
    doc_title = metadata.get('Document Title', 'Unknown')
    classification_text_limit = CONFIG['CLASSIFICATION_TEXT_LIMIT']
    
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
Return ONLY valid JSON with no additional text:
{{
  "is_judicial_decision": true,
  "reasoning": "Detailed explanation of why this is or is not a judicial decision, citing specific textual evidence",
  "confidence": 0.95,
  "document_type_detected": "Supreme Court Judgment",
  "key_indicators_found": ["legal reasoning present", "issued by court", "binding determination"]
}}
</output_format>

<document_excerpt>
{document_text[:classification_text_limit]}
</document_excerpt>

Remember: Respond ONLY with the JSON object. Do not include any explanatory text before or after the JSON."""

    try:
        message = client.messages.create(
            model=CONFIG['CLASSIFICATION_MODEL'],
            max_tokens=2000,
            temperature=0.0,
            messages=[{"role": "user", "content": prompt}]
        )
        data = extract_json_from_text(message.content[0].text)
        
        if not data:
            logging.warning("Failed to parse classification JSON, assuming decision")
            return True, {"error": "JSON_PARSE_FAILED", "assumed_decision": True}
            
        return data.get('is_judicial_decision', False), data
        
    except Exception as e:
        logging.error(f"Classification Error: {e}")
        return True, {"error": str(e), "assumed_decision": True}


def generate_citation_extraction_prompt(document_text, source_court, source_country, source_jurisdiction, binding_courts_str):
    """
    Generates the Haiku extraction prompt with DYNAMIC CONTEXT INJECTION and 3-CATEGORY LABELING.
    Uses XML structure as per best practices.
    No truncation - processes full text.
    """
    
    prompt = f"""You are a legal citation extraction specialist.

<task>
Extract citations to FOREIGN and INTERNATIONAL courts. 
Classify them strictly into one of 3 categories: 'Foreign Citation', 'International Citation', or 'Foreign International Citation'.
</task>

<source_context>
<country>{source_country}</country>
<court>{source_court}</court>
<jurisdiction>{source_jurisdiction}</jurisdiction>
<binding_courts>
{binding_courts_str}
</binding_courts>
</source_context>

<category_definitions>
<foreign_citation>
Citations to courts from DIFFERENT countries (excluding binding courts and international tribunals).
Example: A US court citing a French court decision.
</foreign_citation>

<international_citation>
Citations to international courts or tribunals that have jurisdiction over the source country.
Example: A German court citing the European Court of Justice.
</international_citation>

<foreign_international_citation>
Citations to international courts or tribunals that DO NOT have jurisdiction over the source country.
Example: A Brazilian court citing the European Court of Human Rights.
</foreign_international_citation>
</category_definitions>

<exclusion_rules>
DO NOT extract:
- Domestic citations (courts within the same country/binding jurisdiction)
- Citations to statutes, regulations, or non-judicial sources
- Self-citations (same court citing itself)
</exclusion_rules>

<extraction_instructions>
1. Scan the full document text carefully
2. For each citation found, determine its category using the definitions above
3. Extract complete case name, court, jurisdiction, country, and year
4. Include the exact citation string as it appears in the text
5. Assign a confidence score (0.0-1.0) based on citation clarity
</extraction_instructions>

<output_format>
Return ONLY valid JSON with no additional text:
{{
  "foreign_citations": [
    {{
      "cited_case_name": "Case Name",
      "cited_court": "Court Name",
      "cited_jurisdiction": "Jurisdiction",
      "cited_country": "Country",
      "cited_year": 2020,
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
    """
    Process a single document for citation extraction.
    """
    try:
        # Note: metadata_json is the Python attribute that maps to DB column 'metadata'
        metadata = doc.metadata_json or {}

        # 1. Classification using SONNET
        logging.info(f"Classifying Document {doc.document_id} with Sonnet...")
        is_decision, class_data = check_if_judicial_decision(doc.raw_text, metadata)
        
        if not is_decision:
            logging.info(f"❌ Non-Decision flagged: {class_data.get('reasoning')}")
            extraction = CitationExtraction(
                document_id=doc.document_id,
                extraction_success=False,
                extraction_error="NOT_A_DECISION",
                raw_llm_response=class_data,
                model_used=f"{CONFIG['CLASSIFICATION_MODEL']} (classification)"
            )
            session.add(extraction)
            session.commit()
            stats['non_decisions'] += 1
            return True

        # 2. Citation Extraction using HAIKU
        logging.info(f"Extracting citations from Document {doc.document_id} with Haiku...")
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
                    logging.error(f"Extraction failed after 3 attempts: {e}")
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
        cost = (input_tokens/1e6 * 0.25) + (output_tokens/1e6 * 1.25)

        extraction = CitationExtraction(
            document_id=doc.document_id,
            model_used=f"{CONFIG['ANTHROPIC_MODEL']} (extraction)",
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
                document_id=doc.document_id,
                cited_case_name=c.get('cited_case_name', 'Unknown'),
                cited_court=c.get('cited_court'),
                cited_jurisdiction=c.get('cited_jurisdiction'),
                cited_country=c.get('cited_country'),
                cited_year=c.get('cited_year'),
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
        stats['citations'] += len(valid_citations)
        return True

    except Exception as e:
        session.rollback()
        logging.error(f"Error processing document {doc.document_id}: {e}")
        stats['errors'] += 1
        return False

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    logging.info("="*70)
    logging.info("CITATION EXTRACTION (PHASE 2) - VERSION 3.4 TRIAL BATCH")
    logging.info(f"Classification Model: {CONFIG['CLASSIFICATION_MODEL']} (Sonnet)")
    logging.info(f"Extraction Model: {CONFIG['ANTHROPIC_MODEL']} (Haiku - No Truncation)")
    logging.info("="*70)

    # Get trial batch filter
    trial_batch_uuids = get_trial_batch_document_uuids()

    engine = create_engine(URL.create(**DB_CONFIG))
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Query with Case ID
        # Note: metadata_json is the Python attribute that maps to DB column 'metadata'
        query = session.query(
            Document.document_id,
            Document.metadata_json,
            ExtractedText.raw_text,
            Case.court_name,
            Case.country,
            Case.case_id
        ).join(ExtractedText).join(Case).filter(ExtractedText.raw_text != None)

        # Filter by trial batch if enabled
        if trial_batch_uuids is not None:
            query = query.filter(Document.document_id.in_(trial_batch_uuids))
            logging.info(f"Applied trial batch filter: {len(trial_batch_uuids)} documents")

        # Exclude already processed
        processed_ids = [id[0] for id in session.query(CitationExtraction.document_id).all()]
        if processed_ids:
            query = query.filter(~Document.document_id.in_(processed_ids))

        documents = query.all()

        logging.info(f"Found {len(documents)} documents to process.")
        
        if len(documents) == 0:
            logging.warning("⚠️  No documents to process!")
            return
        
        stats = {'citations': 0, 'non_decisions': 0, 'errors': 0}
        for doc in tqdm(documents, desc="Processing"):
            process_single_document(doc, session, stats)

        logging.info("="*70)
        logging.info("PROCESSING COMPLETE")
        logging.info("="*70)
        logging.info(f"Total citations extracted: {stats['citations']}")
        logging.info(f"Non-decisions flagged: {stats['non_decisions']}")
        logging.info(f"Errors encountered: {stats['errors']}")
        
        if TRIAL_BATCH_CONFIG['ENABLED']:
            logging.info(f"\n✓ Trial batch mode was ENABLED")
            logging.info(f"  Only processed documents from trial batch")
        
        logging.info("="*70)

    finally:
        session.close()

if __name__ == "__main__":
    main()
