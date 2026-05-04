# Orchestrator Driver Prompt

This is the prompt the orchestrator session follows. Paste this into a fresh Claude Code session to begin (or resume) a corpus run.

The orchestrator drives the loop, dispatches per-doc sub-agents, and handles bookkeeping via `scripts/orchestrator_helper.py`. It does NOT do citation extraction itself — sub-agents do that, following `docs/plans/orchestrator-per-doc-agent.md`.

---

## Driver prompt (paste into a fresh session)

```markdown
You are the orchestrator for the phdMutley corpus run. Your job: drive the citation-extraction pipeline across ~4,461 pending documents, dispatching one sub-agent per document. State lives in Postgres (`citation_agent_v1_run_state`); you read from it to decide what to process and update it as work completes.

# Read first

1. `docs/plans/corpus-orchestrator-plan.md` — the architecture you're implementing
2. `docs/plans/orchestrator-per-doc-agent.md` — the prompt template you'll use for each per-doc agent
3. `scripts/orchestrator_helper.py` — the CLI helper for DB operations

# Operating mode

- Auto mode is on. Make reasonable defaults; minimize question-asking.
- Token budget is the parent session's monthly quota. If you near the limit, stop gracefully — the next session will resume.
- Three docs in flight simultaneously (parallelism N=3). Use `run_in_background: true` on Agent calls so transcripts stay out of your context.
- **Hard session cap: 20 docs OR 30 minutes wall-clock, whichever first.** Then stop gracefully. The wrapper loop spawns the next session with fresh context. Empirical finding (2026-05-03): per-doc orchestration burns ~10–15K parent-context tokens; 20 docs is a safe ceiling that keeps the parent session well under the 1M-token window.
- DO NOT self-throttle to ask the user — in unattended (`--print`) mode, there's nobody to answer. Just stop and exit; the loop wrapper handles continuation.

# Startup

1. Run `python scripts/orchestrator_helper.py startup` (resets any in_progress rows from previous interrupted sessions; cleans up partial DB writes).
2. Run `python scripts/orchestrator_helper.py status` to log the snapshot.
3. Open a log file: `logs/corpus_run_{ISO_TIMESTAMP}.log` (use the `Write` tool; append per-doc events to it as you go via `Edit`-with-append-mode using a clear "appendable" pattern, OR write to it with each batch).

# Main loop

Repeat until no more pending docs OR you've processed 500 since last self-throttle:

```
1. Get next batch of pending docs:
   python scripts/orchestrator_helper.py next --limit 3
   
2. For each doc in the batch (parallel via 3 background Agent calls):
   a. Run: python scripts/orchestrator_helper.py prepare <doc_id>
      → captures tier and word_count
   b. Spawn Agent (background, name="corpus-<doc_id_short>"):
      Use the per-doc template from orchestrator-per-doc-agent.md,
      substituting {document_id}, {tier}, {word_count}.
   
3. Wait for all 3 agents to complete (notifications come automatically).

4. For each completed agent's result:
   a. Parse the agent's return JSON
   b. If status == "complete":
      python scripts/orchestrator_helper.py ingest <doc_id> <verified_path>
   c. If status == "failed":
      python scripts/orchestrator_helper.py mark_failed <doc_id> "<error>"
   d. Append a one-line entry to the run log (timestamp, doc_id, tier, status, counts).

5. Every 500 completed docs (across this session):
   - Run: python scripts/orchestrator_helper.py status
   - Log the snapshot
   - Stop and prompt the user to continue
```

# Logging conventions

- Section separator: 70 `=` chars on a line by itself
- Section header: ALL CAPS title between separators
- Per-doc events: `YYYY-MM-DD HH:MM:SS [INFO] [Tier T][N/M] doc XXXXXX <verb> (<duration>s, <citations> citations)`
- Warnings: `[WARN] ⚠ ...`
- Errors: `[ERROR] ✗ ...`

Match the project pattern visible in `scripts/export_decisions_md.py` and `scripts/_t12_metadata_fix.py`.

# Error handling

- Per-doc agent failure (returned JSON with status="failed"): mark_failed, continue
- Per-doc agent JSON not parseable: mark_failed with the JSONDecodeError, continue
- DB error during ingest: caught by helper, helper marks failed and exits 1 — orchestrator logs and continues
- Helper unreachable / DB down: STOP. Hard fail. Log error and exit.
- Token quota near limit: STOP gracefully. Run final status. Print resume instructions.

# Tier-specific dispatch

Most docs are Tier 1 (4,139, ~93%). For Tier 3 docs, before spawning the per-doc agent:
- Verify the chunked .md files exist at `data/decisions_md_chunks/{doc_id}/`
- If they don't exist, run: `python scripts/chunk_large_docs.py {doc_id}` first

The per-doc agent template handles tier 1/2/3 differences internally.

# Stop conditions

You should STOP (gracefully) when ANY of these is true:
1. No more pending docs (corpus run complete!)
2. **20 docs completed in this session** (session cap — exit so the wrapper loop spawns a fresh session)
3. **30 minutes elapsed** in this session (wall-clock cap)
4. User says "stop" or "pause" (interactive mode only)
5. Token quota near limit (you'll feel it as response speed dropping or a 429-equivalent)
6. Unrecoverable DB error
7. Any pattern of repeated agent failures (≥ 3 consecutive failed dispatches) — sign of a code/data issue worth investigating before continuing

On stop:
- Run `python scripts/orchestrator_helper.py status` for final snapshot
- Log a closing block to `logs/corpus_run_*.log` summarizing the session (start time, end time, docs processed, complete count, failed count, citations total)
- Print resume instructions to user

# What you do NOT do

- DO NOT do citation extraction yourself — that's the sub-agent's job
- DO NOT touch the DB outside of helper.py invocations
- DO NOT commit to git
- DO NOT modify the agent definition files (`.claude/agents/*.md`) or the rules document during the run — those are frozen for the corpus run
- DO NOT process docs marked `complete`, `failed` (with attempts ≥ 2), or `skipped`

# Resume semantics

If the previous session was interrupted, the helper's `startup` command resets any `in_progress` docs to `pending` and deletes their partial DB rows. You can resume freely — just start the loop and the helper handles the rest.

# Begin

After reading the three required files above, run `startup`, then `status`, then begin the main loop.
```

---

## When to use this

- **First-ever corpus run**: paste the prompt into a fresh session. The helper's `startup` is a no-op; the seeded run-state has 4,461 pending rows ready.
- **Resume after interruption**: paste the same prompt into a fresh session. The helper's `startup` resets any `in_progress` rows from the dead session and cleans up partial DB writes; you continue from where you stopped.
- **Targeted re-run** (e.g., re-run all `failed` docs after a code fix): before pasting the prompt, manually run:
  ```bash
  psql ... -c "UPDATE citation_agent_v1_run_state SET status='pending', attempts=0 WHERE status='failed'"
  ```
  Then paste the prompt; the helper picks up the now-pending rows.
- **Tier-specific run** (e.g., do all Tier 3 first to get those out of the way): modify the helper's `next` call in the prompt to add `--tier 3`.

## Estimated runtime

Per the agent's earlier estimate: ~1 minute extraction + ~1.5 minutes verification per 5K words. With N=3 parallelism, expected wall-clock: **3–5 hours** for the full corpus.
