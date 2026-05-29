# Agentic Extraction Subsystem

Self-contained pipeline for the **citation-extraction corpus run**: 4,461 climate-litigation
decisions processed end-to-end via a Haiku pre-filter → Sonnet extractor → Sonnet verifier
chain, dispatched by a Python orchestrator, persisted to PostgreSQL `citation_agent_v1*`
tables, and exported to Excel.

This folder consolidates everything the corpus run touches. Files outside this folder that
the pipeline depends on are listed in **External dependencies** below.

---

## Layout

```
agentic-extraction/
├── README.md                         # this file
├── agents/                           # Windows directory junction → ../.claude/agents
│   ├── citation-prefilter.md         # Haiku binary classifier (cost gate)
│   ├── citation-extractor.md         # Sonnet, max-recall extraction
│   └── citation-verifier.md          # Sonnet, max-precision verification
├── loop_corpus.py                    # Python orchestrator (main entrypoint, N-parallel)
├── orchestrator_helper.py            # DB-side helpers: prepare/ingest/mark_*/status
├── chunk_large_docs.py               # Tier-3 pre-chunker (>100K-word docs)
├── merge_chunk_results.py            # Tier-3 result merger
├── export_agentic_to_excel.py        # Export the citation_agent_v1* tables to .xlsx
├── migrations/
│   ├── 001_run_state.sql             # Initial run-state table
│   ├── 002_schema.sql                # citation_agent_v1 + summary tables
│   └── 003_add_prefilter.sql         # 'prefiltered' status + audit columns
└── docs/
    ├── architecture-plan.md          # Original orchestrator design (corpus-orchestrator-plan)
    ├── per-doc-agent-template.md     # Reference template for per-doc agent prompts
    └── citation-extraction-rules.md  # Master rules document (D29–D38 consolidated)
```

### About the `agents/` junction

Claude Code's agent discovery only reads two paths: project `.claude/agents/` and user
`~/.claude/agents/`. There is no flag to point it elsewhere. To keep the canonical files
inside this folder while still letting Claude Code find them, `agents/` is a Windows
**directory junction** (`mklink /J`) pointing at `../.claude/agents`. The two paths name
the same files — edit either, both reflect the change.

If the junction is ever broken (e.g., after a `git clone` on a fresh machine), recreate it:

```powershell
cmd /c mklink /J agentic-extraction\agents .claude\agents
```

---

## Run the pipeline

```bash
# Status snapshot (what's pending / complete / prefiltered / failed)
python agentic-extraction/orchestrator_helper.py status

# Process pending docs, default N=5 parallel, prefilter on, threshold=0.9
python agentic-extraction/loop_corpus.py

# Common variants
python agentic-extraction/loop_corpus.py --max-docs 50            # cap this run
python agentic-extraction/loop_corpus.py --tier 1                 # tier-1 only
python agentic-extraction/loop_corpus.py --workers 3              # gentler on rate cap
python agentic-extraction/loop_corpus.py --no-prefilter           # full pipeline always
python agentic-extraction/loop_corpus.py --confidence-threshold 0.95  # raise bypass bar

# Tier-3 pre-chunking (only needed for >100K-word docs)
python agentic-extraction/chunk_large_docs.py <document_id>
python agentic-extraction/chunk_large_docs.py --all-tier3

# Tier-3 result merge (after the per-chunk extractions land)
python agentic-extraction/merge_chunk_results.py <document_id>

# Export the citation_agent_v1* tables to Excel
python agentic-extraction/export_agentic_to_excel.py
```

Stop the loop with Ctrl+C — in-flight workers finish their current step, no new docs are
claimed. Restart picks up where it left off (DB is the source of truth).

---

## Pipeline shape

```
  ┌──────────────────────────────────────────────────────┐
  │  loop_corpus.py  (Python, ThreadPoolExecutor N=5)    │
  └──────────────────────────────────────────────────────┘
           │ claim next pending (FOR UPDATE SKIP LOCKED)
           ▼
  ┌──────────────────────────────────────────────────────┐
  │  citation-prefilter  (Haiku, Read-only)              │
  │     returns {has_citations, confidence, signals[]}   │
  └──────────────────────────────────────────────────────┘
           │
   ┌───────┴───────┐
   │ has=false     │ otherwise
   │ conf ≥ 0.9    │
   ▼               ▼
 prefiltered      ┌──────────────────────────────────────┐
 (DB)             │  citation-extractor  (Sonnet)        │
                  │  → data/extraction_results/<id>_extracted.json │
                  └──────────────────────────────────────┘
                        │
                        ▼
                  ┌──────────────────────────────────────┐
                  │  citation-verifier  (Sonnet)         │
                  │  → data/extraction_results/<id>_verified.json │
                  └──────────────────────────────────────┘
                        │
                        ▼
                  orchestrator_helper.py ingest
                        │
                        ▼
                  citation_agent_v1, citation_agent_v1_summary,
                  citation_agent_v1_run_state.status='complete'
```

---

## Run state machine

`citation_agent_v1_run_state.status` values:

| Status        | Meaning                                                                     |
|---------------|-----------------------------------------------------------------------------|
| `pending`     | Awaiting processing                                                         |
| `in_progress` | Claimed by a worker; reset to `pending` at startup if a prior run was killed |
| `complete`    | Verifier output ingested into `citation_agent_v1`                           |
| `prefiltered` | Haiku said no-citations with conf ≥ 0.9 — bypassed the full pipeline        |
| `failed`      | Hit `attempts >= 3` or a fatal extractor/verifier error                     |
| `skipped`     | Manually excluded (operator action)                                         |

Pre-filter audit columns (only populated when `status='prefiltered'`):

- `prefilter_reason` — one-sentence justification from Haiku
- `prefilter_confidence` — float in `[0, 1]`
- `prefilter_signals` — JSONB array of signal slugs the model flagged

---

## External dependencies

These live outside `agentic-extraction/` and are *not* moved:

| Path                              | Why it's external                                            |
|-----------------------------------|--------------------------------------------------------------|
| `scripts/gcp_secrets.py`          | Secret Manager helper; the agentic pipeline imports `get_db_config` directly (bypasses `scripts/config.py` to avoid its eager Gemini-key fetch — agentic uses Claude only). |
| `scripts/export_to_excel.py`      | The general exporter; `export_agentic_to_excel.py` reuses its `_clean_df_for_excel` helper |
| `data/decisions_md/`              | Source corpus (Markdown decisions); read-only input          |
| `data/extraction_results/`        | Pipeline outputs land here (per-doc JSON files)              |
| `data/decisions_md_chunks/`       | Tier-3 pre-chunked outputs                                   |
| `logs/`                           | Run logs                                                     |
| `documents`, `cases`, `extracted_text` (DB tables) | Source-of-truth read inputs; shared with other pipelines |

`loop_corpus.py` adds `<project>/scripts` to `sys.path` so `from gcp_secrets import get_db_config`
keeps working from the new location.

---

## Migrations

Apply once per database (in order):

```bash
psql -U phdmutley -p 5433 -d climate_litigation -f agentic-extraction/migrations/001_run_state.sql
psql -U phdmutley -p 5433 -d climate_litigation -f agentic-extraction/migrations/002_schema.sql
psql -U phdmutley -p 5433 -d climate_litigation -f agentic-extraction/migrations/003_add_prefilter.sql
```

All three are idempotent (use `IF NOT EXISTS` / `DROP CONSTRAINT IF EXISTS`).

---

## Hand-off notes (May 2026)

- **Pre-filter signals** (`agents/citation-prefilter.md` §3): the positive/negative
  signal one-liners are the part the operator must hand-tune for this corpus. Until
  filled in, the prefilter will work but with weak signal-naming.
- **Validation gate**: before unleashing on the 4,083 pending docs, run the prefilter
  in shadow mode against the 58 already-complete docs. Zero false negatives required
  on docs known to contain ≥1 citation.
- **Sonnet flip**: extractor + verifier were on Opus until early May 2026. Cost was
  the trigger; quality on a small Sonnet pilot needs review before scaling.
