# Project Build Tracker

SPP v2.0 — see `~/.claude/protocols/SPP.md`.

The SQLite file at `tracker.db` is the canonical record of build work for this project. The schema is exactly SPP v2 §4.

## Common reads

```sh
sqlite3 tracker.db "SELECT id, name, status FROM tasks WHERE status='in_progress' ORDER BY updated_at DESC"
sqlite3 tracker.db "SELECT id, scope, subject FROM decisions WHERE status='pending_validation' ORDER BY timestamp DESC"
```
