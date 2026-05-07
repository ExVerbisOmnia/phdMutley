"""
Merge per-chunk citation extraction results into a single deduplicated JSON
matching the Tier 1/2 output shape.

Tiered chunking strategy (D32):
    Tier 3 documents (>100K words, ~47 docs) are pre-split by chunk_large_docs.py
    and processed by parallel agents. Each parallel agent writes its result to
    data/extraction_results/chunks/{document_id}/chunk_NN_of_TT_extracted.json.
    THIS SCRIPT MERGES THOSE PER-CHUNK RESULTS.

INPUT:
    - data/extraction_results/chunks/{document_id}/chunk_NN_of_TT_extracted.json
      (one per chunk; produced by parallel agent runs)
ALGORITHM:
    1. Read all chunk extraction JSONs for the document.
    2. Concatenate every chunk's `citations` array.
    3. Dedupe by normalized case_name (lowercased, whitespace-collapsed).
       On duplicate:
           - Keep the citation with highest `confidence`.
           - On tie, prefer the one with more non-null fields (richer metadata).
           - On tie still, keep first occurrence.
    4. Re-number `citation_index` sequentially (1..N) in merged output.
    5. Set `total_citations_found` to the unique count post-dedup.
    6. Write merged JSON to data/extraction_results/{document_id}_extracted.json
       (same path Tier 1/2 docs use → uniform downstream).
    7. Per-chunk JSONs are PRESERVED (audit trail; never deleted by this script).
OUTPUT:
    - data/extraction_results/{document_id}_extracted.json
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXTRACTION_RESULTS_DIR = PROJECT_ROOT / "data" / "extraction_results"
CHUNKS_RESULTS_DIR = EXTRACTION_RESULTS_DIR / "chunks"

_CHUNK_FILE_RE = re.compile(r"^chunk_(\d+)_of_(\d+)_extracted\.json$")


# ----- Helpers ---------------------------------------------------------------


def _normalize_case_name(name: object) -> str:
    """Lowercase + collapse all whitespace runs to a single space."""
    if not isinstance(name, str):
        return ""
    return re.sub(r"\s+", " ", name).strip().lower()


def _metadata_completeness(citation: dict) -> int:
    """
    Count fields with non-null, non-empty values. Used as tie-breaker when
    duplicates have identical confidence — richer metadata wins.
    """
    score = 0
    for k, v in citation.items():
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        score += 1
    return score


def _confidence(citation: dict) -> float:
    """Coerce confidence to float; missing/non-numeric → 0.0."""
    raw = citation.get("confidence")
    try:
        return float(raw) if raw is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


# ----- Discovery -------------------------------------------------------------


def find_chunk_files(document_id: str) -> list[Path]:
    """
    Locate all chunk_NN_of_TT_extracted.json files for a document.

    INPUT:
        - document_id: UUID matching data/extraction_results/chunks/{id}/
    ALGORITHM:
        1. List the document's chunks subdirectory.
        2. Filter filenames matching ^chunk_(\\d+)_of_(\\d+)_extracted\\.json$.
        3. Sort by chunk index.
    OUTPUT: ordered list of Path objects
    """
    doc_dir = CHUNKS_RESULTS_DIR / document_id
    if not doc_dir.is_dir():
        return []
    matches: list[tuple[int, Path]] = []
    for p in doc_dir.iterdir():
        m = _CHUNK_FILE_RE.match(p.name)
        if m:
            matches.append((int(m.group(1)), p))
    matches.sort(key=lambda t: t[0])
    return [p for _, p in matches]


def list_documents_with_chunks() -> list[str]:
    """List every document_id that has at least one chunk extraction JSON."""
    if not CHUNKS_RESULTS_DIR.is_dir():
        return []
    return sorted(
        p.name
        for p in CHUNKS_RESULTS_DIR.iterdir()
        if p.is_dir() and find_chunk_files(p.name)
    )


# ----- Merge -----------------------------------------------------------------


def dedupe_citations(all_citations: list[dict]) -> tuple[list[dict], int]:
    """
    Dedupe a flat citations list by normalized case_name.

    INPUT:
        - all_citations: concatenated citations from every chunk
    ALGORITHM:
        1. Walk the list. For each citation, compute normalized case_name key.
        2. Citations with empty key (no case_name) are kept as-is — cannot
           safely dedupe them.
        3. For a key already seen, choose the better citation:
             a. Higher confidence wins.
             b. On tie, more complete metadata wins.
             c. On tie still, the existing (first-seen) wins.
        4. Preserve insertion order for the kept citations.
    OUTPUT: (deduped_list, dropped_count)
    """
    kept_by_key: dict[str, int] = {}  # key → index in `kept`
    kept: list[dict] = []
    no_key_citations: list[dict] = []
    dropped = 0

    for citation in all_citations:
        key = _normalize_case_name(citation.get("case_name"))
        if not key:
            no_key_citations.append(citation)
            continue

        if key not in kept_by_key:
            kept_by_key[key] = len(kept)
            kept.append(citation)
            continue

        idx = kept_by_key[key]
        existing = kept[idx]
        new_conf = _confidence(citation)
        old_conf = _confidence(existing)
        if new_conf > old_conf:
            kept[idx] = citation
            dropped += 1
        elif new_conf == old_conf:
            new_meta = _metadata_completeness(citation)
            old_meta = _metadata_completeness(existing)
            if new_meta > old_meta:
                kept[idx] = citation
                dropped += 1
            else:
                dropped += 1
        else:
            dropped += 1

    merged = kept + no_key_citations
    return merged, dropped


def merge_document(document_id: str) -> dict:
    """
    Merge all chunk extraction JSONs for one document.

    INPUT:
        - document_id: UUID
    ALGORITHM:
        1. Discover chunk files. Abort if none.
        2. Load each chunk's JSON. Concatenate `citations` arrays.
        3. Dedupe by normalized case_name.
        4. Re-number citation_index 1..N.
        5. Build merged record using metadata from chunk 1 (document_id,
           case_id, source_jurisdiction, source_region, source_year,
           extraction_timestamp, quality_check). total_citations_found = unique
           count post-dedup.
        6. Write data/extraction_results/{document_id}_extracted.json.
    OUTPUT: stats dict (chunks_read, raw_count, unique_count, dropped, output_path)
    """
    chunk_files = find_chunk_files(document_id)
    if not chunk_files:
        raise FileNotFoundError(
            f"No chunk extraction JSONs at {CHUNKS_RESULTS_DIR / document_id}"
        )

    log.info(f"  Found {len(chunk_files)} chunk extraction JSONs")

    chunk_payloads: list[dict] = []
    all_citations: list[dict] = []
    for cf in chunk_files:
        try:
            payload = json.loads(cf.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {cf}: {exc}") from exc
        chunk_payloads.append(payload)
        citations = payload.get("citations") or []
        if not isinstance(citations, list):
            raise ValueError(f"`citations` is not a list in {cf}")
        all_citations.extend(citations)

    raw_count = len(all_citations)
    merged, dropped = dedupe_citations(all_citations)

    # Re-number citation_index sequentially.
    for i, c in enumerate(merged, start=1):
        c["citation_index"] = i

    # Inherit document-level metadata from the first chunk.
    first = chunk_payloads[0]
    merged_record = {
        "document_id": first.get("document_id", document_id),
        "case_id": first.get("case_id"),
        "source_jurisdiction": first.get("source_jurisdiction"),
        "source_region": first.get("source_region"),
        "source_year": first.get("source_year"),
        "quality_check": first.get("quality_check", "OK"),
        "extraction_timestamp": first.get("extraction_timestamp"),
        "total_citations_found": len(merged),
        "tier": "tier3_merged",
        "chunks_merged": len(chunk_files),
        "raw_citation_count_pre_dedup": raw_count,
        "citations": merged,
    }

    out_path = EXTRACTION_RESULTS_DIR / f"{document_id}_extracted.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(merged_record, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    log.info(
        f"  ✓ {raw_count} raw → {len(merged)} unique "
        f"(dropped {dropped}) → {out_path.relative_to(PROJECT_ROOT)}"
    )
    return {
        "document_id": document_id,
        "chunks_read": len(chunk_files),
        "raw_count": raw_count,
        "unique_count": len(merged),
        "dropped": dropped,
        "output_path": str(out_path),
    }


# ----- CLI -------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge per-chunk Tier 3 citation extractions into one JSON."
    )
    parser.add_argument(
        "document_id",
        nargs="?",
        help="Document UUID. Omit with --all.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Merge every document under data/extraction_results/chunks/.",
    )
    args = parser.parse_args()

    if not args.all and not args.document_id:
        parser.error("Provide a document_id or use --all.")

    log.info("=" * 70)
    log.info("MERGE CHUNK RESULTS — Tier 3 post-extraction merge")
    log.info("=" * 70)

    if args.all:
        doc_ids = list_documents_with_chunks()
        log.info(f"  Found {len(doc_ids)} documents with chunked extractions")
    else:
        doc_ids = [args.document_id]

    stats = {"processed": 0, "errors": 0, "raw_total": 0, "unique_total": 0}
    for doc_id in doc_ids:
        log.info("-" * 70)
        log.info(f"DOC {doc_id}")
        try:
            r = merge_document(doc_id)
            stats["processed"] += 1
            stats["raw_total"] += r["raw_count"]
            stats["unique_total"] += r["unique_count"]
        except FileNotFoundError as exc:
            log.warning(f"⚠️  {exc}")
            stats["errors"] += 1
        except Exception as exc:  # noqa: BLE001
            log.exception(f"❌ Failed on {doc_id}: {exc}")
            stats["errors"] += 1

    log.info("=" * 70)
    log.info("SUMMARY")
    log.info("=" * 70)
    log.info(f"  Documents processed : {stats['processed']}")
    log.info(f"  Errors              : {stats['errors']}")
    log.info(f"  Raw citation total  : {stats['raw_total']}")
    log.info(f"  Unique total        : {stats['unique_total']}")
    log.info(f"  Dropped (overlap)   : {stats['raw_total'] - stats['unique_total']}")
    log.info("=" * 70)


if __name__ == "__main__":
    main()
