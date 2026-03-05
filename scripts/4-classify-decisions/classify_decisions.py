#!/usr/bin/env python3
"""
Decision Classification Script (Phase 2a) - Version 1.0
======================================================================
Classifies documents as judicial decisions or non-decisions.

🏃 Run from: project root
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

import logging
import os
import re
import sys
import time
from datetime import datetime
from uuid import uuid5

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
from init_database import Document, ExtractedText

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    force=True,
    handlers=[
        logging.FileHandler(LOGS_DIR / "decision_classification.log", encoding="utf-8"),
        logging.StreamHandler(open(sys.stdout.fileno(), mode="w", encoding="utf-8", errors="replace", closefd=False)),
    ],
)
logging.getLogger("httpx").setLevel(logging.WARNING)

# ============================================================================
# API CLIENT SETUP (Gemini via google-genai)
# ============================================================================

# ============================================================================
# TRIAL BATCH FILTERING
# ============================================================================


def get_trial_batch_document_uuids(df=None):
    """
    Return set of Document UUIDs that are in the trial batch.
    Returns None if trial batch mode is disabled or if there's an error.

    INPUT:
        - df: Pre-loaded DataFrame (optional, avoids duplicate Excel read)
    OUTPUT: Set of UUIDs or None
    """
    if not TRIAL_BATCH_CONFIG["ENABLED"]:
        logging.info("ℹ️  Trial batch mode DISABLED - will process all documents")
        return None

    try:
        if df is None:
            df = pd.read_excel(DATABASE_FILE)
        logging.info(f"Loaded database with {len(df)} rows for trial batch filtering")

        col_name = TRIAL_BATCH_CONFIG["COLUMN_NAME"]
        if col_name not in df.columns:
            logging.error(f"❌ Trial batch column '{col_name}' not found!")
            logging.error("   Proceeding without filtering")
            return None

        true_values = TRIAL_BATCH_CONFIG["TRUE_VALUES"]
        trial_batch_df = df[df[col_name].isin(true_values)]

        # Convert Document IDs to UUIDs using same method as populate_metadata
        def generate_document_uuid(document_id_str):
            clean_id = str(document_id_str).strip().lower()
            return uuid5(UUID_NAMESPACE, f"document_{clean_id}")

        doc_uuids = set(trial_batch_df["Document ID"].apply(generate_document_uuid))

        logging.info("=" * 70)
        logging.info("TRIAL BATCH FILTERING FOR DECISION CLASSIFICATION")
        logging.info("=" * 70)
        logging.info(f"Total documents in database:  {len(df)}")
        logging.info(f"Trial batch documents:        {len(doc_uuids)}")
        logging.info(f"Will only classify these {len(doc_uuids)} documents")
        logging.info("=" * 70)

        return doc_uuids, trial_batch_df

    except Exception as e:
        logging.error(f"❌ Error loading trial batch filter: {e}")
        logging.error("   Proceeding without filtering")
        return None, None


# ============================================================================
# DOCUMENT TITLE ANALYSIS
# ============================================================================


def load_document_titles_mapping(df=None):
    """
    Load Document ID → Document Title mapping from Excel.

    INPUT:
        - df: Pre-loaded DataFrame (optional, avoids duplicate Excel read)
    OUTPUT: Dictionary mapping UUID to Document Title string
    """
    try:
        if df is None:
            df = pd.read_excel(DATABASE_FILE)

        if "Document ID" not in df.columns or "Document Title" not in df.columns:
            logging.error("❌ Required columns not found in Excel!")
            return {}

        # Create UUID mapping
        def generate_document_uuid(document_id_str):
            clean_id = str(document_id_str).strip().lower()
            return uuid5(UUID_NAMESPACE, f"document_{clean_id}")

        mapping = {}
        for _, row in df.iterrows():
            doc_uuid = generate_document_uuid(row["Document ID"])
            doc_title = str(row["Document Title"]) if pd.notna(row["Document Title"]) else ""
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
    words = re.findall(r"\b\w+\b", title_clean)

    if not words:
        return None, None

    last_word = words[-1]

    # Check against decision indicators
    decision_words = ["judgment", "decision", "judgement"]  # Include both spellings

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
    doc_type = metadata.get("Document Type", "Unknown")
    doc_title = metadata.get("Document Title", "Unknown")

    # Limit text to first portion to save tokens
    classification_text_limit = CONFIG.get("CLASSIFICATION_TEXT_LIMIT", 8000)
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
  "confidence_score": 0.95
}}

CRITICAL: Output ONLY the JSON object. No markdown, no code blocks, no explanatory text.
</output_format>

<document_excerpt>
{text_sample}
</document_excerpt>"""

    try:
        time.sleep(1.5)  # Rate limiting

        result = call_gemini(
            prompt,
            model=CONFIG["CLASSIFICATION_MODEL"],
            max_output_tokens=1000,
        )

        data = result["data"]

        if not data:
            logging.error("Failed to parse classification JSON")
            logging.error(f"Response was: {result['text'][:500]}")
            return None, None, "JSON parse failed"

        is_decision = data.get("is_judicial_decision", False)
        confidence = data.get("confidence_score", 0.0)

        return is_decision, confidence

    except Exception as e:
        logging.error(f"Error in LLM classification: {e}")
        return None, None, f"API error: {e}"


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
            stats["not_found"] += 1
            return False

        # Skip if already classified
        if document.is_decision is not None:
            logging.debug(f"Document {doc_uuid} already classified, skipping")
            stats["already_classified"] += 1
            return True

        # Get document title from Excel
        doc_title = document_titles.get(doc_uuid, "")

        # STRATEGY 1: Check Document Title last word (POSITIVE IDENTIFICATION ONLY)
        title_result, last_word = check_title_last_word(doc_title)

        if title_result is True:
            # POSITIVE MATCH: Title definitively indicates this is a decision
            document.is_decision = True
            document.decision_classification_method = "document_title"
            document.decision_classification_confidence = (
                1.0  # Heuristic is definitive for positive matches
            )
            document.decision_classification_date = datetime.now()

            session.commit()

            stats["decisions_title"] += 1
            logging.info(f"✓ Decision (Title): {doc_uuid} - '{last_word}'")

            return True

        # STRATEGY 2: LLM Classification (for all non-matching titles)
        # Note: We cannot conclude non-matching titles are NOT decisions
        # They could be decisions with different title formats, so we need LLM analysis
        logging.info(f"Using LLM for {doc_uuid} (title: '{last_word}' - inconclusive)")

        if not extracted_text.raw_text:
            logging.warning(f"No text available for {doc_uuid}")
            stats["no_text"] += 1
            return False

        metadata = document.metadata_data or {}
        is_decision, confidence = classify_with_llm(extracted_text.raw_text, metadata)

        if is_decision is None:
            # LLM classification failed
            logging.error(f"LLM classification failed for {doc_uuid}")
            stats["llm_errors"] += 1
            return False

        # Store LLM classification
        document.is_decision = is_decision
        document.decision_classification_method = "llm_sonnet"
        document.decision_classification_confidence = confidence
        document.decision_classification_date = datetime.now()

        session.commit()

        if is_decision:
            stats["decisions_llm"] += 1
            logging.info(f"✓ Decision (LLM): {doc_uuid} - confidence {confidence:.2f}")
        else:
            stats["non_decisions_llm"] += 1
            logging.info(f"✗ Non-Decision (LLM): {doc_uuid} - confidence {confidence:.2f}")

        return True

    except Exception as e:
        session.rollback()
        logging.error(f"Error classifying document {doc_uuid}: {e}")
        stats["errors"] += 1
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
        2. Load document titles from Excel
        3. Query documents with extracted text
        4. Filter by trial batch
        5. Apply test-run sampling
        6. Classify each document
        7. Report statistics
    OUTPUT: Statistics printed to log
    """
    logging.info("=" * 70)
    logging.info("DECISION CLASSIFICATION - VERSION 1.0")
    logging.info(f"Classification Model: {CONFIG['CLASSIFICATION_MODEL']}")
    logging.info("=" * 70)

    # Load Excel once and share across functions
    logging.info("Loading Excel database (single read)...")
    df_excel = pd.read_excel(DATABASE_FILE)
    logging.info(f"Loaded {len(df_excel)} rows from Excel")

    # Load trial batch filter
    trial_batch_result = get_trial_batch_document_uuids(df=df_excel)
    if trial_batch_result:
        trial_batch_uuids, trial_batch_df = trial_batch_result
    else:
        trial_batch_uuids = None

    # Load document titles
    logging.info("Loading document titles from Excel...")
    document_titles = load_document_titles_mapping(df=df_excel)
    del df_excel  # Free memory

    if not document_titles:
        logging.error("❌ Failed to load document titles. Exiting.")
        return

    # Connect to database
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Query documents with extracted text
        query = (
            session.query(Document.document_id, ExtractedText)
            .join(ExtractedText)
            .filter(ExtractedText.raw_text.isnot(None))
        )

        # Filter by trial batch if enabled
        if trial_batch_uuids is not None:
            query = query.filter(Document.document_id.in_(trial_batch_uuids))
            logging.info(f"Applied trial batch filter: {len(trial_batch_uuids)} documents")

        # Exclude already classified (optional - comment out to re-classify)
        # query = query.filter(Document.is_decision == None)

        # Apply test-run sampling before materializing
        if test_run is not None:
            df_test = pd.read_excel(DATABASE_FILE)
            test_run_uuids = get_sampled_document_uuids(df_test, test_run, seed)
            del df_test
            if test_run_uuids is not None:
                query = query.filter(Document.document_id.in_(test_run_uuids))
                logging.info(f"After test-run filter: {query.count()} documents")

        total_to_classify = query.count()
        logging.info(f"Found {total_to_classify} documents to classify")

        if total_to_classify == 0:
            logging.warning("⚠️  No documents to process!")
            return

        results = query.yield_per(100)

        # Initialize statistics
        stats = {
            "decisions_title": 0,
            "decisions_llm": 0,
            "non_decisions_llm": 0,  # Note: Title-based never classifies as non-decision
            "already_classified": 0,
            "no_text": 0,
            "llm_errors": 0,
            "errors": 0,
            "not_found": 0,
        }

        # Process each document
        # NOTE: Cannot use expunge_all() mid-iteration because yield_per streams
        # ORM entities (ExtractedText) that become invalid after identity map reset.
        # Memory is bounded by commit-time expiry (expire_on_commit=True default).
        for doc_uuid, extracted_text in tqdm(
            results, total=total_to_classify, desc="Classifying"
        ):
            classify_single_document(doc_uuid, extracted_text, document_titles, session, stats)

        # Report statistics
        logging.info("\n" + "=" * 70)
        logging.info("CLASSIFICATION SUMMARY")
        logging.info("=" * 70)
        logging.info("Documents classified as DECISIONS:")
        logging.info(f"  - Via Document Title:  {stats['decisions_title']}")
        logging.info(f"  - Via LLM Analysis:    {stats['decisions_llm']}")
        logging.info(
            f"  - TOTAL DECISIONS:     {stats['decisions_title'] + stats['decisions_llm']}"
        )
        logging.info("")
        logging.info("Documents classified as NON-DECISIONS:")
        logging.info(f"  - Via LLM Analysis:    {stats['non_decisions_llm']}")
        logging.info(
            "  - (Title-based classification only identifies decisions, not non-decisions)"
        )
        logging.info("")
        logging.info(f"Already classified:      {stats['already_classified']}")
        logging.info(f"No text available:       {stats['no_text']}")
        logging.info(f"LLM errors:              {stats['llm_errors']}")
        logging.info(f"Other errors:            {stats['errors']}")

        if TRIAL_BATCH_CONFIG["ENABLED"]:
            logging.info("\n✓ Trial batch mode was ENABLED")
            logging.info("  Only processed documents from trial batch")

        logging.info("=" * 70)

    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Classify documents as judicial decisions")
    add_test_run_arg(parser)
    args = parser.parse_args()

    main(test_run=args.test_run, seed=args.seed)
