#!/usr/bin/env python3
"""
Full Pipeline Runner — Phases 1-5
===================================
Runs the complete pipeline from download through citation extraction
for the entire Sabin seed dataset (no test-run limits).

Captures all output to a real-time log file at logs/full_pipeline_run_TIMESTAMP.log
"""

import io
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Force UTF-8 on Windows console to handle Unicode in pipeline output
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = LOGS_DIR / f"full_pipeline_run_{TIMESTAMP}.log"

# Pipeline phases in order
PHASES = [
    {
        "name": "Phase 2: Populate Metadata",
        "cmd": [sys.executable, str(SCRIPTS_DIR / "2-populate-metadata" / "populate_metadata.py")],
    },
    {
        "name": "Phase 1: Download PDFs",
        "cmd": [sys.executable, str(SCRIPTS_DIR / "1-download-decisions" / "download_decisions.py")],
    },
    {
        "name": "Phase 3: Extract Texts",
        "cmd": [sys.executable, str(SCRIPTS_DIR / "3-extract-texts" / "extract_texts.py")],
    },
    {
        "name": "Phase 4: Classify Decisions",
        "cmd": [sys.executable, str(SCRIPTS_DIR / "4-classify-decisions" / "classify_decisions.py")],
    },
    {
        "name": "Phase 5: Extract Citations",
        "cmd": [sys.executable, str(SCRIPTS_DIR / "5-extract-citations" / "extract_citations.py")],
    },
]


def run_phase(phase, log_fh):
    """Run a single pipeline phase, streaming output to both console and log file."""
    name = phase["name"]
    cmd = phase["cmd"]
    separator = "=" * 70

    header = f"\n{separator}\n  {name}\n  Command: {' '.join(cmd)}\n  Started: {datetime.now().isoformat()}\n{separator}\n"
    print(header, flush=True)
    log_fh.write(header)
    log_fh.flush()

    start = time.time()
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(PROJECT_ROOT),
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
        )

        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            log_fh.write(line)
            log_fh.flush()

        proc.wait()
        elapsed = time.time() - start
        rc = proc.returncode

        footer = f"\n--- {name} finished in {elapsed:.1f}s (exit code {rc}) ---\n"
        print(footer, flush=True)
        log_fh.write(footer)
        log_fh.flush()

        return rc == 0

    except Exception as e:
        err_msg = f"\n--- {name} EXCEPTION: {e} ---\n"
        print(err_msg, flush=True)
        log_fh.write(err_msg)
        log_fh.flush()
        return False


def main(start_phase=1):
    print(f"Pipeline log: {LOG_FILE}")
    print(f"Started at: {datetime.now().isoformat()}\n")

    # Filter phases based on start_phase
    phase_map = {"Phase 2": 2, "Phase 1": 1, "Phase 3": 3, "Phase 4": 4, "Phase 5": 5}
    active_phases = [
        p for p in PHASES
        if int(p["name"].split(":")[0].replace("Phase ", "").strip()) >= start_phase
    ]

    with open(LOG_FILE, "w", encoding="utf-8") as log_fh:
        log_fh.write(f"Full Pipeline Run - {datetime.now().isoformat()}\n")
        log_fh.write(f"Python: {sys.executable}\n")
        log_fh.write(f"Project: {PROJECT_ROOT}\n\n")

        results = []
        pipeline_start = time.time()

        for phase in active_phases:
            success = run_phase(phase, log_fh)
            results.append((phase["name"], success))
            if not success:
                msg = f"\n!!! {phase['name']} FAILED - stopping pipeline !!!\n"
                print(msg)
                log_fh.write(msg)
                log_fh.flush()
                break

        total_time = time.time() - pipeline_start

        # Summary
        summary = f"\n{'=' * 70}\n  PIPELINE SUMMARY\n  Total time: {total_time:.1f}s ({total_time/60:.1f} min)\n{'=' * 70}\n"
        for name, ok in results:
            status = "OK" if ok else "FAILED"
            summary += f"  [{status}] {name}\n"
        summary += f"{'=' * 70}\n"

        print(summary)
        log_fh.write(summary)
        log_fh.flush()


if __name__ == "__main__":
    import argparse as _ap
    _parser = _ap.ArgumentParser()
    _parser.add_argument("--start-phase", type=int, default=1, help="Start from this phase number (1-5)")
    _args = _parser.parse_args()
    main(start_phase=_args.start_phase)
