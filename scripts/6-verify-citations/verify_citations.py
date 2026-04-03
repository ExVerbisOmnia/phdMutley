#!/usr/bin/env python3
"""
Citation Verification Pipeline — Phase V
==========================================
LLM-based verification of extracted citations. For each document, sends the
full text + list of case_name identifiers to Gemini, which confirms whether
each claimed citation actually exists and returns a verbatim quote.

Decisions (from specs/phase-v-citation-verification.html):
  - Identification: case_name only (no raw_citation_text — avoids circular reliance)
  - Scope: kept citations only (11,932 in citation_extraction_phased)
  - Snippet matching: fuzzy >=95% character similarity
  - NOT_FOUND: sets requires_manual_review=True

Usage:
    python verify_citations.py                     # verify all unverified
    python verify_citations.py --concurrent 40     # VM full capacity
    python verify_citations.py --model gemini-3.1-flash-lite-preview
    python verify_citations.py --limit 50          # test batch
    python verify_citations.py --re-verify         # re-process already verified
    python verify_citations.py --dry-run           # show counts + cost estimate
    python verify_citations.py --budget 25         # halt if cost exceeds $25
"""

import argparse
import asyncio
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone

from sqlalchemy import text as sa_text, inspect as sa_inspect
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

# ============================================================================
# PATH SETUP
# ============================================================================

_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _SCRIPTS_DIR)
sys.path.insert(0, os.path.join(_SCRIPTS_DIR, "0-initialize-database"))

from config import CONFIG, LOGS_DIR
from gcp_secrets import get_engine
from gemini_client import call_gemini_async
from snippet_extractor import extract_snippet, normalize_whitespace
from text_quality import is_garbled_text
from citation_verification import (
    SingleCitationVerification,
    DocumentVerificationResponse,
    SYSTEM_INSTRUCTION,
    build_verification_prompt,
    fuzzy_match_snippet,
    MAX_SNIPPET_CHARS,
    FUZZY_THRESHOLD,
)
from init_database import (
    Base,
    CitationExtractionPhased,
    CitationExtractionPhasedSummary,
    Document,
    ExtractedText,
)

# ============================================================================
# LOGGING
# ============================================================================

LOGS_DIR.mkdir(exist_ok=True)
_log_format = "%(asctime)s - %(levelname)s - %(message)s"
_file_handler = logging.FileHandler(LOGS_DIR / "verify_citations.log", encoding="utf-8")
_file_handler.setFormatter(logging.Formatter(_log_format))
_stream_handler = logging.StreamHandler(
    open(sys.stdout.fileno(), mode="w", encoding="utf-8", errors="replace", closefd=False)
)
_stream_handler.setFormatter(logging.Formatter(_log_format))
logging.basicConfig(level=logging.INFO, handlers=[_file_handler, _stream_handler], force=True)

# ============================================================================
# GLOBAL STATE
# ============================================================================

_shutdown_requested = False

# Default model — Flash for cost-effective verification
DEFAULT_MODEL = "gemini-2.5-flash"

# Max citations per LLM call (D1)
BATCH_SIZE = 50

# Fuzzy match threshold (D3 — Issue D decision: option B)
FUZZY_THRESHOLD = 0.95

# Cost estimates per 1K tokens (input/output) for budget tracking
# Flash: $0.15/1M input, $0.60/1M output
COST_PER_1K_INPUT = 0.000150
COST_PER_1K_OUTPUT = 0.000600

    # Note: is_garbled_text, SingleCitationVerification, DocumentVerificationResponse,
    # SYSTEM_INSTRUCTION, build_verification_prompt, fuzzy_match_snippet, MAX_SNIPPET_CHARS,
    # and FUZZY_THRESHOLD are imported from shared modules (text_quality.py, citation_verification.py)


# ============================================================================
# DB MIGRATION
# ============================================================================

def run_migration(engine):
    """Add verification columns if they don't exist."""
    inspector = sa_inspect(engine)
    existing_cols = {c["name"] for c in inspector.get_columns("citation_extraction_phased")}
    v_columns = [
        ("verification_status", "VARCHAR(20)"),
        ("verification_snippet", "TEXT"),
        ("verification_notes", "TEXT"),
        ("verification_model", "VARCHAR(50)"),
        ("verified_at", "TIMESTAMP"),
    ]
    added = 0
    with engine.begin() as conn:
        for col_name, col_type in v_columns:
            if col_name not in existing_cols:
                conn.execute(sa_text(
                    f"ALTER TABLE citation_extraction_phased ADD COLUMN {col_name} {col_type}"
                ))
                added += 1
                logging.info(f"  + Added column: {col_name}")

        # Create index
        conn.execute(sa_text("""
            CREATE INDEX IF NOT EXISTS idx_cep_verification_status
            ON citation_extraction_phased(verification_status)
        """))

    if added:
        logging.info(f"Migration complete: {added} columns added")
    else:
        logging.info("Migration: all columns already exist")


# ============================================================================
# SINGLE DOCUMENT VERIFICATION
# ============================================================================

async def verify_single_document(
    doc_id,
    document_text: str,
    citations: list,
    model: str,
    stats: dict,
    lock: asyncio.Lock,
    sem: asyncio.Semaphore,
    session_factory,
    budget_limit: float | None,
):
    """
    Verify all citations for a single document.

    INPUT:
        - doc_id: UUID of the document
        - document_text: Full extracted text
        - citations: List of CitationExtractionPhased rows
        - model: Gemini model name
        - stats: Shared statistics dict (updated under lock)
        - lock: asyncio.Lock for stats updates
        - sem: asyncio.Semaphore for concurrency control
        - session_factory: SQLAlchemy session factory
        - budget_limit: Stop if cumulative cost exceeds this
    """
    async with sem:
        if _shutdown_requested:
            return

        # Check budget under lock
        if budget_limit:
            async with lock:
                if stats["cost_usd"] >= budget_limit:
                    return

        try:
            # Pre-filter: normalize line endings (#111)
            document_text = document_text.replace("\r\n", "\n").replace("\r", "\n")

            # Pre-filter: skip garbled documents (#108/#112)
            if is_garbled_text(document_text):
                logging.info(f"Skipping garbled doc {doc_id} ({len(document_text):,} chars)")
                session = session_factory()
                try:
                    now = datetime.now(timezone.utc)
                    for citation in citations:
                        session.execute(
                            sa_text("""
                                UPDATE citation_extraction_phased
                                SET verification_status = 'SKIPPED_GARBLED',
                                    verification_notes = 'Document text is garbled/corrupted — skipped to avoid hallucinations',
                                    verification_model = :model,
                                    verified_at = :now,
                                    requires_manual_review = TRUE,
                                    manual_review_reason = 'Garbled source document'
                                WHERE extraction_id = :extraction_id
                            """),
                            {"model": model, "now": now, "extraction_id": str(citation.extraction_id)},
                        )
                    session.commit()
                except Exception:
                    session.rollback()
                    raise
                finally:
                    session.close()
                async with lock:
                    stats["skipped_garbled"] = stats.get("skipped_garbled", 0) + 1
                return

            # Dynamic batch size for large documents (#121)
            # Large docs use smaller batches to stay within token limits
            doc_chars = len(document_text)
            if doc_chars > 500_000:
                effective_batch = max(5, BATCH_SIZE // 4)
            elif doc_chars > 200_000:
                effective_batch = max(10, BATCH_SIZE // 2)
            else:
                effective_batch = BATCH_SIZE

            # Batch citations (max effective_batch per call)
            batches = []
            for i in range(0, len(citations), effective_batch):
                batches.append(citations[i:i + effective_batch])

            all_verifications = {}  # extraction_id -> verification result

            for batch in batches:
                if _shutdown_requested:
                    break

                # Build prompt with case_name only (Issue B decision)
                prompt_citations = [
                    {"index": idx, "case_name": c.case_name or f"Unknown (ID: {c.extraction_id})"}
                    for idx, c in enumerate(batch)
                ]
                prompt = build_verification_prompt(document_text, prompt_citations)

                # Pre-check: estimate tokens (~4 chars/token) against 1M limit
                est_tokens = len(prompt) // 4
                if est_tokens > 900_000:
                    logging.warning(
                        f"Skipping doc {doc_id} batch — estimated {est_tokens:,} tokens "
                        f"exceeds safe threshold (doc text: {len(document_text):,} chars)"
                    )
                    async with lock:
                        stats["skipped_too_long"] += 1
                    continue

                # Call Gemini with structured output
                try:
                    result = await call_gemini_async(
                        prompt,
                        model=model,
                        temperature=0.0,
                        response_schema=DocumentVerificationResponse,
                        thinking_budget=1024,
                    )
                except Exception as e:
                    if "INVALID_ARGUMENT" in str(e) and "token" in str(e).lower():
                        logging.warning(f"Doc {doc_id}: token limit exceeded, skipping")
                        async with lock:
                            stats["skipped_too_long"] += 1
                        continue
                    raise

                # Guard against None result (e.g., all retries exhausted)
                if result is None:
                    logging.warning(f"Doc {doc_id}: API returned None, skipping batch")
                    async with lock:
                        stats["parse_errors"] += 1
                    continue

                # Track cost
                tokens_in = result.get("tokens_in", 0)
                tokens_out = result.get("tokens_out", 0)
                call_cost = (tokens_in / 1000 * COST_PER_1K_INPUT) + (tokens_out / 1000 * COST_PER_1K_OUTPUT)

                async with lock:
                    stats["cost_usd"] += call_cost
                    stats["api_calls"] += 1
                    stats["tokens_in"] += tokens_in
                    stats["tokens_out"] += tokens_out

                # Parse response
                data = result.get("data")
                if not data:
                    logging.warning(f"No structured response for doc {doc_id}, batch of {len(batch)}")
                    async with lock:
                        stats["parse_errors"] += 1
                    continue

                # Handle response: may already be dict if response_schema parsed it
                if isinstance(data, dict):
                    verifications_list = data.get("verifications", [])
                elif hasattr(data, "verifications"):
                    verifications_list = data.verifications
                else:
                    verifications_list = []

                # Map results back to citations
                for v in verifications_list:
                    if isinstance(v, dict):
                        v_index = v.get("citation_index", -1)
                        v_verdict = v.get("verdict", "NOT_FOUND")
                        v_quote = v.get("verbatim_quote")
                        v_corrected = v.get("corrected_case_name")
                        v_notes = v.get("notes")
                    else:
                        v_index = getattr(v, "citation_index", -1)
                        v_verdict = getattr(v, "verdict", "NOT_FOUND")
                        v_quote = getattr(v, "verbatim_quote", None)
                        v_corrected = getattr(v, "corrected_case_name", None)
                        v_notes = getattr(v, "notes", None)

                    if 0 <= v_index < len(batch):
                        citation = batch[v_index]
                        all_verifications[citation.extraction_id] = {
                            "verdict": v_verdict,
                            "quote": v_quote,
                            "corrected": v_corrected,
                            "notes": v_notes,
                        }

            # Update DB for all citations in this document
            session = session_factory()
            try:
                now = datetime.now(timezone.utc)
                confirmed = 0
                not_found = 0
                misattributed = 0
                snippets_improved = 0

                for citation in citations:
                    v = all_verifications.get(citation.extraction_id)

                    if not v and not all_verifications:
                        # All batches were skipped (too long) — persist status
                        session.execute(
                            sa_text("""
                                UPDATE citation_extraction_phased
                                SET verification_status = 'SKIPPED_TOO_LONG',
                                    verification_notes = :notes,
                                    verification_model = :model,
                                    verified_at = :now,
                                    requires_manual_review = TRUE,
                                    manual_review_reason = 'Document exceeds token limit'
                                WHERE extraction_id = :extraction_id
                                  AND verification_status IS NULL
                            """),
                            {
                                "notes": f"Document text {len(document_text):,} chars exceeds model context window",
                                "model": model,
                                "now": now,
                                "extraction_id": str(citation.extraction_id),
                            },
                        )
                        continue

                    if v:
                        verdict = v["verdict"]
                        quote = v["quote"]
                        notes_parts = []
                        if v["corrected"]:
                            notes_parts.append(f"Corrected: {v['corrected']}")
                        if v["notes"]:
                            notes_parts.append(v["notes"])

                        # Cap verification snippet (#120)
                        if quote and len(quote) > MAX_SNIPPET_CHARS:
                            quote = quote[:MAX_SNIPPET_CHARS]

                        # Update verification columns
                        update_vals = {
                            "verification_status": verdict,
                            "verification_snippet": quote,
                            "verification_notes": "; ".join(notes_parts) if notes_parts else None,
                            "verification_model": model,
                            "verified_at": now,
                        }

                        # For CONFIRMED with quote: try fuzzy snippet matching
                        if verdict == "CONFIRMED" and quote:
                            confirmed += 1
                            match = fuzzy_match_snippet(document_text, quote)
                            if match and match.get("found"):
                                update_vals["snippet_text"] = match["snippet"]
                                update_vals["snippet_start_char"] = match["start_char"]
                                update_vals["snippet_end_char"] = match["end_char"]
                                snippets_improved += 1

                        elif verdict == "NOT_FOUND":
                            not_found += 1
                            update_vals["requires_manual_review"] = True
                            update_vals["manual_review_reason"] = "Verification: NOT_FOUND"
                        elif verdict == "MISATTRIBUTED":
                            misattributed += 1
                            update_vals["requires_manual_review"] = True
                            update_vals["manual_review_reason"] = "Verification: MISATTRIBUTED"

                        # Build dynamic SET clause
                        set_parts = [
                            "verification_status = :verification_status",
                            "verification_snippet = :verification_snippet",
                            "verification_notes = :verification_notes",
                            "verification_model = :verification_model",
                            "verified_at = :verified_at",
                        ]
                        if "snippet_text" in update_vals:
                            set_parts.extend([
                                "snippet_text = :snippet_text",
                                "snippet_start_char = :snippet_start_char",
                                "snippet_end_char = :snippet_end_char",
                            ])
                        if "requires_manual_review" in update_vals:
                            set_parts.extend([
                                "requires_manual_review = :requires_manual_review",
                                "manual_review_reason = :manual_review_reason",
                            ])

                        session.execute(
                            sa_text(f"""
                                UPDATE citation_extraction_phased
                                SET {', '.join(set_parts)}
                                WHERE extraction_id = :extraction_id
                            """),
                            {**update_vals, "extraction_id": str(citation.extraction_id)},
                        )
                    else:
                        # No verification result (e.g., parse error)
                        session.execute(
                            sa_text("""
                                UPDATE citation_extraction_phased
                                SET verification_status = 'ERROR',
                                    verification_notes = 'No verification result returned',
                                    verification_model = :model,
                                    verified_at = :now
                                WHERE extraction_id = :extraction_id
                            """),
                            {"model": model, "now": now, "extraction_id": str(citation.extraction_id)},
                        )

                session.commit()

                async with lock:
                    stats["confirmed"] += confirmed
                    stats["not_found"] += not_found
                    stats["misattributed"] += misattributed
                    stats["snippets_improved"] += snippets_improved
                    stats["docs_processed"] += 1

                    if stats["docs_processed"] % 100 == 0:
                        logging.info(
                            f"Progress: {stats['docs_processed']} docs | "
                            f"C:{stats['confirmed']} NF:{stats['not_found']} M:{stats['misattributed']} | "
                            f"Snippets+:{stats['snippets_improved']} | "
                            f"Cost: ${stats['cost_usd']:.2f}"
                        )

            except Exception as e:
                session.rollback()
                raise
            finally:
                session.close()

        except Exception as e:
            logging.error(f"Error verifying doc {doc_id}: {e}")
            async with lock:
                stats["errors"] += 1


# ============================================================================
# MAIN
# ============================================================================

def main():
    global _shutdown_requested

    parser = argparse.ArgumentParser(description="Verify citations via LLM")
    parser.add_argument("--concurrent", type=int, default=25, help="Concurrency level (default: 25)")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help=f"Gemini model (default: {DEFAULT_MODEL})")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of documents to process")
    parser.add_argument("--re-verify", action="store_true", help="Re-process already verified citations")
    parser.add_argument("--dry-run", action="store_true", help="Show counts and cost estimate, don't process")
    parser.add_argument("--budget", type=float, default=None, help="Halt if cost exceeds this amount (USD)")
    args = parser.parse_args()

    logging.info("=" * 70)
    logging.info("PHASE V: CITATION VERIFICATION PIPELINE")
    logging.info("=" * 70)
    logging.info(f"Model: {args.model}")
    logging.info(f"Concurrency: {args.concurrent}")
    logging.info(f"Budget limit: {'$' + str(args.budget) if args.budget else 'none'}")
    logging.info(f"Re-verify: {args.re_verify}")

    # Connect and migrate
    engine = get_engine()
    run_migration(engine)

    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    try:
        # Query documents with unverified citations
        logging.info("\nQuerying documents with citations to verify...")

        if args.re_verify:
            # All documents with citations
            doc_ids_query = session.query(
                CitationExtractionPhased.document_id
            ).distinct()
        else:
            # Only unverified
            doc_ids_query = session.query(
                CitationExtractionPhased.document_id
            ).filter(
                CitationExtractionPhased.verification_status.is_(None)
            ).distinct()

        doc_ids = [row[0] for row in doc_ids_query.all()]

        if args.limit:
            doc_ids = doc_ids[:args.limit]

        # Count citations
        if args.re_verify:
            total_citations = session.query(CitationExtractionPhased).filter(
                CitationExtractionPhased.document_id.in_(doc_ids)
            ).count()
        else:
            total_citations = session.query(CitationExtractionPhased).filter(
                CitationExtractionPhased.document_id.in_(doc_ids),
                CitationExtractionPhased.verification_status.is_(None),
            ).count()

        logging.info(f"Documents to verify: {len(doc_ids)}")
        logging.info(f"Citations to verify: {total_citations}")

        if len(doc_ids) == 0:
            logging.info("Nothing to verify!")
            return

        # Estimate cost
        # Avg doc ~4K tokens input + 50 citations * 20 tokens each = ~5K input
        # Output: ~50 citations * 100 tokens = ~5K output per doc
        est_input_tokens = len(doc_ids) * 5000
        est_output_tokens = len(doc_ids) * 5000
        est_cost = (est_input_tokens / 1000 * COST_PER_1K_INPUT) + (est_output_tokens / 1000 * COST_PER_1K_OUTPUT)
        logging.info(f"Estimated cost: ${est_cost:.2f}")

        if args.dry_run:
            logging.info("\n--- DRY RUN — no processing ---")
            logging.info(f"Would verify {total_citations} citations across {len(doc_ids)} documents")
            logging.info(f"Estimated API calls: {sum(1 + (total_citations // BATCH_SIZE) for _ in range(len(doc_ids)))}")
            logging.info(f"Estimated cost: ${est_cost:.2f}")
            return

        # Pre-load all document data to avoid per-doc queries in async context
        logging.info("\nLoading document texts and citations...")
        doc_data = {}
        for doc_id in tqdm(doc_ids, desc="Loading documents"):
            # Get text
            text_row = session.query(ExtractedText.raw_text).filter(
                ExtractedText.document_id == doc_id
            ).first()
            if not text_row or not text_row[0]:
                continue

            # Get citations
            if args.re_verify:
                cit_query = session.query(CitationExtractionPhased).filter(
                    CitationExtractionPhased.document_id == doc_id
                )
            else:
                cit_query = session.query(CitationExtractionPhased).filter(
                    CitationExtractionPhased.document_id == doc_id,
                    CitationExtractionPhased.verification_status.is_(None),
                )
            citations = cit_query.all()
            if citations:
                # Detach from session so they're safe to use in async
                session.expunge_all()
                doc_data[doc_id] = {
                    "text": text_row[0],
                    "citations": citations,
                }

        logging.info(f"Loaded {len(doc_data)} documents with text and citations")
        session.close()

        # Create concurrent engine
        concurrent_engine = get_engine(pool_size=args.concurrent + 5, max_overflow=10)
        Base.metadata.create_all(concurrent_engine)
        ConcurrentSessionFactory = sessionmaker(bind=concurrent_engine)

        # Statistics
        stats = {
            "docs_processed": 0,
            "confirmed": 0,
            "not_found": 0,
            "misattributed": 0,
            "snippets_improved": 0,
            "errors": 0,
            "parse_errors": 0,
            "skipped_too_long": 0,
            "skipped_garbled": 0,
            "cost_usd": 0.0,
            "api_calls": 0,
            "tokens_in": 0,
            "tokens_out": 0,
        }

        # Async processing
        async def run_concurrent():
            sem = asyncio.Semaphore(args.concurrent)
            lock = asyncio.Lock()
            pbar = tqdm(total=len(doc_data), desc="Verifying Documents")

            async def process_one(doc_id, data):
                if _shutdown_requested:
                    pbar.update(1)
                    return
                await verify_single_document(
                    doc_id=doc_id,
                    document_text=data["text"],
                    citations=data["citations"],
                    model=args.model,
                    stats=stats,
                    lock=lock,
                    sem=sem,
                    session_factory=ConcurrentSessionFactory,
                    budget_limit=args.budget,
                )
                pbar.update(1)

            results = await asyncio.gather(
                *[process_one(did, dd) for did, dd in doc_data.items()],
                return_exceptions=True,
            )
            pbar.close()

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logging.error(f"Unhandled exception: {result}")

        # Graceful shutdown
        original_sigint = signal.getsignal(signal.SIGINT)

        def _handle_sigint(sig, frame):
            global _shutdown_requested
            if _shutdown_requested:
                logging.warning("Force shutdown requested")
                raise KeyboardInterrupt
            _shutdown_requested = True
            logging.warning("Shutdown requested — completing in-progress documents...")

        signal.signal(signal.SIGINT, _handle_sigint)
        start_time = time.time()

        try:
            asyncio.run(run_concurrent())
        finally:
            signal.signal(signal.SIGINT, original_sigint)
            concurrent_engine.dispose()

        elapsed = time.time() - start_time

        # Final report
        logging.info("\n" + "=" * 70)
        logging.info("VERIFICATION COMPLETE — FINAL REPORT")
        logging.info("=" * 70)
        logging.info(f"Documents processed:    {stats['docs_processed']}")
        logging.info(f"CONFIRMED:              {stats['confirmed']}")
        logging.info(f"NOT_FOUND:              {stats['not_found']}")
        logging.info(f"MISATTRIBUTED:          {stats['misattributed']}")
        logging.info(f"Snippets improved:      {stats['snippets_improved']}")
        logging.info(f"Errors:                 {stats['errors']}")
        logging.info(f"Parse errors:           {stats['parse_errors']}")
        logging.info(f"Skipped (too long):     {stats['skipped_too_long']}")
        logging.info(f"Skipped (garbled):      {stats['skipped_garbled']}")
        logging.info("")
        logging.info(f"API calls:              {stats['api_calls']}")
        logging.info(f"Tokens (in/out):        {stats['tokens_in']:,} / {stats['tokens_out']:,}")
        logging.info(f"Total cost:             ${stats['cost_usd']:.4f}")
        logging.info(f"Elapsed time:           {elapsed:.1f}s ({elapsed/60:.1f}min)")
        logging.info("=" * 70)

    except Exception as e:
        logging.error(f"Fatal error: {e}")
        import traceback
        logging.error(traceback.format_exc())
        sys.exit(1)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
