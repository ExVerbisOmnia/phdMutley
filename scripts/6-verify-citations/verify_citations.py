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
import difflib
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone

from pydantic import BaseModel
from typing import Literal

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

# Default model — Flash-Lite for cost efficiency
DEFAULT_MODEL = "gemini-3.1-flash-lite-preview"

# Max citations per LLM call (D1)
BATCH_SIZE = 50

# Fuzzy match threshold (D3 — Issue D decision: option B)
FUZZY_THRESHOLD = 0.95

# Cost estimates per 1K tokens (input/output) for budget tracking
# Flash-Lite: $0.075/1M input, $0.30/1M output
COST_PER_1K_INPUT = 0.000075
COST_PER_1K_OUTPUT = 0.000300

# Max snippet length to store (prevents bloated DB rows)
MAX_SNIPPET_CHARS = 2000

# Garbled text detection thresholds
GARBLED_ALPHA_RATIO_MIN = 0.40  # At least 40% alphabetic characters
GARBLED_AVG_WORD_LEN_MAX = 25   # Average word length under 25 chars


def is_garbled_text(text: str) -> bool:
    """
    Detect garbled/corrupted OCR text that would cause LLM hallucinations.

    INPUT: Document text string
    ALGORITHM:
        1. Check alphabetic character ratio (garbled text has many symbols/digits)
        2. Check average word length (garbled OCR produces long "words")
        3. Sample first 5000 chars for efficiency
    OUTPUT: True if text appears garbled, False if readable
    """
    if not text or len(text) < 100:
        return True  # Too short to be a real document

    sample = text[:5000]

    # Check 1: Alphabetic ratio
    alpha_count = sum(1 for c in sample if c.isalpha())
    alpha_ratio = alpha_count / len(sample)
    if alpha_ratio < GARBLED_ALPHA_RATIO_MIN:
        return True

    # Check 2: Average word length
    words = sample.split()
    if words:
        avg_word_len = sum(len(w) for w in words) / len(words)
        if avg_word_len > GARBLED_AVG_WORD_LEN_MAX:
            return True

    return False


# ============================================================================
# PYDANTIC SCHEMAS — Structured Output (3a)
# ============================================================================

class SingleCitationVerification(BaseModel):
    citation_index: int
    verdict: Literal["CONFIRMED", "NOT_FOUND", "MISATTRIBUTED"]
    verbatim_quote: str | None = None
    corrected_case_name: str | None = None
    notes: str | None = None


class DocumentVerificationResponse(BaseModel):
    verifications: list[SingleCitationVerification]


# ============================================================================
# PROMPT BUILDER (3b)
# ============================================================================

SYSTEM_INSTRUCTION = """You are a legal citation verification assistant. Your task is to verify
whether specific court cases are actually cited in a judicial document.

RULES:
1. For each case name provided, search the document for ANY reference to that case.
2. If found, set verdict to "CONFIRMED" and provide a verbatim_quote that is an EXACT
   copy-paste substring from the document (1-3 sentences around the citation). Do NOT
   paraphrase or normalize — the quote must appear character-for-character in the document.
3. If the case name is not found anywhere in the document, set verdict to "NOT_FOUND".
4. If the document references a similarly-named but different case, set verdict to
   "MISATTRIBUTED" and provide the corrected_case_name.
5. If a case is cited multiple times, return the FIRST occurrence's verbatim quote.
6. The verbatim_quote MUST be a direct substring of the source document text."""


def build_verification_prompt(document_text: str, citations: list[dict]) -> str:
    """
    Build the verification prompt for a batch of citations.

    INPUT:
        - document_text: Full extracted text of the source document
        - citations: List of dicts with 'index' and 'case_name' keys
    OUTPUT: Formatted prompt string
    """
    citation_list = "\n".join(
        f"[{c['index']}] {c['case_name']}"
        for c in citations
    )

    return f"""{SYSTEM_INSTRUCTION}

--- DOCUMENT TEXT ---
{document_text}

--- CITATIONS TO VERIFY ---
{citation_list}

For each citation above, provide your verification result."""


# ============================================================================
# FUZZY SNIPPET MATCHING (Issue D — option B: >=95% similarity)
# ============================================================================

def fuzzy_match_snippet(document_text: str, verbatim_quote: str) -> dict | None:
    """
    Try to find verbatim_quote in document_text using fuzzy matching.

    INPUT:
        - document_text: Full document text
        - verbatim_quote: LLM-provided quote to locate
    OUTPUT: Snippet dict from extract_snippet if match found, else None

    ALGORITHM:
        1. Try exact match via extract_snippet (tier 1-3)
        2. If not found, use SequenceMatcher sliding window for fuzzy match
        3. Accept if ratio >= FUZZY_THRESHOLD (0.95)
    """
    if not verbatim_quote or not document_text:
        return None

    # Cap verbatim_quote length (#120)
    if len(verbatim_quote) > MAX_SNIPPET_CHARS:
        verbatim_quote = verbatim_quote[:MAX_SNIPPET_CHARS]

    # Tier 1: Try existing extract_snippet (exact / normalized / key phrase)
    result = extract_snippet(document_text, verbatim_quote)
    if result.get("found"):
        # Cap snippet text (#120)
        if result.get("snippet") and len(result["snippet"]) > MAX_SNIPPET_CHARS:
            result["snippet"] = result["snippet"][:MAX_SNIPPET_CHARS]
        return result

    # Tier 1.5: Whitespace-normalized matching (#119)
    # LLM often normalizes whitespace in quotes — try matching after normalization
    norm_doc = normalize_whitespace(document_text)
    norm_quote = normalize_whitespace(verbatim_quote)
    pos = norm_doc.find(norm_quote)
    if pos != -1:
        # Found in normalized text — map back to approximate original position
        # Use ratio-based mapping (fast approximation)
        ratio = pos / max(len(norm_doc), 1)
        approx_start = int(ratio * len(document_text))
        # Search nearby in original for a close match
        search_start = max(0, approx_start - 200)
        search_end = min(len(document_text), approx_start + len(verbatim_quote) + 200)
        search_region = document_text[search_start:search_end]
        # Find best substring match in the region
        norm_search = normalize_whitespace(search_region)
        local_pos = norm_search.find(norm_quote)
        if local_pos != -1:
            local_ratio = local_pos / max(len(norm_search), 1)
            est_start = search_start + int(local_ratio * len(search_region))
            est_end = min(len(document_text), est_start + len(verbatim_quote) + 50)
            ctx_start = max(0, est_start - 300)
            ctx_end = min(len(document_text), est_end + 300)
            snippet = document_text[ctx_start:ctx_end]
            if len(snippet) > MAX_SNIPPET_CHARS:
                snippet = snippet[:MAX_SNIPPET_CHARS]
            return {
                "found": True,
                "match_type": "whitespace_normalized",
                "start_char": est_start,
                "end_char": est_end,
                "matched_text": document_text[est_start:est_end][:200],
                "snippet": snippet,
                "snippet_start": ctx_start,
                "snippet_end": ctx_end,
            }

    # Tier 2: Sliding window fuzzy match
    quote_len = len(verbatim_quote)
    if quote_len < 20:
        return None  # Too short for reliable fuzzy matching

    best_ratio = 0.0
    best_start = 0

    # Slide window across document (step by 1/4 of quote length for speed)
    step = max(1, quote_len // 4)
    for i in range(0, len(document_text) - quote_len + 1, step):
        candidate = document_text[i:i + quote_len]
        ratio = difflib.SequenceMatcher(None, verbatim_quote, candidate).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_start = i

    # Refine: search around best_start with step=1
    if best_ratio >= FUZZY_THRESHOLD - 0.05:
        refine_start = max(0, best_start - step)
        refine_end = min(len(document_text) - quote_len + 1, best_start + step)
        for i in range(refine_start, refine_end):
            candidate = document_text[i:i + quote_len]
            ratio = difflib.SequenceMatcher(None, verbatim_quote, candidate).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_start = i

    if best_ratio >= FUZZY_THRESHOLD:
        matched_text = document_text[best_start:best_start + quote_len]
        # Build snippet with context
        ctx_start = max(0, best_start - 300)
        ctx_end = min(len(document_text), best_start + quote_len + 300)
        snippet = document_text[ctx_start:ctx_end]
        if len(snippet) > MAX_SNIPPET_CHARS:
            snippet = snippet[:MAX_SNIPPET_CHARS]
        return {
            "found": True,
            "match_type": f"fuzzy_{best_ratio:.3f}",
            "start_char": best_start,
            "end_char": best_start + quote_len,
            "matched_text": matched_text[:200],
            "snippet": snippet,
            "snippet_start": ctx_start,
            "snippet_end": ctx_end,
        }

    return None


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
                    )
                except Exception as e:
                    if "INVALID_ARGUMENT" in str(e) and "token" in str(e).lower():
                        logging.warning(f"Doc {doc_id}: token limit exceeded, skipping")
                        async with lock:
                            stats["skipped_too_long"] += 1
                        continue
                    raise

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
