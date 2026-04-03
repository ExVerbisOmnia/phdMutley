#!/usr/bin/env python3
"""Investigate two specific documents with bad verification."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gcp_secrets import get_database_url_auto
from sqlalchemy import create_engine, text

engine = create_engine(get_database_url_auto())

with engine.connect() as conn:
    for doc_id in ['8f4cf38c-8406-5e23-9abc-767458553e18', 'ac00bbcd-3d58-42f7-84a4-810a9371d6f2']:
        print(f'===== DOCUMENT: {doc_id} =====')
        # Case info
        r = conn.execute(text("""
            SELECT c.case_name, c.case_url, d.document_url, d.document_type
            FROM documents d JOIN cases c ON d.case_id = c.case_id
            WHERE d.document_id = :did
        """), {'did': doc_id})
        row = r.fetchone()
        if row:
            print(f'  Case: {row[0]}')
            print(f'  Case URL: {row[1]}')
            print(f'  Doc URL: {row[2]}')
            print(f'  Doc type: {row[3]}')

        # Extracted text - full content
        r = conn.execute(text("""
            SELECT raw_text, extraction_method, extraction_quality, LENGTH(raw_text)
            FROM extracted_text WHERE document_id = :did
        """), {'did': doc_id})
        row = r.fetchone()
        doc_text = ""
        if row:
            doc_text = row[0] or ""
            print(f'  Text length: {row[3]:,} chars')
            print(f'  Extraction: {row[1]} / {row[2]}')
            print(f'  --- FULL TEXT (first 2000 chars) ---')
            print(doc_text[:2000])
            print(f'  --- END TEXT ---')
        print()

        # All citations for this document
        r = conn.execute(text("""
            SELECT extraction_id, case_name, verification_status,
                   verification_snippet,
                   verification_notes,
                   snippet_text,
                   raw_citation_text
            FROM citation_extraction_phased
            WHERE document_id = :did
            ORDER BY extraction_id
        """), {'did': doc_id})
        rows = r.fetchall()
        print(f'  Citations: {len(rows)}')
        for i, row in enumerate(rows):
            print(f'  [{i+1}] id={row[0]}')
            print(f'      case_name: {row[1]}')
            print(f'      status: {row[2]}')
            print(f'      raw_citation: {str(row[6])[:300]}')
            print(f'      v_snippet: {str(row[3])[:300]}')
            print(f'      v_notes: {str(row[4])[:300]}')

            # Check if case_name appears anywhere in doc text
            cn = row[1] or ""
            if cn and doc_text:
                if cn in doc_text:
                    print(f'      >> case_name FOUND in doc text')
                elif cn.lower() in doc_text.lower():
                    print(f'      >> case_name found (case-insensitive)')
                else:
                    # Try partial match - first significant word
                    words = [w for w in cn.split() if len(w) > 3]
                    found_words = [w for w in words if w.lower() in doc_text.lower()]
                    print(f'      >> case_name NOT FOUND in doc. Partial words found: {found_words}')

            # Check if raw_citation_text appears in doc
            rct = row[6] or ""
            if rct and doc_text:
                if rct[:50] in doc_text:
                    print(f'      >> raw_citation first 50 chars FOUND in doc')
                else:
                    print(f'      >> raw_citation NOT FOUND in doc')
            print()

        print('=' * 80)
        print()

engine.dispose()
