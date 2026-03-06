# Docker Dependency Assessment — All Projects

**Date:** 5 March 2026
**Machine:** Windows 11, 8 GB RAM, Docker Desktop with WSL2 backend
**Scope:** All projects in `C:\Users\gusta\proj\` — Aegis, nagumo, phdMutley, platEdu, audiovisual

---

## 1. Docker Usage Inventory Across All Projects

### 1.1 Per-Project Summary

| Project | Docker for Local Dev? | Docker for Deployment? | Services Containerized | Can Remove Docker? |
|---------|:---------------------:|:----------------------:|------------------------|:------------------:|
| **Aegis** | **YES** (critical) | **YES** (Cloud Run) | PostgreSQL+pgvector, FastAPI backend, Nginx frontend | **NO** |
| **nagumo** | No | **YES** (Cloud Run) | Dockerfile + cloudbuild.yaml for GCP | Partially |
| **phdMutley** | YES (but unnecessary) | No | PostgreSQL 18 only | **YES** |
| **platEdu** | Not yet | **YES** (planned) | 1 Dockerfile for static catalog; 5-service compose planned in spec | Not yet relevant |
| **audiovisual** | No | No | None (asset-only folder) | N/A |

### 1.2 Aegis — Docker is Load-Bearing

Aegis is the most Docker-dependent project. Its `docker-compose.yml` orchestrates 3 services:

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `postgres` | `pgvector/pgvector:pg15` | 5432 | Vector DB for RAG embeddings |
| `backend` | Custom Python 3.11 (multi-stage) | 8000 | FastAPI API server |
| `frontend` | Custom Node 22 + Nginx 1.27 | 3000 | React SPA + API proxy |

**Deployment:** Manual push to Google Artifact Registry (`us-central1-docker.pkg.dev/aegis-487910/aegis/`) via `scripts/deploy-cloud-run.ps1`. Both backend and frontend images are built locally with `docker build`, pushed, then deployed to Cloud Run.

**Why Docker can't be removed for Aegis:**
- pgvector requires a PostgreSQL extension not trivially installable on native Windows
- The nginx proxy config (`/api/` -> backend:8000) mirrors production Cloud Run routing
- Multi-stage Dockerfiles are the build system for production artifacts
- 19 SQL migrations are mounted into the Postgres container entrypoint
- Deployment script uses `docker build` + `docker push` directly

### 1.3 nagumo — Docker for Deployment Only

Local development runs `npm run dev` natively (Next.js on :3000). No docker-compose.

Docker is used exclusively for the **Cloud Run deployment pipeline**:
- `Dockerfile`: Multi-stage Node 22-alpine build (deps -> build -> runner)
- `cloudbuild.yaml`: Google Cloud Build triggers on push, builds image, deploys to Cloud Run
- `next.config.ts`: `output: "standalone"` enables the containerized `node server.js` pattern

**Impact of removing Docker locally:** Cloud Build runs in GCP, not on your machine. You could build/push from Cloud Build exclusively and never need Docker locally for nagumo. However, testing the Docker build locally before pushing is useful.

### 1.4 phdMutley — Docker is Pure Overhead

Docker runs a single PostgreSQL 18 container. The `pipeline` and `export` services exist but are **never used in practice** — all scripts run natively via `source venv/bin/activate && python script.py`.

| What Docker provides | What native install provides |
|---------------------|------------------------------|
| PostgreSQL 18 on :5432 | PostgreSQL 18 on :5432 |
| 42 MB container RAM | ~30-50 MB service RAM |
| +2 GB WSL2 VM overhead | No VM overhead |
| 481 MB image + 1.1 GB volume | ~300 MB total |

`gcp_secrets.py:get_database_url_auto()` already resolves to `localhost:5432` — zero code changes needed.

### 1.5 platEdu — Docker is Planned, Not Active

Current state: static SCORM player served via `python -m http.server 8000`. One Dockerfile exists for the catalog SPA (Nginx-based).

The technical spec (v1.1) defines a **future 5-service docker-compose** (postgres:15, redis:7, Django backend, Celery worker, React frontend) that hasn't been created yet. When the Django backend is built, Docker will become necessary for local dev.

---

## 2. Current Docker Resource Footprint

### 2.1 Measured Values (5 March 2026)

| Metric | Value |
|--------|-------|
| Docker images on disk | **18.1 GB** (26 images, only 4 active) |
| Build cache | **8.3 GB** (5.5 GB reclaimable) |
| Volumes | **1.1 GB** |
| **Total Docker disk** | **~27.5 GB** |
| Running containers | 1 (`docker-db-1`, postgres:18, 42 MB) |
| WSL2 VM RAM (no .wslconfig) | **~1.5-3 GB** (uncapped, 50% max = 4 GB) |
| System total RAM | **8 GB** |
| System free RAM at measurement | **1.3 GB** |

### 2.2 The WSL2 Problem

Docker Desktop on Windows requires WSL2 — a full Linux VM. Without a `.wslconfig` file (which this machine lacks), WSL2 can consume up to **50% of system RAM (4 GB)**. With 8 GB total, this leaves Windows competing for memory.

The single PostgreSQL container uses 42 MB. The WSL2 VM hosting it uses **40-70x more** than the workload itself.

---

## 3. Options (Narrowed to A, B, C)

### Option A: Native PostgreSQL for phdMutley + Keep Docker for Everything Else (RECOMMENDED)

**What:** Install PostgreSQL 18 natively on Windows. Stop the Docker postgres:18 container. phdMutley connects to the native instance. Aegis, nagumo, and platEdu continue using Docker as-is. Add `.wslconfig` to cap WSL2 memory.

**Changes per project:**

| Project | Change | Code Changes |
|---------|--------|:------------:|
| **phdMutley** | Connect to native PG instead of Docker PG | None (`gcp_secrets.py` already targets localhost:5432) |
| **Aegis** | No change (keeps its own pgvector container on a different compose network) | None |
| **nagumo** | No change | None |
| **platEdu** | No change | None |

**Port conflict resolution:** Aegis's docker-compose also uses port 5432. Two solutions:
1. Change phdMutley's native PG to port **5433** (update `gcp_secrets.py:get_db_config()` default port)
2. Or change Aegis's docker-compose postgres port mapping to `5433:5432`

Recommended: Option 1 — native PG on 5433, since phdMutley only has one config file to update, while Aegis has multiple references.

**Immediate .wslconfig addition:**

```ini
# C:\Users\gusta\.wslconfig
[wsl2]
memory=2GB
swap=1GB
autoMemoryReclaim=gradual
```

This caps WSL2 at 2 GB and enables automatic memory reclaim when idle, benefiting all Docker-using projects.

| Aspect | Assessment |
|--------|------------|
| **RAM recovered** | ~1-2 GB (WSL2 cap + phdMutley PG off Docker) |
| **Disk recovered** | ~14 GB (prune unused images/cache, remove phdMutley's postgres:18 image) |
| **Migration effort** | 15-20 min (install PG, restore dump, update one port config) |
| **Risk** | Very low — native PG is the standard PostgreSQL setup on Windows |
| **Code changes** | 1 line: port `5432` -> `5433` in `gcp_secrets.py` (or zero if Aegis isn't running simultaneously) |

**Pros:**
- Recovers 1-2 GB RAM and ~14 GB disk
- phdMutley gets 3-10x faster DB I/O (native vs VM filesystem)
- Docker stays available for Aegis (which requires it)
- `.wslconfig` benefits all Docker usage on this machine
- Simplest path — no project loses functionality

**Cons:**
- Two PostgreSQL instances when both phdMutley and Aegis are active (native PG + Aegis's Docker pgvector)
- Minor port management overhead
- Native PG Windows service always running (~30-50 MB — negligible)

**Migration steps:**
1. Create `C:\Users\gusta\.wslconfig` (2 min)
2. `wsl --shutdown` to apply config (restarts Docker's WSL2 VM with 2 GB cap)
3. `docker system prune -a` to clean unused images/cache (~14 GB) (5 min)
4. Download & install [PostgreSQL 18 for Windows](https://www.enterprisedb.com/downloads/postgres-postgresql-downloads) on port 5433, user `phdmutley` (5 min)
5. Restore: `pg_restore -U phdmutley -d climate_litigation -p 5433 backup_file.dump` (2 min)
6. Update `scripts/gcp_secrets.py` line 95: `"port": "5433"` (1 min)
7. Verify: `psql -U phdmutley -d climate_litigation -p 5433 -c "SELECT COUNT(*) FROM cases;"` (1 min)
8. Stop phdMutley's Docker container: `docker stop docker-db-1` (instant)
9. Remove phdMutley's docker-compose services: `docker compose -f docker/docker-compose.yml down` (instant)

---

### Option B: Native PostgreSQL for phdMutley + Remove phdMutley's Docker Config (Keep Docker Desktop)

Same as Option A, plus:

- Delete `phdMutley/docker/` directory from the repo
- Remove phdMutley-specific Docker images and volumes
- Docker Desktop stays installed for Aegis/nagumo/platEdu

| Aspect | Assessment |
|--------|------------|
| **Additional disk recovered** | ~2-3 GB (phdMutley's custom Python image + build cache) |
| **Additional effort** | 5 min (cleanup commands + git commit) |
| **Risk** | Low — the Docker config is recoverable from git history |

**Pros (over Option A):**
- Cleaner repo — removes unused infrastructure code
- No confusion about which PostgreSQL to use
- Slightly more disk recovered

**Cons (over Option A):**
- Irreversible without git history
- Loses the "one command to set up" convenience if someone else needs to reproduce the pipeline (unlikely for a PhD project)

**Additional steps (after Option A):**
1. `docker rmi $(docker images -q)` for phdMutley-specific images
2. `docker volume rm docker_pgdata`
3. Delete `phdMutley/docker/` directory
4. Commit: `git add -A && git commit -m "remove Docker config: migrated to native PostgreSQL"`

---

### Option C: Keep Docker for Everything + Optimize WSL2 Configuration

**What:** Change nothing structurally. Add `.wslconfig` to cap WSL2 memory. Clean up unused Docker images.

| Aspect | Assessment |
|--------|------------|
| **RAM recovered** | ~1-2 GB (WSL2 cap from uncapped -> 2 GB, auto-reclaim reduces idle to ~200 MB) |
| **Disk recovered** | ~14 GB (prune unused images/cache) |
| **Migration effort** | 2 minutes (create .wslconfig, run prune) |
| **Performance** | No improvement (VM I/O layer remains for phdMutley's database) |
| **Code changes** | None |

**Pros:**
- Zero risk — nothing changes architecturally
- Immediate RAM relief via `.wslconfig`
- Docker available for all projects without modification
- `autoMemoryReclaim=gradual` dramatically reduces idle memory (3 GB -> ~200 MB when no containers are busy)

**Cons:**
- phdMutley still pays VM overhead for a 42 MB database
- Still slower DB I/O than native
- Doesn't address the fundamental mismatch (containers for a solo dev database)
- 1.3 GB free RAM at measurement suggests the system is under pressure even with optimization

---

## 4. Cross-Project Impact Matrix

| Criterion | A: Native PG + Docker optimized | B: Native PG + Remove phdMutley Docker | C: Optimize Docker only |
|-----------|:------:|:------:|:------:|
| **Aegis impact** | None | None | None |
| **nagumo impact** | None | None | None |
| **phdMutley impact** | Positive (faster DB) | Positive (faster DB, cleaner repo) | Minimal (WSL2 cap helps) |
| **platEdu impact** | None | None | None |
| **RAM recovery** | 1-2 GB | 1-2 GB | 1-2 GB |
| **Disk recovery** | ~14 GB | ~17 GB | ~14 GB |
| **Migration time** | 20 min | 25 min | 2 min |
| **Code changes** | 1 line (port) | 1 line + delete dir | 0 |
| **Risk** | Very low | Low | None |
| **Docker Desktop required?** | Yes (Aegis) | Yes (Aegis) | Yes (Aegis) |

---

## 5. Recommendation

**Option A: Native PostgreSQL for phdMutley + Keep Docker Desktop optimized** — with `.wslconfig` as the immediate first step.

### Rationale

1. **Docker Desktop cannot be removed.** Aegis requires it for local development (3-service compose with pgvector) and for building/pushing Cloud Run deployment images. This eliminates Option B from v1 of this report (full Docker removal).

2. **phdMutley gains the most from native PostgreSQL.** It's the only project running a persistent Docker container (the others use Docker for builds or not at all). Moving its database to native PG eliminates the largest ongoing resource drain.

3. **`.wslconfig` is a universal win.** With no config file, WSL2 can grab up to 4 GB. Capping at 2 GB with `autoMemoryReclaim=gradual` immediately recovers ~1 GB and reduces idle footprint to ~200 MB. This benefits Aegis's Docker usage too.

4. **`docker system prune` recovers massive disk.** 18.1 GB in images with only 4 active — that's ~14 GB of dead weight from accumulated builds and experiments.

5. **Zero code changes for other projects.** Only phdMutley's `gcp_secrets.py` needs a port update (and only if running simultaneously with Aegis's Postgres).

### Execution Priority

| Priority | Action | Time | Impact |
|----------|--------|------|--------|
| **P0 (now)** | Create `.wslconfig` with memory=2GB + autoMemoryReclaim | 2 min | +1 GB RAM |
| **P0 (now)** | `docker system prune -a` to clean dead images | 5 min | +14 GB disk |
| **P1 (this week)** | Install native PostgreSQL 18, restore phdMutley data | 15 min | +0.5-1 GB RAM, 3-10x faster DB |
| **P2 (optional)** | Remove `phdMutley/docker/` from repo | 5 min | Cleaner codebase |
| **P3 (future)** | When platEdu's Django backend is built, audit its Docker needs against available RAM | — | Prevent future RAM pressure |

### Future Consideration: platEdu

The platEdu technical spec defines a 5-service docker-compose (postgres, redis, Django, Celery, React). When this is built, you'll have Aegis (3 services) + platEdu (5 services) potentially competing for Docker resources. At that point, consider:
- Sharing a single PostgreSQL instance between projects (different databases, same server)
- Running only one project's compose stack at a time
- Using native PostgreSQL + native Redis for platEdu's local dev (same argument as phdMutley)

---

## Sources

- [Benchmark PostgreSQL Docker vs Native — ITNEXT](https://itnext.io/benchmark-postgresql-docker-versus-native-2dde6b5a8552)
- [Docker vs Native PostgreSQL Performance — Secnep](https://secnep.com/docker-vs-native-postgresql-performance-comparison/)
- [Best WSL Settings for Low-Memory Systems (8GB) — rsw.io](https://rsw.io/best-wsl-settings-for-low-memory-systems-8gb-ram-or-less/)
- [Docker Desktop Idle Memory Usage — Docker Forums](https://forums.docker.com/t/docker-desktop-idle-memory-usage/138540)
- [Docker Desktop Memory (VmmemWSL) — DevOps.dev](https://blog.devops.dev/docker-desktop-using-too-much-memory-vmmemwsl-cause-and-solution-0a54998ab65a)
- [PostgreSQL Windows Installers — postgresql.org](https://www.postgresql.org/download/windows/)
- [EDB PostgreSQL Downloads](https://www.enterprisedb.com/downloads/postgres-postgresql-downloads)
- [WSL2 Memory Issues on 8GB — GitHub #7080](https://github.com/microsoft/WSL/issues/7080)
- [Configuring Docker Desktop Memory on Windows — OneUptime](https://oneuptime.com/blog/post/2026-02-08-how-to-configure-docker-desktop-memory-and-cpu-limits-on-windows/view)
- [Limiting Memory Usage in WSL2 — Aleksandr Hovhannisyan](https://www.aleksandrhovhannisyan.com/blog/limiting-memory-usage-in-wsl-2/)
