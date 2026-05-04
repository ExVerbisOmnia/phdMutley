# Per-Document Agent Prompt Template

This is the prompt the orchestrator's per-doc sub-agent follows. The orchestrator substitutes `{document_id}`, `{tier}`, and `{word_count}` at dispatch time.

The orchestrator handles DB cleanup (`orchestrator_helper.py prepare`) BEFORE spawning this agent, and DB ingest (`orchestrator_helper.py ingest`) AFTER receiving the agent's output. So this agent doesn't touch the DB — it only reads the source `.md` file, applies the extractor + verifier protocols, writes two JSON files to disk, and returns a brief summary.

---

## Template (orchestrator pastes this verbatim, with substitutions)

```markdown
You are processing document `{document_id}` (Tier {tier}, {word_count} words) through the 2-agent citation-extraction pipeline. This is one of 4,461 docs in the corpus run.

# Mission

Apply the citation-extractor + citation-verifier protocols sequentially, write two JSON files to disk, and return a brief summary. The orchestrator handles DB ingest separately.

# Steps

1. **Read the rule files.** Absorb both protocols before reading the source doc.
   - `.claude/agents/citation-extractor.md`
   - `.claude/agents/citation-verifier.md`

2. **Read the source decision.**
   - Tier 1 ({word_count} ≤ 25,000): read the entire file at `data/decisions_md/{document_id}.md` in one call.
   - Tier 2 (25,000 < {word_count} ≤ 100,000): read in 300-line chunks via `Read(offset=N, limit=300)`. Append per-chunk findings to `data/extraction_results/{document_id}_partial.json` between chunks (the partial file is your persistent memory). After all chunks, read it back and dedupe by `case_name`.
   - Tier 3 ({word_count} > 100,000): the chunked files at `data/decisions_md_chunks/{document_id}/chunk_NN_of_TT.md` should already exist (run `python scripts/chunk_large_docs.py {document_id}` first if they don't). Process each chunk separately; save per-chunk results at `data/extraction_results/chunks/{document_id}/chunk_NN_of_TT_extracted.json` (the `_of_TT` infix is required by `merge_chunk_results.py`'s discovery regex). Then call `python scripts/merge_chunk_results.py {document_id}` to produce the merged extraction.

3. **Apply the citation-extractor protocol.** Output the extraction JSON per the schema in `citation-extractor.md` Section 8. Write to:
   `data/extraction_results/{document_id}_extracted.json`

4. **Apply the citation-verifier protocol** on your own extraction output. Output the verified JSON per `citation-verifier.md` Section 12. Write to:
   `data/extraction_results/{document_id}_verified.json`

5. **Validate the verified JSON parses cleanly.** Run `python -c "import json; json.load(open('data/extraction_results/{document_id}_verified.json', encoding='utf-8'))"` to verify your JSON is parseable. If it fails, FIX the JSON (likely an unescaped quote in a `verbatim_snippet` field) before returning.

# Critical schema requirements

- The verified JSON top-level MUST contain: `document_id`, `case_id`, `source_jurisdiction`, `source_region`, `source_year`, `verification_timestamp`, `total_citations_extracted`, `total_confirmed`, `total_not_found`, `total_misattributed`, `total_not_a_case`, `total_duplicates`, `unique_citations_confirmed`, `citations[]`, `summary{}`.
- Each citation in `citations[]` MUST contain `is_vertical_dialogue` (bool). Set `true` only when source = national court AND cited = international court of which source-country is a member (per Rule 7.2 / D30).
- `functional_use` allowed values: `aligned`, `contested`, `avoided`, `invoked`, `dismissed` (per D31). Use `dismissed` for citations that appear ONLY in summaries of party arguments with no court engagement.
- `sixfold_type` values: `Foreign Citation`, `International Citation`, `Foreign International Citation`, `Inter-System Citation`, `Member-State Citation`, `Non-Member Citation`, `Domestic`, `Unclassified`. Apply Rule 7.0 same-court rule (D29) BEFORE the country comparison.
- `summary.by_vertical_dialogue` should be `{"true": N, "false": M}` if you populate it; if you only have `vertical_dialogue_count`, the orchestrator helper will derive the rest.

# Quote-escaping warning (learned from prior runs)

A common failure mode: `verbatim_snippet` contains a quoted parenthetical from the source — e.g.,

```
"Citizens for a Better Env't, 523 U.S. 83, 107 (1998) ('By the mere bringing... happier...').",
```

If you copy a passage that contains a straight ASCII `"` and you don't escape it as `\"` inside your JSON string, the file will be unparseable. **Either:**
- Escape every `"` inside JSON string values as `\"`, OR
- If the source uses curly quotes (`"` `"`), keep them as-is (they don't conflict with JSON delimiters).

Your final JSON must `python -m json.tool < file` cleanly.

# Output (return to orchestrator, ≤200 words)

JSON object summary that the orchestrator can act on. Format:

```json
{
  "document_id": "{document_id}",
  "status": "complete" | "failed",
  "tier": {tier},
  "extracted_path": "data/extraction_results/{document_id}_extracted.json",
  "verified_path": "data/extraction_results/{document_id}_verified.json",
  "citations_extracted": <int>,
  "citations_verified": <int>,
  "citations_dismissed": <int>,
  "citations_vertical": <int>,
  "notes": "<brief: anything notable, e.g. metadata mismatch flagged, footnotes truncated, dismissed soft-tags applied, etc.>",
  "error": null | "<error description if status=failed>"
}
```

# What NOT to do

- DO NOT touch the DB. The orchestrator handles all DB writes.
- DO NOT delete the `_partial.json` (Tier 2) or `_chunks/` (Tier 3) directories — they're audit trails.
- DO NOT commit. Working tree changes only.
- DO NOT spawn sub-sub-agents (no nested Agent calls); just follow the protocols inline.
```

---

## How the orchestrator dispatches this

```python
# Pseudocode for the orchestrator's loop
prep_result = run("python scripts/orchestrator_helper.py prepare {doc_id}")
agent_result = Agent(
    subagent_type="general-purpose",
    name=f"corpus-{doc_id[:8]}",
    run_in_background=False,  # run synchronously per doc; or true if N=3 parallel
    prompt=PER_DOC_TEMPLATE.format(
        document_id=doc_id,
        tier=prep_result["tier"],
        word_count=prep_result["word_count"],
    ),
)
if agent_result["status"] == "complete":
    run(f"python scripts/orchestrator_helper.py ingest {doc_id} {agent_result['verified_path']}")
else:
    run(f"python scripts/orchestrator_helper.py mark_failed {doc_id} '{agent_result['error']}'")
```

The orchestrator's loop is the subject of `orchestrator-driver.md`.
