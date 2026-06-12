# phdMutley — Citation Patterns in Transnational Climate Litigation

A research data-engineering pipeline that quantifies **North–South citation
asymmetry in transnational climate litigation** — end to end, from the
Columbia / Sabin Center corpus to a verified citation dataset and an interactive
public dashboard.

> **Companion site:** [climatecaselab.org](https://climatecaselab.org) ·
> **Technical dashboard:** GitHub Pages (`docs/index.html`)

---

## Abstract

When a court decides a climate case, whose prior rulings does it cite — and from
where? phdMutley is the pipeline behind a doctoral study of *transnational
judicial dialogue* in climate litigation. It ingests the Climate Case Chart
corpus (Columbia Law School / Sabin Center for Climate Change Law), uses large
language models to extract every case-to-case citation from judicial decisions,
verifies each citation against the source text, and classifies it along a
directional typology (national ↔ international, across the Global North/South).
The central question — whether climate jurisprudence circulates symmetrically
across jurisdictions or flows overwhelmingly in one direction — is answered
empirically; the headline finding (an overwhelming concentration of citations
originating in Global-North jurisdictions) is presented and quantified on the
[companion dashboard](https://climatecaselab.org).

This repository is the **technical pipeline and dataset**. The research is led by
**Lucas Biasetton** (PhD candidate, USP & LSE); the pipeline, database, cloud
execution, and dashboard were designed and built by **Gustavo Rodrigues** as
technical/methodological contributor.

---

## Status / current phase

**Active branch:** `feature/phase-dq` · **Current phase:** agentic re-extraction
(methodology pivot, May 2026).

Two pipelines coexist here, and which one is "the" pipeline depends on the question:

- **Canonical dataset — v2 (Gemini batch pipeline).** The 16,352-document corpus
  run completed in **March 2026** is the dataset behind the live dashboard and the
  headline numbers below. It is **frozen** as a methodological baseline.
- **Current as-built — v3 (agentic Claude pipeline).** Since May 2026 active
  development is `agentic-extraction/` — a worker-queue orchestrator running a
  **pre-filter → extractor → verifier** agent chain per document. It was a
  deliberate pivot to address a **recall** limitation in v2 (see *Pipeline runs*),
  and adds analytical dimensions v2 lacks. It is **in active validation, not yet
  the canonical dataset** — the decision on whether v3 supersedes v2 as the thesis
  dataset is open.

> This README privileges the **current as-built** (Linux, local PostgreSQL on
> port 5432, current-phase files). Some older in-repo guidance predates the
> current environment and may differ on incidental details (earlier Windows port,
> earlier corpus counts).

---

## Headline pipeline results *(v2 — the canonical, verified dataset)*

| Metric | Value |
|---|---|
| Documents processed (corpus) | **16,352** |
| Judicial decisions classified | **4,755** |
| Citations extracted & kept (post corpus-filter) | **13,824** |
| Citations **confirmed** on verification | **95.3%** |
| Out-of-corpus candidates discarded by the Sabin filter | ~197,866 |

The discipline is the point as much as the scale: a two-tier corpus filter and a
dedicated verification pass anchor every kept citation to a snippet in the source
text, so the dataset is *extract → filter-to-corpus → verify*, not *extract and
trust*. The full v2 corpus run was executed on a single GCP Spot VM with tiered
models, within a deliberately tight compute budget.

---

## Pipeline architecture

The pipeline is staged in **numbered directories** under `scripts/`; the numbering
encodes execution order.

```
 Sabin / Columbia corpus export (Excel)
        │
        ▼
 0-initialize-database   →  PostgreSQL schema (UUIDv7 PKs, Alembic migrations)
 1-download-decisions    →  corpus → PDF download (with fallbacks)
 2-populate-metadata     →  metadata → DB (cases, documents; Sabin IDs preserved)
 3-extract-texts         →  PDF → Markdown / raw text (multi-tier extraction fallback)
 4-classify-decisions    →  "is this a judicial decision?" (rule-based + LLM)
 5-extract-citations     →  anti-hallucination extraction (regex patterns + hard filters)
 6-verify-citations      →  verification pass + Sabin corpus filter
 7-queries               →  SQL analysis
 8-python_back_engine    →  analysis engine → network data + dashboard JSON
        │
        ▼
 docs/  →  static D3.js dashboard (GitHub Pages)
```

**Agentic alternative (`agentic-extraction/`, v3)** replaces stages 5–6 with a
per-document agent chain driven by a Python orchestrator (`loop_corpus.py`):

```
 loop_corpus.py  — claims next pending doc (SELECT … FOR UPDATE SKIP LOCKED)
   ├─ prefilter  (lightweight model) → skip clearly citation-free docs (cost gate)
   ├─ extractor  (max-recall)        → candidate citations
   └─ verifier   (max-precision)     → confirmed citations + source snippets
        │  idempotent ingest; run-state in the DB → interruptible & resumable
```

Documents are handled by **tier** (single-pass for short docs; progressive chunked
reads for long ones; pre-split + merge for very large decisions).

---

## ⭐ Pipeline runs — history & methodological evolution

The pipeline has been rebuilt three times in ~7 months. Each run is a distinct
dataset with its own methodology; the *differences between them* are part of the
methodological contribution.

### Run 1 — v1 (Anthropic, dynamic-hosted) · ~Oct–Nov 2025
- **Stack:** Anthropic Claude (single-model extraction); PostgreSQL; dashboard on a
  dynamic backend host.
- **Method:** single-model LLM extraction + directional classification, with a
  manual expert-review loop.
- **Corpus:** ~2,924 judicial decisions; first live dashboard.
- **Why it changed:** single-vendor cost ceiling, a dynamic-hosting bill, and a
  push for stronger reproducibility drove the v2 rebuild.

### Run 2 — v2 (Gemini batch pipeline) · production run **March 2026** → *canonical dataset*
- **Stack:** Google **Gemini 2.5** (Flash for extraction/verification, Pro for
  classification), `temperature = 0` throughout for reproducibility; native
  PostgreSQL; **GitHub Pages** static hosting; executed on a **GCP Spot VM**.
- **Method:** multi-phase **anti-hallucination** extraction (citation-format regex
  + hard filters), a **Sabin corpus filter** that keeps only citations matching a
  known case record, and a separate **verification phase** anchoring each citation
  to a source snippet. A later **Phase DQ** resolved data-quality issues and
  re-anchored snippet positions.
- **Corpus:** **16,352 documents → 4,755 decisions → 13,824 kept citations**, at a
  **95.3% confirmed** rate.
- **What changed vs. v1, and why:**
  - **Anthropic → Gemini** — cost ceiling; Flash/Pro tiering fit the budget.
  - **Dynamic host → GitHub Pages** — eliminate backend hosting cost (static export).
  - **Single-model → role-tiered models + `temperature = 0`** — reproducibility for
    academic defensibility.
  - **Added the corpus filter and an explicit verification phase** — moving from
    "extract and trust" to "extract, filter-to-corpus, then verify against source."

### Run 3 — v3 (agentic 2-agent Claude pipeline) · run window **May 2026** → *in validation*
- **Stack:** Anthropic Claude as **agents** (pre-filter + extractor + verifier)
  driven by a Python orchestrator, running under a fixed-cost subscription quota.
- **Method:** a **worker-queue / run-state-machine** orchestrator — `FOR UPDATE
  SKIP LOCKED` row claiming, concurrent workers, idempotent ingest, graceful
  interrupt/resume from DB state, tier-aware long-document handling. A lightweight
  **pre-filter** gates cost; a dedicated **extractor** maximizes recall; a dedicated
  **verifier** enforces precision.
- **What changed vs. v2, and why (the core synthesis):**
  - **Batch API → agentic worker-queue.** Per-document agents with file access can
    perform *progressive reads* of long decisions rather than a single
    context-window-bounded call.
  - **Single Gemini pass → prefilter / extractor / verifier separation** — one job
    per agent: cost gating, recall, precision.
  - **Gemini → Claude** — driven by extraction quality and fixed-cost quota economics.
  - **The decisive driver was *recall*.** Test runs showed v2 systematically missing
    citations in footnote-dense international decisions — exactly the CJEU/ECtHR
    documents where transnational dialogue concentrates (e.g. on one landmark case,
    the agent recovered ~100 citations where v2 had found ~9). Because the misses
    were systematic rather than random, re-classifying v2 output couldn't fix it; a
    fresh extraction was required. v2 is kept frozen as the "before" baseline so the
    recall gain can be *quantified*.
  - **New analytical dimensions** — a functional-use taxonomy (how the citing court
    *used* the precedent), opinion-type, and vertical-dialogue flagging, with the
    anti-hallucination safeguards retained and extended.

> Decision rationale lives in `docs/reports/methodology-decisions-log.md` and the
> tracked meeting reports under `docs/reports/`.

---

## Data sources

- **Origin:** the **Climate Change Litigation Databases** of the **Sabin Center for
  Climate Change Law (Columbia Law School)** — the *Climate Case Chart* corpus —
  exported and ingested into PostgreSQL.
- **Scale:** ~4,740 cases · 16,352 documents · 4,755 classified as judicial
  decisions.
- **Flow:** source export → downloaded PDFs → extracted Markdown/plain text →
  citation rows in PostgreSQL.

The underlying corpus is governed by the Sabin Center / Grantham database terms,
independent of this repository's own code/data licensing.

---

## Tech stack

Python · PostgreSQL (SQLAlchemy 2 + Alembic, UUIDv7 PKs) · Google Gemini 2.5
(v2) and Anthropic Claude agents (v3) · Google Cloud Platform (Spot VM compute,
Secret Manager for credentials) · D3.js v7 dashboard (static, GitHub Pages) ·
`ruff` / `pytest` / `pydantic-settings`.

---

## Repository layout

```
phdMutley/
├── scripts/                  # numbered pipeline stages 0–8 + shared modules
│   ├── config.py             # single source of truth (DB, models, mappings)
│   ├── gcp_secrets.py        # Secret Manager helper
│   └── sabin_filter.py       # corpus-membership citation filter
├── agentic-extraction/       # v3 agentic pipeline (current phase) + its docs/migrations
├── .claude/agents/           # prefilter / extractor / verifier agent definitions
├── docs/                     # GitHub Pages dashboard (index.html) + data/, reports/, tracker/
├── specs/                    # master plan, phase specs, schema analysis
├── data/                     # corpus: seed export, PDFs, extracted text (large dirs gitignored)
├── our_papers/               # draft paper + methodology section
└── phdmutley-PROJECT-HANDOVER.md   # full provenance-marked project handover
```

---

## Running the pipeline

Research tooling for a single operator; it assumes a local PostgreSQL and GCP
credentials. High level:

1. **Environment** — Python venv + `requirements.txt` (`requirements-dev.txt` for tooling).
2. **Secrets** — via **GCP Secret Manager** (preferred) or a local `.env` (see
   `.env.template`); never commit real keys.
3. **Database** — initialize the schema from `scripts/0-initialize-database/`, or
   restore a dump.
4. **v2 pipeline** — run the numbered stages `1 → 8` in order.
5. **v3 agentic pipeline** — apply `agentic-extraction/migrations/`, then run
   `agentic-extraction/loop_corpus.py` (resumable; check status via the orchestrator helper).
6. **Dashboard** — regenerate the static JSON and serve `docs/` locally.

---

## Companion site & dashboard

- **Public site:** **[climatecaselab.org](https://climatecaselab.org)** — a curated,
  non-technical companion (narrative, interactive citation-flow map, catalytic
  cases). Maintained as a self-contained subproject; Lucas Biasetton is the lead.
- **Technical dashboard:** `docs/index.html` — a single-file **D3.js** app served
  via **GitHub Pages**, reading static JSON regenerated from the analysis engine.

---

## Research output & citation

- **Paper:** *"Courts in Isolation: Citation Patterns in Climate Litigation and the
  Path Toward Structured Judicial Exchange"* — accepted by **Cambridge University
  Press**; technical/methodological contribution by Gustavo Rodrigues.
- **Institutional context:** doctoral research (USP) with **LSE / Grantham Research
  Institute** involvement; engagement with the Sabin Center.
- The dataset feeds the lead researcher's doctoral thesis (deposit expected later;
  no early framing lock-in by design).

> Please confirm the canonical citation form and author order with the research
> team before citing.

---

## Collaborators

- **Lucas Biasetton** — lead researcher (PhD candidate, USP & LSE): research
  questions, legal-domain methodology, citation-classification rules, companion site.
- **Gustavo Rodrigues** — technical/methodological contributor: extraction and
  verification pipelines (v1 → v3), database schema, GCP execution, technical
  dashboard, co-authored methodology.

With thanks to the **Sabin Center for Climate Change Law (Columbia)** for the
underlying corpus.

---

## License

No root `LICENSE` file is set yet for the pipeline. The public-site subproject
(`climatecaselab/`) carries **MIT** (code) and **CC BY 4.0** (content); a similar
split is a reasonable model for the root pipeline, to be decided explicitly by the
authors. The underlying corpus remains governed by the Sabin Center / Grantham
terms.
