#!/usr/bin/env bash
# run_pipeline_vm.sh — Run the full decision-filtered pipeline (Steps A→E) on the VM.
#
# Meant to be called from vm_ctl.sh via tmux, but can also run standalone:
#   cd /opt/phdMutley && source venv/bin/activate && bash scripts/run_pipeline_vm.sh
#
# Each step is run sequentially. If a step fails, the pipeline stops.
# Progress is tracked via pipeline_status.json (read by vm_ctl.sh status).

set -euo pipefail

cd /opt/phdMutley
source venv/bin/activate
export GCP_SECRET_PROJECT="${GCP_SECRET_PROJECT:-gen-lang-client-0764097936}"
export DB_PORT="${DB_PORT:-5432}"

LOGDIR="logs"
mkdir -p "$LOGDIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "========================================"
echo "phdMutley Full Pipeline — ${TIMESTAMP}"
echo "========================================"

# Step A: Title-based classification
echo ""
echo "[$(date +%H:%M:%S)] === STEP A: Title Classification ==="
python scripts/classify_by_title.py --reset 2>&1 | tee "${LOGDIR}/step_a_${TIMESTAMP}.log"
echo "[$(date +%H:%M:%S)] Step A complete."

# Step B+C: LLM classification for ambiguous docs + aggregation
echo ""
echo "[$(date +%H:%M:%S)] === STEP B+C: LLM Classification ==="
python scripts/classify_ambiguous_docs.py 2>&1 | tee "${LOGDIR}/step_b_${TIMESTAMP}.log"
echo "[$(date +%H:%M:%S)] Steps B+C complete."

# Step D: Text extraction (decisions only)
echo ""
echo "[$(date +%H:%M:%S)] === STEP D: Text Extraction ==="
python scripts/3-extract-texts/extract_texts.py --decisions-only 2>&1 | tee "${LOGDIR}/step_d_${TIMESTAMP}.log"
echo "[$(date +%H:%M:%S)] Step D complete."

# Step E: Citation extraction
echo ""
echo "[$(date +%H:%M:%S)] === STEP E: Citation Extraction ==="
python scripts/5-extract-citations/extract_citations.py 2>&1 | tee "${LOGDIR}/step_e_${TIMESTAMP}.log"
echo "[$(date +%H:%M:%S)] Step E complete."

echo ""
echo "========================================"
echo "PIPELINE COMPLETE — $(date)"
echo "========================================"
echo "Next: run './scripts/vm_ctl.sh download' from local machine"
