#!/usr/bin/env python3
"""Delete Phase 2A failed summaries so they can be retried. Keep garbled skips."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gcp_secrets import get_engine
from sqlalchemy import text

engine = get_engine()
with engine.connect() as conn:
    # Show failure breakdown
    rows = conn.execute(text(
        "SELECT extraction_error, COUNT(*) FROM citation_extraction_phased_summary "
        "WHERE extraction_success = false GROUP BY extraction_error"
    )).fetchall()
    print("Failed summaries by type:")
    for r in rows:
        print(f"  {str(r[0])[:80]}: {r[1]}")

    # Delete Phase 2A failures (retryable with lower concurrency)
    d = conn.execute(text(
        "DELETE FROM citation_extraction_phased_summary "
        "WHERE extraction_success = false "
        "AND extraction_error LIKE 'Phase 2A%'"
    ))
    print(f"\nDeleted {d.rowcount} Phase 2A failure summaries (will be retried)")
    conn.commit()

    remaining = conn.execute(text("SELECT COUNT(*) FROM citation_extraction_phased_summary").execution_options(autocommit=True)).scalar()
    success = conn.execute(text("SELECT COUNT(*) FROM citation_extraction_phased_summary WHERE extraction_success = true")).scalar()
    failed = conn.execute(text("SELECT COUNT(*) FROM citation_extraction_phased_summary WHERE extraction_success = false")).scalar()
    print(f"\nRemaining: {remaining} summaries ({success} success, {failed} failed/garbled)")
    print(f"Documents to process on re-launch: {4724 - remaining}")
engine.dispose()
