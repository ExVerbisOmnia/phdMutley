# D24 Comment Review — Action Items

**Source:** `docs/pipeline-extraction-rules-commented.md.docx` (43 comments from Gus + Lucas)
**Reviewed by:** Claude, 3 April 2026
**Status:** Pending Gus approval before implementation

---

## Critical Fixes (Bugs / Data Quality)

### FIX-1: Unify Global North/South classification into single source of truth

**Problem:** The classification exists in 3 separate locations with inconsistencies:
- `populate_metadata.py` — 28 ISO codes (includes POL, CZE, HUN, ROU, ISR)
- `extract_citations.py:get_source_region()` — 26 country names (MISSING Poland, Czech Republic, Hungary, Romania, Israel)
- `KNOWN_FOREIGN_COURTS` — per-court hardcoded regions

Same country can be classified differently depending on code path. Lucas confirmed this already caused errors (EU countries → Global South).

**Action:** Move to a single `GLOBAL_NORTH_COUNTRIES` set in `config.py`, import everywhere. Expand from 26 to ~44 countries.

**Comments:** C4, C5, C6, C32

### FIX-2: Expand Global North list per scholarship

**Add (18 countries):**
- EU members missing: Poland, Czech Republic, Hungary, Romania, Bulgaria, Croatia, Slovakia, Slovenia, Estonia, Latvia, Lithuania, Luxembourg, Malta, Cyprus
- Other European: Turkey (Turkiye), Russia *(contested — needs footnote)*
- Other: Israel, Taiwan *(contested — needs footnote)*

**Remove from Global North:** European Union, Council of Europe → reclassify as "International"

**Sources:** UNCTAD geographic definition, UN WESP developed economies list, Setzer & Higham (LSE), Sabin Center methodology. Full analysis in research report.

**Comments:** C5, C6, C30, C31, C32

---

## Pipeline Design Changes

### CHANGE-1: Drop Origin ID Tiers 1 and 1.5 (Dictionary + Domestic Pattern)

**Decision:** Gus proposed (C28), Lucas agreed (C29).

**Current:** 4-tier origin identification (dictionary → domestic regex → Gemini Pro → web search)
**Proposed:** Remove Tiers 1/1.5. Go directly to LLM for origin ID (but downgrade to Flash per CHANGE-2).

**Rationale:** The dictionary (80+ courts) and regex patterns (25 countries) were built empirically and may have gaps/errors. LLM-based identification is more flexible and doesn't require maintaining hand-coded pattern lists.

**Trade-off:** Higher API cost per citation (every citation needs an LLM call for origin), but simpler and more consistent.

**Comments:** C28, C29

### CHANGE-2: Downgrade Origin ID from Gemini 2.5 Pro to Flash

**Decision:** Gus flagged as possible overkill (C40), Lucas agreed (C41), Claude concurs (C42).

**Current:** Phase 3 Tier 2 uses Gemini 2.5 Pro (~$0.001/citation)
**Proposed:** Use Flash (~$0.0001/citation) — 8x cheaper

**Rationale:** Origin ID is pattern matching + knowledge recall, not deep reasoning. Flash handles this well. Pro would be better used for verification/review where complex reasoning matters.

**Comments:** C40, C41, C42

### CHANGE-3: Restructure Sabin Filter as advisory (transparent matching)

**Decision:** Gus flagged as too broad (C15), Lucas wants transparency (C16).

**Current:** Sabin filter hard-discards unmatched citations
**Proposed:** Keep filter logic but make it advisory:
- Column A: `raw_extracted_case_name` (untouched)
- Column B: `sabin_matched_case_name` (or NULL)
- Column C: `sabin_match_score`
- Column D: `sabin_match_method` (exact / fuzzy_0.72 / etc.)

Lucas can then filter by score and review borderline matches.

**Comments:** C15, C16, C17

### CHANGE-4: Replace negative examples with positive definition in extraction prompt

**Decision:** Gus flagged sensitivity (C7), Lucas proposed simpler approach (C8).

**Current:** Prompt lists what NOT to extract (treaties, statutes, books...) — unbounded set
**Proposed:** Flip to positive definition: "Extract ONLY references to judicial decisions (court cases). Verify each is a judgment, order, opinion, or advisory opinion issued by a court or tribunal." Keep a short illustrative list of false positives as examples, not as the rule.

**Comments:** C7, C8, C9

### CHANGE-5: Adapt functional categories to Nollkaemper's Avoid/Align/Contest typology

**Decision:** Lucas proposed (C18/21/24), Gus agreed (C19/22/25).

**Current categories:** `parties_argument`, `dismissed`, `contributed`
**Proposed categories (citation-level adaptation of Nollkaemper):**

| Old | New | Definition |
|-----|-----|-----------|
| `parties_argument` | `invoked` | Citation recounted as a party's argument |
| `dismissed` | `contested` | Court engages but rejects/distinguishes the citation |
| `contributed` | `aligned` | Citation supports the court's reasoning |
| *(new)* | `avoided` | Citation mentioned but court declines substantive engagement |

**Academic basis:** ILA Study Group typology (2011-2016) → Nollkaemper (2025), TEL 14(3), DOI: 10.1017/S2047102525100058

**Full synthesis saved:** `docs/reports/nollkaemper-avoid-align-contest-synthesis.md`

**Comments:** C18-C26

### CHANGE-6: Pull court name + case number during source jurisdiction ID (Phase 1)

**Decision:** Lucas proposed (C6, C36), Gus agreed (C37).

**Purpose:** Disambiguate multi-instance litigation (Juliana problem, Klimaseniorinnen problem). Kate's feedback confirmed this is a real issue — the pipeline confuses US domestic Juliana with IACtHR Juliana.

**Implementation:** During Phase 1, extract not just `source_jurisdiction` but also `source_court` and `case_number` from metadata. This feeds downstream disambiguation.

**Comments:** C6, C36, C37

### CHANGE-7: Expand year extraction to catch 2-digit years

**Decision:** Gus noted (C14) that years like "89" or "95" should be recognized as possible 19xx references.

**Current:** Only matches 4-digit years (19xx, 20xx)
**Proposed:** Also match 2-digit years in citation context, interpreting as 19xx when in parentheses/brackets: `(89)` → 1989

**Comments:** C14

---

## Document Cleanup (Rules Doc Updates)

### DOC-1: Remove D17 Reporting section from pipeline doc

**Reason:** D17 is about data interpretation, not pipeline logic. Both Gus and Lucas confirmed. D22 (counting rule) stays because it's implemented in code.

**Comments:** C33, C34, C35

### DOC-2: Remove the oversized document review question

**Reason:** Chunking already handles large documents. Question was unnecessary. Both confirmed.

**Comments:** C0, C1, C2, C3

### DOC-3: Clarify "topical overlap" in anti-hallucination rules

**Reason:** Lucas clarified — "topical overlap" means same subject matter. Wording in prompt should be explicit.

**Comments:** C10, C11

---

## Confirmed Non-Changes

| Thread | Decision | Status |
|--------|----------|--------|
| C12→C13 | Chunking is necessary (model constraint) | No change |
| C38→C39 | Do NOT flag domestic citations | No change |

---

## Priority Order for Implementation

1. **FIX-1 + FIX-2** — Global North/South unification (data quality, affects all results)
2. **CHANGE-4** — Positive definition in extraction prompt (simple, high impact)
3. **CHANGE-1 + CHANGE-2** — Origin ID simplification (architectural)
4. **CHANGE-3** — Sabin filter transparency (structural)
5. **CHANGE-5** — Functional categories (requires prompt redesign + testing)
6. **CHANGE-6** — Court/case number extraction (metadata enrichment)
7. **CHANGE-7** — 2-digit year parsing (minor enhancement)
8. **DOC-1/2/3** — Document updates (low effort)
