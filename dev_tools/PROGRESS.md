# phdMutley Progress Tracker

**Primary tracking is now in `docs/tracker/tracker.db` (SPP v2, Harness-managed).** Read with `sqlite3 docs/tracker/tracker.db "SELECT id, name, status FROM tasks WHERE status='in_progress'"` or via the Harness UI. Refresh the dashboard (`docs/progress.html`) with `python scripts/export_tracker_json.py`. Legacy: `progress.legacy.db` + `scripts/progress_tracker.legacy.py` (frozen, audit only). ID map: `docs/tracker/legacy-id-mapping.md`.

## Completed Phases
- [x] Phase A: Data integrity fixes (Mar 2026)
- [x] Phase B: Gemini LLM migration (Mar 2026)
- [x] Phase B+: Reproducibility & code quality (Mar 2026)
- [x] Phase C: Docker integration (Mar 2026)
- [x] Phase D: Railway → GitHub Pages migration (Mar 2026)

## v2.0 Pipeline (Active — see `specs/master-plan-v2.md`)
- [ ] Phase 1: DB Schema Evolution (Sabin IDs)
- [ ] Phase 2: Seed Data & Download (--test-run flag)
- [ ] Phase 3: Markdown Extraction
- [ ] Phase 4: Knowledge Base Construction
- [ ] Phase 5: Citation Extraction v6 (Sabin-filtered)
- [ ] Phase 6: Analysis Engine v2 & Static Export
- [ ] Phase 7: Trial Run (100 docs)
- [ ] Phase 8: Full Run & Deliverable (deadline: 9 Mar)

## Deferred
- [ ] **Enable GitHub Pages** in repository settings (Settings → Pages → Source: main, /docs)
- [ ] **Parquet/DuckDB export layer** — Export analysis results to Parquet for archival
- [ ] CI/CD pipeline with GitHub Actions + Docker
- [ ] Multi-stage Dockerfile for smaller production image

## Backlog
- [ ] Validate full pipeline execution end-to-end in Docker
