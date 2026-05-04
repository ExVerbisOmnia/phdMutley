# Metadata Misattribution Triage — Phase T1

**Date:** 2026-05-03
**Branch:** `feature/phase-dq`
**Investigator:** Claude (read-only, via `mcp__postgres__query` denied → psycopg2 over `DB_CONFIG`)
**Trigger:** Juliana doc `4da6a9cf-9d3c-518f-a0d9-ebb49f771db7` discovered to be a US Ninth Circuit opinion misattributed to IACommHR (the case has 4 docs sharing the IACommHR `case_id`; only this one has extracted text + 30 hallucinated-origin citations).

## 1. Method

Two passes over `cases ⨝ documents ⨝ citation_extraction_phased`:

- **Pass A (broad LIKE on jurisdiction):** 69 docs with ≥3 extracted citations under any jurisdiction containing "international", "tribunal", "arbitral", "inter-american", "european court", etc. Issue: this swept in legitimate national tribunals (Australian VCAT, NZ Immigration & Protection Tribunal, US CIT, Australian AAT) — they are correctly labelled and their citations naturally concentrate in the home country, producing false-positive 100% scores.
- **Pass B (narrow — truly international jurisdictions only):** 50 docs. Excluded national tribunals. Score = % of citations whose `case_law_origin` resolves to a single **non-international** national jurisdiction (excluding "International", "United Nations", "Council of Europe" — those are legitimately international origins for ECtHR/ICJ docs).

Pass B is the relevant denominator. Distribution of national-citation concentration:

| concentration | docs |
|---|---|
| ≥80% | 0 |
| 50–79% | 3 |
| 20–49% | 0 |
| 1–19% | 3 |
| 0% | 44 |

Only **3 docs** in the entire international-jurisdiction corpus have ≥50% citations from a single national jurisdiction.

## 2. Sample classification (20 docs)

Top 5 by national-concentration plus 15 random from the remaining 45.

| # | doc_id (8) | case_name | DB jurisdiction | actual court (from text) | natl% | classification |
|---|---|---|---|---|---|---|
| 1 | `4da6a9cf` | Juliana Youth v. United States | IACommHR | **US Ninth Circuit Court of Appeals** | 70% | **Confirmed misattribution** |
| 2 | `191899bd` | Woodhouse / West Cumbria Mining v. UK | ICSID Arbitral Tribunal | **UK High Court of Justice (KBD, Planning)** [2024] EWHC 2349 (Admin) | 50% | **Confirmed misattribution** |
| 3 | `7f438b61` | Ville de Paris v. EC | ECJ (EU) | EU General Court (Joined Cases T-339/16) | 50% | False positive (Belgium tag = co-applicant Ville de Bruxelles; doc is genuinely EU) |
| 4 | `b9d470c6` | Czech Republic v Poland (Turów) | ECJ (EU) | ECJ Vice-President Order, Case C-121/21 R | 12.5% | False positive |
| 5 | `4cfa6b76` | IACtHR climate advisory opinion | International Courts | IACtHR AO-32/25 | 3.2% | False positive |
| 6 | `dfea175b` | Carême v. France | International Courts | ECtHR Grand Chamber | 0% | Correct |
| 7 | `b3ec484a` | ŠKO-Energo s.r.o. | ECJ (EU) | ECJ (Second Chamber) | 0% | Correct |
| 8 | `0ebe76fb` | Engels v. Germany | International Courts | ECtHR Fourth Section | 0% | Correct |
| 9 | `83c750a0` | De Conto v. Italy + 32 | ECtHR | ECtHR First Section | 0% | Correct |
| 10 | `a6ebba34` | Trinseo v. Germany | ECJ (EU) | ECJ AG Opinion | 0% | Correct |
| 11 | `a1b0b88b` | Cube Infrastructure v. Spain | Arbitral Tribunal | ICSID Annulment Decision | 0% | Correct |
| 12 | `5abd7670` | PPC Power v. Slovak Fin. Dir. | ECJ | ECJ Sixth Chamber | 0% | Correct |
| 13 | `20701a68` | IACtHR AO-23/17 (summary) | IACtHR | IACtHR Official Summary | 0% | Correct |
| 14 | `771519c9` | Poland v. EP, Council | ECJ | ECJ Second Chamber | 0% | Correct |
| 15 | `4c7aa06d` | ExxonMobil v. Germany | ECJ | ECJ Fifth Chamber | 0% | Correct |
| 16 | `8f1e8b02` | Müllner v. Austria | International Courts | ECtHR Fourth Section communication | 0% | Correct |
| 17 | `51682fad` | IACtHR AO-23/17 (full) | IACtHR | IACtHR Advisory Opinion | 0% | Correct |
| 18 | `c3b0afb0` | ArcelorMittal v. Luxembourg | ECJ | ECJ Fifth Chamber | 0% | Correct |
| 19 | `ee2a2157` | ITLOS Small Island States AO | ITLOS | ITLOS Advisory Opinion | 0% | Correct |
| 20 | `e2b2aef2` | Deutsche Umwelthilfe v. Germany | ECJ | ECJ Grand Chamber | 0% | Correct |

**Sample result:** 2 confirmed misattributions / 20 sampled (10%); 18 correct or false-positive.

## 3. Cross-validation findings

- **Juliana case has 4 documents under one `case_id`.** Three (`8e939db0`, `f927cdfc`, `76807720`) have empty `extracted_text` (PDF extraction failed/empty; 0 citations). Only `4da6a9cf` carries the bad citations. Fix should target the document, not the case (this is a classic **multi-document-case** scenario where the IACommHR petition really exists — likely one of the empty docs — but the published Ninth Circuit opinion was filed under the same Sabin entry).
- **Woodhouse / West Cumbria Mining v. UK** also has multi-doc structure. Its case_id is the ICSID arbitration, but doc `191899bd` is the related UK High Court ruling on West Cumbria coal mine planning permission. Two other docs in the case (`25090e85`, `72140980`) are correctly tagged as "High Court of Justice — England and Wales" / United Kingdom — so the data has the right metadata available, just attached to the wrong document.
- **2,278 of 4,739 cases (48%) have multiple documents** — supporting the multi-document-case hypothesis at the corpus scale.
- All 5 random "0% concentration" docs verified: correctly attributed.

## 4. Scope estimate

Manual sample yielded 2 misattributions (10%) but both were already at the top of the concentration ranking, where N is small (only 3 docs ≥50%). The remaining 47 docs in the truly-international set show citation distributions consistent with their stated jurisdictions.

**Estimated total confirmed misattributions in the truly-international corpus: 2 (range: 2–4).**

The signal is sharp: when a document is misattributed, its citations cluster heavily in the actual source jurisdiction (Juliana 70% US, Woodhouse 50% UK-via-US-tag). The 0% bucket is dominated by ECJ/ECtHR/IACtHR/ICJ/ICSID docs whose citations correctly resolve to "International" or supranational origins.

This is a **small** problem (<5 docs), not a systemic 100+ doc data-quality issue.

## 5. Recommendation

**Treat as small, surgical patch.** Two confirmed misattributions, both attributable to multi-document Sabin cases where one PDF was the international filing and another PDF (the actual ruling) was a national court decision filed under the same `case_id`.

### Proposed manual UPDATE statements (DO NOT execute — for user review)

```sql
-- Juliana Ninth Circuit opinion — split off into its own case_id and re-tag
-- Option A: minimal fix — overwrite document-level metadata (requires schema for per-doc jurisdiction; currently lives only on cases)
-- Option B: split case
-- Caveat: jurisdiction/geographies live on cases, not documents. Re-tagging the case
--   would corrupt the 3 sibling documents that ARE legitimate IACommHR petitions.
--
-- Recommended pattern: create a NEW case row for the US 9th Circuit ruling and re-point document_id.
-- INSERT INTO cases (case_id, case_name, jurisdiction, geographies, ...)
-- VALUES (gen_uuid(), 'Juliana v. United States (9th Cir.)',
--         'United States Court of Appeals - Ninth Circuit', 'United States', ...);
-- UPDATE documents SET case_id = <new_case_id> WHERE document_id = '4da6a9cf-9d3c-518f-a0d9-ebb49f771db7';

-- Woodhouse — same pattern, re-point doc 191899bd to a UK High Court case
-- (case 25090e85's case_id already exists for "West Cumbria Mining v. Cumbria County Council")
-- UPDATE documents SET case_id = (SELECT case_id FROM documents WHERE document_id = '25090e85-6a31-5b28-8bef-d14dbabb8e87')
-- WHERE document_id = '191899bd-2c01-5918-ab0f-cc289c81d7d5';
```

### Downstream impact

- **30 citation rows** in `citation_extraction_phased` for Juliana need re-classification (the v7 sixfold output is already corrupted; existing values like `case_law_origin = 'United States'` may actually be correct now that the source court is US 9th Circuit, but the sixfold direction flag will flip from "Int'l → National" to "National → National").
- **4 citation rows** for Woodhouse need re-classification (US tags on UK doc are the bigger concern; those need re-extraction, not just relabel).
- Recommend **rerunning Phase 1 (jurisdiction ID) → Phase 4 (sixfold classification) → Phase 5 (verification)** on these 2 docs after the case_id repair.

### Investigator artefacts (gitignored intermediates under `docs/reports/`)

- `_misattribution_candidates.json`, `_misattribution_candidates_v2.json`, `_misattribution_candidates_v3.json`
- `_misattribution_snippets.json`, `_misattribution_text_dump.txt`
- `_iac_docs_dump.txt`, `_misattribution_zero_dump.txt`, `_woodhouse_text.txt`
- Helper scripts: `scripts/investigate_misattribution.py` (v1 → v6)
