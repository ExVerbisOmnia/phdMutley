#!/usr/bin/env python3
"""Detailed extraction status check for VM. Shows errors, verification, and progress."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gcp_secrets import get_engine
from sqlalchemy import text

engine = get_engine()
target = int(sys.argv[1]) if len(sys.argv) > 1 else 4724

with engine.connect() as conn:
    # Overall progress (no time filter — DB was cleared before run)
    total = conn.execute(text(
        "SELECT COUNT(*) FROM citation_extraction_phased_summary"
    )).scalar()
    success = conn.execute(text(
        "SELECT COUNT(*) FROM citation_extraction_phased_summary "
        "WHERE extraction_success = true"
    )).scalar()
    failed = conn.execute(text(
        "SELECT COUNT(*) FROM citation_extraction_phased_summary "
        "WHERE extraction_success = false"
    )).scalar()

    # Citations and verification
    stats = conn.execute(text(
        "SELECT COALESCE(SUM(total_references_extracted),0), "
        "COALESCE(SUM(verified_confirmed),0), COALESCE(SUM(verified_not_found),0), "
        "COALESCE(SUM(verified_misattributed),0), COALESCE(SUM(verified_skipped),0), "
        "COALESCE(SUM(total_cost_usd),0), COALESCE(SUM(verification_cost_usd),0) "
        "FROM citation_extraction_phased_summary"
    )).fetchone()

    pct = total / target * 100 if target > 0 else 0
    print(f"{'='*60}")
    print(f"VM EXTRACTION STATUS — {total}/{target} ({pct:.0f}%)")
    print(f"{'='*60}")
    print(f"  Success: {success} | Failed: {failed}")
    print(f"  Citations: {stats[0]}")
    print(f"  Verified: C={stats[1]} NF={stats[2]} M={stats[3]} S={stats[4]}")
    print(f"  Cost: ${float(stats[5]):.4f} + verify ${float(stats[6]):.4f}")

    # Per-citation verification status
    v_rows = conn.execute(text(
        "SELECT verification_status, COUNT(*) FROM citation_extraction_phased "
        "GROUP BY verification_status ORDER BY verification_status"
    )).fetchall()
    print(f"\n  Citation verification breakdown:")
    for row in v_rows:
        print(f"    {row[0] or 'NULL'}: {row[1]}")

    # Missing verification
    null_verif = conn.execute(text(
        "SELECT COUNT(*) FROM citation_extraction_phased "
        "WHERE verification_status IS NULL"
    )).scalar()
    if null_verif > 0:
        print(f"  *** WARNING: {null_verif} citations with NULL verification ***")

    # Failed documents (latest 10)
    errs = conn.execute(text(
        "SELECT document_id, extraction_error, total_processing_time_seconds "
        "FROM citation_extraction_phased_summary "
        "WHERE extraction_success = false "
        "ORDER BY extraction_started_at DESC LIMIT 10"
    )).fetchall()
    if errs:
        total_failed = conn.execute(text(
            "SELECT COUNT(*) FROM citation_extraction_phased_summary "
            "WHERE extraction_success = false"
        )).scalar()
        print(f"\n  Failed documents ({total_failed} total, latest 10):")
        for e in errs:
            print(f"    {str(e[0])[:36]}: {str(e[1])[:80]} ({e[2]:.1f}s)")

    # Process check
    import subprocess
    try:
        result = subprocess.run(
            ["ps", "aux"], capture_output=True, text=True, timeout=5
        )
        running = "extract_citations" in result.stdout
        print(f"\n  Process: {'RUNNING' if running else 'STOPPED'}")
    except Exception:
        print(f"\n  Process: UNKNOWN")

    status = "COMPLETE" if total >= target else "RUNNING"
    print(f"\n  STATUS: {status}")
    print(f"{'='*60}")

engine.dispose()
