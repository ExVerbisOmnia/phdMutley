#!/usr/bin/env python3
"""
Pipeline Monitor — Cost, Error, and Processing Time Reporting
==============================================================
Queries the citation_extraction_phased_summary table to report on pipeline
health, cost tracking, and error patterns. Also estimates costs for planned
full-pipeline runs.

Task #25: Monitor cost, errors, processing time.
Task #19: Cost estimation (pre-run gate).

Usage:
    python scripts/pipeline_monitor.py              # full report
    python scripts/pipeline_monitor.py --estimate N  # estimate cost for N docs
    python scripts/pipeline_monitor.py --errors      # show error details
"""

import argparse
import json
import logging
import os
import sys
from decimal import Decimal

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPTS_DIR)

from gcp_secrets import get_engine

logger = logging.getLogger(__name__)

# Model-aware pricing (per 1M tokens)
MODEL_PRICING = {
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00, "thinking": 1.25},
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60, "thinking": 0.15},
    "gemini-2.5-flash-lite": {"input": 0.075, "output": 0.30, "thinking": 0.0},
    "gemini-3.1-pro-preview": {"input": 1.25, "output": 10.00, "thinking": 1.25},
    "gemini-3.1-flash-lite-preview": {"input": 0.01, "output": 0.04, "thinking": 0.0},
}
# Default pricing (Flash for extraction — the bulk operation)
PRICE_INPUT_PER_M = MODEL_PRICING["gemini-2.5-flash"]["input"]
PRICE_OUTPUT_PER_M = MODEL_PRICING["gemini-2.5-flash"]["output"]


def get_summary_stats(engine) -> dict:
    """
    Query aggregate statistics from citation_extraction_phased_summary.

    INPUT: SQLAlchemy engine
    OUTPUT: Dict with processing stats
    """
    from sqlalchemy import text

    with engine.connect() as conn:
        # Overall stats
        row = conn.execute(text("""
            SELECT
                COUNT(*) as total_docs,
                COUNT(*) FILTER (WHERE extraction_success = true) as success,
                COUNT(*) FILTER (WHERE extraction_success = false) as failed,
                SUM(total_references_extracted) as total_refs,
                SUM(total_tokens_input) as total_tokens_in,
                SUM(total_tokens_output) as total_tokens_out,
                SUM(total_cost_usd) as total_cost,
                AVG(total_processing_time_seconds) as avg_time,
                MAX(total_processing_time_seconds) as max_time,
                MIN(total_processing_time_seconds) FILTER (WHERE extraction_success = true) as min_time,
                SUM(items_requiring_review) as review_items,
                AVG(average_confidence) FILTER (WHERE extraction_success = true) as avg_confidence,
                AVG(total_references_extracted) FILTER (WHERE extraction_success = true) as avg_refs
            FROM citation_extraction_phased_summary
        """)).fetchone()

        stats = {
            "total_documents": row[0] or 0,
            "successful": row[1] or 0,
            "failed": row[2] or 0,
            "total_references": int(row[3] or 0),
            "total_tokens_input": int(row[4] or 0),
            "total_tokens_output": int(row[5] or 0),
            "total_cost_usd": float(row[6] or 0),
            "avg_processing_time_s": float(row[7] or 0),
            "max_processing_time_s": float(row[8] or 0),
            "min_processing_time_s": float(row[9] or 0),
            "items_requiring_review": int(row[10] or 0),
            "avg_confidence": float(row[11] or 0),
            "avg_refs_per_doc": float(row[12] or 0),
        }

        # Citation type breakdown
        type_row = conn.execute(text("""
            SELECT
                SUM(foreign_citations_count) as foreign_ct,
                SUM(international_citations_count) as intl_ct,
                SUM(foreign_international_citations_count) as foreign_intl_ct
            FROM citation_extraction_phased_summary
            WHERE extraction_success = true
        """)).fetchone()

        stats["foreign_citations"] = int(type_row[0] or 0)
        stats["international_citations"] = int(type_row[1] or 0)
        stats["foreign_international_citations"] = int(type_row[2] or 0)

        # Count unprocessed decisions
        unprocessed = conn.execute(text("""
            SELECT COUNT(DISTINCT d.document_id)
            FROM documents d
            JOIN extracted_text et ON d.document_id = et.document_id
            WHERE d.is_decision = true
              AND et.raw_text IS NOT NULL
              AND d.document_id NOT IN (
                  SELECT document_id FROM citation_extraction_phased_summary
              )
        """)).scalar()
        stats["unprocessed_decisions"] = unprocessed or 0

        # Total decisions
        total_decisions = conn.execute(text("""
            SELECT COUNT(DISTINCT d.document_id)
            FROM documents d
            JOIN extracted_text et ON d.document_id = et.document_id
            WHERE d.is_decision = true AND et.raw_text IS NOT NULL
        """)).scalar()
        stats["total_decisions"] = total_decisions or 0

    return stats


def get_error_details(engine) -> list[dict]:
    """
    Get details of failed extractions.

    INPUT: SQLAlchemy engine
    OUTPUT: List of error dicts
    """
    from sqlalchemy import text

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT
                s.document_id,
                s.extraction_error,
                s.extraction_started_at,
                s.total_processing_time_seconds
            FROM citation_extraction_phased_summary s
            WHERE s.extraction_success = false
            ORDER BY s.extraction_started_at DESC
            LIMIT 20
        """)).fetchall()

    return [
        {
            "document_id": str(r[0]),
            "error": r[1],
            "started_at": str(r[2]),
            "processing_time": float(r[3] or 0),
        }
        for r in rows
    ]


def estimate_full_run_cost(stats: dict, target_docs: int | None = None) -> dict:
    """
    Estimate cost and time for a full pipeline run.

    INPUT:
        - stats: Current pipeline stats
        - target_docs: Number of documents to estimate for (default: unprocessed)
    OUTPUT: Cost/time estimates
    """
    if stats["successful"] == 0:
        return {"error": "No successful runs to base estimates on"}

    docs = target_docs or stats["unprocessed_decisions"]
    avg_tokens_in = stats["total_tokens_input"] / stats["successful"]
    avg_tokens_out = stats["total_tokens_output"] / stats["successful"]
    avg_time = stats["avg_processing_time_s"]

    # v7: No KB in prompt (removed), but includes extraction + verification calls
    cost_per_doc = (avg_tokens_in / 1e6 * PRICE_INPUT_PER_M) + (
        avg_tokens_out / 1e6 * PRICE_OUTPUT_PER_M
    )
    # Add ~30% overhead for classification + verification + origin ID calls
    cost_per_doc_total = cost_per_doc * 1.3

    return {
        "target_documents": docs,
        "cost_per_doc": round(cost_per_doc, 4),
        "cost_per_doc_total": round(cost_per_doc_total, 4),
        "total_cost": round(cost_per_doc_total * docs, 2),
        "avg_time_per_doc_s": round(avg_time, 1),
        "estimated_total_time_min": round(docs * avg_time / 60, 1),
        "estimated_total_time_hr": round(docs * avg_time / 3600, 1),
        "budget_remaining": round(200 - stats["total_cost_usd"], 2),
        "within_budget": (cost_per_doc_total * docs) < (200 - stats["total_cost_usd"]),
    }


def print_report(stats: dict, estimates: dict):
    """Print formatted pipeline monitoring report."""
    print("\n" + "=" * 70)
    print("PIPELINE MONITOR — EXTRACTION HEALTH REPORT")
    print("=" * 70)

    print(f"\n  Documents processed:  {stats['successful']} / {stats['total_decisions']}")
    print(f"  Failed:               {stats['failed']}")
    print(f"  Remaining:            {stats['unprocessed_decisions']}")
    print(f"  Success rate:         {stats['successful'] / max(stats['total_documents'], 1) * 100:.1f}%")

    print(f"\n  Total citations:      {stats['total_references']}")
    print(f"  Avg per document:     {stats['avg_refs_per_doc']:.1f}")
    print(f"  Foreign:              {stats['foreign_citations']}")
    print(f"  International:        {stats['international_citations']}")
    print(f"  Foreign Int'l:        {stats['foreign_international_citations']}")
    print(f"  Needing review:       {stats['items_requiring_review']}")
    print(f"  Avg confidence:       {stats['avg_confidence']:.2f}")

    print(f"\n  Total tokens (in):    {stats['total_tokens_input']:,}")
    print(f"  Total tokens (out):   {stats['total_tokens_output']:,}")
    print(f"  Total cost (USD):     ${stats['total_cost_usd']:.4f}")

    print(f"\n  Avg time/doc:         {stats['avg_processing_time_s']:.1f}s")
    print(f"  Min time:             {stats['min_processing_time_s']:.1f}s")
    print(f"  Max time:             {stats['max_processing_time_s']:.1f}s")

    print("\n" + "-" * 70)
    print("COST ESTIMATES (v7 — Flash extraction + Pro classification)")
    print("-" * 70)

    if "error" in estimates:
        print(f"  {estimates['error']}")
    else:
        print(f"  Target documents:     {estimates['target_documents']}")
        print(f"  Cost/doc (extract):   ${estimates['cost_per_doc']:.4f}")
        print(f"  Cost/doc (total):     ${estimates['cost_per_doc_total']:.4f}")
        print(f"  Total cost:           ${estimates['total_cost']:.2f}")
        print(f"  Estimated time:       {estimates['estimated_total_time_hr']:.1f} hours")
        print(f"  Budget remaining:     ${estimates['budget_remaining']:.2f}")
        print(f"  Within budget:        {'YES' if estimates['within_budget'] else 'NO - OVER BUDGET'}")

    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Pipeline monitoring and cost estimation")
    parser.add_argument("--estimate", type=int, default=None, help="Estimate cost for N documents")
    parser.add_argument("--errors", action="store_true", help="Show error details")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    engine = get_engine()
    stats = get_summary_stats(engine)
    estimates = estimate_full_run_cost(stats, target_docs=args.estimate)

    if args.errors:
        errors = get_error_details(engine)
        if args.json:
            print(json.dumps(errors, indent=2))
        else:
            print(f"\n{'=' * 70}")
            print(f"FAILED EXTRACTIONS ({len(errors)} most recent)")
            print(f"{'=' * 70}")
            for e in errors:
                print(f"\n  Doc: {e['document_id'][:36]}")
                print(f"  Error: {e['error'][:100]}")
                print(f"  Time: {e['processing_time']:.1f}s")
        return

    if args.json:
        print(json.dumps({"stats": stats, "estimates": estimates}, indent=2, default=str))
    else:
        print_report(stats, estimates)

    engine.dispose()


if __name__ == "__main__":
    main()
