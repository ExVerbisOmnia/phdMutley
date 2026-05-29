#!/usr/bin/env python3
"""
Build Knowledge Base for Citation Extraction v6
================================================
Reads Sabin/Columbia case metadata from Excel and builds a structured
JSON knowledge base for LLM-assisted citation extraction.

Task #12 (Phase 4 of master plan v2.0).
Decision D6: "Add build-knowledge step before citation extraction."

The knowledge base provides case context to the LLM during extraction,
dramatically improving citation recall (learned from Lucas's corporate-cases
project).

INPUT:
    - data/seed/SABIN_DB-2026-02-23.xlsx (master Sabin database)
OUTPUT:
    - data/knowledge_base/sabin_case_index.json (case-level index)
    - data/knowledge_base/kb_stats.json (token estimates for batching)

Usage:
    python scripts/build_knowledge_base.py              # build from Excel
    python scripts/build_knowledge_base.py --stats      # show stats only
    python scripts/build_knowledge_base.py --test-run 50  # limit to N cases
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import pandas as pd

# Add scripts dir to path
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPTS_DIR)

from config import DATABASE_FILE, LOGS_DIR

# ============================================================================
# LOGGING
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "build_knowledge_base.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS
# ============================================================================

KB_DIR = Path(__file__).resolve().parent.parent / "data" / "knowledge_base"
KB_OUTPUT = KB_DIR / "sabin_case_index.json"
KB_STATS_OUTPUT = KB_DIR / "kb_stats.json"

# Approximate tokens-per-character ratio for English legal text
CHARS_PER_TOKEN = 4.0


# ============================================================================
# CORE FUNCTIONS
# ============================================================================


def load_excel(path: Path) -> pd.DataFrame:
    """
    Load the Sabin Excel database.

    INPUT: Path to Excel file
    OUTPUT: DataFrame with all rows
    """
    logger.info(f"Loading Excel: {path}")
    df = pd.read_excel(path)
    logger.info(f"Loaded {len(df)} rows, {df['Case ID'].nunique()} unique cases")
    return df


def parse_jurisdiction_clean(jurisdiction_str) -> str:
    """
    Extract a clean court/jurisdiction name from the raw Jurisdictions field.

    INPUT: Raw jurisdiction string (e.g. "Land and Environment Court;Australia;New South Wales")
    OUTPUT: Cleaned jurisdiction string
    """
    if pd.isna(jurisdiction_str):
        return ""
    parts = [p.strip() for p in str(jurisdiction_str).split(";")]
    return "; ".join(parts[:2]) if len(parts) >= 2 else parts[0]


def parse_region(geography_isos_str) -> str:
    """
    Determine Global North/South from Geography ISOs.

    INPUT: Geography ISO string
    OUTPUT: "Global North", "Global South", "International", or ""
    """
    if pd.isna(geography_isos_str):
        return ""
    isos = str(geography_isos_str).split(";")
    primary_iso = isos[0].split("-")[0].strip() if isos else ""

    global_north = {
        "USA", "CAN", "GBR", "FRA", "DEU", "ITA", "ESP", "NLD", "BEL",
        "AUT", "CHE", "SWE", "NOR", "DNK", "FIN", "IRL", "PRT", "GRC",
        "POL", "CZE", "HUN", "ROU", "AUS", "NZL", "JPN", "KOR", "SGP", "ISR",
    }

    if primary_iso in ("INT", "INTL", "WORLD"):
        return "International"
    elif primary_iso in global_north:
        return "Global North"
    elif primary_iso:
        return "Global South"
    return ""


def build_case_index(df: pd.DataFrame) -> list[dict]:
    """
    Deduplicate Excel rows to case level and extract knowledge base fields.

    INPUT: Full Excel DataFrame (document-level rows)
    ALGORITHM:
        1. Group by Case ID
        2. Take first row per case for metadata
        3. Extract: name, year, jurisdiction, geography, region, summary, sabin_id
        4. Sort by year descending (newest first)
    OUTPUT: List of case dicts
    """
    cases = []
    grouped = df.groupby("Case ID", sort=False)

    for case_id, group in grouped:
        row = group.iloc[0]

        year_raw = row.get("Case Filing Year for Action")
        year = int(year_raw) if pd.notna(year_raw) else None

        summary_raw = row.get("Case Summary", "")
        summary = str(summary_raw).strip() if pd.notna(summary_raw) else ""
        # Truncate very long summaries to keep KB compact
        if len(summary) > 500:
            summary = summary[:497] + "..."

        geography_raw = row.get("Geographies", "")
        geography = str(geography_raw).strip() if pd.notna(geography_raw) else ""
        # Take first two geography parts only
        geo_parts = [p.strip() for p in geography.split(";")]
        geography = "; ".join(geo_parts[:2])

        entry = {
            "sabin_case_id": str(case_id).strip(),
            "case_name": str(row["Case Name"]).strip(),
            "year": year,
            "jurisdiction": parse_jurisdiction_clean(row.get("Jurisdictions")),
            "geography": geography,
            "region": parse_region(row.get("Geography ISOs")),
            "summary": summary,
            "case_number": str(row["Case Number"]).strip()
            if pd.notna(row.get("Case Number"))
            else None,
            "sabin_internal_id": str(row["Internal Case ID"]).strip()
            if pd.notna(row.get("Internal Case ID"))
            else None,
        }
        cases.append(entry)

    # Sort newest first (most likely to be cited in recent decisions)
    cases.sort(key=lambda c: c["year"] or 0, reverse=True)
    return cases


def estimate_tokens(cases: list[dict]) -> dict:
    """
    Estimate token counts for batching strategy design (Task #13).

    INPUT: List of case dicts
    ALGORITHM:
        1. Serialize each case to its prompt representation
        2. Count characters, estimate tokens at ~4 chars/token
        3. Compute total and per-entry stats
    OUTPUT: Dict with token statistics
    """
    entry_sizes = []
    for case in cases:
        # This mirrors how entries will appear in the LLM prompt
        text = format_case_for_prompt(case)
        chars = len(text)
        tokens = chars / CHARS_PER_TOKEN
        entry_sizes.append({"chars": chars, "tokens": int(tokens)})

    total_chars = sum(e["chars"] for e in entry_sizes)
    total_tokens = sum(e["tokens"] for e in entry_sizes)
    avg_tokens = total_tokens / len(entry_sizes) if entry_sizes else 0

    return {
        "total_cases": len(cases),
        "total_chars": total_chars,
        "total_tokens_estimated": total_tokens,
        "avg_tokens_per_case": int(avg_tokens),
        "min_tokens": min(e["tokens"] for e in entry_sizes) if entry_sizes else 0,
        "max_tokens": max(e["tokens"] for e in entry_sizes) if entry_sizes else 0,
        "fits_single_context": total_tokens < 900_000,
        "recommended_batches": max(1, -(-total_tokens // 800_000)),  # ceiling division
    }


def format_case_for_prompt(case: dict) -> str:
    """
    Format a single case entry for inclusion in an LLM prompt.

    INPUT: Case dict from the knowledge base
    OUTPUT: Formatted string for prompt context
    """
    parts = [f"- {case['case_name']}"]
    if case.get("year"):
        parts[0] += f" ({case['year']})"
    if case.get("jurisdiction"):
        parts.append(f"  Court: {case['jurisdiction']}")
    if case.get("geography"):
        parts.append(f"  Location: {case['geography']}")
    if case.get("case_number"):
        parts.append(f"  Case No: {case['case_number']}")
    if case.get("summary"):
        parts.append(f"  Summary: {case['summary']}")
    return "\n".join(parts)


def format_batch_for_prompt(cases: list[dict]) -> str:
    """
    Format a batch of cases as a knowledge base section for the LLM prompt.

    INPUT: List of case dicts
    OUTPUT: Full prompt section text
    """
    header = (
        "KNOWN CLIMATE LITIGATION CASES (Sabin Center / Columbia Law School):\n"
        "The following cases are from the Climate Case Chart database. "
        "When you find a citation that matches any of these cases, note the "
        "sabin_case_id for that match.\n\n"
    )
    entries = [format_case_for_prompt(c) for c in cases]
    return header + "\n\n".join(entries)


# ============================================================================
# LOOKUP FUNCTIONS (used by extraction pipeline)
# ============================================================================


_kb_cache: list[dict] | None = None


def load_knowledge_base(path: Path | None = None) -> list[dict]:
    """
    Load the knowledge base from JSON. Caches in memory after first load.

    INPUT: Optional path override (defaults to KB_OUTPUT)
    OUTPUT: List of case dicts
    """
    global _kb_cache
    if _kb_cache is not None:
        return _kb_cache

    p = path or KB_OUTPUT
    if not p.exists():
        raise FileNotFoundError(
            f"Knowledge base not found at {p}. Run: python scripts/build_knowledge_base.py"
        )

    with open(p, encoding="utf-8") as f:
        _kb_cache = json.load(f)
    return _kb_cache


def lookup_by_name(query: str, kb: list[dict] | None = None) -> list[dict]:
    """
    Simple case-insensitive substring search on case names.
    Used by the Sabin filter (Task #16) for quick lookups.

    INPUT:
        - query: Search string (e.g. "Urgenda" or "Sharma")
        - kb: Optional pre-loaded knowledge base
    OUTPUT: List of matching case entries
    """
    if kb is None:
        kb = load_knowledge_base()

    q = query.lower().strip()
    return [c for c in kb if q in c["case_name"].lower()]


def get_cases_by_jurisdiction(jurisdiction: str, kb: list[dict] | None = None) -> list[dict]:
    """
    Filter KB cases by jurisdiction substring match.

    INPUT: Jurisdiction string to search
    OUTPUT: Matching cases
    """
    if kb is None:
        kb = load_knowledge_base()

    j = jurisdiction.lower().strip()
    return [c for c in kb if j in c.get("jurisdiction", "").lower()]


# ============================================================================
# MAIN
# ============================================================================


def main():
    parser = argparse.ArgumentParser(description="Build knowledge base from Sabin Excel")
    parser.add_argument("--stats", action="store_true", help="Show stats only (no rebuild)")
    parser.add_argument("--test-run", type=int, default=None, help="Limit to N cases")
    args = parser.parse_args()

    if args.stats:
        if not KB_OUTPUT.exists():
            logger.error(f"Knowledge base not found at {KB_OUTPUT}")
            sys.exit(1)
        kb = load_knowledge_base()
        stats = estimate_tokens(kb)
        print(json.dumps(stats, indent=2))
        return

    logger.info("=" * 70)
    logger.info("BUILDING KNOWLEDGE BASE")
    logger.info("=" * 70)

    # Load Excel
    df = load_excel(DATABASE_FILE)

    # Build case-level index
    cases = build_case_index(df)
    logger.info(f"Built index: {len(cases)} unique cases")

    # Apply test-run limit
    if args.test_run:
        cases = cases[: args.test_run]
        logger.info(f"Test-run: limited to {len(cases)} cases")

    # Estimate tokens
    stats = estimate_tokens(cases)
    logger.info(f"Token estimate: {stats['total_tokens_estimated']:,} tokens "
                f"({stats['avg_tokens_per_case']} avg/case)")
    logger.info(f"Fits single context window: {stats['fits_single_context']}")
    logger.info(f"Recommended batches: {stats['recommended_batches']}")

    # Region distribution
    regions = {}
    for c in cases:
        r = c.get("region") or "Unknown"
        regions[r] = regions.get(r, 0) + 1
    logger.info(f"Region distribution: {regions}")

    # Year range
    years = [c["year"] for c in cases if c.get("year")]
    if years:
        logger.info(f"Year range: {min(years)} - {max(years)}")

    # Save knowledge base JSON
    KB_DIR.mkdir(parents=True, exist_ok=True)

    with open(KB_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(cases, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved knowledge base: {KB_OUTPUT} ({KB_OUTPUT.stat().st_size / 1024:.0f} KB)")

    # Save stats
    with open(KB_STATS_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)
    logger.info(f"Saved stats: {KB_STATS_OUTPUT}")

    logger.info("=" * 70)
    logger.info("KNOWLEDGE BASE BUILD COMPLETE")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
