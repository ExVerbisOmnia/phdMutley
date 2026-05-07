# Methodology Decisions Log

**Purpose:** A thesis-defensible audit trail of methodological decisions affecting the citation-extraction pipeline and dataset construction. Each entry records a *fork* — a choice point where alternatives existed, the option chosen, the rationale, and the downstream consequences.

**Convention:** Decisions are numbered sequentially (`D{n}`) and dated. Earlier decisions (D1–D28) live in conversation history and prior memory files; this log starts a permanent record from D29 (April 2026) onward as the agent-pipeline pivot triggered a cluster of methodological refinements that warranted a formal audit trail.

**How to use this log:**

- Reference decisions by D-number when citing in the thesis methodology section
- New decisions append at the bottom with the same template
- This file is the source of truth for "why we chose X over Y" — supersedes conversation summaries and chat logs on conflict
- Cross-references point to test reports, source files, and prior decision documents

---

## Session: 2026-04-09 → 2026-05-03 — Agent-Pipeline Pivot

This session pivoted the citation-extraction methodology from a 6-phase Gemini-API pipeline (v7) to a 2-agent Claude-Code-based approach due to deadline constraints (Lucas's research deliverable). The pivot surfaced and forced explicit decisions on issues that the v7 pipeline had silently absorbed (mis-classification of same-court citations, region miscoding for international courts, recall losses from markdown footnote truncation, source-database metadata misattribution). Every decision below either corrects a previously-implicit assumption or selects between two defensible methodological paths.

---

### D29 — Same-court self-citation = Domestic

| Field | Value |
|---|---|
| Date | 2026-04-09 |
| Decided by | Gus |
| Source issue | Issue 1.1, `docs/reports/agent-test-run-open-issues.md` |

**Context.** The v7 sixfold classifier tagged CJEU citations of prior CJEU rulings as "Inter-System Citation" (Type 4). Surfaced during Saint-Gobain and ExxonMobil test runs.

**Fork:**

- *Left (status quo)* — keep classifying same-court citations as Inter-System. Methodologically incoherent: an international court citing itself is not transnational dialogue.
- *Right (chosen)* — classify same-court citations as Domestic, exclude from transnational analysis.

**Rationale.** Citation-network analysis distinguishes intra-system flows from inter-system flows. CJEU→CJEU is intra-EU-court-system, structurally equivalent to US 9thCir→USSC (intra-national). The "transnational dialogue" research question requires excluding both.

**Scope.** Affects every CJEU, ECtHR, IACtHR, ACHPR document citing its own prior case law, plus all national documents citing higher courts within the same national jurisdiction. The v7 dataset has this systematically wrong on at least 21 citations across two test docs alone.

**Downstream.** Rule 7.1 added to `citation-verifier.md` and the rules document. v7 dataset (now frozen, see D37) preserves the original classification as a baseline.

**Amended by D38** (2026-05-03) — see below for the international/national split.

---

### D38 — Refinement of D29: same-body classification depends on whether the body is international or national

| Field | Value |
|---|---|
| Date | 2026-05-03 |
| Decided by | Gus |
| Source issue | T17 (Tier 3 validation surfaced the WTO AB → WTO Panel ambiguity) |

**Context.** D29 classified ALL same-court / same-system citations as Domestic. Tier 3 validation on the WTO DS-412 doc surfaced that this collapses every WTO Appellate Body → WTO Panel reference into Domestic, which conflicts with the research question — those citations are between international decisions, not within a national legal system. The same problem applies to CJEU AG opinion → CJEU judgment, ECtHR Grand Chamber → ECtHR Chamber, IACtHR Advisory → IACtHR Contentious, etc.

**Fork:**

- *Left (D29 as originally written)* — all same-system = Domestic. Symmetric across national and international, but loses all intra-international dialogue including hierarchical relationships within international courts.
- *Right (chosen)* — split by body type:
  - If the source and cited bodies belong to an **international** institution (CJEU, ECtHR, IACtHR, ACHPR, WTO DSU, ICJ, ITLOS, ICSID, etc.) → classify as **Inter-System Citation (Type 4)**, even if both are within the same dispute-settlement system.
  - If the source and cited bodies are **sub-bodies of the same national jurisdiction** (US 9thCir → USSC, German BVerfG → German lower courts, Brazilian STF → STJ, etc.) → classify as **Domestic**.

**Rationale.** Intra-international citations (e.g., WTO AB → Panel, CJEU → AG, ECtHR Grand Chamber → Chamber) are still part of *international judicial dialogue* and matter for the thesis's transnational-dialogue research question. They sit at a different scale from purely intra-national hierarchies (US Circuit → US Supreme Court), which are clearly out of scope. The distinction tracks the source's region:

- `source_region == "International"` AND `target_region == "International"` → Type 4 Inter-System (regardless of whether they're nominally the same DSU)
- `source_country == target_country` AND both national → Domestic (D29 as originally intended for the national branch)

**Examples:**

| Source | Cited | Old (D29) | New (D38) |
|---|---|---|---|
| CJEU | CJEU | Domestic | **Inter-System (Type 4)** |
| CJEU | General Court (EU) | Domestic | **Inter-System (Type 4)** |
| ECtHR Grand Chamber | ECtHR Chamber | Domestic | **Inter-System (Type 4)** |
| WTO Appellate Body | WTO Panel (different dispute) | (not specified) | **Inter-System (Type 4)** |
| WTO Appellate Body | WTO Panel (THIS dispute, under appeal) | (not specified) | **Inter-System (Type 4)** |
| IACtHR Advisory | IACtHR Contentious | Domestic | **Inter-System (Type 4)** |
| US 9thCir | US Supreme Court | Domestic | Domestic (unchanged) |
| German BVerfG | German lower court | Domestic | Domestic (unchanged) |
| Brazilian STF | Brazilian STJ | Domestic | Domestic (unchanged) |

**Scope.**

- v7 frozen baseline keeps the original classification (no retro-edits per D37).
- Agent-pipeline runs from 2026-05-03 onward apply D38.
- Saint-Gobain's already-ingested `citation_agent_v1` rows (15 Domestic CJEU→CJEU + 1 Type 5) are now wrong under D38 — re-extract rather than SQL-patch (per D37 fresh-extraction principle).
- Tier 3 DS-412 ingest (54 Type 4) is consistent with D38 — no re-run needed.
- Future Tier 1/2 docs from international courts will produce more Type 4 citations than under the original D29.

**Downstream.** Rule 7.0 in `citation-verifier.md` updated. The rules document's example tables updated. Saint-Gobain re-run scheduled before Phase 5.

---

### D30 — National→member international = Type 2 + `is_vertical_dialogue: true`

| Field | Value |
|---|---|
| Date | 2026-04-09 |
| Decided by | Gus |
| Source issue | Issue 1.2; Rule 7.2 in `docs/reports/agent-test-run-open-issues.md` |

**Context.** A national court citing an international court of which it is a member state (e.g., Germany→ECtHR, Colombia→IACtHR, Netherlands→CJEU, Australia→ICJ) is genuine vertical judicial dialogue and a distinct phenomenon from horizontal foreign-court citations or international-internal references. The sixfold scheme handles this as Type 2 (International Citation), but the membership relationship is implicit.

**Fork.** Two questions resolved:

1. *Should this be its own sixfold type?* — No. Type 2 captures it. Adding a seventh type would inflate the typology without analytic gain.
2. *How should it be filterable?* — Two options:
   - *Left* — implicit; downstream queries derive it via JOIN on a court-membership table.
   - *Right (chosen)* — explicit boolean `is_vertical_dialogue: bool` on every citation. Set `true` when source = national court AND cited = international court of which source-country is a member; `false` everywhere else.

**Rationale.** Adding the boolean costs zero per-citation but makes vertical-dialogue queries trivial and auditable. Implicit derivation requires every downstream consumer to maintain its own court-membership table — error-prone.

**Required tables.** ECtHR (46 Council of Europe members), IACtHR (20 OAS members that recognized the Court's jurisdiction), ACHPR (34 African Charter parties), CJEU (27 EU members), ICJ (universal — all UN members), ITLOS (168 UNCLOS parties — treat as universal).

**Downstream.** Output schema gains `is_vertical_dialogue` field. Court-membership tables canonical in the rules document, referenced from the verifier.

---

### D31 — Court engagement is the inclusion criterion (soft-tag encoding)

| Field | Value |
|---|---|
| Date (rule) | 2026-04-09 |
| Date (encoding) | 2026-05-03 |
| Decided by | Gus |
| Source issue | Issue 5.1; T6 |

**Context.** During the Leghari test run, two citations (Imrana Tiwana, Shehla Zia) appeared in two contexts: invoked by the petitioner's counsel (paragraph 3) and later aligned by the court (paragraph 22). The original draft rule was "court treatment > party invocation in case of conflict." Gus's correction was stronger.

**Fork (rule):**

- *Left* — include all citations regardless of court engagement (broadest dataset, but includes party-argument noise)
- *Middle (original draft)* — court treatment > party invocation when both apply; pure-invocation citations stay as `invoked`
- *Right (chosen)* — court engagement is the *inclusion* criterion. Citations only invoked by parties with mere court acknowledgement (the court summarizes a party's argument without endorsing or refuting the case) get tagged separately.

**Sub-fork (encoding):**

- *Encoding #1 (left)* — hard exclusion at extraction time. The extractor silently drops mere-acknowledgement citations. Cleaner dataset.
- *Encoding #2 (right, chosen)* — soft tagging with `functional_use: dismissed`. Default analysis filters them out, but the data is preserved.

**Rationale (rule).** In citation-network research, the citations that matter for the court's holding are those the court itself engaged with — aligns with the ratio decidendi vs. dictum distinction. Mere mentions in dictum or party-argument summaries are not load-bearing.

**Rationale (encoding).** Soft tagging preserves a measurable research signal: the gap between what parties cite and what courts engage with. In some jurisdictions and case-types this gap is itself a finding (e.g., "in IACtHR proceedings, parties invoke ECtHR jurisprudence in 80% of cases but the Court engages with it in 30%"). Hard exclusion would silently destroy this signal at extraction time.

**Allowed `functional_use` values.** `aligned`, `contested`, `avoided`, `invoked` (only when party invoked AND court subsequently engaged), `dismissed`.

**Downstream.** Rule 7.3 in agent files. Output schema's `functional_use` enum extended.

---

### D32 — Tiered chunking strategy for large documents

| Field | Value |
|---|---|
| Date | 2026-04-09 |
| Decided by | Gus |
| Source issue | Issue 4.1 |

**Context.** The corpus has 318 documents over 25K words, including 47 over 100K (max: 521K). Single-pass agent extraction degrades on these — context window pressure, attention dilution, and partial output truncation.

**Fork:**

- *Left* — single-pass for all, accept losses on the long tail
- *Middle* — pre-split everything, parallel extraction, merge. Uniform pipeline but heavy infrastructure for 93% of docs that don't need it
- *Right (chosen)* — tiered approach:
  - **Tier 1** (≤500 lines, ~93%, 3,331 docs ≤ 10K words + 848 docs 10K–25K) — single pass, current behavior
  - **Tier 2** (500–2000 lines, ~6%, 271 docs in 25K–100K range) — progressive file output: agent reads in 300-line chunks, appends to `data/extraction_results/{document_id}_partial.json` on disk, dedupes at end
  - **Tier 3** (>2000 lines, ~1%, 47 docs >100K words) — pre-split + parallel agents + merge. Separate scripts (`agentic-extraction/chunk_large_docs.py`, `agentic-extraction/merge_chunk_results.py`). Deferred until Tier 2 proves out.

**Rationale.** Most documents fit comfortably in single-pass. Adding chunking infrastructure for the 7% that need it is cheap; forcing it on all 4,497 docs is wasteful and complicates the simple case. The disk-resident partial JSON is the persistent memory between chunks — no inter-agent state passing.

**Parameters:** Tier 2 chunk size 300 lines (chosen for context-window comfort with overlap-free reads). Tier 3 chunk size ~20K words with 2K-word overlap at boundaries (to avoid splitting citations mid-reference).

---

### D33 — Global switch to `raw_text` (text source)

| Field | Value |
|---|---|
| Date (decision) | 2026-04-09 |
| Date (locked outcome A) | 2026-05-03 |
| Decided by | Gus |
| Source issue | Issue 3.1; test report `docs/reports/raw-vs-md-test.md` |

**Context.** The v7 pipeline (and the initial agent setup) consumed `extracted_text.text_md` (markdown via pymupdf4llm). During the Saint-Gobain test, pages 8–11 were truncated, dropping 38 footnotes containing at least 12 additional CJEU citations including the named-missing Flachglas Torgau, Sweden v MyTravel, and Bundesverwaltungsgericht references.

**Fork (after empirical T4 test on 5 baseline docs):**

- *A (chosen)* — Global switch: every doc re-exported from `raw_text`
- *B (test agent's recommendation)* — Hybrid via threshold `LENGTH(raw_text) − LENGTH(text_md) > 5000` chars
- *C* — Stay on markdown. Rejected outright (Saint-Gobain shows 75% under-extraction)

**Empirical evidence (T4 test, 5 docs):**

| Doc | md → raw | False positives | Lost citations |
|---|---|---|---|
| Sharma | 17 → 17 | 0 | 0 |
| Leghari | 2 → 2 | 0 | 0 |
| Saint-Gobain | **4 → 16** | 0 | 0 |
| ExxonMobil | 18 → 21 | 0 | 0 |
| Juliana | 100 → 100 | 0 | 0 |

All 3 known-missing Saint-Gobain footnote citations recovered with full ECLIs. Markdown structure was found "useful for parsing structure but not load-bearing for citation extraction" (test agent finding).

**Rationale (A over B).**

1. *Stated criterion satisfied* — Gus had pre-locked: "global switch if that does not lessen the agent capabilities by losing markdown support." Test data confirmed markdown is not load-bearing for extraction.
2. *Empirical 0/5 false positives* across 5 jurisdictions/formats (Australian, Pakistani, CJEU ×2, US 9thCir). The "scale risk" justifying B was speculative.
3. *Coherence* — Hybrid fragments the corpus with `text_source: raw_text` vs `text_source: text_md` per-document, undermining methodological uniformity.
4. *Threshold arbitrariness* — B's 5,000-char cutoff would miss edge cases just below the boundary.
5. *Cost not a constraint* — re-export of all 4,497 docs is cheap.

**Downstream.** All 4,497 documents re-exported from `et.raw_text`. Rule 7.6 (footnote-truncation awareness) is now obsolete and removed from the agent rules.

---

### D34 — Source DB patch for metadata misattribution

| Field | Value |
|---|---|
| Date | 2026-04-09 |
| Decided by | Gus |
| Source issue | Issue 2.1; T1 |

**Context.** The Juliana document (`4da6a9cf-9d3c-518f-a0d9-ebb49f771db7`) has `cases.jurisdiction = "Inter-American Commission on Human Rights"` but the document body is unambiguously the US Ninth Circuit Court of Appeals panel opinion in Juliana v. United States (No. 18-36082, January 17, 2020). The v7 pipeline classified all 30 of its extracted citations as "Inter-System" or "Non-Member Citation" — all wrong (the correct classification is Domestic, US→US).

**Fork:**

- *Left* — patch in a post-processing override layer (override table mapping document_id → corrected jurisdiction). Auditable and reversible. Adds infrastructure.
- *Right (chosen)* — patch the source `cases` table directly via SQL UPDATE.

**Rationale.** Local Postgres on `:5433`, full DB ownership, fork-style workflow (no shared production users to coordinate with). Patching the source means every downstream consumer (export script, agents, dashboards) sees the corrected metadata without override-layer maintenance. The change is git-tracked via migration scripts.

**Scope investigation.** T1 (`docs/reports/metadata-misattribution-T1.md`, in flight at time of writing) is enumerating the full candidate set. Patches will be applied as explicit `UPDATE cases SET jurisdiction = ... WHERE case_id = ...` statements after manual review of each candidate.

---

### D35 — Document date from header text (not `case_number` fallback)

| Field | Value |
|---|---|
| Date | 2026-04-09 |
| Decided by | Gus |
| Source issue | Issue 2.3; T3 |

**Context.** The frontmatter `year` was incorrect for several test docs because:

- `documents.document_date` is NULL for all 4,755 decisions (data not extracted upstream)
- The fallback parses `case_number` for `[YYYY]` / `(YYYY)` patterns, taking the latest year. Got Sharma 2020 (case filing year, in the case_number) instead of 2022 (latest proceeding); got Saint-Gobain 2012 (General Court filing) instead of 2016 (AG Opinion delivery)

**Fork:**

- *Left (initial proposal)* — accept `case_number` parsing as "good enough." Anachronism flag is soft anyway.
- *Right (chosen)* — extract the actual document date from the document text header. Most decisions state the judgment date prominently in the first ~500 chars (e.g., "Judgment of 17 January 2020", "ARRÊT DE LA COUR du 25 octobre 2017", "[2022] FCAFC 35 (15 March 2022)").

**Rationale.** Wrong years trigger false anachronism flags from the verifier (e.g., "2014 case cited in 2012 document — anachronistic"). For a doctoral-grade dataset, metadata accuracy matters even when the dependent flag is soft. Header parsing is a small regex change with high precision because document headers follow conventional formats.

**Implementation.** New `extract_year` algorithm: (1) header date regex on first 500 chars (multiple formats), (2) `case_number` fallback, (3) `case_filing_year` last resort. Refactored signature accepts body text.

---

### D36 — `fix_region()` in export script for international courts

| Field | Value |
|---|---|
| Date | 2026-04-09 |
| Decided by | Gus |
| Source issue | Issue 2.2; T2 |

**Context.** The `region` field used a binary heuristic: "if jurisdiction matches a Global North country list → Global North, else Global South." This put CJEU, ECtHR, IACtHR, ACHPR, ICJ, ITLOS, and arbitral tribunals into "Global South" by default — wrong, and breaks the sixfold classifier (which uses `source_region` as the first split between national and international classification branches).

**Fork:**

- *Left* — handle the international case at classification time only (third bucket added to the sixfold algorithm)
- *Right (chosen)* — fix at export time via `fix_region()` keyword detection

**Rationale.** Region is structural metadata. Correcting it at the export layer means every downstream consumer (agents, dashboards, ad-hoc analysis scripts) sees a single, correct value. Single source of truth, no per-consumer logic duplication.

**Implementation.** `INTERNATIONAL_KEYWORDS` list (CJEU, ECJ, ECtHR, ECHR, IACtHR, IACommHR, ACHPR, ICJ, ITLOS, ICSID, "international", "inter-american", "european court", "african court", "arbitral", "tribunal", "WTO", "PCA", "court of justice of the european union") matched case-insensitively against `cases.jurisdiction`. If matched, override `region` to "International". Applied in `scripts/export_decisions_md.py:build_frontmatter()`.

**Known interaction with D34.** The Juliana document has `jurisdiction = "Inter-American Commission on Human Rights"` despite being a US 9thCir opinion — `fix_region` will map it to "International" even though the underlying document is national. This is a metadata bug being investigated separately as T1, not a flaw in `fix_region` itself.

---

### D37 — Fresh agent dataset; v7 frozen as methodological baseline

| Field | Value |
|---|---|
| Date | 2026-04-09 (proposed) / 2026-05-03 (locked) |
| Decided by | Gus |
| Source | Cross-cutting; T10 |

**Context.** The locked decisions D29, D30, D33, D34, D36 each invalidate a portion of the v7 pipeline output (11,932 citations in `citation_extraction_phased`, etc.). Question: re-classify the existing v7 dataset using the corrected rules, or treat the agent run as a fresh, independent dataset?

**Fork:**

- *Left* — retroactively reclassify v7 output. Cheaper. Keeps one continuous dataset.
- *Right (chosen)* — agent extraction is fresh, v7 frozen as a methodological baseline.

**Rationale.** The v7 pipeline's primary defect is **recall**, not classification. Test runs showed:

- Juliana: 100 unique citations (agent) vs. 9 (v7) — ~91% miss rate
- ExxonMobil: 18 vs. 7 — ~61% miss rate
- Saint-Gobain: 4 vs. 3, plus 38 footnotes truncated outright

If 50–90% of citations are missing from a document's row, fixing the classification of the 10–50% extracted doesn't make the dataset usable — that's patching a sample, not a population. The misses also are not random: they skew toward footnote-heavy CJEU/ECtHR documents and older citation formats, exactly the docs where transnational dialogue lives.

A fresh extraction with all corrections (D29–D36) baked in at extraction time gives Lucas a methodologically clean dataset. The v7 dataset retains independent value as the "before" in a methodology section that quantifies the recall improvement — itself a finding worth reporting.

**Schema.**

| Layer | v7 (frozen baseline) | Agent v1 (current) |
|---|---|---|
| Per-citation | `citation_extraction_phased` | `citation_agent_v1` |
| Per-document | `citation_extraction_phased_summary` | `citation_agent_v1_summary` |
| Sixfold-classified | `citation_sixfold_classification` | `citation_sixfold_agent_v1` |

Same database (`climate_litigation`), parallel tables. Both queryable. Methodology section reports both with the delta.

**Downstream.** T10 plans the schema DDL and migration. T11 (this document) records the rationale.

---

## Index of related artifacts

- **Open-issues working document** (decisions table): `docs/reports/agent-test-run-open-issues.md`
- **T4 test report** (raw_text vs text_md): `docs/reports/raw-vs-md-test.md`
- **T1 metadata misattribution investigation** (in flight): `docs/reports/metadata-misattribution-T1.md`
- **Agent definition files**: `.claude/agents/citation-extractor.md`, `.claude/agents/citation-verifier.md`
- **Master rules document**: `agentic-extraction/docs/citation-extraction-rules.md`
- **Export script**: `scripts/export_decisions_md.py`
- **v7 pipeline (frozen reference)**: `scripts/5-extract-citations/`

---

## Template for future entries

```markdown
### D{n} — {one-line title}

| Field | Value |
|---|---|
| Date | YYYY-MM-DD |
| Decided by | {name} |
| Source issue | {cross-reference to issue tracker / report} |

**Context.** {What problem or question forced a decision}

**Fork:**

- *Left* — {alternative not chosen} — {brief rationale for why it was rejected}
- *Right (chosen)* — {chosen path} — {brief rationale for why}

**Rationale.** {Substantive justification — evidence, principles, constraints, prior commitments}

**Scope.** {How many documents / citations / cases / tables affected}

**Downstream.** {What changes in the codebase, schema, or process as a result}
```

---

*Maintainer: Gus. Last update: 2026-05-03.*
