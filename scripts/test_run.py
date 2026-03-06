"""
Test Run Sampling Utility
=========================
Shared module for reproducible random sampling via --test-run N flag.
Used by all pipeline scripts (phases 1-5) to process a consistent subset of documents.

Design:
- Uses random.Random(seed) instance — no global state side effects
- Sorts by Document ID before sampling — deterministic regardless of Excel row order
- Returns None/unchanged data when n=None — matches existing "no filter" pattern

VERSION: 1.0
"""

import argparse
import logging
import random
from uuid import NAMESPACE_DNS, uuid5

logger = logging.getLogger(__name__)

# Same namespace as config.py — deterministic UUID generation
UUID_NAMESPACE = uuid5(NAMESPACE_DNS, "climatecasechart.com.phdmutley")


def add_test_run_arg(parser: argparse.ArgumentParser) -> None:
    """
    Add --test-run N and --seed arguments to an ArgumentParser.

    INPUT:
        - parser: ArgumentParser instance to augment
    ALGORITHM:
        1. Add --test-run with type=int, default=None
        2. Add --seed with type=int, default=42
    OUTPUT: None (modifies parser in place)
    """
    parser.add_argument(
        "--test-run",
        type=int,
        default=None,
        metavar="N",
        help="Sample N documents for a test run (deterministic random sampling)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible sampling (default: 42)",
    )


def sample_dataframe(df, n, seed=42, id_column="Document ID"):
    """
    Sample N rows from a DataFrame with deterministic random selection.

    INPUT:
        - df: pandas DataFrame to sample from
        - n: number of rows to sample (None = return full df)
        - seed: random seed for reproducibility
        - id_column: column to sort by before sampling
    ALGORITHM:
        1. If n is None, return df unchanged
        2. Sort df by id_column for deterministic ordering
        3. If n >= len(df), warn and return full df
        4. Use random.Random(seed).sample() to pick n indices
        5. Return sampled rows
    OUTPUT: sampled DataFrame (or original if n is None)
    """
    if n is None:
        return df

    total = len(df)

    if n >= total:
        logger.warning(
            f"Test-run requested {n} documents but only {total} available — returning all"
        )
        return df

    # Sort by ID column for deterministic ordering regardless of Excel row order
    sorted_df = df.sort_values(by=id_column).reset_index(drop=True)

    # Sample indices using instance-based RNG (no global state mutation)
    rng = random.Random(seed)
    sampled_indices = sorted(rng.sample(range(total), n))

    sampled_df = sorted_df.iloc[sampled_indices].copy()

    logger.info(f"Test-run: sampled {n} of {total} documents (seed={seed})")

    return sampled_df


def get_sampled_document_ids(df, n, seed=42, id_column="Document ID"):
    """
    Return a set of Document ID strings from a sampled subset.

    INPUT:
        - df: pandas DataFrame with document data
        - n: number of documents to sample (None = no filtering)
        - seed: random seed
        - id_column: column containing Document IDs
    ALGORITHM:
        1. If n is None, return None (no filtering)
        2. Sample df via sample_dataframe()
        3. Extract id_column values as set of strings
    OUTPUT: set[str] of sampled Document IDs, or None
    """
    if n is None:
        return None

    sampled = sample_dataframe(df, n, seed, id_column)
    return set(sampled[id_column].astype(str))


def get_sampled_document_uuids(df, n, seed=42, id_column="Document ID"):
    """
    DEPRECATED: Use get_sampled_document_ids() instead.
    All scripts now query by sabin_document_id (string) rather than computed UUIDs.
    Kept only for backward compatibility — will be removed in a future cleanup.
    """
    import warnings
    warnings.warn(
        "get_sampled_document_uuids() is deprecated. Use get_sampled_document_ids() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    if n is None:
        return None

    sampled = sample_dataframe(df, n, seed, id_column)

    def _generate_document_uuid(document_id_str):
        clean_id = str(document_id_str).strip().lower()
        return uuid5(UUID_NAMESPACE, f"document_{clean_id}")

    return set(sampled[id_column].apply(_generate_document_uuid))
