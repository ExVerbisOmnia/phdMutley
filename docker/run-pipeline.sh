#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# run-pipeline.sh — Run phdMutley pipeline phases inside Docker
# =============================================================================
# Usage:
#   ./docker/run-pipeline.sh all     # Phases 0-8
#   ./docker/run-pipeline.sh 0       # Single phase
#   ./docker/run-pipeline.sh 2-5     # Range of phases
#   ./docker/run-pipeline.sh 9       # Export static site data
#   ./docker/run-pipeline.sh export  # Alias for phase 9

COMPOSE_FILE="$(dirname "$0")/docker-compose.yml"

declare -A PHASE_SCRIPTS=(
    [0]="/app/scripts/0-initialize-database/init_database.py"
    [1]="/app/scripts/1-download-decisions/download_decisions.py"
    [2]="/app/scripts/2-populate-metadata/populate_metadata.py"
    [3]="/app/scripts/3-extract-texts/extract_texts.py"
    [4]="/app/scripts/4-classify-decisions/classify_decisions.py"
    [5]="/app/scripts/5-extract-citations/extract_citations.py"
    [8]="/app/scripts/8-python_back_engine/sixfold_analysis_engine.py"
)

run_phase() {
    local phase="$1"; shift
    local extra_args=("$@")
    local script="${PHASE_SCRIPTS[$phase]:-}"
    if [[ -z "$script" ]]; then
        echo "ERROR: Unknown phase $phase (valid: 0-5, 8)"
        return 1
    fi
    echo "=========================================="
    echo "  Phase $phase: $script"
    if [[ ${#extra_args[@]} -gt 0 ]]; then
        echo "  Extra args: ${extra_args[*]}"
    fi
    echo "=========================================="
    docker compose -f "$COMPOSE_FILE" --profile pipeline run --rm pipeline "$script" "${extra_args[@]}"
}

run_export() {
    echo "=========================================="
    echo "  Phase 9: Export static site data"
    echo "=========================================="
    docker compose -f "$COMPOSE_FILE" --profile export run --rm export
}

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <all|phase|start-end|export> [extra-args...]"
    echo "  $0 all                  # Run phases 0-5, 8"
    echo "  $0 0                    # Run phase 0 only"
    echo "  $0 2-5                  # Run phases 2 through 5"
    echo "  $0 9                    # Export static site data to docs/data/"
    echo "  $0 export               # Alias for phase 9"
    echo "  $0 1 --test-run 100     # Run phase 1 with 100-doc test run"
    echo "  $0 all --test-run 100   # Run all phases with 100-doc test run"
    exit 1
fi

ARG="$1"; shift
EXTRA_ARGS=("$@")

if [[ "$ARG" == "all" ]]; then
    for phase in 0 1 2 3 4 5 8; do
        run_phase "$phase" "${EXTRA_ARGS[@]}"
    done
elif [[ "$ARG" == "export" || "$ARG" == "9" ]]; then
    run_export
elif [[ "$ARG" =~ ^([0-9]+)-([0-9]+)$ ]]; then
    start="${BASH_REMATCH[1]}"
    end="${BASH_REMATCH[2]}"
    for phase in $(seq "$start" "$end"); do
        # Skip phases 6 and 7 (SQL-only, not scripted)
        if [[ "$phase" == "6" || "$phase" == "7" ]]; then
            echo "Skipping phase $phase (SQL-only, run manually)"
            continue
        fi
        run_phase "$phase" "${EXTRA_ARGS[@]}"
    done
elif [[ "$ARG" =~ ^[0-9]+$ ]]; then
    run_phase "$ARG" "${EXTRA_ARGS[@]}"
else
    echo "ERROR: Invalid argument '$ARG'. Use 'all', a number, a range (e.g., 2-5), or 'export'."
    exit 1
fi

echo ""
echo "Pipeline run complete."
