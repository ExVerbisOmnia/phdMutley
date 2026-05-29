#!/usr/bin/env python3
"""
Classify Ambiguous Documents (Steps B + C)
==========================================
Uses LLM partial-text analysis to classify documents whose is_decision is NULL,
then bulk-defaults any remaining unclassified documents to non-decisions.

Step B: For each NULL document, extract head+tail text from PDF and ask Gemini
        whether it is a judicial decision.
Step C: Bulk-update any still-NULL documents to is_decision=FALSE (epilogue).

VERSION: 2.0 — Async parallelized (25 concurrent Gemini calls)
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import pdfplumber
from sqlalchemy import text as sa_text
from sqlalchemy.orm import sessionmaker

# ============================================================================
# CONFIGURATION & IMPORTS
# ============================================================================

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPTS_DIR)
from config import CONFIG, DATABASE_FILE, LOGS_DIR, PDF_DOWNLOAD_DIR
from gcp_secrets import get_engine
from gemini_client import call_gemini, call_gemini_async
from pipeline_status import PipelineStatus
from test_run import add_test_run_arg, get_sampled_document_ids

sys.path.insert(0, os.path.join(_SCRIPTS_DIR, "0-initialize-database"))
from init_database import Document

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    force=True,
    handlers=[
        logging.FileHandler(LOGS_DIR / "classify_ambiguous_docs.log", encoding="utf-8"),
        logging.StreamHandler(
            open(sys.stdout.fileno(), mode="w", encoding="utf-8", errors="replace", closefd=False)
        ),
    ],
)
logging.getLogger("httpx").setLevel(logging.WARNING)


# ============================================================================
# PDF TEXT EXTRACTION
# ============================================================================


def extract_partial_text_from_pdf(pdf_path, head_chars=2400, tail_chars=2400):
    """
    Extract head and tail text from a PDF for classification.

    INPUT:
        - pdf_path: Path to the PDF file
        - head_chars: Characters to take from the beginning
        - tail_chars: Characters to take from the end
    ALGORITHM:
        1. Open PDF with pdfplumber
        2. Extract text from first 2 pages (head)
        3. Extract text from last 2 pages (tail)
        4. Combine as head[:head_chars] + separator + tail[-tail_chars:]
    OUTPUT: Combined partial text string, or None on error
    """
    pdf = None
    try:
        pdf = pdfplumber.open(pdf_path)
        pages = pdf.pages
        if not pages:
            return None

        # Head: first 2 pages
        head_text = ""
        for p in pages[:2]:
            t = p.extract_text()
            if t:
                head_text += t + "\n"

        # Tail: last 2 pages (avoid overlap if <= 2 pages total)
        tail_text = ""
        if len(pages) > 2:
            for p in pages[-2:]:
                t = p.extract_text()
                if t:
                    tail_text += t + "\n"

        if not head_text.strip() and not tail_text.strip():
            return None

        first = head_text[:head_chars]
        last = tail_text[-tail_chars:] if tail_text else ""

        if last:
            return first + "\n...\n" + last
        return first

    except Exception as e:
        logging.warning(f"PDF extraction failed for {pdf_path}: {e}")
        return None
    finally:
        if pdf is not None:
            pdf.close()


# ============================================================================
# LLM CLASSIFICATION
# ============================================================================


def build_classification_prompt(partial_text, doc_title, doc_type):
    """
    Build the Gemini classification prompt.

    INPUT:
        - partial_text: Head+tail excerpt from the PDF
        - doc_title: Document title from metadata
        - doc_type: Document type from metadata
    OUTPUT: Prompt string
    """
    return f"""You are an expert legal document classifier specializing in judicial decisions worldwide.

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

<output_format>
Return ONLY valid JSON with no additional text or markdown:
{{"is_judicial_decision": true, "confidence_score": 0.95}}

CRITICAL: Output ONLY the JSON object. No markdown, no code blocks, no explanatory text.
</output_format>

<document_excerpt>
{partial_text}
</document_excerpt>"""


def classify_with_llm(partial_text, doc_title, doc_type):
    """
    Use Gemini to classify whether a document is a judicial decision (sync version).

    INPUT:
        - partial_text: Head+tail excerpt from the PDF
        - doc_title: Document title from metadata
        - doc_type: Document type from metadata
    OUTPUT: (is_decision, confidence, tokens_in, tokens_out) or (None, None, 0, 0) on error
    """
    prompt = build_classification_prompt(partial_text, doc_title, doc_type)

    try:
        import time
        time.sleep(0.5)  # Rate limiting for sync usage

        result = call_gemini(
            prompt,
            model=CONFIG["CLASSIFICATION_MODEL"],
            max_output_tokens=1024,
        )

        data = result["data"]
        if not data:
            logging.error(f"Failed to parse classification JSON. Response: {result['text'][:300]}")
            return None, None, result.get("tokens_in", 0), result.get("tokens_out", 0)

        is_decision = data.get("is_judicial_decision", False)
        confidence = data.get("confidence_score", 0.0)

        return is_decision, confidence, result["tokens_in"], result["tokens_out"]

    except Exception as e:
        logging.error(f"LLM classification error: {e}")
        return None, None, 0, 0


async def classify_with_llm_async(partial_text, doc_title, doc_type, semaphore):
    """
    Async version: classify a document via Gemini with concurrency control.

    INPUT:
        - partial_text: Head+tail excerpt from the PDF
        - doc_title, doc_type: Document metadata
        - semaphore: asyncio.Semaphore for concurrency control
    OUTPUT: (is_decision, confidence, tokens_in, tokens_out) or (None, None, 0, 0) on error
    """
    async with semaphore:
        prompt = build_classification_prompt(partial_text, doc_title, doc_type)
        try:
            result = await call_gemini_async(
                prompt,
                model=CONFIG["CLASSIFICATION_MODEL"],
                max_output_tokens=1024,
            )

            data = result["data"]
            if not data:
                logging.error(f"Failed to parse classification JSON. Response: {result['text'][:300]}")
                return None, None, result.get("tokens_in", 0), result.get("tokens_out", 0)

            is_decision = data.get("is_judicial_decision", False)
            confidence = data.get("confidence_score", 0.0)

            return is_decision, confidence, result["tokens_in"], result["tokens_out"]

        except Exception as e:
            logging.error(f"LLM classification error: {e}")
            return None, None, 0, 0


# ============================================================================
# ASYNC BATCH ORCHESTRATOR
# ============================================================================


async def classify_batch_async(doc_infos: list[dict], concurrency: int = 25) -> list[dict]:
    """
    Run LLM classification for a batch of documents concurrently.

    INPUT:
        - doc_infos: List of dicts with keys: doc_id, partial_text, title, dtype
        - concurrency: Max concurrent API calls (default 25 → ~100 RPM)
    OUTPUT: List of result dicts with keys: doc_id, is_decision, confidence, tokens_in, tokens_out, error
    """
    semaphore = asyncio.Semaphore(concurrency)
    completed = 0
    total = len(doc_infos)

    async def classify_one(info):
        nonlocal completed
        is_decision, confidence, tokens_in, tokens_out = await classify_with_llm_async(
            info["partial_text"], info["title"], info["dtype"], semaphore
        )
        completed += 1
        if completed % 50 == 0:
            logging.info(f"  Phase 2 progress: {completed}/{total} API calls completed")
        return {
            "doc_id": info["doc_id"],
            "is_decision": is_decision,
            "confidence": confidence,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        }

    tasks = [classify_one(info) for info in doc_infos]
    return await asyncio.gather(*tasks)


# ============================================================================
# STEP C: AGGREGATE UNCLASSIFIED
# ============================================================================


def aggregate_unclassified(session):
    """
    Bulk-default all remaining unclassified documents to non-decisions.

    INPUT:
        - session: SQLAlchemy session
    ALGORITHM:
        1. UPDATE documents SET is_decision=FALSE WHERE is_decision IS NULL
        2. Set method='unclassified_default', confidence=0.0, date=now()
        3. Commit and return count of affected rows
    OUTPUT: Number of rows updated
    """
    result = session.execute(
        sa_text("""
            UPDATE documents
            SET is_decision = FALSE,
                decision_classification_method = 'unclassified_default',
                decision_classification_confidence = 0.0,
                decision_classification_date = :now
            WHERE is_decision IS NULL
        """),
        {"now": datetime.now()},
    )
    session.commit()
    return result.rowcount


# ============================================================================
# MAIN EXECUTION
# ============================================================================


def main(test_run=None, seed=42):
    """
    Classify ambiguous documents via LLM partial-text analysis (Steps B+C).
    3-phase architecture: Preparation → Async API calls → DB commits.

    INPUT:
        - test_run: Number of documents to sample (None = all)
        - seed: Random seed for reproducible sampling
    """
    logging.info("=" * 70)
    logging.info("CLASSIFY AMBIGUOUS DOCUMENTS - Steps B + C (async)")
    logging.info(f"Classification Model: {CONFIG['CLASSIFICATION_MODEL']}")
    logging.info("=" * 70)

    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    stats = {
        "decisions_llm": 0,
        "non_decisions_llm": 0,
        "no_pdf": 0,
        "extraction_failed": 0,
        "llm_errors": 0,
        "errors": 0,
        "unclassified_defaulted": 0,
        "total_tokens_in": 0,
        "total_tokens_out": 0,
    }

    try:
        # Query documents with is_decision IS NULL
        query = session.query(Document).filter(Document.is_decision.is_(None))

        # Apply test-run sampling if requested
        if test_run is not None:
            logging.info(f"Test-run mode: sampling {test_run} documents (seed={seed})")
            df_excel = pd.read_excel(DATABASE_FILE)
            test_ids = get_sampled_document_ids(df_excel, test_run, seed)
            del df_excel
            if test_ids is not None:
                query = query.filter(Document.sabin_document_id.in_(test_ids))

        documents = query.all()
        total = len(documents)
        logging.info(f"Found {total} unclassified documents to process")

        status = PipelineStatus("step-b")

        if total == 0:
            logging.info("No unclassified documents found. Skipping to Step C.")
        else:
            # ==================================================================
            # PHASE 1: Preparation (synchronous) — PDF extraction, filter docs
            # ==================================================================
            logging.info("")
            logging.info("=" * 70)
            logging.info("PHASE 1: Preparation — PDF extraction & filtering")
            logging.info("=" * 70)

            docs_for_llm = []  # List of dicts for async processing
            doc_map = {}       # doc_id -> ORM Document object

            for i, doc in enumerate(documents, 1):
                try:
                    # Extract metadata
                    title = ""
                    dtype = ""
                    if doc.metadata_data:
                        title = doc.metadata_data.get("document_title", "") or ""
                        dtype = doc.metadata_data.get("document_type", "") or ""

                    # Check PDF availability (resolve cross-platform paths)
                    pdf_path = doc.pdf_file_path
                    resolved = False
                    if pdf_path:
                        # Always try local resolution by filename first (handles
                        # Windows paths stored in DB when running on Linux VM)
                        filename = Path(pdf_path.replace("\\", "/")).name
                        candidate = PDF_DOWNLOAD_DIR / filename
                        if candidate.exists():
                            pdf_path = str(candidate)
                            resolved = True
                        elif not resolved:
                            try:
                                if Path(pdf_path).exists():
                                    resolved = True
                            except OSError:
                                pass  # e.g. filename too long on Linux
                    if not pdf_path or not resolved:
                        doc.is_decision = False
                        doc.decision_classification_method = "no_pdf"
                        doc.decision_classification_confidence = 0.5
                        doc.decision_classification_date = datetime.now()
                        session.commit()
                        stats["no_pdf"] += 1
                        if i % 100 == 0 or i <= 5:
                            logging.info(f"  [{i}/{total}] No PDF: {doc.sabin_document_id}")
                        continue

                    # Extract partial text from PDF
                    partial_text = extract_partial_text_from_pdf(pdf_path)
                    if not partial_text:
                        doc.is_decision = False
                        doc.decision_classification_method = "extraction_failed"
                        doc.decision_classification_confidence = 0.5
                        doc.decision_classification_date = datetime.now()
                        session.commit()
                        stats["extraction_failed"] += 1
                        if i % 100 == 0 or i <= 5:
                            logging.info(f"  [{i}/{total}] Extraction failed: {doc.sabin_document_id}")
                        continue

                    # Queue for async LLM classification
                    doc_id = doc.sabin_document_id
                    docs_for_llm.append({
                        "doc_id": doc_id,
                        "partial_text": partial_text,
                        "title": title,
                        "dtype": dtype,
                    })
                    doc_map[doc_id] = doc

                except Exception as e:
                    session.rollback()
                    stats["errors"] += 1
                    logging.error(f"  [{i}/{total}] Error preparing {doc.sabin_document_id}: {e}")

            logging.info(f"Phase 1 complete: {len(docs_for_llm)} docs queued for LLM, "
                         f"{stats['no_pdf']} no-PDF, {stats['extraction_failed']} extraction-failed, "
                         f"{stats['errors']} errors")

            # ==================================================================
            # PHASE 2: Async API calls — all Gemini calls happen here
            # ==================================================================
            if docs_for_llm:
                logging.info("")
                logging.info("=" * 70)
                logging.info(f"PHASE 2: Async LLM classification — {len(docs_for_llm)} docs, concurrency=25")
                logging.info("=" * 70)

                results = asyncio.run(classify_batch_async(docs_for_llm, concurrency=25))

                # ==============================================================
                # PHASE 3: DB commits (synchronous) — batch update from results
                # ==============================================================
                logging.info("")
                logging.info("=" * 70)
                logging.info("PHASE 3: DB commits")
                logging.info("=" * 70)

                batch_count = 0
                for r in results:
                    doc = doc_map[r["doc_id"]]
                    stats["total_tokens_in"] += r["tokens_in"]
                    stats["total_tokens_out"] += r["tokens_out"]

                    if r["is_decision"] is None:
                        doc.is_decision = False
                        doc.decision_classification_method = "llm_error"
                        doc.decision_classification_confidence = 0.3
                        doc.decision_classification_date = datetime.now()
                        stats["llm_errors"] += 1
                    else:
                        doc.is_decision = r["is_decision"]
                        doc.decision_classification_method = "llm_partial_text"
                        doc.decision_classification_confidence = r["confidence"]
                        doc.decision_classification_date = datetime.now()
                        if r["is_decision"]:
                            stats["decisions_llm"] += 1
                        else:
                            stats["non_decisions_llm"] += 1

                    batch_count += 1
                    if batch_count % 50 == 0:
                        session.commit()
                        status.update(
                            processed=stats["no_pdf"] + stats["extraction_failed"] + batch_count,
                            total=total,
                            errors=stats["llm_errors"] + stats["errors"],
                            decisions_llm=stats["decisions_llm"],
                            non_decisions_llm=stats["non_decisions_llm"],
                            no_pdf=stats["no_pdf"],
                        )
                        logging.info(f"  Committed batch {batch_count}/{len(results)}")

                # Final commit for remainder
                session.commit()
                logging.info(f"Phase 3 complete: {batch_count} results committed")

        # Step C: aggregate unclassified
        logging.info("")
        logging.info("=" * 70)
        logging.info("STEP C: Aggregate Unclassified Documents")
        logging.info("=" * 70)
        defaulted = aggregate_unclassified(session)
        stats["unclassified_defaulted"] = defaulted
        logging.info(f"Defaulted {defaulted} remaining documents to non-decision")

        # Summary
        logging.info("")
        logging.info("=" * 70)
        logging.info("CLASSIFICATION SUMMARY (Steps B + C)")
        logging.info("=" * 70)
        logging.info(f"Decisions (LLM):         {stats['decisions_llm']}")
        logging.info(f"Non-decisions (LLM):     {stats['non_decisions_llm']}")
        logging.info(f"No PDF available:        {stats['no_pdf']}")
        logging.info(f"Extraction failed:       {stats['extraction_failed']}")
        logging.info(f"LLM errors:              {stats['llm_errors']}")
        logging.info(f"Other errors:            {stats['errors']}")
        logging.info(f"Unclassified defaulted:  {stats['unclassified_defaulted']}")
        logging.info(f"Total tokens in:         {stats['total_tokens_in']:,}")
        logging.info(f"Total tokens out:        {stats['total_tokens_out']:,}")

        # Cost estimate (Gemini Flash pricing: $0.075/1M input, $0.30/1M output)
        cost_in = stats["total_tokens_in"] * 0.075 / 1_000_000
        cost_out = stats["total_tokens_out"] * 0.30 / 1_000_000
        logging.info(f"Estimated cost:          ${cost_in + cost_out:.4f}")
        logging.info("=" * 70)

        status.update(processed=total, total=total, errors=stats["errors"])
        status.complete(
            cost_usd=round(cost_in + cost_out, 4),
            **{k: v for k, v in stats.items() if k != "total_tokens_in" and k != "total_tokens_out"},
        )

    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Classify ambiguous documents via LLM (Steps B+C)")
    add_test_run_arg(parser)
    args = parser.parse_args()
    main(test_run=args.test_run, seed=args.seed)
