"""
Orchestrator helper — Python side of the corpus-run orchestrator.

Handles DB operations (cleanup, ingest, status updates). The LLM operations
(extract, verify) are handled by the citation-extractor and citation-verifier
subagents — invoked by the orchestrator session, not by this script.

Per `docs/plans/corpus-orchestrator-plan.md`:
  - Layer A (orchestrator session) drives the loop
  - Layer B (per-doc work) splits into:
      * LLM steps (extract, verify) → registered subagents
      * DB steps (cleanup, ingest, mark_complete) → THIS SCRIPT

Per Gus's hard requirement (2026-05-03): a doc interrupted mid-extraction
must be re-run from scratch on resume. This script's `prepare` command
implements that by deleting any partial citation_agent_v1* rows for the
target doc before marking it in_progress.

USAGE
-----
    python scripts/orchestrator_helper.py startup
        Reset all in_progress rows to pending and clean up partial DB writes.
        Run once at the start of each orchestrator session.

    python scripts/orchestrator_helper.py next [--tier 1|2|3] [--limit N]
        Print up to N pending docs as JSON (default N=10), optionally
        filtered by tier. The orchestrator picks from this list.

    python scripts/orchestrator_helper.py prepare <document_id>
        Clean up partial state for the doc + mark in_progress.
        Returns the doc's tier on stdout (for tier-aware dispatch).

    python scripts/orchestrator_helper.py ingest <document_id> <verified_json_path>
        Read the verifier's JSON, INSERT into citation_agent_v1*, mark complete.
        Idempotent: cleans up first.

    python scripts/orchestrator_helper.py mark_failed <document_id> <error_message>
        Mark the doc as failed with the error message. Bumps attempts.
        If attempts >= 2, stays failed (won't auto-retry).

    python scripts/orchestrator_helper.py mark_skipped <document_id> <reason>
        Mark the doc as skipped (manual exclusion, won't be picked up).

    python scripts/orchestrator_helper.py status [--full]
        Print a snapshot of run_state counts.

INPUT
-----
    PostgreSQL connection via scripts/config.py DB_CONFIG.
    Verifier JSON files at data/extraction_results/{doc_id}_verified.json.

OUTPUT
------
    JSON on stdout for `next` and `prepare` (parseable by the orchestrator).
    Plain log lines for everything else. Exit code 0 on success, 1 on error.
"""
import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, text

# Add scripts dir to path for config import
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DB_CONFIG  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXTRACTION_DIR = PROJECT_ROOT / "data" / "extraction_results"
RETRY_CAP = 2  # attempts before terminal-failed (per plan Section 12 question 2)


def get_engine():
    connstr = (
        f"postgresql://{DB_CONFIG['username']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    )
    return create_engine(connstr)


# =============================================================================
# COMMAND: startup
# =============================================================================


def cmd_startup() -> int:
    """
    Reset any in_progress rows from a previous interrupted session.

    INPUT: nothing
    ALGORITHM:
        1. Find docs with status='in_progress' (these were interrupted)
        2. DELETE their rows from citation_agent_v1 + citation_agent_v1_summary
        3. Reset their status to 'pending', append a note to error_message
    OUTPUT: count of rows reset (logged)
    """
    engine = get_engine()
    with engine.begin() as conn:
        # Capture the doc_ids first
        doc_ids = [
            row[0]
            for row in conn.execute(
                text("SELECT document_id FROM citation_agent_v1_run_state WHERE status='in_progress'")
            ).all()
        ]
        if not doc_ids:
            log.info("No in_progress rows to reset. Clean startup.")
            return 0

        log.info(f"Found {len(doc_ids)} in_progress rows from previous session — resetting")

        # Wipe partial DB writes for those docs
        conn.execute(
            text("DELETE FROM citation_agent_v1_summary WHERE document_id = ANY(:ids)"),
            {"ids": doc_ids},
        )
        conn.execute(
            text("DELETE FROM citation_agent_v1 WHERE document_id = ANY(:ids)"),
            {"ids": doc_ids},
        )

        # Reset status
        conn.execute(
            text(
                """
                UPDATE citation_agent_v1_run_state
                SET status = 'pending',
                    error_message = COALESCE(error_message || '; ', '')
                                    || 'reset from in_progress on startup at '
                                    || NOW()::TEXT
                WHERE document_id = ANY(:ids)
                """
            ),
            {"ids": doc_ids},
        )

    log.info(f"✓ Reset {len(doc_ids)} docs to pending; partial citation rows cleared")
    return 0


# =============================================================================
# COMMAND: next
# =============================================================================


def cmd_next(tier: int | None, limit: int) -> int:
    """List the next N pending docs (optionally filtered by tier) as JSON."""
    engine = get_engine()
    where = ["status = 'pending'", f"attempts < {RETRY_CAP + 1}"]
    if tier is not None:
        where.append(f"tier = {tier}")
    sql = (
        "SELECT document_id::TEXT, tier, word_count, attempts "
        "FROM citation_agent_v1_run_state "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY tier ASC, word_count ASC NULLS LAST "
        f"LIMIT {limit}"
    )
    with engine.connect() as conn:
        rows = [dict(r) for r in conn.execute(text(sql)).mappings().all()]
    print(json.dumps(rows, indent=2))
    return 0


# =============================================================================
# COMMAND: prepare
# =============================================================================


def cmd_prepare(document_id: str) -> int:
    """
    Cleanup partial state for the doc + mark in_progress.

    INPUT: document_id (string UUID)
    ALGORITHM:
        1. DELETE any prior citation_agent_v1* rows for this doc
        2. UPDATE run_state: status=in_progress, attempts+=1, last_attempt_started=NOW()
        3. Return the doc's tier on stdout (for tier-aware dispatch)
    OUTPUT: JSON on stdout: {"document_id": "...", "tier": 1, "word_count": 12345, "attempts": 1}
    """
    engine = get_engine()
    with engine.begin() as conn:
        # Verify the doc is actually in run_state and pickable
        row = conn.execute(
            text(
                """
                SELECT status, tier, word_count, attempts
                FROM citation_agent_v1_run_state
                WHERE document_id = :doc_id
                """
            ),
            {"doc_id": document_id},
        ).mappings().first()
        if row is None:
            log.error(f"document_id {document_id} not found in run_state")
            return 1
        if row["status"] not in ("pending", "in_progress", "failed"):
            log.error(
                f"document_id {document_id} has status='{row['status']}' — refusing to prepare"
            )
            return 1
        if row["attempts"] >= RETRY_CAP + 1:
            log.error(
                f"document_id {document_id} has exceeded retry cap "
                f"({row['attempts']}/{RETRY_CAP + 1}) — manual intervention needed"
            )
            return 1

        # Cleanup partial rows (idempotency)
        conn.execute(
            text("DELETE FROM citation_agent_v1_summary WHERE document_id = :doc_id"),
            {"doc_id": document_id},
        )
        conn.execute(
            text("DELETE FROM citation_agent_v1 WHERE document_id = :doc_id"),
            {"doc_id": document_id},
        )

        # Mark in_progress
        conn.execute(
            text(
                """
                UPDATE citation_agent_v1_run_state
                SET status = 'in_progress',
                    attempts = attempts + 1,
                    last_attempt_started = NOW(),
                    error_message = NULL
                WHERE document_id = :doc_id
                """
            ),
            {"doc_id": document_id},
        )

    print(json.dumps({
        "document_id": document_id,
        "tier": row["tier"],
        "word_count": row["word_count"],
        "attempts": row["attempts"] + 1,
    }))
    log.info(
        f"✓ prepare {document_id[:8]}… tier={row['tier']} "
        f"words={row['word_count']} attempt={row['attempts'] + 1}"
    )
    return 0


# =============================================================================
# COMMAND: ingest
# =============================================================================


def cmd_ingest(document_id: str, verified_json_path: str) -> int:
    """
    INSERT the verifier's output into citation_agent_v1 + summary, mark complete.

    INPUT:
        - document_id: UUID string
        - verified_json_path: path to data/extraction_results/{id}_verified.json
    ALGORITHM:
        1. Read verifier JSON; validate top-level shape
        2. Cleanup partial rows (defense-in-depth — prepare should have done it,
           but ingest re-cleans for resume safety)
        3. INSERT N rows into citation_agent_v1 (one per citations[] entry)
        4. INSERT 1 row into citation_agent_v1_summary
        5. UPDATE run_state: status=complete, counts populated
        6. All in a single transaction
    OUTPUT: log lines + exit code
    """
    path = Path(verified_json_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.exists():
        log.error(f"Verified JSON not found: {path}")
        cmd_mark_failed(document_id, f"verified JSON not found at {path}")
        return 1

    try:
        with path.open("r", encoding="utf-8") as f:
            verified = json.load(f)
    except json.JSONDecodeError as e:
        log.error(f"Verified JSON malformed at {path}: {e}")
        cmd_mark_failed(
            document_id,
            f"verifier produced malformed JSON: {e.msg} at line {e.lineno} col {e.colno}",
        )
        return 1

    if verified.get("document_id") != document_id:
        log.error(
            f"document_id mismatch: arg={document_id} vs json={verified.get('document_id')}"
        )
        cmd_mark_failed(
            document_id,
            f"document_id mismatch in verifier JSON (got {verified.get('document_id')})",
        )
        return 1

    citations = verified.get("citations", [])
    summary = verified.get("summary", {})
    by_sf = summary.get("by_sixfold_type", {})
    by_fu = summary.get("by_functional_use", {})
    by_or = summary.get("by_origin_region", {})

    # Vertical-dialogue summary may come in two shapes:
    #   1. {"by_vertical_dialogue": {"true": N, "false": M}}  (per agent rules schema)
    #   2. {"vertical_dialogue_count": N}                     (older/abbreviated shape)
    # Fall through both, else compute from per-citation booleans.
    raw_vd = summary.get("by_vertical_dialogue")
    if isinstance(raw_vd, dict):
        by_vd = raw_vd
    else:
        vd_true = summary.get("vertical_dialogue_count")
        if vd_true is None:
            vd_true = sum(1 for c in citations if c.get("is_vertical_dialogue") is True)
        confirmed_total = verified.get("total_confirmed", len(citations))
        by_vd = {"true": vd_true, "false": max(0, confirmed_total - vd_true)}

    engine = get_engine()
    with engine.begin() as conn:
        # Cleanup (defense-in-depth)
        conn.execute(
            text("DELETE FROM citation_agent_v1_summary WHERE document_id = :doc_id"),
            {"doc_id": document_id},
        )
        conn.execute(
            text("DELETE FROM citation_agent_v1 WHERE document_id = :doc_id"),
            {"doc_id": document_id},
        )

        # INSERT each citation
        run_id = verified.get("verification_timestamp") or datetime.utcnow().isoformat()[:50]
        for c in citations:
            conn.execute(
                text(
                    """
                    INSERT INTO citation_agent_v1 (
                        document_id, case_id, citation_index,
                        source_jurisdiction, source_region, source_year,
                        verification_verdict, case_name, raw_text, verbatim_snippet,
                        cited_court, case_number, cited_year, confidence,
                        functional_use, functional_use_confidence,
                        opinion_type, origin_country, origin_region, origin_court,
                        sixfold_type, is_vertical_dialogue, citation_pattern,
                        requires_manual_review, manual_review_reason,
                        is_duplicate_of, verification_notes,
                        verification_timestamp, extraction_run_id
                    ) VALUES (
                        :document_id, :case_id, :citation_index,
                        :source_jurisdiction, :source_region, :source_year,
                        :verification_verdict, :case_name, :raw_text, :verbatim_snippet,
                        :cited_court, :case_number, :cited_year, :confidence,
                        :functional_use, :functional_use_confidence,
                        :opinion_type, :origin_country, :origin_region, :origin_court,
                        :sixfold_type, :is_vertical_dialogue, :citation_pattern,
                        :requires_manual_review, :manual_review_reason,
                        :is_duplicate_of, :verification_notes,
                        :verification_timestamp, :extraction_run_id
                    )
                    """
                ),
                {
                    "document_id": document_id,
                    "case_id": verified.get("case_id"),
                    "citation_index": c.get("citation_index"),
                    "source_jurisdiction": verified.get("source_jurisdiction"),
                    "source_region": verified.get("source_region"),
                    "source_year": verified.get("source_year"),
                    "verification_verdict": c.get("verification_verdict"),
                    "case_name": c.get("case_name"),
                    "raw_text": c.get("raw_text"),
                    "verbatim_snippet": c.get("verbatim_snippet"),
                    "cited_court": c.get("cited_court"),
                    "case_number": c.get("case_number"),
                    "cited_year": c.get("cited_year"),
                    "confidence": c.get("confidence"),
                    "functional_use": c.get("functional_use"),
                    "functional_use_confidence": c.get("functional_use_confidence"),
                    "opinion_type": c.get("opinion_type"),
                    "origin_country": c.get("origin_country"),
                    "origin_region": c.get("origin_region"),
                    "origin_court": c.get("origin_court"),
                    "sixfold_type": c.get("sixfold_type"),
                    "is_vertical_dialogue": c.get("is_vertical_dialogue", False),
                    "citation_pattern": c.get("citation_pattern"),
                    "requires_manual_review": c.get("requires_manual_review", False),
                    "manual_review_reason": c.get("manual_review_reason"),
                    "is_duplicate_of": c.get("is_duplicate_of"),
                    "verification_notes": c.get("verification_notes"),
                    "verification_timestamp": verified.get("verification_timestamp"),
                    "extraction_run_id": run_id,
                },
            )

        # INSERT summary — column names match the migration's schema
        conn.execute(
            text(
                """
                INSERT INTO citation_agent_v1_summary (
                    document_id, case_id, source_jurisdiction, source_region, source_year,
                    verification_timestamp,
                    total_citations_extracted, total_confirmed, total_not_found,
                    total_misattributed, total_not_a_case, total_duplicates,
                    unique_citations_confirmed,
                    sixfold_foreign_citation_count,
                    sixfold_international_citation_count,
                    sixfold_foreign_international_citation_count,
                    sixfold_inter_system_citation_count,
                    sixfold_member_state_citation_count,
                    sixfold_non_member_citation_count,
                    sixfold_domestic_count,
                    sixfold_unclassified_count,
                    functional_aligned_count,
                    functional_contested_count,
                    functional_avoided_count,
                    functional_invoked_count,
                    functional_dismissed_count,
                    vertical_dialogue_true_count,
                    vertical_dialogue_false_count,
                    origin_global_north_count,
                    origin_global_south_count,
                    origin_international_count,
                    origin_domestic_count,
                    origin_unknown_count,
                    flagged_for_review_count,
                    extraction_run_id
                ) VALUES (
                    :document_id, :case_id, :source_jurisdiction, :source_region, :source_year,
                    :verification_timestamp,
                    :total_extracted, :total_confirmed, :total_not_found,
                    :total_misattributed, :total_not_a_case, :total_duplicates,
                    :unique_confirmed,
                    :sf_foreign, :sf_international, :sf_foreign_international,
                    :sf_inter_system, :sf_member_state, :sf_non_member,
                    :sf_domestic, :sf_unclassified,
                    :fu_aligned, :fu_contested, :fu_avoided, :fu_invoked, :fu_dismissed,
                    :vd_true, :vd_false,
                    :or_gn, :or_gs, :or_intl, :or_dom, :or_unknown,
                    :flagged,
                    :run_id
                )
                """
            ),
            {
                "document_id": document_id,
                "case_id": verified.get("case_id"),
                "source_jurisdiction": verified.get("source_jurisdiction"),
                "source_region": verified.get("source_region"),
                "source_year": verified.get("source_year"),
                "verification_timestamp": verified.get("verification_timestamp"),
                "total_extracted": verified.get("total_citations_extracted", len(citations)),
                "total_confirmed": verified.get("total_confirmed", 0),
                "total_not_found": verified.get("total_not_found", 0),
                "total_misattributed": verified.get("total_misattributed", 0),
                "total_not_a_case": verified.get("total_not_a_case", 0),
                "total_duplicates": verified.get("total_duplicates", 0),
                "unique_confirmed": verified.get("unique_citations_confirmed", 0),
                "sf_foreign": by_sf.get("Foreign Citation", 0),
                "sf_international": by_sf.get("International Citation", 0),
                "sf_foreign_international": by_sf.get("Foreign International Citation", 0),
                "sf_inter_system": by_sf.get("Inter-System Citation", 0),
                "sf_member_state": by_sf.get("Member-State Citation", 0),
                "sf_non_member": by_sf.get("Non-Member Citation", 0),
                "sf_domestic": by_sf.get("Domestic", 0),
                "sf_unclassified": by_sf.get("Unclassified", 0),
                "fu_aligned": by_fu.get("aligned", 0),
                "fu_contested": by_fu.get("contested", 0),
                "fu_avoided": by_fu.get("avoided", 0),
                "fu_invoked": by_fu.get("invoked", 0),
                "fu_dismissed": by_fu.get("dismissed", 0),
                "vd_true": by_vd.get("true", 0) if isinstance(by_vd, dict) else 0,
                "vd_false": by_vd.get("false", 0) if isinstance(by_vd, dict) else 0,
                "or_gn": by_or.get("Global North", 0),
                "or_gs": by_or.get("Global South", 0),
                "or_intl": by_or.get("International", 0),
                "or_dom": by_or.get("Domestic", 0),
                "or_unknown": by_or.get("Unknown", 0),
                "flagged": summary.get("flagged_for_review", 0),
                "run_id": run_id,
            },
        )

        # Update run_state
        verified_count = verified.get("total_confirmed", 0)
        dismissed_count = by_fu.get("dismissed", 0)
        vertical_count = by_vd.get("true", 0) if isinstance(by_vd, dict) else 0
        conn.execute(
            text(
                """
                UPDATE citation_agent_v1_run_state
                SET status = 'complete',
                    last_attempt_finished = NOW(),
                    extract_path = :ext_path,
                    verify_path = :ver_path,
                    citations_extracted = :extracted,
                    citations_verified = :verified,
                    citations_dismissed = :dismissed,
                    citations_vertical = :vertical,
                    error_message = NULL,
                    notes = COALESCE(notes || '; ', '') || 'completed at ' || NOW()::TEXT
                WHERE document_id = :doc_id
                """
            ),
            {
                "doc_id": document_id,
                "ext_path": str(EXTRACTION_DIR / f"{document_id}_extracted.json"),
                "ver_path": str(path),
                "extracted": verified.get("total_citations_extracted", len(citations)),
                "verified": verified_count,
                "dismissed": dismissed_count,
                "vertical": vertical_count,
            },
        )

    log.info(
        f"✓ ingest {document_id[:8]}… {len(citations)} citations "
        f"({verified_count} confirmed, {dismissed_count} dismissed, {vertical_count} vertical)"
    )
    return 0


# =============================================================================
# COMMAND: mark_failed
# =============================================================================


def cmd_mark_failed(document_id: str, error_message: str) -> int:
    """Mark the doc as failed."""
    engine = get_engine()
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                UPDATE citation_agent_v1_run_state
                SET status = 'failed',
                    last_attempt_finished = NOW(),
                    error_message = :error
                WHERE document_id = :doc_id
                RETURNING attempts
                """
            ),
            {"doc_id": document_id, "error": error_message},
        ).first()
    if result is None:
        log.error(f"document_id {document_id} not found")
        return 1
    log.warning(f"⚠ failed {document_id[:8]}… (attempt {result[0]}): {error_message[:100]}")
    return 0


# =============================================================================
# COMMAND: mark_skipped
# =============================================================================


def cmd_mark_skipped(document_id: str, reason: str) -> int:
    """Mark the doc as skipped (manual exclusion)."""
    engine = get_engine()
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                UPDATE citation_agent_v1_run_state
                SET status = 'skipped',
                    notes = COALESCE(notes || '; ', '') || :reason
                WHERE document_id = :doc_id
                """
            ),
            {"doc_id": document_id, "reason": reason},
        )
    if result.rowcount == 0:
        log.error(f"document_id {document_id} not found")
        return 1
    log.info(f"✓ skipped {document_id[:8]}…: {reason}")
    return 0


# =============================================================================
# COMMAND: status
# =============================================================================


def cmd_status(full: bool) -> int:
    """Print run-state snapshot."""
    engine = get_engine()
    with engine.connect() as conn:
        rows = list(
            conn.execute(
                text(
                    """
                    SELECT status, tier, COUNT(*) AS docs,
                           SUM(citations_verified) AS citations,
                           SUM(citations_vertical) AS vertical,
                           SUM(citations_dismissed) AS dismissed
                    FROM citation_agent_v1_run_state
                    GROUP BY status, tier
                    ORDER BY status, tier
                    """
                )
            ).mappings().all()
        )

    print("status     | tier | docs   | citations | vertical | dismissed")
    print("-----------|------|--------|-----------|----------|----------")
    for r in rows:
        tier = str(r["tier"]) if r["tier"] is not None else "—"
        c = r["citations"] or 0
        v = r["vertical"] or 0
        d = r["dismissed"] or 0
        print(f"{r['status']:<10} | {tier:<4} | {r['docs']:>6} | {c:>9} | {v:>8} | {d:>9}")

    if full:
        with engine.connect() as conn:
            failed = list(
                conn.execute(
                    text(
                        """
                        SELECT document_id::TEXT, attempts, error_message
                        FROM citation_agent_v1_run_state
                        WHERE status = 'failed'
                        ORDER BY last_attempt_finished DESC
                        LIMIT 20
                        """
                    )
                ).mappings().all()
            )
            if failed:
                print("\nRecent failures:")
                for f in failed:
                    print(f"  {f['document_id'][:8]}… (attempt {f['attempts']}): {f['error_message'][:80] if f['error_message'] else ''}")
    return 0


# =============================================================================
# CLI
# =============================================================================


def main() -> int:
    parser = argparse.ArgumentParser(description="Orchestrator helper for the corpus-run pipeline.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("startup")

    p_next = sub.add_parser("next")
    p_next.add_argument("--tier", type=int, choices=[1, 2, 3], default=None)
    p_next.add_argument("--limit", type=int, default=10)

    p_prep = sub.add_parser("prepare")
    p_prep.add_argument("document_id")

    p_ing = sub.add_parser("ingest")
    p_ing.add_argument("document_id")
    p_ing.add_argument("verified_json_path")

    p_fail = sub.add_parser("mark_failed")
    p_fail.add_argument("document_id")
    p_fail.add_argument("error_message")

    p_skip = sub.add_parser("mark_skipped")
    p_skip.add_argument("document_id")
    p_skip.add_argument("reason")

    p_status = sub.add_parser("status")
    p_status.add_argument("--full", action="store_true")

    args = parser.parse_args()
    if args.cmd == "startup":
        return cmd_startup()
    if args.cmd == "next":
        return cmd_next(args.tier, args.limit)
    if args.cmd == "prepare":
        return cmd_prepare(args.document_id)
    if args.cmd == "ingest":
        return cmd_ingest(args.document_id, args.verified_json_path)
    if args.cmd == "mark_failed":
        return cmd_mark_failed(args.document_id, args.error_message)
    if args.cmd == "mark_skipped":
        return cmd_mark_skipped(args.document_id, args.reason)
    if args.cmd == "status":
        return cmd_status(args.full)
    return 1


if __name__ == "__main__":
    sys.exit(main())
