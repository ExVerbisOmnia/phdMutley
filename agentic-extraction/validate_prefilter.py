"""
validate_prefilter.py — Validation gate for the citation-prefilter agent.

Runs the prefilter against documents whose ground truth is already known
(status='complete' in citation_agent_v1_run_state, with citation counts in
citation_agent_v1). Compares predictions to ground truth and reports the
confusion matrix.

PASS CRITERION: zero HARD_MISS at the chosen confidence threshold.

Categories
----------
- HARD_MISS       truth ≥1 citation, pred=false, confidence ≥ threshold
                  → prefilter would BYPASS the doc; citations would be lost.
                  This is the only category that gates the pass.
- SOFT_MISS       truth ≥1 citation, pred=false, confidence < threshold
                  → orchestrator routes to full pipeline anyway. No data loss.
- CORRECT_KEPT    truth ≥1 citation, pred=true. Full pipeline runs.
- WASTED          truth 0 citations, pred=true. Doc goes through full pipeline
                  even though it didn't need to. Wasted cost, not data loss.
- CORRECT_BYPASS  truth 0 citations, pred=false, confidence ≥ threshold.
                  Optimal outcome — saves a full extractor+verifier run.
- LOW_CONF_NEG    truth 0 citations, pred=false, confidence < threshold.
                  No bypass; doc routes to full pipeline. Same wasted cost as
                  WASTED, just routed via a different decision path.
- PREFILTER_FAILED  Agent returned no parseable JSON. Logged separately.

The script does NOT modify any DB rows. Reads only.

Usage
-----
    python validate_prefilter.py                         # all complete docs, threshold=0.90
    python validate_prefilter.py --sample 5              # smoke test on 5 docs
    python validate_prefilter.py --threshold 0.95        # raise the bar
    python validate_prefilter.py --workers 5             # parallelism (default 5)
    python validate_prefilter.py --output results.jsonl  # custom output path
"""
import argparse
import json
import logging
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from config import DB_CONFIG  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DECISIONS_DIR = PROJECT_ROOT / "data" / "decisions_md"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "agentic-extraction" / "validation"
DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PREFILTER_TIMEOUT_S = 180
DEFAULT_WORKERS = 5
DEFAULT_THRESHOLD = 0.90

PREFILTER_PROMPT_TEMPLATE = (
    "Read the document at `data/decisions_md/{doc_id}.md` and apply your "
    "classification protocol. Return ONLY the JSON object as specified in your "
    "system prompt (no prose, no markdown fences, no explanation).\n"
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FILE = DEFAULT_OUTPUT_DIR / f"validate_{datetime.now():%Y%m%d_%H%M%S}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger("validate")


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------
def get_engine():
    cs = (f"postgresql://{DB_CONFIG['username']}:{DB_CONFIG['password']}"
          f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    return create_engine(cs)


def fetch_ground_truth(engine, sample: int | None) -> list[dict]:
    """
    Get all status='complete' docs with their CONFIRMED-citation counts.

    Ground truth: a doc has citations if there is at least one row in
    citation_agent_v1 with verification_verdict='CONFIRMED' (the verdict
    assigned by the verifier to citations that exist in the source text).
    DUPLICATE rows are not counted independently — they point to a primary
    CONFIRMED row, so the confirmed count already covers the case.
    """
    sql = """
        SELECT
            r.document_id::TEXT AS doc_id,
            r.tier,
            r.word_count,
            COUNT(*) FILTER (WHERE c.verification_verdict = 'CONFIRMED') AS confirmed_count
        FROM citation_agent_v1_run_state r
        LEFT JOIN citation_agent_v1 c ON c.document_id = r.document_id
        WHERE r.status = 'complete'
        GROUP BY r.document_id, r.tier, r.word_count
        ORDER BY r.tier, r.word_count
    """
    with engine.connect() as conn:
        rows = [dict(r) for r in conn.execute(text(sql)).mappings().all()]
    if sample is not None:
        rows = rows[:sample]
    return rows


# ---------------------------------------------------------------------------
# Prefilter dispatch
# ---------------------------------------------------------------------------
def run_prefilter(doc_id: str) -> tuple[dict | None, str | None, float]:
    """
    Spawn `claude --print --agent citation-prefilter` for one document.

    Returns (parsed_json_or_None, error_or_None, elapsed_seconds).
    """
    cmd = [
        "claude", "--print",
        "--agent", "citation-prefilter",
        "--output-format", "json",
        "--no-session-persistence",
    ]
    started = time.time()
    try:
        proc = subprocess.run(
            cmd,
            input=PREFILTER_PROMPT_TEMPLATE.format(doc_id=doc_id),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=PREFILTER_TIMEOUT_S,
            cwd=str(PROJECT_ROOT),
        )
    except subprocess.TimeoutExpired:
        return None, f"timeout after {PREFILTER_TIMEOUT_S}s", time.time() - started

    elapsed = time.time() - started
    if proc.returncode != 0:
        return None, f"exit={proc.returncode}: {proc.stderr.strip()[:300]}", elapsed

    parsed = parse_agent_json_result(proc.stdout)
    if parsed is None:
        return None, "agent returned no parseable JSON", elapsed
    return parsed, None, elapsed


def parse_agent_json_result(raw_stdout: str) -> dict | None:
    """
    `claude --output-format json` returns an envelope:
        {"type": "result", "result": "<assistant text>", ...}
    Parse out the assistant's JSON. Fall back to scanning for the last
    balanced {...} in raw stdout.
    """
    if not raw_stdout:
        return None
    try:
        env = json.loads(raw_stdout)
        if isinstance(env, dict) and "result" in env:
            inner = env["result"]
            if isinstance(inner, dict):
                return inner
            if isinstance(inner, str):
                return _extract_json_block(inner)
    except json.JSONDecodeError:
        pass
    return _extract_json_block(raw_stdout)


def _extract_json_block(s: str) -> dict | None:
    """Find the last balanced {...} in s and parse it."""
    last_close = s.rfind("}")
    if last_close < 0:
        return None
    depth = 0
    for i in range(last_close, -1, -1):
        if s[i] == "}":
            depth += 1
        elif s[i] == "{":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(s[i:last_close + 1])
                except json.JSONDecodeError:
                    continue
    return None


# ---------------------------------------------------------------------------
# Categorization
# ---------------------------------------------------------------------------
def categorize(truth_has: bool, pred_has: bool, pred_conf: float, threshold: float) -> str:
    """Return one of seven category strings; see module docstring."""
    if truth_has and pred_has:
        return "CORRECT_KEPT"
    if truth_has and (not pred_has):
        return "HARD_MISS" if pred_conf >= threshold else "SOFT_MISS"
    # truth_has is False below
    if (not truth_has) and pred_has:
        return "WASTED"
    return "CORRECT_BYPASS" if pred_conf >= threshold else "LOW_CONF_NEG"


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
def driver(args) -> int:
    log.info("=" * 70)
    log.info(f"validate_prefilter starting  threshold={args.threshold}  "
             f"workers={args.workers}  sample={args.sample or 'all'}")
    log.info("=" * 70)

    engine = get_engine()
    docs = fetch_ground_truth(engine, args.sample)
    if not docs:
        log.error("no status='complete' docs found — nothing to validate")
        return 1

    # Summary of the test set
    total = len(docs)
    has_citation_count = sum(1 for d in docs if d["confirmed_count"] >= 1)
    no_citation_count = total - has_citation_count
    log.info(f"test set: {total} docs   "
             f"({has_citation_count} with ≥1 confirmed citation, "
             f"{no_citation_count} with 0)")
    by_tier = {}
    for d in docs:
        by_tier.setdefault(d["tier"], 0)
        by_tier[d["tier"]] += 1
    for tier, n in sorted(by_tier.items()):
        log.info(f"  tier {tier}: {n} docs")

    # Run prefilter in parallel
    log.info(f"\ndispatching prefilter on {total} docs with N={args.workers} workers...")
    started_run = time.time()
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.workers, thread_name_prefix="val") as ex:
        future_to_doc = {ex.submit(run_prefilter, d["doc_id"]): d for d in docs}
        completed = 0
        for fut in as_completed(future_to_doc):
            d = future_to_doc[fut]
            pred, err, elapsed = fut.result()
            completed += 1
            short = d["doc_id"][:8]
            if err is not None:
                log.warning(f"  [{completed}/{total}] {short} FAILED: {err}")
                results.append({**d, "prediction": None, "error": err,
                                "elapsed_s": elapsed, "category": "PREFILTER_FAILED"})
                continue
            truth_has = d["confirmed_count"] >= 1
            pred_has = bool(pred.get("has_citations"))
            pred_conf = float(pred.get("confidence") or 0)
            category = categorize(truth_has, pred_has, pred_conf, args.threshold)
            log.info(f"  [{completed}/{total}] {short} "
                     f"truth={'+' if truth_has else '-'}{d['confirmed_count']} "
                     f"pred={'+' if pred_has else '-'} conf={pred_conf:.2f} "
                     f"→ {category}  ({elapsed:.1f}s)")
            results.append({**d, "prediction": pred, "error": None,
                            "elapsed_s": elapsed, "category": category})
    total_elapsed = time.time() - started_run

    # Persist per-doc rows for later analysis
    output_path = Path(args.output) if args.output else (
        DEFAULT_OUTPUT_DIR / f"results_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
    )
    with output_path.open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")
    log.info(f"\nper-doc results: {output_path}")

    # Report
    return print_report(results, args.threshold, total_elapsed)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def print_report(results: list[dict], threshold: float, total_elapsed_s: float) -> int:
    """Print summary report. Return 0 on PASS, 1 on FAIL."""
    counts: dict[str, int] = {}
    for r in results:
        counts[r["category"]] = counts.get(r["category"], 0) + 1

    log.info("\n" + "=" * 70)
    log.info("VALIDATION REPORT")
    log.info("=" * 70)
    log.info(f"  threshold:       {threshold}")
    log.info(f"  total docs:      {len(results)}")
    log.info(f"  total wall time: {total_elapsed_s:.1f}s "
             f"({total_elapsed_s / max(len(results),1):.1f}s/doc avg)")
    log.info("")
    log.info("  Category         Count   Meaning")
    log.info("  ---------------- -----   -----------------------------------------------")
    log.info(f"  CORRECT_KEPT     {counts.get('CORRECT_KEPT', 0):>5}   truth=yes, pred=yes — full pipeline runs (correct)")
    log.info(f"  CORRECT_BYPASS   {counts.get('CORRECT_BYPASS', 0):>5}   truth=no,  pred=no, conf≥t — bypass (cost saved!)")
    log.info(f"  WASTED           {counts.get('WASTED', 0):>5}   truth=no,  pred=yes — full pipeline runs (cost wasted)")
    log.info(f"  LOW_CONF_NEG     {counts.get('LOW_CONF_NEG', 0):>5}   truth=no,  pred=no, conf<t — full pipeline runs (no bypass)")
    log.info(f"  SOFT_MISS        {counts.get('SOFT_MISS', 0):>5}   truth=yes, pred=no, conf<t — full pipeline runs (safe, no bypass)")
    log.info(f"  HARD_MISS        {counts.get('HARD_MISS', 0):>5}   truth=yes, pred=no, conf≥t — DATA LOSS, would bypass")
    log.info(f"  PREFILTER_FAILED {counts.get('PREFILTER_FAILED', 0):>5}   agent crashed / unparseable JSON")
    log.info("")

    # Cost-saving estimate (CORRECT_BYPASS rate)
    bypass_rate = counts.get("CORRECT_BYPASS", 0) / max(len(results), 1)
    waste_rate = counts.get("WASTED", 0) / max(len(results), 1)
    log.info(f"  bypass rate (cost saved):  {bypass_rate * 100:.1f}%  ({counts.get('CORRECT_BYPASS', 0)} docs)")
    log.info(f"  waste rate (false alarm):  {waste_rate * 100:.1f}%  ({counts.get('WASTED', 0)} docs)")

    # Hard-miss listing
    hard_misses = [r for r in results if r["category"] == "HARD_MISS"]
    if hard_misses:
        log.info("")
        log.info("HARD MISSES — these docs would be incorrectly bypassed:")
        for r in hard_misses:
            pred = r["prediction"]
            log.info(f"  - doc {r['doc_id']}  (tier {r['tier']}, "
                     f"{r['confirmed_count']} confirmed citations)")
            log.info(f"    confidence: {pred['confidence']:.2f}")
            log.info(f"    signals:    {pred.get('signals_observed')}")
            log.info(f"    reason:     {pred.get('reason')}")

    # Soft-miss listing — useful for tuning even though not a blocker
    soft_misses = [r for r in results if r["category"] == "SOFT_MISS"]
    if soft_misses:
        log.info("")
        log.info(f"SOFT MISSES — {len(soft_misses)} doc(s) would still go through full pipeline (no bypass), "
                 "but the prefilter's binary call was wrong:")
        for r in soft_misses[:5]:
            pred = r["prediction"]
            log.info(f"  - doc {r['doc_id']} conf={pred['confidence']:.2f} "
                     f"(truth={r['confirmed_count']} citations)")
        if len(soft_misses) > 5:
            log.info(f"  ... and {len(soft_misses) - 5} more (see JSONL output)")

    # Verdict
    log.info("")
    log.info("=" * 70)
    if counts.get("HARD_MISS", 0) == 0 and counts.get("PREFILTER_FAILED", 0) == 0:
        log.info("✓ VALIDATION GATE: PASS  (zero hard misses)")
        log.info("=" * 70)
        return 0
    else:
        log.info("✗ VALIDATION GATE: FAIL")
        if counts.get("HARD_MISS", 0):
            log.info(f"   {counts['HARD_MISS']} hard miss(es) — fix prefilter signals before scaling")
        if counts.get("PREFILTER_FAILED", 0):
            log.info(f"   {counts['PREFILTER_FAILED']} agent failure(s) — investigate before scaling")
        log.info("=" * 70)
        return 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                   help=f"bypass confidence threshold (default {DEFAULT_THRESHOLD})")
    p.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                   help=f"parallel claude calls (default {DEFAULT_WORKERS})")
    p.add_argument("--sample", type=int, default=None,
                   help="run on first N docs only (for smoke testing)")
    p.add_argument("--output", type=str, default=None,
                   help="path for per-doc JSONL output (default: timestamped under "
                        "agentic-extraction/validation/)")
    args = p.parse_args()
    return driver(args)


if __name__ == "__main__":
    sys.exit(main())
