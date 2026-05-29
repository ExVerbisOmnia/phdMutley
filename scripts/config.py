# config.py
"""
Central Configuration for phdMutley Project
===========================================
Centralizes paths, database connections, constants, and jurisdiction logic.

VERSION: 5.0 - Pydantic Settings
- Pydantic-validated configuration with __getitem__ bridge for backward compat
- Credentials resolve via gcp_secrets: env vars first, then GCP Secret Manager
  (project: extreme-hull-489213-p9). Env vars documented in .env.template.
- Authentication for Secret Manager: IAM via Application Default Credentials.
"""

import os
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_DNS, uuid5

from pydantic import computed_field
from pydantic_settings import BaseSettings

from gcp_secrets import get_db_config, get_gemini_api_key

# Base Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PDF_DOWNLOAD_DIR = PROJECT_ROOT / "pdfs/downloaded"
LOGS_DIR = PROJECT_ROOT / "logs"
DATABASE_FILE = PROJECT_ROOT / "data/seed/SABIN_DB-2026-02-23.xlsx"

# Create directories immediately
PDF_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Database Configuration — credentials from Secret Manager
DB_CONFIG = get_db_config()

# UUID Generation
UUID_NAMESPACE = uuid5(NAMESPACE_DNS, "climatecasechart.com.phdmutley")


# =============================================================================
# PYDANTIC SETTINGS CLASSES
# =============================================================================


class _DictBridge:
    """Mixin that allows CONFIG['KEY'] and CONFIG.get('KEY') access for backward compat."""

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key.lower())

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except AttributeError:
            return default


class PipelineSettings(_DictBridge, BaseSettings):
    """Validated pipeline configuration."""

    concurrent_downloads: int = 10
    request_timeout: int = 30
    scanned_pdf_threshold: int = 100
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-pro"
    classification_model: str = "gemini-2.5-pro"
    extraction_model: str = "gemini-2.5-flash"
    model_context_window: int = 1_000_000
    model_max_output: int = 65536
    safe_token_threshold: int = 900_000
    classification_text_limit: int = 3000
    min_confidence: float = 0.3

    @computed_field
    @property
    def max_workers(self) -> int:
        return max(1, int((os.cpu_count() or 2) * 0.5))


class TestRunSettings(_DictBridge, BaseSettings):
    """Test run configuration — reproducible random sampling via --test-run N."""

    enabled: bool = False
    sample_size: int = 100
    random_seed: int = 42


class TrialBatchSettings(_DictBridge, BaseSettings):
    """Trial batch filtering — targets specific documents marked in Excel."""

    enabled: bool = False
    column_name: str = "Trial batch"
    true_values: list[Any] = [True, "TRUE", "True", "true", 1, "1", "yes", "Yes", "YES"]


# =============================================================================
# SINGLETON INSTANCES — drop-in replacements for the old dicts
# =============================================================================

CONFIG = PipelineSettings(gemini_api_key=get_gemini_api_key())
TEST_RUN_CONFIG = TestRunSettings()
TRIAL_BATCH_CONFIG = TrialBatchSettings()


# =============================================================================
# JURISDICTION MAPPING
# =============================================================================

BINDING_JURISDICTIONS = {
    # --- Inter-American Court of Human Rights (IACtHR) ---
    "IACtHR": [
        "Argentina",
        "Barbados",
        "Bolivia",
        "Brazil",
        "Chile",
        "Colombia",
        "Ecuador",
        "Paraguay",
        "Peru",
        "Suriname",
        "Uruguay",
        "Costa Rica",
        "El Salvador",
        "Guatemala",
        "Honduras",
        "Nicaragua",
        "Panama",
        "Mexico",
        "Haiti",
        "Dominican Republic",
    ],
    # --- European Court of Human Rights (ECtHR) ---
    "ECtHR": [
        "Albania",
        "Germany",
        "Andorra",
        "Armenia",
        "Austria",
        "Azerbaijan",
        "Belgium",
        "Bosnia and Herzegovina",
        "Bulgaria",
        "Cyprus",
        "Croatia",
        "Denmark",
        "Slovakia",
        "Slovenia",
        "Spain",
        "Estonia",
        "Finland",
        "France",
        "Georgia",
        "Greece",
        "Hungary",
        "Ireland",
        "Iceland",
        "Italy",
        "Latvia",
        "Liechtenstein",
        "Lithuania",
        "Luxembourg",
        "North Macedonia",
        "Malta",
        "Moldova",
        "Monaco",
        "Montenegro",
        "Norway",
        "Netherlands",
        "Poland",
        "Portugal",
        "United Kingdom",
        "Czech Republic",
        "Romania",
        "San Marino",
        "Serbia",
        "Sweden",
        "Switzerland",
        "Turkey",
        "Ukraine",
    ],
    # --- African Court on Human and Peoples' Rights (ACHPR) ---
    "ACHPR": [
        "Algeria",
        "Benin",
        "Burkina Faso",
        "Burundi",
        "Cameroon",
        "Chad",
        "Comoros",
        "Congo",
        "Ivory Coast",
        "Cote d'Ivoire",
        "Gabon",
        "Gambia",
        "Ghana",
        "Guinea-Bissau",
        "Kenya",
        "Lesotho",
        "Libya",
        "Malawi",
        "Mali",
        "Mauritania",
        "Mozambique",
        "Niger",
        "Nigeria",
        "Rwanda",
        "Western Sahara",
        "Senegal",
        "South Africa",
        "Tanzania",
        "Togo",
        "Tunisia",
        "Uganda",
        "Zambia",
        "Zimbabwe",
    ],
}

# Global courts applicable to essentially everyone for the purpose of this study
GLOBAL_COURTS = [
    "International Court of Justice",
    "ICJ",
    "International Tribunal for the Law of the Sea",
    "ITLOS",
]


def get_binding_courts(country):
    """
    Returns a string list of binding international courts for a given country.
    """
    if not country:
        return ", ".join(GLOBAL_COURTS)

    binding = list(GLOBAL_COURTS)  # Start with global courts

    # check IACtHR
    if country in BINDING_JURISDICTIONS["IACtHR"]:
        binding.extend(["Inter-American Court of Human Rights", "IACtHR", "Corte IDH"])

    # check ECtHR
    if country in BINDING_JURISDICTIONS["ECtHR"]:
        binding.extend(["European Court of Human Rights", "ECHR", "ECtHR", "CEDH"])

    # check ACHPR
    if country in BINDING_JURISDICTIONS["ACHPR"]:
        binding.extend(["African Court on Human and Peoples' Rights", "ACHPR", "Corte Africana"])

    return ", ".join(set(binding))
