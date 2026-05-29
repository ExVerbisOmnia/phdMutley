"""
Citation Verification — Shared Verification Logic
===================================================
Extracted from verify_citations.py for reuse by both the standalone
verification pipeline and the inline verification in extract_citations.py.

Provides:
- Pydantic schemas for structured LLM output
- Verification prompt builder
- Fuzzy snippet matching (4-tier: exact → normalized → whitespace → sliding window)
- Inline verification function for use during extraction

VERSION: 1.0
"""

import difflib
import logging
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel

from snippet_extractor import extract_snippet, normalize_whitespace

logger = logging.getLogger(__name__)

# Max snippet length to store (prevents bloated DB rows)
MAX_SNIPPET_CHARS = 2000

# Fuzzy match threshold (D3 — Issue D decision: option B)
FUZZY_THRESHOLD = 0.95


# ============================================================================
# PYDANTIC SCHEMAS — Structured Output
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
# PROMPT BUILDER
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
6. The verbatim_quote MUST be a direct substring of the source document text.
7. A keyword match alone is NOT sufficient — verify that the case is being CITED as
   legal authority, not merely mentioned in passing or in an unrelated context. For
   example, "Wells" matching "exploratory wells" is NOT a citation to R(Wells) v
   Secretary of State. The reference must be to a JUDICIAL DECISION.
8. The citation context must be appropriate — look for footnotes, case law sections,
   "see also" references, party names in case captions, etc."""


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
# FUZZY SNIPPET MATCHING (4-tier)
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
        2. Whitespace-normalized matching
        3. Sliding window fuzzy match (SequenceMatcher)
        4. Accept if ratio >= FUZZY_THRESHOLD (0.95)
    """
    if not verbatim_quote or not document_text:
        return None

    # Cap verbatim_quote length
    if len(verbatim_quote) > MAX_SNIPPET_CHARS:
        verbatim_quote = verbatim_quote[:MAX_SNIPPET_CHARS]

    # Tier 1: Try existing extract_snippet (exact / normalized / key phrase)
    result = extract_snippet(document_text, verbatim_quote)
    if result.get("found"):
        if result.get("snippet") and len(result["snippet"]) > MAX_SNIPPET_CHARS:
            result["snippet"] = result["snippet"][:MAX_SNIPPET_CHARS]
        return result

    # Tier 1.5: Whitespace-normalized matching
    norm_doc = normalize_whitespace(document_text)
    norm_quote = normalize_whitespace(verbatim_quote)
    pos = norm_doc.find(norm_quote)
    if pos != -1:
        # Map back to approximate original position
        ratio = pos / max(len(norm_doc), 1)
        approx_start = int(ratio * len(document_text))
        search_start = max(0, approx_start - 200)
        search_end = min(len(document_text), approx_start + len(verbatim_quote) + 200)
        search_region = document_text[search_start:search_end]
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

    step = max(1, quote_len // 4)
    for i in range(0, len(document_text) - quote_len + 1, step):
        candidate = document_text[i:i + quote_len]
        r = difflib.SequenceMatcher(None, verbatim_quote, candidate).ratio()
        if r > best_ratio:
            best_ratio = r
            best_start = i

    # Refine around best_start with step=1
    if best_ratio >= FUZZY_THRESHOLD - 0.05:
        refine_start = max(0, best_start - step)
        refine_end = min(len(document_text) - quote_len + 1, best_start + step)
        for i in range(refine_start, refine_end):
            candidate = document_text[i:i + quote_len]
            r = difflib.SequenceMatcher(None, verbatim_quote, candidate).ratio()
            if r > best_ratio:
                best_ratio = r
                best_start = i

    if best_ratio >= FUZZY_THRESHOLD:
        matched_text = document_text[best_start:best_start + quote_len]
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
# INLINE VERIFICATION (called during extraction pipeline)
# ============================================================================

async def verify_document_citations_inline(
    document_text: str,
    citation_records: list,
    *,
    model: str,
    thinking_budget: int = 1024,
    batch_size: int = 50,
) -> dict:
    """
    Verify all citations for a document inline during extraction.

    INPUT:
        - document_text: Full extracted text
        - citation_records: List of CitationExtractionPhased ORM objects
        - model: Gemini model name
        - thinking_budget: Thinking token budget
        - batch_size: Max citations per LLM call
    OUTPUT: Dict with verification results:
        - confirmed: int
        - not_found: int
        - misattributed: int
        - cost_usd: float
        - tokens_in: int
        - tokens_out: int
        - tokens_thinking: int
        - api_calls: int
        - updates: list of (extraction_id, update_dict) tuples
    """
    from gemini_client import call_gemini_async

    result = {
        "confirmed": 0,
        "not_found": 0,
        "misattributed": 0,
        "unverified": 0,
        "cost_usd": 0.0,
        "tokens_in": 0,
        "tokens_out": 0,
        "tokens_thinking": 0,
        "api_calls": 0,
        "updates": [],
    }

    if not citation_records or not document_text:
        return result

    # Normalize line endings
    document_text = document_text.replace("\r\n", "\n").replace("\r", "\n")

    # Flash pricing per 1K tokens
    cost_per_1k_in = 0.000150
    cost_per_1k_out = 0.000600

    # Batch citations
    batches = []
    for i in range(0, len(citation_records), batch_size):
        batches.append(citation_records[i:i + batch_size])

    all_verifications = {}  # extraction_id -> verification result

    for batch in batches:
        prompt_citations = [
            {"index": idx, "case_name": getattr(c, 'case_name', None) or f"Unknown"}
            for idx, c in enumerate(batch)
        ]
        prompt = build_verification_prompt(document_text, prompt_citations)

        # Pre-check token estimate
        est_tokens = len(prompt) // 4
        if est_tokens > 900_000:
            logger.warning(f"Verification prompt too large ({est_tokens:,} est tokens), skipping batch")
            continue

        try:
            api_result = await call_gemini_async(
                prompt,
                model=model,
                temperature=0.0,
                response_schema=DocumentVerificationResponse,
                thinking_budget=thinking_budget,
            )
        except Exception as e:
            if "INVALID_ARGUMENT" in str(e) and "token" in str(e).lower():
                logger.warning(f"Verification: token limit exceeded, skipping batch")
                continue
            raise

        if api_result is None:
            continue

        tokens_in = api_result.get("tokens_in", 0)
        tokens_out = api_result.get("tokens_out", 0)
        tokens_thinking = api_result.get("tokens_thinking", 0)
        call_cost = (tokens_in / 1000 * cost_per_1k_in) + (tokens_out / 1000 * cost_per_1k_out)

        result["cost_usd"] += call_cost
        result["api_calls"] += 1
        result["tokens_in"] += tokens_in
        result["tokens_out"] += tokens_out
        result["tokens_thinking"] += tokens_thinking

        data = api_result.get("data")
        if not data:
            continue

        if isinstance(data, dict):
            verifications_list = data.get("verifications", [])
        elif hasattr(data, "verifications"):
            verifications_list = data.verifications
        else:
            verifications_list = []

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

    # Build updates for each citation
    now = datetime.now(timezone.utc)
    for citation in citation_records:
        v = all_verifications.get(citation.extraction_id)
        if not v:
            # VMISSUE-1 fix: default unverified citations instead of skipping
            result["unverified"] += 1
            result["updates"].append((citation.extraction_id, {
                "verification_status": "UNVERIFIED",
                "verification_notes": "LLM verification response omitted this citation",
                "verification_model": model,
                "verified_at": now,
                "requires_manual_review": True,
                "manual_review_reason": "Verification: UNVERIFIED — LLM omission",
            }))
            continue

        verdict = v["verdict"]
        quote = v["quote"]
        notes_parts = []
        if v["corrected"]:
            notes_parts.append(f"Corrected: {v['corrected']}")
        if v["notes"]:
            notes_parts.append(v["notes"])

        if quote and len(quote) > MAX_SNIPPET_CHARS:
            quote = quote[:MAX_SNIPPET_CHARS]

        update = {
            "verification_status": verdict,
            "verification_snippet": quote,
            "verification_notes": "; ".join(notes_parts) if notes_parts else None,
            "verification_model": model,
            "verified_at": now,
        }

        if verdict == "CONFIRMED":
            result["confirmed"] += 1
            if quote:
                match = fuzzy_match_snippet(document_text, quote)
                if match and match.get("found"):
                    update["snippet_text"] = match["snippet"]
                    update["snippet_start_char"] = match["start_char"]
                    update["snippet_end_char"] = match["end_char"]
        elif verdict == "NOT_FOUND":
            result["not_found"] += 1
            update["requires_manual_review"] = True
            update["manual_review_reason"] = "Verification: NOT_FOUND"
        elif verdict == "MISATTRIBUTED":
            result["misattributed"] += 1
            update["requires_manual_review"] = True
            update["manual_review_reason"] = "Verification: MISATTRIBUTED"

        result["updates"].append((citation.extraction_id, update))

    return result
