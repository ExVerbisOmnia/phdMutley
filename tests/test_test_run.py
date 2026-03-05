"""
Tests for scripts/test_run.py — reproducible random sampling utility.
"""

import argparse
from uuid import UUID

import pandas as pd
import pytest

from test_run import (
    add_test_run_arg,
    get_sampled_document_ids,
    get_sampled_document_uuids,
    sample_dataframe,
)


@pytest.fixture
def sample_df():
    """DataFrame mimicking the Excel seed file structure."""
    return pd.DataFrame(
        {
            "Document ID": [f"doc-{i:04d}" for i in range(200)],
            "Case ID": [f"case-{i // 2:04d}" for i in range(200)],
            "Document Title": [f"Title {i}" for i in range(200)],
        }
    )


# ── sample_dataframe ──────────────────────────────────────────────────


class TestSampleDataframe:
    def test_none_returns_unchanged(self, sample_df):
        result = sample_dataframe(sample_df, None)
        pd.testing.assert_frame_equal(result, sample_df)

    def test_returns_exact_count(self, sample_df):
        result = sample_dataframe(sample_df, 50)
        assert len(result) == 50

    def test_reproducible_same_seed(self, sample_df):
        r1 = sample_dataframe(sample_df, 50, seed=42)
        r2 = sample_dataframe(sample_df, 50, seed=42)
        pd.testing.assert_frame_equal(r1.reset_index(drop=True), r2.reset_index(drop=True))

    def test_different_seed_different_sample(self, sample_df):
        r1 = sample_dataframe(sample_df, 50, seed=42)
        r2 = sample_dataframe(sample_df, 50, seed=99)
        # Different seeds should produce different samples (extremely unlikely to be equal)
        assert not r1["Document ID"].tolist() == r2["Document ID"].tolist()

    def test_n_exceeds_total_returns_all(self, sample_df):
        result = sample_dataframe(sample_df, 999)
        assert len(result) == len(sample_df)

    def test_n_equals_total_returns_all(self, sample_df):
        result = sample_dataframe(sample_df, 200)
        assert len(result) == 200

    def test_sample_of_one(self, sample_df):
        result = sample_dataframe(sample_df, 1)
        assert len(result) == 1

    def test_deterministic_ordering(self):
        """Sampling is deterministic regardless of original DataFrame order."""
        df_asc = pd.DataFrame({"Document ID": ["a", "b", "c", "d", "e"]})
        df_desc = pd.DataFrame({"Document ID": ["e", "d", "c", "b", "a"]})
        r1 = sample_dataframe(df_asc, 3, seed=42)
        r2 = sample_dataframe(df_desc, 3, seed=42)
        assert r1["Document ID"].tolist() == r2["Document ID"].tolist()


# ── get_sampled_document_ids ──────────────────────────────────────────


class TestGetSampledDocumentIds:
    def test_none_returns_none(self, sample_df):
        assert get_sampled_document_ids(sample_df, None) is None

    def test_returns_set_of_strings(self, sample_df):
        result = get_sampled_document_ids(sample_df, 10)
        assert isinstance(result, set)
        assert len(result) == 10
        assert all(isinstance(x, str) for x in result)

    def test_reproducible(self, sample_df):
        r1 = get_sampled_document_ids(sample_df, 10, seed=42)
        r2 = get_sampled_document_ids(sample_df, 10, seed=42)
        assert r1 == r2


# ── get_sampled_document_uuids ────────────────────────────────────────


class TestGetSampledDocumentUuids:
    def test_none_returns_none(self, sample_df):
        assert get_sampled_document_uuids(sample_df, None) is None

    def test_returns_set_of_uuids(self, sample_df):
        result = get_sampled_document_uuids(sample_df, 10)
        assert isinstance(result, set)
        assert len(result) == 10
        assert all(isinstance(x, UUID) for x in result)

    def test_reproducible(self, sample_df):
        r1 = get_sampled_document_uuids(sample_df, 10, seed=42)
        r2 = get_sampled_document_uuids(sample_df, 10, seed=42)
        assert r1 == r2

    def test_different_from_ids(self, sample_df):
        """UUIDs should be derived from IDs but not equal to them."""
        ids = get_sampled_document_ids(sample_df, 10, seed=42)
        uuids = get_sampled_document_uuids(sample_df, 10, seed=42)
        # Same count, but different types
        assert len(ids) == len(uuids)
        assert not ids.intersection(uuids)  # no overlap (str vs UUID)


# ── add_test_run_arg ──────────────────────────────────────────────────


class TestAddTestRunArg:
    def test_defaults(self):
        parser = argparse.ArgumentParser()
        add_test_run_arg(parser)
        args = parser.parse_args([])
        assert args.test_run is None
        assert args.seed == 42

    def test_test_run_value(self):
        parser = argparse.ArgumentParser()
        add_test_run_arg(parser)
        args = parser.parse_args(["--test-run", "100"])
        assert args.test_run == 100

    def test_custom_seed(self):
        parser = argparse.ArgumentParser()
        add_test_run_arg(parser)
        args = parser.parse_args(["--test-run", "50", "--seed", "99"])
        assert args.test_run == 50
        assert args.seed == 99
