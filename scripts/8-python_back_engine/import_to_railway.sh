#!/bin/bash
# =============================================================================
# DATABASE IMPORT SCRIPT - Local Backup to Railway
# =============================================================================

set -e

BACKUP_DIR="./db_backup"

# 1. Find the latest backup file
LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/climate_litigation_*.sql 2>/dev/null | head -n1)

if [ -z "$LATEST_BACKUP" ]; then
    echo "❌ No backup files found in $BACKUP_DIR"
    exit 1
fi

echo "✓ Found latest backup: $LATEST_BACKUP"

# 2. Get Railway Database URL
if [ -z "$1" ]; then
    echo ""
    echo "Please paste your Railway DATABASE_URL:"
    read -r RAILWAY_URL
else
    RAILWAY_URL="$1"
fi

if [ -z "$RAILWAY_URL" ]; then
    echo "❌ No Database URL provided."
    exit 1
fi

# Check for internal URL
if [[ "$RAILWAY_URL" == *"railway.internal"* ]]; then
    echo ""
    echo "⚠️  WARNING: INTERNAL URL DETECTED"
    echo "   You provided a URL ending in '.railway.internal'."
    echo "   This URL only works from INSIDE the Railway network."
    echo ""
    echo "   To import from your local machine, you need the PUBLIC URL."
    echo "   1. Go to Railway Dashboard -> Your Project -> PostgreSQL Service."
    echo "   2. Click 'Connect' tab."
    echo "   3. Under 'Public Networking', click 'Enable' (if not enabled)."
    echo "   4. Copy the 'Public Connection URL' (usually looks like: postgresql://...roundhouse.proxy.rlwy.net...)."
    echo ""
    echo "   Please re-run this script with the PUBLIC URL."
    exit 1
fi

echo ""
echo "=============================================="
echo "  IMPORTING TO RAILWAY"
echo "=============================================="
echo "Target: Railway PostgreSQL"
echo "Source: $LATEST_BACKUP"
echo "----------------------------------------------"

# 3. Run Import
# Use PGPASSWORD if needed, but usually URL handles it.
# We use the URL directly with psql.

psql "$RAILWAY_URL" < "$LATEST_BACKUP"

echo ""
echo "✅ Import completed successfully!"
