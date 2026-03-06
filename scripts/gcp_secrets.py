"""
Centralized Secrets Management via Google Cloud Secret Manager
===============================================================
All credentials are stored in GCP Secret Manager. No .env files — ever.

Local dev:  project extreme-hull-489213-p9, PostgreSQL on localhost:5433.
GCP VM:     project gen-lang-client-0764097936, PostgreSQL on localhost:5432.
            Set GCP_SECRET_PROJECT and DB_PORT env vars; password resolves
            from Secret Manager automatically (same secret, both projects).

Authentication: IAM via Application Default Credentials (ADC).
  - Local: `gcloud auth application-default login`
  - VM:    default Compute Engine service account (scopes=cloud-platform)

Usage:
    from gcp_secrets import get_secret, get_db_config, get_database_url

Secret naming convention: phdmutley-<kebab-case-name>
"""

import functools
import logging
import os

from google.cloud import secretmanager

logger = logging.getLogger(__name__)

GCP_PROJECT = os.environ.get("GCP_SECRET_PROJECT", "extreme-hull-489213-p9")

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
    Resolve DB password from GCP Secret Manager.

    INPUT: None
    OUTPUT: Password string
    """
    try:
        return get_secret("phdmutley-db-password")
    except Exception:
        logger.warning("Could not fetch DB password from Secret Manager")
        return ""


def get_gemini_api_key() -> str:
    """
    Resolve Gemini API key: env var override -> GCP Secret Manager.

    INPUT: None (checks GEMINI_API_KEY env var, then GCP)
    OUTPUT: API key string
    """
    env_key = os.environ.get("GEMINI_API_KEY")
    if env_key:
        return env_key
    return get_secret("phdmutley-gemini-api-key")


def get_db_config() -> dict:
    """
    Returns the DB_CONFIG dict used by SQLAlchemy throughout the pipeline.
    Env var overrides for non-secret connection params (DB_HOST, DB_PORT).
    Password always from Secret Manager — no .env files.
    """
    return {
        "drivername": "postgresql+psycopg2",
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": os.environ.get("DB_PORT", "5433"),
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


# Backward compatibility alias (was Railway/Docker auto-resolver, now just get_database_url)
get_database_url_auto = get_database_url


def get_engine(**kwargs):
    """
    Return a configured SQLAlchemy engine.

    INPUT: **kwargs passed to create_engine (e.g. echo=True, pool_size=5)
    OUTPUT: SQLAlchemy Engine instance
    """
    from sqlalchemy import create_engine

    defaults = {"pool_pre_ping": True}
    defaults.update(kwargs)
    return create_engine(get_database_url(), **defaults)
