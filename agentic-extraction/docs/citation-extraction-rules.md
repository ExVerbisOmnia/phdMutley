# Citation Extraction Agent Rules — Working Document v1.1

**Purpose:** Master instruction set for 2-agent citation extraction pipeline, to be run under Claude Code (Max subscription). This document is the **canonical source of truth**; the two agent files (`.claude/agents/citation-extractor.md` and `.claude/agents/citation-verifier.md`) must stay in sync with it.
**Source:** Derived from phdMutley v7 pipeline (`scripts/5-extract-citations/`), as amended by the D24 comment review (Gus + Lucas + Claude, March–April 2026), and the Workstream B consolidation of decisions D29–D37 (May 2026, after the 5-document test run).
**Date:** 3 May 2026
**Status:** Locked rules from D29–D37 consolidated. Source of truth for the two agent files.

---

## Table of Contents

- [0. Architecture & Execution Model](#0-architecture--execution-model)
- [1. Shared Definitions & Reference Data](#1-shared-definitions--reference-data)
- [2. AGENT 1 — EXTRACTOR](#2-agent-1--extractor)
- [3. AGENT 2 — VERIFIER-ENRICHER](#3-agent-2--verifier-enricher)
- [4. Known Edge Cases & Disambiguation Rules](#4-known-edge-cases--disambiguation-rules)
- [Appendix A — Global North Countries](#appendix-a--global-north-countries-definitive-list)
- [Appendix B — International Court Membership](#appendix-b--international-court-membership)
- [Appendix C — Nollkaemper Typology Reference](#appendix-c--nollkaemper-typology-reference)

---

## 0. Architecture & Execution Model

### Pipeline Overview

```
Document (.md file with YAML frontmatter)
  │
  ├── AGENT 1: EXTRACTOR
  │     Mandate: MAXIMUM RECALL
  │     Reads full document text + metadata
  │     Extracts ALL judicial decision citations
  │     Outputs: JSON array of extracted citations
  │
  └── AGENT 2: VERIFIER-ENRICHER
        Mandate: MAXIMUM PRECISION
        Reads full document text + Agent 1 output
        Verifies each citation, finalizes classification
        Outputs: enriched + verified JSON
```

### Input Format

Each document is a Markdown file with a YAML frontmatter header:

```yaml
---
document_id: "uuid"
case_id: "case-slug"
case_name: "Full Case Name"
case_number: "Docket/reference number"
sabin_case_id: "sabin-slug"
document_title: "Document Title"
jurisdiction: "Country or International"
geographies: "Country; Sub-jurisdiction"
geography_iso: "ISO code"
region: "Global North|Global South|International"
year: 2020
language: "en"
word_count: 12345
character_count: 67890
---

[Markdown-formatted judicial decision text]
```

The frontmatter provides the **source metadata** — the agent does NOT need to infer the source jurisdiction, year, or court from the document text. These come from the Sabin Center database and are pre-populated.

### Output Format

Both agents produce JSON. Agent 1's output feeds into Agent 2. Agent 2's output is the final record that gets loaded into the database.

---

## 1. Shared Definitions & Reference Data

### 1.1 Corpus Definition

- **Source:** Climate Case Chart database (Sabin Center for Climate Change Law, Columbia Law School)
- **Scale:** ~5,500 documents classified as judicial decisions (from ~16,000 total documents across ~4,700 cases)
- **Scope:** Only documents where `is_decision = True` are processed. Non-decision documents (briefs, motions, amicus curiae) are excluded.
- **Body source (D33):** The corpus body is the **plain text of the original PDF** (`raw_text` column in `extracted_text`), NOT the markdown rendering. Footnotes are intact. Page-headers like `"CURIA - Documents http://curia.europa.eu/..."` may repeat across pages — these are not citations and must be skipped per the anti-hallucination rules (metadata-format contamination).
- **Region for international courts (D36):** The export script (`scripts/export_decisions_md.py`) applies `fix_region()` so that frontmatter `region` is corrected to `"International"` for CJEU, ECtHR, IACtHR/IACommHR, ACHPR, ICJ, ITLOS, arbitral tribunals, etc. No agent-side handling is needed — the frontmatter is already correct.

### 1.2 What Is a Judicial Decision (Inclusion Criteria)

A **judicial decision** is a judgment, order, ruling, opinion, decree, or advisory opinion issued by a court or tribunal. This includes:

- Majority opinions, dissenting opinions, concurring opinions
- Interim/interlocutory orders
- Advisory opinions (ICJ, IACtHR, etc.)
- Decisions on admissibility, standing, or jurisdiction
- Consent decrees and settlement orders approved by courts

**NOT judicial decisions** (do not extract references to these):

- Treaties, conventions, protocols (Paris Agreement, UNFCCC, Kyoto Protocol, Aarhus Convention)
- Statutes, legislation, regulations, acts of parliament (Clean Air Act, Resource Management Act, CPR rules)
- Academic articles, books, or author names (e.g., "Hogg", "Bowden & Olszynski")
- Reports by UN bodies, IPCC, or other non-judicial organizations (unless citing a specific court case within those reports)
- Procedural rules (Federal Rules of Civil Procedure, CPR)
- Executive orders, ministerial decrees, administrative regulations

> **Design principle (CHANGE-4):** The rule is defined by what TO extract (judicial decisions), not by an exhaustive list of exclusions. The short exclusion list above is illustrative, not exhaustive. When in doubt, ask: "Was this issued by a court or tribunal as a judicial act?" If yes → extract. If no → skip.

### 1.3 What Is a "Citation"

A citation exists when the document **names or references** a specific judicial decision. The reference must be to a **particular, identifiable case** — not a general statement about courts or jurisprudence.

**IS a citation:**

- "In Urgenda Foundation v. State of the Netherlands, the Supreme Court held..."
- "See also Juliana v. United States, No. 18-36082 (9th Cir. 2020)"
- "Following the approach in the Leghari case..."
- "As the ECtHR stated in Öneryıldız v. Turkey..."
- A footnote referencing "Neubauer et al. v. Germany, BVerfG, 1 BvR 2656/18"

**IS NOT a citation:**

- "Courts in several countries have addressed climate change" (no specific case named)
- "The precautionary principle has been applied in environmental cases" (general reference)
- "As Professor Peel has argued..." (academic reference, not a case)
- "Under the Paris Agreement, Article 4..." (treaty, not a case)
- Topical overlap alone: a document about rising sea levels does NOT cite a different case about rising sea levels unless it **names** that case

> **Anti-hallucination rule:** Same subject matter is NOT a citation. The document must explicitly name, reference, or point to the specific case. If the connection exists only because both cases deal with similar topics, it is NOT a citation.

### 1.4 Global North / South Classification

**Classification rule:**

1. If the jurisdiction is "International", "INTL", "World", "European Union", or "Council of Europe" → **International**
2. If the country is in the Global North list (Appendix A) → **Global North**
3. Everything else → **Global South**

See **Appendix A** for the definitive list of ~44 Global North countries (expanded per FIX-1/FIX-2 from the D24 review, sourced from UNCTAD, UN WESP, Setzer & Higham/LSE, Sabin Center methodology).

### 1.5 Sixfold Citation Typology

The sixfold system classifies the **geographic relationship** between the citing court (source) and the cited case (target):

| #   | Type                               | Direction                             | Condition                                                                                                                               |
| --- | ---------------------------------- | ------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **Foreign Citation**               | National → National                   | Source and target are different national jurisdictions                                                                                  |
| 2   | **International Citation**         | National → International (member)     | Source is a national court; target is an international court of which source country is a **member**. Set `is_vertical_dialogue: true`. |
| 3   | **Foreign International Citation** | National → International (non-member) | Source is a national court; target is an international court of which source country is **NOT a member**                                |
| 4   | **Inter-System Citation**          | International → International         | Both source and target are international courts (and not the same court system — see Domestic rule below)                               |
| 5   | **Member-State Citation**          | International → National (member)     | Source is an international court; target is a national court from a **member state**                                                    |
| 6   | **Non-Member Citation**            | International → National (non-member) | Source is an international court; target is a national court from a **non-member state**                                                |

**Domestic citations** (source and target are the same jurisdiction OR the same court system) are classified as **"Domestic"** — they are outside the scope of the transnational dialogue research but should still be extracted and tagged, not discarded.

> **Same-court / same-system rule (D29 + D38 refinement).** When the source court and the cited court are **the same institution** OR are **within the same court system**, the classification depends on whether the body is international or national:
> 
> - **International institution** (CJEU, ECtHR, IACtHR, ACHPR, WTO DSU, ICJ, ITLOS, ICSID, etc.) → classify as **Inter-System Citation (Type 4)**, even when both source and cited are sub-bodies of the same DSU. Intra-international citations are still transnational dialogue.
> - **Sub-body of a national jurisdiction** (US Circuit → US Supreme Court, German BVerfG → German lower court, Brazilian STF → STJ) → classify as **Domestic**. Intra-national hierarchies are out of scope.
> 
> This rule applies BEFORE the sixfold algorithm.
> 
> Examples (D38 refinement, 2026-05-03):
> 
> | Source              | Cited              | Classification            |
> | ------------------- | ------------------ | ------------------------- |
> | CJEU judgment       | prior CJEU ruling  | **Inter-System (Type 4)** |
> | CJEU AG Opinion     | prior CJEU ruling  | **Inter-System (Type 4)** |
> | General Court (EU)  | CJEU               | **Inter-System (Type 4)** |
> | IACtHR Advisory     | IACtHR Contentious | **Inter-System (Type 4)** |
> | ECtHR Grand Chamber | ECtHR Chamber      | **Inter-System (Type 4)** |
> | WTO Appellate Body  | WTO Panel          | **Inter-System (Type 4)** |
> | US 9th Circuit      | US Supreme Court   | **Domestic**              |
> | German BVerfG       | German lower court | **Domestic**              |
> | Brazilian STF       | Brazilian STJ      | **Domestic**              |

> **Vertical-dialogue boolean (D30).** Every citation in the verifier's output gains a boolean field `is_vertical_dialogue`. Set `true` ONLY when:
> 
> - Source = a national court (not international), AND
> - Cited = an international court of which the source's country is a member (per Appendix B).
> 
> Set `false` everywhere else (international→international, international→national, national→non-member-international, etc.).
> 
> Examples:
> 
> - Germany citing ECtHR → Type 2, `is_vertical_dialogue: true`
> - Colombia citing IACtHR → Type 2, `is_vertical_dialogue: true`
> - Netherlands citing CJEU → Type 2, `is_vertical_dialogue: true`
> - Australia citing ICJ → Type 2, `is_vertical_dialogue: true` (ICJ universal jurisdiction)
> - USA citing ECtHR → Type 3, `is_vertical_dialogue: false` (USA is not an ECtHR member)
> - ECtHR citing IACtHR → Type 4, `is_vertical_dialogue: false` (international → international)

**Unclassified:** If source or target region/jurisdiction is missing or cannot be determined.

Court membership lookups use the tables in **Appendix B**.

### 1.6 Functional Use Typology (Nollkaemper Adaptation)

How the **citing court** uses each citation in its reasoning. Based on Nollkaemper (2025), "Avoid, Align or Contest?", *Transnational Environmental Law* 14(3), pp. 469-499, adapted from the ILA Study Group typology (2011-2016) to citation-level granularity.

> **Court engagement = inclusion criterion (D31).** A citation is included in the dataset only if the court itself engages with it (aligns, contests, distinguishes, applies, or actively avoids the cited case). Citations only invoked by parties with mere court acknowledgement (the court summarizes a party's argument without endorsing or refuting the citation) get `functional_use: dismissed`. They are kept in the dataset (soft tag) but excluded from the default analysis layer.
> 
> **Rationale:** in citation-network research, the citations that matter are those that influenced the court's reasoning (ratio decidendi or substantive engagement). Mere mentions in dictum or party-argument summaries are not load-bearing. The `dismissed` soft-tag preserves these for "what parties cite vs. what courts engage with" gap analysis but excludes them from the default analysis layer.

| Category      | Label       | Definition                                                                                                                                                                                         | Signal Words                                                                                                                                                          |
| ------------- | ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Aligned**   | `aligned`   | Court **endorses, follows, or relies on** the cited case                                                                                                                                           | "following", "applying", "as held in", "consistent with", "we adopt", "in line with", "relying on", "in accordance with", "as established in"                         |
| **Contested** | `contested` | Court **rejects, distinguishes, or refuses to follow** the cited case                                                                                                                              | "distinguish", "unlike", "differs from", "not applicable", "little transfer value", "we disagree", "this case is distinguishable", "overruled", "departed from"       |
| **Avoided**   | `avoided`   | Court **declines to engage** with a case it could have applied                                                                                                                                     | "not necessary to consider", "need not address", "not justiciable", "outside our jurisdiction", "we decline to rule on", "moot", "not applicable to the present case" |
| **Invoked**   | `invoked`   | Party invoked the case AND the court subsequently engaged with it. Use only when the party-introduction is integral; usually re-tag with the court's actual treatment (aligned/contested/avoided). | "submitted", "argued", "contended", "relied on", "the appellant/respondent invoked", "plaintiff cited", "as argued by"                                                |
| **Dismissed** | `dismissed` | Party invoked, court only **acknowledged in passing or in summarizing arguments**, no endorsement or rejection. Soft-tag — kept in the dataset but excluded from the default analysis layer.       | "the petitioner cited X", "counsel referred to Y" (with no subsequent engagement by the court)                                                                        |

**Default rule:** If the functional use cannot be determined with reasonable confidence and the court engages with the citation, classify as `aligned` with low confidence. If the court does not engage at all, classify as `dismissed`.

**Opinion type** must also be recorded:

| Type          | Description           |
| ------------- | --------------------- |
| `majority`    | Main/majority opinion |
| `dissent`     | Dissenting opinion    |
| `concurrence` | Concurring opinion    |
| `unclear`     | Cannot determine      |

---

## 2. AGENT 1 — EXTRACTOR

### 2.1 Mandate

**MAXIMUM RECALL.** Extract every reference to a judicial decision in the document. It is better to over-extract (include uncertain references) than to miss genuine citations. Agent 2 will prune false positives.

### 2.2 Input

A single Markdown file with YAML frontmatter (see Section 0). The agent reads:

- The **frontmatter** for source metadata (jurisdiction, year, court, region)
- The **body** for the full document text to search

### 2.3 Quality Pre-Check

Before extracting, the agent performs a quick quality assessment:

1. **Garbled text:** If the document text is predominantly non-alphabetic characters, random symbols, or OCR artifacts (e.g., `"j$k@#m2 f!&x..."`) — flag the document as `SKIPPED_GARBLED` and do not extract.
   
   - Heuristic: If the first 5,000 characters have less than 40% alphabetic characters, or the average word length exceeds 25 characters, the text is garbled.

2. **Empty/trivial text:** If the document has fewer than 100 characters of body text — flag as `SKIPPED_EMPTY`.

3. **Proceed normally** for all other documents, regardless of length. There is no "too long" skip — the agent's context window handles large documents.

### 2.3.1 Tiered Chunking Strategy (D32)

Document size determines the extraction strategy:

| Tier | Size                       | Strategy                                                                                                                                          |
| ---- | -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | ≤ 500 lines (~25K words)   | Single-pass extraction — current default behavior, no changes                                                                                     |
| 2    | 500–2000 lines (25–100K w) | Progressive file output — see below                                                                                                               |
| 3    | > 2000 lines (> 100K w)    | Pre-split + parallel + merge (handled by external scripts: `agentic-extraction/chunk_large_docs.py`, `agentic-extraction/merge_chunk_results.py`) |

**Tier 2 — Progressive file output (for documents over 500 lines):**

1. Read the document in chunks using `Read(offset=N, limit=300)`.
2. After processing each chunk, append the chunk's found citations to `data/extraction_results/{document_id}_partial.json` (create the file on first chunk).
3. The partial file is your persistent memory between chunks — no inter-chunk state passing needed.
4. After all chunks are processed, read back the partial file, deduplicate by `case_name`, and produce the final JSON output.

### 2.4 Source Document Metadata

Read from the YAML frontmatter. Do NOT infer these from the document text:

- `source_jurisdiction`: The country/entity where the citing court sits (from `jurisdiction` field)
- `source_region`: Global North / Global South / International (from `region` field)
- `source_year`: The year of the document (from `year` field)
- `source_court`: Can be inferred from `document_title` or the document text's header if not in frontmatter

These fields contextualize the extraction — for example, the document year enables anachronism detection.

### 2.5 Extraction Scope — What to Extract

Extract **every reference to a judicial decision** (as defined in Section 1.2) found anywhere in the document, regardless of:

- Whether the cited case is domestic or foreign
- Whether the citation is formal or informal
- Whether the citation is in a footnote, endnote, dissenting opinion, or main text
- The language of the citation (documents may cite cases in English, Spanish, Portuguese, French, German, Dutch, Norwegian, etc.)
- Whether you recognize the case or not — extract what the document says

### 2.6 Citation Patterns to Capture

The following patterns should all trigger extraction. This list is illustrative, not exhaustive — any pattern that references a specific judicial decision should be captured.

**Pattern 1 — Traditional/Formal Citations:**
Formal legal citations with case names, reporters, and court identifiers.

- `"Brown v. Board of Education, 347 U.S. 483 (1954)"`
- `"R (Miller) v Secretary of State [2017] UKSC 5"`
- `"Case C-473/14 Dimos Kropias Attikis"`
- `"Recurso Extraordinário 654.833/AC"` (Brazilian)
- `"Sentencia T-300 de 2018"` (Colombian)
- Include all parallel citations

**Pattern 2 — Narrative References:**
Descriptive mentions that name a court and a ruling without a formal citation.

- `"The Norwegian Supreme Court held in 2020..."`
- `"Following the Dutch court's approach in..."`
- `"The European Court of Human Rights stated..."`

**Pattern 3 — Shorthand/Case Name References:**
Abbreviated case names used after the case has been introduced or is well-known.

- `"the Urgenda case"`
- `"following Abraham"`
- `"the landmark Dutch climate decision"`
- `"as established in Öneryıldız"`

**Pattern 4 — Scholarly Context Citations:**
Cases referenced within academic or analytical passages of the decision.

- `"The UNEP analysis of the Urgenda ruling noted..."`
- `"Commentary on the ECtHR's climate jurisprudence..."`

**Pattern 5 — Procedural History References:**
References to prior or subsequent proceedings of the same case or related cases.

- `"On appeal from the District Court..."`
- `"Affirmed by the Supreme Court in..."`
- `"Following reversal by the Court of Appeal..."`

**Pattern 6 — Comparative References:**
Explicit comparisons to other cases.

- `"Unlike the approach taken in..."`
- `"Similar to the holding in..."`
- `"Distinguishing the facts of..."`

**Pattern 7 — Signal Citations:**
Legal citation signals.

- `"See also..."`, `"Cf..."`, `"Compare with..."`, `"But see..."`, `"Accord..."`

**Pattern 8 — Footnote/Endnote Citations:**
Citations appearing in footnotes or endnotes, including cross-references.

- `"Supra note 12"` (if note 12 references a case)
- `"Ibid."` or `"Id."` referencing a case
- Full citations in footnote text

**Pattern 9 — Dissenting/Concurring Opinion Citations:**
Citations within non-majority opinions. Note which opinion type contains the citation.

**Pattern 10 — Doctrine/Principle Attribution:**
When a legal doctrine is attributed to a specific case.

- `"The doctrine of proportionality as developed in..."`
- `"The European precautionary principle jurisprudence established in..."`

**Pattern 11 — Advisory Opinions:**
References to advisory opinions from international tribunals.

- `"ICJ Advisory Opinion on the Legality of the Threat or Use of Nuclear Weapons"`
- `"IACtHR Advisory Opinion OC-23/17"`

**Pattern 12 — Pending/Ongoing Case References:**
References to cases that may not yet have a judgment.

- `"The case currently pending before..."`
- `"The ongoing proceedings in..."`

**Pattern 13 — Numeric/Short-Form References (2-digit years):**
Some citations use abbreviated year forms.

- `"(89)"` or `"(95)"` in citation context → may refer to 1989, 1995
- Case numbers like `"No. 95-123"` may encode year information

### 2.7 Anti-Hallucination Protocol

These rules are **mandatory** and override all other instructions:

1. **EXTRACT ONLY what appears in the document text.** Do not add cases from your training data that are not mentioned in this specific document. Even if you know that a particular landmark case is relevant to the topic, if the document does not reference it, do NOT extract it.

2. **The `raw_text` field must be a VERBATIM substring of the document.** Copy-paste the exact passage. Do not paraphrase, normalize, translate, or edit. If you cannot point to the exact passage in the document where this citation appears, do not include it. Critically: `raw_text` must be the passage **where the case name appears** — the sentence or clause containing the reference. It must NOT be a quote from the cited case's own text. For example, if the document quotes a passage from Chapman v Hearse, the `raw_text` should be the sentence that says "observations made in _Chapman v Hearse_...", NOT the quoted holding itself.

3. **Same subject matter is NOT a citation.** Two cases about sea level rise do not cite each other unless one explicitly names the other. Topical overlap is not a citation.

4. **Do NOT fabricate case names, court names, docket numbers, or years.** If the document says "a French court ruled in 2019..." without naming the case, you may extract this as a narrative reference with low confidence, but do NOT guess the case name.

5. **Do NOT reproduce knowledge base metadata format.** If you see text matching the pattern `Case Name (YYYY) | Court; Jurisdiction` — this is Sabin database metadata contamination, not a citation. Skip it.

6. **Anachronism check:** If the document year is known (from frontmatter), any citation referencing a year more than 1 year AFTER the document year is almost certainly an error. Flag it with confidence 0.1 and note "ANACHRONISTIC" in the extraction_notes.

7. **Self-check before including each citation:**
   
   - Can I point to the exact passage in the document? If not → REMOVE
   - Is the case name actually written in the document? If not → REMOVE
   - Is my `raw_text` a verbatim substring of the document? If not → FIX or REMOVE

### 2.8 Per-Citation Metadata to Extract

For **each** extracted citation, provide ALL of the following fields:

| Field              | Type     | Description                                                                                                                                                                            | Required        |
| ------------------ | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------- |
| `citation_index`   | int      | Sequential index (1, 2, 3...)                                                                                                                                                          | Yes             |
| `case_name`        | string   | Name of the cited case as it appears in the document                                                                                                                                   | Yes             |
| `raw_text`         | string   | **VERBATIM** passage from the document containing the citation — include enough surrounding text (the sentence or clause) to show context. Must be an exact substring of the document. | Yes             |
| `cited_court`      | string   | Name of the court that issued the cited decision, if identifiable from the text                                                                                                        | If identifiable |
| `case_number`      | string   | Docket number, reference number, or case number (e.g., "No. 18-36082", "1 BvR 2656/18", "T-300")                                                                                       | If present      |
| `cited_year`       | int/null | Year of the cited decision                                                                                                                                                             | If identifiable |
| `confidence`       | float    | 0.0–1.0, how confident you are this is a genuine judicial decision reference                                                                                                           | Yes             |
| `functional_use`   | string   | One of: `aligned`, `contested`, `avoided`, `invoked`, `dismissed` (see Section 1.6)                                                                                                    | Yes             |
| `opinion_type`     | string   | One of: `majority`, `dissent`, `concurrence`, `unclear`                                                                                                                                | Yes             |
| `origin_country`   | string   | Country of origin of the cited case (e.g., "Netherlands", "United States")                                                                                                             | Best effort     |
| `origin_region`    | string   | `Global North`, `Global South`, or `International`                                                                                                                                     | Best effort     |
| `origin_court`     | string   | Full name of the court (e.g., "Supreme Court of the Netherlands", "Hoge Raad")                                                                                                         | If identifiable |
| `citation_pattern` | string   | Which pattern from Section 2.6 this matches (e.g., "traditional", "narrative", "shorthand")                                                                                            | Yes             |
| `extraction_notes` | string   | Any notes about ambiguity, uncertainty, or special circumstances                                                                                                                       | If applicable   |

### 2.9 Origin Identification (Initial)

The Extractor performs a **best-effort** initial origin identification. This will be reviewed and corrected by Agent 2.

**Approach (CHANGE-1/CHANGE-2):** There is no dictionary lookup or regex pattern matching. The agent reasons directly from the citation text to determine origin.

**Reasoning strategy:**

1. **Court name:** If the citation names a court (e.g., "UK Supreme Court", "Corte Constitucional de Colombia"), that directly identifies the origin.
2. **Citation format:** Legal citation formats are jurisdiction-specific:
   - `"347 U.S. 483"` → United States (U.S. Reports)
   - `"[2017] UKSC 5"` → United Kingdom
   - `"[2014] FCA 1093"` → Australia (Federal Court)
   - `"ECLI:NL:HR:2019:2007"` → Netherlands
   - `"BVerfG, 1 BvR 2656/18"` → Germany
   - `"Sentencia T-300"` → Colombia (Constitutional Court tutela)
   - `"RE 654.833/AC"` → Brazil (STF)
3. **Case name patterns:** Language and naming conventions provide clues:
   - `"Minister for the Environment v. ..."` → likely Ireland or Australia
   - `"Reference re ..."` → Canada (constitutional reference)
   - `"Conseil d'État, ..."` → France
4. **Context:** The surrounding text may state the origin: `"In the Australian case of..."`
5. **Document's own jurisdiction:** If the source document is from country X and the citation uses domestic formats without specifying a foreign court, it is likely domestic.

**Confidence guidelines:**

- Court explicitly named + format matches → 0.90–1.0
- Format strongly suggests a jurisdiction → 0.75–0.90
- Contextual inference only → 0.50–0.75
- Cannot determine → set `origin_country: null`, confidence 0.0

**Do NOT default to domestic.** If you cannot determine the origin, say so with null and low confidence. The fallback-to-domestic assumption from the pipeline has been removed.

### 2.10 Sabin Advisory Match (CHANGE-3)

After extraction, if the agent recognizes a citation as corresponding to a known climate litigation case from the Sabin Center database, it should note this in `extraction_notes`. However:

- The Sabin match is **advisory only** — it does NOT cause discarding
- All citations are kept regardless of whether they match a Sabin case
- The match (if any) is recorded for the domain expert to review later

The agent does not have access to the full Sabin database during extraction. Post-extraction Sabin matching will be performed by a separate script.

### 2.11 Confidence Scoring Guidelines

| Confidence | Meaning                                                  | Examples                                                                                         |
| ---------- | -------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| 0.95–1.0   | Certain — formal citation with full details              | `"Urgenda Foundation v. State of the Netherlands, Hoge Raad, 20 Dec 2019, ECLI:NL:HR:2019:2007"` |
| 0.80–0.95  | High — clear reference, minor ambiguity                  | `"the Urgenda case"` (well-known, context is clear)                                              |
| 0.60–0.80  | Moderate — reference is present but details are sparse   | `"a Dutch court ruled in 2015..."` (no case name given, but identifiable)                        |
| 0.40–0.60  | Low — uncertain if this is a judicial decision           | `"following Abraham"` (could be a case name or a person)                                         |
| 0.10–0.40  | Very low — likely not a citation but included for review | Anachronistic reference, ambiguous text                                                          |
| 0.0        | Cannot determine if this is a citation                   | Flagged for manual review only                                                                   |

### 2.12 Output JSON Schema (Agent 1)

```json
{
  "document_id": "uuid-from-frontmatter",
  "case_id": "case-slug-from-frontmatter",
  "source_jurisdiction": "Country",
  "source_region": "Global North|Global South|International",
  "source_year": 2020,
  "quality_check": "OK|SKIPPED_GARBLED|SKIPPED_EMPTY",
  "extraction_timestamp": "2026-04-08T12:00:00Z",
  "total_citations_found": 15,
  "citations": [
    {
      "citation_index": 1,
      "case_name": "Urgenda Foundation v. State of the Netherlands",
      "raw_text": "As the Hoge Raad held in Urgenda Foundation v. State of the Netherlands (ECLI:NL:HR:2019:2007), the State has a duty...",
      "cited_court": "Hoge Raad (Supreme Court of the Netherlands)",
      "case_number": "19/00135",
      "cited_year": 2019,
      "confidence": 0.98,
      "functional_use": "aligned",
      "opinion_type": "majority",
      "origin_country": "Netherlands",
      "origin_region": "Global North",
      "origin_court": "Hoge Raad",
      "citation_pattern": "traditional",
      "extraction_notes": null
    }
  ],
  "extraction_notes": "General notes about the extraction process for this document"
}
```

---

## 3. AGENT 2 — VERIFIER-ENRICHER

### 3.1 Mandate

**MAXIMUM PRECISION.** Verify that every citation extracted by Agent 1 actually exists in the document. Prune false positives. Finalize all classifications. The output of Agent 2 is the **final record of truth**.

### 3.2 Input

Agent 2 receives TWO inputs:

1. **The same Markdown document** (with YAML frontmatter) that Agent 1 processed
2. **Agent 1's JSON output** (the full extraction result from Section 2.12)

### 3.3 Verification Protocol

For **each citation** in Agent 1's output:

1. **Search** the document for the case name and/or raw_text
2. **Verify** that the reference is actually present — not a hallucination
3. **Verify** that the reference is to a **judicial decision** (not a treaty, statute, academic article)
4. **Verify** that the `raw_text` is a faithful verbatim substring of the document

### 3.4 Verdict Categories

Each citation receives a verification verdict:

| Verdict         | Meaning                                                                                          | Action                                                                                                                  |
| --------------- | ------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------- |
| `CONFIRMED`     | Citation found in document, verified as a judicial decision reference                            | Keep — extract verbatim snippet                                                                                         |
| `NOT_FOUND`     | Case name not found anywhere in the document                                                     | Flag for manual review. Possible hallucination.                                                                         |
| `MISATTRIBUTED` | A similarly-named but different case is referenced                                               | Provide `corrected_case_name`. Flag for manual review.                                                                  |
| `NOT_A_CASE`    | The reference exists but is to a treaty, statute, academic article, or other non-judicial source | Discard with reason.                                                                                                    |
| `DUPLICATE`     | This citation is a repeat of another citation in the list (same case, different textual mention) | Mark as duplicate, point to the primary citation_index. Counting rule: one citation per unique case per document (D22). |

### 3.5 Verification Rules (Detailed)

1. A **keyword match alone is NOT sufficient.** The word "Wells" appearing in "exploratory wells" is NOT a citation to "R(Wells) v Secretary of State". The reference must be to a judicial decision in context.

2. **Citation context must be appropriate:** Look for footnotes, case law sections, "see also" references, party names in case captions, comparative law discussions. A word that matches a case name but appears in an unrelated context (geography, common noun, surname in a non-legal context) is NOT a citation.

3. **Ibid. / Id. / Supra tracking:** If the document uses back-references (ibid., id., supra note X), trace them back to the original citation. The back-reference counts as a mention of the same case, not a separate citation. This affects the deduplication/counting logic.

4. **Multi-instance disambiguation:** If a case name could refer to multiple proceedings (e.g., "Juliana" could be the US domestic case or the IACtHR petition), use the document's context to determine which instance is being cited:
   
   - Does the text name a specific court? → Use that court
   - Is the citing court a member of a relevant international body? → Consider which instance is more likely
   - If ambiguous → flag for manual review with note "MULTI_INSTANCE_AMBIGUOUS"

### 3.6 Verbatim Snippet Extraction

For each `CONFIRMED` citation, extract a **verbatim snippet** — a passage of 1–3 sentences from the document that contains the citation in context. This snippet:

- Must be an **exact substring** of the document (no paraphrasing)
- Should include enough context to understand how the citation is used
- Should be between 100–500 characters (longer if needed for context)
- Must preserve original language, punctuation, and formatting

### 3.7 Origin Finalization

Review Agent 1's origin identification. Confirm or correct:

- `origin_country`: Is this correct given the cited court and citation format?
- `origin_region`: Does this match the country classification in Appendix A?
- `origin_court`: Is the court name accurate and complete?

If Agent 1 set `origin_country: null` (could not determine), Agent 2 should make a second attempt using the full document context — sometimes earlier passages introduce a case with full details, and later passages use shorthand.

### 3.8 Functional Use Finalization

Review Agent 1's functional classification. The Verifier has the advantage of seeing ALL citations together + the full document, which provides better context for classification.

Check each citation against the Nollkaemper criteria (Section 1.6):

- **invoked:** Is this genuinely a party's argument being reported, not the court's own reasoning?
- **aligned:** Does the court actually adopt or follow this citation?
- **contested:** Does the court engage with and then reject/distinguish?
- **avoided:** Does the court mention but decline to engage substantively?

**Common correction pattern:** Agent 1 may classify a citation as `aligned` when it is actually `invoked` (because the court quotes a party's argument that cites the case). The surrounding text is key: "The plaintiff argued, citing Urgenda, that..." → `invoked`, not `aligned`.

### 3.9 Sixfold Classification

Using the verified origin and the source metadata from the frontmatter, classify each citation into the sixfold typology (Section 1.5).

**Classification algorithm (D29 + D38 same-body rule applied first):**

```
source_region       = frontmatter.region
target_region       = citation.origin_region
source_jurisdiction = frontmatter.jurisdiction
target_jurisdiction = citation.origin_country
source_court        = frontmatter (or inferred from document_title)
target_court        = citation.origin_court

# D29 + D38 — same-court / same-system rule, applied BEFORE the sixfold algorithm
# Split by body type per D38 (2026-05-03)
IF source_court == target_court
   OR (source and target belong to the same court system, e.g., CJEU & General Court, ECtHR Grand Chamber & Chamber, WTO AB & WTO Panel, US 9th Circuit & US Supreme Court):
    IF source_region == "International":
        → Type 4: "Inter-System Citation"   # D38: intra-international stays transnational
        is_vertical_dialogue = false
    ELSE:
        → "Domestic"                         # D29: intra-national is domestic
        is_vertical_dialogue = false

ELSE IF source_jurisdiction == target_jurisdiction:
    → "Domestic"
    is_vertical_dialogue = false

ELSE IF source_region IN ("Global North", "Global South"):
    IF target_region IN ("Global North", "Global South"):
        → Type 1: "Foreign Citation"
        is_vertical_dialogue = false
    ELSE IF target_region == "International":
        IF source_jurisdiction is MEMBER of the cited international court (Appendix B):
            → Type 2: "International Citation"
            is_vertical_dialogue = true        # D30 — set true ONLY here
        ELSE:
            → Type 3: "Foreign International Citation"
            is_vertical_dialogue = false

ELSE IF source_region == "International":
    IF target_region == "International":
        → Type 4: "Inter-System Citation"
        is_vertical_dialogue = false
    ELSE IF target_region IN ("Global North", "Global South"):
        IF target_jurisdiction is MEMBER of the source international court (Appendix B):
            → Type 5: "Member-State Citation"
            is_vertical_dialogue = false
        ELSE:
            → Type 6: "Non-Member Citation"
            is_vertical_dialogue = false

ELSE:
    → "Unclassified"
    is_vertical_dialogue = false
```

**Court-membership matching:** To determine if a country is a "member" of an international court, consult **Appendix B**. The source court's identity must be mapped to one of the international courts (IACtHR, ECtHR, ACHPR, ICJ, ITLOS, CJEU, etc.). Semantic patterns to recognize:

- "European Union" / "CJEU" / "ECJ" → Court of Justice of the EU
- "Council of Europe" / "ECtHR" / "ECHR" → European Court of Human Rights
- "Inter-American" / "IACtHR" / "Corte IDH" → Inter-American Court
- "African" / "ACtHPR" / "ACHPR" → African Court
- "ICJ" / "International Court of Justice" → ICJ (universal jurisdiction)
- "ITLOS" → ITLOS (universal jurisdiction)
- "WTO" / "World Trade" → WTO Appellate Body
- "ICSID" → ICSID

ICJ and ITLOS have **universal jurisdiction** — all UN / UNCLOS members are considered members for the purposes of this study.

### 3.10 Manual Review Flagging

A citation is flagged for manual review (`requires_manual_review: true`) if ANY of the following apply:

- Verification verdict is `NOT_FOUND`, `MISATTRIBUTED`, or `NOT_A_CASE`
- Origin confidence < 0.7
- Sixfold type is `Unclassified`
- Functional use could not be determined (set as default with low confidence)
- Multi-instance ambiguity detected
- Anachronistic year detected
- Agent 1 confidence < 0.5

The `manual_review_reason` field should contain a brief explanation.

### 3.11 Counting Rules (D22)

**One citation per unique case per document.** If a document references "Urgenda" 15 times across its text, this counts as **1 citation** of Urgenda by this document.

Implementation: Agent 2 deduplicates by `case_name` (normalized — case-insensitive, ignoring minor formatting differences). Duplicate entries receive verdict `DUPLICATE` pointing to the primary citation.

The **primary citation** should be the one with the highest confidence and the most complete metadata. Subsequent mentions are recorded as duplicates but are not counted separately.

### 3.12 Output JSON Schema (Agent 2 — Final)

> **Output destination (D37):** The verified citation JSON is intended for ingestion into the new `citation_agent_v1*` tables in the `climate_litigation` database (NOT the v7 tables, which are frozen as a methodological baseline). The agent itself does not write to the DB — a downstream script ingests the JSON. This is informational only; the agent's job stops at producing valid JSON.

```json
{
  "document_id": "uuid-from-frontmatter",
  "case_id": "case-slug-from-frontmatter",
  "source_jurisdiction": "Country",
  "source_region": "Global North|Global South|International",
  "source_year": 2020,
  "verification_timestamp": "2026-04-08T12:30:00Z",
  "total_citations_extracted": 15,
  "total_confirmed": 12,
  "total_not_found": 1,
  "total_misattributed": 0,
  "total_not_a_case": 1,
  "total_duplicates": 1,
  "unique_citations_confirmed": 11,
  "citations": [
    {
      "citation_index": 1,
      "verification_verdict": "CONFIRMED",
      "case_name": "Urgenda Foundation v. State of the Netherlands",
      "raw_text": "As the Hoge Raad held in Urgenda Foundation v. State of the Netherlands (ECLI:NL:HR:2019:2007), the State has a duty...",
      "verbatim_snippet": "As the Hoge Raad held in Urgenda Foundation v. State of the Netherlands (ECLI:NL:HR:2019:2007), the State has a duty to protect the right to life and well-being of its citizens under Articles 2 and 8 ECHR.",
      "cited_court": "Hoge Raad (Supreme Court of the Netherlands)",
      "case_number": "19/00135",
      "cited_year": 2019,
      "confidence": 0.98,
      "functional_use": "aligned",
      "functional_use_confidence": 0.95,
      "opinion_type": "majority",
      "origin_country": "Netherlands",
      "origin_region": "Global North",
      "origin_court": "Hoge Raad",
      "sixfold_type": "Foreign Citation",
      "is_vertical_dialogue": false,
      "citation_pattern": "traditional",
      "requires_manual_review": false,
      "manual_review_reason": null,
      "is_duplicate_of": null,
      "verification_notes": null
    },
    {
      "citation_index": 7,
      "verification_verdict": "NOT_FOUND",
      "case_name": "Smith v. Environment Agency",
      "raw_text": "...",
      "verbatim_snippet": null,
      "confidence": 0.0,
      "is_vertical_dialogue": false,
      "requires_manual_review": true,
      "manual_review_reason": "Verification: NOT_FOUND — case name not present in document text. Likely hallucination.",
      "is_duplicate_of": null,
      "verification_notes": "Agent 1 extracted this with confidence 0.45. Unable to locate in document."
    },
    {
      "citation_index": 12,
      "verification_verdict": "DUPLICATE",
      "case_name": "Urgenda Foundation v. State of the Netherlands",
      "raw_text": "...the Urgenda precedent...",
      "confidence": 0.95,
      "is_vertical_dialogue": false,
      "is_duplicate_of": 1,
      "verification_notes": "Second mention of Urgenda. Primary citation at index 1."
    }
  ],
  "summary": {
    "confirmed_unique": 11,
    "by_sixfold_type": {
      "Foreign Citation": 5,
      "International Citation": 2,
      "Foreign International Citation": 0,
      "Inter-System Citation": 0,
      "Member-State Citation": 0,
      "Non-Member Citation": 0,
      "Domestic": 4,
      "Unclassified": 0
    },
    "by_functional_use": {
      "aligned": 6,
      "contested": 2,
      "avoided": 1,
      "invoked": 1,
      "dismissed": 1
    },
    "by_origin_region": {
      "Global North": 7,
      "Global South": 1,
      "International": 2,
      "Domestic": 4,
      "Unknown": 0
    },
    "vertical_dialogue_count": 2,
    "flagged_for_review": 1
  }
}
```

**Field reference (new fields added in v1.1):**

- `is_vertical_dialogue` (bool, **required on every citation**) — `true` ONLY when source = national court AND target = international court of which source country is a member (D30). `false` everywhere else, including for Domestic, Type 1, Type 3, Type 4, Type 5, Type 6, and any verdict other than CONFIRMED.
- `functional_use` enum gains `dismissed` (D31) — see Section 1.6.

---

## 4. Known Edge Cases & Disambiguation Rules

### 4.1 The Juliana Problem (Multi-Instance Litigation)

The same case can be litigated in multiple courts across different jurisdictions. **Juliana v. United States** exists both as a US domestic case (9th Circuit) and as a petition before the Inter-American Commission. **Klimaseniorinnen** exists as a Swiss domestic case and an ECtHR case.

**Rules:**

- If the citing text names a specific court → use that court's jurisdiction
- If the citing text references a specific proceeding stage ("on appeal before the 9th Circuit") → use that court
- If ambiguous: check the context — an IACtHR decision citing "Juliana" likely means the US domestic case (as precedent), while a Colombian court might mean either
- If still ambiguous → extract both possible interpretations in `extraction_notes`, flag for manual review

### 4.2 Abbreviation Ambiguity

Some abbreviations are shared between courts:

| Abbreviation | Possible Courts                                               | Disambiguation Rule                                                                    |
| ------------ | ------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| FCA          | Federal Court of Australia / Federal Court of Appeal (Canada) | Check citation format: `[YYYY] FCA` = Australia; `FCA` with Canadian reporter = Canada |
| SC           | Supreme Court (many countries)                                | Requires additional context (reporter, jurisdiction mention)                           |
| HC           | High Court (many common law jurisdictions)                    | Requires additional context                                                            |
| CA           | Court of Appeal (many jurisdictions)                          | Requires additional context                                                            |

**Rule:** If abbreviation alone cannot disambiguate, check:

1. The citation format (reporter names, numbering style)
2. The language of the surrounding text
3. The source document's jurisdiction (domestic citation is most likely)
4. Other citations in the same passage (clustering by jurisdiction)

### 4.3 Non-English Citations

Documents may cite cases in their original language. Common patterns:

| Language   | Court/Case Patterns                                                                                |
| ---------- | -------------------------------------------------------------------------------------------------- |
| Portuguese | "Recurso Extraordinário", "Ação Direta de Inconstitucionalidade (ADI)", "Supremo Tribunal Federal" |
| Spanish    | "Sentencia T-300", "Corte Constitucional", "Corte Suprema de Justicia", "tutela"                   |
| French     | "Conseil d'État", "Conseil Constitutionnel", "Cour de cassation", "arrêt"                          |
| German     | "Bundesverfassungsgericht", "BVerfG", "Beschluss", "Urteil"                                        |
| Dutch      | "Hoge Raad", "Rechtbank Den Haag", "uitspraak", "arrest"                                           |
| Norwegian  | "Høyesterett", "Oslo tingrett", "kjennelse", "dom"                                                 |

The agent should recognize these patterns and correctly identify the origin country.

### 4.4 Self-Citation Scope (D29 + D38)

**Domestic citations** (same national jurisdiction OR same national court system) are extracted and tagged as "Domestic" but are NOT classified in the sixfold system (they fall outside the transnational dialogue research question). They are still valuable data for completeness and should not be discarded.

**Same-court self-citations** are split by body type per the D38 refinement (2026-05-03):

- **National same-court** (UK Supreme Court → its own prior decision; US 9th Circuit → US Supreme Court; German BVerfG → German Federal Administrative Court; Brazilian STF → STJ) → **Domestic** (intra-national hierarchy is out of scope).
- **International same-body** (CJEU → CJEU; CJEU → General Court; ECtHR Grand Chamber → ECtHR Chamber; IACtHR Advisory → IACtHR Contentious; WTO Appellate Body → WTO Panel) → **Inter-System Citation (Type 4)** (intra-international citations are still transnational dialogue).

The same-body rule applies BEFORE the sixfold algorithm.

### 4.5 Advisory Opinions vs. Contentious Cases

Advisory opinions from international courts (ICJ, IACtHR) should be classified as emanating from that international court. They are NOT domestic citations even though they may concern a specific country's situation.

### 4.6 EU Law Specifics

- **CJEU/ECJ** decisions → origin: "International" (for EU member states) or "Foreign International" (for non-EU states)
- **EU Directives and Regulations** → these are NOT judicial decisions (they are legislation). Do not extract.
- **Advocate General opinions** → these ARE quasi-judicial opinions from the CJEU process. Extract them as CJEU citations.

---

## Appendix A — Global North Countries (Definitive List)

**44 countries** — unified from UNCTAD geographic classification, UN WESP developed economies list (37 economies), Setzer & Higham/LSE Global Trends methodology, and Sabin Center classification.

**Core Group (established in all sources):**

- United States, United Kingdom, Canada, Australia, New Zealand
- Germany, France, Netherlands, Belgium, Switzerland, Austria
- Sweden, Norway, Denmark, Finland, Iceland, Ireland
- Italy, Spain, Portugal, Greece
- Japan, South Korea, Singapore

**EU Member States (added per FIX-2 — previously missing, caused misclassification bugs):**

- Poland, Czech Republic, Hungary, Romania, Bulgaria, Croatia
- Slovakia, Slovenia, Estonia, Latvia, Lithuania
- Luxembourg, Malta, Cyprus

**Contested (included with footnote):**

- Israel — classified as "developed economy" by UN WESP and IMF; included in Global North for this study
- Turkey (Turkiye) — ECtHR member, OECD member, classified as "developed" by some sources; included in Global North
- Russia — contested; pre-2022 classified as developed by some metrics; **included in Global North with footnote** (classification may be revisited)
- Taiwan — classified as "developed economy" by IMF and World Bank; **included in Global North with footnote** (political status contested)

**Reclassified as International (NOT in Global North list):**

- European Union → International
- Council of Europe → International

**Classification rule:** Any country NOT in this list defaults to **Global South**.

---

## Appendix B — International Court Membership

### Inter-American Court of Human Rights (IACtHR)

**20 member states** (countries that have accepted contentious jurisdiction):

Argentina, Barbados, Bolivia, Brazil, Chile, Colombia, Costa Rica, Dominican Republic, Ecuador, El Salvador, Guatemala, Haiti, Honduras, Mexico, Nicaragua, Panama, Paraguay, Peru, Suriname, Uruguay

### European Court of Human Rights (ECtHR)

**46 member states** (Council of Europe members):

Albania, Andorra, Armenia, Austria, Azerbaijan, Belgium, Bosnia and Herzegovina, Bulgaria, Croatia, Cyprus, Czech Republic, Denmark, Estonia, Finland, France, Georgia, Germany, Greece, Hungary, Iceland, Ireland, Italy, Latvia, Liechtenstein, Lithuania, Luxembourg, Malta, Moldova, Monaco, Montenegro, Netherlands, North Macedonia, Norway, Poland, Portugal, Romania, San Marino, Serbia, Slovakia, Slovenia, Spain, Sweden, Switzerland, Turkey, Ukraine, United Kingdom

### African Court on Human and Peoples' Rights (ACHPR)

**34 member states** (countries that have ratified the Protocol):

Algeria, Benin, Burkina Faso, Burundi, Cameroon, Chad, Comoros, Congo, Cote d'Ivoire (Ivory Coast), Gabon, Gambia, Ghana, Guinea-Bissau, Kenya, Lesotho, Libya, Malawi, Mali, Mauritania, Mozambique, Niger, Nigeria, Rwanda, Senegal, South Africa, Tanzania, Togo, Tunisia, Uganda, Western Sahara, Zambia, Zimbabwe

### Courts with Universal Jurisdiction

These courts are considered binding on ALL countries for the purposes of the sixfold classification:

- **International Court of Justice (ICJ)** — principal judicial organ of the UN
- **International Tribunal for the Law of the Sea (ITLOS)** — established under UNCLOS

### Other International Courts/Bodies

These are international courts that may appear in citations but do not have the same membership structure as the three regional human rights courts:

- **Court of Justice of the European Union (CJEU/ECJ)** — jurisdiction over EU member states
- **WTO Appellate Body** — WTO dispute settlement
- **ICSID** — international investment arbitration
- **International Criminal Court (ICC)** — international criminal jurisdiction
- **Permanent Court of Arbitration (PCA)** — inter-state arbitration

For these courts, membership should be determined case-by-case based on the specific treaty or agreement.

---

## Appendix C — Nollkaemper Typology Reference

**Source:** Andre Nollkaemper, "Avoid, Align or Contest? An Examination of National Courts' Postures in International Climate Law Litigation," *Transnational Environmental Law*, Vol. 14(3), November 2025, pp. 469-499. DOI: 10.1017/S2047102525100058.

**Origin:** ILA Study Group on "Principles on the Engagement of Domestic Courts with International Law" (2011-2016), led by Tzanakopoulos, Nollkaemper, Shany & Methymaki.

### Typology (Case-Level → Citation-Level Adaptation)

**AVOIDANCE → `avoided`**
The court mentions a case but declines to engage substantively with its reasoning or holding. The cited case is acknowledged but set aside — the court does not adopt, follow, or reject it on the merits.

Sub-signals:

- Non-justiciability: "this is a matter for the legislature"
- Lack of standing: "the applicant lacks standing to invoke"
- Separation of powers: "not within the court's competence"
- Procedural: "need not address this point given our finding on..."

**ALIGNMENT → `aligned`**
The court engages substantively with the cited case and uses it to support or inform its own reasoning. The citation contributes to the court's conclusion.

Sub-signals:

- Fair weather: harmonizing domestic and international law where no tension exists
- Consubstantial: using international case law to give content to domestic norms (e.g., using Urgenda/Paris Agreement to interpret duty of care)
- Overriding: applying international precedent even against domestic law (rare)

**CONTESTATION → `contested`**
The court engages substantively with the cited case but ultimately rejects, distinguishes, or reinterprets it. Unlike avoidance (which sidesteps), contestation involves engagement followed by disagreement.

Sub-signals:

- Interpretive: reinterprets the cited case to narrow its applicability
- Distinguishing: finds factual or legal differences that make the precedent inapplicable
- Overruling: explicitly rejects the cited case's reasoning

**INVOCATION → `invoked`**
The court is reporting a party's argument — the citation is attributed to the plaintiff, defendant, or intervener, not to the court's own reasoning. This is a pre-posture category: the court has not yet taken a position on the cited case.

Key distinction: "The plaintiff argued, citing Urgenda, that..." → `invoked` (the plaintiff cites it, the court merely reports). "Following Urgenda, this court holds..." → `aligned` (the court itself relies on it).

---

*End of working document.*
