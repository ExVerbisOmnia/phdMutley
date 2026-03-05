#!/usr/bin/env python3
"""
============================================================================
SIXFOLD DECISION CLASSIFICATION AND CITATION TRACKING
============================================================================

Climate Litigation PhD Research Project
Author: Gustavo (with Claude assistance)
Date: December 7, 2025

Purpose:
--------
This script performs three main functions:

1. SIXFOLD CLASSIFICATION: Updates the citation_type column in
   citation_extraction_phased with the sixfold classification:
   - Foreign Citation (National → National)
   - International Citation (National → Int'l member)
   - Foreign International Citation (National → Int'l non-member)
   - Inter-System Citation (Int'l → Int'l)
   - Member-State Citation (Int'l → National member)
   - Non-Member Citation (Int'l → National non-member)

2. UNIQUE CITATIONS TRACKING: Counts how many unique cases cite each case
   and stores the list of citing case_ids.

3. UNIQUE CITED CASES TRACKING: Counts how many unique cases are cited BY
   each case and stores the list of cited case_ids.

Prerequisites:
-------------
- Run international_court_jurisdiction.sql first (creates membership table)
- Run add_citation_tracking_columns.py first (adds new columns to cases)

Usage:
------
    python classify_decisions_sixfold.py [--dry-run] [--classification-only] [--tracking-only]

============================================================================
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("SixfoldClassification")

# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gcp_secrets import get_database_url_auto

DATABASE_URL = get_database_url_auto()


# =============================================================================
# CLASSIFICATION ENGINE
# =============================================================================


class SixfoldClassificationEngine:
    """
    Engine for sixfold classification and citation tracking.

    This class performs:
    1. Updates citation_type in citation_extraction_phased
    2. Computes unique_citations and citing_cases for each case
    3. Computes unique_cited_count and cited_cases for each case
    """

    def __init__(self, database_url: str = DATABASE_URL):
        """
        Initialize the classification engine.

        INPUT:
            - database_url: PostgreSQL connection string
        """
        self.engine = create_engine(database_url, pool_size=5, max_overflow=10, pool_pre_ping=True)
        self.Session = sessionmaker(bind=self.engine)

        # Statistics tracking
        self.stats = {
            "classifications_updated": 0,
            "cases_with_citations_updated": 0,
            "cases_with_cited_updated": 0,
            "errors": 0,
        }

        logger.info("SixfoldClassificationEngine initialized")

    def _execute_query(self, sql: str, params: dict = None) -> list[dict]:
        """Execute a SQL query and return results as list of dictionaries."""
        with self.engine.connect() as conn:
            result = conn.execute(text(sql), params or {})
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result.fetchall()]

    def _execute_update(self, sql: str, params: dict = None) -> int:
        """Execute an UPDATE query and return rows affected."""
        with self.engine.begin() as conn:
            result = conn.execute(text(sql), params or {})
            return result.rowcount

    # =========================================================================
    # PART 1: SIXFOLD CLASSIFICATION
    # =========================================================================

    def update_citation_types(self, dry_run: bool = False) -> int:
        """
        Update citation_type column with sixfold classification.

        This reproduces the logic from the citation_sixfold_classification VIEW
        but writes the result directly to the citation_extraction_phased table.

        INPUT:
            - dry_run: If True, only report what would be updated

        ALGORITHM:
            1. Query all citations that need classification
            2. For each citation, determine sixfold type based on:
               - source_region (Global North, Global South, International)
               - case_law_region (Global North, Global South, International)
               - Membership in international courts
            3. Update citation_type column

        OUTPUT:
            - int: Number of records updated
        """
        logger.info("=" * 70)
        logger.info("PART 1: SIXFOLD CLASSIFICATION")
        logger.info("=" * 70)

        # The classification logic is implemented as a single UPDATE query
        # that mirrors the VIEW logic from sixfold_classification_complete.sql

        classification_sql = """
        UPDATE citation_extraction_phased cep
        SET citation_type =
            CASE
                -- 4. INTER-SYSTEM CITATION: International → International
                WHEN cep.source_region = 'International'
                     AND cep.case_law_region = 'International'
                THEN 'Inter-System Citation'

                -- 1. FOREIGN CITATION: National → National (different countries)
                WHEN cep.source_region IN ('Global North', 'Global South')
                     AND cep.case_law_region IN ('Global North', 'Global South')
                     AND cep.source_jurisdiction != cep.case_law_origin
                THEN 'Foreign Citation'

                -- 2 & 3. National → International: Check membership
                WHEN cep.source_region IN ('Global North', 'Global South')
                     AND cep.case_law_region = 'International'
                THEN
                    CASE
                        WHEN EXISTS (
                            SELECT 1 FROM international_court_jurisdiction icj
                            WHERE (
                                LOWER(COALESCE(cep.cited_court, '')) LIKE '%' || LOWER(icj.court_abbreviation) || '%'
                                OR LOWER(COALESCE(cep.case_law_origin, '')) LIKE '%' || LOWER(icj.court_abbreviation) || '%'
                                OR LOWER(COALESCE(cep.cited_court, '')) LIKE '%' || LOWER(icj.court_name) || '%'
                                OR LOWER(COALESCE(cep.case_law_origin, '')) LIKE '%' || LOWER(icj.court_name) || '%'
                                OR (LOWER(COALESCE(cep.case_law_origin, '')) LIKE '%european union%' AND icj.court_abbreviation IN ('CJEU', 'ECJ'))
                                OR (LOWER(COALESCE(cep.case_law_origin, '')) LIKE '%council of europe%' AND icj.court_abbreviation IN ('ECtHR', 'CoE'))
                                OR (LOWER(COALESCE(cep.case_law_origin, '')) LIKE '%inter-american%' AND icj.court_abbreviation IN ('IACtHR', 'IAHRS'))
                                OR (LOWER(COALESCE(cep.case_law_origin, '')) LIKE '%african%' AND icj.court_abbreviation = 'ACtHPR')
                                OR (LOWER(COALESCE(cep.case_law_origin, '')) LIKE '%wto%' AND icj.court_abbreviation = 'WTO')
                                OR (LOWER(COALESCE(cep.case_law_origin, '')) LIKE '%world trade%' AND icj.court_abbreviation = 'WTO')
                                OR (LOWER(COALESCE(cep.case_law_origin, '')) LIKE '%icsid%' AND icj.court_abbreviation = 'ICSID')
                                OR (LOWER(COALESCE(cep.case_law_origin, '')) LIKE '%united nations%' AND icj.court_abbreviation = 'ICJ')
                            )
                            AND (
                                cep.source_jurisdiction = ANY(icj.member_jurisdictions)
                                OR '*ALL*' = ANY(icj.member_jurisdictions)
                            )
                        ) THEN 'International Citation'
                        ELSE 'Foreign International Citation'
                    END

                -- 5 & 6. International → National: Check membership
                WHEN cep.source_region = 'International'
                     AND cep.case_law_region IN ('Global North', 'Global South')
                THEN
                    CASE
                        WHEN EXISTS (
                            SELECT 1 FROM international_court_jurisdiction icj
                            WHERE (
                                LOWER(COALESCE(cep.source_jurisdiction, '')) LIKE '%' || LOWER(icj.court_abbreviation) || '%'
                                OR LOWER(COALESCE(cep.source_jurisdiction, '')) LIKE '%' || LOWER(icj.court_name) || '%'
                            )
                            AND (
                                cep.case_law_origin = ANY(icj.member_jurisdictions)
                                OR '*ALL*' = ANY(icj.member_jurisdictions)
                            )
                        ) THEN 'Member-State Citation'
                        ELSE 'Non-Member Citation'
                    END

                ELSE 'Unclassified'
            END
        WHERE cep.source_region IS NOT NULL
          AND cep.case_law_region IS NOT NULL
        """

        if dry_run:
            # Count how many would be updated
            count_sql = """
                SELECT COUNT(*) as cnt FROM citation_extraction_phased
                WHERE source_region IS NOT NULL AND case_law_region IS NOT NULL
            """
            result = self._execute_query(count_sql)
            count = result[0]["cnt"] if result else 0
            logger.info(f"  [DRY RUN] Would update {count} citations")
            return count

        # Execute the update
        rows_updated = self._execute_update(classification_sql)
        self.stats["classifications_updated"] = rows_updated
        logger.info(f"  ✓ Updated {rows_updated} citations with sixfold classification")

        # Show distribution of classifications
        dist_sql = """
            SELECT citation_type, COUNT(*) as cnt
            FROM citation_extraction_phased
            WHERE citation_type IS NOT NULL
            GROUP BY citation_type
            ORDER BY cnt DESC
        """
        distribution = self._execute_query(dist_sql)

        logger.info("\n  Classification distribution:")
        for row in distribution:
            logger.info(f"    {row['citation_type']}: {row['cnt']}")

        return rows_updated

    # =========================================================================
    # PART 2: UNIQUE CITATIONS TRACKING (who cites this case)
    # =========================================================================

    def update_unique_citations(self, dry_run: bool = False) -> int:
        """
        Update unique_citations and citing_cases for each case.

        Counts how many UNIQUE cases cite each case (one citation per citing case,
        regardless of how many times the citing case references the cited case).

        INPUT:
            - dry_run: If True, only report what would be updated

        ALGORITHM:
            1. For each case that appears as a cited case (in case_name column):
               a. Find all documents that cite it
               b. Get unique case_ids from those documents
               c. Update the cited case with count and list of citing case_ids

        OUTPUT:
            - int: Number of cases updated
        """
        logger.info("\n" + "=" * 70)
        logger.info("PART 2: UNIQUE CITATIONS TRACKING (cases citing each case)")
        logger.info("=" * 70)

        # This query finds for each case (matched by case_name):
        # - The unique citing cases (via documents referencing it)
        # - Count and list of citing case_ids

        # Note: We match cases by comparing case_name in citations to cases.case_name
        # This is an approximation since exact case matching is complex

        update_sql = """
        WITH citing_data AS (
            SELECT
                c.case_id AS cited_case_id,
                ARRAY_AGG(DISTINCT d.case_id) FILTER (WHERE d.case_id IS NOT NULL AND d.case_id != c.case_id) AS citing_case_ids,
                COUNT(DISTINCT d.case_id) FILTER (WHERE d.case_id IS NOT NULL AND d.case_id != c.case_id) AS citing_count
            FROM cases c
            JOIN citation_extraction_phased cep ON
                -- Match by case name (case-insensitive, partial match)
                LOWER(cep.case_name) LIKE '%' || LOWER(SUBSTRING(c.case_name FROM 1 FOR 50)) || '%'
                OR LOWER(c.case_name) LIKE '%' || LOWER(SUBSTRING(cep.case_name FROM 1 FOR 50)) || '%'
            JOIN documents d ON cep.document_id = d.document_id
            WHERE cep.case_name IS NOT NULL
              AND c.case_name IS NOT NULL
            GROUP BY c.case_id
        )
        UPDATE cases c
        SET
            unique_citations = COALESCE(cd.citing_count, 0),
            citing_cases = cd.citing_case_ids
        FROM citing_data cd
        WHERE c.case_id = cd.cited_case_id
          AND cd.citing_count > 0
        """

        if dry_run:
            # Count how many cases have citations
            count_sql = """
                SELECT COUNT(DISTINCT cep.case_name) as cnt
                FROM citation_extraction_phased cep
                WHERE cep.case_name IS NOT NULL
            """
            result = self._execute_query(count_sql)
            count = result[0]["cnt"] if result else 0
            logger.info(f"  [DRY RUN] Would analyze {count} unique cited case names")
            return count

        rows_updated = self._execute_update(update_sql)
        self.stats["cases_with_citations_updated"] = rows_updated
        logger.info(f"  ✓ Updated {rows_updated} cases with citation tracking data")

        # Show top cited cases
        top_sql = """
            SELECT case_name, unique_citations, ARRAY_LENGTH(citing_cases, 1) as num_citing
            FROM cases
            WHERE unique_citations > 0
            ORDER BY unique_citations DESC
            LIMIT 10
        """
        top_cases = self._execute_query(top_sql)

        if top_cases:
            logger.info("\n  Top 10 most cited cases:")
            for row in top_cases:
                name = (
                    row["case_name"][:50] + "..."
                    if len(row["case_name"]) > 50
                    else row["case_name"]
                )
                logger.info(f"    {row['unique_citations']} citations: {name}")

        return rows_updated

    # =========================================================================
    # PART 3: UNIQUE CITED CASES TRACKING (cases cited BY this case)
    # =========================================================================

    def update_unique_cited_cases(self, dry_run: bool = False) -> int:
        """
        Update unique_cited_count and cited_cases for each case.

        Counts how many UNIQUE cases are cited BY each case (excluding duplicate
        references to the same cited case).

        INPUT:
            - dry_run: If True, only report what would be updated

        ALGORITHM:
            1. For each case:
               a. Find all citations from documents belonging to that case
               b. Get unique case_names from those citations
               c. Try to match cited case_names to actual case_ids where possible
               d. Update the case with count and list of cited case references

        OUTPUT:
            - int: Number of cases updated
        """
        logger.info("\n" + "=" * 70)
        logger.info("PART 3: UNIQUE CITED CASES TRACKING (cases cited BY each case)")
        logger.info("=" * 70)

        # This query finds for each case:
        # - All unique case names it cites
        # - Tries to match to actual case_ids where possible

        update_sql = """
        WITH cited_data AS (
            SELECT
                d.case_id AS citing_case_id,
                -- Get unique cited case names (as identifiers since we may not have case_ids)
                ARRAY_AGG(DISTINCT cep.case_name) FILTER (WHERE cep.case_name IS NOT NULL) AS cited_case_names,
                COUNT(DISTINCT cep.case_name) FILTER (WHERE cep.case_name IS NOT NULL) AS cited_count
            FROM documents d
            JOIN citation_extraction_phased cep ON d.document_id = cep.document_id
            WHERE cep.case_name IS NOT NULL
            GROUP BY d.case_id
        )
        UPDATE cases c
        SET
            unique_cited_count = COALESCE(cd.cited_count, 0),
            cited_cases = cd.cited_case_names
        FROM cited_data cd
        WHERE c.case_id = cd.citing_case_id
          AND cd.cited_count > 0
        """

        if dry_run:
            # Count how many cases have outgoing citations
            count_sql = """
                SELECT COUNT(DISTINCT d.case_id) as cnt
                FROM documents d
                JOIN citation_extraction_phased cep ON d.document_id = cep.document_id
                WHERE cep.case_name IS NOT NULL
            """
            result = self._execute_query(count_sql)
            count = result[0]["cnt"] if result else 0
            logger.info(f"  [DRY RUN] Would analyze {count} cases with outgoing citations")
            return count

        rows_updated = self._execute_update(update_sql)
        self.stats["cases_with_cited_updated"] = rows_updated
        logger.info(f"  ✓ Updated {rows_updated} cases with cited cases tracking data")

        # Show top citing cases
        top_sql = """
            SELECT case_name, unique_cited_count
            FROM cases
            WHERE unique_cited_count > 0
            ORDER BY unique_cited_count DESC
            LIMIT 10
        """
        top_cases = self._execute_query(top_sql)

        if top_cases:
            logger.info("\n  Top 10 cases citing the most other cases:")
            for row in top_cases:
                name = (
                    row["case_name"][:50] + "..."
                    if len(row["case_name"]) > 50
                    else row["case_name"]
                )
                logger.info(f"    {row['unique_cited_count']} cited: {name}")

        return rows_updated

    # =========================================================================
    # MAIN EXECUTION
    # =========================================================================

    def run_full_classification(
        self, dry_run: bool = False, classification_only: bool = False, tracking_only: bool = False
    ) -> dict[str, int]:
        """
        Run the complete classification and tracking process.

        INPUT:
            - dry_run: If True, only report what would be done
            - classification_only: Only run sixfold classification
            - tracking_only: Only run citation tracking

        OUTPUT:
            - Dict with statistics
        """
        start_time = datetime.now()

        logger.info("=" * 70)
        logger.info("SIXFOLD CLASSIFICATION AND CITATION TRACKING")
        logger.info(f"Started: {start_time.isoformat()}")
        if dry_run:
            logger.info("MODE: DRY RUN (no changes will be made)")
        logger.info("=" * 70)

        try:
            # Part 1: Sixfold Classification
            if not tracking_only:
                self.update_citation_types(dry_run=dry_run)

            # Part 2 & 3: Citation Tracking
            if not classification_only:
                self.update_unique_citations(dry_run=dry_run)
                self.update_unique_cited_cases(dry_run=dry_run)

            # Summary
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            logger.info("\n" + "=" * 70)
            logger.info("FINAL SUMMARY")
            logger.info("=" * 70)
            logger.info(f"  Classifications updated: {self.stats['classifications_updated']}")
            logger.info(f"  Cases with citing data:  {self.stats['cases_with_citations_updated']}")
            logger.info(f"  Cases with cited data:   {self.stats['cases_with_cited_updated']}")
            logger.info(f"  Errors:                  {self.stats['errors']}")
            logger.info(f"  Duration:                {duration:.1f} seconds")
            logger.info("=" * 70)
            logger.info("✓ Classification and tracking completed!")

            return self.stats

        except Exception as e:
            logger.error(f"✗ Classification failed: {e}")
            import traceback

            logger.error(traceback.format_exc())
            self.stats["errors"] += 1
            return self.stats


# =============================================================================
# COMMAND-LINE INTERFACE
# =============================================================================


def main():
    """Main entry point for command-line execution."""
    parser = argparse.ArgumentParser(
        description="Sixfold Decision Classification and Citation Tracking"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report what would be done, without making changes",
    )
    parser.add_argument(
        "--classification-only",
        action="store_true",
        help="Only run sixfold classification, skip citation tracking",
    )
    parser.add_argument(
        "--tracking-only",
        action="store_true",
        help="Only run citation tracking, skip classification",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    engine = SixfoldClassificationEngine()
    stats = engine.run_full_classification(
        dry_run=args.dry_run,
        classification_only=args.classification_only,
        tracking_only=args.tracking_only,
    )

    sys.exit(0 if stats["errors"] == 0 else 1)


if __name__ == "__main__":
    main()
