#!/usr/bin/env python3
"""
One-off test: run extract_citations pipeline for a single document by ID.
Usage: python test_single_doc.py 66dca36b-282e-5822-af8d-14cf3b1edb75
"""
import sys
import os
import uuid

_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _SCRIPTS_DIR)
sys.path.insert(0, os.path.join(_SCRIPTS_DIR, "0-initialize-database"))

from extract_citations import (
    extract_all_case_references_phase2,
    extract_country_from_geographies,
    get_source_region,
    classify_citations_functionally,
    identify_case_origin,
    estimate_token_count,
)
from gcp_secrets import get_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from init_database import Base, Case, Document, ExtractedText
import logging
import time
import json

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_single_doc.py <document_id>")
        sys.exit(1)

    doc_id = uuid.UUID(sys.argv[1])
    print(f"\n{'='*70}")
    print(f"TEST: Processing single document {doc_id}")
    print(f"{'='*70}\n")

    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        row = (
            session.query(
                Document.document_id,
                ExtractedText.raw_text,
                Case.geographies,
            )
            .join(ExtractedText, Document.document_id == ExtractedText.document_id)
            .join(Case, Document.case_id == Case.case_id)
            .filter(Document.document_id == doc_id)
            .first()
        )

        if not row:
            print(f"ERROR: Document {doc_id} not found or has no extracted text")
            sys.exit(1)

        document_id, raw_text, geographies = row
        print(f"Document found: {len(raw_text):,} chars (~{estimate_token_count(raw_text):,} tokens)")
        print(f"Geographies: {geographies}")

        # Phase 1: Source jurisdiction
        source_jurisdiction = extract_country_from_geographies(geographies)
        source_region = get_source_region(source_jurisdiction)
        print(f"Source: {source_jurisdiction} ({source_region})")

        # Phase 2A: Extraction
        print(f"\n{'='*70}")
        print("PHASE 2A: EXTRACTION")
        print(f"{'='*70}")
        start = time.time()
        result = extract_all_case_references_phase2(document_id, raw_text, source_jurisdiction, source_region)
        elapsed = time.time() - start

        if not result:
            print("FAILED: No result returned")
            sys.exit(1)

        refs = result.get("case_law_references", [])
        print(f"\nResult: {len(refs)} references in {elapsed:.1f}s")
        print(f"Tokens: {result.get('tokens_input', 0):,} in / {result.get('tokens_output', 0):,} out")
        print(f"Chunks: {result.get('chunk_count', 1)}")
        print(f"Notes: {result.get('extraction_notes', 'N/A')}")

        # Show first 5 citations
        print(f"\nFirst 5 citations:")
        for i, ref in enumerate(refs[:5]):
            print(f"  {i+1}. {ref.get('case_name', '?')} (conf: {ref.get('confidence', '?')})")
            print(f"     raw: {ref.get('raw_text', '')[:120]}...")

        # Phase 2B: Functional classification
        if refs:
            print(f"\n{'='*70}")
            print("PHASE 2B: FUNCTIONAL CLASSIFICATION")
            print(f"{'='*70}")
            classifications = classify_citations_functionally(refs, raw_text, source_jurisdiction)
            classified = len(classifications)
            print(f"Classified: {classified}/{len(refs)} ({100*classified/len(refs):.0f}%)")

        # Phase 3: Origin identification
        if refs:
            print(f"\n{'='*70}")
            print("PHASE 3: ORIGIN IDENTIFICATION")
            print(f"{'='*70}")
            origins = {}
            for i, ref in enumerate(refs):
                origin = identify_case_origin(
                    ref.get("case_name", ""),
                    ref.get("raw_text", ""),
                    source_jurisdiction,
                    source_region,
                )
                origins[i] = origin
                method = origin.get("method", "?")
                origin_country = origin.get("origin", "?")
                conf = origin.get("confidence", 0)
                if origin_country != source_jurisdiction:
                    print(f"  FOREIGN: {ref.get('case_name', '?')} -> {origin_country} ({method}, conf={conf})")

            domestic = sum(1 for o in origins.values() if o.get("origin") == source_jurisdiction)
            foreign = len(origins) - domestic
            print(f"\nDomestic: {domestic}, Foreign/International: {foreign}")

        print(f"\n{'='*70}")
        print("TEST COMPLETE")
        print(f"{'='*70}")

    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    main()
