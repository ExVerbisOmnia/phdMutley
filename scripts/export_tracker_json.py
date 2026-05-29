#!/usr/bin/env python3
"""
Dashboard exporter: SPP v2 docs/tracker/tracker.db -> docs/data/progress.json.

Replaces the `export` command of the retired scripts/progress_tracker.legacy.py.
Reads the SPP v2 tracker and reconstructs the *legacy* JSON shape that
docs/progress.html already `fetch`es, so the dashboard keeps working unchanged.

What is reconstructed vs. derived:
    - Legacy-only task fields (priority / owner / due_date / completed_date) are
      parsed back out of the `notes` column where the migration folded them.
    - The 8 meeting action items (migrated into tasks, tagged `[legacy action A*]`)
      are split back out into the dashboard's `action_items` section and excluded
      from the phase task lists, matching the original layout.
    - Phase metadata (status, ordering) is DERIVED — SPP v2 has no phases table.
      Order = first task appearance; status = rolled up from member task statuses.
      Phase descriptions / explicit sort_order from the old `phases` table are not
      carried (acceptable for a local dashboard; full history lives in progress.legacy.db).

Run from repo root:  python scripts/export_tracker_json.py
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "docs" / "tracker" / "tracker.db"
OUT = REPO / "docs" / "data" / "progress.json"

# SPP v2 -> legacy status (inverse of the migration's forward maps)
TASK_STATUS_BACK = {
    "done": "completed", "approved": "pending", "in_progress": "in_progress",
    "blocked": "blocked", "deferred": "deferred", "cancelled": "deferred", "pending": "pending",
}
DECISION_STATUS_BACK = {"validated": "active", "pending_validation": "pending",
                        "superseded": "deferred", "rejected": "deferred"}

ACTION_RE = re.compile(r"\[legacy action (A\d+)\]")


def kv(notes: str | None, key: str) -> str | None:
    """Pull `key: value` out of the pipe-joined notes string."""
    if not notes:
        return None
    m = re.search(rf"{key}:\s*([^|]+)", notes)
    return m.group(1).strip() if m else None


def phase_status(statuses: list[str]) -> str:
    s = set(statuses)
    if s and s <= {"completed", "deferred"}:
        return "completed"
    if "in_progress" in s:
        return "in_progress"
    if "blocked" in s:
        return "blocked"
    return "pending"


def main() -> None:
    assert DB.exists(), f"tracker.db not found: {DB}"
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row

    all_tasks = [dict(r) for r in conn.execute(
        "SELECT id, name, phase, status, description, notes FROM tasks ORDER BY id")]

    # split action-item tasks back out
    action_items, regular = [], []
    for t in all_tasks:
        m = ACTION_RE.search(t["notes"] or "")
        if m:
            action_items.append({
                "id": m.group(1),
                "owner": kv(t["notes"], "owner"),
                "description": t["name"],
                "deadline": kv(t["notes"], "deadline"),
                "status": TASK_STATUS_BACK.get(t["status"], t["status"]),
                "source": kv(t["notes"], "source"),
            })
        else:
            regular.append(t)

    def legacy_task(t: dict) -> dict:
        return {
            "id": t["id"],
            "subject": t["name"],
            "description": t["description"],
            "owner": kv(t["notes"], "owner"),
            "priority": kv(t["notes"], "priority") or "medium",
            "status": TASK_STATUS_BACK.get(t["status"], t["status"]),
            "due_date": kv(t["notes"], "due"),
            "completed_date": kv(t["notes"], "completed"),
        }

    # decisions (legacy shape); keep original status via context "original status: X"
    decisions = []
    for r in conn.execute(
        "SELECT id, scope, subject, status, context, decision, rationale FROM decisions ORDER BY id"
    ):
        orig = kv(r["context"], "original status")
        decisions.append({
            "id": r["id"],
            "title": r["subject"],
            "rationale": r["rationale"] or r["decision"],
            "source": kv(r["context"], "source"),
            "status": orig or DECISION_STATUS_BACK.get(r["status"], r["status"]),
            "scope": r["scope"],
        })

    # phases derived from regular tasks, first-appearance order
    phase_order, phase_tasks = [], {}
    for t in regular:
        ph = t["phase"] or "(unphased)"
        if ph not in phase_tasks:
            phase_tasks[ph] = []
            phase_order.append(ph)
    for t in regular:
        phase_tasks[t["phase"] or "(unphased)"].append(legacy_task(t))

    phases = []
    for i, ph in enumerate(phase_order, 1):
        tasks = phase_tasks[ph]
        phases.append({
            "id": i,
            "name": ph,
            "status": phase_status([t["status"] for t in tasks]),
            "sort_order": i,
            "tasks": tasks,
            "decisions": [d for d in decisions if d["scope"] == ph],
        })

    # dependencies with subjects
    name_by_id = {t["id"]: t["name"] for t in all_tasks}
    dependencies = [{
        "task_id": r["task_id"], "depends_on": r["depends_on_id"], "dep_type": "blocks",
        "task_subject": name_by_id.get(r["task_id"]),
        "depends_on_subject": name_by_id.get(r["depends_on_id"]),
    } for r in conn.execute("SELECT task_id, depends_on_id FROM task_dependencies")]

    task_counts: dict[str, int] = {}
    for t in regular:
        st = TASK_STATUS_BACK.get(t["status"], t["status"])  # legacy keys for the dashboard
        task_counts[st] = task_counts.get(st, 0) + 1
    phase_counts: dict[str, int] = {}
    for p in phases:
        phase_counts[p["status"]] = phase_counts.get(p["status"], 0) + 1

    data = {
        "phases": phases,
        "decisions": decisions,
        "dependencies": dependencies,
        "action_items": action_items,
        "summary": {
            "total_tasks": len(regular),
            "tasks_by_status": task_counts,
            "total_phases": len(phases),
            "phases_by_status": phase_counts,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "deliverable_deadline": "2026-03-09",
            "article_deadline": "2026-03-15",
            "source": "docs/tracker/tracker.db (SPP v2)",
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Exported to {OUT.relative_to(REPO)} "
          f"({len(phases)} phases, {len(regular)} tasks, "
          f"{len(action_items)} action items, {len(decisions)} decisions)")
    conn.close()


if __name__ == "__main__":
    main()
