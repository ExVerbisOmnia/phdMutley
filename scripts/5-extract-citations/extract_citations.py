#!/usr/bin/env python3
"""
Citation Extraction Script - Version 7.0 (Anti-Hallucination Pipeline)
=======================================================================
Full-text extraction with KB-removed prompt, hard filters, and inline verification.

🏃 Run from: project root
Command: python scripts/5-extract-citations/extract_citations.py

VERSION 7.0 - ANTI-HALLUCINATION PIPELINE
==========================================

Pipeline phases:
  Phase 0:  Document quality pre-check (garbled/too-long detection)
  Phase 1:  Source Jurisdiction Identification
  Phase 2A: Extract ALL case references (Gemini 2.5 Flash, thinking=1024)
  Phase 2A+: Hard filters (pipe-format, anachronism detection)
  Phase 2A+: Sabin Filter (keep only KB-matched citations)
  Phase 2A+: Snippet Extraction (locate citations in document text)
  Phase 2B: Functional Classification (Gemini 2.5 Flash, thinking=2048)
  Phase 3:  Identify case origin (3-Tier: Dictionary > Gemini > Web)
  Phase 4:  Classify citation type (Geographic + Functional)
  Phase 5:  Inline verification (Gemini 2.5 Flash, thinking=1024)

REQUIREMENTS:
- Documents must be classified first (is_decision = True)
- Database tables: citation_extraction_phased, citation_extraction_phased_summary
- NO DATABASE RESET REQUIRED - uses existing schema

Author: Lucas Biasetton & Claude
Project: Doutorado PM
Version: 7.0
Date: March 2026
"""

import asyncio
import json
import logging
import os
import re
import signal
import sys
import time
import uuid
from datetime import datetime, timezone

import pandas as pd

# Database
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

# ============================================================================
# CONFIGURATION & IMPORTS
# ============================================================================

_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _SCRIPTS_DIR)
from config import CONFIG, DATABASE_FILE, LOGS_DIR, TRIAL_BATCH_CONFIG
from gcp_secrets import get_engine
from gemini_client import call_gemini, call_gemini_async
from test_run import add_test_run_arg, get_sampled_document_ids

# v6 Knowledge Base modules
from build_knowledge_base import load_knowledge_base
from extraction_prompt_v6 import generate_v6_extraction_prompt
from sabin_filter import SabinFilter
from snippet_extractor import extract_snippets_batch

# v7 Quality & Verification modules
from text_quality import is_garbled_text, is_too_long
from citation_verification import verify_document_citations_inline

sys.path.insert(0, os.path.join(_SCRIPTS_DIR, "0-initialize-database"))

# ============================================================================
# SQLALCHEMY MODELS FOR NEW TABLES
# ============================================================================
# Import Base and citation tables from init_database to avoid duplication
from init_database import (
    Base,
    Case,
    CitationExtractionDiscarded,
    CitationExtractionPhased,
    CitationExtractionPhasedSummary,
    Document,
    ExtractedText,
)

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

_log_format = "%(asctime)s - %(levelname)s - %(message)s"
_file_handler = logging.FileHandler(LOGS_DIR / "citation_extraction_v5_3.log", encoding="utf-8")
_file_handler.setFormatter(logging.Formatter(_log_format))
_stream_handler = logging.StreamHandler(
    open(sys.stdout.fileno(), mode="w", encoding="utf-8", errors="replace", closefd=False)  # noqa: SIM115
)
_stream_handler.setFormatter(logging.Formatter(_log_format))
logging.basicConfig(level=logging.INFO, handlers=[_file_handler, _stream_handler], force=True)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("google.genai").setLevel(logging.WARNING)

# ============================================================================
# v6 KNOWLEDGE BASE STATE (initialized in main())
# ============================================================================

_kb_cases: list[dict] | None = None  # Loaded once in main()
_sabin_filter: SabinFilter | None = None  # Initialized once in main()
_extraction_run_id: str | None = None  # Set once per run in main()
_shutdown_requested = False  # Graceful shutdown flag for concurrent mode


# ============================================================================
# POST-EXTRACTION HARD FILTERS (anti-hallucination, Step 1D.1)
# ============================================================================


def is_pipe_format(raw_text: str) -> bool:
    """
    Detect Sabin metadata format: 'Case Name (Year) | Court; Jurisdiction'.
    Citations with this format are KB contamination, not real citations.
    """
    if not raw_text:
        return False
    return bool('|' in raw_text and re.search(r'\(\d{4}\)\s*\|', raw_text))


def is_anachronistic(cited_year, document_year) -> bool:
    """
    Detect citations to cases that didn't exist when the document was written.
    +1 year tolerance for cases decided near year boundary.
    """
    if cited_year and document_year:
        try:
            return int(cited_year) > int(document_year) + 1
        except (ValueError, TypeError):
            return False
    return False


def apply_hard_filters(references: list[dict], document_year: int | None = None) -> tuple[list[dict], list[dict]]:
    """
    Apply post-extraction hard filters to remove hallucinated citations.

    INPUT:
        - references: List of extracted citation dicts
        - document_year: Year of the source document
    OUTPUT: (kept, discarded) — both lists of citation dicts
        Discarded items have 'discard_reason' added.
    """
    kept = []
    discarded = []

    for ref in references:
        raw_text = ref.get("raw_text", ref.get("raw_citation_text", ""))

        # Filter 1: Pipe-format metadata contamination
        if is_pipe_format(raw_text):
            ref["discard_reason"] = "pipe_format_metadata"
            discarded.append(ref)
            continue

        # Filter 2: Anachronistic citation
        cited_year = ref.get("cited_year") or _extract_year_from_text(raw_text)
        if document_year and cited_year and is_anachronistic(cited_year, document_year):
            ref["discard_reason"] = f"anachronistic_{cited_year}_from_{document_year}"
            discarded.append(ref)
            continue

        kept.append(ref)

    return kept, discarded


def _extract_year_from_text(text: str) -> int | None:
    """Extract a 4-digit year from citation text, preferring years in parentheses."""
    if not text:
        return None
    # Prefer years in parentheses like (2015) or [2015]
    m = re.search(r'[\(\[]((?:19|20)\d{2})[\)\]]', text)
    if m:
        return int(m.group(1))
    # Fallback: any 4-digit year
    m = re.search(r'\b((?:19|20)\d{2})\b', text)
    if m:
        return int(m.group(1))
    return None


# ============================================================================
# PROCESSING CONFIGURATION
# ============================================================================

# Token estimation: ~1 token per 4 characters (conservative estimate for legal text)
CHARS_PER_TOKEN = 4

# Chunking: documents above this token threshold are split into chunks for extraction.
# Each chunk gets its own LLM call; results are merged and deduplicated.
# 40K tokens ≈ 160K chars. Documents below this are sent as a single prompt.
CHUNK_TOKEN_THRESHOLD = 40_000
CHUNK_TARGET_TOKENS = 30_000  # target size per chunk (with ~1K token prompt overhead)
CHUNK_OVERLAP_TOKENS = 2_000  # overlap between chunks to catch citations at boundaries

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
    # AUSTRALIA
    "Federal Court of Australia": {
        "country": "Australia",
        "region": "Global North",
        "type": "Federal",
    },
    "FCA": {"country": "Australia", "region": "Global North", "type": "Federal", "ambiguous_for": ["Canada"]},
    "Full Federal Court": {"country": "Australia", "region": "Global North", "type": "Federal"},
    "Land and Environment Court": {
        "country": "Australia",
        "region": "Global North",
        "type": "Specialist",
    },
    # LATIN AMERICA (native-language names)
    "Corte Constitucional": {
        "country": "Colombia",
        "region": "Global South",
        "type": "Constitutional",
    },
    "Corte Suprema de Justicia": {
        "country": "Colombia",
        "region": "Global South",
        "type": "Supreme",
    },
    "Consejo de Estado": {
        "country": "Colombia",
        "region": "Global South",
        "type": "Administrative",
    },
    "Supremo Tribunal Federal": {
        "country": "Brazil",
        "region": "Global South",
        "type": "Supreme",
    },
    "STF": {"country": "Brazil", "region": "Global South", "type": "Supreme"},
    "Superior Tribunal de Justica": {
        "country": "Brazil",
        "region": "Global South",
        "type": "Superior",
    },
    "STJ": {"country": "Brazil", "region": "Global South", "type": "Superior"},
    "Tribunal Regional Federal": {
        "country": "Brazil",
        "region": "Global South",
        "type": "Federal Regional",
    },
    "TRF": {"country": "Brazil", "region": "Global South", "type": "Federal Regional"},
    "Corte Suprema de Justicia de la Nacion": {
        "country": "Argentina",
        "region": "Global South",
        "type": "Supreme",
    },
    "Tribunal Constitucional": {
        "country": "Chile",
        "region": "Global South",
        "type": "Constitutional",
    },
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
    "Turkey": "T\u00fcrkiye",
    "Turkiye": "T\u00fcrkiye",
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


def get_trial_batch_document_ids() -> set[str] | None:
    """
    Load Excel file and return set of Document IDs (sabin_document_id) in trial batch.

    INPUT: None (reads from config)
    ALGORITHM:
        1. Check if trial batch mode enabled
        2. Load Excel database
        3. Filter rows with TRUE in trial batch column
        4. Return set of string Document IDs
    OUTPUT: Set of string IDs or None
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

        doc_ids = set(trial_batch_df["Document ID"].astype(str))

        logging.info("=" * 70)
        logging.info("TRIAL BATCH FILTERING")
        logging.info("=" * 70)
        logging.info(f"Total documents in database:  {len(df)}")
        logging.info(f"Trial batch documents:        {len(doc_ids)}")
        logging.info("=" * 70)

        return doc_ids

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
    text: str, source_jurisdiction: str, source_region: str
) -> str:
    """
    Generate comprehensive extraction prompt for Phase 2A.

    KEY PRINCIPLE: Extract EVERYTHING - no filtering, no classification.
    FOCUS: Maximum recall of case law references.

    INPUT:
        - text: Full document text
        - source_jurisdiction: Where the citing court is located
        - source_region: Global North/South/International
    OUTPUT: Complete prompt string
    """

    prompt = f"""You are extracting ALL legal references from a judicial decision document.
Your ONLY task is EXTRACTION — identify and extract every reference.

SOURCE COURT INFORMATION:
- Jurisdiction: {source_jurisdiction}
- Region: {source_region}

============================================================
CRITICAL INSTRUCTIONS:
============================================================
1. Extract EVERY reference to case law (judicial decisions), regardless of domestic or foreign origin
2. Do NOT filter by jurisdiction — extract everything
4. Do NOT classify how citations are used — just extract them
5. Be EXHAUSTIVE — capture every mention of any case, court ruling, judicial decision, or treaty
6. Read the ENTIRE document text carefully — do not skip any sections
7. Do NOT extract academic articles, books, or author names (e.g., "Hogg", "Bowden & Olszynski")
8. Do NOT extract treaties, conventions, statutes, legislation, or procedural rules (e.g., Paris Agreement, UNFCCC, Clean Air Act, Resource Management Act, CPR rules, Federal Rules of Civil Procedure). Only extract JUDICIAL DECISIONS (cases decided by courts or tribunals).
9. For raw_text: copy the COMPLETE citation text VERBATIM as it appears in the document — this is critical for manual review

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
      "case_name": "case name (e.g., 'Urgenda Foundation v. State of the Netherlands')",
      "raw_text": "VERBATIM citation text — copy the COMPLETE sentence or passage where this reference appears, exactly as written in the document, preserving original language, punctuation, and formatting",
      "confidence": 0.0-1.0
    }}
  ],
  "total_references_found": number,
  "extraction_notes": "any notes about the extraction process"
}}

FIELD INSTRUCTIONS:
- "case_name": The name of the case being cited
- "raw_text": The FULL verbatim passage from the document containing the citation — include enough surrounding text to show context (the sentence or clause where the reference appears). This must be copied EXACTLY from the source text, ipsis litteris.
- "confidence": How confident you are this is a genuine judicial decision reference (0.0-1.0)

============================================================
IMPORTANT REMINDERS:
============================================================
- Extract EVERY judicial decision reference (case law only — no treaties, statutes, or legislation)
- Do NOT skip any sections of the document
- Include citations even if you're uncertain about the format
- Better to over-extract than to miss citations
- Your job is ONLY extraction — classification comes later
- Do NOT generate fabricated or hallucinated citations — only extract what actually appears in the text
- The raw_text field is used for manual review — it MUST be a verbatim copy from the document

Document text:
{text}"""

    return prompt


def extract_citations_from_text(
    document_id: uuid.UUID,
    text: str,
    source_jurisdiction: str,
    source_region: str,
) -> dict | None:
    """
    Phase 2A: Extract ALL case law references using Gemini.

    No max_output_tokens or response_mime_type — let the model finish naturally.
    The JSON parser handles markdown fences. Retries once on parse failure.

    INPUT:
        - document_id: UUID of document
        - text: Full document text
        - source_jurisdiction: Source court jurisdiction
        - source_region: Global North/South/International
    OUTPUT: Dict with extracted references or None
    """
    try:
        prompt = generate_v6_extraction_prompt(
            text, source_jurisdiction, source_region, kb_cases=_kb_cases
        )

        estimated_tokens = estimate_token_count(prompt)
        logging.info(f"  Prompt size: ~{estimated_tokens:,} tokens")

        start_time = time.time()
        result = call_gemini(prompt, model=CONFIG["EXTRACTION_MODEL"])
        extraction_time = time.time() - start_time

        # Parse response (handles markdown fences via _extract_json in gemini_client)
        data = result["data"]
        if not data:
            data = extract_json_from_text(result["text"])

        # LLM sometimes wraps response in a list
        if isinstance(data, list) and len(data) > 0:
            data = data[0]

        if not data or not isinstance(data, dict):
            raw_text_snippet = result.get("text", "")[:500]
            logging.error(f"Failed to parse extraction JSON for document {document_id}")
            logging.info(f"Raw response (first 500 chars): {raw_text_snippet}")
            logging.info("Retrying extraction...")
            retry_result = call_gemini(prompt, model=CONFIG["EXTRACTION_MODEL"])
            data = retry_result["data"] if retry_result else None
            if isinstance(data, list) and len(data) > 0:
                data = data[0]
            if not data or not isinstance(data, dict):
                data = extract_json_from_text(retry_result["text"]) if retry_result else None
            if not data:
                logging.error(f"Retry also failed for document {document_id}")
                return None

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



def _split_into_chunks(text: str) -> list[str]:
    """
    Split document text into overlapping chunks by paragraph boundaries.

    INPUT: Full document text
    ALGORITHM:
        1. Split text into paragraphs (double newline or single newline)
        2. Accumulate paragraphs until target chunk size is reached
        3. Add overlap from previous chunk's tail paragraphs
    OUTPUT: List of text chunks
    """
    target_chars = CHUNK_TARGET_TOKENS * CHARS_PER_TOKEN
    overlap_chars = CHUNK_OVERLAP_TOKENS * CHARS_PER_TOKEN

    # Split on paragraph boundaries (prefer double newline, fall back to single)
    paragraphs = re.split(r'\n\s*\n', text)
    if len(paragraphs) < 3:
        paragraphs = text.split('\n')

    chunks = []
    current_paras = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para)
        if current_len + para_len > target_chars and current_paras:
            chunks.append('\n\n'.join(current_paras))
            # Build overlap from tail of current chunk
            overlap_paras = []
            overlap_len = 0
            for p in reversed(current_paras):
                if overlap_len + len(p) > overlap_chars:
                    break
                overlap_paras.insert(0, p)
                overlap_len += len(p)
            current_paras = overlap_paras
            current_len = overlap_len

        current_paras.append(para)
        current_len += para_len

    if current_paras:
        chunks.append('\n\n'.join(current_paras))

    return chunks


def _deduplicate_references(references: list[dict]) -> list[dict]:
    """
    Remove duplicate citations extracted from overlapping chunks.

    INPUT: List of citation dicts (may contain duplicates from chunk overlaps)
    ALGORITHM: Deduplicate by normalized case_name. On collision, keep the
               entry with the longer raw_text (more context).
    OUTPUT: Deduplicated list
    """
    seen = {}
    for ref in references:
        key = ref.get("case_name", "").strip().lower()
        raw = ref.get("raw_text", "")
        if key not in seen or len(raw) > len(seen[key].get("raw_text", "")):
            seen[key] = ref
    return list(seen.values())


def extract_all_case_references_phase2(
    document_id: uuid.UUID, raw_text: str, source_jurisdiction: str, source_region: str
) -> dict | None:
    """
    Phase 2A: Extract ALL case law references from full document.

    For small documents (< CHUNK_TOKEN_THRESHOLD), sends the full text in one call.
    For large documents, splits into overlapping chunks, extracts from each, then
    merges and deduplicates results. All citations map to the same document_id.

    INPUT:
        - document_id: UUID of document
        - raw_text: Full document text
        - source_jurisdiction: Source court jurisdiction
        - source_region: Global North/South/International
    OUTPUT: Dict with extracted references or None
    """
    char_count = len(raw_text)
    estimated_tokens = estimate_token_count(raw_text)
    logging.info(f"  Document size: {char_count:,} chars (~{estimated_tokens:,} tokens)")

    # Small document — single call (original path)
    if estimated_tokens <= CHUNK_TOKEN_THRESHOLD:
        result = extract_citations_from_text(
            document_id, raw_text, source_jurisdiction, source_region
        )
        return result

    # Large document — chunked extraction
    chunks = _split_into_chunks(raw_text)
    logging.info(f"  Document exceeds {CHUNK_TOKEN_THRESHOLD:,} tokens — splitting into {len(chunks)} chunks")

    all_references = []
    total_tokens_in = 0
    total_tokens_out = 0
    total_time = 0.0
    model_used = None
    chunk_failures = 0

    for i, chunk in enumerate(chunks):
        chunk_tokens = estimate_token_count(chunk)
        logging.info(f"  Chunk {i + 1}/{len(chunks)}: ~{chunk_tokens:,} tokens")

        result = extract_citations_from_text(
            document_id, chunk, source_jurisdiction, source_region
        )

        if result:
            refs = result.get("case_law_references", [])
            all_references.extend(refs)
            total_tokens_in += result.get("tokens_input", 0)
            total_tokens_out += result.get("tokens_output", 0)
            total_time += result.get("extraction_time", 0.0)
            model_used = result.get("model", model_used)
            logging.info(f"  Chunk {i + 1}: {len(refs)} references extracted")
        else:
            chunk_failures += 1
            logging.warning(f"  Chunk {i + 1}: extraction failed")

    if not all_references and chunk_failures == len(chunks):
        logging.error(f"  All {len(chunks)} chunks failed for document {document_id}")
        return None

    # Deduplicate citations from overlapping chunks
    before_dedup = len(all_references)
    all_references = _deduplicate_references(all_references)
    if before_dedup > len(all_references):
        logging.info(
            f"  Deduplication: {before_dedup} → {len(all_references)} "
            f"({before_dedup - len(all_references)} duplicates removed)"
        )

    return {
        "case_law_references": all_references,
        "total_references_found": len(all_references),
        "extraction_notes": f"Chunked extraction: {len(chunks)} chunks, {chunk_failures} failures",
        "extraction_time": total_time,
        "tokens_input": total_tokens_in,
        "tokens_output": total_tokens_out,
        "model": model_used,
        "chunk_count": len(chunks),
    }


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
        1. Split citations into batches of 30
        2. Generate classification prompt per batch
        3. Call Gemini per batch
        4. Merge and return all classifications
    OUTPUT: Dict mapping citation index to classification data
    """
    if not citations:
        return {}

    BATCH_SIZE = 30
    all_classifications = {}

    try:
        text_sample = raw_text

        for batch_start in range(0, len(citations), BATCH_SIZE):
            batch = citations[batch_start : batch_start + BATCH_SIZE]

            prompt = generate_functional_classification_prompt(
                batch, text_sample, source_jurisdiction
            )

            result = call_gemini(prompt, model=CONFIG["EXTRACTION_MODEL"])
            data = result.get("data") if result else None

            # Fallback: local JSON extractor (handles markdown fences)
            if not data and result:
                data = extract_json_from_text(result["text"])

            # Retry once (matching Phase 2A pattern)
            if not data:
                batch_num = batch_start // BATCH_SIZE + 1
                raw_snippet = (result.get("text", "")[:300] if result else "no response")
                logging.warning(f"Failed to parse functional classification JSON (batch {batch_num}) - retrying...")
                logging.info(f"  Initial raw response (first 300 chars): {raw_snippet}")
                retry_result = call_gemini(prompt, model=CONFIG["EXTRACTION_MODEL"])
                data = retry_result.get("data") if retry_result else None
                if not data and retry_result:
                    data = extract_json_from_text(retry_result["text"])
                if not data:
                    raw_snippet = (retry_result.get("text", "")[:300] if retry_result else "no response")
                    logging.warning(f"Retry also failed for functional classification batch {batch_num}")
                    logging.info(f"  Raw response (first 300 chars): {raw_snippet}")
                    continue

            # LLM sometimes wraps response in a list
            if isinstance(data, list) and len(data) > 0:
                data = data[0]

            for item in data.get("classifications", []) if isinstance(data, dict) else []:
                # citation_index is 1-based within the batch
                batch_idx = item.get("citation_index", 0) - 1
                global_idx = batch_start + batch_idx
                all_classifications[global_idx] = {
                    "functional_use": item.get("functional_use", "unknown"),
                    "opinion_type": item.get("opinion_type", "unclear"),
                    "key_signals": item.get("key_signals", []),
                    "reasoning": item.get("reasoning", ""),
                }

        logging.info(f"  Functional classification complete for {len(all_classifications)} citations")
        return all_classifications

    except Exception as e:
        logging.warning(f"Error in functional classification: {e}")
        return all_classifications


# ============================================================================
# PHASE 3: ORIGIN IDENTIFICATION (3-TIER APPROACH)
# ============================================================================


def identify_origin_tier1_dictionary(
    case_name: str, raw_text: str, source_jurisdiction: str = ""
) -> dict | None:
    """
    Tier 1: Lookup in KNOWN_FOREIGN_COURTS dictionary.

    INPUT:
        - case_name: Extracted case name
        - raw_text: Raw citation text
        - source_jurisdiction: Where the citing court is located (for ambiguity checks)
    ALGORITHM:
        1. Check cache first
        2. Search KNOWN_FOREIGN_COURTS for court name match
        3. Skip entries marked ambiguous for the source jurisdiction
    OUTPUT: Dict with origin data or None
    """
    # Check cache
    cache_key = case_name.lower().strip()
    if cache_key in CITATION_ORIGIN_CACHE:
        logging.debug(f"Tier 1: Cache hit for '{case_name}'")
        return CITATION_ORIGIN_CACHE[cache_key]

    # Search KNOWN_FOREIGN_COURTS (word-boundary match to prevent substring collisions)
    for court_pattern, court_data in KNOWN_FOREIGN_COURTS.items():
        # Skip abbreviations that are ambiguous for the source jurisdiction
        # (e.g., "FCA" means Federal Court of Australia, but also Federal Court of Appeal in Canada)
        ambiguous_for = court_data.get("ambiguous_for", [])
        if source_jurisdiction and source_jurisdiction in ambiguous_for:
            continue

        pattern_re = rf'\b{re.escape(court_pattern)}\b'
        if re.search(pattern_re, raw_text, re.IGNORECASE) or re.search(pattern_re, case_name, re.IGNORECASE):
            result = {
                "origin": court_data["country"],
                "region": court_data["region"],
                "court": court_pattern,
                "tier": 1,
                "confidence": 0.95,
                "method": "dictionary_court_match",
            }
            CITATION_ORIGIN_CACHE[cache_key] = result
            logging.debug(f"Tier 1: Court match for '{case_name}' -> {court_data['country']}")
            return result

    logging.debug(f"Tier 1: No match for '{case_name}'")
    return None


def identify_origin_tier2_sonnet(case_name: str, raw_text: str, source_jurisdiction: str = "") -> dict | None:
    """
    Tier 2: Use Gemini for intelligent origin identification.

    INPUT:
        - case_name: Extracted case name
        - raw_text: Raw citation text
    ALGORITHM:
        1. Build prompt
        2. Call Gemini
        3. Parse origin identification
        4. Return with confidence score
    OUTPUT: Dict with origin data or None
    """
    try:
        source_context = (
            f"\nSOURCE COURT JURISDICTION: {source_jurisdiction}\n"
            f"(The citing court is from {source_jurisdiction}. The citation may be domestic or foreign.)\n"
            if source_jurisdiction
            else ""
        )

        prompt = f"""Identify the jurisdiction/country of origin for this legal case citation.

CASE NAME: {case_name}
RAW CITATION: {raw_text}
{source_context}
ANALYSIS RULES:
1. Identify the court from the citation text (including non-English court names)
2. Use citation format clues (e.g., "U.S." = United States, "UKSC" = UK, "[2014] FCA" = Australia, "ECLI:NL" = Netherlands)
3. Analyze case name patterns and language for origin signals
4. "Reference re ..." citations in Canadian documents are Canadian constitutional references
5. If you cannot confidently determine the origin, set confidence below 0.5

Respond in JSON:
{{
  "origin_country": "country name",
  "region": "Global North|Global South|International",
  "court": "court name if identifiable",
  "year": year if mentioned,
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}}

Analyze the citation objectively. Do NOT assume domestic origin by default."""

        gemini_result = call_gemini(
            prompt,
            model=CONFIG["EXTRACTION_MODEL"],
            max_output_tokens=500,
        )

        data = gemini_result["data"]
        if not data:
            data = extract_json_from_text(gemini_result["text"])

        # LLM sometimes wraps response in a list
        if isinstance(data, list) and len(data) > 0:
            data = data[0]

        if not data or not isinstance(data, dict) or data.get("confidence", 0) < 0.5:
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


def _is_likely_domestic(
    case_name: str, raw_text: str, source_jurisdiction: str
) -> bool:
    """
    Heuristic check: is this citation likely from the source jurisdiction?

    Only matches country-specific citation FORMAT patterns (reporter names,
    case numbering conventions). Does NOT match on country name alone, as
    international court cases often name countries as parties (e.g.,
    "Estonia v. X" at the ECtHR is NOT a domestic Estonian case).
    """
    combined = f"{case_name} {raw_text}".lower()
    src = source_jurisdiction.lower()

    # Country-specific citation format patterns
    DOMESTIC_PATTERNS = {
        "colombia": [
            r"\b[TCcSs][Uu]?-\d{2,4}\b",  # T-300, SU-217, C-035
            r"\bsentencia\b",
            r"\btutela\b",
        ],
        "brazil": [
            r"\b(?:AC|RE|ADI|ADPF|HC|MS|AgR)\s*\d",  # Brazilian case types
            r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b",  # CNJ numbering
            r"\bTRF\b",
            r"\bSTF\b",
            r"\bSTJ\b",
        ],
        "australia": [
            r"\[\d{4}\]\s*(?:FCA|HCA|FCAFC|NSWLEC|VSC|QSC)\b",  # Medium neutral citations
            r"\bFCR\b",
            r"\bALR\b",
            r"\bCLR\b",
        ],
        "united states": [
            r"\b\d+\s*(?:U\.S\.|S\.Ct\.|F\.\d[a-z]*|F\.Supp|L\.Ed)\b",
            r"\b\d+\s*(?:Cal\.|N\.Y\.|Ill\.|Tex\.|Fla\.)\s",
        ],
        "united kingdom": [
            r"\[\d{4}\]\s*(?:UKSC|UKHL|EWCA|EWHC|UKPC)\b",
        ],
        "new zealand": [
            r"\[\d{4}\]\s*(?:NZSC|NZCA|NZHC)\b",
        ],
        "canada": [
            r"\[\d{4}\]\s*(?:SCC|SCR|FC|FCA|ABCA|BCCA|BCSC|ONCA|ONSC|QCCA|MBCA|SKCA|NSCA|NBCA|NLCA|PECA|YTCA|NTCA|NUCA)\b",
            r"\b\d+\s*(?:SCR|DLR|OR|WWR|CCC|CR)\b",  # Canadian reporters
            r"\bSCC?\s+\d",  # SCC 12, SC 2019
            r"\bReference\s+re\b",  # Constitutional references
        ],
        "germany": [
            r"\bBVerfG\b",
            r"\bBGH\b",
            r"\bBundesverfassungsgericht\b",
        ],
        "france": [
            r"\bConseil\s+d'[EÉ]tat\b",
            r"\bConseil\s+[Cc]onstitutionnel\b",
            r"\bCour\s+de\s+[Cc]assation\b",
        ],
        "india": [
            r"\bAIR\s+\d{4}\b",  # All India Reporter
            r"\bSCC\b",
        ],
        "south africa": [
            r"\[\d{4}\]\s*(?:ZACC|ZASCA|ZAGP|ZAWCHC|ZAKZDHC|ZAECGHC|ZALMPPHC|ZANWHC|ZAFSHC|ZAECMHC)\b",
            r"\b\d+\s*(?:SA|BCLR|SACR|SALR)\s",  # South African reporters
            r"\b(?:Pty|NPC)\s*\)?\s*Ltd\b",  # SA corporate entities in case names
            r"\bMinister of\s+(?:Mineral Resources|Environmental Affairs|Water)\b",
        ],
        "netherlands": [
            r"\bECLI:NL\b",
            r"\bRechtbank\b",
            r"\bHoge\s+Raad\b",
        ],
        "t\u00fcrkiye": [
            r"\bDan\u0131\u015ftay\b",  # Council of State (Danıştay)
            r"\bAnayasa\s+Mahkemesi\b",  # Constitutional Court
            r"\bYarg\u0131tay\b",  # Court of Cassation
            r"\bE:\d{4}/\d+",  # Turkish case numbering
        ],
        "turkey": [
            r"\bDan\u0131\u015ftay\b",
            r"\bAnayasa\s+Mahkemesi\b",
            r"\bYarg\u0131tay\b",
            r"\bE:\d{4}/\d+",
        ],
        "norway": [
            r"\bHR-\d{4}-\d+\b",  # Norwegian Supreme Court
            r"\bRt\.\s*\d{4}\b",
        ],
        "sweden": [
            r"\bNJA\s+\d{4}\b",  # Nytt Juridiskt Arkiv
        ],
        "ireland": [
            r"\[\d{4}\]\s*(?:IESC|IEHC|IECA)\b",
        ],
        "pakistan": [
            r"\bPLD\s+\d{4}\b",  # Pakistan Legal Decisions
            r"\bSCMR\b",
        ],
        "kenya": [
            r"\[\d{4}\]\s*(?:eKLR)\b",
        ],
        "philippines": [
            r"\bG\.R\.\s*No\.\b",  # General Register number
        ],
    }

    patterns = DOMESTIC_PATTERNS.get(src, [])
    for pattern in patterns:
        if re.search(pattern, combined, re.IGNORECASE):
            return True

    return False


def identify_case_origin(
    case_name: str, raw_text: str, source_jurisdiction: str = "", source_region: str = ""
) -> dict:
    """
    Identify origin using tiered approach.

    INPUT:
        - case_name: Extracted case name
        - raw_text: Raw citation text
        - source_jurisdiction: Where the citing court is located
        - source_region: Global North/South/International
    ALGORITHM:
        Cache: Check if already identified (avoids repeat Tier 2 calls)
        Tier 1: Dictionary lookup (word-boundary match, $0)
        Tier 1.5: Domestic pattern heuristic (regex, $0)
        Tier 2: Neutral LLM Analysis (Gemini, ~$0.001)
        Tier 3: Web search stub (future)
        Fallback: Domestic default (if no source jurisdiction, unknown)
    OUTPUT: Dict with origin, region, confidence, method
    """
    # Cache check — catches repeated case names within/across documents
    cache_key = case_name.lower().strip()
    if cache_key in CITATION_ORIGIN_CACHE:
        logging.debug(f"Cache hit for '{case_name}'")
        return CITATION_ORIGIN_CACHE[cache_key]

    # Tier 1: Dictionary lookup (source_jurisdiction for ambiguity filtering)
    tier1_result = identify_origin_tier1_dictionary(case_name, raw_text, source_jurisdiction)
    if tier1_result:
        return tier1_result

    # Tier 1.5: Domestic pattern heuristic ($0 - regex)
    if source_jurisdiction and _is_likely_domestic(case_name, raw_text, source_jurisdiction):
        domestic_result = {
            "origin": source_jurisdiction,
            "region": source_region or get_source_region(source_jurisdiction),
            "court": None,
            "year": None,
            "tier": 1,
            "confidence": 0.80,
            "method": "domestic_pattern_match",
        }
        CITATION_ORIGIN_CACHE[cache_key] = domestic_result
        logging.debug(f"Domestic pattern match for '{case_name}' -> {source_jurisdiction}")
        return domestic_result

    # Tier 2: LLM Analysis (pass source context for better results)
    tier2_result = identify_origin_tier2_sonnet(case_name, raw_text, source_jurisdiction)
    if tier2_result and tier2_result["confidence"] >= 0.5:
        return tier2_result

    # Tier 3: Web search (if implemented)
    tier3_result = identify_origin_tier3_websearch(case_name, raw_text)
    if tier3_result:
        return tier3_result

    # All tiers failed — default to domestic (most citations in a document are domestic)
    if source_jurisdiction:
        logging.info(f"Phase 3: Defaulting to domestic for '{case_name}' -> {source_jurisdiction}")
        fallback_result = {
            "origin": source_jurisdiction,
            "region": source_region or get_source_region(source_jurisdiction),
            "court": None,
            "year": None,
            "tier": 3,
            "confidence": 0.60,
            "method": "domestic_default",
        }
        CITATION_ORIGIN_CACHE[cache_key] = fallback_result
        return fallback_result

    # No source jurisdiction available — truly unknown
    logging.warning(f"Phase 3: Could not identify origin for '{case_name}'")
    unknown_result = {
        "origin": "Unknown",
        "region": "Unknown",
        "court": None,
        "year": None,
        "tier": 0,
        "confidence": 0.0,
        "method": "failed_identification",
    }
    CITATION_ORIGIN_CACHE[cache_key] = unknown_result
    return unknown_result


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
            # Create failed summary so document isn't retried on next run
            try:
                summary = CitationExtractionPhasedSummary(
                    document_id=document_id,
                    extraction_started_at=datetime.fromtimestamp(start_time),
                    extraction_completed_at=datetime.now(timezone.utc),
                    total_processing_time_seconds=time.time() - start_time,
                    extraction_success=False,
                    extraction_error="Phase 2A extraction failed - no result returned",
                )
                session.add(summary)
                session.commit()
            except Exception as summary_err:
                session.rollback()
                logging.warning(f"⚠️  Could not save Phase 2A error summary: {summary_err}")
            return False

        total_api_calls += phase2a_result.get("chunk_count", 1)
        total_tokens_input += phase2a_result.get("tokens_input", 0)
        total_tokens_output += phase2a_result.get("tokens_output", 0)

        references = phase2a_result.get("case_law_references", [])
        logging.info(f"  Extracted {len(references)} references")

        # ====================================================================
        # SABIN FILTER (v6): Keep only citations matching Sabin KB cases
        # ====================================================================
        sabin_kept = 0
        sabin_discarded = 0
        if _sabin_filter is not None:
            logging.info("Sabin Filter: Matching citations against knowledge base...")
            kept, discarded = _sabin_filter.filter_citations(references)
            sabin_kept = len(kept)
            sabin_discarded = len(discarded)
            logging.info(f"  Sabin filter: {sabin_kept} kept, {sabin_discarded} discarded")
            references = kept  # Only process Sabin-matched citations from here on

            # Save discarded citations for manual verification (in savepoint so failures don't abort main pipeline)
            if discarded:
                try:
                    nested = session.begin_nested()
                    for d in discarded:
                        match_info = d.get("sabin_match", {})
                        session.add(CitationExtractionDiscarded(
                            document_id=document_id,
                            case_name=d.get("case_name", "")[:500],
                            raw_text=d.get("raw_text", d.get("raw_citation_text", "")),
                            confidence=d.get("confidence"),
                            sabin_closest_match=match_info.get("closest_name", "")[:500] if match_info.get("closest_name") else None,
                            sabin_match_score=match_info.get("closest_score"),
                            discard_reason=match_info.get("reason", "no_sabin_match"),
                            extraction_run_id=_extraction_run_id,
                        ))
                    nested.commit()
                except Exception as e:
                    logging.warning(f"Failed to save discarded citations: {e}")
                    session.rollback()

        # ====================================================================
        # SNIPPET EXTRACTION (v6): Extract text snippets for kept citations
        # ====================================================================
        snippets = []
        if references:
            logging.info("Snippet Extraction: Locating citations in document text...")
            snippets = extract_snippets_batch(raw_text, references)
            found_count = sum(1 for s in snippets if s.get("found"))
            logging.info(f"  Snippets: {found_count}/{len(references)} located in text")

        if len(references) == 0:
            logging.info("  No references found (or all filtered) - creating summary with zero citations")

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
                total_cost_usd=(total_tokens_input / 1e6 * 0.01)
                + (total_tokens_output / 1e6 * 0.04),
                extraction_started_at=datetime.fromtimestamp(start_time),
                extraction_completed_at=datetime.now(timezone.utc),
                total_processing_time_seconds=time.time() - start_time,
                extraction_success=True,
                average_confidence=0.0,
                items_requiring_review=0,
            )
            session.add(summary)
            session.commit()

            stats["processed"] += 1
            stats["no_citations"] += 1
            stats["sabin_kept"] += sabin_kept
            stats["sabin_discarded"] += sabin_discarded
            return True

        # ====================================================================
        # PHASE 2B: FUNCTIONAL CLASSIFICATION (OPTIONAL SEPARATE PASS)
        # ====================================================================
        logging.info("Phase 2B: Functional classification of citations...")

        # Inject snippet context into references for Phase 2B prompt
        for i, ref in enumerate(references):
            if i < len(snippets) and snippets[i].get("found"):
                ref["context_snippet"] = snippets[i].get("snippet", "")

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
        domestic_count = 0
        unknown_count = 0
        # treaty_count removed — treaties excluded from extraction in v5.4
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
            origin_data = identify_case_origin(
                ref.get("case_name", ""), ref.get("raw_text", ""),
                source_jurisdiction, source_region,
            )

            # Track API calls (Tier 2 uses Gemini)
            if origin_data.get("tier") == 2:
                total_api_calls += 1

            # Phase 4: Classify (Geographic)
            citation_type, is_cross_jurisdictional = classify_citation_type(
                source_jurisdiction, source_region, origin_data["origin"], origin_data["region"]
            )

            # Count by type (geographic) — ALL citations counted, none skipped
            if citation_type == "Domestic":
                domestic_count += 1
            elif citation_type == "Foreign Citation":
                foreign_count += 1
            elif citation_type == "International Citation":
                international_count += 1
            elif citation_type == "Foreign International Citation":
                foreign_international_count += 1
            elif citation_type == "Unknown":
                unknown_count += 1

            # Get functional classification from Phase 2B
            func_class = functional_classifications.get(i, {})
            functional_use = func_class.get("functional_use", "unknown")
            opinion_type = func_class.get("opinion_type", ref.get("location", "unclear"))
            key_signals = func_class.get("key_signals", [])

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
            needs_review = confidence < 0.7 or citation_type == "Unknown"
            if needs_review:
                items_for_review += 1

            # Prepare functional metadata for storage
            functional_metadata = {
                "functional_use": functional_use,
                "opinion_type": opinion_type,
                "key_signals": key_signals,
                "v5_4_extraction": True,
            }

            # v6: Extract Sabin match metadata (attached by filter_citations)
            sabin_match = ref.get("sabin_match", {})

            # v6: Extract snippet data (parallel list from extract_snippets_batch)
            snippet_data = snippets[i] if i < len(snippets) else {}

            # Create citation record — ALL citations stored (domestic, foreign, treaty, unknown)
            citation_record = CitationExtractionPhased(
                document_id=document_id,
                case_id=case_id,
                # Phase 1
                source_jurisdiction=source_jurisdiction,
                source_region=source_region,
                # Phase 2
                case_name=ref.get("case_name"),
                raw_citation_text=ref.get("raw_text"),
                location_in_document=opinion_type,
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
                phase_2_model=CONFIG["EXTRACTION_MODEL"],
                phase_3_model=origin_data.get("method"),
                phase_4_model="rule-based",
                processing_time_seconds=time.time() - start_time,
                api_calls_used=total_api_calls,
                # Quality control
                requires_manual_review=needs_review,
                manual_review_reason=(
                    f"Low confidence: {confidence:.2f} | FUNC: {json.dumps(functional_metadata)}"
                    if needs_review
                    else f"FUNC: {json.dumps(functional_metadata)}"
                ),
                # v6 Sabin Filter (D1)
                sabin_case_id_cited=sabin_match.get("sabin_case_id"),
                sabin_match_tier=sabin_match.get("tier"),
                sabin_match_confidence=sabin_match.get("confidence"),
                # v6 Snippet Extraction (D7)
                snippet_text=snippet_data.get("snippet"),
                snippet_start_char=snippet_data.get("snippet_start"),
                snippet_end_char=snippet_data.get("snippet_end"),
            )

            citation_records.append(citation_record)

        # ====================================================================
        # SAVE TO DATABASE
        # ====================================================================
        logging.info(f"Saving {len(citation_records)} citations (all types)...")

        # Calculate totals
        total_cross_jurisdictional = (
            foreign_count + international_count + foreign_international_count
        )
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        # Calculate cost (Gemini 3.1 Flash-Lite: ~$0.01/M input, ~$0.04/M output)
        total_cost = (total_tokens_input / 1e6 * 0.01) + (total_tokens_output / 1e6 * 0.04)

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
            extraction_completed_at=datetime.now(timezone.utc),
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
        stats["domestic_citations"] += domestic_count
        stats["unknown_citations"] += unknown_count
        stats["needs_review"] += items_for_review
        stats["functional_parties"] += functional_parties_count
        stats["functional_dismissed"] += functional_dismissed_count
        stats["functional_contributed"] += functional_contributed_count
        stats["majority_citations"] += majority_count
        stats["dissent_citations"] += dissent_count
        stats["sabin_kept"] += sabin_kept
        stats["sabin_discarded"] += sabin_discarded
        stats["snippets_found"] += sum(1 for s in snippets if s.get("found"))

        logging.info("✓ Completed successfully:")
        logging.info(f"  Total references: {len(references)}")
        logging.info(f"    - Domestic: {domestic_count}")
        logging.info(f"    - Unknown origin: {unknown_count}")
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

        # Create failed summary (use begin_nested to isolate from prior rollback)
        try:
            session.rollback()  # Ensure clean session state before retry
            summary = CitationExtractionPhasedSummary(
                document_id=document_id,
                extraction_started_at=datetime.fromtimestamp(start_time),
                extraction_completed_at=datetime.now(timezone.utc),
                total_processing_time_seconds=time.time() - start_time,
                extraction_success=False,
                extraction_error=str(e)[:500],
            )
            session.add(summary)
            session.commit()
        except Exception as summary_err:
            session.rollback()
            logging.warning(f"⚠️  Could not save error summary: {summary_err}")

        return False


# ============================================================================
# ASYNC WRAPPERS FOR CONCURRENT MODE
# ============================================================================


async def extract_citations_from_text_async(
    document_id: uuid.UUID,
    text: str,
    source_jurisdiction: str,
    source_region: str,
    document_year: int | None = None,
) -> dict | None:
    """Async version of extract_citations_from_text. Uses call_gemini_async."""
    try:
        prompt = generate_v6_extraction_prompt(
            text, source_jurisdiction, source_region, kb_cases=_kb_cases,
            document_year=document_year
        )

        estimated_tokens = estimate_token_count(prompt)
        logging.info(f"  Prompt size: ~{estimated_tokens:,} tokens")

        start_time = time.time()
        result = await call_gemini_async(prompt, model=CONFIG["EXTRACTION_MODEL"], thinking_budget=1024)
        extraction_time = time.time() - start_time

        if result is None:
            logging.error(f"  API call returned None for document {document_id}")
            return None

        data = result["data"]
        if not data:
            data = extract_json_from_text(result["text"])

        if isinstance(data, list) and len(data) > 0:
            data = data[0]

        if not data or not isinstance(data, dict):
            raw_text_snippet = result.get("text", "")[:500]
            logging.error(f"Failed to parse extraction JSON for document {document_id}")
            logging.info(f"Raw response (first 500 chars): {raw_text_snippet}")
            logging.info("Retrying extraction...")
            retry_result = await call_gemini_async(prompt, model=CONFIG["EXTRACTION_MODEL"], thinking_budget=1024)
            data = retry_result["data"] if retry_result else None
            if isinstance(data, list) and len(data) > 0:
                data = data[0]
            if not data or not isinstance(data, dict):
                data = extract_json_from_text(retry_result["text"]) if retry_result else None
            if not data:
                logging.error(f"Retry also failed for document {document_id}")
                return None

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


async def extract_all_case_references_phase2_async(
    document_id: uuid.UUID, raw_text: str, source_jurisdiction: str, source_region: str,
    document_year: int | None = None,
) -> dict | None:
    """Async version of extract_all_case_references_phase2."""
    char_count = len(raw_text)
    estimated_tokens = estimate_token_count(raw_text)
    logging.info(f"  Document size: {char_count:,} chars (~{estimated_tokens:,} tokens)")

    if estimated_tokens <= CHUNK_TOKEN_THRESHOLD:
        return await extract_citations_from_text_async(
            document_id, raw_text, source_jurisdiction, source_region,
            document_year=document_year,
        )

    # Large document — chunked extraction (sequential chunks within a document)
    chunks = _split_into_chunks(raw_text)
    logging.info(f"  Document exceeds {CHUNK_TOKEN_THRESHOLD:,} tokens -- splitting into {len(chunks)} chunks")

    all_references = []
    total_tokens_in = 0
    total_tokens_out = 0
    total_time = 0.0
    model_used = None
    chunk_failures = 0

    for i, chunk in enumerate(chunks):
        chunk_tokens = estimate_token_count(chunk)
        logging.info(f"  Chunk {i + 1}/{len(chunks)}: ~{chunk_tokens:,} tokens")

        result = await extract_citations_from_text_async(
            document_id, chunk, source_jurisdiction, source_region,
            document_year=document_year
        )

        if result:
            refs = result.get("case_law_references", [])
            all_references.extend(refs)
            total_tokens_in += result.get("tokens_input", 0)
            total_tokens_out += result.get("tokens_output", 0)
            total_time += result.get("extraction_time", 0.0)
            model_used = result.get("model", model_used)
            logging.info(f"  Chunk {i + 1}: {len(refs)} references extracted")
        else:
            chunk_failures += 1
            logging.warning(f"  Chunk {i + 1}: extraction failed")

    if not all_references and chunk_failures == len(chunks):
        logging.error(f"  All {len(chunks)} chunks failed for document {document_id}")
        return None

    before_dedup = len(all_references)
    all_references = _deduplicate_references(all_references)
    if before_dedup > len(all_references):
        logging.info(
            f"  Deduplication: {before_dedup} -> {len(all_references)} "
            f"({before_dedup - len(all_references)} duplicates removed)"
        )

    return {
        "case_law_references": all_references,
        "total_references_found": len(all_references),
        "extraction_notes": f"Chunked extraction: {len(chunks)} chunks, {chunk_failures} failures",
        "extraction_time": total_time,
        "tokens_input": total_tokens_in,
        "tokens_output": total_tokens_out,
        "model": model_used,
        "chunk_count": len(chunks),
    }


async def classify_citations_functionally_async(
    citations: list[dict], raw_text: str, source_jurisdiction: str
) -> dict[int, dict]:
    """Async version of classify_citations_functionally."""
    if not citations:
        return {}

    BATCH_SIZE = 30
    all_classifications = {}

    try:
        text_sample = raw_text

        for batch_start in range(0, len(citations), BATCH_SIZE):
            batch = citations[batch_start : batch_start + BATCH_SIZE]

            prompt = generate_functional_classification_prompt(
                batch, text_sample, source_jurisdiction
            )

            result = await call_gemini_async(prompt, model=CONFIG["EXTRACTION_MODEL"], thinking_budget=2048)
            data = result.get("data") if result else None

            if not data and result:
                data = extract_json_from_text(result["text"])

            if not data:
                batch_num = batch_start // BATCH_SIZE + 1
                raw_snippet = (result.get("text", "")[:300] if result else "no response")
                logging.warning(f"Failed to parse functional classification JSON (batch {batch_num}) - retrying...")
                logging.info(f"  Initial raw response (first 300 chars): {raw_snippet}")
                retry_result = await call_gemini_async(prompt, model=CONFIG["EXTRACTION_MODEL"], thinking_budget=2048)
                data = retry_result.get("data") if retry_result else None
                if not data and retry_result:
                    data = extract_json_from_text(retry_result["text"])
                if not data:
                    raw_snippet = (retry_result.get("text", "")[:300] if retry_result else "no response")
                    logging.warning(f"Retry also failed for functional classification batch {batch_num}")
                    logging.info(f"  Raw response (first 300 chars): {raw_snippet}")
                    continue

            if isinstance(data, list) and len(data) > 0:
                data = data[0]

            for item in data.get("classifications", []) if isinstance(data, dict) else []:
                batch_idx = item.get("citation_index", 0) - 1
                global_idx = batch_start + batch_idx
                all_classifications[global_idx] = {
                    "functional_use": item.get("functional_use", "unknown"),
                    "opinion_type": item.get("opinion_type", "unclear"),
                    "key_signals": item.get("key_signals", []),
                    "reasoning": item.get("reasoning", ""),
                }

        logging.info(f"  Functional classification complete for {len(all_classifications)} citations")
        return all_classifications

    except Exception as e:
        logging.warning(f"Error in functional classification: {e}")
        return all_classifications


async def identify_origin_tier2_sonnet_async(
    case_name: str, raw_text: str, source_jurisdiction: str = ""
) -> dict | None:
    """Async version of identify_origin_tier2_sonnet."""
    try:
        source_context = (
            f"\nSOURCE COURT JURISDICTION: {source_jurisdiction}\n"
            f"(The citing court is from {source_jurisdiction}. The citation may be domestic or foreign.)\n"
            if source_jurisdiction
            else ""
        )

        prompt = f"""Identify the jurisdiction/country of origin for this legal case citation.

CASE NAME: {case_name}
RAW CITATION: {raw_text}
{source_context}
ANALYSIS RULES:
1. Identify the court from the citation text (including non-English court names)
2. Use citation format clues (e.g., "U.S." = United States, "UKSC" = UK, "[2014] FCA" = Australia, "ECLI:NL" = Netherlands)
3. Analyze case name patterns and language for origin signals
4. "Reference re ..." citations in Canadian documents are Canadian constitutional references
5. If you cannot confidently determine the origin, set confidence below 0.5

Respond in JSON:
{{
  "origin_country": "country name",
  "region": "Global North|Global South|International",
  "court": "court name if identifiable",
  "year": year if mentioned,
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}}

Analyze the citation objectively. Do NOT assume domestic origin by default."""

        gemini_result = await call_gemini_async(
            prompt,
            model=CONFIG["CLASSIFICATION_MODEL"],
            max_output_tokens=500,
            thinking_budget=1024,
        )

        data = gemini_result["data"]
        if not data:
            data = extract_json_from_text(gemini_result["text"])

        if isinstance(data, list) and len(data) > 0:
            data = data[0]

        if not data or not isinstance(data, dict) or data.get("confidence", 0) < 0.5:
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


async def identify_case_origin_async(
    case_name: str, raw_text: str, source_jurisdiction: str = "", source_region: str = ""
) -> dict:
    """Async version of identify_case_origin. Only Tier 2 is async (API call)."""
    cache_key = case_name.lower().strip()
    if cache_key in CITATION_ORIGIN_CACHE:
        logging.debug(f"Cache hit for '{case_name}'")
        return CITATION_ORIGIN_CACHE[cache_key]

    # Tier 1: Dictionary lookup (no API call)
    tier1_result = identify_origin_tier1_dictionary(case_name, raw_text, source_jurisdiction)
    if tier1_result:
        return tier1_result

    # Tier 1.5: Domestic pattern heuristic (no API call)
    if source_jurisdiction and _is_likely_domestic(case_name, raw_text, source_jurisdiction):
        domestic_result = {
            "origin": source_jurisdiction,
            "region": source_region or get_source_region(source_jurisdiction),
            "court": None,
            "year": None,
            "tier": 1,
            "confidence": 0.80,
            "method": "domestic_pattern_match",
        }
        CITATION_ORIGIN_CACHE[cache_key] = domestic_result
        logging.debug(f"Domestic pattern match for '{case_name}' -> {source_jurisdiction}")
        return domestic_result

    # Tier 2: LLM Analysis (async API call)
    tier2_result = await identify_origin_tier2_sonnet_async(case_name, raw_text, source_jurisdiction)
    if tier2_result and tier2_result["confidence"] >= 0.5:
        return tier2_result

    # Tier 3: Web search (sync, stub)
    tier3_result = identify_origin_tier3_websearch(case_name, raw_text)
    if tier3_result:
        return tier3_result

    # Fallback
    if source_jurisdiction:
        logging.info(f"Phase 3: Defaulting to domestic for '{case_name}' -> {source_jurisdiction}")
        fallback_result = {
            "origin": source_jurisdiction,
            "region": source_region or get_source_region(source_jurisdiction),
            "court": None,
            "year": None,
            "tier": 3,
            "confidence": 0.60,
            "method": "domestic_default",
        }
        CITATION_ORIGIN_CACHE[cache_key] = fallback_result
        return fallback_result

    logging.warning(f"Phase 3: Could not identify origin for '{case_name}'")
    unknown_result = {
        "origin": "Unknown",
        "region": "Unknown",
        "court": None,
        "year": None,
        "tier": 0,
        "confidence": 0.0,
        "method": "failed_identification",
    }
    CITATION_ORIGIN_CACHE[cache_key] = unknown_result
    return unknown_result


async def process_single_document_phased_async(
    doc_tuple, session_factory, stats: dict, stats_lock: asyncio.Lock, semaphore: asyncio.Semaphore
) -> bool:
    """
    Async version of process_single_document_phased.

    Each invocation creates its own DB session from session_factory.
    Semaphore limits concurrent API calls. Stats updated under lock.
    """
    async with semaphore:
        document_id = doc_tuple[0]
        metadata_data = doc_tuple[1]
        raw_text = doc_tuple[2]
        case_id = doc_tuple[3]
        geographies = doc_tuple[4]

        start_time = time.time()
        total_api_calls = 0
        total_tokens_input = 0
        total_tokens_output = 0

        session = session_factory()
        try:
            logging.info(f"\n{'=' * 70}")
            logging.info(f"Processing Document: {document_id}")
            logging.info(f"{'=' * 70}")

            # PHASE 0: DOCUMENT QUALITY PRE-CHECK (no API call)
            if is_garbled_text(raw_text):
                logging.info(f"Phase 0: SKIPPED — garbled text ({len(raw_text):,} chars)")
                summary = CitationExtractionPhasedSummary(
                    document_id=document_id,
                    total_references_extracted=0,
                    extraction_started_at=datetime.fromtimestamp(start_time),
                    extraction_completed_at=datetime.now(timezone.utc),
                    total_processing_time_seconds=time.time() - start_time,
                    extraction_success=False,
                    extraction_error="SKIPPED_GARBLED: Document text is garbled/corrupted",
                )
                session.add(summary)
                session.commit()
                async with stats_lock:
                    stats["errors"] += 1
                return False

            doc_is_too_long = is_too_long(raw_text)
            if doc_is_too_long:
                logging.warning(f"Phase 0: Document is very large ({len(raw_text):,} chars) — will process but flag verification")

            # PHASE 1: SOURCE JURISDICTION (no API call)
            logging.info("Phase 1: Identifying source jurisdiction...")
            if not geographies and isinstance(metadata_data, dict):
                geographies = metadata_data.get("Geographies", "")

            source_jurisdiction = extract_country_from_geographies(geographies)
            source_region = get_source_region(source_jurisdiction)
            logging.info(f"  Geography raw: {geographies}")
            logging.info(f"  Source: {source_jurisdiction} ({source_region})")

            # Extract document_year early (used by prompt and hard filters)
            document_year = None
            if isinstance(metadata_data, dict):
                date_val = metadata_data.get("Filing Date") or metadata_data.get("Document Date")
                if date_val:
                    try:
                        if hasattr(date_val, 'year'):
                            document_year = date_val.year
                        else:
                            year_match = re.search(r'((?:19|20)\d{2})', str(date_val))
                            if year_match:
                                document_year = int(year_match.group(1))
                    except (ValueError, TypeError):
                        pass

            # PHASE 2A: PURE EXTRACTION (async API call)
            logging.info("Phase 2A: Extracting ALL case law references (full document)...")
            phase2a_result = await extract_all_case_references_phase2_async(
                document_id, raw_text, source_jurisdiction, source_region,
                document_year=document_year,
            )

            if not phase2a_result:
                logging.error(f"  Phase 2A failed - skipping document "
                              f"(text_len={len(raw_text):,} chars)")
                async with stats_lock:
                    stats["phase2_failures"] += 1
                try:
                    summary = CitationExtractionPhasedSummary(
                        document_id=document_id,
                        extraction_started_at=datetime.fromtimestamp(start_time),
                        extraction_completed_at=datetime.now(timezone.utc),
                        total_processing_time_seconds=time.time() - start_time,
                        extraction_success=False,
                        extraction_error="Phase 2A extraction failed - no result returned",
                    )
                    session.add(summary)
                    session.commit()
                except Exception as summary_err:
                    session.rollback()
                    logging.warning(f"Could not save Phase 2A error summary: {summary_err}")
                return False

            total_api_calls += phase2a_result.get("chunk_count", 1)
            total_tokens_input += phase2a_result.get("tokens_input", 0)
            total_tokens_output += phase2a_result.get("tokens_output", 0)

            references = phase2a_result.get("case_law_references", [])
            logging.info(f"  Extracted {len(references)} references")

            # HARD FILTERS (anti-hallucination, no API call)
            if references:
                kept_refs, filter_discarded = apply_hard_filters(references, document_year)
                if filter_discarded:
                    logging.info(f"  Hard filters: {len(filter_discarded)} citations discarded "
                                 f"(pipe:{sum(1 for d in filter_discarded if d.get('discard_reason','').startswith('pipe'))} "
                                 f"anachronistic:{sum(1 for d in filter_discarded if d.get('discard_reason','').startswith('anach'))})")
                    # Save discarded to DB
                    try:
                        nested = session.begin_nested()
                        for d in filter_discarded:
                            session.add(CitationExtractionDiscarded(
                                document_id=document_id,
                                case_name=d.get("case_name", "")[:500],
                                raw_text=d.get("raw_text", d.get("raw_citation_text", "")),
                                confidence=d.get("confidence"),
                                discard_reason=d.get("discard_reason", "hard_filter"),
                                extraction_run_id=_extraction_run_id,
                            ))
                        nested.commit()
                    except Exception as e:
                        logging.warning(f"Failed to save hard-filter discarded citations: {e}")
                        session.rollback()
                references = kept_refs

            # SABIN FILTER (no API call)
            sabin_kept = 0
            sabin_discarded = 0
            if _sabin_filter is not None:
                logging.info("Sabin Filter: Matching citations against knowledge base...")
                kept, discarded = _sabin_filter.filter_citations(references)
                sabin_kept = len(kept)
                sabin_discarded = len(discarded)
                logging.info(f"  Sabin filter: {sabin_kept} kept, {sabin_discarded} discarded")
                references = kept

                if discarded:
                    try:
                        nested = session.begin_nested()
                        for d in discarded:
                            match_info = d.get("sabin_match", {})
                            session.add(CitationExtractionDiscarded(
                                document_id=document_id,
                                case_name=d.get("case_name", "")[:500],
                                raw_text=d.get("raw_text", d.get("raw_citation_text", "")),
                                confidence=d.get("confidence"),
                                sabin_closest_match=match_info.get("closest_name", "")[:500] if match_info.get("closest_name") else None,
                                sabin_match_score=match_info.get("closest_score"),
                                discard_reason=match_info.get("reason", "no_sabin_match"),
                                extraction_run_id=_extraction_run_id,
                            ))
                        nested.commit()
                    except Exception as e:
                        logging.warning(f"Failed to save discarded citations: {e}")
                        session.rollback()

            # SNIPPET EXTRACTION (no API call)
            snippets = []
            if references:
                logging.info("Snippet Extraction: Locating citations in document text...")
                snippets = extract_snippets_batch(raw_text, references)
                found_count = sum(1 for s in snippets if s.get("found"))
                logging.info(f"  Snippets: {found_count}/{len(references)} located in text")

            if len(references) == 0:
                logging.info("  No references found (or all filtered) - creating summary with zero citations")
                summary = CitationExtractionPhasedSummary(
                    document_id=document_id,
                    total_references_extracted=0,
                    foreign_citations_count=0,
                    international_citations_count=0,
                    foreign_international_citations_count=0,
                    total_api_calls=total_api_calls,
                    total_tokens_input=total_tokens_input,
                    total_tokens_output=total_tokens_output,
                    total_cost_usd=(total_tokens_input / 1e6 * 0.15) + (total_tokens_output / 1e6 * 0.60),
                    extraction_started_at=datetime.fromtimestamp(start_time),
                    extraction_completed_at=datetime.now(timezone.utc),
                    total_processing_time_seconds=time.time() - start_time,
                    extraction_success=True,
                    average_confidence=0.0,
                    items_requiring_review=0,
                )
                session.add(summary)
                session.commit()

                async with stats_lock:
                    stats["processed"] += 1
                    stats["no_citations"] += 1
                    stats["sabin_kept"] += sabin_kept
                    stats["sabin_discarded"] += sabin_discarded
                return True

            # PHASE 2B: FUNCTIONAL CLASSIFICATION (async API call)
            logging.info("Phase 2B: Functional classification of citations...")
            for i, ref in enumerate(references):
                if i < len(snippets) and snippets[i].get("found"):
                    ref["context_snippet"] = snippets[i].get("snippet", "")

            functional_classifications = await classify_citations_functionally_async(
                references, raw_text, source_jurisdiction
            )
            if functional_classifications:
                total_api_calls += 1

            # PHASE 3 & 4: ORIGIN + CLASSIFICATION
            logging.info("Phase 3: Identifying case origins...")
            logging.info("Phase 4: Classifying citations...")

            citation_records = []
            foreign_count = 0
            international_count = 0
            foreign_international_count = 0
            domestic_count = 0
            unknown_count = 0
            confidences = []
            items_for_review = 0
            functional_parties_count = 0
            functional_dismissed_count = 0
            functional_contributed_count = 0
            majority_count = 0
            dissent_count = 0

            for i, ref in enumerate(references):
                origin_data = await identify_case_origin_async(
                    ref.get("case_name", ""), ref.get("raw_text", ""),
                    source_jurisdiction, source_region,
                )

                if origin_data.get("tier") == 2:
                    total_api_calls += 1

                citation_type, is_cross_jurisdictional = classify_citation_type(
                    source_jurisdiction, source_region, origin_data["origin"], origin_data["region"]
                )

                if citation_type == "Domestic":
                    domestic_count += 1
                elif citation_type == "Foreign Citation":
                    foreign_count += 1
                elif citation_type == "International Citation":
                    international_count += 1
                elif citation_type == "Foreign International Citation":
                    foreign_international_count += 1
                elif citation_type == "Unknown":
                    unknown_count += 1

                func_class = functional_classifications.get(i, {})
                functional_use = func_class.get("functional_use", "unknown")
                opinion_type = func_class.get("opinion_type", ref.get("location", "unclear"))
                key_signals = func_class.get("key_signals", [])

                if functional_use == "parties_argument":
                    functional_parties_count += 1
                elif functional_use == "dismissed":
                    functional_dismissed_count += 1
                elif functional_use == "contributed":
                    functional_contributed_count += 1

                if opinion_type == "majority":
                    majority_count += 1
                elif opinion_type in ["dissent", "concurrence"]:
                    dissent_count += 1

                confidence = origin_data.get("confidence", 0.0)
                confidences.append(confidence)
                needs_review = confidence < 0.7 or citation_type == "Unknown"
                if needs_review:
                    items_for_review += 1

                functional_metadata = {
                    "functional_use": functional_use,
                    "opinion_type": opinion_type,
                    "key_signals": key_signals,
                    "v5_4_extraction": True,
                }

                sabin_match = ref.get("sabin_match", {})
                snippet_data = snippets[i] if i < len(snippets) else {}

                citation_record = CitationExtractionPhased(
                    document_id=document_id,
                    case_id=case_id,
                    source_jurisdiction=source_jurisdiction,
                    source_region=source_region,
                    case_name=ref.get("case_name"),
                    raw_citation_text=ref.get("raw_text"),
                    location_in_document=opinion_type,
                    case_law_origin=origin_data["origin"],
                    case_law_region=origin_data["region"],
                    origin_identification_tier=origin_data["tier"],
                    origin_confidence=origin_data["confidence"],
                    citation_type=citation_type,
                    is_cross_jurisdictional=is_cross_jurisdictional,
                    cited_court=origin_data.get("court"),
                    cited_year=origin_data.get("year"),
                    phase_2_model=CONFIG["EXTRACTION_MODEL"],
                    phase_3_model=origin_data.get("method"),
                    phase_4_model="rule-based",
                    processing_time_seconds=time.time() - start_time,
                    api_calls_used=total_api_calls,
                    requires_manual_review=needs_review,
                    manual_review_reason=(
                        f"Low confidence: {confidence:.2f} | FUNC: {json.dumps(functional_metadata)}"
                        if needs_review
                        else f"FUNC: {json.dumps(functional_metadata)}"
                    ),
                    sabin_case_id_cited=sabin_match.get("sabin_case_id"),
                    sabin_match_tier=sabin_match.get("tier"),
                    sabin_match_confidence=sabin_match.get("confidence"),
                    snippet_text=snippet_data.get("snippet"),
                    snippet_start_char=snippet_data.get("snippet_start"),
                    snippet_end_char=snippet_data.get("snippet_end"),
                )
                citation_records.append(citation_record)

            # PHASE 5: INLINE VERIFICATION (async API call)
            verification_stats = {"confirmed": 0, "not_found": 0, "misattributed": 0,
                                  "cost_usd": 0.0, "tokens_in": 0, "tokens_out": 0, "tokens_thinking": 0}
            if citation_records and not doc_is_too_long:
                logging.info("Phase 5: Inline verification of extracted citations...")
                try:
                    # Add records to session first so they get extraction_id assigned
                    for cr in citation_records:
                        session.add(cr)
                    session.flush()  # Assign PKs without committing

                    v_result = await verify_document_citations_inline(
                        document_text=raw_text,
                        citation_records=citation_records,
                        model=CONFIG["EXTRACTION_MODEL"],
                        thinking_budget=1024,
                    )
                    verification_stats = v_result

                    # Apply verification updates to ORM objects
                    for extraction_id, update_dict in v_result.get("updates", []):
                        for cr in citation_records:
                            if cr.extraction_id == extraction_id:
                                for key, val in update_dict.items():
                                    setattr(cr, key, val)
                                break

                    total_api_calls += v_result.get("api_calls", 0)
                    total_tokens_input += v_result.get("tokens_in", 0)
                    total_tokens_output += v_result.get("tokens_out", 0)

                    unverified_count = v_result.get('unverified', 0)
                    uv_suffix = f" UV:{unverified_count}" if unverified_count else ""
                    logging.info(f"  Verification: C:{v_result['confirmed']} NF:{v_result['not_found']} "
                                 f"M:{v_result['misattributed']}{uv_suffix} Cost:${v_result['cost_usd']:.4f}")
                except Exception as ve:
                    logging.warning(f"Phase 5 verification failed (non-fatal): {ve}")
                    # VMISSUE-3 fix: set all citations to UNVERIFIED when Phase 5 fails entirely
                    from datetime import timezone as _tz
                    _now = datetime.now(_tz.utc)
                    for cr in citation_records:
                        if not getattr(cr, 'verification_status', None):
                            cr.verification_status = "UNVERIFIED"
                            cr.verification_notes = f"Phase 5 failed: {str(ve)[:200]}"
                            cr.verified_at = _now
                            cr.requires_manual_review = True
                            cr.manual_review_reason = "Verification: UNVERIFIED — Phase 5 exception"
            elif doc_is_too_long:
                logging.info("Phase 5: SKIPPED — document too long for verification")
                verification_stats["skipped"] = len(citation_records)

            # SAVE TO DATABASE
            logging.info(f"Saving {len(citation_records)} citations (all types)...")
            total_cross_jurisdictional = foreign_count + international_count + foreign_international_count
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            total_cost = (total_tokens_input / 1e6 * 0.15) + (total_tokens_output / 1e6 * 0.60)

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
                extraction_completed_at=datetime.now(timezone.utc),
                total_processing_time_seconds=time.time() - start_time,
                extraction_success=True,
                average_confidence=avg_confidence,
                items_requiring_review=items_for_review,
                verified_confirmed=verification_stats.get("confirmed", 0),
                verified_not_found=verification_stats.get("not_found", 0),
                verified_misattributed=verification_stats.get("misattributed", 0),
                verified_skipped=verification_stats.get("skipped", 0),
                verification_cost_usd=verification_stats.get("cost_usd", 0.0),
            )

            session.add(summary)
            # citation_records may already be added via session.add() in Phase 5
            # Only add if not already in session
            for citation in citation_records:
                if citation not in session:
                    session.add(citation)
            session.commit()

            # Update shared stats
            async with stats_lock:
                stats["processed"] += 1
                stats["total_references"] += len(references)
                stats["foreign_citations"] += foreign_count
                stats["international_citations"] += international_count
                stats["foreign_international_citations"] += foreign_international_count
                stats["domestic_citations"] += domestic_count
                stats["unknown_citations"] += unknown_count
                stats["needs_review"] += items_for_review
                stats["functional_parties"] += functional_parties_count
                stats["functional_dismissed"] += functional_dismissed_count
                stats["functional_contributed"] += functional_contributed_count
                stats["majority_citations"] += majority_count
                stats["dissent_citations"] += dissent_count
                stats["sabin_kept"] += sabin_kept
                stats["sabin_discarded"] += sabin_discarded
                stats["snippets_found"] += sum(1 for s in snippets if s.get("found"))
                stats["verified_confirmed"] += verification_stats.get("confirmed", 0)
                stats["verified_not_found"] += verification_stats.get("not_found", 0)
                stats["verified_misattributed"] += verification_stats.get("misattributed", 0)
                stats["verification_cost_usd"] += verification_stats.get("cost_usd", 0.0)

            logging.info(f"Completed document {document_id}: {len(references)} refs, ${total_cost:.4f}")
            return True

        except Exception as e:
            session.rollback()
            logging.error(f"Error processing document {document_id}: {e}")
            import traceback
            logging.error(traceback.format_exc())

            async with stats_lock:
                stats["errors"] += 1

            try:
                session.rollback()
                summary = CitationExtractionPhasedSummary(
                    document_id=document_id,
                    extraction_started_at=datetime.fromtimestamp(start_time),
                    extraction_completed_at=datetime.now(timezone.utc),
                    total_processing_time_seconds=time.time() - start_time,
                    extraction_success=False,
                    extraction_error=str(e)[:500],
                )
                session.add(summary)
                session.commit()
            except Exception as summary_err:
                session.rollback()
                logging.warning(f"Could not save error summary: {summary_err}")

            return False

        finally:
            session.close()


# ============================================================================
# MAIN EXECUTION
# ============================================================================


def main(test_run=None, seed=42, concurrent=None):
    """
    Main execution function.

    INPUT:
        - test_run: number of documents to sample (None = all)
        - seed: random seed for reproducible sampling
        - concurrent: number of concurrent documents (None = sequential)
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
    global _kb_cases, _sabin_filter, _extraction_run_id
    _extraction_run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    logging.info("=" * 70)
    logging.info("CITATION EXTRACTION v7.0 - ANTI-HALLUCINATION PIPELINE")
    logging.info("Full-text extraction with hard filters and inline verification")
    logging.info("=" * 70)
    logging.info("Architecture:")
    logging.info("  Phase 0:  Document Quality Pre-check")
    logging.info("  Phase 1:  Source Jurisdiction Identification")
    logging.info(f"  Phase 2A: Extract ALL Case References ({CONFIG['EXTRACTION_MODEL']}, thinking)")
    logging.info("  Phase 2A+: Hard Filters (pipe-format, anachronism)")
    logging.info("  Phase 2A+: Sabin Filter (keep only KB-matched citations)")
    logging.info("  Phase 2A+: Snippet Extraction (locate citations in document)")
    logging.info(f"  Phase 2B: Functional Classification ({CONFIG['EXTRACTION_MODEL']}, thinking)")
    logging.info("  Phase 3:  Identify Case Origin (3-Tier: Dictionary > Gemini > Web)")
    logging.info("  Phase 4:  Classify Citation Type (Geographic + Functional)")
    logging.info("  Phase 5:  Inline Verification (confirm citations in source text)")
    logging.info("=" * 70)
    logging.info("Loading Sabin knowledge base...")
    _kb_cases = load_knowledge_base()
    logging.info(f"  ✓ Loaded {len(_kb_cases)} cases")
    _sabin_filter = SabinFilter()
    logging.info("  ✓ Sabin filter initialized")
    logging.info("=" * 70)

    # Get trial batch filter
    trial_batch_ids = get_trial_batch_document_ids()

    # Connect to database
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    # Ensure tables exist
    Base.metadata.create_all(engine)

    # v6 migration: add new columns if they don't exist yet
    from sqlalchemy import text as sa_text, inspect as sa_inspect
    inspector = sa_inspect(engine)
    existing_cols = {c["name"] for c in inspector.get_columns("citation_extraction_phased")}
    v6_columns = [
        ("sabin_case_id_cited", "VARCHAR(200)"),
        ("sabin_match_tier", "INTEGER"),
        ("sabin_match_confidence", "DECIMAL(3,2)"),
        ("snippet_text", "TEXT"),
        ("snippet_start_char", "INTEGER"),
        ("snippet_end_char", "INTEGER"),
    ]
    with engine.begin() as conn:
        for col_name, col_type in v6_columns:
            if col_name not in existing_cols:
                conn.execute(sa_text(
                    f"ALTER TABLE citation_extraction_phased ADD COLUMN {col_name} {col_type}"
                ))
                logging.info(f"  + Added column: {col_name}")

    # Ensure citation_extraction_discarded table exists
    if not inspector.has_table("citation_extraction_discarded"):
        CitationExtractionDiscarded.__table__.create(engine)
        logging.info("  + Created table: citation_extraction_discarded")

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
            .distinct(Document.document_id)
        )

        # Count total decisions
        total_decisions = query.count()
        logging.info(f"Found {total_decisions} documents classified as decisions")

        # Filter by trial batch if enabled
        if trial_batch_ids is not None:
            query = query.filter(Document.sabin_document_id.in_(trial_batch_ids))
            trial_filtered_count = query.count()
            logging.info(f"After trial batch filter: {trial_filtered_count} documents")

        # Apply test-run sampling: filter query to sampled document IDs
        if test_run is not None:
            df = pd.read_excel(DATABASE_FILE)
            test_run_ids = get_sampled_document_ids(df, test_run, seed)
            if test_run_ids is not None:
                query = query.filter(Document.sabin_document_id.in_(test_run_ids))
                logging.info(f"After test-run filter: {query.count()} documents")

        # Exclude already processed (single-level NOT IN subquery)
        query = query.filter(~Document.document_id.in_(
            session.query(CitationExtractionPhasedSummary.document_id)
        ))
        excluded_count = session.query(CitationExtractionPhasedSummary.document_id).count()
        if excluded_count:
            logging.info(f"Excluding {excluded_count} already processed documents")

        # Materialize results to avoid server-side cursor issues with per-doc commits
        total_to_process = query.count()
        logging.info(f"\n✓ Documents to process: {total_to_process}")
        documents = query.all()

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
            # Citation type breakdown
            "domestic_citations": 0,
            "unknown_citations": 0,
            # Functional classification stats
            "functional_parties": 0,
            "functional_dismissed": 0,
            "functional_contributed": 0,
            "majority_citations": 0,
            "dissent_citations": 0,
            # v6 Sabin filter stats
            "sabin_kept": 0,
            "sabin_discarded": 0,
            # v6 Snippet stats
            "snippets_found": 0,
            # v7 Hard filter stats
            "hard_filter_discarded": 0,
            # v7 Verification stats
            "verified_confirmed": 0,
            "verified_not_found": 0,
            "verified_misattributed": 0,
            "verification_cost_usd": 0.0,
        }

        # Process each document
        logging.info("\n" + "=" * 70)
        logging.info("STARTING FULL-TEXT EXTRACTION")
        if concurrent:
            logging.info(f"MODE: CONCURRENT (N={concurrent})")
        else:
            logging.info("MODE: SEQUENTIAL")
        logging.info("=" * 70)

        if concurrent:
            # Concurrent mode: use asyncio with per-document sessions
            concurrent_engine = get_engine(pool_size=concurrent + 5, max_overflow=10)
            Base.metadata.create_all(concurrent_engine)
            ConcurrentSessionFactory = sessionmaker(bind=concurrent_engine)

            async def run_concurrent():
                global _shutdown_requested
                sem = asyncio.Semaphore(concurrent)
                lock = asyncio.Lock()
                pbar = tqdm(total=len(documents), desc="Processing Documents")

                async def process_one(doc):
                    if _shutdown_requested:
                        pbar.update(1)
                        return
                    result = await process_single_document_phased_async(
                        doc, ConcurrentSessionFactory, stats, lock, sem
                    )
                    pbar.update(1)
                    return result

                results = await asyncio.gather(
                    *[process_one(doc) for doc in documents],
                    return_exceptions=True,
                )
                pbar.close()

                # Log any unexpected exceptions from gather
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logging.error(f"Document {i} raised unhandled exception: {result}")

            # Set up graceful shutdown
            original_sigint = signal.getsignal(signal.SIGINT)

            def _handle_sigint(sig, frame):
                global _shutdown_requested
                if _shutdown_requested:
                    # Second Ctrl+C: force exit
                    logging.warning("Force shutdown requested")
                    raise KeyboardInterrupt
                _shutdown_requested = True
                logging.warning("Shutdown requested - completing in-progress documents...")

            signal.signal(signal.SIGINT, _handle_sigint)
            try:
                asyncio.run(run_concurrent())
            finally:
                signal.signal(signal.SIGINT, original_sigint)
                concurrent_engine.dispose()
        else:
            # Sequential mode — uses async path to ensure Phase 0, hard filters,
            # Phase 5 verification, and thinking are all active
            sequential_engine = get_engine(pool_size=5, max_overflow=5)
            Base.metadata.create_all(sequential_engine)
            SequentialSessionFactory = sessionmaker(bind=sequential_engine)

            async def run_sequential():
                global _shutdown_requested
                lock = asyncio.Lock()
                sem = asyncio.Semaphore(1)
                pbar = tqdm(total=len(documents), desc="Processing Documents")
                for doc in documents:
                    if _shutdown_requested:
                        pbar.update(1)
                        continue
                    await process_single_document_phased_async(
                        doc, SequentialSessionFactory, stats, lock, sem
                    )
                    pbar.update(1)
                pbar.close()

            original_sigint = signal.getsignal(signal.SIGINT)

            def _handle_sigint_seq(sig, frame):
                global _shutdown_requested
                if _shutdown_requested:
                    logging.warning("Force shutdown requested")
                    raise KeyboardInterrupt
                _shutdown_requested = True
                logging.warning("Shutdown requested - completing current document...")

            signal.signal(signal.SIGINT, _handle_sigint_seq)
            try:
                asyncio.run(run_sequential())
            finally:
                signal.signal(signal.SIGINT, original_sigint)
                sequential_engine.dispose()

        # Report final statistics
        logging.info("\n" + "=" * 70)
        logging.info("EXTRACTION COMPLETE - FINAL STATISTICS (v7.0)")
        logging.info("=" * 70)
        logging.info(f"Total decisions in database:     {total_decisions}")
        logging.info(f"Documents processed:             {stats['processed']}")
        logging.info(f"Documents with no citations:     {stats['no_citations']}")
        logging.info(f"Phase 2 failures:                {stats['phase2_failures']}")
        logging.info(f"Other errors:                    {stats['errors']}")
        logging.info("")
        logging.info("GEOGRAPHIC CLASSIFICATION:")
        logging.info(f"Total references extracted:      {stats['total_references']}")
        logging.info(f"Domestic Citations:              {stats['domestic_citations']}")
        logging.info(f"Unknown Origin Citations:        {stats['unknown_citations']}")
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
        logging.info("")
        logging.info("SABIN FILTER:")
        logging.info(f"  Citations kept (Sabin match):  {stats['sabin_kept']}")
        logging.info(f"  Citations discarded:           {stats['sabin_discarded']}")
        logging.info(f"  Snippets located in text:      {stats['snippets_found']}")
        logging.info("")
        logging.info("INLINE VERIFICATION (Phase 5):")
        logging.info(f"  CONFIRMED:                     {stats['verified_confirmed']}")
        logging.info(f"  NOT_FOUND:                     {stats['verified_not_found']}")
        logging.info(f"  MISATTRIBUTED:                 {stats['verified_misattributed']}")
        logging.info(f"  Verification cost:             ${stats['verification_cost_usd']:.4f}")

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
    parser.add_argument(
        "--concurrent", type=int, default=None, metavar="N",
        help="Process N documents concurrently via asyncio (default: sequential)",
    )
    args = parser.parse_args()

    main(test_run=args.test_run, seed=args.seed, concurrent=args.concurrent)
