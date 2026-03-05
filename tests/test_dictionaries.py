"""
Tests for reference dictionaries used across the citation pipeline.

Validates KNOWN_FOREIGN_COURTS, LANDMARK_CLIMATE_CASES, JURISDICTION_ALIASES,
KNOWN_COUNTRIES, and BINDING_JURISDICTIONS for structural integrity.
"""

from extract_citations_v5_2 import (
    JURISDICTION_ALIASES,
    KNOWN_COUNTRIES,
    KNOWN_FOREIGN_COURTS,
    LANDMARK_CLIMATE_CASES,
)

from config import BINDING_JURISDICTIONS, get_binding_courts

# ============================================================================
# KNOWN_FOREIGN_COURTS
# ============================================================================


class TestKnownForeignCourts:
    REQUIRED_KEYS = {"country", "region", "type"}
    VALID_REGIONS = {"Global North", "Global South", "International"}
    VALID_TYPES = {
        "Supreme",
        "Appellate",
        "Constitutional",
        "Trial",
        "International",
        "Administrative",
        "Environmental",
        "High",
        "Criminal Supreme",
        "Federal",
        "Superior",
    }

    def test_not_empty(self):
        assert len(KNOWN_FOREIGN_COURTS) > 50

    def test_all_entries_have_required_keys(self):
        for court, info in KNOWN_FOREIGN_COURTS.items():
            missing = self.REQUIRED_KEYS - set(info.keys())
            assert not missing, f"Court '{court}' missing keys: {missing}"

    def test_no_empty_string_values(self):
        for court, info in KNOWN_FOREIGN_COURTS.items():
            for key, val in info.items():
                assert val and val.strip(), f"Court '{court}' has empty '{key}'"

    def test_valid_regions(self):
        for court, info in KNOWN_FOREIGN_COURTS.items():
            assert info["region"] in self.VALID_REGIONS, (
                f"Court '{court}' has invalid region '{info['region']}'"
            )

    def test_valid_types(self):
        for court, info in KNOWN_FOREIGN_COURTS.items():
            assert info["type"] in self.VALID_TYPES, (
                f"Court '{court}' has unexpected type '{info['type']}'. Valid: {self.VALID_TYPES}"
            )

    def test_no_duplicate_court_names(self):
        courts = list(KNOWN_FOREIGN_COURTS.keys())
        assert len(courts) == len(set(courts)), "Duplicate court names found"


# ============================================================================
# LANDMARK_CLIMATE_CASES
# ============================================================================


class TestLandmarkClimateCases:
    REQUIRED_KEYS = {"full_name", "country", "region", "year", "court"}
    VALID_REGIONS = {"Global North", "Global South"}

    def test_not_empty(self):
        assert len(LANDMARK_CLIMATE_CASES) >= 15

    def test_all_entries_have_required_keys(self):
        for case, info in LANDMARK_CLIMATE_CASES.items():
            missing = self.REQUIRED_KEYS - set(info.keys())
            assert not missing, f"Case '{case}' missing keys: {missing}"

    def test_valid_regions(self):
        for case, info in LANDMARK_CLIMATE_CASES.items():
            assert info["region"] in self.VALID_REGIONS, (
                f"Case '{case}' has invalid region '{info['region']}'"
            )

    def test_valid_year_range(self):
        for case, info in LANDMARK_CLIMATE_CASES.items():
            year = info["year"]
            assert isinstance(year, int), f"Case '{case}' year is not int: {year}"
            assert 1990 <= year <= 2030, f"Case '{case}' has out-of-range year: {year}"

    def test_no_duplicate_case_names(self):
        cases = list(LANDMARK_CLIMATE_CASES.keys())
        assert len(cases) == len(set(cases)), "Duplicate case names found"


# ============================================================================
# JURISDICTION_ALIASES
# ============================================================================


class TestJurisdictionAliases:
    def test_not_empty(self):
        assert len(JURISDICTION_ALIASES) >= 10

    def test_all_canonical_values_in_known_countries(self):
        for alias, canonical in JURISDICTION_ALIASES.items():
            assert canonical in KNOWN_COUNTRIES, (
                f"Alias '{alias}' → '{canonical}' not in KNOWN_COUNTRIES"
            )

    def test_no_duplicate_aliases(self):
        aliases = list(JURISDICTION_ALIASES.keys())
        assert len(aliases) == len(set(aliases)), "Duplicate alias keys found"

    def test_aliases_are_not_canonical(self):
        """Aliases should differ from their canonical values (otherwise pointless).
        Exception: identity mappings like 'New Zealand' -> 'New Zealand' are allowed
        when the alias exists to catch common alternate forms nearby in the dict."""
        # Known identity mappings that exist for organizational reasons
        allowed_identity = {"New Zealand"}
        for alias, canonical in JURISDICTION_ALIASES.items():
            if alias in allowed_identity:
                continue
            assert alias != canonical, f"Alias '{alias}' maps to itself — redundant"


# ============================================================================
# KNOWN_COUNTRIES
# ============================================================================


class TestKnownCountries:
    def test_minimum_count(self):
        assert len(KNOWN_COUNTRIES) >= 150

    def test_no_duplicate_country_names(self):
        # KNOWN_COUNTRIES is a set, so duplicates are impossible by definition
        # but let's confirm it's indeed a set
        assert isinstance(KNOWN_COUNTRIES, set)

    def test_binding_jurisdiction_members_in_known_countries(self):
        """All countries in BINDING_JURISDICTIONS member lists must appear in KNOWN_COUNTRIES."""
        missing = []
        for court, members in BINDING_JURISDICTIONS.items():
            for country in members:
                if country not in KNOWN_COUNTRIES:
                    missing.append(f"{court}: {country}")
        assert not missing, (
            "Countries in BINDING_JURISDICTIONS not in KNOWN_COUNTRIES:\n" + "\n".join(missing)
        )

    def test_known_foreign_courts_countries_in_known_countries(self):
        """Country values from KNOWN_FOREIGN_COURTS should appear in KNOWN_COUNTRIES
        (with exceptions for supranational entities)."""
        supranational = {
            "United Nations",
            "European Union",
            "Council of Europe",
            "Organization of American States",
            "African Union",
            "Scotland",  # Sub-jurisdiction of UK, not a country
        }
        missing = []
        for court, info in KNOWN_FOREIGN_COURTS.items():
            country = info["country"]
            if country not in KNOWN_COUNTRIES and country not in supranational:
                missing.append(f"{court}: {country}")
        assert not missing, (
            "Court countries not in KNOWN_COUNTRIES or supranational:\n" + "\n".join(missing)
        )


# ============================================================================
# BINDING_JURISDICTIONS
# ============================================================================


class TestBindingJurisdictions:
    def test_has_exactly_three_courts(self):
        assert set(BINDING_JURISDICTIONS.keys()) == {"IACtHR", "ECtHR", "ACHPR"}

    def test_non_empty_member_lists(self):
        for court, members in BINDING_JURISDICTIONS.items():
            assert isinstance(members, list), f"{court} members is not a list"
            assert len(members) > 0, f"{court} has empty member list"

    def test_members_are_strings(self):
        for court, members in BINDING_JURISDICTIONS.items():
            for m in members:
                assert isinstance(m, str), f"{court} has non-string member: {m}"

    def test_no_duplicates_within_each_court(self):
        for court, members in BINDING_JURISDICTIONS.items():
            assert len(members) == len(set(members)), f"{court} has duplicate members"

    def test_get_binding_courts_for_member(self):
        """A known ECtHR member should get ECtHR in their binding courts."""
        result = get_binding_courts("France")
        assert "European Court of Human Rights" in result or "ECtHR" in result

    def test_get_binding_courts_for_iacthtr_member(self):
        """A known IACtHR member should get IACtHR in their binding courts."""
        result = get_binding_courts("Brazil")
        assert "Inter-American Court of Human Rights" in result or "IACtHR" in result

    def test_get_binding_courts_for_non_member(self):
        """A country not in any regional court should only get global courts."""
        result = get_binding_courts("Japan")
        assert "International Court of Justice" in result or "ICJ" in result
        assert "ECtHR" not in result
        assert "IACtHR" not in result

    def test_get_binding_courts_none_returns_global(self):
        """None country should return global courts only."""
        result = get_binding_courts(None)
        assert "ICJ" in result or "International Court of Justice" in result
