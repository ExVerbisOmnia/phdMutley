#!/usr/bin/env python3
"""
Classify Documents by Title Keywords (Step 0 + Step A)
======================================================
Step 0: Links PDF file paths to documents using metadata_data->>'original_document_id'.
Step A: Classifies documents as decision/non-decision based on title keyword matching.

Documents whose titles end with a recognized keyword after the last " - " separator
are classified with 0.95 confidence. Ambiguous documents (no title, no separator,
unknown keyword) are deferred for LLM classification in Step B.

VERSION: 1.0
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPTS_DIR)

from config import DATABASE_FILE, LOGS_DIR, PDF_DOWNLOAD_DIR
from gcp_secrets import get_engine
from pipeline_status import PipelineStatus
from test_run import add_test_run_arg, get_sampled_document_ids

sys.path.insert(0, os.path.join(_SCRIPTS_DIR, "0-initialize-database"))
from init_database import Document

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    force=True,
    handlers=[
        logging.FileHandler(LOGS_DIR / "classify_by_title.log", encoding="utf-8"),
        logging.StreamHandler(
            open(
                sys.stdout.fileno(),
                mode="w",
                encoding="utf-8",
                errors="replace",
                closefd=False,
            )
        ),
    ],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DECISION_KEYWORDS = {
    "judgment",
    "judgement",
    "decision",
    "order",
    "ruling",
    "sentence",
    "sentencia",
    "arrêt",
    "urteil",
    "decreto",
    "acórdão",
    "verdict",
    "opinion",
    "opinion and order",
    "memorandum opinion",
    "memorandum opinion and order",
    "memorandum decision",
    "memorandum and order",
    "minute order",
    "order to show cause",
    "order list",
    "order denying petition for review",
    "administrative order",
    "consent order",
    "consent decree",
    "consent decree/order",
    "findings of fact and conclusions of law",
    "findings and recommendations",
    "report and recommendation",
    "tentative ruling",
    "minute proceedings",
}

NON_DECISION_KEYWORDS = {
    "complaint",
    "motion",
    "brief",
    "petition",
    "appeal",
    "amicus brief",
    "amicus motion",
    "notice of appeal",
    "reply",
    "response",
    "opposition",
    "press release",
    "motion for summary judgment",
    "motion to dismiss",
    "motion to intervene",
    "notice",
    "settlement",
    "application",
    "submission",
    "letter",
    "report",
}


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------


def link_pdf_paths(session: Session, pdf_dir: Path) -> int:
    """
    Populate pdf_file_path for all documents using metadata_data->>'original_document_id'.

    INPUT:
        - session: SQLAlchemy session
        - pdf_dir: Path to directory containing downloaded PDFs
    ALGORITHM:
        1. UPDATE documents SET pdf_file_path where NULL and original_document_id exists
        2. Commit and return count of updated rows
    OUTPUT: Number of rows updated
    """
    result = session.execute(
        text("""
            UPDATE documents
            SET pdf_file_path = :pdf_dir || '/doc_' || (metadata_data->>'original_document_id') || '.pdf'
            WHERE pdf_file_path IS NULL
              AND metadata_data->>'original_document_id' IS NOT NULL
        """),
        {"pdf_dir": str(pdf_dir)},
    )
    session.commit()
    return result.rowcount


def extract_keyword_from_title(title: str) -> tuple[str | None, str]:
    """
    Extract the document-type keyword from a Sabin-style title.

    INPUT:
        - title: Document title string (may be empty/NaN)
    ALGORITHM:
        1. Normalize en-dash and em-dash to " - "
        2. If empty/NaN -> (None, "no_title")
        3. If no " - " separator -> (None, "no_separator")
        4. rsplit on " - ", take right side, strip, lowercase
    OUTPUT: (keyword_or_none, reason_string)
    """
    if not title or (isinstance(title, float) and pd.isna(title)):
        return (None, "no_title")

    title = str(title)
    # Normalize en-dash (\u2013) and em-dash (\u2014) to spaced hyphen
    title = title.replace("\u2013", " - ").replace("\u2014", " - ")

    if " - " not in title:
        return (None, "no_separator")

    keyword = title.rsplit(" - ", maxsplit=1)[1].strip().lower()
    return (keyword, "has_keyword")


def classify_keyword(keyword: str) -> tuple[bool | None, str, float]:
    """
    Classify a keyword as decision, non-decision, or ambiguous.

    INPUT:
        - keyword: Lowercase keyword extracted from title
    ALGORITHM:
        1. Check DECISION_KEYWORDS -> (True, "title_keyword", 0.95)
        2. Check NON_DECISION_KEYWORDS -> (False, "title_keyword_excluded", 0.95)
        3. "other" -> (None, "other_keyword", 0.0)
        4. Else -> (None, "unknown_keyword", 0.0)
    OUTPUT: (is_decision, method, confidence)
    """
    if keyword in DECISION_KEYWORDS:
        return (True, "title_keyword", 0.95)
    if keyword in NON_DECISION_KEYWORDS:
        return (False, "title_keyword_excluded", 0.95)
    if keyword == "other":
        return (None, "other_keyword", 0.0)
    return (None, "unknown_keyword", 0.0)


def reset_all_classifications(session: Session) -> int:
    """
    Clear all existing decision classifications from the documents table.

    INPUT:
        - session: SQLAlchemy session
    ALGORITHM:
        1. Bulk UPDATE setting classification fields to NULL where is_decision IS NOT NULL
        2. Commit and return rowcount
    OUTPUT: Number of rows reset
    """
    result = session.execute(
        text("""
            UPDATE documents
            SET is_decision = NULL,
                decision_classification_method = NULL,
                decision_classification_confidence = NULL,
                decision_classification_date = NULL
            WHERE is_decision IS NOT NULL
        """)
    )
    session.commit()
    return result.rowcount


def main(test_run=None, seed=42, reset=False, link_pdfs=True):
    """
    Main entry point: link PDFs (Step 0) then classify by title keyword (Step A).

    INPUT:
        - test_run: int or None — if set, sample N documents for test
        - seed: random seed for test sampling
        - reset: if True, clear all existing classifications first
        - link_pdfs: if True, run Step 0 (PDF path linking)
    ALGORITHM:
        1. Setup engine and session
        2. Optionally link PDF paths and verify
        3. Load Excel title mapping
        4. Optionally reset existing classifications
        5. Query unclassified documents, filter by test set if applicable
        6. For each doc: extract keyword -> classify -> update DB
        7. Batch commit every 500 docs
        8. Log summary stats
    OUTPUT: None (updates database in place)
    """
    logger.info("=" * 70)
    logger.info("CLASSIFY BY TITLE KEYWORD — Step 0 + Step A")
    logger.info("=" * 70)

    engine = get_engine()

    stats = {
        "decisions": 0,
        "non_decisions": 0,
        "no_title": 0,
        "deferred_no_separator": 0,
        "deferred_other": 0,
        "deferred_unknown": 0,
        "already_classified": 0,
        "not_in_excel": 0,
        "reset_count": 0,
        "pdfs_linked": 0,
    }

    with Session(engine) as session:
        # ---------------------------------------------------------------
        # Step 0: Link PDF paths
        # ---------------------------------------------------------------
        if link_pdfs:
            logger.info("-" * 50)
            logger.info("STEP 0: Linking PDF file paths")
            linked = link_pdf_paths(session, PDF_DOWNLOAD_DIR)
            stats["pdfs_linked"] = linked
            logger.info(f"Linked {linked} PDF paths")

            # Verify: how many docs have paths vs how many PDFs exist on disk
            total_with_path = session.execute(
                text("SELECT COUNT(*) FROM documents WHERE pdf_file_path IS NOT NULL")
            ).scalar()
            total_docs = session.execute(text("SELECT COUNT(*) FROM documents")).scalar()
            logger.info(
                f"Documents with PDF path: {total_with_path} / {total_docs}"
            )

            # Count actually existing files
            if PDF_DOWNLOAD_DIR.exists():
                existing_pdfs = sum(1 for f in PDF_DOWNLOAD_DIR.iterdir() if f.suffix == ".pdf")
                logger.info(f"PDF files on disk: {existing_pdfs}")

        # ---------------------------------------------------------------
        # Load Excel -> title mapping
        # ---------------------------------------------------------------
        logger.info("-" * 50)
        logger.info("Loading Excel title mapping")
        df = pd.read_excel(DATABASE_FILE, dtype=str)
        title_map = {}
        for _, row in df.iterrows():
            doc_id = str(row.get("Document ID", "")).strip()
            title = str(row.get("Document Title", "")).strip()
            if doc_id:
                title_map[doc_id] = title
        logger.info(f"Loaded {len(title_map)} document titles from Excel")

        # ---------------------------------------------------------------
        # Optional: reset classifications
        # ---------------------------------------------------------------
        if reset:
            logger.info("-" * 50)
            logger.info("RESETTING all existing classifications")
            stats["reset_count"] = reset_all_classifications(session)
            logger.info(f"Reset {stats['reset_count']} documents")

        # ---------------------------------------------------------------
        # Test-run sampling
        # ---------------------------------------------------------------
        test_ids = None
        if test_run is not None:
            logger.info(f"Test-run mode: sampling {test_run} documents (seed={seed})")
            test_ids = get_sampled_document_ids(df, test_run, seed)

        # ---------------------------------------------------------------
        # Step A: Classify unclassified documents
        # ---------------------------------------------------------------
        logger.info("-" * 50)
        logger.info("STEP A: Title keyword classification")

        status = PipelineStatus("step-a")

        query = session.query(Document).filter(Document.is_decision.is_(None))

        if test_ids is not None:
            query = query.filter(Document.sabin_document_id.in_(test_ids))

        unclassified = query.all()
        logger.info(f"Documents to classify: {len(unclassified)}")

        now = datetime.now(timezone.utc)
        batch_size = 500

        for i, doc in enumerate(unclassified):
            title = title_map.get(doc.sabin_document_id)
            if title is None:
                stats["not_in_excel"] += 1
                continue

            keyword, reason = extract_keyword_from_title(title)

            if reason == "no_title":
                stats["no_title"] += 1
                continue

            if reason == "no_separator":
                stats["deferred_no_separator"] += 1
                continue

            # reason == "has_keyword"
            is_decision, method, confidence = classify_keyword(keyword)

            if is_decision is True:
                stats["decisions"] += 1
            elif is_decision is False:
                stats["non_decisions"] += 1
            elif method == "other_keyword":
                stats["deferred_other"] += 1
                continue
            elif method == "unknown_keyword":
                stats["deferred_unknown"] += 1
                continue

            doc.is_decision = is_decision
            doc.decision_classification_method = method
            doc.decision_classification_confidence = confidence
            doc.decision_classification_date = now

            if (i + 1) % batch_size == 0:
                session.commit()
                logger.info(f"Committed batch at {i + 1} documents")
                status.update(
                    processed=i + 1,
                    total=len(unclassified),
                    errors=0,
                    decisions=stats["decisions"],
                    non_decisions=stats["non_decisions"],
                )

        session.commit()

    # ---------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------
    logger.info("=" * 70)
    logger.info("CLASSIFICATION SUMMARY")
    logger.info("=" * 70)
    for key, value in stats.items():
        logger.info(f"  {key}: {value}")

    classified = stats["decisions"] + stats["non_decisions"]
    deferred = (
        stats["no_title"]
        + stats["deferred_no_separator"]
        + stats["deferred_other"]
        + stats["deferred_unknown"]
        + stats["not_in_excel"]
    )
    logger.info(f"  --- classified: {classified}")
    logger.info(f"  --- deferred (for Step B): {deferred}")
    logger.info("=" * 70)

    status.update(processed=classified + deferred, total=classified + deferred)
    status.complete(**stats)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Classify documents by title keywords (Step 0 + Step A)"
    )
    add_test_run_arg(parser)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset all existing classifications before running",
    )
    parser.add_argument(
        "--no-link-pdfs",
        action="store_true",
        help="Skip PDF path linking step",
    )
    args = parser.parse_args()
    main(
        test_run=args.test_run,
        seed=args.seed,
        reset=args.reset,
        link_pdfs=not args.no_link_pdfs,
    )
