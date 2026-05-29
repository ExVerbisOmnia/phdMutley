#!/usr/bin/env python3
"""
Progress Tracker — SQLite database for project task management.

Stores phases, tasks, decisions, and dependencies. Serves JSON for the
progress dashboard (docs/progress.html).

Usage:
    python scripts/progress_tracker.py init      # Create DB + seed data
    python scripts/progress_tracker.py status     # Print status summary
    python scripts/progress_tracker.py export     # Export JSON to docs/data/progress.json
    python scripts/progress_tracker.py update TASK_ID STATUS  # Update task status
"""

import json
import os
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    sys.stdout.reconfigure(encoding="utf-8")

DB_PATH = Path(__file__).resolve().parent.parent / "progress.db"
EXPORT_PATH = Path(__file__).resolve().parent.parent / "docs" / "data" / "progress.json"


def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ─── Schema ───────────────────────────────────────────────────────────────────


def init_schema(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS phases (
            id          INTEGER PRIMARY KEY,
            name        TEXT NOT NULL,
            description TEXT,
            status      TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','in_progress','completed','blocked')),
            start_date  TEXT,
            due_date    TEXT,
            completed_date TEXT,
            sort_order  INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            phase_id    INTEGER NOT NULL REFERENCES phases(id),
            subject     TEXT NOT NULL,
            description TEXT,
            owner       TEXT,
            priority    TEXT NOT NULL DEFAULT 'medium'
                        CHECK (priority IN ('critical','high','medium','low')),
            status      TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','in_progress','completed','blocked','deferred')),
            due_date    TEXT,
            completed_date TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS decisions (
            id          TEXT PRIMARY KEY,
            title       TEXT NOT NULL,
            rationale   TEXT,
            source      TEXT,
            status      TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','implemented','active','deferred')),
            phase_id    INTEGER REFERENCES phases(id),
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS dependencies (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id     INTEGER NOT NULL REFERENCES tasks(id),
            depends_on  INTEGER NOT NULL REFERENCES tasks(id),
            dep_type    TEXT NOT NULL DEFAULT 'blocks'
                        CHECK (dep_type IN ('blocks','related')),
            UNIQUE(task_id, depends_on)
        );

        CREATE TABLE IF NOT EXISTS action_items (
            id          TEXT PRIMARY KEY,
            owner       TEXT NOT NULL,
            description TEXT NOT NULL,
            deadline    TEXT,
            status      TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','in_progress','completed')),
            source      TEXT
        );

        CREATE TRIGGER IF NOT EXISTS tasks_updated_at
        AFTER UPDATE ON tasks
        BEGIN
            UPDATE tasks SET updated_at = datetime('now') WHERE id = NEW.id;
        END;
    """)
    conn.commit()


# ─── Seed Data ────────────────────────────────────────────────────────────────


def seed_data(conn):
    """Populate with current project state — all known phases, tasks, decisions."""

    # ── Completed infrastructure phases ──
    completed_phases = [
        (100, "v1.0 (1st Run)", "Full pipeline: 2,924 decisions processed, deployed on Railway",
         "completed", "2025-11-01", "2025-11-30", "2025-11-30", -5),
        (101, "Phase A: Data Integrity", "Duplicate columns, hardcoded paths, bare excepts, tests",
         "completed", "2026-03-01", "2026-03-02", "2026-03-02", -4),
        (102, "Phase B: Gemini Migration", "Anthropic SDK to google-genai for all LLM calls",
         "completed", "2026-03-02", "2026-03-02", "2026-03-02", -3),
        (103, "Phase B+: Reproducibility", "Ruff, Pydantic config, pinned deps, Alembic, pipeline models",
         "completed", "2026-03-02", "2026-03-03", "2026-03-03", -2),
        (104, "Phase C: Docker Integration", "Dockerfile, docker-compose, run-pipeline.sh, Docker secrets",
         "completed", "2026-03-03", "2026-03-03", "2026-03-03", -1),
        (105, "Phase D: GitHub Pages Migration", "Railway decommissioned, static site at docs, export script",
         "completed", "2026-03-04", "2026-03-04", "2026-03-04", 0),
    ]

    # ── v2.0 pipeline phases ──
    v2_phases = [
        (1, "Phase 1: DB Schema Evolution", "Add Sabin Case/Document IDs, Alembic migration",
         "pending", None, "2026-03-04", None, 1),
        (2, "Phase 2: Seed Data & Download", "Load updated Excel, --test-run flag, download pipeline",
         "blocked", None, "2026-03-04", None, 2),
        (3, "Phase 3: Markdown Extraction", "PDF to Markdown instead of plain text",
         "pending", None, "2026-03-05", None, 3),
        (4, "Phase 4: Knowledge Base", "Build case metadata index from Sabin/Columbia data",
         "pending", None, "2026-03-05", None, 4),
        (5, "Phase 5: Citation Extraction v6", "Sabin-filtered extraction with knowledge base",
         "pending", None, "2026-03-06", None, 5),
        (6, "Phase 6: Analysis & Export v2", "Updated engine, top-5, static maps, disclaimer",
         "pending", None, "2026-03-07", None, 6),
        (7, "Phase 7: Trial Run (100 docs)", "Validate full v2.0 pipeline on sample",
         "pending", None, "2026-03-07", None, 7),
        (8, "Phase 8: Full Run & Deliverable", "Process all documents, generate maps + text for Joana",
         "pending", None, "2026-03-09", None, 8),
    ]

    for row in completed_phases + v2_phases:
        conn.execute(
            "INSERT OR IGNORE INTO phases (id, name, description, status, start_date, due_date, completed_date, sort_order) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", row
        )

    # ── Tasks ──
    tasks = [
        # Phase 1 tasks
        (1, 1, "Add sabin_case_id / sabin_document_id columns", None, "Gustavo", "high", "pending", "2026-03-04"),
        (2, 1, "Create Alembic migration for new columns", None, "Gustavo", "high", "pending", "2026-03-04"),
        (3, 1, "Update init_database.py for new schema", None, "Gustavo", "medium", "pending", "2026-03-04"),
        (4, 1, "Update populate_metadata.py to store Sabin IDs", None, "Gustavo", "high", "pending", "2026-03-04"),
        # Phase 2 tasks
        (5, 2, "Implement --test-run N CLI flag across pipeline scripts", None, "Gustavo", "critical", "pending", "2026-03-04"),
        (6, 2, "Add TestRunSettings to config.py", None, "Gustavo", "high", "pending", "2026-03-04"),
        (7, 2, "Adapt populate_metadata.py for new Excel structure", None, "Gustavo", "high", "pending", "2026-03-04"),
        (8, 2, "Acquire updated Columbia/Sabin Excel", None, "Lucas", "critical", "pending", None),
        # Phase 3 tasks
        (9, 3, "Evaluate Markdown conversion libraries", None, "Gustavo", "high", "pending", "2026-03-05"),
        (10, 3, "Modify extract_texts.py for Markdown output", None, "Gustavo", "high", "pending", "2026-03-05"),
        (11, 3, "Add text_md column to extracted_text table", None, "Gustavo", "medium", "pending", "2026-03-05"),
        # Phase 4 tasks
        (12, 4, "Create build_knowledge_base.py", None, "Gustavo", "critical", "pending", "2026-03-05"),
        (13, 4, "Design batching strategy for context windows", None, "Gustavo", "high", "pending", "2026-03-05"),
        (14, 4, "Export knowledge base as JSON for validation", None, "Gustavo", "medium", "pending", "2026-03-05"),
        # Phase 5 tasks
        (15, 5, "Design v6 extraction prompt with knowledge base", None, "Gustavo", "critical", "pending", "2026-03-06"),
        (16, 5, "Implement Sabin filter (citation → Sabin case matching)", None, "Gustavo", "critical", "pending", "2026-03-06"),
        (17, 5, "Implement snippet extraction with char-count anchoring", None, "Gustavo", "high", "pending", "2026-03-06"),
        (18, 5, "Generate validation Excel for Lucas review", None, "Gustavo", "high", "pending", "2026-03-06"),
        (19, 5, "Cost estimation: tokens × docs × price", None, "Gustavo", "medium", "pending", "2026-03-05"),
        # Phase 6 tasks
        (20, 6, "Update analysis engine for v2.0 citation data", None, "Gustavo", "high", "pending", "2026-03-07"),
        (21, 6, "Add top-5 jurisdiction queries", None, "Gustavo", "high", "pending", "2026-03-07"),
        (22, 6, "Generate static maps (top-5 + US aesthetic)", None, "Gustavo", "high", "pending", "2026-03-07"),
        (23, 6, "Add error margin disclaimer", None, "Gustavo", "medium", "pending", "2026-03-07"),
        # Phase 7 tasks
        (24, 7, "Execute --test-run 100 through full pipeline", None, "Gustavo", "critical", "pending", "2026-03-07"),
        (25, 7, "Monitor cost, errors, processing time", None, "Gustavo", "high", "pending", "2026-03-07"),
        (26, 7, "Lucas validates sample of results", None, "Lucas", "critical", "pending", "2026-03-07"),
        # Phase 8 tasks
        (27, 8, "Full pipeline run on all documents", None, "Gustavo", "critical", "pending", "2026-03-08"),
        (28, 8, "Generate final static maps for Joana", None, "Gustavo", "critical", "pending", "2026-03-08"),
        (29, 8, "Write 2-3 descriptive paragraphs", None, "Lucas", "critical", "pending", "2026-03-09"),
        (30, 8, "Package and deliver to Joana/Kate", None, "Both", "critical", "pending", "2026-03-09"),
    ]

    for row in tasks:
        conn.execute(
            "INSERT OR IGNORE INTO tasks (id, phase_id, subject, description, owner, priority, status, due_date) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", row
        )

    # ── Dependencies (task_id depends_on) ──
    deps = [
        # Phase 2 blocked by Excel from Lucas
        (7, 8, "blocks"),   # Excel needed before metadata adaptation
        (5, 8, "blocks"),   # Excel needed for test-run to have data
        # Phase 3 can run on existing data (no hard dep on Phase 2)
        # Phase 4 depends on Phase 1 (needs Sabin IDs in DB)
        (12, 4, "blocks"),  # KB needs Sabin IDs populated
        # Phase 5 depends on Phase 3 + Phase 4
        (15, 10, "blocks"),  # v6 prompt needs Markdown texts
        (15, 12, "blocks"),  # v6 prompt needs knowledge base
        (16, 12, "blocks"),  # Sabin filter needs knowledge base
        # Phase 6 depends on Phase 5
        (20, 16, "blocks"),  # Analysis needs v6 citations
        # Phase 7 depends on Phase 5 + Phase 6
        (24, 20, "blocks"),  # Trial run needs analysis engine
        (24, 5, "blocks"),   # Trial run needs --test-run flag
        # Phase 8 depends on Phase 7
        (27, 24, "blocks"),  # Full run after trial validation
        (29, 28, "blocks"),  # Text after maps
    ]

    for task_id, depends_on, dep_type in deps:
        conn.execute(
            "INSERT OR IGNORE INTO dependencies (task_id, depends_on, dep_type) VALUES (?, ?, ?)",
            (task_id, depends_on, dep_type)
        )

    # ── Decisions ──
    decisions = [
        ("D1", "Sabin-only citation filter", "Australia data noise from non-climate citations", "Meeting 3 Mar", "pending", 5),
        ("D2", "Gemini as primary LLM", "Cheaper, matches benchmarks, Lucas has credits", "Meeting 3 Mar", "implemented", None),
        ("D3", "Markdown text extraction", "Better optimized for LLM processing", "Meeting 3 Mar", "pending", 3),
        ("D4", "Use Sabin Case/Document IDs", "Sabin DB already provides both IDs", "Meeting 3 Mar", "pending", 1),
        ("D5", "No wholesale reclassification", "Too expensive; trust Sabin scope", "Meeting 3 Mar", "active", None),
        ("D6", "Build Knowledge step before extraction", "Dramatically improved recall in corporate-cases project", "Meeting 3 Mar", "pending", 4),
        ("D7", "Snippets after filter only", "Don't waste tokens on discarded citations", "Meeting 3 Mar", "pending", 5),
        ("D8", "Gustavo handles all pipeline work", "Iterative work, dividing creates overhead", "Meeting 3 Mar", "active", None),
        ("D9", "Top-5 format for deliverable", "Comfortable with ranked format given data imperfections", "Meeting 3 Mar", "pending", 6),
        ("D10", "Error margin disclaimer", "Transparency about LLM limitations", "Meeting 3 Mar", "pending", 6),
        ("D11", "Trial run: 100 random documents", "Validate before full-scale execution", "Session 4 Mar", "pending", 7),
    ]

    for row in decisions:
        conn.execute(
            "INSERT OR IGNORE INTO decisions (id, title, rationale, source, status, phase_id) "
            "VALUES (?, ?, ?, ?, ?, ?)", row
        )

    # ── Action Items from meeting ──
    actions = [
        ("A1", "Lucas", "Acquire updated Columbia/Sabin Excel with latest cases", None, "pending", "Meeting 3 Mar"),
        ("A2", "Gustavo", "Pipeline v2.0 development and execution (all phases)", "2026-03-08", "in_progress", "Meeting 3 Mar"),
        ("A3", "Lucas", "Develop map presentation (text, colors, aesthetics)", "2026-03-08", "pending", "Meeting 3 Mar"),
        ("A4", "Lucas", "Write descriptive/reflective paragraphs (pending data)", "2026-03-09", "pending", "Meeting 3 Mar"),
        ("A5", "Both", "Daily touchpoints (morning sync + end-of-day review)", None, "in_progress", "Meeting 3 Mar"),
        ("A6", "Lucas", "Create Discord/Teams room for always-on communication", "2026-03-04", "pending", "Meeting 3 Mar"),
        ("A7", "Gustavo", "Estimate token costs for full pipeline run", "2026-03-05", "pending", "Meeting 3 Mar"),
        ("A8", "Both", "Consider Columbia Junior Scholars submission (15 Mar)", "2026-03-10", "pending", "Meeting 3 Mar"),
    ]

    for row in actions:
        conn.execute(
            "INSERT OR IGNORE INTO action_items (id, owner, description, deadline, status, source) "
            "VALUES (?, ?, ?, ?, ?, ?)", row
        )

    conn.commit()


# ─── Export ───────────────────────────────────────────────────────────────────


def export_json(conn):
    """Export all tracker data as a single JSON for the dashboard."""
    data = {}

    # Phases
    phases = []
    for row in conn.execute("SELECT * FROM phases ORDER BY sort_order"):
        p = dict(row)
        # Attach tasks
        p["tasks"] = [dict(t) for t in conn.execute(
            "SELECT * FROM tasks WHERE phase_id = ? ORDER BY id", (p["id"],)
        )]
        # Attach decisions
        p["decisions"] = [dict(d) for d in conn.execute(
            "SELECT * FROM decisions WHERE phase_id = ? ORDER BY id", (p["id"],)
        )]
        phases.append(p)

    data["phases"] = phases

    # Standalone decisions (no phase)
    data["decisions"] = [dict(d) for d in conn.execute(
        "SELECT * FROM decisions ORDER BY id"
    )]

    # Dependencies
    data["dependencies"] = [dict(d) for d in conn.execute(
        "SELECT d.*, t1.subject as task_subject, t2.subject as depends_on_subject "
        "FROM dependencies d "
        "JOIN tasks t1 ON d.task_id = t1.id "
        "JOIN tasks t2 ON d.depends_on = t2.id"
    )]

    # Action items
    data["action_items"] = [dict(a) for a in conn.execute(
        "SELECT * FROM action_items ORDER BY id"
    )]

    # Summary stats
    task_counts = dict(conn.execute(
        "SELECT status, COUNT(*) FROM tasks GROUP BY status"
    ).fetchall())
    phase_counts = dict(conn.execute(
        "SELECT status, COUNT(*) FROM phases GROUP BY status"
    ).fetchall())

    data["summary"] = {
        "total_tasks": sum(task_counts.values()),
        "tasks_by_status": task_counts,
        "total_phases": sum(phase_counts.values()),
        "phases_by_status": phase_counts,
        "exported_at": datetime.now().isoformat(),
        "deliverable_deadline": "2026-03-09",
        "article_deadline": "2026-03-15",
    }

    EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(EXPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    print(f"Exported to {EXPORT_PATH} ({len(data['phases'])} phases, {data['summary']['total_tasks']} tasks)")
    return data


# ─── Status Report ────────────────────────────────────────────────────────────


def print_status(conn):
    print("=" * 60)
    print("phdMutley Progress Tracker")
    print("=" * 60)

    today = date.today().isoformat()
    print(f"\nDate: {today}")
    print(f"Deliverable deadline: 9 March 2026")

    # Phase summary
    print("\n--- Phases ---")
    for row in conn.execute("SELECT * FROM phases ORDER BY sort_order"):
        icon = {"completed": "[x]", "in_progress": "[~]", "pending": "[ ]", "blocked": "[!]"}
        print(f"  {icon.get(row['status'], '[ ]')} {row['name']} — {row['status']}"
              + (f" (due: {row['due_date']})" if row['due_date'] else ""))

    # Task summary
    print("\n--- Task Summary ---")
    for status, count in conn.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status ORDER BY status"):
        print(f"  {status}: {count}")

    # Critical/overdue tasks
    print("\n--- Critical Tasks ---")
    for row in conn.execute(
        "SELECT t.id, t.subject, t.owner, t.due_date, t.status FROM tasks t "
        "WHERE t.priority = 'critical' AND t.status NOT IN ('completed','deferred') "
        "ORDER BY t.due_date"
    ):
        overdue = " *** OVERDUE ***" if row["due_date"] and row["due_date"] < today else ""
        print(f"  #{row['id']} [{row['status']}] {row['subject']} "
              f"(@{row['owner']}, due: {row['due_date']}){overdue}")

    # Blocked items
    print("\n--- Blocked ---")
    blocked = conn.execute(
        "SELECT t.id, t.subject, GROUP_CONCAT(t2.subject, '; ') as blockers "
        "FROM tasks t "
        "JOIN dependencies d ON d.task_id = t.id "
        "JOIN tasks t2 ON d.depends_on = t2.id "
        "WHERE t.status != 'completed' AND t2.status != 'completed' "
        "GROUP BY t.id"
    ).fetchall()
    if blocked:
        for row in blocked:
            print(f"  #{row['id']} {row['subject']} ← blocked by: {row['blockers']}")
    else:
        print("  None")

    print()


# ─── CLI ──────────────────────────────────────────────────────────────────────


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]

    if cmd == "init":
        conn = get_conn()
        init_schema(conn)
        seed_data(conn)
        print(f"Database initialized at {DB_PATH}")
        print_status(conn)
        conn.close()

    elif cmd == "status":
        conn = get_conn()
        print_status(conn)
        conn.close()

    elif cmd == "export":
        conn = get_conn()
        export_json(conn)
        conn.close()

    elif cmd == "update":
        if len(sys.argv) < 4:
            print("Usage: progress_tracker.py update TASK_ID STATUS")
            return
        task_id = int(sys.argv[2])
        new_status = sys.argv[3]
        conn = get_conn()
        conn.execute("UPDATE tasks SET status = ? WHERE id = ?", (new_status, task_id))
        if new_status == "completed":
            conn.execute("UPDATE tasks SET completed_date = ? WHERE id = ?",
                         (datetime.now().isoformat(), task_id))
        conn.commit()
        print(f"Task #{task_id} → {new_status}")
        conn.close()

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)


if __name__ == "__main__":
    main()
