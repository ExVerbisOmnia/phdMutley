#!/usr/bin/env python3
"""
PDF Text Extraction Script (Version 3.0 - Trial Batch Support)
==============================================================
Optimized for systems with limited RAM (8GB).
Caps concurrency and enforces garbage collection.

📍 Run from: project root
Command: python scripts/phase1/extract_texts.py

Version 3.0 Changes:
- Added trial batch filtering support
- Only processes PDFs corresponding to trial batch documents
"""

import argparse
import concurrent.futures
import gc
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
import fitz  # PyMuPDF
import pandas as pd
import pymupdf4llm

# PDF Libraries
import pdfplumber
import PyPDF2

# Database
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

# ============================================================================
# CONFIGURATION & IMPORTS
# ============================================================================

# Add scripts directory to path
_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _SCRIPTS_DIR)
from config import (
    CONFIG,
    DATABASE_FILE,
    LOGS_DIR,
    PDF_DOWNLOAD_DIR,
    TRIAL_BATCH_CONFIG,
)
from gcp_secrets import get_engine
from test_run import add_test_run_arg, get_sampled_document_ids

# Import database models
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
        logging.FileHandler(LOGS_DIR / "extraction_memory_safe.log", mode="a", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

# ============================================================================
# SAFETY SETTINGS
# ============================================================================

SAFE_WORKERS = min(os.cpu_count() or 8, 16)  # Match VM vCPUs (16 on e2-standard-16, 8 on local)
PDF_TIMEOUT_SECONDS = 300  # 5 min per PDF — prevents worker hangs on corrupt/huge files

# ============================================================================
# TRIAL BATCH FILTERING
# ============================================================================


def get_trial_batch_document_ids(df=None):
    """
    Return set of Document IDs that are in the trial batch.
    Returns None if trial batch mode is disabled or if there's an error.

    INPUT:
        - df: Pre-loaded DataFrame (optional, avoids duplicate Excel read)
    """
    if not TRIAL_BATCH_CONFIG["ENABLED"]:
        logging.info("ℹ️  Trial batch mode DISABLED - will process all PDFs")
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

        # Extract Document IDs as strings (they're stored in filenames as "doc_{id}.pdf")
        doc_ids = set(trial_batch_df["Document ID"].astype(str))

        logging.info("=" * 70)
        logging.info("TRIAL BATCH FILTERING FOR TEXT EXTRACTION")
        logging.info("=" * 70)
        logging.info(f"Total documents in database:  {len(df)}")
        logging.info(f"Trial batch documents:        {len(doc_ids)}")
        logging.info(f"Will only process PDFs matching these {len(doc_ids)} Document IDs")
        logging.info("=" * 70)

        return doc_ids

    except Exception as e:
        logging.error(f"❌ Error loading trial batch filter: {e}")
        logging.error("   Proceeding without filtering")
        return None


def should_process_pdf(pdf_filename, trial_batch_ids):
    """
    Determine if a PDF should be processed based on trial batch filter.

    Args:
        pdf_filename: Name of PDF file (e.g., "doc_12345.pdf")
        trial_batch_ids: Set of Document IDs in trial batch, or None if no filtering

    Returns:
        bool: True if should process, False otherwise
    """
    if trial_batch_ids is None:
        return True  # No filtering

    # Extract document ID from filename
    doc_id = extract_document_id_from_filename(pdf_filename)
    if doc_id is None:
        return False  # Invalid filename format

    return doc_id in trial_batch_ids


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def extract_document_id_from_filename(filename):
    """
    Extract document ID from filename.
    Format: doc_{document_id}.pdf
    Note: The hash suffix (_XXXX) is part of the document ID, not separate.
    """
    if filename.startswith("doc_") and filename.endswith(".pdf"):
        # Remove 'doc_' prefix and '.pdf' suffix
        # The remaining string is the complete document ID (including hash if present)
        return filename[4:-4]
    return None


def assess_text_quality(text, page_count):
    notes = []
    words = text.split() if text else []
    word_count = len(words)
    char_count = len(text)

    avg_word_len = char_count / word_count if word_count > 0 else 0
    words_per_page = word_count / page_count if page_count > 0 else 0

    is_scanned = False
    if page_count >= 1 and word_count < CONFIG["SCANNED_PDF_THRESHOLD"]:
        is_scanned = True
        notes.append(f"Likely scanned: {word_count} words in {page_count} pages")
    elif words_per_page < 10:
        is_scanned = True
        notes.append(f"Very low density: {words_per_page:.1f} words/page")

    if word_count == 0:
        quality = "failed"
    elif is_scanned:
        quality = "poor"
    elif not (2 <= avg_word_len <= 20):
        quality = "fair"
        notes.append(f"Bad avg word length: {avg_word_len:.1f}")
    else:
        quality = "excellent"

    return {
        "quality": quality,
        "is_scanned": is_scanned,
        "word_count": word_count,
        "character_count": char_count,
        "notes": "; ".join(notes),
    }


# ============================================================================
# MARKDOWN EXTRACTION
# ============================================================================


def extract_markdown(pdf_path):
    """
    Extract Markdown-formatted text from a PDF using pymupdf4llm.

    INPUT:
        - pdf_path: Path to PDF file
    OUTPUT: Markdown string, or None on failure

    NOTE: Opens fitz.Document explicitly and passes it via doc= param
    to prevent internal handle leak (~50MB per PDF if left unclosed).
    """
    doc = None
    try:
        doc = fitz.open(str(pdf_path))
        md_text = pymupdf4llm.to_markdown(doc=doc)
        if md_text and md_text.strip():
            return md_text
        return None
    except MemoryError:
        logging.error(f"MemoryError during markdown extraction for {pdf_path}")
        gc.collect()
        return None
    except Exception as e:
        logging.debug(f"Markdown extraction failed for {pdf_path}: {e}")
        return None
    finally:
        if doc is not None:
            doc.close()
            del doc


# ============================================================================
# EXTRACTION LOGIC
# ============================================================================


def extract_text_hierarchical(pdf_path):
    path_str = str(pdf_path)

    # 1. pdfplumber (Best quality, highest memory usage)
    try:
        with pdfplumber.open(path_str) as pdf:
            text_parts = []
            for p in pdf.pages:
                txt = p.extract_text() or ""
                text_parts.append(txt)

            full_text = "\n\n".join(text_parts)
            del text_parts

            if full_text.strip():
                return {
                    "text": full_text,
                    "pages": len(pdf.pages),
                    "method": "pdfplumber",
                    "success": True,
                }
    except MemoryError:
        logging.error(f"MemoryError in pdfplumber extraction for {path_str}")
        gc.collect()
    except Exception as e:
        logging.debug(f"pdfplumber extraction failed for {path_str}: {e}")

    # 2. PyMuPDF (Fast, low memory)
    try:
        with fitz.open(path_str) as doc:
            text_parts = [page.get_text() for page in doc]
            full_text = "\n\n".join(text_parts)
            del text_parts
            if full_text.strip():
                return {"text": full_text, "pages": len(doc), "method": "pymupdf", "success": True}
    except MemoryError:
        logging.error(f"MemoryError in PyMuPDF extraction for {path_str}")
        gc.collect()
    except Exception as e:
        logging.debug(f"PyMuPDF extraction failed for {path_str}: {e}")

    # 3. PyPDF2
    try:
        reader = PyPDF2.PdfReader(path_str)
        text_parts = [p.extract_text() or "" for p in reader.pages]
        full_text = "\n\n".join(text_parts)
        del text_parts
        if full_text.strip():
            return {
                "text": full_text,
                "pages": len(reader.pages),
                "method": "pypdf2",
                "success": True,
            }
    except MemoryError:
        logging.error(f"MemoryError in PyPDF2 extraction for {path_str}")
        gc.collect()
    except Exception as e:
        logging.debug(f"PyPDF2 extraction failed for {path_str}: {e}")

    return {"text": "", "pages": 0, "method": "failed", "success": False}


# ============================================================================
# WORKER FUNCTION
# ============================================================================


def process_single_pdf_safe(args_tuple):
    """
    Worker function with aggressive memory cleanup.

    INPUT:
        - args_tuple: (pdf_path_str, format_mode) where format_mode is "markdown" or "plain"
    """
    pdf_path_str, format_mode = args_tuple
    pdf_path = Path(pdf_path_str)

    # Initialize DB connection
    try:
        local_engine = get_engine()
        LocalSession = sessionmaker(bind=local_engine)
        session = LocalSession()
    except Exception as e:
        return {"status": "db_error", "file": pdf_path.name, "error": str(e)}

    result_data = None

    try:
        # 1. Identify
        doc_id_str = extract_document_id_from_filename(pdf_path.name)
        if not doc_id_str:
            return {"status": "skipped_invalid_name", "file": pdf_path.name}

        # 2. Check DB
        document = session.query(Document).filter(Document.sabin_document_id == doc_id_str).first()
        if not document:
            return {"status": "skipped_not_in_db", "file": pdf_path.name}

        if session.query(ExtractedText).filter(ExtractedText.document_id == document.document_id).first():
            return {"status": "skipped_exists", "file": pdf_path.name}

        # 3. Extract
        extraction_result = extract_text_hierarchical(pdf_path)

        if not extraction_result["success"]:
            extracted = ExtractedText(
                document_id=document.document_id,
                raw_text="",
                extraction_quality="failed",
                extraction_date=datetime.now(),
                extraction_notes="All extraction methods failed",
            )
            session.add(extracted)
            session.commit()
            return {"status": "failed", "file": pdf_path.name}

        # 4. Assess
        quality = assess_text_quality(extraction_result["text"], extraction_result["pages"])

        # 5. Save
        document.page_count = extraction_result["pages"]
        document.pdf_file_path = str(pdf_path)
        document.pdf_downloaded = True
        try:
            document.file_size_bytes = pdf_path.stat().st_size
        except OSError:
            pass

        # 6. Markdown extraction (non-blocking)
        md_text = None
        method = extraction_result["method"]
        if format_mode == "markdown":
            md_text = extract_markdown(pdf_path)
            if md_text:
                method = f"{extraction_result['method']}+md"

        extracted = ExtractedText(
            document_id=document.document_id,
            raw_text=extraction_result["text"],
            processed_text=extraction_result["text"],
            text_md=md_text,
            word_count=quality["word_count"],
            character_count=quality["character_count"],
            extraction_date=datetime.now(),
            extraction_method=method,
            extraction_quality=quality["quality"],
            extraction_notes=quality["notes"],
        )

        session.add(extracted)
        session.commit()

        result_data = {
            "status": "success",
            "file": pdf_path.name,
            "method": method,
            "quality": quality["quality"],
            "md_success": md_text is not None,
        }
        return result_data

    except MemoryError as e:
        logging.error(f"MemoryError processing {pdf_path.name}: {e}")
        session.rollback()
        gc.collect()
        return {"status": "error", "file": pdf_path.name, "error": f"MemoryError: {e}"}

    except Exception as e:
        session.rollback()
        return {"status": "error", "file": pdf_path.name, "error": str(e)}

    finally:
        # AGGRESSIVE CLEANUP — null all large vars before GC
        session.close()
        local_engine.dispose()

        # Null out large references so GC can reclaim
        document = None  # noqa: F841
        extracted = None  # noqa: F841
        extraction_result = None  # noqa: F841
        md_text = None  # noqa: F841
        result_data = None  # noqa: F841

        gc.collect()


def _tally_result(stats, res):
    """Increment stats counters based on a single PDF result dict."""
    status = res.get("status", "error")
    if status == "success":
        stats["success"] += 1
        if res.get("md_success"):
            stats["md_success"] += 1
    elif status == "skipped_exists":
        stats["skipped_exists"] += 1
    elif status in ["skipped_invalid_name", "skipped_not_in_db"]:
        stats["skipped_invalid"] += 1
    elif status == "failed":
        stats["failed"] += 1
    elif status not in ("timeout", "error"):
        stats["errors"] += 1
        if res.get("error"):
            logging.error(f"Error: {res['error']}")


# ============================================================================
# MAIN EXECUTION
# ============================================================================


def get_decision_pdf_paths(engine):
    """Return set of PDF filenames for documents classified as decisions."""
    from sqlalchemy import text
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT pdf_file_path FROM documents "
            "WHERE is_decision = TRUE AND pdf_file_path IS NOT NULL"
        ))
        return {Path(row[0]).name for row in rows}


def process_all_pdfs(test_run=None, seed=42, format_mode="markdown", decisions_only=False):
    logging.info("=" * 70)
    logging.info(f"PDF TEXT EXTRACTION (SAFE MODE) - Workers: {SAFE_WORKERS}")
    logging.info(f"Format mode: {format_mode}")
    logging.info("=" * 70)

    if not PDF_DOWNLOAD_DIR.exists():
        logging.error(f"PDF Directory not found: {PDF_DOWNLOAD_DIR}")
        return

    # Load Excel once for all filtering
    df_excel = pd.read_excel(DATABASE_FILE)
    logging.info(f"Loaded {len(df_excel)} rows from Excel (single read)")

    # Get trial batch filter
    trial_batch_ids = get_trial_batch_document_ids(df=df_excel)

    # Get all PDF files
    all_pdf_files = list(PDF_DOWNLOAD_DIR.glob("*.pdf"))
    logging.info(f"Found {len(all_pdf_files)} PDF files in download directory")

    # Filter by trial batch if enabled
    if trial_batch_ids is not None:
        pdf_files = [f for f in all_pdf_files if should_process_pdf(f.name, trial_batch_ids)]
        excluded = len(all_pdf_files) - len(pdf_files)
        logging.info(
            f"After trial batch filter: {len(pdf_files)} files to process ({excluded} excluded)"
        )
    else:
        pdf_files = all_pdf_files

    # Filter to decisions only if requested
    if decisions_only:
        decision_filenames = get_decision_pdf_paths(get_engine())
        pre_count = len(pdf_files)
        pdf_files = [f for f in pdf_files if f.name in decision_filenames]
        logging.info(f"After --decisions-only filter: {len(pdf_files)} decision PDFs (excluded {pre_count - len(pdf_files)})")

    # Apply test-run sampling
    if test_run is not None:
        test_run_ids = get_sampled_document_ids(df_excel, test_run, seed)
        if test_run_ids is not None:
            pdf_files = [
                f for f in pdf_files
                if extract_document_id_from_filename(f.name) in test_run_ids
            ]
            logging.info(f"After test-run filter: {len(pdf_files)} files to process")

    del df_excel  # Free memory

    if len(pdf_files) == 0:
        logging.error("❌ No PDF files to process!")
        return

    logging.info(f"Processing {len(pdf_files)} files...")

    stats = {
        "success": 0, "failed": 0, "skipped_exists": 0,
        "skipped_invalid": 0, "errors": 0, "md_success": 0, "timeouts": 0,
    }

    # Process in batches with a fresh executor per batch to prevent deadlocks.
    # If all workers in a pool die (e.g., on a corrupt PDF), as_completed()
    # blocks forever. Batching isolates failures: a dead pool only loses the
    # current batch, and a new pool is created for the next one.
    BATCH_SIZE = SAFE_WORKERS * 4  # 64 PDFs per batch
    args_list = [(str(p), format_mode) for p in pdf_files]

    with tqdm(total=len(args_list), desc="Extracting (MemSafe)") as pbar:
        for batch_start in range(0, len(args_list), BATCH_SIZE):
            batch = args_list[batch_start:batch_start + BATCH_SIZE]

            try:
                with concurrent.futures.ProcessPoolExecutor(
                    max_workers=SAFE_WORKERS, max_tasks_per_child=10
                ) as executor:
                    futures = {
                        executor.submit(process_single_pdf_safe, args): args[0]
                        for args in batch
                    }

                    # Timeout for the entire batch: PDF_TIMEOUT_SECONDS per PDF in batch
                    batch_deadline = PDF_TIMEOUT_SECONDS
                    done, not_done = concurrent.futures.wait(
                        futures, timeout=batch_deadline, return_when=concurrent.futures.ALL_COMPLETED
                    )

                    # Process completed futures
                    for future in done:
                        pdf_path = futures[future]
                        try:
                            res = future.result(timeout=0)
                        except Exception as e:
                            stats["errors"] += 1
                            logging.error(f"❌ Error on {Path(pdf_path).name}: {e}")
                            res = {"status": "error", "file": Path(pdf_path).name, "error": str(e)}
                        _tally_result(stats, res)
                        pbar.update(1)

                    # Handle timed-out futures
                    if not_done:
                        timed_out_files = [Path(futures[f]).name for f in not_done]
                        stats["timeouts"] += len(not_done)
                        logging.error(
                            f"⏱️ BATCH TIMEOUT: {len(not_done)} PDFs did not finish in "
                            f"{batch_deadline}s: {timed_out_files[:5]}{'...' if len(timed_out_files) > 5 else ''}"
                        )
                        for f in not_done:
                            f.cancel()
                            pbar.update(1)

            except (concurrent.futures.BrokenExecutor, Exception) as pool_err:
                # All workers died — count entire batch as errors
                stats["errors"] += len(batch)
                logging.error(
                    f"💀 Pool crashed on batch at index {batch_start} ({type(pool_err).__name__}: {pool_err}). "
                    f"{len(batch)} PDFs lost. Restarting with fresh pool."
                )
                pbar.update(len(batch))

    logging.info("\n" + "=" * 70)
    logging.info("EXTRACTION SUMMARY")
    logging.info("=" * 70)
    logging.info(f"Successful:        {stats['success']}")
    logging.info(f"  Markdown OK:     {stats['md_success']}")
    logging.info(f"Already extracted: {stats['skipped_exists']}")
    logging.info(f"Failed:            {stats['failed']}")
    logging.info(f"Timeouts:          {stats['timeouts']}")
    logging.info(f"Errors:            {stats['errors']}")

    if TRIAL_BATCH_CONFIG["ENABLED"]:
        logging.info("\n✓ Trial batch mode was ENABLED")
        logging.info(f"  Processed {len(pdf_files)} out of {len(all_pdf_files)} total PDFs")

    logging.info("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract text from decision PDFs")
    add_test_run_arg(parser)
    parser.add_argument(
        "--format",
        choices=["markdown", "plain"],
        default="markdown",
        dest="format_mode",
        help="Text format: 'markdown' (default) adds pymupdf4llm extraction, 'plain' skips it",
    )
    parser.add_argument(
        "--decisions-only",
        action="store_true",
        help="Only extract text from documents classified as decisions",
    )
    args = parser.parse_args()

    process_all_pdfs(test_run=args.test_run, seed=args.seed, format_mode=args.format_mode, decisions_only=args.decisions_only)
