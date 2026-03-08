#!/usr/bin/env python3
"""
Snippet Extractor — Character-Anchored Citation Context
========================================================
Extracts verbatim text snippets for Sabin-matched citations with precise
character position anchoring. Decision D7: snippets only for kept citations.

The extractor locates each citation's raw_text in the source document and
extracts a context window around it, recording exact character offsets for
reproducibility and manual review.

Task #17 (Phase 5 of master plan v2.0).

Usage:
    from snippet_extractor import extract_snippet

    snippet = extract_snippet(
        document_text="... the court applied the Urgenda ruling ...",
        raw_citation_text="the court applied the Urgenda ruling",
    )
    # → {"found": True, "start_char": 42, "end_char": 78,
    #    "snippet": "... context ...", "paragraph": "..."}
"""

import logging
import re

logger = logging.getLogger(__name__)

# Default context window: characters before/after the citation
CONTEXT_CHARS_BEFORE = 300
CONTEXT_CHARS_AFTER = 300


def extract_snippet(
    document_text: str,
    raw_citation_text: str,
    context_before: int = CONTEXT_CHARS_BEFORE,
    context_after: int = CONTEXT_CHARS_AFTER,
) -> dict:
    """
    Locate a citation in the document and extract a context snippet.

    INPUT:
        - document_text: Full document text
        - raw_citation_text: Verbatim citation text from LLM extraction
        - context_before: Characters of context before the citation
        - context_after: Characters of context after the citation
    ALGORITHM:
        1. Try exact substring match
        2. If not found, try normalized match (collapse whitespace)
        3. If not found, try fuzzy match (longest common subsequence)
        4. Extract context window around match position
        5. Extract full paragraph containing the citation
    OUTPUT: Dict with snippet data and character anchors
    """
    if not document_text or not raw_citation_text:
        return {"found": False, "reason": "empty_input"}

    # === Tier 1: Exact match ===
    pos = document_text.find(raw_citation_text)
    if pos != -1:
        return _build_snippet(
            document_text, pos, pos + len(raw_citation_text),
            context_before, context_after, match_type="exact"
        )

    # === Tier 2: Normalized match (collapse whitespace, case-insensitive) ===
    norm_doc = _normalize_whitespace(document_text)
    norm_cite = _normalize_whitespace(raw_citation_text)

    pos = norm_doc.lower().find(norm_cite.lower())
    if pos != -1:
        # Map normalized position back to original text
        orig_pos = _map_to_original(document_text, norm_doc, pos, len(norm_cite))
        if orig_pos is not None:
            start, end = orig_pos
            return _build_snippet(
                document_text, start, end,
                context_before, context_after, match_type="normalized"
            )

    # === Tier 3: Key phrase match ===
    # Extract the most distinctive phrase from the citation (case name part)
    key_phrase = _extract_key_phrase(raw_citation_text)
    if key_phrase and len(key_phrase) >= 10:
        pos = document_text.lower().find(key_phrase.lower())
        if pos != -1:
            # Expand to sentence boundaries
            start, end = _expand_to_sentence(document_text, pos, pos + len(key_phrase))
            return _build_snippet(
                document_text, start, end,
                context_before, context_after, match_type="key_phrase"
            )

    return {"found": False, "reason": "not_found_in_document"}


def extract_snippets_batch(
    document_text: str,
    citations: list[dict],
) -> list[dict]:
    """
    Extract snippets for a batch of citations from the same document.

    INPUT:
        - document_text: Full document text
        - citations: List of citation dicts with 'raw_text' or 'raw_citation_text'
    OUTPUT: List of snippet dicts (same order as input)
    """
    results = []
    for cite in citations:
        raw_text = cite.get("raw_text", cite.get("raw_citation_text", ""))
        snippet = extract_snippet(document_text, raw_text)
        results.append(snippet)
    return results


# ============================================================================
# INTERNAL HELPERS
# ============================================================================


def _build_snippet(
    text: str, start: int, end: int,
    ctx_before: int, ctx_after: int,
    match_type: str,
) -> dict:
    """Build the snippet result dict with context and paragraph."""
    # Context window
    ctx_start = max(0, start - ctx_before)
    ctx_end = min(len(text), end + ctx_after)

    # Snap to word boundaries
    if ctx_start > 0:
        space = text.rfind(" ", ctx_start - 20, ctx_start)
        if space != -1:
            ctx_start = space + 1
    if ctx_end < len(text):
        space = text.find(" ", ctx_end, ctx_end + 20)
        if space != -1:
            ctx_end = space

    snippet = text[ctx_start:ctx_end]

    # Extract paragraph
    para_start = text.rfind("\n\n", 0, start)
    para_start = 0 if para_start == -1 else para_start + 2
    para_end = text.find("\n\n", end)
    para_end = len(text) if para_end == -1 else para_end
    paragraph = text[para_start:para_end].strip()

    # Truncate very long paragraphs
    if len(paragraph) > 2000:
        paragraph = paragraph[:1997] + "..."

    return {
        "found": True,
        "match_type": match_type,
        "start_char": start,
        "end_char": end,
        "matched_text": text[start:end][:200],  # first 200 chars of match
        "snippet": snippet,
        "snippet_start": ctx_start,
        "snippet_end": ctx_end,
        "paragraph": paragraph,
    }


def normalize_whitespace(text: str) -> str:
    """Collapse all whitespace to single spaces. Public API for reuse."""
    return re.sub(r"\s+", " ", text).strip()


# Keep private alias for backward compatibility within this module
_normalize_whitespace = normalize_whitespace


def _map_to_original(original: str, normalized: str, norm_pos: int, norm_len: int) -> tuple[int, int] | None:
    """
    Map a position in normalized text back to the original text.

    INPUT:
        - original: Original text
        - normalized: Whitespace-normalized text
        - norm_pos: Position in normalized text
        - norm_len: Length in normalized text
    OUTPUT: (start, end) in original text, or None
    """
    # Walk both strings in parallel
    orig_idx = 0
    norm_idx = 0
    start_orig = None

    while orig_idx < len(original) and norm_idx < len(normalized):
        if original[orig_idx].isspace() and (norm_idx >= len(normalized) or not normalized[norm_idx].isspace()):
            orig_idx += 1
            continue

        if norm_idx == norm_pos and start_orig is None:
            start_orig = orig_idx

        if norm_idx == norm_pos + norm_len:
            return (start_orig, orig_idx)

        orig_idx += 1
        norm_idx += 1

    if start_orig is not None and norm_idx >= norm_pos + norm_len:
        return (start_orig, orig_idx)

    return None


def _extract_key_phrase(citation_text: str) -> str | None:
    """
    Extract the most distinctive phrase from a citation for fallback matching.
    Typically the case name (party v. party portion).

    INPUT: Full citation text
    OUTPUT: Key phrase string or None
    """
    # Try to extract "X v. Y" pattern
    m = re.search(r"([A-Z][\w\s,.'-]+\s+v\.?\s+[\w\s,.'-]+)", citation_text)
    if m:
        return m.group(1).strip()

    # Fallback: first 50 chars after stripping common prefixes
    cleaned = re.sub(r"^(see|cf\.?|compare|following|in)\s+", "", citation_text, flags=re.IGNORECASE)
    if len(cleaned) >= 10:
        return cleaned[:50]

    return None


def _expand_to_sentence(text: str, start: int, end: int) -> tuple[int, int]:
    """Expand a match to sentence boundaries."""
    # Find sentence start (previous period/newline)
    sent_start = start
    for i in range(start - 1, max(start - 500, -1), -1):
        if i < 0:
            sent_start = 0
            break
        if text[i] in ".!?\n":
            sent_start = i + 1
            break

    # Find sentence end
    sent_end = end
    for i in range(end, min(end + 500, len(text))):
        if text[i] in ".!?\n":
            sent_end = i + 1
            break

    return sent_start, sent_end
