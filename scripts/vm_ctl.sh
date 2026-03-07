#!/usr/bin/env bash
# vm_ctl.sh — Local CLI for managing the phdMutley pipeline on GCP VM
#
# Usage:
#   ./scripts/vm_ctl.sh start [step-a|step-b|step-d|step-e|all]
#   ./scripts/vm_ctl.sh logs [step]
#   ./scripts/vm_ctl.sh status
#   ./scripts/vm_ctl.sh cmd "any shell command"
#   ./scripts/vm_ctl.sh attach
#   ./scripts/vm_ctl.sh stop
#   ./scripts/vm_ctl.sh download
#   ./scripts/vm_ctl.sh vm-start    # boot the VM
#   ./scripts/vm_ctl.sh vm-stop     # shut down the VM

set -euo pipefail

# ── Config ──────────────────────────────────────────────────────────────────
VM_NAME="phdmutley-pipeline"
VM_ZONE="us-central1-a"
VM_PROJECT="gen-lang-client-0764097936"
REMOTE_DIR="/opt/phdMutley"
REMOTE_VENV="source ${REMOTE_DIR}/venv/bin/activate"
REMOTE_ENV="export GCP_SECRET_PROJECT=${VM_PROJECT} DB_PORT=5432"
GCS_BUCKET="gs://phdmutley-pipeline-transfer"
LOCAL_BACKUP_DIR="$(cd "$(dirname "$0")/.." && pwd)/backups"

# ntfy config (reuse existing)
NTFY_TOPIC="phdmutley-pipeline"
NTFY_SERVER="https://ntfy.sh"

ssh_cmd() {
    gcloud compute ssh "$VM_NAME" \
        --zone="$VM_ZONE" \
        --project="$VM_PROJECT" \
        --command="$1" \
        2>&1
}

ssh_interactive() {
    gcloud compute ssh "$VM_NAME" \
        --zone="$VM_ZONE" \
        --project="$VM_PROJECT" \
        -- "$@"
}

# ── Commands ────────────────────────────────────────────────────────────────

cmd_start() {
    local step="${1:-all}"

    # Build the pipeline command based on step
    local pipeline_cmd=""
    case "$step" in
        step-a)
            pipeline_cmd="cd ${REMOTE_DIR} && ${REMOTE_VENV} && ${REMOTE_ENV} && python scripts/classify_by_title.py --reset 2>&1 | tee logs/step_a_\$(date +%Y%m%d_%H%M%S).log"
            ;;
        step-b)
            pipeline_cmd="cd ${REMOTE_DIR} && ${REMOTE_VENV} && ${REMOTE_ENV} && python scripts/classify_ambiguous_docs.py 2>&1 | tee logs/step_b_\$(date +%Y%m%d_%H%M%S).log"
            ;;
        step-d)
            pipeline_cmd="cd ${REMOTE_DIR} && ${REMOTE_VENV} && ${REMOTE_ENV} && python scripts/3-extract-texts/extract_texts.py --decisions-only 2>&1 | tee logs/step_d_\$(date +%Y%m%d_%H%M%S).log"
            ;;
        step-e)
            pipeline_cmd="cd ${REMOTE_DIR} && ${REMOTE_VENV} && ${REMOTE_ENV} && python scripts/5-extract-citations/extract_citations.py 2>&1 | tee logs/step_e_\$(date +%Y%m%d_%H%M%S).log"
            ;;
        all)
            pipeline_cmd="cd ${REMOTE_DIR} && ${REMOTE_VENV} && ${REMOTE_ENV} && bash scripts/run_pipeline_vm.sh"
            ;;
        *)
            echo "Unknown step: $step"
            echo "Valid steps: step-a, step-b, step-d, step-e, all"
            exit 1
            ;;
    esac

    echo "Starting ${step} in tmux session 'pipeline'..."
    ssh_cmd "tmux kill-session -t pipeline 2>/dev/null; tmux new-session -d -s pipeline '${pipeline_cmd}; echo \"=== PIPELINE FINISHED ===\"; read'"
    echo "Pipeline started. Use './scripts/vm_ctl.sh logs' to stream output."
}

cmd_logs() {
    local step="${1:-}"
    local log_pattern

    if [[ -n "$step" ]]; then
        log_pattern="step_${step//-/_}*.log"
    else
        log_pattern="*.log"
    fi

    echo "Streaming latest log (Ctrl+C to stop)..."
    # Find the most recent log file matching the pattern and tail it
    ssh_cmd "cd ${REMOTE_DIR}/logs && ls -t ${log_pattern} 2>/dev/null | head -1 | xargs -I{} tail -f {}"
}

cmd_status() {
    ssh_cmd "
        ${REMOTE_ENV} && \
        echo '=== VM STATUS ===' && \
        uptime && \
        echo '' && \
        echo '=== TMUX SESSIONS ===' && \
        tmux list-sessions 2>/dev/null || echo '  No active sessions' && \
        echo '' && \
        echo '=== PIPELINE STATUS ===' && \
        cat ${REMOTE_DIR}/pipeline_status.json 2>/dev/null | python3 -m json.tool || echo '  No status file yet' && \
        echo '' && \
        echo '=== DB CLASSIFICATION COUNTS ===' && \
        cd ${REMOTE_DIR} && ${REMOTE_VENV} && \
        python3 -c \"
import sys; sys.path.insert(0, 'scripts')
from gcp_secrets import get_engine
from sqlalchemy import text
engine = get_engine()
with engine.connect() as conn:
    total = conn.execute(text('SELECT COUNT(*) FROM documents')).scalar()
    decisions = conn.execute(text('SELECT COUNT(*) FROM documents WHERE is_decision = TRUE')).scalar()
    non_dec = conn.execute(text('SELECT COUNT(*) FROM documents WHERE is_decision = FALSE')).scalar()
    null_dec = conn.execute(text('SELECT COUNT(*) FROM documents WHERE is_decision IS NULL')).scalar()
    extracted = conn.execute(text('SELECT COUNT(*) FROM extracted_text')).scalar()
    citations = conn.execute(text('SELECT COUNT(DISTINCT document_id) FROM citation_extraction_phased_summary WHERE extraction_success = TRUE')).scalar() if conn.execute(text(\\\"SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='citation_extraction_phased_summary')\\\")).scalar() else 0
    print(f'  Total docs:       {total:>6}')
    print(f'  is_decision=TRUE: {decisions:>6}')
    print(f'  is_decision=FALSE:{non_dec:>6}')
    print(f'  is_decision=NULL: {null_dec:>6}')
    print(f'  Texts extracted:  {extracted:>6}')
    print(f'  Citations done:   {citations:>6}')
engine.dispose()
\" && \
        echo '' && \
        echo '=== DISK ===' && \
        df -h /opt | tail -1
    "
}

cmd_cmd() {
    local remote_command="${1:?Usage: vm_ctl.sh cmd \"command\"}"
    ssh_cmd "cd ${REMOTE_DIR} && ${REMOTE_VENV} && ${REMOTE_ENV} && ${remote_command}"
}

cmd_attach() {
    echo "Attaching to tmux session 'pipeline' (Ctrl+B, D to detach)..."
    # Use interactive SSH with tmux attach
    ssh_interactive -t "tmux attach-session -t pipeline 2>/dev/null || tmux new-session -s pipeline"
}

cmd_stop() {
    echo "Sending Ctrl+C to pipeline tmux session..."
    ssh_cmd "tmux send-keys -t pipeline C-c 2>/dev/null && echo 'Interrupt sent' || echo 'No pipeline session found'"
}

cmd_download() {
    mkdir -p "$LOCAL_BACKUP_DIR"
    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)
    local dump_name="db_after_pipeline_${timestamp}.sql"

    echo "Dumping database on VM..."
    ssh_cmd "cd ${REMOTE_DIR} && ${REMOTE_ENV} && pg_dump -U phdmutley -p 5432 -d climate_litigation > /tmp/${dump_name}"

    echo "Downloading via GCS..."
    ssh_cmd "gcloud storage cp /tmp/${dump_name} ${GCS_BUCKET}/${dump_name}"
    gcloud storage cp "${GCS_BUCKET}/${dump_name}" "${LOCAL_BACKUP_DIR}/${dump_name}"

    echo "Download complete: ${LOCAL_BACKUP_DIR}/${dump_name}"
    echo "To restore locally:"
    echo "  psql -U phdmutley -p 5433 -d climate_litigation < ${LOCAL_BACKUP_DIR}/${dump_name}"
}

cmd_vm_start() {
    echo "Starting VM ${VM_NAME}..."
    gcloud compute instances start "$VM_NAME" --zone="$VM_ZONE" --project="$VM_PROJECT"
    echo "VM started."
}

cmd_vm_stop() {
    echo "Stopping VM ${VM_NAME}..."
    gcloud compute instances stop "$VM_NAME" --zone="$VM_ZONE" --project="$VM_PROJECT"
    echo "VM stopped."
}

# ── Dispatch ────────────────────────────────────────────────────────────────

case "${1:-help}" in
    start)      cmd_start "${2:-all}" ;;
    logs)       cmd_logs "${2:-}" ;;
    status)     cmd_status ;;
    cmd)        cmd_cmd "${2:-}" ;;
    attach)     cmd_attach ;;
    stop)       cmd_stop ;;
    download)   cmd_download ;;
    vm-start)   cmd_vm_start ;;
    vm-stop)    cmd_vm_stop ;;
    help|--help|-h)
        echo "vm_ctl.sh — Manage phdMutley pipeline on GCP VM"
        echo ""
        echo "Commands:"
        echo "  start [step]   Start pipeline step in tmux (step-a|step-b|step-d|step-e|all)"
        echo "  logs [step]    Stream latest log file in real-time"
        echo "  status         Show VM status, DB counts, pipeline progress"
        echo "  cmd \"...\"      Run arbitrary command on VM"
        echo "  attach         Attach to tmux session (interactive)"
        echo "  stop           Send Ctrl+C to running pipeline"
        echo "  download       Dump DB and download to local machine"
        echo "  vm-start       Boot the VM"
        echo "  vm-stop        Shut down the VM"
        ;;
    *)
        echo "Unknown command: $1 (try --help)"
        exit 1
        ;;
esac
