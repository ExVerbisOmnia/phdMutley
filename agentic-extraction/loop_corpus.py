"""
loop_corpus.py — Python orchestrator for the corpus-run citation-extraction pipeline.

Replaces the legacy LLM-orchestrator (loop_corpus_orchestrator.sh + orchestrator-driver.md).
Rationale: every responsibility of the LLM orchestrator (pick docs, dispatch agents, parse
JSON, mark DB rows) is mechanical — no model judgment needed. A Python orchestrator
gives us:
  - Real parallelism (asyncio/threads) instead of sequential N=3 background dispatches
  - Zero parent-session token burn per doc (the LLM orchestrator was spending ~250-400K
    tokens per 20-doc session just on bookkeeping)
  - Cleaner cost shape under Claude Max rate caps

Modes:
  - default          full pipeline per doc (prefilter → extract → verify → ingest).
                     Claims rows where status IN ('pending', 'prefilter_keep').
  - --prefilter-only prefilter pass only — Haiku triages every claimed doc into
                     either 'prefiltered' (Sonnet bypassed) or 'prefilter_keep'
                     (full pipeline still owes work). Both are persistent
                     terminal states for this pass; the row will not be
                     re-claimed within the same run.
                     Claims only status='pending'. Failures (timeout / non-zero
                     exit / unparseable JSON) are released back to 'pending'
                     for retry while attempts < RETRY_CAP_TOTAL, then marked
                     'failed' once the cap is hit. A fixed sleep (RETRY_BACKOFF_S)
                     after each transient failure gives rate-limit blips a
                     chance to clear without manual intervention.
                     Cheap (Haiku-only) cost-prediction phase.

Pipeline per document (default mode):
  1. PREFILTER  — citation-prefilter agent (Haiku). Returns {has_citations, confidence, ...}.
                  If has_citations=false AND confidence >= 0.9, mark_prefiltered and DONE.
                  Otherwise (or if has_citations=true), continue.
  2. EXTRACT    — citation-extractor agent (Sonnet). Writes data/extraction_results/<id>_extracted.json.
  3. VERIFY     — citation-verifier agent (Sonnet). Writes data/extraction_results/<id>_verified.json.
  4. INGEST     — orchestrator_helper.py ingest <id> <verified.json>. Marks complete.

Parallelism: ThreadPoolExecutor(max_workers=N). One worker = one full doc pipeline.
Workers are independent; failures in one doc don't block others.

Usage:
    python loop_corpus.py                                  # process pending docs, N=5
    python loop_corpus.py --workers 3                      # N=3
    python loop_corpus.py --max-docs 50                    # cap total docs this run
    python loop_corpus.py --tier 1                         # only Tier 1 docs
    python loop_corpus.py --no-prefilter                   # skip prefilter (full pipeline always)
    python loop_corpus.py --prefilter-only                 # prefilter pass only — bypass + release; no extraction
    python loop_corpus.py --confidence-threshold 0.95      # raise prefilter bypass bar

Stop with Ctrl+C — in-flight workers finish their current step; no new docs are picked.
DB is the source of truth; restart picks up where this left off.
"""
import argparse
import json
import logging
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from gcp_secrets import get_db_config  # noqa: E402

DB_CONFIG = get_db_config()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DECISIONS_DIR = PROJECT_ROOT / "data" / "decisions_md"
EXTRACTION_DIR = PROJECT_ROOT / "data" / "extraction_results"
LOG_DIR = PROJECT_ROOT / "logs"
AGENT_DUMP_DIR = LOG_DIR / "agent_dumps"
LOG_DIR.mkdir(exist_ok=True)
EXTRACTION_DIR.mkdir(parents=True, exist_ok=True)
AGENT_DUMP_DIR.mkdir(parents=True, exist_ok=True)

ORCH_HELPER = "agentic-extraction/orchestrator_helper.py"

# Per-step timeouts (seconds). A bit slack over what the agent should need.
# Prefilter is one Haiku read+classify; cost scales with input size, so Tier 2/3
# need more wall-clock than Tier 1 (which routinely lands in 20-35s).
PREFILTER_TIMEOUT_S = {1: 180, 2: 600, 3: 1800}  # by tier
EXTRACT_TIMEOUT_S = {1: 600, 2: 1800, 3: 3600}   # by tier
VERIFY_TIMEOUT_S = {1: 600, 2: 1800, 3: 3600}

DEFAULT_WORKERS = 5
DEFAULT_CONFIDENCE_THRESHOLD = 0.90

# Retry policy (shared with orchestrator_helper.RETRY_CAP). Exit≠0 / empty-stderr
# CLI failures are treated as transient: release back to pending, sleep, let the
# claim-side filter (`attempts < RETRY_CAP_TOTAL`) eventually quarantine docs
# that fail this way RETRY_CAP_TOTAL times in a row.
RETRY_CAP_TOTAL = 3
RETRY_BACKOFF_S = 60

# Stop-flag set on SIGINT; checked between dispatches.
_STOP = threading.Event()


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FILE = LOG_DIR / f"loop_corpus_{datetime.now():%Y%m%d_%H%M%S}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(threadName)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger("loop_corpus")


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------
def get_engine():
    cs = (f"postgresql://{DB_CONFIG['username']}:{DB_CONFIG['password']}"
          f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    return create_engine(cs)


def claim_next_pending(
    engine, tier: int | None, prefilter_only: bool = False
) -> dict | None:
    """
    Atomically claim the next claimable doc: pick one and set status='in_progress'.
    Returns {document_id, tier, word_count, attempts} or None if queue empty.

    Mode semantics:
      - prefilter_only=True  → only 'pending' rows are claimable. 'prefilter_keep'
                               rows already have a Haiku verdict and are skipped
                               for this pass.
      - prefilter_only=False → claim 'pending' AND 'prefilter_keep'. The full
                               pipeline drains both pools; 'prefilter_keep' rows
                               just skip the Haiku step (their verdict is already
                               known to be "keep").

    Uses SELECT ... FOR UPDATE SKIP LOCKED for safe concurrent claiming. The
    document_id tie-breaker on the ORDER BY makes the queue order stable, so a
    just-released doc cannot bob to the head and get re-claimed instantly.
    """
    if prefilter_only:
        status_pred = "status = 'pending'"
    else:
        status_pred = "status IN ('pending', 'prefilter_keep')"
    where = [status_pred, "attempts < 3"]
    if tier is not None:
        where.append(f"tier = {int(tier)}")
    sql = f"""
        WITH picked AS (
            SELECT document_id
            FROM citation_agent_v1_run_state
            WHERE {' AND '.join(where)}
            ORDER BY tier ASC, word_count ASC NULLS LAST, document_id ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        )
        UPDATE citation_agent_v1_run_state r
        SET status = 'in_progress',
            attempts = r.attempts + 1,
            last_attempt_started = NOW(),
            error_message = NULL
        FROM picked
        WHERE r.document_id = picked.document_id
        RETURNING r.document_id::TEXT, r.tier, r.word_count, r.attempts
    """
    with engine.begin() as conn:
        row = conn.execute(text(sql)).mappings().first()
    return dict(row) if row else None


def reset_in_progress_at_startup(engine) -> int:
    """Reset stale in_progress rows from a prior interrupted run."""
    return subprocess.run(
        [sys.executable, ORCH_HELPER, "startup"], cwd=str(PROJECT_ROOT)
    ).returncode


# ---------------------------------------------------------------------------
# Agent dispatch
# ---------------------------------------------------------------------------
def run_claude_agent(
    agent_name: str, prompt: str, timeout_s: int, doc_id: str
) -> tuple[bool, str, str]:
    """
    Spawn `claude --print --agent <name> --output-format json` with the given prompt
    on stdin. Return (ok, stdout, stderr). `ok` is True iff exit code 0 within timeout.
    """
    cmd = [
        "claude", "--print",
        "--agent", agent_name,
        "--output-format", "json",
        "--no-session-persistence",
    ]
    log.debug(f"[{doc_id[:8]}] dispatch agent={agent_name} timeout={timeout_s}s")
    try:
        proc = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            cwd=str(PROJECT_ROOT),
        )
        return (proc.returncode == 0, proc.stdout, proc.stderr)
    except subprocess.TimeoutExpired as e:
        return (False, e.stdout or "", f"TIMEOUT after {timeout_s}s")


def parse_agent_json_result(raw_stdout: str) -> dict | None:
    """
    `claude --output-format json` returns an envelope like:
        {"type": "result", "subtype": "success", "result": "<assistant's text>", ...}
    We want the assistant's text parsed as JSON. Try the envelope's "result" first;
    fall back to scanning for the last {...} block in the raw stdout.
    """
    if not raw_stdout:
        return None
    # Try envelope
    try:
        env = json.loads(raw_stdout)
        if isinstance(env, dict) and "result" in env:
            inner = env["result"]
            if isinstance(inner, dict):
                return inner
            if isinstance(inner, str):
                # The agent's final message — may have prose wrapping JSON
                return _extract_json_block(inner)
    except json.JSONDecodeError:
        pass
    # Fallback: scan raw stdout for last JSON block
    return _extract_json_block(raw_stdout)


def is_agent_error_envelope(raw_stdout: str) -> bool:
    """
    Detect whether `claude --output-format json` returned a structurally-valid
    *error* envelope rather than a successful result. Distinct from "unparseable
    JSON" — the JSON parses fine; it just signals the agent's turn was aborted
    (often `stop_reason=tool_use` mid-streaming) and produced no usable result.

    Example shape we want to flag:
        {"type":"result","subtype":"error_during_execution","is_error":true,
         "stop_reason":"tool_use","terminal_reason":"aborted_streaming", ...}
    """
    if not raw_stdout:
        return False
    try:
        env = json.loads(raw_stdout)
    except json.JSONDecodeError:
        return False
    if not isinstance(env, dict):
        return False
    return bool(env.get("is_error")) or env.get("subtype") == "error_during_execution"


def _extract_json_block(s: str) -> dict | None:
    """Find the last balanced {...} in s and parse it. Returns None on failure."""
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


MAX_DUMP_BYTES = 100_000  # cap per stream — Haiku occasionally echoes the source doc


def dump_agent_output(
    agent: str, doc_id: str, stdout: str, stderr: str, reason: str
) -> Path | None:
    """
    Persist a failing agent invocation's raw stdout/stderr to AGENT_DUMP_DIR for
    post-mortem inspection. Called from process_doc when the agent CLI exited
    non-zero or returned output we couldn't parse as JSON. Best-effort — never
    raises into the caller.

    Filename: {ts}_{agent}_{reason}_{doc_id_short}.txt (sortable by time,
    greppable by reason). Each stream is capped at MAX_DUMP_BYTES with a
    truncation footer so a single failure can't blow up disk usage during a
    4k-doc run.
    """
    def _truncate(s: str) -> str:
        if not s:
            return "(empty)"
        b = s.encode("utf-8", errors="replace")
        if len(b) <= MAX_DUMP_BYTES:
            return s
        head = b[:MAX_DUMP_BYTES].decode("utf-8", errors="replace")
        return f"{head}\n\n[... truncated, total {len(b)} bytes ...]"

    try:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = AGENT_DUMP_DIR / f"{ts}_{agent}_{reason}_{doc_id[:8]}.txt"
        body = (
            f"timestamp: {datetime.now().isoformat()}\n"
            f"agent:     {agent}\n"
            f"doc_id:    {doc_id}\n"
            f"reason:    {reason}\n"
            f"\n--- STDOUT ---\n{_truncate(stdout)}\n"
            f"\n--- STDERR ---\n{_truncate(stderr)}\n"
        )
        path.write_text(body, encoding="utf-8")
        return path
    except Exception as e:
        log.warning(f"dump_agent_output failed for {doc_id[:8]}/{reason}: {e}")
        return None


# ---------------------------------------------------------------------------
# Step prompts
# ---------------------------------------------------------------------------
PREFILTER_PROMPT = """Read the document at `data/decisions_md/{doc_id}.md` and apply your
classification protocol. Return ONLY the JSON object as specified in your system prompt
(no prose, no markdown fences, no explanation).
"""

EXTRACT_PROMPT = """You are processing document `{doc_id}` (Tier {tier}, {word_count} words)
through the citation-EXTRACTOR protocol.

Steps:
1. Read the source document at `data/decisions_md/{doc_id}.md`. For Tier 2 (25k-100k words),
   read in 300-line chunks via Read(offset=N, limit=300) and aggregate findings. For Tier 3
   (>100k words), pre-chunked files exist at `data/decisions_md_chunks/{doc_id}/chunk_NN_of_TT.md`
   (run `python agentic-extraction/chunk_large_docs.py {doc_id}` first if they don't).
2. Apply the citation-extraction protocol from your system prompt. Maximize recall.
3. Write your output JSON to `data/extraction_results/{doc_id}_extracted.json` (use Bash
   with python -c or a heredoc; you don't have the Write tool).
4. Validate it parses with `python -c "import json; json.load(open('data/extraction_results/{doc_id}_extracted.json', encoding='utf-8'))"`.
5. Return ONLY this JSON summary (no prose):

{{
  "document_id": "{doc_id}",
  "status": "complete" | "failed",
  "extracted_path": "data/extraction_results/{doc_id}_extracted.json",
  "citations_extracted": <int>,
  "notes": "<brief>",
  "error": null | "<description if failed>"
}}

Do NOT touch the database. Do NOT commit. Do NOT spawn sub-agents.
"""

VERIFY_PROMPT = """You are processing document `{doc_id}` (Tier {tier}, {word_count} words)
through the citation-VERIFIER protocol.

Inputs:
- Original document: `data/decisions_md/{doc_id}.md`
- Extractor output:  `data/extraction_results/{doc_id}_extracted.json`

Steps:
1. Read the extractor JSON and the original document.
2. Apply the verification protocol from your system prompt. Maximize precision: confirm
   each citation actually exists, prune false positives, finalize sixfold + functional_use
   + origin classifications, deduplicate per D22, tag dismissed per D31, set
   is_vertical_dialogue per D30.
3. Write your output JSON to `data/extraction_results/{doc_id}_verified.json`.
4. Validate it parses with `python -c "import json; json.load(open('data/extraction_results/{doc_id}_verified.json', encoding='utf-8'))"`.
5. Return ONLY this JSON summary (no prose):

{{
  "document_id": "{doc_id}",
  "status": "complete" | "failed",
  "verified_path": "data/extraction_results/{doc_id}_verified.json",
  "citations_extracted": <int>,
  "citations_verified": <int>,
  "citations_dismissed": <int>,
  "citations_vertical": <int>,
  "notes": "<brief>",
  "error": null | "<description if failed>"
}}

Critical schema requirements (top-level): document_id, case_id, source_jurisdiction,
source_region, source_year, verification_timestamp, total_citations_extracted,
total_confirmed, total_not_found, total_misattributed, total_not_a_case, total_duplicates,
unique_citations_confirmed, citations[], summary{{}}.

Each citation MUST include is_vertical_dialogue (bool). functional_use values: aligned,
contested, avoided, invoked, dismissed. sixfold_type values: Foreign Citation,
International Citation, Foreign International Citation, Inter-System Citation,
Member-State Citation, Non-Member Citation, Domestic, Unclassified.

Do NOT touch the database. Do NOT commit. Do NOT spawn sub-agents.
"""


# ---------------------------------------------------------------------------
# Per-doc pipeline
# ---------------------------------------------------------------------------
def run_helper(*args: str) -> tuple[int, str, str]:
    """Invoke orchestrator_helper.py and return (rc, stdout, stderr).

    Uses sys.executable (the running parent's interpreter path) instead of
    bare "python" so a Windows PATH ambiguity can't silently swap out the
    interpreter and cause import failures (e.g. missing sqlalchemy in a
    different installation than the parent's).
    """
    cmd = [sys.executable, ORCH_HELPER, *args]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(PROJECT_ROOT))
    return (p.returncode, p.stdout, p.stderr)


def mark_failed(doc_id: str, message: str) -> None:
    rc, _, err = run_helper("mark_failed", doc_id, message[:500])
    if rc != 0:
        log.error(f"[{doc_id[:8]}] mark_failed itself failed: {err.strip()}")


def fail_or_retry(doc: dict, step: str, err_msg: str, started: float) -> dict:
    """
    Decide whether to release for retry (transient — under cap) or mark
    permanently failed (cap hit).

    Why: a single rate-limit event was previously enough to permanently
    quarantine hundreds of docs in 'failed', because mark_failed jumped
    straight to terminal status on the first exit≠0. The retry cap was
    nominally 3 (claim-side filter) but never reachable. This helper
    routes attempts < RETRY_CAP_TOTAL back to pending (with a fixed sleep
    to let transient blips clear) and only marks failed once the cap is hit.

    INPUT:
        - doc: claim_next_pending row (post-increment attempts)
        - step: short label for the failed phase ('prefilter' | 'extract' | ...)
        - err_msg: short diagnostic (kept on the row + log)
        - started: wall-clock when process_doc began, for elapsed reporting
    OUTPUT: result dict with outcome="retry" or outcome="failed"
    """
    doc_id = doc["document_id"]
    short = doc_id[:8]
    attempts = doc["attempts"]
    elapsed = time.time() - started
    err_msg = (err_msg or "").strip()
    short_err = err_msg[:120] if err_msg else "(empty)"

    if attempts >= RETRY_CAP_TOTAL:
        log.warning(f"[{short}] {step} fail (attempt {attempts}/{RETRY_CAP_TOTAL}); "
                    f"cap hit, marking failed: {short_err}")
        mark_failed(doc_id, f"{step}: {err_msg}")
        return {"doc_id": doc_id, "outcome": "failed", "step": step,
                "elapsed_s": elapsed}

    log.warning(f"[{short}] {step} fail (attempt {attempts}/{RETRY_CAP_TOTAL}); "
                f"releasing for retry, sleeping {RETRY_BACKOFF_S}s: {short_err}")
    rc, _, ferr = run_helper(
        "release_for_retry", doc_id, f"{step}: {err_msg[:300]}"
    )
    if rc != 0:
        # Log the full helper stderr — previously truncated at 200 chars, which
        # cut off Python tracebacks before the actual exception message.
        log.error(f"[{short}] release_for_retry failed; falling back to mark_failed: "
                  f"{ferr.strip()}")
        mark_failed(doc_id, f"{step} (release_for_retry failed): {err_msg}")
        return {"doc_id": doc_id, "outcome": "failed", "step": step,
                "elapsed_s": elapsed}
    time.sleep(RETRY_BACKOFF_S)
    return {"doc_id": doc_id, "outcome": "retry", "step": step,
            "elapsed_s": elapsed}


def process_doc(
    doc: dict,
    use_prefilter: bool,
    confidence_threshold: float,
    prefilter_only: bool = False,
) -> dict:
    """
    Full pipeline for one doc. Returns a result dict with `status` and `outcome`.
    Outcomes: prefiltered | complete | failed.
    """
    doc_id = doc["document_id"]
    tier = doc["tier"] or 1
    wc = doc["word_count"] or 0
    short = doc_id[:8]
    started = time.time()

    log.info(f"[{short}] start  tier={tier} words={wc}")

    # ----- PREFILTER -----
    # The prefilter agent's verdict drives one of three persistent outcomes
    # (set on the DB row before this function returns):
    #   - 'prefiltered'     : Haiku said no_citations w/ conf >= threshold → skip Sonnet
    #   - 'prefilter_keep'  : Haiku said keep (has_citations or sub-threshold) → Sonnet still owes work
    #   - 'failed'          : agent timed out, exited non-zero, or returned unparseable JSON
    #
    # In --prefilter-only mode, all three terminate the pipeline here.
    # In default mode, only 'prefiltered' short-circuits; the other two fall through
    # to extract+verify (a 'prefilter_keep' verdict from a prior pass also lands here
    # because we re-claim those rows; the prefilter is then re-run, which is fine —
    # in practice the default mode will not re-prefilter when claiming a prefilter_keep
    # row, see the early-return branch below).
    if use_prefilter:
        prefilter_to = PREFILTER_TIMEOUT_S.get(tier, 180)
        ok, out, err = run_claude_agent(
            "citation-prefilter",
            PREFILTER_PROMPT.format(doc_id=doc_id),
            prefilter_to,
            doc_id,
        )
        if not ok:
            err_msg = (err or "").strip()[:300]
            dump_agent_output("citation-prefilter", doc_id, out, err, "exit_nonzero")
            if prefilter_only:
                return fail_or_retry(
                    doc, "prefilter", f"agent exit≠0: {err_msg}", started
                )
            log.warning(f"[{short}] prefilter agent exit≠0 ({err_msg[:120]}); "
                        f"falling through to full pipeline")
        else:
            verdict = parse_agent_json_result(out)
            if verdict and "has_citations" in verdict and "confidence" in verdict:
                conf = float(verdict.get("confidence") or 0)
                has = bool(verdict.get("has_citations"))
                signals = verdict.get("signals_observed") or []
                reason = (verdict.get("reason") or "")[:1000]

                if (not has) and conf >= confidence_threshold:
                    # BYPASS — high-confidence "no citations"
                    rc, _, ferr = run_helper(
                        "mark_prefiltered",
                        doc_id, reason, f"{conf:.2f}", json.dumps(signals),
                    )
                    if rc == 0:
                        elapsed = time.time() - started
                        log.info(f"[{short}] PREFILTERED conf={conf:.2f} "
                                 f"signals={signals} ({elapsed:.0f}s)")
                        return {"doc_id": doc_id, "outcome": "prefiltered",
                                "confidence": conf, "elapsed_s": elapsed}
                    log.error(f"[{short}] mark_prefiltered failed: {ferr.strip()}")
                    # fall through to keep-or-fail handling below

                elif prefilter_only:
                    # KEEP in prefilter-only mode → record verdict as 'prefilter_keep'
                    rc, _, ferr = run_helper(
                        "mark_prefilter_keep",
                        doc_id, reason, f"{conf:.2f}", json.dumps(signals),
                    )
                    elapsed = time.time() - started
                    if rc == 0:
                        log.info(f"[{short}] PREFILTER_KEEP has={has} conf={conf:.2f} "
                                 f"signals={signals} ({elapsed:.0f}s)")
                        return {"doc_id": doc_id, "outcome": "prefilter_keep",
                                "confidence": conf, "elapsed_s": elapsed}
                    return fail_or_retry(
                        doc, "mark_prefilter_keep", ferr.strip()[:300], started
                    )
                else:
                    # KEEP in full-pipeline mode → continue to extract+verify
                    log.info(f"[{short}] prefilter: has={has} conf={conf:.2f} "
                             f"→ full pipeline")
            else:
                # No usable verdict — distinguish two shapes:
                #   * agent_error_envelope : CLI returned a valid JSON envelope
                #     with is_error=true / subtype=error_during_execution
                #     (e.g. aborted_streaming with stop_reason=tool_use). Cost
                #     was real, no work done; transient — retry.
                #   * unparseable_json     : envelope present but inner result
                #     wasn't parseable JSON (markdown fences, prose wrapping,
                #     malformed model output).
                if is_agent_error_envelope(out):
                    label = "agent_error_envelope"
                    retry_msg = "agent error envelope (CLI aborted)"
                else:
                    label = "unparseable_json"
                    retry_msg = "unparseable JSON"
                dump_agent_output("citation-prefilter", doc_id, out, err, label)
                if prefilter_only:
                    return fail_or_retry(doc, "prefilter", retry_msg, started)
                log.warning(f"[{short}] prefilter returned {retry_msg}; "
                            f"falling through to full pipeline")

    # Defense-in-depth: if --prefilter-only somehow reached this point without
    # returning above (e.g. use_prefilter was False, which the CLI rejects), do
    # not silently run the full pipeline.
    if prefilter_only:
        elapsed = time.time() - started
        log.error(f"[{short}] reached extract step in --prefilter-only mode (use_prefilter={use_prefilter}); marking failed")
        mark_failed(doc_id, "prefilter-only mode reached extract step (likely flag mismatch)")
        return {"doc_id": doc_id, "outcome": "failed", "step": "prefilter_only_guard",
                "elapsed_s": elapsed}

    # ----- EXTRACT -----
    extract_to = EXTRACT_TIMEOUT_S.get(tier, 1800)
    ok, out, err = run_claude_agent(
        "citation-extractor",
        EXTRACT_PROMPT.format(doc_id=doc_id, tier=tier, word_count=wc),
        extract_to,
        doc_id,
    )
    if not ok:
        return fail_or_retry(
            doc, "extract", f"agent exit≠0: {err.strip()[:300]}", started
        )

    extract_summary = parse_agent_json_result(out)
    extracted_path = EXTRACTION_DIR / f"{doc_id}_extracted.json"
    if not extracted_path.exists():
        return fail_or_retry(
            doc, "extract", f"no output file at {extracted_path}", started
        )
    log.info(f"[{short}] extracted ({extract_summary.get('citations_extracted', '?') if extract_summary else '?'} citations)")

    # ----- VERIFY -----
    verify_to = VERIFY_TIMEOUT_S.get(tier, 1800)
    ok, out, err = run_claude_agent(
        "citation-verifier",
        VERIFY_PROMPT.format(doc_id=doc_id, tier=tier, word_count=wc),
        verify_to,
        doc_id,
    )
    if not ok:
        return fail_or_retry(
            doc, "verify", f"agent exit≠0: {err.strip()[:300]}", started
        )

    verified_path = EXTRACTION_DIR / f"{doc_id}_verified.json"
    if not verified_path.exists():
        return fail_or_retry(
            doc, "verify", f"no output file at {verified_path}", started
        )

    # ----- INGEST -----
    rc, _, ierr = run_helper("ingest", doc_id, str(verified_path))
    if rc != 0:
        return fail_or_retry(
            doc, "ingest", f"helper rc={rc}: {ierr.strip()[:300]}", started
        )
    elapsed = time.time() - started

    log.info(f"[{short}] COMPLETE ({elapsed:.0f}s)")
    return {"doc_id": doc_id, "outcome": "complete", "elapsed_s": elapsed}


# ---------------------------------------------------------------------------
# Driver loop
# ---------------------------------------------------------------------------
def driver(args) -> int:
    engine = get_engine()
    log.info("=" * 70)
    mode = "PREFILTER-ONLY" if args.prefilter_only else "full pipeline"
    log.info(f"loop_corpus starting  mode={mode}  workers={args.workers}  "
             f"prefilter={'on' if not args.no_prefilter else 'off'}  "
             f"threshold={args.confidence_threshold}  "
             f"tier={args.tier or 'any'}  max_docs={args.max_docs or '∞'}")
    log.info(f"log file: {LOG_FILE}")
    log.info("=" * 70)

    # Reset stale in_progress rows from prior interrupted run.
    reset_in_progress_at_startup(engine)

    counters = {
        "complete": 0, "prefiltered": 0, "prefilter_keep": 0,
        "released": 0, "retry": 0, "failed": 0, "dispatched": 0,
    }
    counters_lock = threading.Lock()

    def submit_one(executor):
        if _STOP.is_set():
            return None
        if args.max_docs and counters["dispatched"] >= args.max_docs:
            return None
        doc = claim_next_pending(engine, args.tier, prefilter_only=args.prefilter_only)
        if doc is None:
            return None
        with counters_lock:
            counters["dispatched"] += 1
        return executor.submit(
            process_doc, doc, not args.no_prefilter, args.confidence_threshold,
            args.prefilter_only,
        )

    started_run = time.time()
    with ThreadPoolExecutor(max_workers=args.workers, thread_name_prefix="wkr") as ex:
        in_flight = set()
        # Prime the pool
        for _ in range(args.workers):
            fut = submit_one(ex)
            if fut is not None:
                in_flight.add(fut)

        # Drain & refill
        while in_flight:
            done = next(as_completed(in_flight))
            in_flight.remove(done)
            try:
                result = done.result()
                with counters_lock:
                    counters[result["outcome"]] = counters.get(result["outcome"], 0) + 1
            except Exception as e:
                log.exception(f"worker raised: {e}")
                with counters_lock:
                    counters["failed"] += 1

            # Refill
            fut = submit_one(ex)
            if fut is not None:
                in_flight.add(fut)

    elapsed = time.time() - started_run
    log.info("=" * 70)
    log.info(f"loop_corpus finished in {elapsed/60:.1f} min")
    log.info(f"  dispatched     : {counters['dispatched']}")
    log.info(f"  complete       : {counters['complete']}")
    log.info(f"  prefiltered    : {counters['prefiltered']}     (Sonnet bypassed)")
    log.info(f"  prefilter_keep : {counters['prefilter_keep']}  (full pipeline owes work)")
    log.info(f"  retried        : {counters['retry']}  (transient — released back to pending)")
    log.info(f"  failed         : {counters['failed']}")
    if counters["released"]:
        log.info(f"  released       : {counters['released']}  (legacy outcome — should be 0)")
    log.info("=" * 70)
    return 0 if counters["failed"] == 0 else 1


# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------
def _sigint(sig, frame):
    if _STOP.is_set():
        log.warning("Second Ctrl+C — exiting hard")
        sys.exit(130)
    log.warning("SIGINT received — finishing in-flight workers, no new docs will be claimed. "
                "Press Ctrl+C again to exit immediately.")
    _STOP.set()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                   help=f"parallel docs in flight (default {DEFAULT_WORKERS})")
    p.add_argument("--max-docs", type=int, default=None,
                   help="cap total docs processed this run")
    p.add_argument("--tier", type=int, choices=[1, 2, 3], default=None,
                   help="restrict to a single tier")
    p.add_argument("--no-prefilter", action="store_true",
                   help="skip the Haiku pre-filter; always run full pipeline")
    p.add_argument("--prefilter-only", action="store_true",
                   help="prefilter pass only — bypass + release; no extraction. "
                        "Cheap (~70 min for 4k docs at N=5) cost-prediction phase.")
    p.add_argument("--confidence-threshold", type=float,
                   default=DEFAULT_CONFIDENCE_THRESHOLD,
                   help=f"prefilter bypass threshold (default {DEFAULT_CONFIDENCE_THRESHOLD})")
    args = p.parse_args()
    if args.prefilter_only and args.no_prefilter:
        p.error("--prefilter-only and --no-prefilter are mutually exclusive")

    signal.signal(signal.SIGINT, _sigint)
    return driver(args)


if __name__ == "__main__":
    sys.exit(main())
