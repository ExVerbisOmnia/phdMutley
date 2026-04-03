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
import json
import logging
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# =============================================================================
# LOGGING CONFIGURATION — Rich file + console logging
# =============================================================================

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f"sixfold_classification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# File handler — DEBUG level, full detail
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(
    logging.Formatter("%(asctime)s | %(name)s | %(levelname)-7s | %(message)s")
)

# Console handler — INFO level
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)

# Root logger setup
logging.basicConfig(level=logging.DEBUG, handlers=[file_handler, console_handler])
logger = logging.getLogger("SixfoldClassification")
logger.info(f"Log file: {LOG_FILE}")

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
            "diagnostics": {},
        }

        logger.info("SixfoldClassificationEngine initialized")

    # =========================================================================
    # DIAGNOSTIC METHODS
    # =========================================================================

    def _run_pre_classification_diagnostics(self):
        """Log detailed pre-classification data quality checks."""
        logger.info("=" * 70)
        logger.info("PRE-CLASSIFICATION DIAGNOSTICS")
        logger.info("=" * 70)

        diag = {}

        # 1. Total citation counts
        result = self._execute_query("""
            SELECT
                COUNT(*) as total,
                COUNT(source_region) as has_source_region,
                COUNT(case_law_region) as has_case_law_region,
                COUNT(CASE WHEN source_region IS NOT NULL AND case_law_region IS NOT NULL THEN 1 END) as classifiable,
                COUNT(source_jurisdiction) as has_source_jurisdiction,
                COUNT(case_law_origin) as has_case_law_origin,
                COUNT(cited_court) as has_cited_court,
                COUNT(citation_type) as has_existing_type
            FROM citation_extraction_phased
        """)
        row = result[0]
        diag["totals"] = row
        logger.info(f"  Total citations:           {row['total']}")
        logger.info(f"  Has source_region:         {row['has_source_region']}")
        logger.info(f"  Has case_law_region:       {row['has_case_law_region']}")
        logger.info(f"  Classifiable (both set):   {row['classifiable']}")
        logger.info(f"  Has source_jurisdiction:   {row['has_source_jurisdiction']}")
        logger.info(f"  Has case_law_origin:       {row['has_case_law_origin']}")
        logger.info(f"  Has cited_court:           {row['has_cited_court']}")
        logger.info(f"  Has existing citation_type:{row['has_existing_type']}")

        # 2. Source region distribution
        result = self._execute_query("""
            SELECT source_region, COUNT(*) as cnt
            FROM citation_extraction_phased GROUP BY source_region ORDER BY cnt DESC
        """)
        diag["source_region_dist"] = {r["source_region"]: r["cnt"] for r in result}
        logger.info("\n  Source region distribution:")
        for r in result:
            logger.info(f"    {r['source_region']}: {r['cnt']}")

        # 3. Case law region distribution
        result = self._execute_query("""
            SELECT case_law_region, COUNT(*) as cnt
            FROM citation_extraction_phased GROUP BY case_law_region ORDER BY cnt DESC
        """)
        diag["case_law_region_dist"] = {r["case_law_region"]: r["cnt"] for r in result}
        logger.info("\n  Case law region distribution:")
        for r in result:
            logger.info(f"    {r['case_law_region']}: {r['cnt']}")

        # 4. Existing citation_type distribution (before reclassification)
        result = self._execute_query("""
            SELECT COALESCE(citation_type, 'NULL') as ct, COUNT(*) as cnt
            FROM citation_extraction_phased GROUP BY citation_type ORDER BY cnt DESC
        """)
        diag["existing_type_dist"] = {r["ct"]: r["cnt"] for r in result}
        logger.info("\n  Existing citation_type distribution (PRE-classification):")
        for r in result:
            logger.info(f"    {r['ct']}: {r['cnt']}")

        # 5. Cross-jurisdictional vs domestic breakdown
        result = self._execute_query("""
            SELECT
                COUNT(CASE WHEN source_jurisdiction = case_law_origin THEN 1 END) as domestic,
                COUNT(CASE WHEN source_jurisdiction != case_law_origin THEN 1 END) as cross_jurisdictional,
                COUNT(CASE WHEN source_jurisdiction IS NULL OR case_law_origin IS NULL THEN 1 END) as unknown
            FROM citation_extraction_phased
            WHERE source_region IS NOT NULL AND case_law_region IS NOT NULL
        """)
        row = result[0]
        diag["domestic_vs_cross"] = row
        logger.info(f"\n  Domestic (same jurisdiction):       {row['domestic']}")
        logger.info(f"  Cross-jurisdictional (different):   {row['cross_jurisdictional']}")
        logger.info(f"  Unknown (NULL jurisdiction):        {row['unknown']}")

        # 6. International court jurisdiction table check
        result = self._execute_query("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'international_court_jurisdiction'
            ) as exists_flag
        """)
        icj_exists = result[0]["exists_flag"]
        diag["icj_table_exists"] = icj_exists
        logger.info(f"\n  international_court_jurisdiction table exists: {icj_exists}")

        if icj_exists:
            result = self._execute_query("""
                SELECT court_abbreviation, court_name, court_system,
                       array_length(member_jurisdictions, 1) as member_count
                FROM international_court_jurisdiction
                ORDER BY court_system, court_name
            """)
            logger.info(f"  Courts loaded: {len(result)}")
            for r in result:
                logger.info(f"    {r['court_abbreviation']:8s} | {r['court_name'][:40]:40s} | {r['member_count'] or 0} members")
        else:
            logger.warning("  PREREQUISITE MISSING: international_court_jurisdiction table not found!")

        # 7. Region combination matrix (what sixfold branches will be triggered)
        result = self._execute_query("""
            SELECT source_region, case_law_region, COUNT(*) as cnt
            FROM citation_extraction_phased
            WHERE source_region IS NOT NULL AND case_law_region IS NOT NULL
            GROUP BY source_region, case_law_region
            ORDER BY cnt DESC
        """)
        diag["region_matrix"] = [(r["source_region"], r["case_law_region"], r["cnt"]) for r in result]
        logger.info("\n  Region combination matrix (source -> case_law):")
        for r in result:
            logger.info(f"    {r['source_region']:20s} -> {r['case_law_region']:20s} : {r['cnt']}")

        # 8. Sample of International citations — show what court matching will use
        result = self._execute_query("""
            SELECT source_jurisdiction, case_law_origin, cited_court, case_law_region, source_region
            FROM citation_extraction_phased
            WHERE (source_region = 'International' OR case_law_region = 'International')
            LIMIT 20
        """)
        logger.debug("\n  Sample of International citations (first 20):")
        for r in result:
            logger.debug(f"    src={r['source_jurisdiction']!r}, origin={r['case_law_origin']!r}, court={r['cited_court']!r}")

        self.stats["diagnostics"]["pre"] = diag
        logger.info("=" * 70)
        return diag

    def _run_post_classification_diagnostics(self):
        """Log detailed post-classification results and quality checks."""
        logger.info("=" * 70)
        logger.info("POST-CLASSIFICATION DIAGNOSTICS")
        logger.info("=" * 70)

        diag = {}

        # 1. New citation_type distribution
        result = self._execute_query("""
            SELECT COALESCE(citation_type, 'NULL') as ct, COUNT(*) as cnt
            FROM citation_extraction_phased GROUP BY citation_type ORDER BY cnt DESC
        """)
        diag["new_type_dist"] = {r["ct"]: r["cnt"] for r in result}
        logger.info("  New citation_type distribution (POST-classification):")
        total = sum(r["cnt"] for r in result)
        for r in result:
            pct = (r["cnt"] / total * 100) if total > 0 else 0
            logger.info(f"    {r['ct']:35s}: {r['cnt']:6d}  ({pct:5.1f}%)")

        # 2. Unclassified analysis — WHY were they unclassified?
        result = self._execute_query("""
            SELECT source_region, case_law_region, source_jurisdiction, case_law_origin,
                   COUNT(*) as cnt
            FROM citation_extraction_phased
            WHERE citation_type = 'Unclassified'
            GROUP BY source_region, case_law_region, source_jurisdiction, case_law_origin
            ORDER BY cnt DESC
            LIMIT 20
        """)
        if result:
            diag["unclassified_reasons"] = result
            logger.warning(f"\n  UNCLASSIFIED citations: {sum(r['cnt'] for r in result)} (top 20 patterns):")
            for r in result:
                logger.warning(f"    src_region={r['source_region']!r}, cl_region={r['case_law_region']!r}, "
                             f"src_jur={r['source_jurisdiction']!r}, cl_origin={r['case_law_origin']!r} -> {r['cnt']}")

        # 3. Domestic citations that became Unclassified (expected behavior)
        result = self._execute_query("""
            SELECT COUNT(*) as cnt FROM citation_extraction_phased
            WHERE citation_type = 'Unclassified'
              AND source_jurisdiction = case_law_origin
        """)
        domestic_unclassified = result[0]["cnt"]
        diag["domestic_unclassified"] = domestic_unclassified
        logger.info(f"\n  Domestic citations now Unclassified: {domestic_unclassified}")
        logger.info(f"  (These are same-jurisdiction citations — expected to be Unclassified in sixfold)")

        # 4. Sixfold type by direction
        result = self._execute_query("""
            SELECT
                citation_type,
                CASE
                    WHEN source_region IN ('Global North','Global South') AND case_law_region IN ('Global North','Global South') THEN 'National -> National'
                    WHEN source_region IN ('Global North','Global South') AND case_law_region = 'International' THEN 'National -> International'
                    WHEN source_region = 'International' AND case_law_region = 'International' THEN 'International -> International'
                    WHEN source_region = 'International' AND case_law_region IN ('Global North','Global South') THEN 'International -> National'
                    ELSE 'Other'
                END as direction,
                COUNT(*) as cnt
            FROM citation_extraction_phased
            WHERE citation_type IS NOT NULL
            GROUP BY citation_type, direction
            ORDER BY direction, cnt DESC
        """)
        diag["type_by_direction"] = result
        logger.info("\n  Classification by direction:")
        for r in result:
            logger.info(f"    [{r['direction']:30s}] {r['citation_type']:35s}: {r['cnt']}")

        # 5. North-South asymmetry in Foreign Citations
        result = self._execute_query("""
            SELECT source_region, case_law_region, COUNT(*) as cnt
            FROM citation_extraction_phased
            WHERE citation_type = 'Foreign Citation'
            GROUP BY source_region, case_law_region
            ORDER BY cnt DESC
        """)
        if result:
            diag["foreign_asymmetry"] = result
            logger.info("\n  Foreign Citation North-South flow:")
            for r in result:
                logger.info(f"    {r['source_region']} -> {r['case_law_region']}: {r['cnt']}")

        # 6. Top 5 paradigmatic cases (most cited across documents)
        result = self._execute_query("""
            SELECT case_name, case_law_origin, citation_type,
                   COUNT(DISTINCT document_id) as doc_count,
                   COUNT(*) as total_refs
            FROM citation_extraction_phased
            WHERE citation_type NOT IN ('Unclassified', 'Domestic')
              AND case_name IS NOT NULL
            GROUP BY case_name, case_law_origin, citation_type
            ORDER BY doc_count DESC
            LIMIT 10
        """)
        if result:
            diag["paradigmatic_cases"] = result
            logger.info("\n  Top 10 paradigmatic cases (by distinct documents citing them):")
            for r in result:
                name = r['case_name'][:55] + '...' if len(r['case_name'] or '') > 55 else r['case_name']
                logger.info(f"    {r['doc_count']:3d} docs | {r['total_refs']:3d} refs | {r['citation_type']:30s} | {name}")

        self.stats["diagnostics"]["post"] = diag
        logger.info("=" * 70)
        return diag

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
            # Pre-classification diagnostics
            self._run_pre_classification_diagnostics()

            # Part 1: Sixfold Classification
            if not tracking_only:
                self.update_citation_types(dry_run=dry_run)

            # Post-classification diagnostics (only if not dry run and classification ran)
            if not dry_run and not tracking_only:
                self._run_post_classification_diagnostics()

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
            logger.info("Classification and tracking completed!")
            logger.info(f"Full log saved to: {LOG_FILE}")

            # Export diagnostics to JSON for downstream inspection
            diag_file = LOG_DIR / f"sixfold_diagnostics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            try:
                # Convert non-serializable values
                serializable_stats = json.loads(json.dumps(self.stats, default=str))
                with open(diag_file, "w", encoding="utf-8") as f:
                    json.dump(serializable_stats, f, indent=2, ensure_ascii=False)
                logger.info(f"Diagnostics JSON saved to: {diag_file}")
            except Exception as je:
                logger.warning(f"Could not save diagnostics JSON: {je}")

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
