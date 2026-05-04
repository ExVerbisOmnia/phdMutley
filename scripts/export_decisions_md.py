"""
Export judicial decisions as individual Markdown files with YAML frontmatter.

Reads raw_text from the extracted_text table (joined with documents + cases),
writes one .md file per document to data/decisions_md/.

INPUT:
    - PostgreSQL: extracted_text.raw_text + document/case metadata
    - Only documents where is_decision=True AND raw_text IS NOT NULL
OUTPUT:
    - data/decisions_md/{document_id}.md  (one per document)
    - data/decisions_md/_manifest.json    (index of all exported files)
ALGORITHM:
    1. Query DB for decision documents with raw text (D33: switched from text_md to raw_text)
    2. For each: write .md with YAML frontmatter (metadata) + body (raw_text)
    3. Write manifest JSON for orchestration

DECISIONS APPLIED:
    - D33: Body source switched from extracted_text.text_md to extracted_text.raw_text.
      T4 dual-extraction test (5 docs) showed raw_text recovers footnote-truncated
      citations (Saint-Gobain 4→16) with 0 false positives, 0 lost citations.
      Markdown structure is not load-bearing for citation extraction.
    - D36 / T2: fix_region() overrides region to "International" for international
      courts (CJEU/ECtHR/IACtHR/ICJ/ITLOS/ICSID/...) so they don't default to
      "Global South" and corrupt sixfold classification.
    - D35 / T3: Year extraction now reads the document body's first ~500 chars
      (most decisions state their date in the header) before falling back to
      case_number parsing or case_filing_year.
"""

import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import create_engine, text

# Add scripts dir to path for config import
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DB_CONFIG

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "decisions_md"

QUERY = """
SELECT
    d.document_id,
    d.document_title,
    d.document_date,
    d.is_garbled,
    c.case_id,
    c.case_name,
    c.case_number,
    c.jurisdiction,
    c.geographies,
    c.geography_iso,
    c.region,
    c.case_filing_year,
    c.language,
    c.sabin_case_id,
    et.raw_text,
    et.language_detected,
    et.word_count,
    et.character_count
FROM documents d
JOIN cases c ON d.case_id = c.case_id
JOIN extracted_text et ON et.document_id = d.document_id
WHERE d.is_decision = TRUE
  AND et.raw_text IS NOT NULL
  AND COALESCE(d.is_garbled, FALSE) = FALSE
ORDER BY c.case_name, d.document_title
"""


# ----- D36 / T2: fix_region() for international courts -------------------------

INTERNATIONAL_KEYWORDS = [
    "international", "inter-american", "european court", "ecthr", "echr",
    "cjeu", "ecj", "european court of justice", "european court of human rights",
    "african court", "achpr", "icj", "itlos", "icsid",
    "arbitral", "wto", "pca", "tribunal",
    "court of justice of the european union",
]


def fix_region(jurisdiction: str | None, region: str | None) -> str:
    """Override region to 'International' for international courts."""
    j = (jurisdiction or "").lower()
    if any(kw in j for kw in INTERNATIONAL_KEYWORDS):
        return "International"
    return region or ""


# ----- D35 / T3: Document-header date extraction -------------------------------

_MONTHS = (
    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
)

# Patterns ordered as specified. Each pattern returns the year via the
# explicitly named year_group (1-indexed match group containing YYYY).
_DATE_PATTERNS = [
    # "17 January 2020"
    (re.compile(rf"\b(\d{{1,2}})\s+{_MONTHS}\s+(\d{{4}})\b", re.IGNORECASE), 3),
    # "January 17, 2020" or "January 17 2020"
    (re.compile(rf"\b{_MONTHS}\s+(\d{{1,2}}),?\s+(\d{{4}})\b", re.IGNORECASE), 3),
    # "17/01/2020" or "01/17/2020"
    (re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b"), 3),
    # "[2020]" neutral citation year
    (re.compile(r"\[(\d{4})\]"), 1),
]


def _years_from_text(snippet: str) -> list[int]:
    """Apply all date patterns to snippet, return all years found (>=1900)."""
    found: list[int] = []
    for pattern, year_group in _DATE_PATTERNS:
        for m in pattern.finditer(snippet):
            try:
                y = int(m.group(year_group))
            except (ValueError, IndexError):
                continue
            # Sanity: filter out absurd years (e.g. day numbers parsed as years)
            if 1900 <= y <= 2100:
                found.append(y)
    return found


def extract_year(row: dict, body: str | None = None) -> int | None:
    """
    Best-effort year of the document (not the case filing).

    INPUT:
        - row: DB row with document_date, case_number, case_filing_year
        - body: full document body text (raw_text); first 500 chars are scanned
    ALGORITHM (D35):
        1. document_date (most accurate, currently NULL for all records — kept as future-proof check)
        2. Parse a date from the first 500 chars of the body. Patterns tried:
             a. "17 January 2020"
             b. "January 17, 2020"
             c. "17/01/2020" or "01/17/2020"
             d. "[2020]" neutral citation
           Take the latest year found in the header.
        3. Fall back: parse case_number for [YYYY] or (YYYY).
        4. Last resort: case_filing_year.
    OUTPUT: int year or None
    """
    # 1. Explicit document_date column (NULL for all rows currently, but future-proof).
    if row.get("document_date"):
        return row["document_date"].year

    # 2. Header parsing — first ~500 chars of body.
    if body:
        header = body[:500]
        years = _years_from_text(header)
        if years:
            return max(years)  # latest year = most recent proceeding mentioned

    # 3. case_number neutral citation parsing.
    if row.get("case_number"):
        cn = str(row["case_number"])
        cn_years = re.findall(r"[\[\(](\d{4})[\]\)]", cn)
        if cn_years:
            return int(max(cn_years))

    # 4. Last resort: case_filing_year.
    if row.get("case_filing_year"):
        return int(row["case_filing_year"])

    return None


# ----- Frontmatter assembly ---------------------------------------------------

def sanitize_yaml_string(value: str | None) -> str:
    """Escape a string for safe YAML inline quoting."""
    if value is None:
        return ""
    value = str(value).replace("\\", "\\\\").replace('"', '\\"')
    # Collapse newlines into spaces
    value = re.sub(r"[\r\n]+", " ", value).strip()
    return value


def build_frontmatter(row: dict, body: str | None = None) -> str:
    """Build YAML frontmatter block from a DB row."""
    year = extract_year(row, body)
    region_fixed = fix_region(row["jurisdiction"], row["region"])
    lines = [
        "---",
        f'document_id: "{row["document_id"]}"',
        f'case_id: "{sanitize_yaml_string(row["case_id"])}"',
        f'case_name: "{sanitize_yaml_string(row["case_name"])}"',
        f'case_number: "{sanitize_yaml_string(row["case_number"])}"',
        f'sabin_case_id: "{sanitize_yaml_string(row["sabin_case_id"])}"',
        f'document_title: "{sanitize_yaml_string(row["document_title"])}"',
        f'jurisdiction: "{sanitize_yaml_string(row["jurisdiction"])}"',
        f'geographies: "{sanitize_yaml_string(row["geographies"])}"',
        f'geography_iso: "{sanitize_yaml_string(row["geography_iso"])}"',
        f'region: "{sanitize_yaml_string(region_fixed)}"',
        f"year: {year if year else 'null'}",
        f'language: "{sanitize_yaml_string(row["language_detected"] or row["language"])}"',
        f"word_count: {row['word_count'] or 'null'}",
        f"character_count: {row['character_count'] or 'null'}",
        "---",
    ]
    return "\n".join(lines)


def export_all():
    """Export all decision markdown files."""
    connstr = (
        f"postgresql://{DB_CONFIG['username']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    )
    engine = create_engine(connstr)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []

    # Run-level stats
    stats = {
        "total": 0,
        "total_chars": 0,
        "year_source": {
            "document_date": 0,
            "body_header": 0,
            "case_number": 0,
            "case_filing_year": 0,
            "none": 0,
        },
        "region_overrides": 0,
    }

    log.info("=" * 70)
    log.info("EXPORT DECISIONS TO MARKDOWN")
    log.info("=" * 70)

    with engine.connect() as conn:
        result = conn.execute(text(QUERY))
        rows = result.mappings().all()

    log.info(f"Found {len(rows)} decision documents with raw_text")

    for i, row in enumerate(rows, 1):
        doc_id = str(row["document_id"])
        filename = f"{doc_id}.md"
        filepath = OUTPUT_DIR / filename

        body = row["raw_text"]

        # --- Track year-extraction provenance (mirror logic of extract_year) ---
        if row.get("document_date"):
            stats["year_source"]["document_date"] += 1
            year_for_manifest = row["document_date"].year
        elif body and _years_from_text(body[:500]):
            stats["year_source"]["body_header"] += 1
            year_for_manifest = max(_years_from_text(body[:500]))
        elif row.get("case_number") and re.findall(r"[\[\(](\d{4})[\]\)]", str(row["case_number"])):
            stats["year_source"]["case_number"] += 1
            year_for_manifest = int(max(re.findall(r"[\[\(](\d{4})[\]\)]", str(row["case_number"]))))
        elif row.get("case_filing_year"):
            stats["year_source"]["case_filing_year"] += 1
            year_for_manifest = int(row["case_filing_year"])
        else:
            stats["year_source"]["none"] += 1
            year_for_manifest = None

        # --- Track region overrides ---
        original_region = row["region"] or ""
        fixed_region = fix_region(row["jurisdiction"], row["region"])
        if fixed_region != original_region:
            stats["region_overrides"] += 1

        frontmatter = build_frontmatter(row, body)

        filepath.write_text(f"{frontmatter}\n\n{body}", encoding="utf-8")

        char_count = row["character_count"] or (len(body) if body else 0)
        stats["total"] += 1
        stats["total_chars"] += char_count

        manifest.append({
            "file": filename,
            "document_id": doc_id,
            "case_id": row["case_id"],
            "case_name": row["case_name"],
            "jurisdiction": row["jurisdiction"],
            "region": fixed_region,
            "year": year_for_manifest,
            "word_count": row["word_count"],
            "character_count": row["character_count"],
        })

        if i % 500 == 0:
            log.info(f"  Exported {i}/{len(rows)} files...")

    # Write manifest
    manifest_path = OUTPUT_DIR / "_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )

    log.info(f"Exported {len(rows)} files to {OUTPUT_DIR}")
    log.info(f"Manifest written to {manifest_path}")
    log.info(f"  Total character count: {sum(r['character_count'] or 0 for r in manifest):,}")
    log.info("-" * 70)
    log.info("RUN STATS")
    log.info("-" * 70)
    log.info(f"  Total docs exported       : {stats['total']}")
    log.info(f"  Total characters          : {stats['total_chars']:,}")
    log.info(f"  Year source — document_date    : {stats['year_source']['document_date']}")
    log.info(f"  Year source — body_header      : {stats['year_source']['body_header']}")
    log.info(f"  Year source — case_number      : {stats['year_source']['case_number']}")
    log.info(f"  Year source — case_filing_year : {stats['year_source']['case_filing_year']}")
    log.info(f"  Year source — none             : {stats['year_source']['none']}")
    log.info(f"  Region overrides applied  : {stats['region_overrides']}")
    log.info("-" * 70)


if __name__ == "__main__":
    export_all()
