"""
Centralized Secrets Management via Google Cloud Secret Manager
===============================================================
All credentials for the phdMutley project are stored in GCP Secret Manager
(project: extreme-hull-489213-p9). No .env files are used.

Authentication: IAM via Application Default Credentials (ADC).
Run `gcloud auth application-default login` once to set up.

Usage:
    from gcp_secrets import get_secret, get_db_config, get_database_url

Secret naming convention: phdmutley-<kebab-case-name>
"""

import functools
import logging
import os
from pathlib import Path

from google.cloud import secretmanager

logger = logging.getLogger(__name__)

GCP_PROJECT = "extreme-hull-489213-p9"

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = secretmanager.SecretManagerServiceClient()
    return _client


@functools.lru_cache(maxsize=32)
def get_secret(secret_id: str, version: str = "latest") -> str:
    """
    Fetch a secret value from Google Cloud Secret Manager.

    INPUT:
        - secret_id: The secret name (e.g. 'phdmutley-db-password')
        - version: Version string, defaults to 'latest'
    OUTPUT: The secret value as a string
    """
    client = _get_client()
    name = f"projects/{GCP_PROJECT}/secrets/{secret_id}/versions/{version}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")


def get_db_password() -> str:
    """
    Resolve DB password: Docker secret file -> GCP Secret Manager.

    INPUT: None (reads POSTGRES_PASSWORD_FILE env var, then falls back to GCP)
    OUTPUT: Password string
    """
    secret_file = os.environ.get("POSTGRES_PASSWORD_FILE")
    if secret_file and os.path.isfile(secret_file):
        return Path(secret_file).read_text().strip()
    try:
        return get_secret("phdmutley-db-password")
    except Exception:
        logger.warning("Could not fetch DB password from Secret Manager")
        return ""


def get_gemini_api_key() -> str:
    """
    Resolve Gemini API key: env var -> Docker secret file -> GCP Secret Manager.

    INPUT: None (checks GEMINI_API_KEY, GEMINI_API_KEY_FILE env vars, then GCP)
    OUTPUT: API key string
    """
    env_key = os.environ.get("GEMINI_API_KEY")
    if env_key:
        return env_key
    secret_file = os.environ.get("GEMINI_API_KEY_FILE")
    if secret_file and os.path.isfile(secret_file):
        return Path(secret_file).read_text().strip()
    return get_secret("phdmutley-gemini-api-key")


def get_db_config() -> dict:
    """
    Returns the DB_CONFIG dict used by SQLAlchemy throughout the pipeline.
    Non-secret values use sensible defaults; password comes from Secret Manager.
    """
    return {
        "drivername": "postgresql+psycopg2",
        "host": "localhost",
        "port": "5432",
        "database": "climate_litigation",
        "username": "phdmutley",
        "password": get_db_password(),
    }


def get_database_url() -> str:
    """
    Returns a full PostgreSQL connection URL for scripts that need a string.
    """
    cfg = get_db_config()
    return (
        f"postgresql://{cfg['username']}:{cfg['password']}"
        f"@{cfg['host']}:{cfg['port']}/{cfg['database']}"
    )


def get_database_url_auto() -> str:
    """
    Auto-resolve database URL: Railway DATABASE_URL -> Secret Manager -> localhost fallback.

    INPUT: None (reads from environment and Secret Manager)
    OUTPUT: PostgreSQL connection URL string
    """
    import os

    railway_url = os.getenv("DATABASE_URL")
    if railway_url:
        # SQLAlchemy 2.0+ requires postgresql://, Railway gives postgres://
        if railway_url.startswith("postgres://"):
            railway_url = railway_url.replace("postgres://", "postgresql://", 1)
        return railway_url
    try:
        return get_database_url()
    except Exception:
        return "postgresql://phdmutley:@localhost:5432/climate_litigation"


def get_engine(**kwargs):
    """
    Return a configured SQLAlchemy engine using auto-resolved URL.

    INPUT: **kwargs passed to create_engine (e.g. echo=True, pool_size=5)
    OUTPUT: SQLAlchemy Engine instance
    """
    from sqlalchemy import create_engine

    defaults = {"pool_pre_ping": True}
    defaults.update(kwargs)
    return create_engine(get_database_url_auto(), **defaults)
