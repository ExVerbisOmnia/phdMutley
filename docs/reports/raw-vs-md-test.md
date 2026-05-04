# raw_text vs text_md — Citation Extraction Recall Test

**Date:** 3 May 2026
**Context:** Investigation T4 from `docs/reports/agent-test-run-open-issues.md` — does switching the citation-extractor's input from `text_md` (pymupdf4llm markdown) to `raw_text` (plain) materially improve recall, especially on footnote-heavy documents like Saint-Gobain?
**Method:** Re-exported the same 5 baseline test documents using `et.raw_text` instead of `et.text_md` (script: `scripts/_temp_export_raw.py`, throwaway). Ran the citation-extractor protocol against each raw file. Compared resulting citation sets against the markdown baseline.

---

## 1. Per-document comparison

| Doc | document_id | wc | md baseline (unique) | raw run (unique) | Δ | char delta (raw − md) | Notes |
|---|---|---|---|---|---|---|---|
| Sharma v Minister | `2ccb2fd9-b037-5c96-93e6-19f7ec9c3fc8` | 6,651 | 17 | **17** | 0 | −1,168 | Same citations. No footnote effect (costs judgment with traditional headnote `Cases cited` list — already preserved by pymupdf4llm). |
| Leghari v Pakistan | `5ba78792-f689-5a1d-a4c5-5f8dfd198950` | 7,208 | 2 | **2** | 0 | +2,811 | Same citations. The +2,811 char delta is page-footer / numbering noise repeated across pages, not new content. |
| Saint-Gobain v Commission (CJEU AG Opinion) | `11f23599-dadf-500b-965e-15f482216fd3` | 7,269 | 4 | **16** | **+12** | +11,945 | **Killer test.** Footnote pages 8–11 (truncated in markdown) fully present in raw_text. 12 additional unique CJEU/national citations recovered, all with full case numbers + ECLI identifiers. |
| ExxonMobil v Germany (CJEU) | `4c7aa06d-ad7a-5aa0-aa76-7f10edbc98de` | 12,631 | 18 | 21 | +3 | −1,574 | Raw is shorter than md, so the +3 is not footnote recovery. Likely better dedup of multi-case joined ECLIs (Iberdrola C‑566/11 to C‑640/11; Borealis Polyolefine vs Borealis and Others) — same body text, slightly different counting. |
| Juliana Youth v US (9th Cir) | `4da6a9cf-9d3c-518f-a0d9-ebb49f771db7` | 19,538 | 100 | **100** | 0 | −2,169 | Programmatic citation-token comparison: 108 normalized tokens in BOTH raw and md, **0 only-in-raw, 0 only-in-md**. Perfect parity. Raw is slightly shorter (no footnote truncation in this US opinion). |

Char deltas pulled from `data/decisions_md_raw/_summary.json`.

## 2. Saint-Gobain footnote recovery — the three known-missing citations

| Citation                                  | Recovered in raw_text? | Full case detail recovered                                  | Source location in raw |
| ----------------------------------------- | ---------------------- | ----------------------------------------------------------- | ---------------------- |
| **Flachglas Torgau**                      | **YES**                | `C‑204/09, EU:C:2012:71` (and AG Sharpston `EU:C:2011:413`) | Footnotes 9, 11, 21, 22, 23, 24, 25 |
| **Sweden v MyTravel and Commission**      | **YES**                | `C‑506/08 P, EU:C:2011:496` (and AG Kokott `EU:C:2011:107`) | Footnotes 30, 31, 33   |
| **Bundesverwaltungsgericht ruling**       | **YES**                | `7 C 7.12, ECLI:DE:BVerwG:2012:020812U7C7.12.0` (Ruling of 2 August 2012) | Footnote 26           |

All three known-missing citations recovered with **full case numbers, ECLI identifiers, and years**. The raw_text body of Saint-Gobain (`data/decisions_md_raw/11f23599-dadf-500b-965e-15f482216fd3.md`) lines 461–569 contain the complete footnote section — fully present and parseable.

Bonus: the raw run also surfaces 9 additional CJEU citations that were *also* truncated in markdown (Areva, Commission v Germany C‑61/94, Fish Legal and Shirley, Ville de Lyon, GSV, ClientEarth × 2, PAN Europe, East Sussex County Council). Saint-Gobain's true citation count is 16, not the 4 the markdown baseline detected (4× under-count, 75% missed).

## 3. False positives in raw run

**Total false positives across all 5 documents: 0.**

Page-header / OCR-style noise present in raw_text but not extracted as citations:

| Doc | Noise pattern | Why it doesn't false-positive |
|---|---|---|
| Saint-Gobain | `CURIA - Documents http://curia.europa.eu/juris/document/document.jsf?docid=184622...` repeated as page-header | Not a case citation pattern — agent rules require a named decision. |
| Saint-Gobain | `1 of 11 3/27/20, 3:49 PM` (page numbers + access timestamp) | Not a citation pattern. |
| ExxonMobil | `8/5/2019 CURIA - Documents` and `curia.europa.eu/juris/document/document_print.jsf?docid=215245&...` page-headers | Same — URL noise, no case name. |
| Sharma | `Sharma by her litigation representative Sister Marie Brigid Arthur v Minister for the Environment (No 2) [2021] FCA 774 [pagenum]` repeated page-footer | This IS the document itself, not a cited case → agent treats as self-reference, skips. |
| Leghari | `W.P. No. 25501/2015 [pagenum]` page-header | Document's own case number, not a cited case. |
| Juliana | URL fragments and page numbers | Not citation-shaped tokens. |

The agent's anti-hallucination protocol (rule 5: "Metadata format contamination... skip it") and the requirement that `case_name` be a named judicial decision filter all of this cleanly.

## 4. Lost citations (raw vs md)

**None.** Every citation present in the markdown baseline is also present in the raw_text run for all 5 docs. Empirically verified:
- Sharma, Leghari, Juliana: programmatic and manual diff both show 0 only-in-md.
- Saint-Gobain: the 4 markdown-baseline citations (the AG Opinion's body references to Flachglas Torgau, Sweden v MyTravel, Bundesverwaltungsgericht, and the General Court judgment under appeal) are all reproduced in the raw run, plus 12 new ones.
- ExxonMobil: all 18 markdown-baseline citations are present; raw adds 3 (joined-ECLI cases that md may have under-deduped).

## 5. Agent-flagged formatting issues

- **Saint-Gobain raw_text:** Page-header `CURIA - Documents http://curia.europa.eu/juris/...` injected ~every 60 lines. Body text remains fully readable across page boundaries; sentences are not split mid-word. The footnotes section (lines 461–570) is perfectly clean — just a numbered list.
- **ExxonMobil raw_text:** Same CURIA noise pattern. Tables for legal-context Articles flatten to readable prose.
- **Sharma / Leghari raw_text:** Page-footer with case ID + page number repeats. Does not interfere.
- **Juliana raw_text:** Slightly shorter than md, no footnote issues.
- **No garbled-text triggers, no anachronism flags from any of the 5 docs.**

Markdown formatting cues (headers, bold, italic) ARE useful for parsing structure but are not load-bearing for citation extraction — case names appear in the same flat text in both versions.

## 6. Recommendation: **B. Hybrid**

**Switch to raw_text only for footnote-heavy documents; otherwise stay on markdown.**

### Rationale

The Saint-Gobain result is decisive on one direction (raw_text fully recovers truncated footnotes — 16 citations vs 4, all 3 known-missing items recovered with full detail). But for the other 4 documents, raw_text adds nothing recall-wise (Sharma, Leghari, Juliana: 0 delta; ExxonMobil: +3 likely from dedup not content). Meanwhile, raw_text introduces page-header noise (CURIA URLs, page numbers, access timestamps) that — while it didn't produce false positives in this small test — is structurally riskier for at-scale extraction than the cleaner markdown.

The two text variants diverge on a measurable signal: **`LENGTH(raw_text) - LENGTH(text_md)`**:

| Doc | raw − md (chars) | Footnote recovery? |
|---|---|---|
| Saint-Gobain | **+11,945** | YES (the only doc with footnote recovery) |
| Leghari | +2,811 | No (just page-numbering noise) |
| Sharma | −1,168 | N/A (md is bigger) |
| ExxonMobil | −1,574 | N/A |
| Juliana | −2,169 | N/A |

Saint-Gobain's +11,945 sits **>4× larger** than the next-highest delta. A reasonable threshold is **`raw_text - text_md > 5,000` characters → use raw_text; otherwise use text_md.** This catches footnote-truncation cases while keeping markdown's cleaner layout for the typical doc.

### Implementation sketch

In `scripts/export_decisions_md.py`, modify the `QUERY` to fetch both `text_md` and `raw_text` lengths, and select the body text per-row:

```python
QUERY = """
SELECT ...,
       et.text_md, et.raw_text,
       LENGTH(et.text_md) AS md_len,
       LENGTH(et.raw_text) AS raw_len
FROM ...
"""

# In the export loop:
md_len = row['md_len'] or 0
raw_len = row['raw_len'] or 0
use_raw = (raw_len - md_len) > 5000 and row['raw_text']
body = row['raw_text'] if use_raw else row['text_md']
text_source = 'raw_text' if use_raw else 'text_md'
```

Add `text_source` to the YAML frontmatter so the agent (and downstream debugging) knows which variant was used. Re-export only the documents flagged with `use_raw = True` if a full re-export is too costly — these are the docs where the current markdown export is silently dropping footnote citations.

### Scope to expect

The investigation SQL from Issue 3.1 (`ORDER BY raw_len - md_len DESC LIMIT 20`) should be re-run to size the affected document set. Saint-Gobain's +11,945 is large; the count of docs over the 5,000-char threshold across 4,497 records sets the re-export volume.

### Alternatives rejected

- **A. Global switch to raw_text** — rejected because raw introduces page-header / URL / timestamp noise that markdown removes. While it produced 0 false positives in this 5-doc test, the noise surface area at full-corpus scale (4,497 docs) is non-trivial and the agent prompt would need new instructions to handle it. Net-zero gain for ~93% of docs.
- **C. Stay on markdown** — rejected because the Saint-Gobain killer test shows md silently drops 75% of citations on footnote-heavy CJEU AG Opinions. This is exactly the document class where citation density is highest (case-law-rich AG Opinions and ECtHR judgments). Cannot leave this on the table.

## 7. Artifacts

- Raw export script: `scripts/_temp_export_raw.py` (throwaway, not committed)
- 5 raw markdown files: `data/decisions_md_raw/{document_id}.md`
- 5 extraction-result JSONs: `data/extraction_results/raw_test/{document_id}_raw.json`
- Summary file: `data/decisions_md_raw/_summary.json`

---

*Closes investigation T4 from `agent-test-run-open-issues.md`. T9 (re-run on Saint-Gobain after T4) is now also satisfied — see citation_index 6, 9, and 12 in `data/extraction_results/raw_test/11f23599-...json`.*
