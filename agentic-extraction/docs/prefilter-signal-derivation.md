# Prefilter Signal Derivation — Audit Trail

**Companion to:** `agentic-extraction/agents/citation-prefilter.md`
**Source of truth:** `agentic-extraction/docs/citation-extraction-rules.md`
**Date:** May 2026

This document explains *why* the citation-prefilter agent has the signals it has and traces each one back to the canonical rules document. **It is not loaded by Haiku at runtime** — the prompt itself is self-contained. This file exists so a future reviewer (Lucas, Gus, or a successor) can verify the mapping is faithful to the rules and amend it when the rules change.

If you change a signal in the prompt, update the corresponding row here. If you change the rules document, scan this file for affected rows.

---

## Design principle

The extractor in `citation-extraction-rules.md` §2.6 enumerates **13 citation patterns** because it must classify what it finds. The prefilter is a **binary classifier** — it only needs to detect that *any* citation pattern is present. So the 13 patterns are coarsened by surface form into 7 macro-signals (one signal can absorb multiple patterns when their surface forms overlap).

A signal in the prefilter ≠ a pattern in the rules doc. A signal is a *visible cue at scan-time*; a pattern is a *taxonomy bucket the extractor uses to record its findings*.

---

## Positive signals — derivation

| Prompt signal slug                       | Source in rules doc                                        | Coarsening rationale                                                                                                                                              |
| ---------------------------------------- | ---------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `party_pairing_pattern`                  | §2.6 Patterns 1, 3                                         | Workhorse heuristic. Generalized from `v.` to multilingual connectors (`v.`, `vs`, `c.`, `gegen`, `tegen`, `contra`) — civil-law jurisdictions do not use `v.`.   |
| `formal_reporter_or_neutral_citation`    | §2.6 Patterns 1, 11, 13                                    | Lifts the reporter / neutral-citation / advisory / numeric-shortform patterns into one signal. They are distinct format families, but for "is it present?" they are equivalent. |
| `narrative_court_attribution`            | §2.6 Pattern 2; §1.3 examples 1 and 4                      | Multilingual: covers any "[Specific Court] held / sostuvo / entschied / oordeelde / décida / decidiu" construction.                                              |
| `shorthand_case_reference`               | §2.6 Pattern 3                                             | Standalone case names after first introduction. Often italicized in formatted source PDFs (preserved when conversion was clean).                                  |
| `legal_citation_signal`                  | §2.6 Patterns 6, 7                                         | Comparative phrases ("Distinguishing…") and signal citations ("See also", "Cf.") merged — both are *cue phrases that announce a citation is coming*.            |
| `footnote_or_id_reference`               | §2.6 Pattern 8                                             | Footnote citations + supra/ibid./id. cross-references. Heavy footnote density alone is a weak hint; this signal fires only when those references appear in a legal-reference context. |
| `procedural_history_reference`           | §2.6 Pattern 5                                             | Appeals, reversals, affirmances when they describe specific judicial proceedings.                                                                                 |

### Patterns from §2.6 NOT given a dedicated signal

| Rules-doc pattern                            | Why merged or omitted                                                                                                                                                                                                                                  |
| -------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Pattern 4 (Scholarly Context)                | Rare standalone occurrence; when present, it co-occurs with `shorthand_case_reference` or `narrative_court_attribution`. Adding a dedicated signal would multiply false positives in academic-leaning judgments without adding recall.                |
| Pattern 9 (Dissent/Concurring Citations)     | The opinion type is metadata for the *extractor*; for the prefilter, citations within a dissent look the same as citations in the majority. Already covered by other signals.                                                                          |
| Pattern 10 (Doctrine Attribution)            | Co-occurs with `narrative_court_attribution` ("the doctrine of proportionality as developed in [Case]…"). Folding into that signal is sufficient.                                                                                                     |
| Pattern 12 (Pending/Ongoing Cases)           | Edge case; pending references are usually accompanied by other signals when they matter. Not worth a dedicated slug.                                                                                                                                  |
| §1.6 court-engagement signal-words (functional-use table) | Originally given a dedicated `court_engagement_language` signal but removed: when paired with a case name, it is redundant with the four positive signals above; alone, it is a weak signal that risks over-triggering on procedural narrative. |

---

## Negative signals — derivation

| Prompt signal slug                       | Source in rules doc                                        | Notes                                                                                                                                                |
| ---------------------------------------- | ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `general_topic_no_specific_case`         | §1.3 negative example 1                                    | "Courts in several countries have addressed climate change" — generic jurisprudence-talk without naming a specific case.                            |
| `statute_treaty_or_regulation_only`      | §1.3 negative example 4                                    | Statute / treaty / regulation references **only**. Anti-hallucination corollary of §2.7 Rule 1 (do not fabricate from training data).                |
| `academic_or_commentary_only`            | §1.3 negative example 3                                    | Scholarly references are not judicial citations.                                                                                                    |
| `procedural_administrative_only`         | (synthesized from §1.2 inclusion criteria + §2.3)          | Documents that are purely procedural — hearing-scheduling orders, notices, settlement decrees. The inclusion criteria in §1.2 imply these are not the kind of document the corpus targets. |
| `sabin_pipe_format_metadata`             | §2.7 Rule 5                                                | The rules doc has an *explicit* "skip it" instruction for `Case Name (YYYY) \| Court; Jurisdiction` patterns. The prefilter mirrors this at gate-time. |

---

## Multilingual coverage

The corpus contains documents in English, Spanish, Portuguese, French, German, Dutch, Italian, and Norwegian (per §2.5). The prompt instructs Haiku to recognize the patterns in any language rather than enumerating translations:

> "Documents in this corpus appear in English, Spanish, Portuguese, French, German, Dutch, Italian, and Norwegian. Recognize the patterns below in any language; do not require an English match."

**Why no translated keyword lists:** for any one signal, the translations across 7 languages × ~5 surface variants each = ~35 strings. Across all 12 signals = ~420 strings. The prompt would become a glossary, with the signal *names* losing salience to the model. Haiku 4.5 has solid multilingual capability for these languages — recognizing "el Tribunal Constitucional sostuvo" as functionally equivalent to "the Constitutional Court held" is precisely what an LLM is good at and what regex is not.

The two cases where translations *are* explicit in the prompt:

1. `party_pairing_pattern` — connector tokens are too short and orthographic for paraphrase recognition (`v.`, `vs`, `c.`, `gegen`, `tegen`, `contra`). Listed explicitly.
2. `narrative_court_attribution` — the example sentences include Spanish, German, Dutch variants to anchor the multilingual instruction.

---

## What is NOT in the prompt that is in the rules doc

The prompt deliberately omits material that is load-bearing for the *extractor* but useless for the *prefilter*:

- The Sixfold Citation Typology (§1.5)
- The full Nollkaemper functional-use table (§1.6)
- Anti-hallucination Rules 1, 2, 3, 4, 6, 7 from §2.7 (only Rule 5 is operative for the prefilter)
- Tiered chunking strategy (§2.3.1)
- Origin identification logic (§2.9)
- Verifier protocol (entire §3)
- Edge cases in §4

The prefilter never needs to *classify* a citation — it only needs to spot one. So all post-detection logic is dead weight.

---

## Maintenance

When updating signals, keep in mind:

1. **Total signal count vs. signal salience.** Every signal beyond ~12-15 dilutes attention without proportional recall gain.
2. **Avoid soft-overlapping signals.** If `narrative_court_attribution` and `court_engagement_language` both fire on "the Court adopted in [Case]", the model may double-count, inflating apparent positive evidence. We removed `court_engagement_language` for this reason.
3. **Negative signals are weaker than positive signals.** It is easier to say "this looks like a citation" than "I am sure there is no citation in 50 pages." That asymmetry is reflected in the decision rule: zero positives + one negative = 0.90+ confidence (not 0.95+).
4. **Validation before scaling.** Run the prefilter against the 58 already-complete docs in `citation_agent_v1_run_state` (`status='complete'`) before unleashing on the 4,083 pending. Required: zero false negatives on docs known to contain ≥1 citation.


---

## Validation gate results (May 2026)

The prefilter was validated against all 58 documents with `status='complete'` in `citation_agent_v1_run_state` (14 with ≥1 confirmed citation, 44 with zero). The validation script `agentic-extraction/validate_prefilter.py` runs the prefilter against each doc and compares its prediction to the ground-truth citation count from `citation_agent_v1`.

### Round 1 (initial prompt)

- **Result: FAIL** — 1 hard miss out of 58.
- The single failure was doc `f0138829-2dca-557e-a2aa-def0ef0924a0` ("California v. Council on Environmental Quality"), a 203-word stay order containing a single procedural reference: "the related case, Alaska Community Action on Toxics v. CEQ, No. 3:20-cv-05199-RS (N.D. Cal.)".
- The prefilter correctly *identified* the case mention but classified it as "contextual only, not precedential citation" and returned `has_citations: false, confidence=0.94`. The prefilter was making an engagement-level judgment that belongs to the verifier, not the triage step.

### Root cause

The original prompt''s anti-mistakes section read: *"A party''s argument ('Plaintiff argues…') is not a citation by itself — the court must engage with it."* This was meant to prevent confusion of generic argument-language with citations, but the model generalized it to "non-engaged mentions don''t count" — which is an over-correction for a triage step.

Per the rules document §1.3, "See also Juliana v. United States, No. 18-36082 (9th Cir. 2020)" *is* a citation — the inclusion criterion at extraction time is "the document names a specific judicial decision". The prefilter was applying a stricter standard than the corpus rule.

### Fix applied

Three changes to `agents/citation-prefilter.md`:

1. **Mission reframed** from "contains a citation" to "mentions at least one specific judicial decision by name — in any context: as precedent, in narrative attribution, as a related/companion case, in procedural-history references, or in passing." Plus an explicit caveat: *"do not filter for ''precedential value'', ''court engagement'', or ''substantive use'' — that is the verifier''s job."*
2. **Anti-mistake replaced** with a tighter version: *"A generic reference to argument types without naming a specific case is not a citation. But once a specific case is named — even contextually, in passing, in a related-case mention, or in scheduling language — that is a citation for your purposes."*
3. **Positive signal `formal_reporter_or_neutral_citation`** had a docket-number example added (`No. 3:20-cv-05199-RS`) with a note that "docket numbers count even when the citation is to a related/companion case rather than precedent."

### Round 2 (post-fix)

- **Result: PASS** — zero hard misses.

| Category         | Count | Notes                                                                  |
| ---------------- | ----- | ---------------------------------------------------------------------- |
| CORRECT_KEPT     | 14    | All 14 citation-bearing docs correctly routed to full pipeline         |
| CORRECT_BYPASS   | 35    | Cost saved (~$0.05 × 35 docs ≈ $1.75 vs. ~$0.001 × 35 prefilter calls) |
| WASTED           | 9     | False positives — full pipeline runs, but no data loss                 |
| LOW_CONF_NEG     | 0     |                                                                        |
| SOFT_MISS        | 0     |                                                                        |
| **HARD_MISS**    | **0** | **Pass criterion met**                                                 |
| PREFILTER_FAILED | 0     |                                                                        |

- **Bypass rate:** 60.3% — extrapolating to the 4,083 pending docs, ~2,460 should avoid full Sonnet extraction
- **Waste rate:** 15.5% — false alarms are operationally fine (full pipeline runs anyway), just an extra Haiku call

### Per-doc record

The full per-doc results from each run are saved as JSONL in `agentic-extraction/validation/results_<timestamp>.jsonl`. Each row records doc_id, tier, word_count, ground-truth confirmed_count, prediction (has_citations / confidence / signals_observed / reason), elapsed_s, and category. These are the audit trail for the gate.

### Lesson learned

The prefilter''s job is **inclusion-permissive triage**, not doctrinal filtering. The verifier already has the more nuanced "court engagement" criterion (D31 dismissed-vs-engaged distinction); the prefilter just needs to avoid bypassing any document where a case is named. When designing future agents, the same disposition applies: triage steps should be permissive, downstream verifiers should be strict.
