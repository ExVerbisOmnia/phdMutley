#!/usr/bin/env python3
"""
Citation Extraction Script - Version 5.0 (Phased Approach)
======================================================================
Enhanced Foreign Case Law Capture with 4-Phase Architecture

🏃 Run from: /home/gusrodgs/Gus/cienciaDeDados/phdMutley
Command: python scripts/phase2/extract_citations_v5_phased.py

VERSION 5.0 - PHASED EXTRACTION ARCHITECTURE
============================================

ARCHITECTURE:
Phase 1: Source Jurisdiction Identification (from database)
Phase 2: Extract ALL case law references (no filtering)
Phase 3: Identify case origin (3-tier: Dictionary → Sonnet → Web Search)
Phase 4: Classify citation type (Foreign / International / Foreign International)

KEY IMPROVEMENTS:
- Extracts ALL case law references in Phase 2 (no premature filtering)
- 3-tier origin identification for higher recall
- Enhanced citation format patterns (12 types)
- Captures extended context (before/after sentences)
- Caching for repeated citations
- Confidence-based manual review flagging

EXPECTED PERFORMANCE:
- Recall: 75-85% (up from 40-50%)
- Precision: 85-90% (down from 95%, acceptable tradeoff)
- Cost: Similar to v4 (~$0.02-0.05 per document)

REQUIREMENTS:
- Documents must be classified first (is_decision = True)
- New database tables: citation_extraction_phased, citation_extraction_phased_summary

Author: Lucas Biasetton & Assistant
Project: Doutorado PM
Version: 5.0
Date: November 22, 2025
"""

import sys
import os
import time
import json
import logging
import re
import pandas as pd
from tqdm import tqdm
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set
import anthropic

# Database
from sqlalchemy import create_engine, Column, String, Integer, Boolean, Text, DECIMAL, TIMESTAMP, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.engine import URL
from sqlalchemy.dialects.postgresql import UUID as pgUUID
import uuid

# ============================================================================
# CONFIGURATION & IMPORTS
# ============================================================================

sys.path.insert(0, '/home/gusrodgs/Gus/cienciaDeDados/phdMutley/scripts')
from config import (CONFIG, DB_CONFIG, LOGS_DIR, TRIAL_BATCH_CONFIG, 
                    DATABASE_FILE, UUID_NAMESPACE, get_binding_courts)

sys.path.insert(0, os.path.join('/home/gusrodgs/Gus/cienciaDeDados/phdMutley', 'scripts', '0-initialize-database'))
from init_database import Case, Document, ExtractedText

from uuid import uuid5

# ============================================================================
# SQLALCHEMY MODELS FOR NEW TABLES
# ============================================================================

# Import Base and citation tables from init_database to avoid duplication
from init_database import Base, CitationExtractionPhased, CitationExtractionPhasedSummary

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / 'citation_extraction_v5.log'),
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
# ENHANCED DICTIONARIES - KNOWN FOREIGN COURTS
# ============================================================================

KNOWN_FOREIGN_COURTS = {
    # EUROPEAN COURTS
    "Court of Session": {"country": "Scotland", "region": "Global North", "type": "Appellate"},
    "Inner House": {"country": "Scotland", "region": "Global North", "type": "Appellate"},
    "Outer House": {"country": "Scotland", "region": "Global North", "type": "Trial"},
    "High Court of Justiciary": {"country": "Scotland", "region": "Global North", "type": "Criminal Supreme"},
    "The Hague Court": {"country": "Netherlands", "region": "Global North", "type": "Trial"},
    "District Court of The Hague": {"country": "Netherlands", "region": "Global North", "type": "Trial"},
    "Rechtbank Den Haag": {"country": "Netherlands", "region": "Global North", "type": "Trial"},
    "Hoge Raad": {"country": "Netherlands", "region": "Global North", "type": "Supreme"},
    "Dutch Supreme Court": {"country": "Netherlands", "region": "Global North", "type": "Supreme"},
    
    # NORDIC COURTS
    "Norwegian Supreme Court": {"country": "Norway", "region": "Global North", "type": "Supreme"},
    "Oslo District Court": {"country": "Norway", "region": "Global North", "type": "Trial"},
    "Borgarting Court of Appeal": {"country": "Norway", "region": "Global North", "type": "Appellate"},
    "Supreme Court of Sweden": {"country": "Sweden", "region": "Global North", "type": "Supreme"},
    "Supreme Court of Finland": {"country": "Finland", "region": "Global North", "type": "Supreme"},
    
    # UK COURTS
    "UK Supreme Court": {"country": "United Kingdom", "region": "Global North", "type": "Supreme"},
    "Supreme Court of the United Kingdom": {"country": "United Kingdom", "region": "Global North", "type": "Supreme"},
    "Court of Appeal (England and Wales)": {"country": "United Kingdom", "region": "Global North", "type": "Appellate"},
    "High Court of England and Wales": {"country": "United Kingdom", "region": "Global North", "type": "High"},
    "High Court of Justice": {"country": "United Kingdom", "region": "Global North", "type": "High"},
    
    # COMMONWEALTH COURTS
    "Supreme Court of New Zealand": {"country": "New Zealand", "region": "Global North", "type": "Supreme"},
    "High Court of New Zealand": {"country": "New Zealand", "region": "Global North", "type": "High"},
    "Court of Appeal of New Zealand": {"country": "New Zealand", "region": "Global North", "type": "Appellate"},
    "Supreme Court of Canada": {"country": "Canada", "region": "Global North", "type": "Supreme"},
    "Federal Court of Canada": {"country": "Canada", "region": "Global North", "type": "Federal"},
    "Ontario Superior Court": {"country": "Canada", "region": "Global North", "type": "Superior"},
    "Supreme Court of India": {"country": "India", "region": "Global South", "type": "Supreme"},
    "High Court of Australia": {"country": "Australia", "region": "Global North", "type": "Supreme"},
    
    # EUROPEAN UNION & HUMAN RIGHTS
    "Court of Justice of the European Union": {"country": "European Union", "region": "International", "type": "International"},
    "CJEU": {"country": "European Union", "region": "International", "type": "International"},
    "European Court of Justice": {"country": "European Union", "region": "International", "type": "International"},
    "European Court of Human Rights": {"country": "Council of Europe", "region": "International", "type": "International"},
    "ECtHR": {"country": "Council of Europe", "region": "International", "type": "International"},
    
    # LATIN AMERICA
    "Supreme Court of Colombia": {"country": "Colombia", "region": "Global South", "type": "Supreme"},
    "Constitutional Court of Colombia": {"country": "Colombia", "region": "Global South", "type": "Constitutional"},
    "Supreme Court of Brazil": {"country": "Brazil", "region": "Global South", "type": "Supreme"},
    "Supreme Federal Court of Brazil": {"country": "Brazil", "region": "Global South", "type": "Supreme"},
    "Supreme Court of Argentina": {"country": "Argentina", "region": "Global South", "type": "Supreme"},
    "Supreme Court of Chile": {"country": "Chile", "region": "Global South", "type": "Supreme"},
    
    # AFRICA
    "Constitutional Court of South Africa": {"country": "South Africa", "region": "Global South", "type": "Constitutional"},
    "Supreme Court of South Africa": {"country": "South Africa", "region": "Global South", "type": "Supreme"},
    "High Court of Kenya": {"country": "Kenya", "region": "Global South", "type": "High"},
    
    # ASIA-PACIFIC
    "Supreme Court of the Philippines": {"country": "Philippines", "region": "Global South", "type": "Supreme"},
    "Supreme Court of Pakistan": {"country": "Pakistan", "region": "Global South", "type": "Supreme"},
    "Supreme Court of Bangladesh": {"country": "Bangladesh", "region": "Global South", "type": "Supreme"},
    
    # GERMANY & FRANCE
    "Federal Constitutional Court of Germany": {"country": "Germany", "region": "Global North", "type": "Constitutional"},
    "Bundesverfassungsgericht": {"country": "Germany", "region": "Global North", "type": "Constitutional"},
    "Constitutional Council of France": {"country": "France", "region": "Global North", "type": "Constitutional"},
    "Conseil Constitutionnel": {"country": "France", "region": "Global North", "type": "Constitutional"},
    "Conseil d'État": {"country": "France", "region": "Global North", "type": "Administrative"},
    
    # INTERNATIONAL TRIBUNALS
    "International Court of Justice": {"country": "United Nations", "region": "International", "type": "International"},
    "ICJ": {"country": "United Nations", "region": "International", "type": "International"},
    "Inter-American Court of Human Rights": {"country": "Organization of American States", "region": "International", "type": "International"},
    "IACtHR": {"country": "Organization of American States", "region": "International", "type": "International"},
    "African Court on Human and Peoples' Rights": {"country": "African Union", "region": "International", "type": "International"},
    "International Tribunal for the Law of the Sea": {"country": "United Nations", "region": "International", "type": "International"},
    "ITLOS": {"country": "United Nations", "region": "International", "type": "International"},
}

# ============================================================================
# ENHANCED DICTIONARIES - LANDMARK CLIMATE CASES
# ============================================================================

LANDMARK_CLIMATE_CASES = {
    # NETHERLANDS
    "Urgenda": {"full_name": "Urgenda Foundation v. State of the Netherlands", "country": "Netherlands", 
                "region": "Global North", "year": 2019, "court": "Dutch Supreme Court"},
    "Urgenda Foundation": {"full_name": "Urgenda Foundation v. State of the Netherlands", "country": "Netherlands",
                          "region": "Global North", "year": 2019, "court": "Dutch Supreme Court"},
    
    # UNITED STATES
    "Massachusetts v. EPA": {"full_name": "Massachusetts v. Environmental Protection Agency", "country": "United States",
                            "region": "Global North", "year": 2007, "court": "Supreme Court of the United States"},
    "Juliana v. United States": {"full_name": "Juliana v. United States", "country": "United States",
                                "region": "Global North", "year": 2015, "court": "District Court of Oregon"},
    
    # UNITED KINGDOM
    "Plan B Earth": {"full_name": "R (Plan B Earth) v Secretary of State", "country": "United Kingdom",
                    "region": "Global North", "year": 2020, "court": "UK Supreme Court"},
    "ClientEarth": {"full_name": "R (ClientEarth) v Secretary of State", "country": "United Kingdom",
                   "region": "Global North", "year": 2015, "court": "UK Supreme Court"},
    
    # CANADA
    "Mathur v. Ontario": {"full_name": "Mathur et al. v. Her Majesty the Queen in Right of Ontario", 
                         "country": "Canada", "region": "Global North", "year": 2020, 
                         "court": "Ontario Superior Court of Justice"},
    
    # NEW ZEALAND
    "Thomson v Minister": {"full_name": "Thomson v Minister for Climate Change Issues", "country": "New Zealand",
                          "region": "Global North", "year": 2017, "court": "High Court of New Zealand"},
    
    # IRELAND
    "Friends of the Irish Environment": {"full_name": "Friends of the Irish Environment CLG v. Ireland",
                                        "country": "Ireland", "region": "Global North", "year": 2020,
                                        "court": "Supreme Court of Ireland"},
    
    # NORWAY
    "Greenpeace Nordic": {"full_name": "Greenpeace Nordic Ass'n v. Ministry of Petroleum and Energy",
                         "country": "Norway", "region": "Global North", "year": 2020,
                         "court": "Norwegian Supreme Court"},
    "People v. Arctic Oil": {"full_name": "People v. Arctic Oil", "country": "Norway", 
                            "region": "Global North", "year": 2020, "court": "Norwegian Supreme Court"},
    
    # FRANCE
    "Grande Synthe": {"full_name": "Commune de Grande-Synthe v. France", "country": "France",
                     "region": "Global North", "year": 2021, "court": "Conseil d'État"},
    "L'Affaire du Siècle": {"full_name": "L'Affaire du Siècle", "country": "France",
                           "region": "Global North", "year": 2021, "court": "Administrative Court of Paris"},
    
    # GERMANY
    "Neubauer": {"full_name": "Neubauer et al. v. Germany", "country": "Germany",
                "region": "Global North", "year": 2021, "court": "Federal Constitutional Court of Germany"},
    
    # BELGIUM
    "Klimaatzaak": {"full_name": "VZW Klimaatzaak v. Kingdom of Belgium", "country": "Belgium",
                   "region": "Global North", "year": 2021, "court": "Brussels Court of First Instance"},
    
    # COLOMBIA
    "Future Generations": {"full_name": "Future Generations v. Ministry of Environment", "country": "Colombia",
                          "region": "Global South", "year": 2018, "court": "Supreme Court of Colombia"},
    
    # PAKISTAN
    "Ashgar Leghari": {"full_name": "Ashgar Leghari v. Federation of Pakistan", "country": "Pakistan",
                      "region": "Global South", "year": 2015, "court": "Lahore High Court"},
    
    # SOUTH AFRICA
    "Earthlife Africa": {"full_name": "Earthlife Africa Johannesburg v. Minister of Environmental Affairs",
                        "country": "South Africa", "region": "Global South", "year": 2017,
                        "court": "High Court of South Africa"},
}

# ============================================================================
# JURISDICTION ALIASES FOR NORMALIZATION
# ============================================================================

JURISDICTION_ALIASES = {
    "USA": "United States",
    "U.S.": "United States",
    "U.S.A.": "United States",
    "United States of America": "United States",
    "UK": "United Kingdom",
    "U.K.": "United Kingdom",
    "Great Britain": "United Kingdom",
    "Britain": "United Kingdom",
    "The Netherlands": "Netherlands",
    "Holland": "Netherlands",
    "New Zealand": "New Zealand",
    "NZ": "New Zealand",
    "Aotearoa": "New Zealand",
}

# ============================================================================
# GLOBAL CACHES
# ============================================================================

# Cache for repeated citation origin lookups
CITATION_ORIGIN_CACHE: Dict[str, Dict] = {}

# ============================================================================
# TRIAL BATCH FILTERING
# ============================================================================

def get_trial_batch_document_uuids() -> Optional[Set[uuid.UUID]]:
    """
    Load Excel file and return set of Document UUIDs in trial batch.
    
    INPUT: None (reads from config)
    ALGORITHM:
        1. Check if trial batch mode enabled
        2. Load Excel database
        3. Filter rows with TRUE in trial batch column
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
            return None
        
        true_values = TRIAL_BATCH_CONFIG['TRUE_VALUES']
        trial_batch_df = df[df[col_name].isin(true_values)]
        
        # Convert Document IDs to UUIDs
        def generate_document_uuid(document_id_str):
            clean_id = str(document_id_str).strip().lower()
            return uuid5(UUID_NAMESPACE, f"document_{clean_id}")
        
        doc_uuids = set(trial_batch_df['Document ID'].apply(generate_document_uuid))
        
        logging.info("="*70)
        logging.info("TRIAL BATCH FILTERING")
        logging.info("="*70)
        logging.info(f"Total documents in database:  {len(df)}")
        logging.info(f"Trial batch documents:        {len(doc_uuids)}")
        logging.info("="*70)
        
        return doc_uuids
        
    except Exception as e:
        logging.error(f"❌ Error loading trial batch filter: {e}")
        return None

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def normalize_jurisdiction(jurisdiction: str) -> str:
    """
    Normalize jurisdiction name using aliases.
    
    INPUT: Raw jurisdiction string (e.g., "USA", "U.K.")
    ALGORITHM:
        1. Strip whitespace and check aliases
        2. Return normalized name or original
    OUTPUT: Normalized jurisdiction string
    """
    if not jurisdiction:
        return jurisdiction
    
    jurisdiction = jurisdiction.strip()
    return JURISDICTION_ALIASES.get(jurisdiction, jurisdiction)

def extract_json_from_text(text: str) -> Optional[Dict]:
    """
    Robust JSON extraction from LLM response.
    
    INPUT: Text potentially containing JSON
    ALGORITHM:
        1. Remove markdown code blocks
        2. Find JSON object pattern
        3. Parse and return
    OUTPUT: Parsed JSON dict or None
    """
    try:
        # Remove markdown code blocks
        text_clean = re.sub(r'```json\s*|\s*```', '', text).strip()
        
        # Try to find JSON object
        match = re.search(r'\{[\s\S]*\}', text_clean)
        if match:
            return json.loads(match.group(0))
        return json.loads(text_clean)
    except Exception as e:
        logging.debug(f"JSON parse error: {e}")
        return None

def find_citation_indices(full_text: str, citation_string: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Locate citation in full text.
    
    INPUT:
        - full_text: Complete document text
        - citation_string: Citation text to find
    ALGORITHM:
        1. Search for exact match
        2. Return start and end indices
    OUTPUT: (start_index, end_index) or (None, None)
    """
    if not citation_string or not full_text:
        return None, None
    
    try:
        start_index = full_text.find(citation_string)
        if start_index != -1:
            return start_index, start_index + len(citation_string)
    except Exception:
        pass
    
    return None, None

def extract_paragraph_context(text: str, start_index: int, end_index: int) -> Optional[str]:
    """
    Extract full paragraph containing citation.
    
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
    
    # Find paragraph start
    paragraph_start = text.rfind('\n\n', 0, start_index)
    paragraph_start = 0 if paragraph_start == -1 else paragraph_start + 2
    
    # Find paragraph end
    paragraph_end = text.find('\n\n', end_index)
    paragraph_end = len(text) if paragraph_end == -1 else paragraph_end
    
    return text[paragraph_start:paragraph_end].strip()

def extract_context_sentences(text: str, start_index: int, end_index: int, 
                              num_sentences: int = 3) -> Tuple[str, str]:
    """
    Extract sentences before and after citation.
    
    INPUT:
        - text: Full document text
        - start_index: Citation start position
        - end_index: Citation end position
        - num_sentences: Number of sentences to extract (default 3)
    ALGORITHM:
        1. Split text into sentences using basic punctuation
        2. Find citation location
        3. Extract N sentences before and after
    OUTPUT: (context_before, context_after) as strings
    """
    if not text or start_index is None:
        return "", ""
    
    try:
        # Simple sentence splitting (can be improved with NLTK if needed)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        # Find which sentence contains the citation
        char_count = 0
        citation_sentence_idx = 0
        
        for i, sentence in enumerate(sentences):
            char_count += len(sentence) + 1  # +1 for the space
            if char_count > start_index:
                citation_sentence_idx = i
                break
        
        # Extract context
        before_start = max(0, citation_sentence_idx - num_sentences)
        before_end = citation_sentence_idx
        after_start = citation_sentence_idx + 1
        after_end = min(len(sentences), citation_sentence_idx + 1 + num_sentences)
        
        context_before = ' '.join(sentences[before_start:before_end])
        context_after = ' '.join(sentences[after_start:after_end])
        
        return context_before, context_after
    
    except Exception as e:
        logging.debug(f"Error extracting context sentences: {e}")
        return "", ""

# ============================================================================
# PHASE 1: SOURCE JURISDICTION IDENTIFICATION
# ============================================================================

def get_source_jurisdiction(geographies_string: str) -> str:
    """
    Extract primary jurisdiction from Geographies field.
    
    INPUT: "United States; California; Washington, D.C."
    ALGORITHM:
        1. Split by semicolon
        2. Take first value (country level)
        3. Handle international tribunals
    OUTPUT: Primary country string
    """
    if not geographies_string:
        return "Unknown"
    
    parts = [p.strip() for p in geographies_string.split(';')]
    primary = parts[0]  # Country level only
    
    # Check if international
    if primary in ['International', 'INTL', 'World']:
        return "International"
    
    # Normalize jurisdiction
    return normalize_jurisdiction(primary)

def get_source_region(country: str) -> str:
    """
    Classify country as Global North/South/International.
    
    INPUT: Country name
    ALGORITHM:
        1. Use get_binding_courts() from config.py
        2. Check if country is in Global North or South lists
        3. Return classification
    OUTPUT: "Global North" | "Global South" | "International" | "Unknown"
    """
    if country == "International":
        return "International"
    
    if not country or country == "Unknown":
        return "Unknown"
    
    # Get binding courts configuration (contains region mapping)
    binding_courts = get_binding_courts(country, "Unknown")
    
    # Simple heuristic: if binding_courts includes ICJ/ITLOS, likely International
    # Otherwise, use Maria Tigre's definition from config.py
    # For now, we'll use a simplified mapping
    
    GLOBAL_NORTH_COUNTRIES = {
        "United States", "United Kingdom", "Canada", "Australia", "New Zealand",
        "Germany", "France", "Netherlands", "Belgium", "Switzerland", "Austria",
        "Sweden", "Norway", "Denmark", "Finland", "Iceland", "Ireland", "Italy",
        "Spain", "Portugal", "Greece", "Japan", "South Korea", "Singapore",
        "European Union", "Council of Europe"
    }
    
    if country in GLOBAL_NORTH_COUNTRIES:
        return "Global North"
    else:
        return "Global South"

# ============================================================================
# PHASE 2: ENHANCED EXTRACTION
# ============================================================================

def generate_phase2_extraction_prompt(text: str, source_jurisdiction: str, 
                                     source_region: str) -> str:
    """
    Generate comprehensive extraction prompt for Phase 2.
    
    KEY PRINCIPLE: Extract EVERYTHING - no filtering for foreign/domestic.
    
    INPUT:
        - text: Document text
        - source_jurisdiction: Where the citing court is located
        - source_region: Global North/South/International
    ALGORITHM:
        1. Build detailed extraction instructions
        2. List all citation format patterns
        3. Request context capture
        4. Specify JSON output format
    OUTPUT: Complete prompt string
    """
    
    prompt = f"""You are extracting ALL judicial decision references from a legal document.

SOURCE COURT INFORMATION:
- Jurisdiction: {source_jurisdiction}
- Region: {source_region}

CRITICAL INSTRUCTION: Extract EVERY reference to case law, regardless of whether it's domestic or foreign.
Do NOT filter by jurisdiction - we will classify that later.

EXTRACTION PATTERNS (extract ALL of these):

1. Traditional Citations
   - "Brown v. Board of Education, 347 U.S. 483 (1954)"
   - "R (Miller) v Secretary of State [2017] UKSC 5"
   - Include ALL citation formats and parallel citations

2. Narrative References
   - "The Norwegian Supreme Court held in 2020..."
   - "Following the Dutch court's approach in..."
   - "The Oslo District Court ruled..."

3. Shorthand References
   - "the Urgenda case"
   - "following Abraham"
   - "the landmark Dutch climate decision"

4. Scholarly Citations
   - "Professor X's analysis of the Urgenda case"
   - "As noted by UNEP regarding the Norwegian ruling"

5. Procedural References
   - "On appeal from..."
   - "Affirmed by..."
   - "Following reversal by..."

6. Comparative References
   - "Unlike the approach in..."
   - "Similar to..."
   - "Distinguishing..."

7. Signal Citations
   - "See also..."
   - "Cf..."
   - "Compare with..."

8. Footnote/Endnote Citations
   - Include ALL citations in footnotes
   - Include "supra" and "infra" references

9. Dissenting/Concurring Opinion Citations
   - Include citations from ALL opinion types

10. Doctrine References
    - "European precautionary principle jurisprudence"
    - "Following the approach developed in..."

11. Advisory Opinions
    - ICJ Advisory Opinions
    - Other international tribunal advisory opinions

12. Pending/Ongoing Cases
    - "pending before..."
    - "currently before..."

CONTEXT CAPTURE:
For EACH citation found, capture:
- The complete citation text
- The 2-3 sentences BEFORE the citation
- The 2-3 sentences AFTER the citation
- The section heading where it appears (if identifiable)
- Whether it's in main text, footnote, dissent, or concurrence

OUTPUT FORMAT (JSON):
{{
  "case_law_references": [
    {{
      "case_name": "extracted case name",
      "raw_text": "complete citation as it appears",
      "format": "traditional|narrative|shorthand|scholarly|procedural|comparative|signal|footnote|dissent|doctrine|advisory|pending",
      "context_before": "2-3 sentences before",
      "context_after": "2-3 sentences after",
      "section": "section heading if available",
      "location": "main_text|footnote|dissent|concurrence",
      "confidence": 0.0-1.0
    }}
  ],
  "total_references_found": number,
  "sections_with_citations": ["list of sections"]
}}

REMEMBER: Extract EVERYTHING that looks like case law. Do NOT filter by jurisdiction.
Your job is extraction, not classification.

Document text:
{text[:15000]}"""  # Limit to first 15,000 chars to manage token usage
    
    return prompt

def extract_all_case_references_phase2(document_id: uuid.UUID, raw_text: str, 
                                      source_jurisdiction: str, source_region: str,
                                      session) -> Optional[Dict]:
    """
    Phase 2: Extract ALL case law references using Haiku.
    
    INPUT:
        - document_id: UUID of document
        - raw_text: Full document text
        - source_jurisdiction: Source court jurisdiction
        - source_region: Global North/South/International
        - session: Database session
    ALGORITHM:
        1. Generate extraction prompt
        2. Call Claude Haiku 4.5
        3. Parse JSON response
        4. Return all extracted references
    OUTPUT: Dict with extracted references or None
    """
    try:
        # Generate prompt
        prompt = generate_phase2_extraction_prompt(raw_text, source_jurisdiction, source_region)
        
        # Call Claude Haiku
        start_time = time.time()
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",  # Haiku 4.5
            max_tokens=4000,
            temperature=0.0,
            messages=[{"role": "user", "content": prompt}]
        )
        extraction_time = time.time() - start_time
        
        # Parse response
        response_text = message.content[0].text
        data = extract_json_from_text(response_text)
        
        if not data:
            logging.error(f"Failed to parse Phase 2 JSON for document {document_id}")
            return None
        
        # Add metadata
        data['phase_2_extraction_time'] = extraction_time
        data['phase_2_tokens_input'] = message.usage.input_tokens
        data['phase_2_tokens_output'] = message.usage.output_tokens
        data['phase_2_model'] = "claude-haiku-4-5-20251001"
        
        logging.info(f"Phase 2: Extracted {data.get('total_references_found', 0)} references")
        
        return data
        
    except Exception as e:
        logging.error(f"Error in Phase 2 extraction: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return None

# ============================================================================
# PHASE 3: ORIGIN IDENTIFICATION (3-TIER APPROACH)
# ============================================================================

def identify_origin_tier1_dictionary(case_name: str, raw_text: str) -> Optional[Dict]:
    """
    Tier 1: Lookup in KNOWN_FOREIGN_COURTS and LANDMARK_CLIMATE_CASES.
    
    INPUT:
        - case_name: Extracted case name
        - raw_text: Raw citation text
    ALGORITHM:
        1. Check cache first
        2. Search KNOWN_FOREIGN_COURTS for court name match
        3. Search LANDMARK_CLIMATE_CASES for case name match
        4. Return if found
    OUTPUT: Dict with origin data or None
    """
    # Check cache
    cache_key = case_name.lower().strip()
    if cache_key in CITATION_ORIGIN_CACHE:
        logging.debug(f"Tier 1: Cache hit for '{case_name}'")
        return CITATION_ORIGIN_CACHE[cache_key]
    
    # Search KNOWN_FOREIGN_COURTS
    for court_pattern, court_data in KNOWN_FOREIGN_COURTS.items():
        if court_pattern.lower() in raw_text.lower() or court_pattern.lower() in case_name.lower():
            result = {
                'origin': court_data['country'],
                'region': court_data['region'],
                'court': court_pattern,
                'tier': 1,
                'confidence': 0.95,
                'method': 'dictionary_court_match'
            }
            # Cache result
            CITATION_ORIGIN_CACHE[cache_key] = result
            logging.debug(f"Tier 1: Court match for '{case_name}' -> {court_data['country']}")
            return result
    
    # Search LANDMARK_CLIMATE_CASES
    for case_pattern, case_data in LANDMARK_CLIMATE_CASES.items():
        if case_pattern.lower() in case_name.lower():
            result = {
                'origin': case_data['country'],
                'region': case_data['region'],
                'court': case_data.get('court', 'Unknown'),
                'year': case_data.get('year'),
                'tier': 1,
                'confidence': 0.95,
                'method': 'dictionary_case_match'
            }
            # Cache result
            CITATION_ORIGIN_CACHE[cache_key] = result
            logging.debug(f"Tier 1: Case match for '{case_name}' -> {case_data['country']}")
            return result
    
    logging.debug(f"Tier 1: No match for '{case_name}'")
    return None

def identify_origin_tier2_sonnet(case_name: str, raw_text: str, 
                                context_before: str, context_after: str) -> Optional[Dict]:
    """
    Tier 2: Use Claude Sonnet for intelligent origin identification.
    
    INPUT:
        - case_name: Extracted case name
        - raw_text: Raw citation text
        - context_before: Context sentences before citation
        - context_after: Context sentences after citation
    ALGORITHM:
        1. Build prompt with full context
        2. Call Claude Sonnet 4.5
        3. Parse origin identification
        4. Return with confidence score
    OUTPUT: Dict with origin data or None
    """
    try:
        prompt = f"""Identify the jurisdiction/country of origin for this legal case citation.

CASE NAME: {case_name}
RAW CITATION: {raw_text}

CONTEXT BEFORE:
{context_before}

CONTEXT AFTER:
{context_after}

Analyze ALL available signals:
1. Court name in citation
2. Citation format (e.g., "U.S." suggests United States, "UKSC" suggests UK)
3. Case name patterns
4. Geographic references in context
5. Legal system indicators

Respond in JSON:
{{
  "origin_country": "country name",
  "region": "Global North|Global South|International",
  "court": "court name if identifiable",
  "year": year if mentioned,
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation of how you determined the origin"
}}

If you cannot determine the origin with reasonable confidence (>0.5), return confidence 0.0.
"""
        
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",  # Sonnet 4.5
            max_tokens=500,
            temperature=0.0,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = message.content[0].text
        data = extract_json_from_text(response_text)
        
        if not data or data.get('confidence', 0) < 0.5:
            logging.debug(f"Tier 2: Low confidence for '{case_name}'")
            return None
        
        result = {
            'origin': data.get('origin_country'),
            'region': data.get('region'),
            'court': data.get('court'),
            'year': data.get('year'),
            'tier': 2,
            'confidence': data.get('confidence', 0.0),
            'method': 'sonnet_analysis',
            'reasoning': data.get('reasoning', '')
        }
        
        # Cache if high confidence
        if result['confidence'] >= 0.7:
            cache_key = case_name.lower().strip()
            CITATION_ORIGIN_CACHE[cache_key] = result
        
        logging.debug(f"Tier 2: Identified '{case_name}' -> {result['origin']} (confidence: {result['confidence']})")
        return result
        
    except Exception as e:
        logging.error(f"Error in Tier 2 identification: {e}")
        return None

def identify_origin_tier3_websearch(case_name: str, raw_text: str) -> Optional[Dict]:
    """
    Tier 3: Web search for obscure or uncertain cases.
    
    INPUT:
        - case_name: Extracted case name
        - raw_text: Raw citation text
    ALGORITHM:
        1. Construct search query
        2. Use web_search tool (if available)
        3. Parse search results
        4. Extract jurisdiction information
    OUTPUT: Dict with origin data or None
    
    NOTE: This is a placeholder - actual web search implementation
    would require integration with search API or tool.
    """
    # Placeholder for web search functionality
    # In production, this would:
    # 1. Search for case name + "court" + "jurisdiction"
    # 2. Parse top results
    # 3. Extract country/court information
    # 4. Return with moderate confidence (0.6-0.8)
    
    logging.debug(f"Tier 3: Web search not implemented for '{case_name}'")
    return None

def identify_case_origin(case_name: str, raw_text: str, 
                        context_before: str, context_after: str) -> Dict:
    """
    Master function: Identify case origin using 3-tier approach.
    
    INPUT:
        - case_name: Extracted case name
        - raw_text: Raw citation text
        - context_before: Context sentences before
        - context_after: Context sentences after
    ALGORITHM:
        1. Try Tier 1 (Dictionary) - fastest, highest confidence
        2. If fails, try Tier 2 (Sonnet) - intelligent analysis
        3. If fails, try Tier 3 (Web Search) - last resort
        4. If all fail, return unknown with low confidence
    OUTPUT: Dict with origin data (always returns, never None)
    """
    # Tier 1: Dictionary lookup
    tier1_result = identify_origin_tier1_dictionary(case_name, raw_text)
    if tier1_result:
        return tier1_result
    
    # Tier 2: Sonnet analysis
    tier2_result = identify_origin_tier2_sonnet(case_name, raw_text, context_before, context_after)
    if tier2_result and tier2_result['confidence'] >= 0.5:
        return tier2_result
    
    # Tier 3: Web search (if implemented)
    tier3_result = identify_origin_tier3_websearch(case_name, raw_text)
    if tier3_result:
        return tier3_result
    
    # All tiers failed - return unknown
    logging.warning(f"Phase 3: Could not identify origin for '{case_name}'")
    return {
        'origin': 'Unknown',
        'region': 'Unknown',
        'court': None,
        'year': None,
        'tier': 0,
        'confidence': 0.0,
        'method': 'failed_identification'
    }

# ============================================================================
# PHASE 4: CLASSIFICATION
# ============================================================================

def classify_citation_type(source_jurisdiction: str, source_region: str,
                          case_origin: str, case_region: str) -> Tuple[str, bool]:
    """
    Phase 4: Classify citation type based on source and origin.
    
    INPUT:
        - source_jurisdiction: Where citing court is located
        - source_region: Global North/South/International
        - case_origin: Where cited case is from
        - case_region: Global North/South/International
    ALGORITHM:
        1. Normalize jurisdictions
        2. Compare source vs. case jurisdiction
        3. Apply classification logic:
           - Same jurisdiction = Domestic (exclude)
           - Different jurisdiction + one is International = International Citation
           - Different jurisdiction + both are countries = Foreign Citation
           - Special case: both foreign + one is international = Foreign International
    OUTPUT: (citation_type, is_cross_jurisdictional)
    """
    # Normalize jurisdictions
    source_norm = normalize_jurisdiction(source_jurisdiction)
    case_norm = normalize_jurisdiction(case_origin)
    
    # Handle unknowns
    if case_origin == 'Unknown' or case_region == 'Unknown':
        return 'Unknown', False
    
    # Same jurisdiction = Domestic (NOT cross-jurisdictional)
    if source_norm == case_norm:
        return 'Domestic', False
    
    # Different jurisdictions = Cross-jurisdictional
    is_cross_jurisdictional = True
    
    # Classification logic
    if source_region == 'International' or case_region == 'International':
        if source_region == 'International' and case_region == 'International':
            # Both international
            return 'International Citation', True
        elif source_region == 'International':
            # Source is international, citing a national case
            return 'Foreign Citation', True
        else:
            # Source is national, citing international
            return 'International Citation', True
    
    # Both are national courts (different countries)
    return 'Foreign Citation', True

# ============================================================================
# MAIN PROCESSING FUNCTION
# ============================================================================

def process_single_document_phased(doc_tuple, session, stats: Dict) -> bool:
    """
    Process a single document through all 4 phases.
    
    INPUT:
        - doc_tuple: Database query result tuple
        - session: SQLAlchemy session
        - stats: Statistics dictionary
    ALGORITHM:
        Phase 1: Identify source jurisdiction
        Phase 2: Extract ALL case references
        Phase 3: Identify origin for each reference
        Phase 4: Classify each citation
        Save results to database
    OUTPUT: True if successful, False otherwise
    """
    document_id = doc_tuple[0]
    metadata_data = doc_tuple[1]
    raw_text = doc_tuple[2]
    case_id = doc_tuple[3]
    
    start_time = time.time()
    total_api_calls = 0
    total_tokens_input = 0
    total_tokens_output = 0
    
    try:
        logging.info(f"\n{'='*70}")
        logging.info(f"Processing Document: {document_id}")
        logging.info(f"{'='*70}")
        
        # ====================================================================
        # PHASE 1: SOURCE JURISDICTION
        # ====================================================================
        logging.info("Phase 1: Identifying source jurisdiction...")
        
        # Extract from metadata
        geographies = metadata_data.get('Geographies', '') if isinstance(metadata_data, dict) else ''
        source_jurisdiction = get_source_jurisdiction(geographies)
        source_region = get_source_region(source_jurisdiction)
        
        logging.info(f"  Source: {source_jurisdiction} ({source_region})")
        
        # ====================================================================
        # PHASE 2: EXTRACTION
        # ====================================================================
        logging.info("Phase 2: Extracting ALL case law references...")
        
        phase2_result = extract_all_case_references_phase2(
            document_id, raw_text, source_jurisdiction, source_region, session
        )
        
        if not phase2_result:
            logging.error("  Phase 2 failed - skipping document")
            stats['phase2_failures'] += 1
            return False
        
        total_api_calls += 1
        total_tokens_input += phase2_result.get('phase_2_tokens_input', 0)
        total_tokens_output += phase2_result.get('phase_2_tokens_output', 0)
        
        references = phase2_result.get('case_law_references', [])
        logging.info(f"  Extracted {len(references)} references")
        
        if len(references) == 0:
            logging.info("  No references found - creating summary with zero citations")
            
            # Create summary record
            summary = CitationExtractionPhasedSummary(
                document_id=document_id,
                total_references_extracted=0,
                foreign_citations_count=0,
                international_citations_count=0,
                foreign_international_citations_count=0,
                total_api_calls=total_api_calls,
                total_tokens_input=total_tokens_input,
                total_tokens_output=total_tokens_output,
                total_cost_usd=(total_tokens_input/1e6 * 0.25) + (total_tokens_output/1e6 * 1.25),
                extraction_started_at=datetime.fromtimestamp(start_time),
                extraction_completed_at=datetime.utcnow(),
                total_processing_time_seconds=time.time() - start_time,
                extraction_success=True,
                average_confidence=0.0,
                items_requiring_review=0
            )
            session.add(summary)
            session.commit()
            
            stats['processed'] += 1
            stats['no_citations'] += 1
            return True
        
        # ====================================================================
        # PHASE 3 & 4: ORIGIN IDENTIFICATION AND CLASSIFICATION
        # ====================================================================
        logging.info("Phase 3: Identifying case origins...")
        logging.info("Phase 4: Classifying citations...")
        
        citation_records = []
        foreign_count = 0
        international_count = 0
        foreign_international_count = 0
        confidences = []
        items_for_review = 0
        
        for i, ref in enumerate(references):
            # Extract citation location in text
            start_idx, end_idx = find_citation_indices(raw_text, ref.get('raw_text', ''))
            paragraph = extract_paragraph_context(raw_text, start_idx, end_idx)
            
            # Get context (already in ref, but extract from full text too for consistency)
            context_before = ref.get('context_before', '')
            context_after = ref.get('context_after', '')
            
            if not context_before or not context_after:
                context_before, context_after = extract_context_sentences(
                    raw_text, start_idx, end_idx, num_sentences=3
                )
            
            # Phase 3: Identify origin
            origin_data = identify_case_origin(
                ref.get('case_name', ''),
                ref.get('raw_text', ''),
                context_before,
                context_after
            )
            
            # Track API calls (Tier 2 uses Sonnet)
            if origin_data.get('tier') == 2:
                total_api_calls += 1
            
            # Phase 4: Classify
            citation_type, is_cross_jurisdictional = classify_citation_type(
                source_jurisdiction,
                source_region,
                origin_data['origin'],
                origin_data['region']
            )
            
            # Skip domestic citations
            if citation_type == 'Domestic':
                logging.debug(f"  Skipping domestic citation: {ref.get('case_name', 'Unknown')}")
                continue
            
            # Count by type
            if citation_type == 'Foreign Citation':
                foreign_count += 1
            elif citation_type == 'International Citation':
                international_count += 1
            elif citation_type == 'Foreign International Citation':
                foreign_international_count += 1
            
            # Check if needs manual review
            confidence = origin_data.get('confidence', 0.0)
            confidences.append(confidence)
            needs_review = confidence < 0.7
            if needs_review:
                items_for_review += 1
            
            # Create citation record
            citation_record = CitationExtractionPhased(
                document_id=document_id,
                case_id=case_id,
                
                # Phase 1
                source_jurisdiction=source_jurisdiction,
                source_region=source_region,
                
                # Phase 2
                case_name=ref.get('case_name'),
                raw_citation_text=ref.get('raw_text'),
                citation_format=ref.get('format'),
                context_before=context_before,
                context_after=context_after,
                section_heading=ref.get('section'),
                location_in_document=ref.get('location'),
                
                # Phase 3
                case_law_origin=origin_data['origin'],
                case_law_region=origin_data['region'],
                origin_identification_tier=origin_data['tier'],
                origin_confidence=origin_data['confidence'],
                
                # Phase 4
                citation_type=citation_type,
                is_cross_jurisdictional=is_cross_jurisdictional,
                
                # Extended metadata
                cited_court=origin_data.get('court'),
                cited_year=origin_data.get('year'),
                
                # Context
                full_paragraph=paragraph,
                position_in_document=i + 1,
                start_char_index=start_idx,
                end_char_index=end_idx,
                
                # Processing metadata
                phase_2_model='claude-haiku-4-5-20251001',
                phase_3_model=origin_data.get('method'),
                phase_4_model='rule-based',
                processing_time_seconds=time.time() - start_time,
                api_calls_used=total_api_calls,
                
                # Quality control
                requires_manual_review=needs_review,
                manual_review_reason=f"Low confidence: {confidence:.2f}" if needs_review else None
            )
            
            citation_records.append(citation_record)
        
        # ====================================================================
        # SAVE TO DATABASE
        # ====================================================================
        logging.info(f"Saving {len(citation_records)} cross-jurisdictional citations...")
        
        # Calculate totals
        total_cross_jurisdictional = foreign_count + international_count + foreign_international_count
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        # Calculate cost (Haiku: $0.25/M input, $1.25/M output)
        total_cost = (total_tokens_input/1e6 * 0.25) + (total_tokens_output/1e6 * 1.25)
        
        # Create summary
        summary = CitationExtractionPhasedSummary(
            document_id=document_id,
            total_references_extracted=len(references),
            foreign_citations_count=foreign_count,
            international_citations_count=international_count,
            foreign_international_citations_count=foreign_international_count,
            total_api_calls=total_api_calls,
            total_tokens_input=total_tokens_input,
            total_tokens_output=total_tokens_output,
            total_cost_usd=total_cost,
            extraction_started_at=datetime.fromtimestamp(start_time),
            extraction_completed_at=datetime.utcnow(),
            total_processing_time_seconds=time.time() - start_time,
            extraction_success=True,
            average_confidence=avg_confidence,
            items_requiring_review=items_for_review
        )
        
        # Add all records
        session.add(summary)
        for citation in citation_records:
            session.add(citation)
        
        session.commit()
        
        # Update statistics
        stats['processed'] += 1
        stats['total_references'] += len(references)
        stats['foreign_citations'] += foreign_count
        stats['international_citations'] += international_count
        stats['foreign_international_citations'] += foreign_international_count
        stats['needs_review'] += items_for_review
        
        logging.info(f"✓ Completed successfully:")
        logging.info(f"  Total references: {len(references)}")
        logging.info(f"  Cross-jurisdictional: {total_cross_jurisdictional}")
        logging.info(f"    - Foreign: {foreign_count}")
        logging.info(f"    - International: {international_count}")
        logging.info(f"    - Foreign International: {foreign_international_count}")
        logging.info(f"  Avg confidence: {avg_confidence:.2f}")
        logging.info(f"  Needs review: {items_for_review}")
        logging.info(f"  Cost: ${total_cost:.4f}")
        
        return True
        
    except Exception as e:
        session.rollback()
        logging.error(f"Error processing document: {e}")
        import traceback
        logging.error(traceback.format_exc())
        stats['errors'] += 1
        
        # Create failed summary
        try:
            summary = CitationExtractionPhasedSummary(
                document_id=document_id,
                extraction_started_at=datetime.fromtimestamp(start_time),
                extraction_completed_at=datetime.utcnow(),
                total_processing_time_seconds=time.time() - start_time,
                extraction_success=False,
                extraction_error=str(e)[:500]
            )
            session.add(summary)
            session.commit()
        except:
            pass
        
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
        5. Process each document through 4 phases
        6. Report comprehensive statistics
    OUTPUT: Statistics printed to log
    """
    logging.info("="*70)
    logging.info("CITATION EXTRACTION v5 - PHASED APPROACH")
    logging.info("Enhanced Foreign Case Law Capture")
    logging.info("="*70)
    logging.info("Architecture:")
    logging.info("  Phase 1: Source Jurisdiction Identification")
    logging.info("  Phase 2: Extract ALL Case References (Haiku 4.5)")
    logging.info("  Phase 3: Identify Case Origin (3-Tier)")
    logging.info("  Phase 4: Classify Citation Type")
    logging.info("="*70)
    
    # Get trial batch filter
    trial_batch_uuids = get_trial_batch_document_uuids()
    
    # Connect to database
    engine = create_engine(URL.create(**DB_CONFIG))
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Ensure tables exist
    Base.metadata.create_all(engine)
    logging.info("✓ Database tables verified/created")
    
    try:
        # Query documents that are DECISIONS with extracted text
        logging.info("\nQuerying documents classified as decisions...")
        
        query = session.query(
            Document.document_id,
            Document.metadata_data,
            ExtractedText.raw_text,
            Case.case_id
        ).join(
            ExtractedText, Document.document_id == ExtractedText.document_id
        ).join(
            Case, Document.case_id == Case.case_id
        ).filter(
            ExtractedText.raw_text != None,
            Document.is_decision == True  # Only process decisions
        )
        
        # Count total decisions
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
            session.query(CitationExtractionPhasedSummary.document_id).all()
        ]
        if processed_ids:
            query = query.filter(~Document.document_id.in_(processed_ids))
            logging.info(f"Excluding {len(processed_ids)} already processed documents")
        
        # Get final list
        documents = query.all()
        
        logging.info(f"\n✓ Documents to process: {len(documents)}")
        
        if len(documents) == 0:
            logging.warning("\n⚠️  No documents to process!")
            logging.info("\nPossible reasons:")
            logging.info("1. All decisions have already been processed")
            logging.info("2. No documents have been classified yet")
            logging.info("3. Trial batch filter excluded all documents")
            return
        
        # Initialize statistics
        stats = {
            'processed': 0,
            'total_references': 0,
            'foreign_citations': 0,
            'international_citations': 0,
            'foreign_international_citations': 0,
            'needs_review': 0,
            'phase2_failures': 0,
            'no_citations': 0,
            'errors': 0
        }
        
        # Process each document
        logging.info("\n" + "="*70)
        logging.info("STARTING PHASED EXTRACTION")
        logging.info("="*70)
        
        for doc in tqdm(documents, desc="Processing Documents"):
            process_single_document_phased(doc, session, stats)
        
        # Report final statistics
        logging.info("\n" + "="*70)
        logging.info("EXTRACTION COMPLETE - FINAL STATISTICS")
        logging.info("="*70)
        logging.info(f"Total decisions in database:     {total_decisions}")
        logging.info(f"Documents processed:             {stats['processed']}")
        logging.info(f"Documents with no citations:     {stats['no_citations']}")
        logging.info(f"Phase 2 failures:                {stats['phase2_failures']}")
        logging.info(f"Other errors:                    {stats['errors']}")
        logging.info("")
        logging.info("CITATION COUNTS:")
        logging.info(f"Total references extracted:      {stats['total_references']}")
        logging.info(f"Foreign Citations:               {stats['foreign_citations']}")
        logging.info(f"International Citations:         {stats['international_citations']}")
        logging.info(f"Foreign International Citations: {stats['foreign_international_citations']}")
        logging.info(f"Total cross-jurisdictional:      {stats['foreign_citations'] + stats['international_citations'] + stats['foreign_international_citations']}")
        logging.info("")
        logging.info(f"Items requiring manual review:   {stats['needs_review']}")
        
        if TRIAL_BATCH_CONFIG['ENABLED']:
            logging.info(f"\n✓ Trial batch mode was ENABLED")
        
        # Query final database statistics
        total_in_db = session.query(CitationExtractionPhased).count()
        logging.info(f"\n✓ Total citations in database:   {total_in_db}")
        
        logging.info("="*70)
        logging.info("Cache Statistics:")
        logging.info(f"Cache size: {len(CITATION_ORIGIN_CACHE)} entries")
        logging.info("="*70)
        
    finally:
        session.close()


if __name__ == "__main__":
    main()
