"""
Pre-split Tier 3 decision Markdown files into overlapping chunks for parallel
citation extraction.

Tiered chunking strategy (D32):
    - Tier 1 (≤500 lines, ~93% of corpus): single-pass extraction by agent.
    - Tier 2 (501–2000 lines, ~6%, 271 docs): progressive file output by agent.
    - Tier 3 (>2000 lines / >100K words, ~1%, 47 docs, max 521K words): pre-split
      + parallel agent extraction + merge. THIS SCRIPT IMPLEMENTS THE PRE-SPLIT.

INPUT:
    - data/decisions_md/{document_id}.md (YAML frontmatter + raw_text body)
    - CLI flags --target-words (default 20000) and --overlap-words (default 2000)
ALGORITHM:
    1. Read source file. Parse YAML frontmatter (preserve verbatim).
    2. Split body on whitespace into a flat word list.
    3. Walk word list emitting chunks of `target_words`, sharing
       `overlap_words` of trailing context with the next chunk. Snap chunk end
       to a sentence boundary (./?/! followed by whitespace) within the last
       200 words; fall back to raw word boundary if none found.
    4. For each chunk write data/decisions_md_chunks/{document_id}/
       chunk_{n:02d}_of_{total:02d}.md with augmented YAML frontmatter
       (chunk_index, chunk_total, chunk_word_start, chunk_word_end) + body.
    5. Write _manifest.json sibling listing all chunks with word ranges.
OUTPUT:
    - data/decisions_md_chunks/{document_id}/chunk_NN_of_TT.md (one per chunk)
    - data/decisions_md_chunks/{document_id}/_manifest.json
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

# Add scripts dir to path for config import
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DB_CONFIG

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DECISIONS_MD_DIR = PROJECT_ROOT / "data" / "decisions_md"
CHUNKS_DIR = PROJECT_ROOT / "data" / "decisions_md_chunks"

DEFAULT_TARGET_WORDS = 15_000  # T17 (2026-05-03): dropped from 20K — agents reported some 20K-word chunks exceeded the Read tool's per-call limit (43K tokens / 129K chars). 15K stays comfortably below.
DEFAULT_OVERLAP_WORDS = 2_000
TIER3_WORD_THRESHOLD = 100_000

# Sentence-end snap window: look back this many words from the desired chunk
# end to find a clean ./?/! boundary; if none, fall back to the raw word edge.
SENTENCE_SNAP_WINDOW = 200


# ----- Frontmatter parsing ----------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?\n)---\s*\n?(.*)$", re.DOTALL)


def split_frontmatter(content: str) -> tuple[str, str]:
    """
    Split source file content into (frontmatter_block, body).

    INPUT:
        - content: full file text including leading "---\\n…\\n---\\n" block
    ALGORITHM:
        1. Regex-match leading frontmatter delimiters; capture inner block + body.
        2. If no match (file lacks frontmatter), treat the entire content as
           body and return an empty frontmatter block.
    OUTPUT: (frontmatter_inner_yaml, body_text)
    """
    m = _FRONTMATTER_RE.match(content)
    if not m:
        return ("", content)
    return (m.group(1).rstrip("\n"), m.group(2).lstrip("\n"))


# ----- Sentence-aware chunking ------------------------------------------------

# Match a word followed by sentence-end punctuation (. ? !), optionally with
# closing quotes/parens. Used to detect "this word ends a sentence".
_SENTENCE_END_RE = re.compile(r"[.?!][\"')\]]*$")


def _is_sentence_end_word(word: str) -> bool:
    """Return True if `word` ends with sentence-final punctuation."""
    return bool(_SENTENCE_END_RE.search(word))


def find_chunk_end(words: list[str], start: int, target_end: int) -> int:
    """
    Pick the chunk's end-word index, snapping to a sentence boundary if possible.

    INPUT:
        - words: full token list of the body
        - start: first word index (inclusive) of this chunk
        - target_end: desired exclusive end index (start + target_words)
    ALGORITHM:
        1. Clamp target_end to len(words).
        2. Scan backward from target_end - 1 over the last SENTENCE_SNAP_WINDOW
           words; if any word ends with .?!, place the chunk boundary
           immediately AFTER that word.
        3. If no boundary found, return the unsnapped target_end.
    OUTPUT: exclusive end index for words[start:end]
    """
    n = len(words)
    if target_end >= n:
        return n

    snap_floor = max(start + 1, target_end - SENTENCE_SNAP_WINDOW)
    for i in range(target_end - 1, snap_floor - 1, -1):
        if _is_sentence_end_word(words[i]):
            return i + 1
    return target_end


def chunk_words(
    words: list[str],
    target_words: int,
    overlap_words: int,
) -> list[tuple[int, int]]:
    """
    Compute (start, end) word-index ranges for each chunk.

    INPUT:
        - words: tokenized body
        - target_words: nominal chunk size
        - overlap_words: trailing words shared with the next chunk
    ALGORITHM:
        1. start = 0. Compute desired end = start + target_words.
        2. Snap end to sentence boundary via find_chunk_end().
        3. Append (start, end). If end == len(words), stop.
        4. Next start = max(end - overlap_words, start + 1) — guarantees
           forward progress even if the snap pulled the end too far back.
    OUTPUT: list of (start, end) tuples, end exclusive
    """
    if target_words <= 0:
        raise ValueError("target_words must be positive")
    if overlap_words < 0 or overlap_words >= target_words:
        raise ValueError("overlap_words must be in [0, target_words)")

    n = len(words)
    if n == 0:
        return []

    ranges: list[tuple[int, int]] = []
    start = 0
    while start < n:
        desired_end = start + target_words
        end = find_chunk_end(words, start, desired_end)
        ranges.append((start, end))
        if end >= n:
            break
        next_start = max(end - overlap_words, start + 1)
        # Defensive: avoid infinite loop if snap returned start+1 etc.
        if next_start <= start:
            next_start = start + 1
        start = next_start
    return ranges


# ----- Frontmatter augmentation ----------------------------------------------


def build_chunk_frontmatter(
    base_frontmatter: str,
    chunk_index: int,
    chunk_total: int,
    word_start: int,
    word_end: int,
) -> str:
    """
    Wrap the original frontmatter block with chunk-level metadata appended.

    INPUT:
        - base_frontmatter: original YAML inner block (no surrounding ---)
        - chunk_index: 1-based chunk number
        - chunk_total: total chunks for the document
        - word_start, word_end: word-index range in the original body (end exclusive)
    OUTPUT: full frontmatter block including the surrounding --- delimiters
    """
    extra = "\n".join(
        [
            f"chunk_index: {chunk_index}",
            f"chunk_total: {chunk_total}",
            f"chunk_word_start: {word_start}",
            f"chunk_word_end: {word_end}",
        ]
    )
    base = base_frontmatter.rstrip("\n")
    inner = f"{base}\n{extra}" if base else extra
    return f"---\n{inner}\n---"


# ----- Per-document driver ----------------------------------------------------


def chunk_document(
    document_id: str,
    target_words: int = DEFAULT_TARGET_WORDS,
    overlap_words: int = DEFAULT_OVERLAP_WORDS,
) -> dict:
    """
    Chunk a single decision_md file. Returns stats dict.

    INPUT:
        - document_id: UUID matching data/decisions_md/{document_id}.md
        - target_words, overlap_words: chunk parameters
    ALGORITHM:
        1. Read source .md file (UTF-8). Split frontmatter / body.
        2. Tokenize body on whitespace.
        3. Compute chunk word ranges. Write each chunk with augmented
           frontmatter to data/decisions_md_chunks/{document_id}/.
        4. Write _manifest.json sibling.
    OUTPUT: stats dict with document_id, total_words, chunk_count, output_dir
    """
    src = DECISIONS_MD_DIR / f"{document_id}.md"
    if not src.is_file():
        raise FileNotFoundError(f"Source file not found: {src}")

    content = src.read_text(encoding="utf-8")
    frontmatter, body = split_frontmatter(content)

    words = body.split()
    total_words = len(words)
    log.info(f"  Source: {src.name}  body words: {total_words:,}")

    ranges = chunk_words(words, target_words, overlap_words)
    total = len(ranges)
    if total == 0:
        log.warning(f"⚠️  No words found in {document_id}; nothing to chunk.")
        return {
            "document_id": document_id,
            "total_words": 0,
            "chunk_count": 0,
            "output_dir": None,
        }

    out_dir = CHUNKS_DIR / document_id
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest_chunks: list[dict] = []
    for i, (ws, we) in enumerate(ranges, start=1):
        chunk_body = " ".join(words[ws:we])
        fm = build_chunk_frontmatter(frontmatter, i, total, ws, we)
        chunk_path = out_dir / f"chunk_{i:02d}_of_{total:02d}.md"
        chunk_path.write_text(f"{fm}\n\n{chunk_body}\n", encoding="utf-8")
        manifest_chunks.append(
            {
                "file": chunk_path.name,
                "chunk_index": i,
                "chunk_total": total,
                "word_start": ws,
                "word_end": we,
                "word_count": we - ws,
            }
        )

    manifest = {
        "document_id": document_id,
        "source_file": str(src.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "total_words": total_words,
        "target_words": target_words,
        "overlap_words": overlap_words,
        "chunk_count": total,
        "chunks": manifest_chunks,
    }
    manifest_path = out_dir / "_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    log.info(f"  ✓ Wrote {total} chunks → {out_dir.relative_to(PROJECT_ROOT)}")
    return {
        "document_id": document_id,
        "total_words": total_words,
        "chunk_count": total,
        "output_dir": str(out_dir),
    }


# ----- DB helper for --all-tier3 ---------------------------------------------


def list_tier3_document_ids(threshold: int = TIER3_WORD_THRESHOLD) -> list[str]:
    """
    Query the DB for document IDs whose extracted_text.word_count exceeds the
    Tier 3 threshold.

    INPUT:
        - threshold: minimum word_count to qualify as Tier 3 (default 100,000)
    ALGORITHM:
        1. Connect to PostgreSQL via DB_CONFIG.
        2. SELECT document_id FROM extracted_text WHERE word_count > threshold
           AND raw_text IS NOT NULL, ORDER BY word_count DESC.
    OUTPUT: list of UUID strings, ordered by word_count desc
    """
    connstr = (
        f"postgresql://{DB_CONFIG['username']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    )
    engine = create_engine(connstr)
    query = text(
        """
        SELECT et.document_id::text AS document_id, et.word_count
        FROM extracted_text et
        JOIN documents d ON d.document_id = et.document_id
        WHERE et.word_count > :threshold
          AND et.raw_text IS NOT NULL
          AND d.is_decision = TRUE
          AND COALESCE(d.is_garbled, FALSE) = FALSE
        ORDER BY et.word_count DESC
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(query, {"threshold": threshold}).mappings().all()
    return [r["document_id"] for r in rows]


# ----- CLI --------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pre-split Tier 3 decision .md files into overlapping chunks."
    )
    parser.add_argument(
        "document_id",
        nargs="?",
        help="Document UUID (matching data/decisions_md/{id}.md). Omit with --all-tier3.",
    )
    parser.add_argument(
        "--all-tier3",
        action="store_true",
        help=f"Chunk every document with word_count > {TIER3_WORD_THRESHOLD:,} (queries DB).",
    )
    parser.add_argument(
        "--target-words",
        type=int,
        default=DEFAULT_TARGET_WORDS,
        help=f"Target words per chunk (default {DEFAULT_TARGET_WORDS}).",
    )
    parser.add_argument(
        "--overlap-words",
        type=int,
        default=DEFAULT_OVERLAP_WORDS,
        help=f"Overlap words shared between adjacent chunks (default {DEFAULT_OVERLAP_WORDS}).",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=TIER3_WORD_THRESHOLD,
        help="Override Tier 3 word threshold for --all-tier3 mode.",
    )
    args = parser.parse_args()

    if not args.all_tier3 and not args.document_id:
        parser.error("Provide a document_id or use --all-tier3.")

    log.info("=" * 70)
    log.info("CHUNK LARGE DOCS — Tier 3 pre-split")
    log.info("=" * 70)
    log.info(f"  target_words = {args.target_words:,}")
    log.info(f"  overlap_words = {args.overlap_words:,}")

    if args.all_tier3:
        log.info(f"  Mode: --all-tier3 (threshold {args.threshold:,} words)")
        try:
            doc_ids = list_tier3_document_ids(args.threshold)
        except Exception as exc:  # noqa: BLE001
            log.error(f"❌ Failed to query DB for Tier 3 docs: {exc}")
            sys.exit(1)
        log.info(f"  Found {len(doc_ids)} Tier 3 documents")
    else:
        doc_ids = [args.document_id]

    stats = {"processed": 0, "errors": 0, "total_chunks": 0}
    for doc_id in doc_ids:
        log.info("-" * 70)
        log.info(f"DOC {doc_id}")
        try:
            r = chunk_document(doc_id, args.target_words, args.overlap_words)
            stats["processed"] += 1
            stats["total_chunks"] += r["chunk_count"]
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
    log.info(f"  Total chunks written: {stats['total_chunks']}")
    log.info("=" * 70)


if __name__ == "__main__":
    main()
