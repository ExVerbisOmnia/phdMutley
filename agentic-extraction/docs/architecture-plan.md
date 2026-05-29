# Corpus-Run Orchestrator — Design Plan

**Date:** 2026-05-03
**Status:** Plan, not yet implemented
**Cross-references:** D32 (tiered chunking), D37 (citation_agent_v1* tables), T7 (chunking scripts), T8 (agent rules), T10 (schema migration), `methodology-decisions-log.md`

---

## 1. Goal

Run the validated 2-agent citation-extraction pipeline (citation-extractor → citation-verifier) over **all 4,724 documents** in `data/decisions_md/`, ingesting verified outputs into the new `citation_agent_v1*` tables. The corpus run is the production execution that produces the dataset Lucas analyzes for the thesis.

## 2. Constraints

| Constraint | Implication for the design |
|---|---|
| **Token quota is finite** (Claude Max subscription, shared across the parent session and any sub-agents it spawns) | Must support graceful interruption + resume from a fresh session |
| **A document interrupted mid-extraction must be re-run from scratch** (Gus's requirement, 2026-05-03) | Idempotent write semantics: DELETE any partial rows before INSERTing new ones |
| **Conversation context window is finite** (~1M tokens) | Sub-agent transcripts must NOT bloat the parent session — use background agents with brief return summaries; persist all real state in the DB |
| **Tier-aware processing** (D32) | Three execution paths: Tier 1 single-pass / Tier 2 progressive-file / Tier 3 pre-split + parallel + merge |
| **No duplicate writes if interrupted between extract and verify or between verify and ingest** | Single transactional ingest per doc; intermediate JSON files are durable on disk |
| **Read access to existing `cases`, `documents`, `extracted_text`** + write access to new `citation_agent_v1*` tables only | v7 tables are FROZEN per D37 — never touched by the orchestrator |
| **Reproducibility for thesis defense** | All runs are logged with tier, doc_id, timestamps, tokens used, citation counts; logs are durable, queryable post-hoc |

## 3. Architecture

Two layers, with the DB as the single source of truth for run state:

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Layer A — Orchestrator session (Claude Code, foreground)                │
│                                                                         │
│  for each pending doc (read from citation_agent_v1_run_state):          │
│      classify tier (1/2/3)                                              │
│      spawn background sub-agent with the per-doc prompt                 │
│      receive brief summary on completion                                │
│      update run_state row                                               │
│                                                                         │
│  on token-near-quota or context-near-limit: stop gracefully,            │
│  state in DB tells the next session where to resume.                    │
└─────────────────────────────────────────────────────────────────────────┘
           │                      ▲
           ▼                      │
┌─────────────────────────────────────────────────────────────────────────┐
│ Layer B — Per-document sub-agent (general-purpose, background)          │
│                                                                         │
│  Receives: { document_id, tier }                                        │
│  Steps:                                                                 │
│    1. Cleanup prior partial state                                       │
│         DELETE FROM citation_agent_v1 WHERE document_id = ...           │
│         DELETE FROM citation_agent_v1_summary WHERE document_id = ...   │
│    2. Run extractor protocol (per .claude/agents/citation-extractor.md) │
│         - Tier 1: read whole file, extract, output JSON                 │
│         - Tier 2: progressive Read(offset, limit) chunks; partial JSON  │
│         - Tier 3: assume chunks already split; receives chunk paths,    │
│                   processes each chunk, then calls merge_chunk_results  │
│    3. Save extractor JSON to data/extraction_results/{doc_id}_extract.json │
│    4. Run verifier protocol                                             │
│    5. Save verifier JSON to data/extraction_results/{doc_id}_verified.json │
│    6. Ingest verifier JSON into citation_agent_v1 + summary             │
│         (single transaction)                                            │
│    7. Mark doc complete in run_state                                    │
│  Returns: { document_id, status, citations_count, duration_s,           │
│             tokens_used (if available), notes }                         │
│                                                                         │
│  On any exception: re-raise. Layer A handles; the run_state row stays   │
│  in_progress so the next session sees it as needing re-run.             │
└─────────────────────────────────────────────────────────────────────────┘
```

Why background agents (`run_in_background: true`)?

- The agent's full transcript stays out of the parent session's context window
- The parent only receives a short summary on completion
- Multiple sub-agents can run in parallel (orchestrator can dispatch up to N at a time)

Why a Python script — i.e., do we need one? **No.** The orchestrator is a Claude Code session that drives a loop of `Agent` tool calls. The "script" is the prompt the orchestrator follows. A separate Python orchestrator (Layer A reimplemented in Python calling the Anthropic API directly) is a possible future migration if Max-subscription quotas become limiting; the design below stays usable in that future too because all state is in the DB.

## 4. State Model — `citation_agent_v1_run_state`

A new tracking table in the same DB (`climate_litigation`). Migration appended to the T10 file (or a sibling file).

```sql
CREATE TABLE IF NOT EXISTS citation_agent_v1_run_state (
    document_id           UUID            PRIMARY KEY,
    status                VARCHAR(20)     NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending', 'in_progress',
                                            'complete', 'failed', 'skipped')),
    tier                  SMALLINT,                    -- 1, 2, or 3
    word_count            INTEGER,                     -- copied from extracted_text for query convenience
    attempts              SMALLINT        NOT NULL DEFAULT 0,
    last_attempt_started  TIMESTAMP,
    last_attempt_finished TIMESTAMP,
    extract_path          TEXT,           -- data/extraction_results/{doc_id}_extracted.json
    verify_path           TEXT,           -- data/extraction_results/{doc_id}_verified.json
    citations_extracted   INTEGER,
    citations_verified    INTEGER,
    citations_dismissed   INTEGER,        -- D31 soft-tag count
    citations_vertical    INTEGER,        -- D30 boolean=true count
    error_message         TEXT,           -- last error if failed
    notes                 TEXT,           -- agent's summary, observations
    created_at            TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMP       NOT NULL DEFAULT NOW(),

    FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_run_state_status ON citation_agent_v1_run_state(status);
CREATE INDEX IF NOT EXISTS idx_run_state_tier   ON citation_agent_v1_run_state(tier);
```

### State transitions

```
       seed                   pick up                   success
pending  ─────────► in_progress ──────► complete
   ▲                     │
   │                     │ failure / interruption
   │                     ▼
   └──── reset ──── failed   (or stays in_progress if killed mid-run)
```

- **`pending`** — seeded, never attempted
- **`in_progress`** — currently being processed (or was, when the previous session died)
- **`complete`** — extracted + verified + ingested successfully
- **`failed`** — terminal error after N attempts (default: 3)
- **`skipped`** — explicitly excluded (e.g., known-garbled doc)

### On orchestrator startup

```sql
-- Cleanup any in_progress rows from a previous interrupted session.
-- Per Gus 2026-05-03: an interrupted doc must be re-run from scratch,
-- overriding any partial entries.
UPDATE citation_agent_v1_run_state
SET status = 'pending', error_message = 'reset from in_progress on resume'
WHERE status = 'in_progress';

-- Cleanup partial DB writes for those docs (idempotency)
DELETE FROM citation_agent_v1
WHERE document_id IN (SELECT document_id FROM citation_agent_v1_run_state
                      WHERE status = 'pending' AND error_message LIKE 'reset from%');
DELETE FROM citation_agent_v1_summary WHERE document_id IN (...);
```

This guarantees Gus's requirement: **a doc that was mid-run gets re-run from scratch on restart.**

### Seeding

```sql
INSERT INTO citation_agent_v1_run_state (document_id, status, tier, word_count)
SELECT
    d.document_id,
    'pending',
    CASE
        WHEN et.word_count <= 25000 THEN 1   -- ~500 lines
        WHEN et.word_count <= 100000 THEN 2  -- ~2000 lines
        ELSE 3
    END AS tier,
    et.word_count
FROM documents d
JOIN extracted_text et ON et.document_id = d.document_id
WHERE et.raw_text IS NOT NULL
  AND d.is_decision = TRUE
  AND COALESCE(d.is_garbled, FALSE) = FALSE
ON CONFLICT (document_id) DO NOTHING;
```

## 5. Per-Document Flow (Tier-Aware)

Layer B's responsibilities, in order. **Every step must be safely re-runnable from scratch on the same doc.**

### Step 1 — Cleanup (idempotency)

```sql
BEGIN;
DELETE FROM citation_agent_v1_summary WHERE document_id = :doc_id;
DELETE FROM citation_agent_v1         WHERE document_id = :doc_id;
COMMIT;
```

### Step 2 — Mark in_progress

```sql
UPDATE citation_agent_v1_run_state
SET status = 'in_progress',
    attempts = attempts + 1,
    last_attempt_started = NOW(),
    error_message = NULL
WHERE document_id = :doc_id;
```

### Step 3 — Extract (tier-specific)

| Tier | Action |
|---|---|
| **1** | Read `data/decisions_md/{doc_id}.md`, run extractor, write JSON to `data/extraction_results/{doc_id}_extracted.json` |
| **2** | Read in 300-line chunks via `Read(offset, limit)`, append per-chunk citations to `data/extraction_results/{doc_id}_partial.json`, dedupe at end, write final JSON to `data/extraction_results/{doc_id}_extracted.json`. The partial JSON is the persistent memory between chunks. |
| **3** | (a) Verify chunks exist at `data/decisions_md_chunks/{doc_id}/chunk_*.md` (run `chunk_large_docs.py` if not). (b) For each chunk, run extractor, save to `data/extraction_results/chunks/{doc_id}/chunk_{n:02d}_extracted.json`. (c) Run `merge_chunk_results.py {doc_id}` to produce `data/extraction_results/{doc_id}_extracted.json`. |

Tier 3 chunk-level extractions can be parallelized within the per-doc agent (multiple sub-sub-agents) but for the v1 orchestrator we'll do them sequentially to keep the design simple. Parallelization is an optimization for later.

### Step 4 — Verify

Run citation-verifier on the extractor's JSON output. Write to `data/extraction_results/{doc_id}_verified.json`.

### Step 5 — Ingest

Single transaction: INSERT N citation rows into `citation_agent_v1`, INSERT 1 summary row into `citation_agent_v1_summary`. Use the verifier's JSON 1:1 mapping (per T10 schema design).

```sql
BEGIN;
INSERT INTO citation_agent_v1 (...) VALUES (...), (...), ...;  -- batch insert
INSERT INTO citation_agent_v1_summary (...) VALUES (...);
UPDATE citation_agent_v1_run_state
SET status = 'complete',
    last_attempt_finished = NOW(),
    citations_extracted = :extracted_count,
    citations_verified = :verified_count,
    citations_dismissed = :dismissed_count,
    citations_vertical = :vertical_count,
    extract_path = :extract_path,
    verify_path  = :verify_path,
    notes = :notes
WHERE document_id = :doc_id;
COMMIT;
```

### Step 6 — Return summary

The sub-agent returns to the orchestrator:

```json
{
  "document_id": "uuid",
  "status": "complete" | "failed",
  "tier": 1 | 2 | 3,
  "duration_seconds": 123,
  "citations_extracted": 17,
  "citations_verified": 17,
  "citations_dismissed": 1,
  "citations_vertical": 5,
  "notes": "brief observations or warnings",
  "error_message": null  // populated on failure
}
```

## 6. Resumability (the critical piece)

Three independent guarantees, each handling a different failure mode:

| Failure mode | What's persisted | What's lost | How resume works |
|---|---|---|---|
| **Orchestrator session killed mid-doc** (token quota, manual interrupt, crash) | Run-state row (status=`in_progress`), partial DB rows in `citation_agent_v1` if ingest started | The doc's extraction JSON might be on disk but invalidated | New session: reset `in_progress` → `pending`, DELETE partial rows, re-run from scratch |
| **Sub-agent crashes during extraction** | Run-state status=`in_progress`, possibly a `_partial.json` (Tier 2) on disk | The `_partial.json` is invalidated (the orchestrator's idempotency cleanup also wipes it) | Same as above |
| **Ingest transaction fails** (constraint violation, etc.) | Run-state, no partial DB rows (transaction rolled back) | The extraction + verification JSONs ARE on disk and valid | Increment attempts; orchestrator can retry ingest only without re-extracting (optimization for later) |

For v1, we keep things simple: **any non-`complete` doc is re-run from scratch on resume.** That's Gus's requested semantics and avoids subtle bugs around partial state.

### What doesn't get re-run

- Docs in status `complete` are skipped on every subsequent run
- Docs in status `failed` with `attempts >= 3` are skipped (manual review needed)
- Docs in status `skipped` are explicitly excluded by the user

### Manual override hooks

```sql
-- Force re-run of a specific doc
UPDATE citation_agent_v1_run_state SET status='pending', attempts=0
WHERE document_id = :doc_id;
DELETE FROM citation_agent_v1 WHERE document_id = :doc_id;
DELETE FROM citation_agent_v1_summary WHERE document_id = :doc_id;

-- Mark failed-and-investigated docs to skip
UPDATE citation_agent_v1_run_state SET status='skipped', notes='reason'
WHERE document_id = :doc_id;

-- Reset all failed docs for another attempt (after a code fix)
UPDATE citation_agent_v1_run_state SET status='pending', attempts=0, error_message=NULL
WHERE status='failed';
```

## 7. Logging

Structured logging across two surfaces:

### Per-doc (in run-state row)

- `last_attempt_started`, `last_attempt_finished`, `attempts`, `error_message`, `notes`, citation counts. Queryable for progress dashboards.

### Per-run (in `logs/corpus_run_{timestamp}.log`)

```
2026-05-04 09:15:01 [INFO] ============================================================
2026-05-04 09:15:01 [INFO] CORPUS-RUN ORCHESTRATOR — starting session
2026-05-04 09:15:01 [INFO] ============================================================
2026-05-04 09:15:01 [INFO] Reset 3 in_progress rows to pending (cleanup from previous session)
2026-05-04 09:15:01 [INFO] Pending docs: 1,247 (Tier 1: 1,180, Tier 2: 60, Tier 3: 7)
2026-05-04 09:15:01 [INFO] Already complete: 3,477  Failed: 0  Skipped: 0
2026-05-04 09:15:01 [INFO] ------------------------------------------------------------
2026-05-04 09:15:01 [INFO] [Tier 1][1/1247] doc 7b99bf45 (12,879 words) → spawning agent
2026-05-04 09:15:14 [INFO] [Tier 1][1/1247] doc 7b99bf45 ✓ complete (13s, 6 verified, 5 vertical, 0 dismissed)
2026-05-04 09:15:14 [INFO] [Tier 1][2/1247] doc 4da6a9cf (19,538 words) → spawning agent
...
2026-05-04 11:42:33 [WARN] [Tier 2][847/1247] doc xyz123 ⚠ failed (attempt 2/3): JSON parse error in verifier output
2026-05-04 11:42:33 [INFO]   marked failed; will retry up to 3x. Continuing.
...
2026-05-04 14:55:18 [INFO] Token quota near limit (estimated 92% used). Stopping gracefully.
2026-05-04 14:55:18 [INFO] Session summary: 1,089 docs processed in 5h40m. 1,072 complete, 17 failed.
2026-05-04 14:55:18 [INFO] To resume: re-invoke the orchestrator. State is in DB.
```

Section separators per project convention. ✓ for success, ⚠ for warnings, ✗ for errors.

### Progress dashboard (cheap SQL)

```sql
SELECT
    status,
    tier,
    COUNT(*) AS docs,
    SUM(citations_verified) AS total_citations,
    SUM(citations_vertical) AS total_vertical_dialogue,
    AVG(EXTRACT(EPOCH FROM (last_attempt_finished - last_attempt_started))) AS avg_seconds_per_doc
FROM citation_agent_v1_run_state
GROUP BY status, tier
ORDER BY status, tier;
```

Run periodically during the corpus run to monitor health.

## 8. Idempotency Guarantees

| Operation | How it stays idempotent |
|---|---|
| Re-running a doc that's currently `complete` | Skipped — orchestrator only picks up non-`complete` rows |
| Re-running a doc after partial DB write | Cleanup step (DELETE WHERE document_id) before INSERT |
| Reading a doc that's already chunked (Tier 3) | `chunk_large_docs.py` is idempotent (overwrites). Chunks dir gets re-built on each attempt for that doc |
| Restarting the orchestrator session | `UPDATE in_progress → pending` + cleanup deletes |
| Concurrent orchestrator runs (NOT recommended) | Use `SELECT ... FOR UPDATE SKIP LOCKED` to claim rows; v1 is single-orchestrator only — concurrency is a future feature |

## 9. CLI / Invocation Patterns

The orchestrator is a Claude Code session that follows an orchestration prompt. Invocation patterns:

### A. Manual orchestration (during this development session)

User says: "run the corpus extraction" → I read the orchestration prompt + run the loop in foreground, dispatching background agents as I go. I stop gracefully if I detect quota pressure.

### B. Auto-resume (for long runs)

User starts a fresh session and says: "resume corpus extraction" → I check the run-state, log the snapshot, and continue.

### C. Targeted re-runs

User says: "re-run failed docs" or "re-run docs with citations_dismissed > 0" → I form the appropriate `WHERE` clause and dispatch.

### D. Tier-only runs

For initial validation: "run all Tier 1 docs only" → orchestrator filters by `tier=1`.

### E. Dry-run

`SELECT` only, no agent spawns, no DB writes. Useful to verify the queue + the state cleanup logic before committing to a run.

These are all driven by orchestration prompts the orchestrator session reads, NOT a CLI flag system. We may formalize them as `scripts/orchestrate_corpus_run.py` (Python wrapping Anthropic SDK) later if Max-quota becomes the bottleneck.

## 10. Error Handling

| Error class | Action |
|---|---|
| **Per-doc transient** (network blip, single API call timeout) | Sub-agent retries internally up to 2× before giving up. Marked failed; orchestrator continues. |
| **Per-doc terminal** (JSON parse error, doc fundamentally broken) | Marked failed with error_message. Orchestrator continues. |
| **Quota near limit** (orchestrator detects from response metadata or pre-quota tracker) | Graceful shutdown. Current doc finishes if mid-flight; no new docs spawn. Exit. |
| **Hard quota exceeded** (mid-doc 429) | Sub-agent fails. Doc stays in_progress. Orchestrator catches; marks doc failed; no further docs spawn; exit. |
| **DB unreachable** | Hard fail. Orchestrator exits without further attempts. State on disk (extraction JSON files) is preserved; ingest can be retried later. |
| **Repeated failures on the same doc** (3 attempts) | Mark failed permanently. Surfaced in the failed-doc report for manual review. |

## 11. Implementation — Phased

### Phase 1 — Schema + run-state seeding (~30 min)

1. Apply T10 migration to local DB
2. Append run-state DDL to T10 migration (or sibling file); apply
3. Run the seeding query — verify 4,724 rows in `pending`
4. Verify tier distribution matches Section 4 of `agent-test-run-open-issues.md` (~93% Tier 1, ~6% Tier 2, ~1% Tier 3)

### Phase 2 — Per-doc agent prompt (~1 hour)

Write the per-doc agent prompt that Layer B follows. Test on 1 doc end-to-end (extract + verify + ingest). Verify:
- Cleanup deletes prior rows
- Idempotency: running twice on the same doc produces identical state
- DB row counts match verifier JSON
- Run-state transitions correctly (pending → in_progress → complete)

### Phase 3 — Orchestrator prompt (~1 hour)

Write the orchestrator prompt that Layer A follows. Test on 5 docs (mix of Tier 1 + Tier 2). Verify:
- Sequential dispatch works
- Run-state cleanup on startup
- Brief summaries returned to orchestrator
- Logging output

### Phase 4 — Tier 3 path validation (~30 min)

Run on the smallest Tier 3 doc end-to-end. Verify:
- Chunks generated correctly
- Per-chunk extractions
- Merge produces expected dedup
- Verifier processes the merged output normally

### Phase 5 — Full corpus run

Pre-flight checklist:
- [ ] All Phase 1–4 phases passed
- [ ] DB backup taken (`pg_dump`)
- [ ] Run-state shows expected counts
- [ ] Quota baseline checked (% used at start)

Then start. Monitor progress via SQL dashboard. Expected duration: **15–25 hours of agent time** if processed serially (per the agent's earlier estimate). With cautious parallelism (5 docs at a time), 3–5 hours.

### Phase 6 — Failed-doc review (~depends on count)

After the corpus run, query for failed docs. Manually inspect each. Either fix and re-run, or mark `skipped` with a note.

## 12. Open Questions for Gus

These are decisions the orchestrator design depends on. None block writing the prompt; all should be answered before Phase 5.

1. **Parallelism level.** The orchestrator can dispatch N background agents in flight at once. Higher N = faster total run, but more peaky quota usage. Recommend N=3 to start (matches our smoke-test pattern). What's the right number for production?

2. **Failed-doc retry policy.** Default: 3 attempts before marking permanently failed. Higher = more chance to recover transients but wastes effort on genuinely broken docs. Lower = faster fail. **Recommend: 2 for the corpus run** since extracting a single doc twice is cheap and a pattern of repeated failures usually indicates a real issue.

3. **Ingest target — direct DB or staging area first?** Two options:
   - *Direct* (current plan): every doc's verifier JSON is INSERTed into `citation_agent_v1*` immediately on completion
   - *Staged*: collect verifier JSONs in `data/extraction_results/` for the entire run, then bulk-load into the DB at the end. Pros: faster (one big COPY), atomic (all or nothing), easy to inspect before committing. Cons: longer feedback loop, more disk space, less progress visibility
   - **Recommend direct** — gives real-time progress visibility, makes resume cheap, doesn't block on the bulk-load step

4. **Quota-near-limit detection.** No clean Anthropic SDK signal for "you're at X% of monthly quota" today. Options:
   - *Manual* — user watches and asks me to stop when concerned
   - *Self-throttling* — orchestrator stops every 1,000 docs and asks the user to confirm continuation
   - *None — run until 429* — accept that one doc will fail with a quota error; that's how we learn we hit the wall
   - **Recommend: self-throttle every 500 docs** with a brief progress report and a "continue Y/N" prompt. Robust to absent-minded user; easy to disable.

5. **Where does the orchestration prompt live?** Two options:
   - As a `.md` file under `docs/plans/` that the user pastes when starting a session
   - As a slash command (`/run-corpus`) — requires Claude Code plugin setup
   - **Recommend: a markdown file (`agentic-extraction/docs/orchestrator-prompt.md`) for v1.** Slash command is a future improvement.

6. **Exclusion list for known-bad docs.** Aside from `is_garbled` (already filtered at seeding), are there docs you want to pre-exclude (e.g., the sibling Juliana docs with empty extracted_text)?

7. **Tier 3 sub-parallelism.** A Tier 3 doc has N chunks. Should the per-doc agent spawn parallel sub-agents for each chunk (faster per-doc, more agents in flight), or process them sequentially (simpler)?
   - **Recommend: sequential for v1.** Tier 3 is 47 docs total — even at sequential 30 min/doc, it's 24 hours. Optimize later.

---

## Summary of what changes after Gus reviews this plan

- Apply T10 schema migration + add run-state DDL
- Implement Phase 2 (per-doc agent prompt) and Phase 3 (orchestrator prompt) — write 2 markdown files
- Run Phase 4 validation on a Tier 3 doc
- Run Phase 5 full corpus extraction
- Review Phase 6 failed docs

Estimated dev time: **~3 hours** for the prompts + ~15-25 hours of agent runtime for the actual extraction.
