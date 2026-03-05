#!/usr/bin/env python3
"""
Citation Extraction Script - Version 5.3 (Full Text Processing)
================================================================
Enhanced Foreign Case Law Capture with Complete Document Analysis

🏃 Run from: project root
Command: python scripts/phase2/extract_citations_v5_3_fulltext.py

VERSION 5.3 - FULL TEXT PROCESSING WITH SEPARATION OF CONCERNS
==============================================================

CHANGES FROM v5.2:
- FULL TEXT PROCESSING: Passes entire document to LLM (no arbitrary text window)
- RESTORED ALL 12 EXTRACTION PATTERNS (v5.2 accidentally removed 6)
- TWO-PASS APPROACH: Extraction and Functional Classification are separated
  - Pass 1: Pure extraction (maximize recall)
  - Pass 2: Functional classification (applied to extracted citations)
- DYNAMIC CHUNKING: Only if document exceeds safe token threshold (~150K tokens)
- NO OUTPUT TOKEN LIMIT: Set to model maximum (16,384 for Sonnet 4.5)
- DEDUPLICATION: Removes duplicate citations when using chunked processing

ARCHITECTURE:
Phase 1: Source Jurisdiction Identification (from Case.geographies)
Phase 2A: Extract ALL case law references - FULL DOCUMENT (Sonnet 4.5)
Phase 2B: Functional Classification of extracted citations (Sonnet 4.5)
Phase 3: Identify case origin (3-tier: Dictionary → Sonnet → Web Search)
Phase 4: Classify citation type (Geographic + Functional)

KEY IMPROVEMENTS (v5.3):
- 100% document coverage (no text truncation)
- All 12 extraction patterns restored
- Separation of concerns: extraction vs. classification
- Dynamic chunking for very long documents (>300 pages)
- Improved recall targeting 85-95%

EXPECTED PERFORMANCE:
- Recall: 85-95% (major improvement from full document processing)
- Precision: 90-95%
- Cost: ~$0.10-0.25 per document (higher but necessary for quality)

REQUIREMENTS:
- Documents must be classified first (is_decision = True)
- Database tables: citation_extraction_phased, citation_extraction_phased_summary
- NO DATABASE RESET REQUIRED - uses existing schema

Author: Lucas Biasetton & Claude
Project: Doutorado PM
Version: 5.3
Date: November 25, 2025
"""

import json
import logging
import os
import re
import sys
import time
import uuid
from datetime import datetime

import pandas as pd

# Database
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

# ============================================================================
# CONFIGURATION & IMPORTS
# ============================================================================

_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _SCRIPTS_DIR)
from config import CONFIG, DATABASE_FILE, LOGS_DIR, TRIAL_BATCH_CONFIG, UUID_NAMESPACE
from gcp_secrets import get_engine
from gemini_client import call_gemini
from test_run import add_test_run_arg, get_sampled_document_uuids

sys.path.insert(0, os.path.join(_SCRIPTS_DIR, "0-initialize-database"))
from uuid import uuid5

# ============================================================================
# SQLALCHEMY MODELS FOR NEW TABLES
# ============================================================================
# Import Base and citation tables from init_database to avoid duplication
from init_database import (
    Base,
    Case,
    CitationExtractionPhased,
    CitationExtractionPhasedSummary,
    Document,
    ExtractedText,
)

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "citation_extraction_v5_3.log"),
        logging.StreamHandler(),
    ],
)
logging.getLogger("httpx").setLevel(logging.WARNING)

# ============================================================================
# API CLIENT SETUP (Gemini via google-genai)
# ============================================================================

# ============================================================================
# PROCESSING CONFIGURATION
# ============================================================================

# Token estimation: ~1 token per 4 characters (conservative estimate for legal text)
CHARS_PER_TOKEN = 4

# Sonnet 4.5 has 200K context window - we use 150K as safe threshold for input
# to leave room for system prompt and output
SAFE_TOKEN_THRESHOLD = 150000
SAFE_CHAR_THRESHOLD = SAFE_TOKEN_THRESHOLD * CHARS_PER_TOKEN  # ~600K chars

# Model maximum output tokens (Sonnet 4.5 supports up to 16,384)
MAX_OUTPUT_TOKENS = 16384

# Overlap for chunking (to avoid missing citations at chunk boundaries)
CHUNK_OVERLAP_CHARS = 5000

# ============================================================================
# ENHANCED DICTIONARIES - KNOWN FOREIGN COURTS
# ============================================================================

KNOWN_FOREIGN_COURTS = {
    # EUROPEAN COURTS
    "Court of Session": {"country": "Scotland", "region": "Global North", "type": "Appellate"},
    "Inner House": {"country": "Scotland", "region": "Global North", "type": "Appellate"},
    "Outer House": {"country": "Scotland", "region": "Global North", "type": "Trial"},
    "High Court of Justiciary": {
        "country": "Scotland",
        "region": "Global North",
        "type": "Criminal Supreme",
    },
    "The Hague Court": {"country": "Netherlands", "region": "Global North", "type": "Trial"},
    "District Court of The Hague": {
        "country": "Netherlands",
        "region": "Global North",
        "type": "Trial",
    },
    "Rechtbank Den Haag": {"country": "Netherlands", "region": "Global North", "type": "Trial"},
    "Hoge Raad": {"country": "Netherlands", "region": "Global North", "type": "Supreme"},
    "Dutch Supreme Court": {"country": "Netherlands", "region": "Global North", "type": "Supreme"},
    # NORDIC COURTS
    "Norwegian Supreme Court": {"country": "Norway", "region": "Global North", "type": "Supreme"},
    "Oslo District Court": {"country": "Norway", "region": "Global North", "type": "Trial"},
    "Borgarting Court of Appeal": {
        "country": "Norway",
        "region": "Global North",
        "type": "Appellate",
    },
    "Supreme Court of Sweden": {"country": "Sweden", "region": "Global North", "type": "Supreme"},
    "Supreme Court of Finland": {"country": "Finland", "region": "Global North", "type": "Supreme"},
    # UK COURTS
    "UK Supreme Court": {"country": "United Kingdom", "region": "Global North", "type": "Supreme"},
    "Supreme Court of the United Kingdom": {
        "country": "United Kingdom",
        "region": "Global North",
        "type": "Supreme",
    },
    "Court of Appeal (England and Wales)": {
        "country": "United Kingdom",
        "region": "Global North",
        "type": "Appellate",
    },
    "High Court of England and Wales": {
        "country": "United Kingdom",
        "region": "Global North",
        "type": "High",
    },
    "High Court of Justice": {
        "country": "United Kingdom",
        "region": "Global North",
        "type": "High",
    },
    # COMMONWEALTH COURTS
    "Supreme Court of New Zealand": {
        "country": "New Zealand",
        "region": "Global North",
        "type": "Supreme",
    },
    "High Court of New Zealand": {
        "country": "New Zealand",
        "region": "Global North",
        "type": "High",
    },
    "Court of Appeal of New Zealand": {
        "country": "New Zealand",
        "region": "Global North",
        "type": "Appellate",
    },
    "Supreme Court of Canada": {"country": "Canada", "region": "Global North", "type": "Supreme"},
    "Federal Court of Canada": {"country": "Canada", "region": "Global North", "type": "Federal"},
    "Ontario Superior Court": {"country": "Canada", "region": "Global North", "type": "Superior"},
    "Supreme Court of India": {"country": "India", "region": "Global South", "type": "Supreme"},
    "High Court of Australia": {
        "country": "Australia",
        "region": "Global North",
        "type": "Supreme",
    },
    # EUROPEAN UNION & HUMAN RIGHTS
    "Court of Justice of the European Union": {
        "country": "European Union",
        "region": "International",
        "type": "International",
    },
    "CJEU": {"country": "European Union", "region": "International", "type": "International"},
    "European Court of Justice": {
        "country": "European Union",
        "region": "International",
        "type": "International",
    },
    "European Court of Human Rights": {
        "country": "Council of Europe",
        "region": "International",
        "type": "International",
    },
    "ECtHR": {"country": "Council of Europe", "region": "International", "type": "International"},
    # LATIN AMERICA
    "Supreme Court of Colombia": {
        "country": "Colombia",
        "region": "Global South",
        "type": "Supreme",
    },
    "Constitutional Court of Colombia": {
        "country": "Colombia",
        "region": "Global South",
        "type": "Constitutional",
    },
    "Supreme Court of Brazil": {"country": "Brazil", "region": "Global South", "type": "Supreme"},
    "Supreme Federal Court of Brazil": {
        "country": "Brazil",
        "region": "Global South",
        "type": "Supreme",
    },
    "Supreme Court of Argentina": {
        "country": "Argentina",
        "region": "Global South",
        "type": "Supreme",
    },
    "Supreme Court of Chile": {"country": "Chile", "region": "Global South", "type": "Supreme"},
    # AFRICA
    "Constitutional Court of South Africa": {
        "country": "South Africa",
        "region": "Global South",
        "type": "Constitutional",
    },
    "Supreme Court of South Africa": {
        "country": "South Africa",
        "region": "Global South",
        "type": "Supreme",
    },
    "High Court of Kenya": {"country": "Kenya", "region": "Global South", "type": "High"},
    # ASIA-PACIFIC
    "Supreme Court of the Philippines": {
        "country": "Philippines",
        "region": "Global South",
        "type": "Supreme",
    },
    "Supreme Court of Pakistan": {
        "country": "Pakistan",
        "region": "Global South",
        "type": "Supreme",
    },
    "Supreme Court of Bangladesh": {
        "country": "Bangladesh",
        "region": "Global South",
        "type": "Supreme",
    },
    # GERMANY & FRANCE
    "Federal Constitutional Court of Germany": {
        "country": "Germany",
        "region": "Global North",
        "type": "Constitutional",
    },
    "Bundesverfassungsgericht": {
        "country": "Germany",
        "region": "Global North",
        "type": "Constitutional",
    },
    "Constitutional Council of France": {
        "country": "France",
        "region": "Global North",
        "type": "Constitutional",
    },
    "Conseil Constitutionnel": {
        "country": "France",
        "region": "Global North",
        "type": "Constitutional",
    },
    "Conseil d'État": {"country": "France", "region": "Global North", "type": "Administrative"},
    # INTERNATIONAL TRIBUNALS
    "International Court of Justice": {
        "country": "United Nations",
        "region": "International",
        "type": "International",
    },
    "ICJ": {"country": "United Nations", "region": "International", "type": "International"},
    "Inter-American Court of Human Rights": {
        "country": "Organization of American States",
        "region": "International",
        "type": "International",
    },
    "IACtHR": {
        "country": "Organization of American States",
        "region": "International",
        "type": "International",
    },
    "African Court on Human and Peoples' Rights": {
        "country": "African Union",
        "region": "International",
        "type": "International",
    },
    "International Tribunal for the Law of the Sea": {
        "country": "United Nations",
        "region": "International",
        "type": "International",
    },
    "ITLOS": {"country": "United Nations", "region": "International", "type": "International"},
}

# ============================================================================
# ENHANCED DICTIONARIES - LANDMARK CLIMATE CASES
# ============================================================================

LANDMARK_CLIMATE_CASES = {
    # NETHERLANDS
    "Urgenda": {
        "full_name": "Urgenda Foundation v. State of the Netherlands",
        "country": "Netherlands",
        "region": "Global North",
        "year": 2019,
        "court": "Dutch Supreme Court",
    },
    "Urgenda Foundation": {
        "full_name": "Urgenda Foundation v. State of the Netherlands",
        "country": "Netherlands",
        "region": "Global North",
        "year": 2019,
        "court": "Dutch Supreme Court",
    },
    # UNITED STATES
    "Massachusetts v. EPA": {
        "full_name": "Massachusetts v. Environmental Protection Agency",
        "country": "United States",
        "region": "Global North",
        "year": 2007,
        "court": "Supreme Court of the United States",
    },
    "Juliana v. United States": {
        "full_name": "Juliana v. United States",
        "country": "United States",
        "region": "Global North",
        "year": 2015,
        "court": "District Court of Oregon",
    },
    # UNITED KINGDOM
    "Plan B Earth": {
        "full_name": "R (Plan B Earth) v Secretary of State",
        "country": "United Kingdom",
        "region": "Global North",
        "year": 2020,
        "court": "UK Supreme Court",
    },
    "ClientEarth": {
        "full_name": "R (ClientEarth) v Secretary of State",
        "country": "United Kingdom",
        "region": "Global North",
        "year": 2015,
        "court": "UK Supreme Court",
    },
    # CANADA
    "Mathur v. Ontario": {
        "full_name": "Mathur et al. v. Her Majesty the Queen in Right of Ontario",
        "country": "Canada",
        "region": "Global North",
        "year": 2020,
        "court": "Ontario Superior Court of Justice",
    },
    # NEW ZEALAND
    "Thomson v Minister": {
        "full_name": "Thomson v Minister for Climate Change Issues",
        "country": "New Zealand",
        "region": "Global North",
        "year": 2017,
        "court": "High Court of New Zealand",
    },
    # IRELAND
    "Friends of the Irish Environment": {
        "full_name": "Friends of the Irish Environment CLG v. Ireland",
        "country": "Ireland",
        "region": "Global North",
        "year": 2020,
        "court": "Supreme Court of Ireland",
    },
    # NORWAY
    "Greenpeace Nordic": {
        "full_name": "Greenpeace Nordic Ass'n v. Ministry of Petroleum and Energy",
        "country": "Norway",
        "region": "Global North",
        "year": 2020,
        "court": "Norwegian Supreme Court",
    },
    "People v. Arctic Oil": {
        "full_name": "People v. Arctic Oil",
        "country": "Norway",
        "region": "Global North",
        "year": 2020,
        "court": "Norwegian Supreme Court",
    },
    # FRANCE
    "Grande Synthe": {
        "full_name": "Commune de Grande-Synthe v. France",
        "country": "France",
        "region": "Global North",
        "year": 2021,
        "court": "Conseil d'État",
    },
    "L'Affaire du Siècle": {
        "full_name": "L'Affaire du Siècle",
        "country": "France",
        "region": "Global North",
        "year": 2021,
        "court": "Administrative Court of Paris",
    },
    # GERMANY
    "Neubauer": {
        "full_name": "Neubauer et al. v. Germany",
        "country": "Germany",
        "region": "Global North",
        "year": 2021,
        "court": "Federal Constitutional Court of Germany",
    },
    # BELGIUM
    "Klimaatzaak": {
        "full_name": "VZW Klimaatzaak v. Kingdom of Belgium",
        "country": "Belgium",
        "region": "Global North",
        "year": 2021,
        "court": "Brussels Court of First Instance",
    },
    # COLOMBIA
    "Future Generations": {
        "full_name": "Future Generations v. Ministry of Environment",
        "country": "Colombia",
        "region": "Global South",
        "year": 2018,
        "court": "Supreme Court of Colombia",
    },
    # PAKISTAN
    "Ashgar Leghari": {
        "full_name": "Ashgar Leghari v. Federation of Pakistan",
        "country": "Pakistan",
        "region": "Global South",
        "year": 2015,
        "court": "Lahore High Court",
    },
    # SOUTH AFRICA
    "Earthlife Africa": {
        "full_name": "Earthlife Africa Johannesburg v. Minister of Environmental Affairs",
        "country": "South Africa",
        "region": "Global South",
        "year": 2017,
        "court": "High Court of South Africa",
    },
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
# KNOWN COUNTRIES LIST - FOR GEOGRAPHY PARSING
# ============================================================================

KNOWN_COUNTRIES = {
    # AMERICAS
    "United States",
    "Canada",
    "Mexico",
    "Brazil",
    "Argentina",
    "Chile",
    "Peru",
    "Colombia",
    "Ecuador",
    "Venezuela",
    "Bolivia",
    "Paraguay",
    "Uruguay",
    "Guatemala",
    "Honduras",
    "El Salvador",
    "Nicaragua",
    "Costa Rica",
    "Panama",
    "Cuba",
    "Jamaica",
    "Haiti",
    "Dominican Republic",
    "Puerto Rico",
    "Bahamas",
    "Barbados",
    "Trinidad and Tobago",
    "Grenada",
    "Guyana",
    "Suriname",
    # EUROPE - WESTERN
    "United Kingdom",
    "Ireland",
    "France",
    "Germany",
    "Netherlands",
    "Belgium",
    "Luxembourg",
    "Switzerland",
    "Austria",
    "Spain",
    "Portugal",
    "Italy",
    "Holy See (Vatican City State)",
    # EUROPE - NORTHERN
    "Norway",
    "Sweden",
    "Finland",
    "Denmark",
    "Iceland",
    # EUROPE - EASTERN
    "Poland",
    "Czech Republic",
    "Czechia",
    "Slovakia",
    "Hungary",
    "Romania",
    "Bulgaria",
    "Ukraine",
    "Russia",
    "Russian Federation",
    "Belarus",
    "Moldova",
    "Estonia",
    "Latvia",
    "Lithuania",
    # EUROPE - SOUTHEASTERN
    "Greece",
    "Turkey",
    "Türkiye",
    "Cyprus",
    "Malta",
    "Croatia",
    "Slovenia",
    "Serbia",
    "Bosnia and Herzegovina",
    "Montenegro",
    "North Macedonia",
    "Albania",
    # ASIA - EAST
    "China",
    "Japan",
    "South Korea",
    "North Korea",
    "Taiwan",
    "Mongolia",
    # ASIA - SOUTH
    "India",
    "Pakistan",
    "Bangladesh",
    "Sri Lanka",
    "Nepal",
    "Bhutan",
    "Maldives",
    # ASIA - SOUTHEAST
    "Philippines",
    "Indonesia",
    "Malaysia",
    "Singapore",
    "Thailand",
    "Vietnam",
    "Myanmar",
    "Cambodia",
    "Laos",
    "Brunei",
    "East Timor",
    # ASIA - CENTRAL & WEST
    "Kazakhstan",
    "Uzbekistan",
    "Turkmenistan",
    "Kyrgyzstan",
    "Tajikistan",
    "Afghanistan",
    "Iran",
    "Iraq",
    "Saudi Arabia",
    "United Arab Emirates",
    "Qatar",
    "Kuwait",
    "Bahrain",
    "Oman",
    "Yemen",
    "Israel",
    "Jordan",
    "Lebanon",
    "Syria",
    "Palestine",
    # AFRICA - NORTH
    "Egypt",
    "Morocco",
    "Algeria",
    "Tunisia",
    "Libya",
    "Sudan",
    "South Sudan",
    # AFRICA - WEST
    "Nigeria",
    "Ghana",
    "Senegal",
    "Ivory Coast",
    "Mali",
    "Burkina Faso",
    "Niger",
    "Guinea",
    "Sierra Leone",
    "Liberia",
    "Gambia",
    "Mauritania",
    "Cape Verde",
    "Benin",
    "Togo",
    # AFRICA - CENTRAL
    "Democratic Republic of the Congo",
    "Republic of the Congo",
    "Cameroon",
    "Central African Republic",
    "Chad",
    "Gabon",
    "Equatorial Guinea",
    # AFRICA - EAST
    "Kenya",
    "Ethiopia",
    "Tanzania",
    "Uganda",
    "Rwanda",
    "Burundi",
    "Somalia",
    "Eritrea",
    "Djibouti",
    "Seychelles",
    "Comoros",
    "Mauritius",
    "Madagascar",
    "Malawi",
    # AFRICA - SOUTHERN
    "South Africa",
    "Zimbabwe",
    "Zambia",
    "Botswana",
    "Namibia",
    "Mozambique",
    "Angola",
    "Lesotho",
    "Eswatini",
    # OCEANIA
    "Australia",
    "New Zealand",
    "Papua New Guinea",
    "Fiji",
    "Vanuatu",
    "Samoa",
    "Tonga",
    "Solomon Islands",
    "Kiribati",
    "Micronesia",
    "Palau",
    "Marshall Islands",
    "Nauru",
    "Tuvalu",
    # INTERNATIONAL / SUPRANATIONAL
    "European Union",
    "International",
}

# ============================================================================
# GLOBAL CACHES
# ============================================================================

# Cache for repeated citation origin lookups
CITATION_ORIGIN_CACHE: dict[str, dict] = {}

# ============================================================================
# TRIAL BATCH FILTERING
# ============================================================================


def get_trial_batch_document_uuids() -> set[uuid.UUID] | None:
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
    if not TRIAL_BATCH_CONFIG["ENABLED"]:
        logging.info("ℹ️  Trial batch mode DISABLED - will process all classified decisions")
        return None

    try:
        df = pd.read_excel(DATABASE_FILE)
        logging.info(f"Loaded database with {len(df)} rows for trial batch filtering")

        col_name = TRIAL_BATCH_CONFIG["COLUMN_NAME"]
        if col_name not in df.columns:
            logging.error(f"❌ Trial batch column '{col_name}' not found!")
            return None

        true_values = TRIAL_BATCH_CONFIG["TRUE_VALUES"]
        trial_batch_df = df[df[col_name].isin(true_values)]

        # Convert Document IDs to UUIDs
        def generate_document_uuid(document_id_str):
            clean_id = str(document_id_str).strip().lower()
            return uuid5(UUID_NAMESPACE, f"document_{clean_id}")

        doc_uuids = set(trial_batch_df["Document ID"].apply(generate_document_uuid))

        logging.info("=" * 70)
        logging.info("TRIAL BATCH FILTERING")
        logging.info("=" * 70)
        logging.info(f"Total documents in database:  {len(df)}")
        logging.info(f"Trial batch documents:        {len(doc_uuids)}")
        logging.info("=" * 70)

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


def extract_json_from_text(text: str) -> dict | None:
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
        text_clean = re.sub(r"```json\s*|\s*```", "", text).strip()

        # Try to find JSON object
        match = re.search(r"\{[\s\S]*\}", text_clean)
        if match:
            return json.loads(match.group(0))
        return json.loads(text_clean)
    except Exception as e:
        logging.debug(f"JSON parse error: {e}")
        return None


def find_citation_indices(full_text: str, citation_string: str) -> tuple[int | None, int | None]:
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


def extract_paragraph_context(text: str, start_index: int, end_index: int) -> str | None:
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
    paragraph_start = text.rfind("\n\n", 0, start_index)
    paragraph_start = 0 if paragraph_start == -1 else paragraph_start + 2

    # Find paragraph end
    paragraph_end = text.find("\n\n", end_index)
    paragraph_end = len(text) if paragraph_end == -1 else paragraph_end

    return text[paragraph_start:paragraph_end].strip()


def extract_context_sentences(
    text: str, start_index: int, end_index: int, num_sentences: int = 5
) -> tuple[str, str]:
    """
    Extract sentences before and after citation.

    INPUT:
        - text: Full document text
        - start_index: Citation start position
        - end_index: Citation end position
        - num_sentences: Number of sentences to extract (default 5)
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
        sentences = re.split(r"(?<=[.!?])\s+", text)

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

        context_before = " ".join(sentences[before_start:before_end])
        context_after = " ".join(sentences[after_start:after_end])

        return context_before, context_after

    except Exception as e:
        logging.debug(f"Error extracting context sentences: {e}")
        return "", ""


def estimate_token_count(text: str) -> int:
    """
    Estimate token count for a text string.

    INPUT: Text string
    ALGORITHM: Divide character count by average chars per token (4)
    OUTPUT: Estimated token count
    """
    return len(text) // CHARS_PER_TOKEN


def should_chunk_document(text: str) -> bool:
    """
    Determine if document needs to be chunked based on size.

    INPUT: Document text
    ALGORITHM: Compare character count to safe threshold
    OUTPUT: True if chunking needed, False otherwise
    """
    return len(text) > SAFE_CHAR_THRESHOLD


def chunk_document(text: str) -> list[tuple[str, int, int]]:
    """
    Split document into overlapping chunks for processing.

    INPUT: Full document text
    ALGORITHM:
        1. Calculate chunk size (half of safe threshold for 2 chunks)
        2. Create chunks with overlap at boundaries
        3. Return list of (chunk_text, start_position, end_position)
    OUTPUT: List of tuples (chunk_text, start_pos, end_pos)
    """
    # Use half the safe threshold for each chunk to ensure two chunks fit comfortably
    chunk_size = SAFE_CHAR_THRESHOLD // 2

    chunks = []
    start = 0

    while start < len(text):
        # Calculate end position for this chunk
        end = min(start + chunk_size, len(text))

        # If this is not the last chunk, extend to include overlap
        if end < len(text):
            end = min(end + CHUNK_OVERLAP_CHARS, len(text))

        chunk_text = text[start:end]
        chunks.append((chunk_text, start, end))

        # Move start position (accounting for overlap in previous chunk)
        if end < len(text):
            start = end - CHUNK_OVERLAP_CHARS
        else:
            break

    logging.info(f"Document chunked into {len(chunks)} parts")
    for i, (chunk, s, e) in enumerate(chunks):
        logging.info(
            f"  Chunk {i + 1}: chars {s}-{e} ({len(chunk):,} chars, ~{estimate_token_count(chunk):,} tokens)"
        )

    return chunks


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

    parts = [p.strip() for p in geographies_string.split(";")]
    primary = parts[0]  # Country level only

    # Check if international
    if primary in ["International", "INTL", "World"]:
        return "International"

    # Normalize jurisdiction
    return normalize_jurisdiction(primary)


def get_source_region(country: str) -> str:
    """
    Classify country as Global North/South/International.

    INPUT: Country name
    ALGORITHM:
        1. Check if international
        2. Check against GLOBAL_NORTH_COUNTRIES list
        3. Default to Global South
    OUTPUT: "Global North" | "Global South" | "International" | "Unknown"
    """
    if country == "International":
        return "International"

    if not country or country == "Unknown":
        return "Unknown"

    GLOBAL_NORTH_COUNTRIES = {
        "United States",
        "United Kingdom",
        "Canada",
        "Australia",
        "New Zealand",
        "Germany",
        "France",
        "Netherlands",
        "Belgium",
        "Switzerland",
        "Austria",
        "Sweden",
        "Norway",
        "Denmark",
        "Finland",
        "Iceland",
        "Ireland",
        "Italy",
        "Spain",
        "Portugal",
        "Greece",
        "Japan",
        "South Korea",
        "Singapore",
        "European Union",
        "Council of Europe",
    }

    if country in GLOBAL_NORTH_COUNTRIES:
        return "Global North"
    else:
        return "Global South"


def extract_country_from_geographies(geographies_string: str) -> str:
    """
    Extract country name from Case.geographies field.

    INPUT: Geography string from Case.geographies column
    ALGORITHM:
        1. If empty/null, return "Unknown"
        2. Split by semicolon and strip whitespace
        3. Check each part against KNOWN_COUNTRIES set
        4. Return first country found or first part as fallback
    OUTPUT: Country name string
    """
    if not geographies_string:
        return "Unknown"

    # Split and clean parts
    parts = [p.strip() for p in str(geographies_string).split(";")]

    # Find the country among the parts
    for part in parts:
        if part in KNOWN_COUNTRIES:
            return part

    # No country found in KNOWN_COUNTRIES
    logging.debug(f"No recognized country in geography: {geographies_string}")
    return parts[0] if parts else "Unknown"


# ============================================================================
# PHASE 2A: PURE EXTRACTION (MAXIMUM RECALL)
# ============================================================================


def generate_extraction_prompt(
    text: str, source_jurisdiction: str, source_region: str, chunk_info: str = ""
) -> str:
    """
    Generate comprehensive extraction prompt for Phase 2A.

    KEY PRINCIPLE: Extract EVERYTHING - no filtering, no classification.
    FOCUS: Maximum recall of case law references.

    INPUT:
        - text: Document text (full or chunk)
        - source_jurisdiction: Where the citing court is located
        - source_region: Global North/South/International
        - chunk_info: Optional info about which chunk this is
    ALGORITHM:
        1. Build detailed extraction instructions
        2. List ALL 12 citation format patterns (RESTORED)
        3. Specify JSON output format focused on extraction
    OUTPUT: Complete prompt string
    """

    chunk_notice = ""
    if chunk_info:
        chunk_notice = (
            f"\n\nNOTE: This is {chunk_info}. Extract ALL case law references from this portion.\n"
        )

    prompt = f"""You are extracting ALL judicial decision references from a legal document.
Your ONLY task is EXTRACTION - identify and extract every reference to case law.
{chunk_notice}
SOURCE COURT INFORMATION:
- Jurisdiction: {source_jurisdiction}
- Region: {source_region}

============================================================
CRITICAL INSTRUCTIONS:
============================================================
1. Extract EVERY reference to case law, regardless of domestic or foreign origin
2. Do NOT filter by jurisdiction - extract everything
3. Do NOT classify how citations are used - just extract them
4. Be EXHAUSTIVE - capture every mention of any case, court ruling, or judicial decision
5. Read the ENTIRE text carefully - do not skip any sections

============================================================
EXTRACTION PATTERNS - CAPTURE ALL OF THESE:
============================================================

1. TRADITIONAL CITATIONS (formal legal citations)
   - "Brown v. Board of Education, 347 U.S. 483 (1954)"
   - "R (Miller) v Secretary of State [2017] UKSC 5"
   - "Case C-473/14 Dimos Kropias Attikis"
   - Include ALL citation formats and parallel citations

2. NARRATIVE REFERENCES (descriptive mentions)
   - "The Norwegian Supreme Court held in 2020..."
   - "Following the Dutch court's approach in..."
   - "The Oslo District Court ruled..."
   - "The European Court of Human Rights stated..."

3. SHORTHAND REFERENCES (abbreviated mentions)
   - "the Urgenda case"
   - "following Abraham"
   - "the landmark Dutch climate decision"
   - "as established in Öneryıldız"

4. SCHOLARLY CITATIONS (academic references to cases)
   - "Professor X's analysis of the Urgenda case"
   - "As noted by UNEP regarding the Norwegian ruling"
   - "Commentary on the ECtHR jurisprudence"

5. PROCEDURAL REFERENCES (case history)
   - "On appeal from..."
   - "Affirmed by..."
   - "Following reversal by..."
   - "Remanded to..."

6. COMPARATIVE REFERENCES (comparing to other cases)
   - "Unlike the approach in..."
   - "Similar to..."
   - "Distinguishing..."
   - "Consistent with..."

7. SIGNAL CITATIONS (legal signals)
   - "See also..."
   - "Cf..."
   - "Compare with..."
   - "But see..."
   - "Accord..."

8. FOOTNOTE/ENDNOTE CITATIONS
   - Include ALL citations appearing in footnotes
   - Include "supra" and "infra" references
   - Include ibid. and id. references that refer to cases

9. DISSENTING/CONCURRING OPINION CITATIONS
   - Citations in dissenting opinions
   - Citations in concurring opinions
   - Note which type of opinion contains the citation

10. DOCTRINE REFERENCES (legal principle attributions)
    - "European precautionary principle jurisprudence"
    - "Following the approach developed in..."
    - "The doctrine established by..."

11. ADVISORY OPINIONS
    - ICJ Advisory Opinions
    - Other international tribunal advisory opinions
    - "Advisory Opinion on..."

12. PENDING/ONGOING CASE REFERENCES
    - "pending before..."
    - "currently before..."
    - "the ongoing case of..."

============================================================
OUTPUT FORMAT (JSON):
============================================================
{{
  "case_law_references": [
    {{
      "case_name": "extracted case name (e.g., 'Urgenda Foundation v. State of the Netherlands')",
      "raw_text": "complete citation text exactly as it appears",
      "confidence": 0.0-1.0
    }}
  ],
  "total_references_found": number,
  "extraction_notes": "any notes about the extraction process"
}}

============================================================
IMPORTANT REMINDERS:
============================================================
- Extract EVERYTHING that looks like a case reference
- Do NOT skip any sections of the document
- Include citations even if you're uncertain about the format
- Better to over-extract than to miss citations
- Your job is ONLY extraction - classification comes later

Document text:
{text}"""

    return prompt


def extract_citations_from_text(
    document_id: uuid.UUID,
    text: str,
    source_jurisdiction: str,
    source_region: str,
    chunk_info: str = "",
) -> dict | None:
    """
    Phase 2A: Extract ALL case law references using Sonnet 4.5.

    INPUT:
        - document_id: UUID of document
        - text: Document text (full or chunk)
        - source_jurisdiction: Source court jurisdiction
        - source_region: Global North/South/International
        - chunk_info: Optional info about which chunk this is
    ALGORITHM:
        1. Generate extraction prompt
        2. Call Claude Sonnet 4.5 with maximum output tokens
        3. Parse JSON response
        4. Return extracted references
    OUTPUT: Dict with extracted references or None
    """
    try:
        # Generate prompt
        prompt = generate_extraction_prompt(text, source_jurisdiction, source_region, chunk_info)

        # Log token estimate
        estimated_tokens = estimate_token_count(prompt)
        logging.info(f"  Prompt size: ~{estimated_tokens:,} tokens")

        # Call Gemini Flash-Lite for bulk extraction
        start_time = time.time()
        result = call_gemini(
            prompt,
            model=CONFIG["EXTRACTION_MODEL"],
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )
        extraction_time = time.time() - start_time

        # Parse response
        data = result["data"]
        if not data:
            data = extract_json_from_text(result["text"])

        if not data:
            logging.error(f"Failed to parse extraction JSON for document {document_id}")
            logging.debug(f"Raw response: {result['text'][:1000]}...")
            return None

        # Add metadata
        data["extraction_time"] = extraction_time
        data["tokens_input"] = result["tokens_in"]
        data["tokens_output"] = result["tokens_out"]
        data["model"] = result["model"]

        logging.info(
            f"  Extraction complete: {data.get('total_references_found', 0)} references in {extraction_time:.1f}s"
        )
        logging.info(f"  Tokens: {result['tokens_in']:,} in / {result['tokens_out']:,} out")

        return data

    except Exception as e:
        logging.error(f"Error in extraction: {e}")
        import traceback

        logging.error(traceback.format_exc())
        return None


def deduplicate_citations(all_references: list[dict]) -> list[dict]:
    """
    Remove duplicate citations from combined chunk results.

    INPUT: List of citation dictionaries (potentially with duplicates from overlapping chunks)
    ALGORITHM:
        1. Create signature for each citation (case_name + raw_text)
        2. Keep first occurrence of each unique citation
        3. Return deduplicated list
    OUTPUT: Deduplicated list of citations
    """
    seen_signatures = set()
    unique_references = []

    for ref in all_references:
        # Create signature from case name and raw text
        case_name = ref.get("case_name", "").lower().strip()
        raw_text = ref.get("raw_text", "").lower().strip()[:100]  # Use first 100 chars
        signature = f"{case_name}|{raw_text}"

        if signature not in seen_signatures:
            seen_signatures.add(signature)
            unique_references.append(ref)

    if len(all_references) != len(unique_references):
        logging.info(f"  Deduplication: {len(all_references)} → {len(unique_references)} citations")

    return unique_references


def extract_all_case_references_phase2(
    document_id: uuid.UUID, raw_text: str, source_jurisdiction: str, source_region: str
) -> dict | None:
    """
    Phase 2A: Extract ALL case law references from full document.
    Handles chunking automatically if document is too large.

    INPUT:
        - document_id: UUID of document
        - raw_text: Full document text
        - source_jurisdiction: Source court jurisdiction
        - source_region: Global North/South/International
    ALGORITHM:
        1. Check if document needs chunking
        2. If yes, chunk and process each chunk separately
        3. Merge and deduplicate results
        4. If no, process entire document at once
    OUTPUT: Dict with extracted references or None
    """

    # Log document size
    char_count = len(raw_text)
    estimated_tokens = estimate_token_count(raw_text)
    logging.info(f"  Document size: {char_count:,} chars (~{estimated_tokens:,} tokens)")

    # Check if chunking is needed
    if should_chunk_document(raw_text):
        logging.info(
            f"  Document exceeds safe threshold ({SAFE_CHAR_THRESHOLD:,} chars) - using chunked processing"
        )
        chunks = chunk_document(raw_text)

        all_references = []
        total_tokens_input = 0
        total_tokens_output = 0
        total_time = 0

        for i, (chunk_text, start_pos, end_pos) in enumerate(chunks):
            chunk_info = f"chunk {i + 1} of {len(chunks)} (chars {start_pos:,}-{end_pos:,})"
            logging.info(f"  Processing {chunk_info}...")

            chunk_result = extract_citations_from_text(
                document_id, chunk_text, source_jurisdiction, source_region, chunk_info
            )

            if chunk_result:
                # Adjust citation positions for chunk offset
                for ref in chunk_result.get("case_law_references", []):
                    ref["chunk_number"] = i + 1
                    ref["chunk_offset"] = start_pos

                all_references.extend(chunk_result.get("case_law_references", []))
                total_tokens_input += chunk_result.get("tokens_input", 0)
                total_tokens_output += chunk_result.get("tokens_output", 0)
                total_time += chunk_result.get("extraction_time", 0)

        # Deduplicate citations from overlapping regions
        unique_references = deduplicate_citations(all_references)

        return {
            "case_law_references": unique_references,
            "total_references_found": len(unique_references),
            "extraction_time": total_time,
            "tokens_input": total_tokens_input,
            "tokens_output": total_tokens_output,
            "model": "claude-sonnet-4-5-20250929",
            "chunked": True,
            "chunk_count": len(chunks),
        }

    else:
        # Process entire document at once
        logging.info("  Processing full document (no chunking needed)")
        result = extract_citations_from_text(
            document_id, raw_text, source_jurisdiction, source_region
        )
        if result:
            result["chunked"] = False
            result["chunk_count"] = 1
        return result


# ============================================================================
# PHASE 2B: FUNCTIONAL CLASSIFICATION (SEPARATE PASS)
# ============================================================================


def generate_functional_classification_prompt(
    citations: list[dict], document_text_sample: str, source_jurisdiction: str
) -> str:
    """
    Generate prompt for functional classification of extracted citations.

    INPUT:
        - citations: List of extracted citation dictionaries
        - document_text_sample: Sample of document text for context
        - source_jurisdiction: Source court jurisdiction
    OUTPUT: Prompt string for functional classification
    """

    # Format citations for the prompt
    citations_list = ""
    for i, cit in enumerate(citations[:30]):  # Limit to 30 citations per batch
        citations_list += f"""
{i + 1}. Case: {cit.get("case_name", "Unknown")}
   Citation: {cit.get("raw_text", "")[:200]}
   Context: {cit.get("context_snippet", "")}
"""

    prompt = f"""You are classifying HOW a court used each citation in its judgment.

SOURCE COURT: {source_jurisdiction}

For each citation below, determine:

1. FUNCTIONAL USE:
   - "parties_argument": The court is recounting what a party argued
   - "dismissed": The court REJECTS or distinguishes this citation
   - "contributed": The citation supports the court's own reasoning

2. OPINION TYPE:
   - "majority": Main/majority opinion
   - "dissent": Dissenting opinion
   - "concurrence": Concurring opinion
   - "unclear": Cannot determine

KEY SIGNALS:
- "parties_argument": "submitted", "argued", "contended", "relied on", "appellant/respondent"
- "dismissed": "distinguish", "not applicable", "unlike", "differs from", "little transfer value"
- "contributed": "following", "applying", "as held in", "consistent with", "we adopt"

CITATIONS TO CLASSIFY:
{citations_list}

OUTPUT FORMAT (JSON):
{{
  "classifications": [
    {{
      "citation_index": 1,
      "functional_use": "parties_argument|dismissed|contributed",
      "opinion_type": "majority|dissent|concurrence|unclear",
      "key_signals": ["list", "of", "signals"]
    }}
  ]
}}

If uncertain, use "contributed" with low confidence."""

    return prompt


def classify_citations_functionally(
    citations: list[dict], raw_text: str, source_jurisdiction: str
) -> dict[int, dict]:
    """
    Phase 2B: Classify extracted citations by functional use.

    INPUT:
        - citations: List of extracted citation dictionaries
        - raw_text: Full document text for context
        - source_jurisdiction: Source court jurisdiction
    ALGORITHM:
        1. Generate classification prompt
        2. Call Claude Sonnet 4.5
        3. Parse and return classifications
    OUTPUT: Dict mapping citation index to classification data
    """
    if not citations:
        return {}

    try:
        # Take a sample of the document for context (first 10K chars)
        text_sample = raw_text[:10000]

        # Generate prompt
        prompt = generate_functional_classification_prompt(
            citations, text_sample, source_jurisdiction
        )

        # Call Gemini for functional classification
        result = call_gemini(prompt, model=CONFIG["GEMINI_MODEL"])
        data = result.get("parsed") if result else None

        if not data:
            logging.warning("Failed to parse functional classification JSON")
            return {}

        # Convert to dict indexed by citation_index
        classifications = {}
        for item in data.get("classifications", []):
            idx = item.get("citation_index", 0) - 1  # Convert to 0-indexed
            classifications[idx] = {
                "functional_use": item.get("functional_use", "unknown"),
                "opinion_type": item.get("opinion_type", "unclear"),
                "key_signals": item.get("key_signals", []),
                "reasoning": item.get("reasoning", ""),
            }

        logging.info(f"  Functional classification complete for {len(classifications)} citations")
        return classifications

    except Exception as e:
        logging.warning(f"Error in functional classification: {e}")
        return {}


# ============================================================================
# PHASE 3: ORIGIN IDENTIFICATION (3-TIER APPROACH)
# ============================================================================


def identify_origin_tier1_dictionary(case_name: str, raw_text: str) -> dict | None:
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
                "origin": court_data["country"],
                "region": court_data["region"],
                "court": court_pattern,
                "tier": 1,
                "confidence": 0.95,
                "method": "dictionary_court_match",
            }
            # Cache result
            CITATION_ORIGIN_CACHE[cache_key] = result
            logging.debug(f"Tier 1: Court match for '{case_name}' -> {court_data['country']}")
            return result

    # Search LANDMARK_CLIMATE_CASES
    for case_pattern, case_data in LANDMARK_CLIMATE_CASES.items():
        if case_pattern.lower() in case_name.lower():
            result = {
                "origin": case_data["country"],
                "region": case_data["region"],
                "court": case_data.get("court", "Unknown"),
                "year": case_data.get("year"),
                "tier": 1,
                "confidence": 0.95,
                "method": "dictionary_case_match",
            }
            # Cache result
            CITATION_ORIGIN_CACHE[cache_key] = result
            logging.debug(f"Tier 1: Case match for '{case_name}' -> {case_data['country']}")
            return result

    logging.debug(f"Tier 1: No match for '{case_name}'")
    return None


def identify_origin_tier2_sonnet(case_name: str, raw_text: str) -> dict | None:
    """
    Tier 2: Use Claude Sonnet for intelligent origin identification.

    INPUT:
        - case_name: Extracted case name
        - raw_text: Raw citation text
    ALGORITHM:
        1. Build prompt
        2. Call Claude Sonnet 4.5
        3. Parse origin identification
        4. Return with confidence score
    OUTPUT: Dict with origin data or None
    """
    try:
        prompt = f"""Identify the jurisdiction/country of origin for this legal case citation.

CASE NAME: {case_name}
RAW CITATION: {raw_text}

Analyze ALL available signals:
1. Court name in citation
2. Citation format (e.g., "U.S." suggests United States, "UKSC" suggests UK)
3. Case name patterns
4. Legal system indicators

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

        gemini_result = call_gemini(
            prompt,
            model=CONFIG["GEMINI_MODEL"],
            max_output_tokens=500,
        )

        data = gemini_result["data"]
        if not data:
            data = extract_json_from_text(gemini_result["text"])

        if not data or data.get("confidence", 0) < 0.5:
            logging.debug(f"Tier 2: Low confidence for '{case_name}'")
            return None

        result = {
            "origin": data.get("origin_country"),
            "region": data.get("region"),
            "court": data.get("court"),
            "year": data.get("year"),
            "tier": 2,
            "confidence": data.get("confidence", 0.0),
            "method": "gemini_analysis",
            "reasoning": data.get("reasoning", ""),
        }

        # Cache if high confidence
        if result["confidence"] >= 0.7:
            cache_key = case_name.lower().strip()
            CITATION_ORIGIN_CACHE[cache_key] = result

        logging.debug(
            f"Tier 2: Identified '{case_name}' -> {result['origin']} (confidence: {result['confidence']})"
        )
        return result

    except Exception as e:
        logging.error(f"Error in Tier 2 identification: {e}")
        return None


def identify_origin_tier3_websearch(case_name: str, raw_text: str) -> dict | None:
    """
    Tier 3: Web search for obscure or uncertain cases.

    INPUT:
        - case_name: Extracted case name
        - raw_text: Raw citation text
    OUTPUT: Dict with origin data or None

    integration with search API.
    """
    logging.debug(f"Tier 3: Web search not implemented for '{case_name}'")
    return None


def identify_case_origin(case_name: str, raw_text: str) -> dict:
    """
    Identify origin using 3-tier approach.

    INPUT:
        - case_name: Extracted case name
        - raw_text: Raw citation text
    ALGORITHM:
        Tier 1: Dictionary lookup (fastest)
        Tier 2: LLM Analysis (Sonnet)
        Tier 3: Web Search (fallback - placeholder)
    OUTPUT: Dict with origin, region, confidence, method
    """
    # Tier 1: Dictionary lookup
    tier1_result = identify_origin_tier1_dictionary(case_name, raw_text)
    if tier1_result:
        return tier1_result

    # Tier 2: LLM Analysis
    tier2_result = identify_origin_tier2_sonnet(case_name, raw_text)
    if tier2_result and tier2_result["confidence"] >= 0.5:
        return tier2_result

    # Tier 3: Web search (if implemented)
    tier3_result = identify_origin_tier3_websearch(case_name, raw_text)
    if tier3_result:
        return tier3_result

    # All tiers failed - return unknown
    logging.warning(f"Phase 3: Could not identify origin for '{case_name}'")
    return {
        "origin": "Unknown",
        "region": "Unknown",
        "court": None,
        "year": None,
        "tier": 0,
        "confidence": 0.0,
        "method": "failed_identification",
    }


# ============================================================================
# PHASE 4: CLASSIFICATION
# ============================================================================


def classify_citation_type(
    source_jurisdiction: str, source_region: str, case_origin: str, case_region: str
) -> tuple[str, bool]:
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
        3. Apply classification logic
    OUTPUT: (citation_type, is_cross_jurisdictional)
    """
    # Normalize jurisdictions
    source_norm = normalize_jurisdiction(source_jurisdiction)
    case_norm = normalize_jurisdiction(case_origin)

    # Handle unknowns
    if case_origin == "Unknown" or case_region == "Unknown":
        return "Unknown", False

    # Same jurisdiction = Domestic (NOT cross-jurisdictional)
    if source_norm == case_norm:
        return "Domestic", False

    # Different jurisdictions = Cross-jurisdictional

    # Classification logic
    if source_region == "International" or case_region == "International":
        if source_region == "International" and case_region == "International":
            # Both international
            return "International Citation", True
        elif source_region == "International":
            # Source is international, citing a national case
            return "Foreign Citation", True
        else:
            # Source is national, citing international
            return "International Citation", True

    # Both are national courts (different countries)
    return "Foreign Citation", True


# ============================================================================
# MAIN PROCESSING FUNCTION
# ============================================================================


def process_single_document_phased(doc_tuple, session, stats: dict) -> bool:
    """
    Process a single document through all phases with separation of concerns.

    INPUT:
        - doc_tuple: Database query result tuple
                     (document_id, metadata_data, raw_text, case_id, geographies)
        - session: SQLAlchemy session
        - stats: Statistics dictionary
    ALGORITHM:
        Phase 1: Identify source jurisdiction from Case.geographies
        Phase 2A: Extract ALL case references (pure extraction)
        Phase 2B: Functional classification (separate pass)
        Phase 3: Identify origin for each reference
        Phase 4: Classify each citation
        Save results to database
    OUTPUT: True if successful, False otherwise
    """
    # Unpack query results
    document_id = doc_tuple[0]
    metadata_data = doc_tuple[1]
    raw_text = doc_tuple[2]
    case_id = doc_tuple[3]
    geographies = doc_tuple[4]

    start_time = time.time()
    total_api_calls = 0
    total_tokens_input = 0
    total_tokens_output = 0

    try:
        logging.info(f"\n{'=' * 70}")
        logging.info(f"Processing Document: {document_id}")
        logging.info(f"{'=' * 70}")

        # ====================================================================
        # PHASE 1: SOURCE JURISDICTION
        # ====================================================================
        logging.info("Phase 1: Identifying source jurisdiction...")

        # Fallback to metadata_data if Case.geographies is NULL
        if not geographies and isinstance(metadata_data, dict):
            geographies = metadata_data.get("Geographies", "")
            logging.debug(f"  Case.geographies was NULL, using metadata_data: {geographies}")

        # Extract country from geography string
        source_jurisdiction = extract_country_from_geographies(geographies)
        source_region = get_source_region(source_jurisdiction)

        logging.info(f"  Geography raw: {geographies}")
        logging.info(f"  Source: {source_jurisdiction} ({source_region})")

        # ====================================================================
        # PHASE 2A: PURE EXTRACTION
        # ====================================================================
        logging.info("Phase 2A: Extracting ALL case law references (full document)...")

        phase2a_result = extract_all_case_references_phase2(
            document_id, raw_text, source_jurisdiction, source_region
        )

        if not phase2a_result:
            logging.error("  Phase 2A failed - skipping document")
            stats["phase2_failures"] += 1
            return False

        total_api_calls += phase2a_result.get("chunk_count", 1)
        total_tokens_input += phase2a_result.get("tokens_input", 0)
        total_tokens_output += phase2a_result.get("tokens_output", 0)

        references = phase2a_result.get("case_law_references", [])
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
                total_cost_usd=(total_tokens_input / 1e6 * 3.0)
                + (total_tokens_output / 1e6 * 15.0),
                extraction_started_at=datetime.fromtimestamp(start_time),
                extraction_completed_at=datetime.utcnow(),
                total_processing_time_seconds=time.time() - start_time,
                extraction_success=True,
                average_confidence=0.0,
                items_requiring_review=0,
            )
            session.add(summary)
            session.commit()

            stats["processed"] += 1
            stats["no_citations"] += 1
            return True

        # ====================================================================
        # PHASE 2B: FUNCTIONAL CLASSIFICATION (OPTIONAL SEPARATE PASS)
        # ====================================================================
        logging.info("Phase 2B: Functional classification of citations...")

        functional_classifications = classify_citations_functionally(
            references, raw_text, source_jurisdiction
        )

        if functional_classifications:
            total_api_calls += 1

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

        # Functional classification counters
        functional_parties_count = 0
        functional_dismissed_count = 0
        functional_contributed_count = 0
        majority_count = 0
        dissent_count = 0

        for i, ref in enumerate(references):
            # Phase 3: Identify origin
            origin_data = identify_case_origin(ref.get("case_name", ""), ref.get("raw_text", ""))

            # Track API calls (Tier 2 uses Sonnet)
            if origin_data.get("tier") == 2:
                total_api_calls += 1

            # Phase 4: Classify (Geographic)
            citation_type, is_cross_jurisdictional = classify_citation_type(
                source_jurisdiction, source_region, origin_data["origin"], origin_data["region"]
            )

            # Skip domestic citations
            if citation_type == "Domestic":
                logging.debug(f"  Skipping domestic citation: {ref.get('case_name', 'Unknown')}")
                continue

            # Get functional classification from Phase 2B
            func_class = functional_classifications.get(i, {})
            functional_use = func_class.get("functional_use", "unknown")
            opinion_type = func_class.get("opinion_type", ref.get("location", "unclear"))
            key_signals = func_class.get("key_signals", [])

            # Count by type (geographic)
            if citation_type == "Foreign Citation":
                foreign_count += 1
            elif citation_type == "International Citation":
                international_count += 1
            elif citation_type == "Foreign International Citation":
                foreign_international_count += 1

            # Count by functional use
            if functional_use == "parties_argument":
                functional_parties_count += 1
            elif functional_use == "dismissed":
                functional_dismissed_count += 1
            elif functional_use == "contributed":
                functional_contributed_count += 1

            # Count by opinion type
            if opinion_type == "majority":
                majority_count += 1
            elif opinion_type in ["dissent", "concurrence"]:
                dissent_count += 1

            # Check if needs manual review
            confidence = origin_data.get("confidence", 0.0)
            confidences.append(confidence)
            needs_review = confidence < 0.7
            if needs_review:
                items_for_review += 1

            # Prepare functional metadata for storage
            functional_metadata = {
                "functional_use": functional_use,
                "opinion_type": opinion_type,
                "key_signals": key_signals,
                "v5_3_extraction": True,
            }

            # Create citation record using existing schema fields
            citation_record = CitationExtractionPhased(
                document_id=document_id,
                case_id=case_id,
                # Phase 1
                source_jurisdiction=source_jurisdiction,
                source_region=source_region,
                # Phase 2
                case_name=ref.get("case_name"),
                raw_citation_text=ref.get("raw_text"),
                location_in_document=opinion_type,  # Use for opinion_type
                # Phase 3
                case_law_origin=origin_data["origin"],
                case_law_region=origin_data["region"],
                origin_identification_tier=origin_data["tier"],
                origin_confidence=origin_data["confidence"],
                # Phase 4 - Geographic Classification
                citation_type=citation_type,
                is_cross_jurisdictional=is_cross_jurisdictional,
                # Extended metadata
                cited_court=origin_data.get("court"),
                cited_year=origin_data.get("year"),
                # Processing metadata
                phase_2_model="claude-sonnet-4-5-20250929",
                phase_3_model=origin_data.get("method"),
                phase_4_model="rule-based",
                processing_time_seconds=time.time() - start_time,
                api_calls_used=total_api_calls,
                # Quality control - store functional metadata in manual_review_reason
                requires_manual_review=needs_review,
                manual_review_reason=(
                    f"Low confidence: {confidence:.2f} | FUNC: {json.dumps(functional_metadata)}"
                    if needs_review
                    else f"FUNC: {json.dumps(functional_metadata)}"
                ),
            )

            citation_records.append(citation_record)

        # ====================================================================
        # SAVE TO DATABASE
        # ====================================================================
        logging.info(f"Saving {len(citation_records)} cross-jurisdictional citations...")

        # Calculate totals
        total_cross_jurisdictional = (
            foreign_count + international_count + foreign_international_count
        )
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        # Calculate cost (Sonnet 4.5: $3/M input, $15/M output)
        total_cost = (total_tokens_input / 1e6 * 3.0) + (total_tokens_output / 1e6 * 15.0)

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
            items_requiring_review=items_for_review,
        )

        # Add all records
        session.add(summary)
        for citation in citation_records:
            session.add(citation)

        session.commit()

        # Update statistics
        stats["processed"] += 1
        stats["total_references"] += len(references)
        stats["foreign_citations"] += foreign_count
        stats["international_citations"] += international_count
        stats["foreign_international_citations"] += foreign_international_count
        stats["needs_review"] += items_for_review
        stats["functional_parties"] += functional_parties_count
        stats["functional_dismissed"] += functional_dismissed_count
        stats["functional_contributed"] += functional_contributed_count
        stats["majority_citations"] += majority_count
        stats["dissent_citations"] += dissent_count

        logging.info("✓ Completed successfully:")
        logging.info(f"  Total references: {len(references)}")
        logging.info(f"  Cross-jurisdictional: {total_cross_jurisdictional}")
        logging.info(f"    - Foreign: {foreign_count}")
        logging.info(f"    - International: {international_count}")
        logging.info(f"    - Foreign International: {foreign_international_count}")
        logging.info("  Functional Classification:")
        logging.info(f"    - Parties' argument: {functional_parties_count}")
        logging.info(f"    - Dismissed/Distinguished: {functional_dismissed_count}")
        logging.info(f"    - Contributed to decision: {functional_contributed_count}")
        logging.info("  Opinion Type:")
        logging.info(f"    - Majority: {majority_count}")
        logging.info(f"    - Dissent/Concurrence: {dissent_count}")
        logging.info(f"  Avg confidence: {avg_confidence:.2f}")
        logging.info(f"  Needs review: {items_for_review}")
        logging.info(f"  Cost: ${total_cost:.4f}")

        return True

    except Exception as e:
        session.rollback()
        logging.error(f"Error processing document: {e}")
        import traceback

        logging.error(traceback.format_exc())
        stats["errors"] += 1

        # Create failed summary
        try:
            summary = CitationExtractionPhasedSummary(
                document_id=document_id,
                extraction_started_at=datetime.fromtimestamp(start_time),
                extraction_completed_at=datetime.utcnow(),
                total_processing_time_seconds=time.time() - start_time,
                extraction_success=False,
                extraction_error=str(e)[:500],
            )
            session.add(summary)
            session.commit()
        except Exception as e:
            logging.warning(f"⚠️  Could not save error summary: {e}")

        return False


# ============================================================================
# MAIN EXECUTION
# ============================================================================


def main(test_run=None, seed=42):
    """
    Main execution function.

    INPUT:
        - test_run: number of documents to sample (None = all)
        - seed: random seed for reproducible sampling
    ALGORITHM:
        1. Load trial batch filter (if enabled)
        2. Query documents classified as decisions (is_decision = True)
        3. Filter by trial batch if enabled
        4. Apply test-run sampling
        5. Exclude already processed documents
        6. Process each document through all phases
        7. Report comprehensive statistics
    OUTPUT: Statistics printed to log
    """
    logging.info("=" * 70)
    logging.info("CITATION EXTRACTION v5.3 - FULL TEXT PROCESSING")
    logging.info("Complete Document Analysis with Separation of Concerns")
    logging.info("=" * 70)
    logging.info("Architecture:")
    logging.info("  Phase 1:  Source Jurisdiction Identification")
    logging.info("  Phase 2A: Extract ALL Case References - FULL DOCUMENT (Sonnet 4.5)")
    logging.info("  Phase 2B: Functional Classification (Separate Pass)")
    logging.info("  Phase 3:  Identify Case Origin (3-Tier)")
    logging.info("  Phase 4:  Classify Citation Type (Geographic + Functional)")
    logging.info("=" * 70)
    logging.info("v5.3 Key Features:")
    logging.info("  - FULL document processing (no text truncation)")
    logging.info("  - ALL 12 extraction patterns restored")
    logging.info("  - Separation of concerns: extraction vs. classification")
    logging.info("  - Dynamic chunking for documents > 600K chars")
    logging.info("  - Maximum output tokens (16,384)")
    logging.info("  - Uses existing database schema (no reset required)")
    logging.info("=" * 70)

    # Get trial batch filter
    trial_batch_uuids = get_trial_batch_document_uuids()

    # Connect to database
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    # Ensure tables exist
    Base.metadata.create_all(engine)
    logging.info("✓ Database tables verified/created")

    try:
        # Query documents that are DECISIONS with extracted text
        logging.info("\nQuerying documents classified as decisions...")

        query = (
            session.query(
                Document.document_id,
                Document.metadata_data,
                ExtractedText.raw_text,
                Case.case_id,
                Case.geographies,
            )
            .join(ExtractedText, Document.document_id == ExtractedText.document_id)
            .join(Case, Document.case_id == Case.case_id)
            .filter(ExtractedText.raw_text.isnot(None), Document.is_decision.is_(True))
        )

        # Count total decisions
        total_decisions = query.count()
        logging.info(f"Found {total_decisions} documents classified as decisions")

        # Filter by trial batch if enabled
        if trial_batch_uuids is not None:
            query = query.filter(Document.document_id.in_(trial_batch_uuids))
            trial_filtered_count = query.count()
            logging.info(f"After trial batch filter: {trial_filtered_count} documents")

        # Apply test-run sampling: filter query to sampled document UUIDs
        if test_run is not None:
            df = pd.read_excel(DATABASE_FILE)
            test_run_uuids = get_sampled_document_uuids(df, test_run, seed)
            if test_run_uuids is not None:
                query = query.filter(Document.document_id.in_(test_run_uuids))
                logging.info(f"After test-run filter: {query.count()} documents")

        # Exclude already processed (single-level NOT IN subquery)
        query = query.filter(~Document.document_id.in_(
            session.query(CitationExtractionPhasedSummary.document_id)
        ))
        excluded_count = session.query(CitationExtractionPhasedSummary.document_id).count()
        if excluded_count:
            logging.info(f"Excluding {excluded_count} already processed documents")

        # Stream results instead of materializing all at once
        total_to_process = query.count()
        logging.info(f"\n✓ Documents to process: {total_to_process}")
        documents = query.yield_per(50)

        if total_to_process == 0:
            logging.warning("\n⚠️  No documents to process!")
            logging.info("\nPossible reasons:")
            logging.info("1. All decisions have already been processed")
            logging.info("2. No documents have been classified yet")
            logging.info("3. Trial batch filter excluded all documents")
            return

        # Initialize statistics
        stats = {
            "processed": 0,
            "total_references": 0,
            "foreign_citations": 0,
            "international_citations": 0,
            "foreign_international_citations": 0,
            "needs_review": 0,
            "phase2_failures": 0,
            "no_citations": 0,
            "errors": 0,
            # Functional classification stats
            "functional_parties": 0,
            "functional_dismissed": 0,
            "functional_contributed": 0,
            "majority_citations": 0,
            "dissent_citations": 0,
        }

        # Process each document
        logging.info("\n" + "=" * 70)
        logging.info("STARTING FULL-TEXT EXTRACTION")
        logging.info("=" * 70)

        for i, doc in enumerate(
            tqdm(documents, total=total_to_process, desc="Processing Documents")
        ):
            process_single_document_phased(doc, session, stats)
            if (i + 1) % 100 == 0:
                session.expunge_all()  # Detach cached objects to free memory

        # Report final statistics
        logging.info("\n" + "=" * 70)
        logging.info("EXTRACTION COMPLETE - FINAL STATISTICS (v5.3)")
        logging.info("=" * 70)
        logging.info(f"Total decisions in database:     {total_decisions}")
        logging.info(f"Documents processed:             {stats['processed']}")
        logging.info(f"Documents with no citations:     {stats['no_citations']}")
        logging.info(f"Phase 2 failures:                {stats['phase2_failures']}")
        logging.info(f"Other errors:                    {stats['errors']}")
        logging.info("")
        logging.info("GEOGRAPHIC CLASSIFICATION:")
        logging.info(f"Total references extracted:      {stats['total_references']}")
        logging.info(f"Foreign Citations:               {stats['foreign_citations']}")
        logging.info(f"International Citations:         {stats['international_citations']}")
        logging.info(f"Foreign International Citations: {stats['foreign_international_citations']}")
        logging.info(
            f"Total cross-jurisdictional:      {stats['foreign_citations'] + stats['international_citations'] + stats['foreign_international_citations']}"
        )
        logging.info("")
        logging.info("FUNCTIONAL CLASSIFICATION:")
        logging.info(f"  Reference to parties' arguments: {stats['functional_parties']}")
        logging.info(f"  Dismissed/Distinguished:         {stats['functional_dismissed']}")
        logging.info(f"  Contributed to decision:         {stats['functional_contributed']}")
        logging.info("")
        logging.info("OPINION TYPE BREAKDOWN:")
        logging.info(f"  Majority opinion citations:      {stats['majority_citations']}")
        logging.info(f"  Dissent/Concurrence citations:   {stats['dissent_citations']}")
        logging.info("")
        logging.info(f"Items requiring manual review:   {stats['needs_review']}")

        if TRIAL_BATCH_CONFIG["ENABLED"]:
            logging.info("\n✓ Trial batch mode was ENABLED")

        # Query final database statistics
        total_in_db = session.query(CitationExtractionPhased).count()
        logging.info(f"\n✓ Total citations in database:   {total_in_db}")

        logging.info("=" * 70)
        logging.info("Cache Statistics:")
        logging.info(f"Cache size: {len(CITATION_ORIGIN_CACHE)} entries")
        logging.info("=" * 70)

    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract citations from judicial decisions")
    add_test_run_arg(parser)
    args = parser.parse_args()

    main(test_run=args.test_run, seed=args.seed)
