#!/usr/bin/env python3
"""Check extraction progress on VM via DB query. Run on the VM."""
import sys
sys.path.insert(0, '/opt/phdMutley/scripts')
from gcp_secrets import get_engine
from sqlalchemy import text

engine = get_engine()
with engine.connect() as conn:
    total = conn.execute(text(
        "SELECT COUNT(*) FROM citation_extraction_phased_summary "
        "WHERE extraction_started_at > NOW() - INTERVAL '2 hours'"
    )).scalar()
    success = conn.execute(text(
        "SELECT COUNT(*) FROM citation_extraction_phased_summary "
        "WHERE extraction_success = true AND extraction_started_at > NOW() - INTERVAL '2 hours'"
    )).scalar()
    failed = conn.execute(text(
        "SELECT COUNT(*) FROM citation_extraction_phased_summary "
        "WHERE extraction_success = false AND extraction_started_at > NOW() - INTERVAL '2 hours'"
    )).scalar()
    refs = conn.execute(text(
        "SELECT COALESCE(SUM(total_references_extracted),0) FROM citation_extraction_phased_summary "
        "WHERE extraction_started_at > NOW() - INTERVAL '2 hours'"
    )).scalar()
    verified = conn.execute(text(
        "SELECT COALESCE(SUM(verified_confirmed),0), COALESCE(SUM(verified_not_found),0), "
        "COALESCE(SUM(verified_misattributed),0) FROM citation_extraction_phased_summary "
        "WHERE extraction_started_at > NOW() - INTERVAL '2 hours'"
    )).fetchone()
    cost = conn.execute(text(
        "SELECT COALESCE(SUM(total_cost_usd),0), COALESCE(SUM(verification_cost_usd),0) "
        "FROM citation_extraction_phased_summary WHERE extraction_started_at > NOW() - INTERVAL '2 hours'"
    )).fetchone()
    errors = conn.execute(text(
        "SELECT extraction_error FROM citation_extraction_phased_summary "
        "WHERE extraction_success = false AND extraction_started_at > NOW() - INTERVAL '2 hours' LIMIT 5"
    )).fetchall()

    target = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    pct = total / target * 100 if target > 0 else 0
    print(f"=== VM Extraction Progress ===")
    print(f"Processed: {total}/{target} ({pct:.0f}%)")
    print(f"Success: {success} | Failed: {failed}")
    print(f"Citations: {refs}")
    print(f"Verified: C={verified[0]} NF={verified[1]} M={verified[2]}")
    print(f"Cost: ${float(cost[0]):.4f} + verify ${float(cost[1]):.4f}")
    if errors:
        print(f"Errors ({len(errors)}):")
        for e in errors:
            print(f"  {str(e[0])[:100]}")
    print(f"STATUS: {'COMPLETE' if total >= target else 'RUNNING'}")
engine.dispose()
