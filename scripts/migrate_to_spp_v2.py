#!/usr/bin/env python3
"""
One-off migration: legacy progress.db -> SPP v2 docs/tracker/tracker.db.

Onboards phdMutley to Harness SPP v2 (Harness ADR-0015 / ADR-0016).
Source of truth: the repo-root `progress.db` (the richer, authoritative copy;
NOT the stale dev_tools/progress.db). Destination: `docs/tracker/tracker.db`
created by `harness-tracker init`.

INPUT:
    - progress.db (legacy schema: phases / tasks / decisions / dependencies / action_items)
    - docs/tracker/tracker.db (empty SPP v2 schema)
ALGORITHM:
    1. Build legacy-int -> canonical SPP id maps (tasks T-NNN, decisions D-YYYYMMDD-NN).
    2. Insert tasks (phase name string, status-mapped, legacy-only fields folded to notes).
    3. Insert action_items as tasks (owner/deadline/source -> notes).
    4. Insert task_dependencies (remapped ids).
    5. Insert decisions (status-mapped, scope = phase name, source/orig-status -> context).
    6. Write docs/tracker/legacy-id-mapping.md sidecar.
OUTPUT: populated tracker.db + id-mapping sidecar. Idempotent (INSERT OR IGNORE).

Run from repo root:  python scripts/migrate_to_spp_v2.py
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "progress.db"
DST = REPO / "docs" / "tracker" / "tracker.db"
MAPPING_OUT = REPO / "docs" / "tracker" / "legacy-id-mapping.md"

# ---- status mappings -------------------------------------------------------
# legacy task status -> SPP v2 task status
TASK_STATUS = {
    "completed": "done",
    "pending": "approved",       # planned-from-spec tasks; matches leni-borralho precedent
    "in_progress": "in_progress",
    "blocked": "blocked",
    "deferred": "deferred",
}
# legacy action_item status -> SPP v2 task status
ACTION_STATUS = {
    "completed": "done",
    "pending": "approved",
    "in_progress": "in_progress",
}
# legacy decision status -> SPP v2 decision status (original kept in context, lossless)
DECISION_STATUS = {
    "implemented": "validated",
    "active": "validated",
    "pending": "pending_validation",
    "deferred": "pending_validation",  # none present, defensive
}


def iso(ts: str | None) -> str | None:
    """Normalize a legacy timestamp to ISO 8601 UTC (…Z). Best-effort, lossless-ish."""
    if not ts:
        return None
    t = ts.strip().replace(" ", "T")
    if "." in t:                       # drop microseconds
        t = t.split(".", 1)[0]
    if not t.endswith("Z"):
        t += "Z"
    return t


def note_join(parts: list[str]) -> str | None:
    parts = [p for p in parts if p]
    return " | ".join(parts) if parts else None


def main() -> None:
    assert SRC.exists(), f"legacy DB not found: {SRC}"
    assert DST.exists(), f"tracker.db not found (run `harness-tracker init` first): {DST}"

    src = sqlite3.connect(str(SRC))
    src.row_factory = sqlite3.Row
    dst = sqlite3.connect(str(DST))
    dst.execute("PRAGMA foreign_keys = ON")

    # phase_id -> phase name string (SPP tasks.phase is free text)
    phase_name = {
        r["id"]: r["name"] for r in src.execute("SELECT id, name FROM phases")
    }

    # ---- 1. id maps --------------------------------------------------------
    task_id_map: dict[int, str] = {}   # legacy tasks.id -> T-NNN
    counter = 0
    for r in src.execute("SELECT id FROM tasks ORDER BY id"):
        counter += 1
        task_id_map[r["id"]] = f"T-{counter:03d}"

    action_id_map: dict[str, str] = {}  # legacy action_items.id (A1..) -> T-NNN
    for r in src.execute("SELECT id FROM action_items ORDER BY id"):
        counter += 1
        action_id_map[r["id"]] = f"T-{counter:03d}"

    # decisions D1.. -> D-YYYYMMDD-NN (per-day counter over created_at)
    dec_id_map: dict[str, str] = {}
    per_day: dict[str, int] = {}
    for r in src.execute("SELECT id, created_at FROM decisions ORDER BY created_at, id"):
        day = (iso(r["created_at"]) or "1970-01-01T00:00:00Z")[:10].replace("-", "")
        per_day[day] = per_day.get(day, 0) + 1
        dec_id_map[r["id"]] = f"D-{day}-{per_day[day]:02d}"

    # ---- 2. tasks ----------------------------------------------------------
    for r in src.execute("SELECT * FROM tasks ORDER BY id"):
        new_id = task_id_map[r["id"]]
        notes = note_join([
            f"[legacy #{r['id']}]",
            f"priority: {r['priority']}" if r["priority"] else "",
            f"owner: {r['owner']}" if r["owner"] else "",
            f"due: {r['due_date']}" if r["due_date"] else "",
            f"completed: {r['completed_date']}" if r["completed_date"] else "",
        ])
        dst.execute(
            "INSERT OR IGNORE INTO tasks "
            "(id, name, phase, status, parent_id, description, notes, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                new_id,
                r["subject"],
                phase_name.get(r["phase_id"]),
                TASK_STATUS.get(r["status"], "approved"),
                None,
                r["description"],
                notes,
                iso(r["created_at"]) or iso(r["updated_at"]),
                iso(r["updated_at"]) or iso(r["created_at"]),
            ),
        )

    # ---- 3. action_items as tasks -----------------------------------------
    for r in src.execute("SELECT * FROM action_items ORDER BY id"):
        new_id = action_id_map[r["id"]]
        notes = note_join([
            f"[legacy action {r['id']}]",
            f"owner: {r['owner']}" if r["owner"] else "",
            f"deadline: {r['deadline']}" if r["deadline"] else "",
            f"source: {r['source']}" if r["source"] else "",
        ])
        dst.execute(
            "INSERT OR IGNORE INTO tasks "
            "(id, name, phase, status, parent_id, description, notes, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                new_id,
                r["description"],
                "Meeting Action Items (3 Mar)",
                ACTION_STATUS.get(r["status"], "approved"),
                None,
                None,
                notes,
                "2026-03-03T00:00:00Z",
                "2026-03-03T00:00:00Z",
            ),
        )

    # ---- 4. dependencies ---------------------------------------------------
    for r in src.execute("SELECT task_id, depends_on FROM dependencies"):
        a, b = task_id_map.get(r["task_id"]), task_id_map.get(r["depends_on"])
        if a and b and a != b:
            dst.execute(
                "INSERT OR IGNORE INTO task_dependencies (task_id, depends_on_id) VALUES (?,?)",
                (a, b),
            )

    # ---- 5. decisions ------------------------------------------------------
    for r in src.execute("SELECT * FROM decisions ORDER BY created_at, id"):
        new_id = dec_id_map[r["id"]]
        scope = phase_name.get(r["phase_id"]) or "project"
        context = note_join([
            f"legacy id: {r['id']}",
            f"source: {r['source']}" if r["source"] else "",
            f"original status: {r['status']}" if r["status"] else "",
        ])
        dst.execute(
            "INSERT OR IGNORE INTO decisions "
            "(id, timestamp, scope, subject, status, context, decision, rationale, "
            " alternatives, superseded_by, triggered_spec_updates) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                new_id,
                iso(r["created_at"]) or "1970-01-01T00:00:00Z",
                scope,
                r["title"],
                DECISION_STATUS.get(r["status"], "pending_validation"),
                context,
                r["title"],            # the decision = what was decided
                r["rationale"],        # the why / detail
                None,
                None,
                None,
            ),
        )

    dst.commit()

    # ---- 6. mapping sidecar ------------------------------------------------
    lines = ["# Legacy → SPP v2 ID mapping", "",
             "Generated by `scripts/migrate_to_spp_v2.py` during SPP v2 onboarding.",
             "Source: repo-root `progress.legacy.db` (formerly `progress.db`).", "",
             "## Tasks", "", "| legacy id | SPP id |", "| --- | --- |"]
    lines += [f"| {k} | {v} |" for k, v in sorted(task_id_map.items())]
    lines += ["", "## Action items (now tasks)", "", "| legacy id | SPP id |", "| --- | --- |"]
    lines += [f"| {k} | {v} |" for k, v in action_id_map.items()]
    lines += ["", "## Decisions", "", "| legacy id | SPP id |", "| --- | --- |"]
    lines += [f"| {k} | {v} |" for k, v in dec_id_map.items()]
    MAPPING_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ---- report ------------------------------------------------------------
    t = dst.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    d = dst.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    dep = dst.execute("SELECT COUNT(*) FROM task_dependencies").fetchone()[0]
    print(f"[migrate] tasks={t} decisions={d} dependencies={dep}")
    print(f"[migrate] mapping written to {MAPPING_OUT.relative_to(REPO)}")

    src.close()
    dst.close()


if __name__ == "__main__":
    main()
