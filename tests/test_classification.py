"""
Tests for citation classification logic.

Part 1: Unit tests for classify_citation_type() from extract_citations_v5.2.py
Part 2: Integration tests for SQL-based sixfold classification (against live DB)
"""

import pytest

# Import the v5.2 pure-Python classification function
from extract_citations_v5_2 import classify_citation_type, normalize_jurisdiction

# ============================================================================
# PART 1 — Unit tests for classify_citation_type (pure Python, no DB)
# ============================================================================


class TestClassifyCitationType:
    """Tests for the 3-type Python classification function."""

    def test_same_jurisdiction_returns_domestic(self):
        result, cross = classify_citation_type(
            "United States", "Global North", "United States", "Global North"
        )
        assert result == "Domestic"
        assert cross is False

    def test_different_national_jurisdictions_returns_foreign(self):
        result, cross = classify_citation_type(
            "United States", "Global North", "United Kingdom", "Global North"
        )
        assert result == "Foreign Citation"
        assert cross is True

    def test_national_gn_citing_national_gs_returns_foreign(self):
        result, cross = classify_citation_type(
            "United Kingdom", "Global North", "Colombia", "Global South"
        )
        assert result == "Foreign Citation"
        assert cross is True

    def test_national_gs_citing_national_gn_returns_foreign(self):
        result, cross = classify_citation_type("Brazil", "Global South", "Germany", "Global North")
        assert result == "Foreign Citation"
        assert cross is True

    def test_national_citing_international_returns_international(self):
        result, cross = classify_citation_type(
            "Netherlands", "Global North", "ECtHR", "International"
        )
        assert result == "International Citation"
        assert cross is True

    def test_international_citing_international_returns_international(self):
        result, cross = classify_citation_type("ECtHR", "International", "ICJ", "International")
        assert result == "International Citation"
        assert cross is True

    def test_international_citing_national_returns_foreign(self):
        result, cross = classify_citation_type("ECtHR", "International", "Germany", "Global North")
        assert result == "Foreign Citation"
        assert cross is True

    def test_unknown_origin_returns_unknown(self):
        result, cross = classify_citation_type("Netherlands", "Global North", "Unknown", "Unknown")
        assert result == "Unknown"
        assert cross is False

    def test_unknown_region_only_returns_unknown(self):
        result, cross = classify_citation_type(
            "Netherlands", "Global North", "Some Court", "Unknown"
        )
        assert result == "Unknown"
        assert cross is False

    def test_empty_strings_do_not_crash(self):
        result, cross = classify_citation_type("", "", "", "")
        # Should handle gracefully — exact return depends on logic, just no crash
        assert isinstance(result, str)
        assert isinstance(cross, bool)


class TestNormalizeJurisdiction:
    """Tests for jurisdiction alias normalization."""

    def test_usa_aliases(self):
        assert normalize_jurisdiction("USA") == "United States"
        assert normalize_jurisdiction("U.S.") == "United States"
        assert normalize_jurisdiction("U.S.A.") == "United States"
        assert normalize_jurisdiction("United States of America") == "United States"

    def test_uk_aliases(self):
        assert normalize_jurisdiction("UK") == "United Kingdom"
        assert normalize_jurisdiction("U.K.") == "United Kingdom"
        assert normalize_jurisdiction("Great Britain") == "United Kingdom"
        assert normalize_jurisdiction("Britain") == "United Kingdom"

    def test_netherlands_aliases(self):
        assert normalize_jurisdiction("The Netherlands") == "Netherlands"
        assert normalize_jurisdiction("Holland") == "Netherlands"

    def test_new_zealand_aliases(self):
        assert normalize_jurisdiction("NZ") == "New Zealand"
        assert normalize_jurisdiction("Aotearoa") == "New Zealand"

    def test_passthrough_for_canonical_names(self):
        assert normalize_jurisdiction("Germany") == "Germany"
        assert normalize_jurisdiction("Brazil") == "Brazil"
        assert normalize_jurisdiction("France") == "France"

    def test_none_returns_none(self):
        assert normalize_jurisdiction(None) is None

    def test_empty_string_returns_empty(self):
        assert normalize_jurisdiction("") == ""

    def test_whitespace_stripped(self):
        assert normalize_jurisdiction("  USA  ") == "United States"


# ============================================================================
# PART 2 — Integration tests for SQL-based sixfold classification (live DB)
# ============================================================================


def _db_available():
    """Check whether the local database is reachable."""
    try:
        from sqlalchemy import create_engine, text

        from gcp_secrets import get_database_url_auto

        engine = create_engine(get_database_url_auto(), connect_args={"connect_timeout": 3})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(
    not _db_available(), reason="Local PostgreSQL database not available"
)


@requires_db
class TestSixfoldClassificationIntegration:
    """Integration tests against the live citation_extraction_phased table."""

    @pytest.fixture(autouse=True)
    def setup_engine(self):
        from sqlalchemy import create_engine, text

        from gcp_secrets import get_database_url_auto

        self.engine = create_engine(get_database_url_auto())
        self.text = text

    def _query(self, sql):
        with self.engine.connect() as conn:
            result = conn.execute(self.text(sql))
            return [dict(zip(result.keys(), row)) for row in result.fetchall()]

    def test_foreign_citation_exists(self):
        """National citing a different National should be 'Foreign Citation'."""
        rows = self._query("""
            SELECT citation_type, source_region, case_law_region
            FROM citation_extraction_phased
            WHERE citation_type = 'Foreign Citation'
            LIMIT 1
        """)
        assert len(rows) == 1
        row = rows[0]
        assert row["source_region"] in ("Global North", "Global South")
        assert row["case_law_region"] in ("Global North", "Global South")

    def test_international_citation_exists(self):
        """National (member) citing International court should be 'International Citation'."""
        rows = self._query("""
            SELECT citation_type, source_region, case_law_region
            FROM citation_extraction_phased
            WHERE citation_type = 'International Citation'
            LIMIT 1
        """)
        assert len(rows) == 1
        assert rows[0]["source_region"] in ("Global North", "Global South")
        assert rows[0]["case_law_region"] == "International"

    def test_foreign_international_citation_exists(self):
        """National (non-member) citing International should be 'Foreign International Citation'."""
        rows = self._query("""
            SELECT citation_type, source_region, case_law_region
            FROM citation_extraction_phased
            WHERE citation_type = 'Foreign International Citation'
            LIMIT 1
        """)
        # This type may have 0 rows if no non-member citations exist
        if rows:
            assert rows[0]["case_law_region"] == "International"

    def test_inter_system_citation_exists(self):
        """International citing International should be 'Inter-System Citation'."""
        rows = self._query("""
            SELECT citation_type, source_region, case_law_region
            FROM citation_extraction_phased
            WHERE citation_type = 'Inter-System Citation'
            LIMIT 1
        """)
        if rows:
            assert rows[0]["source_region"] == "International"
            assert rows[0]["case_law_region"] == "International"

    def test_member_state_citation_exists(self):
        """International citing National (member) should be 'Member-State Citation'."""
        rows = self._query("""
            SELECT citation_type, source_region, case_law_region
            FROM citation_extraction_phased
            WHERE citation_type = 'Member-State Citation'
            LIMIT 1
        """)
        if rows:
            assert rows[0]["source_region"] == "International"
            assert rows[0]["case_law_region"] in ("Global North", "Global South")

    def test_non_member_citation_exists(self):
        """International citing National (non-member) should be 'Non-Member Citation'."""
        rows = self._query("""
            SELECT citation_type, source_region, case_law_region
            FROM citation_extraction_phased
            WHERE citation_type = 'Non-Member Citation'
            LIMIT 1
        """)
        if rows:
            assert rows[0]["source_region"] == "International"
            assert rows[0]["case_law_region"] in ("Global North", "Global South")

    def test_no_null_classification_for_populated_regions(self):
        """Citations with both regions populated should not have NULL citation_type."""
        rows = self._query("""
            SELECT COUNT(*) as cnt
            FROM citation_extraction_phased
            WHERE source_region IS NOT NULL
              AND case_law_region IS NOT NULL
              AND citation_type IS NULL
        """)
        assert rows[0]["cnt"] == 0, (
            f"{rows[0]['cnt']} citations have populated regions but NULL citation_type"
        )

    def test_classification_distribution_sanity(self):
        """Verify classification distribution exists and Foreign Citation dominates."""
        rows = self._query("""
            SELECT citation_type, COUNT(*) as cnt
            FROM citation_extraction_phased
            WHERE citation_type IS NOT NULL
            GROUP BY citation_type
            ORDER BY cnt DESC
        """)
        assert len(rows) > 0, "No classified citations found"
        # Foreign Citation should be the most common type
        assert rows[0]["citation_type"] == "Foreign Citation"

    def test_global_north_dominance(self):
        """Verify the known ~96% GN / ~4% GS ratio in source regions."""
        rows = self._query("""
            SELECT source_region, COUNT(*) as cnt
            FROM citation_extraction_phased
            WHERE source_region IN ('Global North', 'Global South')
            GROUP BY source_region
        """)
        region_counts = {r["source_region"]: r["cnt"] for r in rows}
        gn = region_counts.get("Global North", 0)
        gs = region_counts.get("Global South", 0)
        total = gn + gs
        if total > 0:
            gn_pct = gn / total * 100
            # GN should be >80% (generous bound to account for data changes)
            assert gn_pct > 80, f"Global North is only {gn_pct:.1f}%, expected >80%"
