#!/usr/bin/env python3
"""Auto-launch extraction pipeline when Gemini Flash quota recovers.

Tests with a ~10K token prompt to verify daily quota is available,
then launches extract_citations.py --concurrent 1.
"""
import subprocess
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gemini_client import call_gemini

# Test with ~10K tokens (realistic extraction size)
test_prompt = "Analyze this legal text. " * 1000

try:
    r = call_gemini(test_prompt, model="gemini-2.5-flash", max_retries=1)
    print(f"FLASH QUOTA OK — tokens_in: {r['tokens_in']}, tokens_out: {r['tokens_out']}")
except Exception as e:
    print(f"FLASH QUOTA STILL EXHAUSTED: {e}")
    sys.exit(1)

# Quota is available — clean up any failed summaries first
print("Cleaning up failed summaries...")
subprocess.run([sys.executable, "scripts/vm_cleanup_failed.py"], cwd="/opt/phdMutley")

# Launch pipeline with --concurrent 1 (conservative, avoids thundering herd)
print("Launching pipeline with --concurrent 1...")
log_file = "/tmp/extraction_v7_full_r5.log"
cmd = (
    f"cd /opt/phdMutley/scripts/5-extract-citations && "
    f"PYTHONPATH=/opt/phdMutley/scripts "
    f"nohup python3 extract_citations.py --concurrent 1 > {log_file} 2>&1 &"
)
subprocess.Popen(cmd, shell=True, cwd="/opt/phdMutley")
print(f"Pipeline launched! Log: {log_file}")
print("Monitor with: tail -f /tmp/extraction_v7_full_r5.log")
