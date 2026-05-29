#!/usr/bin/env python3
"""
Citation Extraction Prompt v7 — Anti-Hallucination Hardened
============================================================
Generates extraction prompts WITHOUT the Sabin knowledge base to prevent
hallucination via KB contamination. The Sabin Filter runs AFTER extraction
to match citations to KB entries — preserving Sabin ID linking without
contaminating the LLM.

CHANGE FROM v6:
- REMOVED: 4,741-case "KNOWN CASES" section from prompt
- ADDED: Explicit anti-hallucination instructions
- ADDED: Negative examples (what NOT to extract)
- ADDED: Document year context for anachronism self-check
- RETAINED: All 12 extraction patterns, output format

The function signature is backward-compatible with v6. The kb_cases
parameter is accepted but ignored (kept for call-site compatibility).

Task #15 (Phase 5 of master plan v2.0).
"""

import logging
import os
import sys

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPTS_DIR)

logger = logging.getLogger(__name__)

# ============================================================================
# KNOWLEDGE BASE FORMATTING (retained for backward compat, now returns empty)
# ============================================================================


def format_kb_compact(cases: list[dict]) -> str:
    """Retained for backward compatibility. Returns empty string — KB is no
    longer included in extraction prompts to prevent hallucination."""
    return ""


# ============================================================================
# V7 PROMPT GENERATOR (backward-compatible function name)
# ============================================================================


def generate_v6_extraction_prompt(
    text: str,
    source_jurisdiction: str,
    source_region: str,
    kb_cases: list[dict] | None = None,
    document_year: int | None = None,
) -> str:
    """
    Generate extraction prompt WITHOUT knowledge base context.

    INPUT:
        - text: Full document text
        - source_jurisdiction: Where the citing court is located
        - source_region: Global North/South/International
        - kb_cases: IGNORED (kept for backward compatibility)
        - document_year: Year the document was issued (for anachronism check)
    OUTPUT: Complete prompt string
    """
    year_context = ""
    if document_year:
        year_context = f"\n- Document Year: {document_year} (this document CANNOT cite cases from after this year)"

    prompt = f"""You are extracting ALL legal case references from a judicial decision document.
Your ONLY task is EXTRACTION — identify and extract every case law reference
that ACTUALLY APPEARS in the document text.

SOURCE COURT INFORMATION:
- Jurisdiction: {source_jurisdiction}
- Region: {source_region}{year_context}

============================================================
CRITICAL ANTI-HALLUCINATION RULES:
============================================================
You MUST follow these rules strictly to avoid false extractions:

1. Extract ONLY citations that appear as VERBATIM text in the document.
2. Do NOT infer citations from topical similarity to cases you may know.
3. The raw_text field MUST be a direct copy-paste from the document — if
   you cannot find the exact text passage, do NOT extract the citation.
4. Do NOT fabricate or guess case names. If a reference is ambiguous,
   extract exactly what the document says without embellishing.
5. Do NOT add case names from your training data that are not explicitly
   mentioned in this specific document.
6. A case is "cited" only if the document NAMES or REFERENCES it. Topical
   overlap (e.g., both about climate change) is NOT a citation.

============================================================
WHAT NOT TO EXTRACT (negative examples):
============================================================
- A case you know is related to the topic but NOT mentioned in the document
- Metadata-format strings (e.g., "Case Name (2015) | Court; Jurisdiction")
- Author names or book titles that are not judicial decisions
- Treaties, conventions, statutes, legislation, or procedural rules
  (Paris Agreement, UNFCCC, Clean Air Act, etc.)
- Generic court references without a specific case (e.g., "the courts have held")

============================================================
EXTRACTION INSTRUCTIONS:
============================================================
1. Extract EVERY reference to case law (judicial decisions), regardless of
   domestic or foreign origin
2. Do NOT filter by jurisdiction — extract everything
3. Do NOT classify how citations are used — just extract them
4. Read the ENTIRE document text carefully — do not skip any sections
5. For raw_text: copy the COMPLETE citation text VERBATIM as it appears
   in the document — this is critical for manual review
6. Use the case name as it appears in the document

============================================================
EXTRACTION PATTERNS - CAPTURE ALL OF THESE:
============================================================

1. TRADITIONAL CITATIONS (formal legal citations)
   - "Brown v. Board of Education, 347 U.S. 483 (1954)"
   - "R (Miller) v Secretary of State [2017] UKSC 5"
   - Include ALL citation formats and parallel citations

2. NARRATIVE REFERENCES (descriptive mentions)
   - "The Norwegian Supreme Court held in 2020..."
   - "Following the Dutch court's approach in..."
   - "The European Court of Human Rights stated..."

3. SHORTHAND REFERENCES (abbreviated mentions)
   - "the Urgenda case"
   - "following Abraham"
   - "the landmark Dutch climate decision"

4. SCHOLARLY CITATIONS (academic references to cases)
   - "Professor X's analysis of the Urgenda case"
   - "Commentary on the ECtHR jurisprudence"

5. PROCEDURAL REFERENCES (case history)
   - "On appeal from...", "Affirmed by...", "Remanded to..."

6. COMPARATIVE REFERENCES
   - "Unlike the approach in...", "Similar to...", "Distinguishing..."

7. SIGNAL CITATIONS
   - "See also...", "Cf...", "Compare with...", "But see..."

8. FOOTNOTE/ENDNOTE CITATIONS
   - Include ALL citations in footnotes
   - Include "supra", "infra", ibid., id. references to cases

9. DISSENTING/CONCURRING OPINION CITATIONS

10. ADVISORY OPINIONS
    - ICJ Advisory Opinions, other tribunal advisory opinions

============================================================
OUTPUT FORMAT (JSON):
============================================================
{{
  "case_law_references": [
    {{
      "case_name": "Case name as it appears in the document",
      "raw_text": "VERBATIM citation text — copy the COMPLETE sentence or passage where this reference appears, exactly as written in the document",
      "confidence": 0.0-1.0
    }}
  ],
  "total_references_found": number,
  "extraction_notes": "any notes about the extraction process"
}}

FIELD INSTRUCTIONS:
- "case_name": The name of the case being cited, as it appears in the
  document text. Do NOT substitute or normalize case names.
- "raw_text": The FULL verbatim passage from the document containing the
  citation. This must be copied EXACTLY from the source text.
- "confidence": How confident you are this is a genuine judicial decision
  reference that actually appears in the document (0.0-1.0). Set to 0.5 or
  below if you are uncertain whether the text is truly citing this case.

============================================================
SELF-CHECK BEFORE SUBMITTING:
============================================================
For each citation you extract, verify:
1. Can you point to the EXACT passage in the document text? If not, REMOVE it.
2. Is the case name actually written in the document? If not, REMOVE it.
3. Is the raw_text a verbatim substring of the document? If not, FIX it.

============================================================
DOCUMENT TEXT:
============================================================
{text}"""

    return prompt


def estimate_v6_prompt_tokens(text_length: int, kb_size: int = 0) -> int:
    """
    Estimate total prompt tokens for an extraction call.

    INPUT:
        - text_length: Character count of document text
        - kb_size: IGNORED (KB no longer included in prompt)
    OUTPUT: Estimated token count
    """
    # Prompt template overhead: ~1000 tokens (slightly larger with anti-hallucination instructions)
    template_tokens = 1000
    # Document text: ~4 chars per token
    text_tokens = text_length // 4

    return template_tokens + text_tokens
