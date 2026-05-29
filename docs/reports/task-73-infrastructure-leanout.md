# Task #73: Infrastructure Lean-out Report

**Date:** 5 March 2026
**Protocol:** DevProtocol_1 (explore -> plan -> execute)
**Status:** COMPLETED

## Exploration Findings

Two agents audited the codebase:

### Docker Remnants (78 references found)
- `docker/` directory: Dockerfile, docker-compose.yml, run-pipeline.sh, secrets/, requirements-docker.txt
- `gcp_secrets.py`: 3 Docker-specific code paths (POSTGRES_PASSWORD_FILE, GEMINI_API_KEY_FILE, DATABASE_URL/Railway)
- `.gitignore`: Docker-specific entries
- `.claude/CLAUDE.md`: References to Docker being "retained for reference"

### Hosting Assessment
- Dashboard is **100% static** — single HTML file, client-side JS, pre-computed JSON
- No API endpoints, no auth, no server-side rendering, no dynamic content
- GitHub Pages is **completely sufficient** for all current and foreseeable needs
- Cloud Run/Cloud Functions would add **zero value** and unnecessary complexity

## Decision

**GitHub Pages stays. Docker goes. No Cloud Run/Functions needed.**

## Changes Made

### 1. `scripts/gcp_secrets.py` — Simplified
- Removed: `POSTGRES_PASSWORD_FILE` Docker secret file fallback
- Removed: `GEMINI_API_KEY_FILE` Docker secret file fallback
- Removed: `DATABASE_URL` / Railway URL auto-detection (`get_database_url_auto()`)
- Removed: `from pathlib import Path` (no longer needed)
- Kept: `GEMINI_API_KEY` env var override (useful for CI/testing)
- Added: `get_database_url_auto = get_database_url` alias for backward compat (10 scripts import it)
- Simplified: `get_engine()` now calls `get_database_url()` directly

### 2. `docker/` directory — Deleted
- Dockerfile, docker-compose.yml, run-pipeline.sh, secrets/, requirements-docker.txt
- Recoverable from git history if ever needed

### 3. `.gitignore` — Cleaned
- Removed Docker-specific entries (secrets/, .env)
- Added comment noting Docker was removed

### 4. `.claude/CLAUDE.md` — Updated
- Removed "retained for reference" note
- Added clear statement: "Docker is not used for this project"

## Verification

All functions tested after changes:
- `get_db_config()`: OK
- `get_database_url()`: OK
- `get_database_url_auto()` (alias): OK
- `get_engine()` + DB query: OK (91 cases returned)

## Lines of Code Removed

| Item | Lines/Files Removed |
|------|---------------------|
| docker/ directory | ~200 lines across 6 files |
| gcp_secrets.py Docker paths | ~20 lines |
| .gitignore Docker entries | 3 lines |
| Total | ~223 lines of dead infrastructure code |
