#!/usr/bin/env python3
"""
Sabin Filter — Match Citations Against Knowledge Base
======================================================
Decision D1: Only keep citations that reference cases in the Sabin Center /
Climate Case Chart database.

This module provides the matching logic between extracted citations and
known Sabin cases. It is called after Phase 2A extraction to filter results
before origin identification and classification.

Matching strategy (3-tier):
    Tier 1: Exact case name match (normalized)
    Tier 2: Fuzzy match — case name similarity + year + jurisdiction
    Tier 3: LLM confirmation (for ambiguous matches)

Usage:
    from sabin_filter import SabinFilter

    sf = SabinFilter()  # loads KB automatically
    result = sf.match_citation("Urgenda Foundation v. State of the Netherlands")
    # → {"matched": True, "sabin_case_id": "urgenda-...", "tier": 1, "confidence": 1.0, ...}

    filtered = sf.filter_citations(phase2a_references)
    # → list of citations with sabin_match data attached
"""

import logging
import re
import unicodedata

from build_knowledge_base import KB_OUTPUT, load_knowledge_base

logger = logging.getLogger(__name__)

# ============================================================================
# TEXT NORMALIZATION
# ============================================================================

# Common legal abbreviations and noise words to strip for matching
_STRIP_PATTERNS = [
    r"\b(No\.|Nos\.|Case No\.|Docket No\.)\s*[\w\-/]+",  # case numbers
    r"\[?\d{4}\]",  # bracketed years like [2019]
    r"\(\d{4}\)",  # parenthesized years like (2019)
    r"\b\d{1,3}\s+(F\.\s*\d[a-z]*|S\.?\s*Ct\.|U\.S\.|L\.?\s*Ed\.)",  # US reporters
    r"\bet\s+al\.?\b",  # et al
]

_STRIP_RE = [re.compile(p, re.IGNORECASE) for p in _STRIP_PATTERNS]

# Words to remove for comparison (articles, prepositions, conjunctions)
_NOISE_WORDS = {"the", "of", "and", "in", "for", "on", "v", "vs", "v.", "vs."}


def normalize_case_name(name: str) -> str:
    """
    Normalize a case name for comparison.

    INPUT: Raw case name string
    ALGORITHM:
        1. Unicode normalize (NFKD → ASCII)
        2. Lowercase
        3. Strip citation-style patterns (case numbers, reporters)
        4. Remove noise words (articles, prepositions)
        5. Collapse whitespace
    OUTPUT: Normalized string for matching
    """
    if not name:
        return ""

    # Unicode normalize
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    s = s.lower().strip()

    # Strip citation patterns
    for pat in _STRIP_RE:
        s = pat.sub(" ", s)

    # Remove punctuation except hyphens (useful in case slugs)
    s = re.sub(r"[^\w\s-]", " ", s)

    # Remove noise words
    words = s.split()
    words = [w for w in words if w not in _NOISE_WORDS]

    # Collapse whitespace
    return " ".join(words).strip()


def extract_year_from_citation(text: str) -> int | None:
    """
    Extract a 4-digit year from citation text.

    INPUT: Raw citation text
    OUTPUT: Year as int, or None
    """
    # Look for years in parentheses/brackets first (most reliable)
    m = re.search(r"[\(\[]\s*(\d{4})\s*[\)\]]", text)
    if m:
        year = int(m.group(1))
        if 1900 <= year <= 2030:
            return year

    # Fallback: any 4-digit number that looks like a year
    years = re.findall(r"\b(19\d{2}|20[0-2]\d)\b", text)
    return int(years[-1]) if years else None


# ============================================================================
# SABIN FILTER CLASS
# ============================================================================


class SabinFilter:
    """
    Matches extracted citations against the Sabin knowledge base.

    INPUT: Knowledge base JSON (loaded automatically)
    METHODS:
        match_citation(case_name, year=None, jurisdiction=None) → match dict
        filter_citations(references) → filtered list
    """

    # Tier 2 thresholds
    FUZZY_THRESHOLD = 0.70  # minimum similarity for fuzzy match
    FUZZY_WITH_YEAR_THRESHOLD = 0.60  # lower threshold when year also matches

    def __init__(self, kb_path=None):
        self._kb = load_knowledge_base(kb_path)
        self._index = self._build_index()
        logger.info(f"SabinFilter initialized: {len(self._kb)} cases indexed")

    def _build_index(self) -> dict[str, list[int]]:
        """
        Build a normalized-name → KB indices lookup.

        OUTPUT: Dict mapping normalized names to list of indices in self._kb
        """
        index = {}
        for i, case in enumerate(self._kb):
            norm = normalize_case_name(case["case_name"])
            index.setdefault(norm, []).append(i)

            # Also index without parenthetical descriptors
            # e.g. "Juliana v. United States (No. 18-36082)" → "juliana united states"
            short = re.sub(r"\(.*?\)", "", case["case_name"])
            short_norm = normalize_case_name(short)
            if short_norm != norm:
                index.setdefault(short_norm, []).append(i)

        return index

    def match_citation(
        self,
        case_name: str,
        year: int | None = None,
        jurisdiction: str | None = None,
        raw_text: str | None = None,
    ) -> dict:
        """
        Match a single citation against the knowledge base.

        INPUT:
            - case_name: Extracted case name
            - year: Extracted year (optional, improves matching)
            - jurisdiction: Extracted jurisdiction (optional)
            - raw_text: Full citation text (optional, for year extraction)
        ALGORITHM:
            Tier 1: Exact normalized name match
            Tier 2: Fuzzy substring match with year/jurisdiction boost
        OUTPUT: Dict with {matched, sabin_case_id, tier, confidence, kb_entry}
        """
        if not case_name:
            return {"matched": False, "reason": "empty_case_name"}

        # Extract year from raw_text if not provided
        if year is None and raw_text:
            year = extract_year_from_citation(raw_text)

        query_norm = normalize_case_name(case_name)

        if not query_norm:
            return {"matched": False, "reason": "empty_after_normalization"}

        # === TIER 1: Exact normalized match ===
        if query_norm in self._index:
            candidates = [self._kb[i] for i in self._index[query_norm]]

            # If year provided, prefer year-matching candidate
            if year and len(candidates) > 1:
                year_matches = [c for c in candidates if c.get("year") == year]
                if year_matches:
                    candidates = year_matches

            best = candidates[0]
            return {
                "matched": True,
                "sabin_case_id": best["sabin_case_id"],
                "sabin_internal_id": best.get("sabin_internal_id"),
                "kb_case_name": best["case_name"],
                "kb_year": best.get("year"),
                "kb_jurisdiction": best.get("jurisdiction"),
                "kb_region": best.get("region"),
                "tier": 1,
                "confidence": 1.0,
                "candidates": len(self._index[query_norm]),
            }

        # === TIER 2: Fuzzy matching ===
        best_score = 0.0
        best_match = None

        for norm_name, indices in self._index.items():
            score = self._similarity(query_norm, norm_name)

            # Year boost: if year matches, lower the threshold
            if year and score >= self.FUZZY_WITH_YEAR_THRESHOLD:
                for idx in indices:
                    if self._kb[idx].get("year") == year:
                        score += 0.15  # year match bonus
                        break

            if score > best_score:
                best_score = score
                best_match = indices[0]

        threshold = self.FUZZY_THRESHOLD
        if best_match is not None and best_score >= threshold:
            entry = self._kb[best_match]

            # Additional year validation when available
            confidence = min(best_score, 1.0)
            if year and entry.get("year") and year != entry["year"]:
                # Year mismatch reduces confidence
                confidence *= 0.8

            return {
                "matched": True,
                "sabin_case_id": entry["sabin_case_id"],
                "sabin_internal_id": entry.get("sabin_internal_id"),
                "kb_case_name": entry["case_name"],
                "kb_year": entry.get("year"),
                "kb_jurisdiction": entry.get("jurisdiction"),
                "kb_region": entry.get("region"),
                "tier": 2,
                "confidence": round(confidence, 2),
                "similarity_score": round(best_score, 3),
            }

        # === NO MATCH ===
        return {
            "matched": False,
            "best_similarity": round(best_score, 3) if best_match is not None else 0,
            "closest_name": self._kb[best_match]["case_name"] if best_match is not None else None,
            "closest_score": round(best_score, 3) if best_match is not None else None,
            "reason": "below_threshold",
        }

    def filter_citations(self, references: list[dict]) -> tuple[list[dict], list[dict]]:
        """
        Filter a list of extracted citations through the Sabin filter.

        INPUT: List of citation dicts from Phase 2A extraction
        ALGORITHM:
            1. For each citation, attempt match against KB
            2. Separate into kept (Sabin match) and discarded (no match)
            3. Attach sabin_match metadata to kept citations
        OUTPUT: Tuple of (kept_citations, discarded_citations)
        """
        kept = []
        discarded = []

        for ref in references:
            case_name = ref.get("case_name", "")
            raw_text = ref.get("raw_text", ref.get("raw_citation_text", ""))
            cited_year = ref.get("cited_year") or ref.get("year")

            match = self.match_citation(
                case_name=case_name,
                year=int(cited_year) if cited_year else None,
                raw_text=raw_text,
            )

            ref_copy = dict(ref)
            ref_copy["sabin_match"] = match

            if match["matched"]:
                kept.append(ref_copy)
            else:
                discarded.append(ref_copy)

        logger.info(
            f"Sabin filter: {len(kept)} kept, {len(discarded)} discarded "
            f"out of {len(references)} total"
        )

        # Log tier distribution for kept citations
        tier_counts = {}
        for r in kept:
            t = r["sabin_match"]["tier"]
            tier_counts[t] = tier_counts.get(t, 0) + 1
        if tier_counts:
            logger.info(f"  Match tiers: {tier_counts}")

        return kept, discarded

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        """
        Compute similarity between two normalized strings.
        Uses a combination of token overlap (Jaccard) and substring containment.

        INPUT: Two normalized strings
        OUTPUT: Similarity score 0.0-1.0
        """
        if a == b:
            return 1.0
        if not a or not b:
            return 0.0

        # Token-based Jaccard similarity
        tokens_a = set(a.split())
        tokens_b = set(b.split())

        if not tokens_a or not tokens_b:
            return 0.0

        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        jaccard = len(intersection) / len(union)

        # Containment bonus: if one name is a subset of the other
        containment = max(
            len(intersection) / len(tokens_a),
            len(intersection) / len(tokens_b),
        )

        # Weighted combination
        return 0.5 * jaccard + 0.5 * containment
