#!/usr/bin/env python3
"""
Export Agentic-Extraction Output to Excel
==========================================
Exports only the rows produced by the corpus-run orchestrator (citation_agent_v1*
tables), enriched with case_name + URLs for traceability.

Three sheets:
  - citations  : every row in citation_agent_v1 (incl. dismissed; filter by
                 verification_verdict in Excel)
  - summaries  : per-document stats from citation_agent_v1_summary
  - run_state  : run_state rows for documents the agent has touched
                 (status IN ('complete','failed','in_progress')) — pending
                 rows are excluded as they predate any agent activity.

Reuses sanitization helpers from scripts/export_to_excel.py.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from export_to_excel import _clean_df_for_excel  # noqa: E402  (brings openpyxl monkey-patch)
from gcp_secrets import get_database_url_auto  # noqa: E402

DATABASE_URL = get_database_url_auto()
OUTPUT_DIR = PROJECT_ROOT / "data" / "exports"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "export_agentic_to_excel.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


SHEETS = {
    "citations": """
        SELECT
            c.case_name              AS source_case_name,
            c.case_url               AS source_case_url,
            d.document_url           AS source_document_url,
            ag.*
        FROM citation_agent_v1 ag
        JOIN documents d ON ag.document_id = d.document_id
        JOIN cases     c ON d.case_id     = c.case_id
        ORDER BY c.case_name, ag.document_id, ag.citation_index
    """,
    "summaries": """
        SELECT
            c.case_name              AS source_case_name,
            c.case_url               AS source_case_url,
            d.document_url           AS source_document_url,
            s.*
        FROM citation_agent_v1_summary s
        JOIN documents d ON s.document_id = d.document_id
        JOIN cases     c ON d.case_id     = c.case_id
        ORDER BY s.verification_timestamp DESC
    """,
    "run_state": """
        SELECT
            c.case_name              AS source_case_name,
            c.case_url               AS source_case_url,
            d.document_url           AS source_document_url,
            rs.*
        FROM citation_agent_v1_run_state rs
        JOIN documents d ON rs.document_id = d.document_id
        JOIN cases     c ON d.case_id     = c.case_id
        WHERE rs.status IN ('complete','failed','in_progress')
        ORDER BY rs.last_attempt_finished DESC NULLS LAST
    """,
}


def export(output_file: Path | None = None) -> Path:
    if output_file is None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = OUTPUT_DIR / f"agentic_extraction_export_{stamp}.xlsx"
    output_file = Path(output_file)

    log.info("=" * 60)
    log.info("AGENTIC-EXTRACTION EXPORT")
    log.info("=" * 60)
    log.info(f"Output: {output_file}")

    engine = create_engine(DATABASE_URL, echo=False)
    try:
        with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
            for sheet_name, sql in SHEETS.items():
                log.info(f"\n[{sheet_name}] querying…")
                df = pd.read_sql_query(text(sql), engine)
                log.info(f"  rows: {len(df):,}")
                _clean_df_for_excel(df)
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                log.info(f"  ✓ written")
    finally:
        engine.dispose()

    size_mb = output_file.stat().st_size / 1024 / 1024
    log.info("=" * 60)
    log.info(f"✓ Done — {size_mb:.2f} MB")
    log.info(f"  {output_file}")
    log.info("=" * 60)
    return output_file


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Export agentic-extraction tables to Excel")
    p.add_argument("--output", "-o", type=str, help="Output .xlsx path (default: timestamped)")
    args = p.parse_args()
    export(Path(args.output) if args.output else None)
