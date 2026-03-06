#!/usr/bin/env python3
"""
Citation Extraction Prompt v6 — Knowledge-Base-Enhanced
========================================================
Integrates the Sabin knowledge base into the extraction prompt to improve
citation recall. Decision D6: "Providing contextual info about target cases
dramatically improved citation capture vs. just using case names."

The prompt includes a compact case index (name + year + jurisdiction) so the
LLM recognizes shorthand references like "the Urgenda case" or "the Dutch
climate ruling" and maps them to known Sabin cases.

Task #15 (Phase 5 of master plan v2.0).

Usage:
    from extraction_prompt_v6 import generate_v6_extraction_prompt

    prompt = generate_v6_extraction_prompt(
        text=document_text,
        source_jurisdiction="Australia",
        source_region="Global North",
        kb_cases=knowledge_base_cases,  # or None to auto-load
    )
"""

import logging
import os
import sys

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPTS_DIR)

from build_knowledge_base import load_knowledge_base

logger = logging.getLogger(__name__)

# ============================================================================
# KNOWLEDGE BASE FORMATTING
# ============================================================================


def format_kb_compact(cases: list[dict]) -> str:
    """
    Format KB cases in compact form for prompt inclusion.
    Uses ~150K tokens for 4,741 cases (vs 535K with full summaries).

    INPUT: List of case dicts from knowledge base
    OUTPUT: Compact text block with one case per line
    """
    lines = []
    for c in cases:
        year = c.get("year", "?")
        jurisdiction = c.get("jurisdiction", "")
        # Truncate long jurisdiction strings
        if len(jurisdiction) > 80:
            jurisdiction = jurisdiction[:77] + "..."
        lines.append(f"  {c['case_name']} ({year}) | {jurisdiction}")
    return "\n".join(lines)


# ============================================================================
# V6 PROMPT GENERATOR
# ============================================================================


def generate_v6_extraction_prompt(
    text: str,
    source_jurisdiction: str,
    source_region: str,
    kb_cases: list[dict] | None = None,
) -> str:
    """
    Generate v6 extraction prompt with knowledge base context.

    INPUT:
        - text: Full document text
        - source_jurisdiction: Where the citing court is located
        - source_region: Global North/South/International
        - kb_cases: Pre-loaded KB cases (auto-loads if None)
    OUTPUT: Complete prompt string with KB context
    """
    if kb_cases is None:
        kb_cases = load_knowledge_base()

    kb_text = format_kb_compact(kb_cases)
    kb_count = len(kb_cases)

    prompt = f"""You are extracting ALL legal case references from a judicial decision document.
Your ONLY task is EXTRACTION — identify and extract every case law reference.

SOURCE COURT INFORMATION:
- Jurisdiction: {source_jurisdiction}
- Region: {source_region}

============================================================
KNOWN CLIMATE LITIGATION CASES ({kb_count} cases)
============================================================
Below is a reference list of known climate litigation cases from the Sabin
Center / Columbia Law School Climate Case Chart database. Use this list to
help you recognize case references in the document, INCLUDING:
- Shorthand references ("the Urgenda case", "the Dutch climate ruling")
- Abbreviated names ("Sharma", "Neubauer")
- Non-English case names or translations
- References by court/year only ("the 2015 Hague District Court decision")

{kb_text}

============================================================
CRITICAL INSTRUCTIONS:
============================================================
1. Extract EVERY reference to case law (judicial decisions), regardless of
   domestic or foreign origin
2. Do NOT filter by jurisdiction — extract everything
3. Do NOT classify how citations are used — just extract them
4. Be EXHAUSTIVE — capture every mention of any case, court ruling, or
   judicial decision
5. Read the ENTIRE document text carefully — do not skip any sections
6. Do NOT extract academic articles, books, or author names
7. Do NOT extract treaties, conventions, statutes, legislation, or
   procedural rules (Paris Agreement, UNFCCC, Clean Air Act, etc.).
   Only extract JUDICIAL DECISIONS (cases decided by courts or tribunals).
8. For raw_text: copy the COMPLETE citation text VERBATIM as it appears
   in the document — this is critical for manual review
9. If a reference matches a case from the KNOWN CASES list above, use the
   exact case name from that list in the case_name field. If it does not
   match any known case, use the case name as it appears in the document.

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
      "case_name": "Full case name (use exact name from KNOWN CASES list if it matches a known case)",
      "raw_text": "VERBATIM citation text — copy the COMPLETE sentence or passage where this reference appears, exactly as written in the document",
      "confidence": 0.0-1.0
    }}
  ],
  "total_references_found": number,
  "extraction_notes": "any notes about the extraction process"
}}

FIELD INSTRUCTIONS:
- "case_name": The name of the case being cited. If it matches a case from
  the KNOWN CASES list above, use that exact name. Otherwise, use the name
  as it appears in the document.
- "raw_text": The FULL verbatim passage from the document containing the
  citation. This must be copied EXACTLY from the source text.
- "confidence": How confident you are this is a genuine judicial decision
  reference (0.0-1.0)

============================================================
IMPORTANT REMINDERS:
============================================================
- Extract EVERY judicial decision reference (case law only)
- Do NOT skip any sections of the document
- Better to over-extract than to miss citations
- Your job is ONLY extraction — filtering and classification come later
- Do NOT generate fabricated or hallucinated citations
- The raw_text field MUST be a verbatim copy from the document

============================================================
DOCUMENT TEXT:
============================================================
{text}"""

    return prompt


def estimate_v6_prompt_tokens(text_length: int, kb_size: int = 4741) -> int:
    """
    Estimate total prompt tokens for a v6 extraction call.

    INPUT:
        - text_length: Character count of document text
        - kb_size: Number of KB cases (default: full KB)
    OUTPUT: Estimated token count
    """
    # Prompt template overhead: ~800 tokens
    template_tokens = 800
    # Compact KB: ~32 tokens per case on average
    kb_tokens = kb_size * 32
    # Document text: ~4 chars per token
    text_tokens = text_length // 4

    return template_tokens + kb_tokens + text_tokens
