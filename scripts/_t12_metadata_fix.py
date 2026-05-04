"""
T12 — Surgical metadata fix for 2 confirmed misattributed documents.

Per `docs/reports/metadata-misattribution-T1.md`:
- Juliana doc 4da6a9cf — currently linked to an IACommHR case row, but is actually
  the US Ninth Circuit panel opinion. Three sibling docs in the same case are
  legitimate IACommHR petitions, so we must NOT mutate the case row. Instead:
  CREATE a new cases row for the 9thCir opinion + repoint the document.

- Woodhouse doc 191899bd — currently linked to an ICSID arbitral case row, but is
  actually a UK High Court ruling. The case has correctly-tagged sibling docs
  (notably 25090e85, "High Court of Justice — England and Wales" / UK), so:
  REPOINT to that existing case_id, no new case row needed.

INPUT: nothing (hard-coded to the 2 confirmed misattributions from T1)
ALGORITHM:
    1. Generate deterministic UUID5 for the new Juliana case row
    2. Pull the IACommHR case row for the misattributed Juliana doc (to copy
       case_filing_year, language, sabin_internal_case_id — but NOT sabin_case_id
       which stays NULL per Gus's decision)
    3. Single transaction:
        a. INSERT new cases row for Juliana 9thCir
        b. UPDATE doc 4da6a9cf SET case_id = new_juliana_case_id
        c. Look up the UK High Court sibling case_id from doc 25090e85
        d. UPDATE doc 191899bd SET case_id = uk_high_court_case_id
    4. Verify both docs now point to correctly-attributed cases (SELECT JOIN)
    5. Print summary
OUTPUT: applied fixes + verification report; throw on any error
"""
import logging
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import create_engine, text

# Add scripts dir to path for config import
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DB_CONFIG, UUID_NAMESPACE  # noqa: E402
from uuid import uuid5  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


# Confirmed misattributions per T1 report (docs/reports/metadata-misattribution-T1.md)
JULIANA_DOC_ID = "4da6a9cf-9d3c-518f-a0d9-ebb49f771db7"
WOODHOUSE_DOC_ID = "191899bd-2c01-5918-ab0f-cc289c81d7d5"
UK_SIBLING_DOC_ID = "25090e85-6a31-5b28-8bef-d14dbabb8e87"  # correctly-tagged High Court

# Deterministic key for the new Juliana 9thCir case_id — encodes the source
# document_id and the corrective intent so this script is idempotent.
JULIANA_CASE_KEY = f"case_manual_correction_{JULIANA_DOC_ID}_us_9thcir"


def main():
    connstr = (
        f"postgresql://{DB_CONFIG['username']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    )
    engine = create_engine(connstr)

    new_juliana_case_id = str(uuid5(UUID_NAMESPACE, JULIANA_CASE_KEY))
    log.info("=" * 70)
    log.info("T12 — Surgical metadata fix")
    log.info("=" * 70)
    log.info(f"New Juliana 9thCir case_id (deterministic UUID5): {new_juliana_case_id}")

    with engine.begin() as conn:  # transactional
        # ---- 1. Pull metadata from the misattributed IACommHR case row to inherit ----
        existing_juliana_row = conn.execute(
            text(
                """
                SELECT c.case_id, c.case_name, c.case_number, c.jurisdiction,
                       c.geographies, c.geography_iso, c.region, c.case_filing_year,
                       c.language, c.sabin_internal_case_id, c.case_url, c.case_summary
                FROM cases c
                JOIN documents d ON d.case_id = c.case_id
                WHERE d.document_id = :doc_id
                """
            ),
            {"doc_id": JULIANA_DOC_ID},
        ).mappings().one()
        log.info(f"Existing Juliana case (IACommHR-attributed): {existing_juliana_row['case_id']}")
        log.info(f"  case_name: {existing_juliana_row['case_name']}")
        log.info(f"  filing_year: {existing_juliana_row['case_filing_year']}")

        # ---- 2. Look up the UK High Court sibling case_id for Woodhouse fix ----
        uk_sibling_case_id = conn.execute(
            text("SELECT case_id FROM documents WHERE document_id = :doc_id"),
            {"doc_id": UK_SIBLING_DOC_ID},
        ).scalar_one()
        log.info(f"UK High Court sibling case_id (existing): {uk_sibling_case_id}")

        # ---- 3. INSERT new Juliana 9thCir case row ----
        verification_note = (
            f"manual correction per T12 (2026-05-03) — original Sabin record was the "
            f"IACommHR petition (case_id={existing_juliana_row['case_id']}); "
            f"this row carries the US Ninth Circuit panel opinion (No 18-36082, 17 Jan 2020) "
            f"that was misfiled under the IACommHR case. See "
            f"docs/reports/metadata-misattribution-T1.md and "
            f"docs/reports/methodology-decisions-log.md (T12)."
        )
        conn.execute(
            text(
                """
                INSERT INTO cases (
                    case_id, case_name, case_number, jurisdiction,
                    geographies, geography_iso, region, case_filing_year,
                    language, sabin_case_id, sabin_internal_case_id,
                    case_url, case_summary, created_at, updated_at
                )
                VALUES (
                    :case_id, :case_name, :case_number, :jurisdiction,
                    :geographies, :geography_iso, :region, :case_filing_year,
                    :language, NULL, :sabin_internal_case_id,
                    :case_url, :case_summary, NOW(), NOW()
                )
                """
            ),
            {
                "case_id": new_juliana_case_id,
                "case_name": "Juliana v. United States (9th Cir.)",
                "case_number": "No. 18-36082 (9th Cir. 17 Jan 2020)",
                "jurisdiction": "United States Court of Appeals - Ninth Circuit",
                "geographies": "United States",
                "geography_iso": "USA",
                "region": "Global North",
                "case_filing_year": existing_juliana_row["case_filing_year"],
                "language": existing_juliana_row["language"] or "en",
                "sabin_internal_case_id": existing_juliana_row["sabin_internal_case_id"],
                "case_url": existing_juliana_row["case_url"],
                "case_summary": verification_note,
            },
        )
        log.info(f"✓ INSERT cases row for Juliana 9thCir ({new_juliana_case_id})")

        # ---- 4. UPDATE Juliana document → new case_id ----
        result = conn.execute(
            text(
                """
                UPDATE documents
                SET case_id = :new_case_id, updated_at = NOW()
                WHERE document_id = :doc_id
                """
            ),
            {"new_case_id": new_juliana_case_id, "doc_id": JULIANA_DOC_ID},
        )
        assert result.rowcount == 1, f"Expected 1 row, got {result.rowcount}"
        log.info(f"✓ UPDATE document {JULIANA_DOC_ID} → new case_id")

        # ---- 5. UPDATE Woodhouse document → existing UK High Court case_id ----
        result = conn.execute(
            text(
                """
                UPDATE documents
                SET case_id = :uk_case_id, updated_at = NOW()
                WHERE document_id = :doc_id
                """
            ),
            {"uk_case_id": uk_sibling_case_id, "doc_id": WOODHOUSE_DOC_ID},
        )
        assert result.rowcount == 1, f"Expected 1 row, got {result.rowcount}"
        log.info(f"✓ UPDATE document {WOODHOUSE_DOC_ID} → UK High Court case_id")

    # ---- 6. Verification ----
    log.info("=" * 70)
    log.info("VERIFICATION (post-commit)")
    log.info("=" * 70)
    with engine.connect() as conn:
        for label, doc_id in [("Juliana", JULIANA_DOC_ID), ("Woodhouse", WOODHOUSE_DOC_ID)]:
            row = conn.execute(
                text(
                    """
                    SELECT d.document_id, d.case_id, c.case_name, c.jurisdiction,
                           c.geographies, c.region
                    FROM documents d
                    JOIN cases c ON c.case_id = d.case_id
                    WHERE d.document_id = :doc_id
                    """
                ),
                {"doc_id": doc_id},
            ).mappings().one()
            log.info(f"\n{label} ({doc_id[:8]}…)")
            log.info(f"  case_id:      {row['case_id']}")
            log.info(f"  case_name:    {row['case_name']}")
            log.info(f"  jurisdiction: {row['jurisdiction']}")
            log.info(f"  geographies:  {row['geographies']}")
            log.info(f"  region:       {row['region']}")

    log.info("=" * 70)
    log.info("T12 complete. Next: re-run export_decisions_md.py to refresh frontmatter.")
    log.info("=" * 70)


if __name__ == "__main__":
    main()
