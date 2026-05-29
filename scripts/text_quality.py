"""
Text Quality Assessment — Reusable Quality Functions
======================================================
Centralized text quality checks extracted from verify_citations.py.
Used by extract_texts.py (Phase 3), extract_citations.py (Phase 5),
and verify_citations.py (Phase V) to detect garbled/corrupted text
and oversized documents.

VERSION: 1.0
"""

# Garbled text detection thresholds
GARBLED_ALPHA_RATIO_MIN = 0.40  # At least 40% alphabetic characters
GARBLED_AVG_WORD_LEN_MAX = 25   # Average word length under 25 chars

# Token estimation
CHARS_PER_TOKEN = 4
SAFE_TOKEN_THRESHOLD = 900_000  # ~3.6M chars


def is_garbled_text(
    text: str,
    alpha_ratio_min: float = GARBLED_ALPHA_RATIO_MIN,
    avg_word_len_max: int = GARBLED_AVG_WORD_LEN_MAX,
) -> bool:
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
    if alpha_ratio < alpha_ratio_min:
        return True

    # Check 2: Average word length
    words = sample.split()
    if words:
        avg_word_len = sum(len(w) for w in words) / len(words)
        if avg_word_len > avg_word_len_max:
            return True

    return False


def is_too_long(
    text: str,
    safe_token_threshold: int = SAFE_TOKEN_THRESHOLD,
    chars_per_token: int = CHARS_PER_TOKEN,
) -> bool:
    """
    Check if text exceeds the model's safe token threshold.

    INPUT: Document text string
    OUTPUT: True if text is too long for the model context window
    """
    if not text:
        return False
    est_tokens = len(text) // chars_per_token
    return est_tokens > safe_token_threshold


def compute_text_quality_flags(text: str) -> dict:
    """
    Compute all text quality flags in one pass.

    INPUT: Document text string
    OUTPUT: Dict with quality assessment:
        - is_garbled: bool
        - is_too_long: bool
        - char_count: int
        - est_tokens: int
    """
    if not text:
        return {
            "is_garbled": True,
            "is_too_long": False,
            "char_count": 0,
            "est_tokens": 0,
        }

    char_count = len(text)
    est_tokens = char_count // CHARS_PER_TOKEN

    return {
        "is_garbled": is_garbled_text(text),
        "is_too_long": is_too_long(text),
        "char_count": char_count,
        "est_tokens": est_tokens,
    }
