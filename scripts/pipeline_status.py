"""
Pipeline Status Tracker — writes pipeline_status.json for vm_ctl.sh monitoring.

Usage in pipeline scripts:

    from pipeline_status import PipelineStatus
    status = PipelineStatus("step-a")
    status.update(processed=100, total=2921, errors=0)
    status.complete(decisions=2921, non_decisions=9375)
    status.error("Something went wrong")
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

STATUS_FILE = Path(__file__).resolve().parent.parent / "pipeline_status.json"

# ntfy config — optional, best-effort
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "phdmutley-pipeline")


def _send_ntfy(title: str, message: str, priority: str = "default"):
    """Best-effort push notification via ntfy. Never raises."""
    try:
        import urllib.request

        req = urllib.request.Request(
            f"{NTFY_SERVER}/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={
                "Title": title,
                "Priority": priority,
                "Tags": "clipboard",
            },
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass  # Non-critical — don't break the pipeline for a notification


class PipelineStatus:
    """Track and persist pipeline step progress."""

    def __init__(self, step_name: str):
        self.step_name = step_name
        self.start_time = time.time()
        self.data = {
            "step": step_name,
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": None,
            "processed": 0,
            "total": 0,
            "errors": 0,
            "elapsed_seconds": 0,
            "eta_seconds": None,
            "details": {},
        }
        self._write()
        _send_ntfy(f"Pipeline: {step_name}", f"Step {step_name} started")

    def update(self, processed: int, total: int, errors: int = 0, **details):
        """Update progress. Call periodically from the processing loop."""
        elapsed = time.time() - self.start_time
        eta = None
        if processed > 0 and total > 0:
            rate = processed / elapsed
            remaining = total - processed
            eta = remaining / rate if rate > 0 else None

        self.data.update({
            "status": "running",
            "processed": processed,
            "total": total,
            "errors": errors,
            "elapsed_seconds": round(elapsed, 1),
            "eta_seconds": round(eta, 1) if eta else None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "details": details,
        })
        self._write()

    def complete(self, **details):
        """Mark step as complete. Sends ntfy notification."""
        elapsed = time.time() - self.start_time
        self.data.update({
            "status": "completed",
            "elapsed_seconds": round(elapsed, 1),
            "eta_seconds": 0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "details": {**self.data.get("details", {}), **details},
        })
        self._write()

        mins = elapsed / 60
        msg = f"Done in {mins:.1f}min. {self.data['processed']}/{self.data['total']} processed, {self.data['errors']} errors."
        if details:
            detail_str = ", ".join(f"{k}={v}" for k, v in details.items())
            msg += f"\n{detail_str}"
        _send_ntfy(
            f"Pipeline: {self.step_name} complete",
            msg,
            priority="high",
        )

    def error(self, message: str):
        """Record a fatal error. Sends high-priority ntfy notification."""
        elapsed = time.time() - self.start_time
        self.data.update({
            "status": "error",
            "elapsed_seconds": round(elapsed, 1),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "details": {**self.data.get("details", {}), "error": message},
        })
        self._write()
        _send_ntfy(
            f"Pipeline ERROR: {self.step_name}",
            message,
            priority="urgent",
        )

    def _write(self):
        """Persist current status to JSON file."""
        try:
            STATUS_FILE.write_text(
                json.dumps(self.data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass  # Don't crash the pipeline over status persistence
