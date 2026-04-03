#!/usr/bin/env python3
"""Investigate citations with NULL verification status."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gcp_secrets import get_engine
from sqlalchemy import text

engine = get_engine()
with engine.connect() as conn:
    rows = conn.execute(text(
        "SELECT c.extraction_id, c.document_id, c.case_name, "
        "c.verification_status, s.verified_skipped, "
        "LENGTH(et.raw_text) as text_len "
        "FROM citation_extraction_phased c "
        "JOIN citation_extraction_phased_summary s ON c.document_id = s.document_id "
        "JOIN extracted_text et ON c.document_id = et.document_id "
        "WHERE c.created_at > NOW() - INTERVAL '4 hours' "
        "AND c.verification_status IS NULL"
    )).fetchall()
    print(f"Citations with NULL verification: {len(rows)}")
    for r in rows:
        print(f"  doc={str(r[1])[:36]}, case={r[2][:50] if r[2] else 'N/A'}, "
              f"skipped={r[4]}, text_len={r[5]:,}")
engine.dispose()
