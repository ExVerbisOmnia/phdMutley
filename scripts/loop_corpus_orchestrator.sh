#!/usr/bin/env bash
# loop_corpus_orchestrator.sh
#
# Multi-session relay wrapper for the corpus-run orchestrator.
#
# Each iteration spawns a fresh `claude --print` process with the
# orchestrator-driver prompt piped to stdin. The fresh process gets a clean
# context window; it processes ~20 docs (per the session cap in
# docs/plans/orchestrator-driver.md), commits its progress to the
# citation_agent_v1_run_state table, and exits. The wrapper checks the
# pending count and either spawns the next session or stops.
#
# Usage:
#   bash scripts/loop_corpus_orchestrator.sh             # run until done
#   bash scripts/loop_corpus_orchestrator.sh --max-sessions 10
#   bash scripts/loop_corpus_orchestrator.sh --dry-run   # show what it would do, don't spawn
#
# Stop with Ctrl+C — current session will finish; loop won't spawn the next.
#
# Logs (per-iteration session output) are written to logs/corpus_loop_*.log.
# The DB run_state table is the source of truth for what's been processed.
#
# Requirements:
#   - claude CLI in PATH (Claude Code, with Max subscription auth)
#   - python in PATH; scripts/orchestrator_helper.py importable
#   - DB reachable (Postgres on :5433)

set -uo pipefail

# ---------------------------------------------------------------------------
# Args
# ---------------------------------------------------------------------------
MAX_SESSIONS=${MAX_SESSIONS:-1000}
DRY_RUN=false
SLEEP_BETWEEN=${SLEEP_BETWEEN:-15}      # seconds between sessions
SESSION_TIMEOUT=${SESSION_TIMEOUT:-2400} # 40-min hard cap per session (driver promises 30; we add slack)
PROMPT_FILE="docs/plans/orchestrator-driver.md"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --max-sessions) MAX_SESSIONS="$2"; shift 2 ;;
        --dry-run)      DRY_RUN=true; shift ;;
        --sleep)        SLEEP_BETWEEN="$2"; shift 2 ;;
        --timeout)      SESSION_TIMEOUT="$2"; shift 2 ;;
        --prompt)       PROMPT_FILE="$2"; shift 2 ;;
        *) echo "Unknown arg: $1" >&2; exit 2 ;;
    esac
done

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$PROJECT_ROOT"

LOG_DIR="logs"
mkdir -p "$LOG_DIR"
LOOP_LOG="$LOG_DIR/corpus_loop_$(date +%Y%m%d_%H%M%S).log"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log()      { echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO]  $*" | tee -a "$LOOP_LOG"; }
log_warn() { echo "$(date '+%Y-%m-%d %H:%M:%S') [WARN]  $*" | tee -a "$LOOP_LOG" >&2; }
log_err()  { echo "$(date '+%Y-%m-%d %H:%M:%S') [ERROR] $*" | tee -a "$LOOP_LOG" >&2; }

pending_count() {
    python -c "
import sys
sys.path.insert(0, 'scripts')
from config import DB_CONFIG
from sqlalchemy import create_engine, text
e = create_engine(f\"postgresql://{DB_CONFIG['username']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}\")
with e.connect() as c:
    n = c.execute(text(\"SELECT COUNT(*) FROM citation_agent_v1_run_state WHERE status='pending'\")).scalar()
print(n)
" 2>/dev/null
}

# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------
if [[ ! -f "$PROMPT_FILE" ]]; then
    log_err "Prompt file not found: $PROMPT_FILE"
    exit 1
fi

if ! command -v claude >/dev/null 2>&1; then
    log_err "claude CLI not on PATH. Aborting."
    exit 1
fi

log "============================================================"
log "Corpus-run loop wrapper starting"
log "  prompt:      $PROMPT_FILE"
log "  max sessions: $MAX_SESSIONS"
log "  per-session timeout: ${SESSION_TIMEOUT}s"
log "  sleep between: ${SLEEP_BETWEEN}s"
log "  loop log:    $LOOP_LOG"
log "============================================================"

initial_pending=$(pending_count)
if [[ -z "$initial_pending" ]]; then
    log_err "Could not query pending count from DB. Check Postgres on :5433."
    exit 1
fi
log "Initial pending docs: $initial_pending"

if [[ "$initial_pending" -eq 0 ]]; then
    log "Nothing pending — nothing to do."
    exit 0
fi

# ---------------------------------------------------------------------------
# Loop
# ---------------------------------------------------------------------------
session_idx=0
docs_at_start_of_loop="$initial_pending"

while [[ $session_idx -lt $MAX_SESSIONS ]]; do
    session_idx=$((session_idx + 1))
    pending="$(pending_count)"

    if [[ -z "$pending" ]]; then
        log_warn "Pending count query returned empty. Pausing 60s and retrying."
        sleep 60
        continue
    fi

    if [[ "$pending" -eq 0 ]]; then
        log "All pending docs processed. Loop complete."
        break
    fi

    delta=$((docs_at_start_of_loop - pending))
    log "------------------------------------------------------------"
    log "Session $session_idx — pending: $pending  (this loop: $delta processed since start)"

    if $DRY_RUN; then
        log "  [dry-run] would: cat $PROMPT_FILE | claude --print --dangerously-skip-permissions"
    else
        # Spawn one fresh Claude Code session, non-interactive
        # --dangerously-skip-permissions: no prompts (we trust the orchestrator's
        # actions; permissions are pre-allowlisted in .claude/settings.json)
        # timeout: hard cap per session
        session_log="$LOG_DIR/corpus_session_$(date +%Y%m%d_%H%M%S)_${session_idx}.log"
        log "  Session log: $session_log"

        timeout "$SESSION_TIMEOUT" claude --print --dangerously-skip-permissions \
            < "$PROMPT_FILE" \
            > "$session_log" 2>&1
        rc=$?

        if [[ $rc -eq 124 ]]; then
            log_warn "  Session timed out after ${SESSION_TIMEOUT}s (claude killed by 'timeout'). Continuing."
        elif [[ $rc -ne 0 ]]; then
            log_warn "  Session exit code $rc (non-zero). Tail of log:"
            tail -20 "$session_log" | sed 's/^/    /' | tee -a "$LOOP_LOG" >/dev/null
        else
            log "  Session $session_idx OK (exit 0)"
        fi
    fi

    log "  Sleeping ${SLEEP_BETWEEN}s before next session..."
    sleep "$SLEEP_BETWEEN"
done

# ---------------------------------------------------------------------------
# Final
# ---------------------------------------------------------------------------
final_pending=$(pending_count)
log "============================================================"
log "Loop wrapper finished"
log "  sessions run:        $session_idx"
log "  pending at start:    $initial_pending"
log "  pending at end:      $final_pending"
log "  docs processed:      $((initial_pending - final_pending))"
log "============================================================"

if [[ "$final_pending" -gt 0 ]]; then
    log_warn "Still $final_pending pending docs. Re-run this script to continue, or investigate why progress halted."
    exit 1
fi
exit 0
