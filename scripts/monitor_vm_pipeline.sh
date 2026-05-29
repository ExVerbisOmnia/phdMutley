#!/bin/bash
# Monitor VM pipeline execution every 5 minutes
# Sends ntfy notification when complete
# Usage: bash scripts/monitor_vm_pipeline.sh [target_docs]

TARGET=${1:-4724}
PROJECT="gen-lang-client-0764097936"
ZONE="us-central1-a"
VM="phdmutley-pipeline"
INTERVAL=300  # 5 minutes

echo "=== PhD Pipeline Monitor ==="
echo "Target: $TARGET documents"
echo "Checking every $(( INTERVAL / 60 )) minutes..."
echo ""

while true; do
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

    # Run the status script on the VM
    OUTPUT=$(gcloud compute ssh "$VM" --zone="$ZONE" --project="$PROJECT" \
        --command="cd /opt/phdMutley && source venv/bin/activate && python3 scripts/vm_detailed_status.py $TARGET" \
        2>/dev/null)

    if [ $? -ne 0 ]; then
        echo "[$TIMESTAMP] SSH connection failed — retrying in $INTERVAL seconds"
        sleep $INTERVAL
        continue
    fi

    echo "[$TIMESTAMP]"
    echo "$OUTPUT"
    echo ""

    # Check if complete
    if echo "$OUTPUT" | grep -q "STATUS: COMPLETE"; then
        echo "=== PIPELINE COMPLETE ==="
        # Send ntfy notification
        chcp.com 65001 > /dev/null 2>&1
        powershell.exe -NoProfile -File C:/Users/gusta/bin/notify.ps1 \
            -Message "PhD: full re-run complete. $TARGET documents processed." \
            -Title "PhD Pipeline Complete"
        break
    fi

    # Check if process died
    if echo "$OUTPUT" | grep -q "Process: STOPPED"; then
        PROCESSED=$(echo "$OUTPUT" | grep "Processed:" | head -1)
        if echo "$OUTPUT" | grep -q "STATUS: COMPLETE"; then
            break
        fi
        echo "*** WARNING: Process stopped before completion! ***"
        echo "$PROCESSED"
        chcp.com 65001 > /dev/null 2>&1
        powershell.exe -NoProfile -File C:/Users/gusta/bin/notify.ps1 \
            -Message "PhD: pipeline STOPPED before completion! $PROCESSED" \
            -Title "PhD Pipeline STOPPED"
        break
    fi

    sleep $INTERVAL
done
