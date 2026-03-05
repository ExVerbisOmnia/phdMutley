#!/usr/bin/env python3
"""
Export static site data for GitHub Pages deployment.

Runs the analysis engine and generates all JSON files needed by docs/index.html.
"""

import json
import logging
import shutil
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

# Resolve imports
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gcp_secrets import get_database_url_auto

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ExportStaticSite")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DATA = PROJECT_ROOT / "docs" / "data"
ENGINE_DIR = PROJECT_ROOT / "scripts" / "8-python_back_engine"


def run_analysis_engine():
    """Run the sixfold analysis engine to generate analysis_output/ files."""
    sys.path.insert(0, str(ENGINE_DIR))
    from sixfold_analysis_engine import SixfoldAnalysisEngine

    engine = SixfoldAnalysisEngine()
    engine.run_full_analysis()
    logger.info("Analysis engine completed")


def copy_engine_output():
    """Copy analysis engine output files to docs/data/."""
    DOCS_DATA.mkdir(parents=True, exist_ok=True)

    analysis_output = Path("./analysis_output")

    # dashboard_complete.json
    src = analysis_output / "dashboard_data" / "dashboard_complete.json"
    if src.exists():
        shutil.copy2(src, DOCS_DATA / "dashboard_complete.json")
        logger.info(f"Copied {src.name}")
    else:
        logger.warning(f"Missing: {src}")

    # network.json (D3 format)
    src = analysis_output / "network_data" / "d3_network.json"
    if src.exists():
        shutil.copy2(src, DOCS_DATA / "network.json")
        logger.info("Copied d3_network.json → network.json")
    else:
        logger.warning(f"Missing: {src}")

    # nodes.json (full node attributes)
    src = analysis_output / "network_data" / "nodes.json"
    if src.exists():
        shutil.copy2(src, DOCS_DATA / "nodes.json")
        logger.info(f"Copied {src.name}")
    else:
        logger.warning(f"Missing: {src}")


def export_custom_queries():
    """Run custom SQL queries and write results to docs/data/."""
    db_url = get_database_url_auto()
    engine = create_engine(db_url)

    # flow.json — all jurisdiction pairs with citation counts
    flow_sql = """
        SELECT
            source_jurisdiction,
            source_region,
            case_law_origin,
            case_law_region,
            sixfold_type,
            COUNT(*) as citation_count
        FROM citation_sixfold_classification
        WHERE 1=1
        GROUP BY source_jurisdiction, source_region,
                 case_law_origin, case_law_region, sixfold_type
        ORDER BY citation_count DESC
    """

    # citations_received.json — citations received by jurisdiction
    received_sql = """
        SELECT
            case_law_origin as label,
            case_law_region as region,
            COUNT(*) as citations_received
        FROM citation_sixfold_classification
        GROUP BY case_law_origin, case_law_region
        ORDER BY citations_received DESC
    """

    # citations_by_jurisdiction.json — ALL case-level citations
    by_jurisdiction_sql = """
        SELECT
            c.case_name,
            c.case_url,
            v.source_jurisdiction,
            v.source_region,
            cep.cited_year,
            cep.cited_case_citation as cited_case_name,
            v.case_law_origin,
            v.sixfold_type as citation_type
        FROM citation_sixfold_classification v
        JOIN cases c ON v.case_id = c.case_id
        JOIN citation_extraction_phased cep ON v.extraction_id = cep.extraction_id
    """

    queries = {
        "flow.json": flow_sql,
        "citations_received.json": received_sql,
        "citations_by_jurisdiction.json": by_jurisdiction_sql,
    }

    with engine.connect() as conn:
        for filename, sql in queries.items():
            result = conn.execute(text(sql))
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result.fetchall()]
            out_path = DOCS_DATA / filename
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False, default=str)
            logger.info(f"Exported {filename}: {len(rows)} rows")


def main():
    logger.info("=" * 60)
    logger.info("EXPORT STATIC SITE DATA")
    logger.info("=" * 60)

    logger.info("\n[Step 1/3] Running analysis engine...")
    run_analysis_engine()

    logger.info("\n[Step 2/3] Copying engine output to docs/data/...")
    copy_engine_output()

    logger.info("\n[Step 3/3] Exporting custom queries to docs/data/...")
    export_custom_queries()

    logger.info("\n" + "=" * 60)
    logger.info("Export complete. Files written to docs/data/")
    logger.info("To preview: cd docs && python -m http.server 8080")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
