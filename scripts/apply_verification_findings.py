#!/usr/bin/env python3
"""
Apply Claude Chat Verification Findings
==========================================
One-time cleanup script that reads the Claude Chat manual verification
results and updates citation_extraction_phased records accordingly.

Source: data/processed/claude-chat-verification-run-output.xlsx
- 1,410 citations manually verified by Claude Chat against source PDFs
- 49.3% REJECTED, 3.8% CORRECTED, 3.6% UNCLEAR

Usage:
    python scripts/apply_verification_findings.py              # dry run
    python scripts/apply_verification_findings.py --apply       # actually update DB
    python scripts/apply_verification_findings.py --apply --verbose
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import text as sa_text
from sqlalchemy.orm import sessionmaker

# Path setup
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPTS_DIR)
sys.path.insert(0, os.path.join(_SCRIPTS_DIR, "0-initialize-database"))

from config import LOGS_DIR
from gcp_secrets import get_engine

# Logging
LOGS_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "apply_verification_findings.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

# Source file
EXCEL_PATH = Path(_SCRIPTS_DIR).parent / "data" / "processed" / "claude-chat-verification-run-output.xlsx"


def load_findings(excel_path: Path) -> pd.DataFrame:
    """Load and validate the Claude Chat verification Excel."""
    if not excel_path.exists():
        raise FileNotFoundError(f"Verification findings not found: {excel_path}")

    df = pd.read_excel(excel_path)
    logging.info(f"Loaded {len(df)} rows from {excel_path.name}")

    # Expected columns (flexible — check what exists)
    required = {"extraction_id"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}. Available: {list(df.columns)}")

    return df


def apply_findings(df: pd.DataFrame, apply: bool = False, verbose: bool = False):
    """
    Apply verification findings to the database.

    INPUT:
        - df: DataFrame with columns: extraction_id, verdict (CONFIRMED/REJECTED/CORRECTED/UNCLEAR),
              corrected_case_name (optional), notes (optional)
        - apply: If False, only report what would change (dry run)
        - verbose: Log each update
    """
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    stats = {
        "rejected": 0,
        "corrected": 0,
        "unclear": 0,
        "confirmed": 0,
        "skipped": 0,
        "errors": 0,
    }

    now = datetime.now(timezone.utc)

    # Identify verdict column (may be named differently in the Excel)
    verdict_col = None
    for candidate in ["verdict", "status", "verification_result", "result", "claude_verdict"]:
        if candidate in df.columns:
            verdict_col = candidate
            break

    if verdict_col is None:
        logging.error(f"No verdict column found. Available columns: {list(df.columns)}")
        return stats

    logging.info(f"Using verdict column: '{verdict_col}'")

    # Identify corrected name column
    corrected_col = None
    for candidate in ["corrected_case_name", "corrected_name", "correct_name"]:
        if candidate in df.columns:
            corrected_col = candidate
            break

    # Identify notes column
    notes_col = None
    for candidate in ["notes", "verification_notes", "claude_notes"]:
        if candidate in df.columns:
            notes_col = candidate
            break

    try:
        for _, row in df.iterrows():
            extraction_id = str(row["extraction_id"])
            verdict = str(row.get(verdict_col, "")).strip().upper()

            if not extraction_id or extraction_id == "nan":
                stats["skipped"] += 1
                continue

            if verdict in ("REJECTED", "NOT_FOUND", "HALLUCINATED"):
                if apply:
                    session.execute(sa_text("""
                        UPDATE citation_extraction_phased
                        SET verification_status = 'REJECTED',
                            verification_notes = :notes,
                            verification_model = 'claude-chat-manual',
                            verified_at = :now,
                            requires_manual_review = FALSE
                        WHERE extraction_id = :eid
                    """), {
                        "eid": extraction_id,
                        "notes": f"Claude Chat manual verification: REJECTED. {row.get(notes_col, '') if notes_col else ''}".strip(),
                        "now": now,
                    })
                stats["rejected"] += 1
                if verbose:
                    logging.info(f"  REJECTED: {extraction_id}")

            elif verdict == "CORRECTED":
                corrected_name = row.get(corrected_col, "") if corrected_col else ""
                if apply:
                    session.execute(sa_text("""
                        UPDATE citation_extraction_phased
                        SET verification_status = 'CORRECTED',
                            verification_notes = :notes,
                            verification_model = 'claude-chat-manual',
                            verified_at = :now,
                            requires_manual_review = FALSE
                        WHERE extraction_id = :eid
                    """), {
                        "eid": extraction_id,
                        "notes": f"Corrected: {corrected_name}. {row.get(notes_col, '') if notes_col else ''}".strip(),
                        "now": now,
                    })
                stats["corrected"] += 1
                if verbose:
                    logging.info(f"  CORRECTED: {extraction_id} → {corrected_name}")

            elif verdict in ("UNCLEAR", "UNCERTAIN"):
                if apply:
                    session.execute(sa_text("""
                        UPDATE citation_extraction_phased
                        SET requires_manual_review = TRUE,
                            manual_review_reason = 'UNCLEAR_MANUAL: Claude Chat could not determine',
                            verification_model = 'claude-chat-manual',
                            verified_at = :now
                        WHERE extraction_id = :eid
                    """), {
                        "eid": extraction_id,
                        "now": now,
                    })
                stats["unclear"] += 1
                if verbose:
                    logging.info(f"  UNCLEAR: {extraction_id}")

            elif verdict in ("CONFIRMED", "ACCEPTED"):
                stats["confirmed"] += 1

            else:
                stats["skipped"] += 1
                if verbose:
                    logging.info(f"  SKIPPED (unknown verdict '{verdict}'): {extraction_id}")

        if apply:
            session.commit()
            logging.info("Changes committed to database")
        else:
            session.rollback()
            logging.info("DRY RUN — no changes applied")

    except Exception as e:
        session.rollback()
        logging.error(f"Error applying findings: {e}")
        import traceback
        logging.error(traceback.format_exc())
        stats["errors"] += 1
    finally:
        session.close()
        engine.dispose()

    return stats


def main():
    parser = argparse.ArgumentParser(description="Apply Claude Chat verification findings to DB")
    parser.add_argument("--apply", action="store_true", help="Actually update the database (default: dry run)")
    parser.add_argument("--verbose", action="store_true", help="Log each update")
    parser.add_argument("--file", type=str, default=str(EXCEL_PATH), help="Path to verification Excel")
    args = parser.parse_args()

    logging.info("=" * 70)
    logging.info("APPLY CLAUDE CHAT VERIFICATION FINDINGS")
    logging.info("=" * 70)
    logging.info(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")
    logging.info(f"Source: {args.file}")

    df = load_findings(Path(args.file))

    # Report distribution
    verdict_col = None
    for candidate in ["verdict", "status", "verification_result", "result", "claude_verdict"]:
        if candidate in df.columns:
            verdict_col = candidate
            break

    if verdict_col:
        logging.info(f"\nVerdict distribution:")
        for verdict, count in df[verdict_col].value_counts().items():
            logging.info(f"  {verdict}: {count}")

    stats = apply_findings(df, apply=args.apply, verbose=args.verbose)

    logging.info("\n" + "=" * 70)
    logging.info("RESULTS")
    logging.info("=" * 70)
    logging.info(f"REJECTED:   {stats['rejected']}")
    logging.info(f"CORRECTED:  {stats['corrected']}")
    logging.info(f"UNCLEAR:    {stats['unclear']}")
    logging.info(f"CONFIRMED:  {stats['confirmed']} (no DB change needed)")
    logging.info(f"SKIPPED:    {stats['skipped']}")
    logging.info(f"ERRORS:     {stats['errors']}")
    logging.info("=" * 70)


if __name__ == "__main__":
    main()
