#!/bin/bash
# =============================================================================
# DATABASE MIGRATION SCRIPT - Local PostgreSQL to Railway
# =============================================================================
# PhD Climate Litigation Project
# Last Updated: December 01, 2025
# =============================================================================

set -e  # Exit on any error

# --- Configuration ---
LOCAL_DB_HOST="localhost"
LOCAL_DB_PORT="5432"
LOCAL_DB_NAME="climate_litigation"
LOCAL_DB_USER="phdmutley"

BACKUP_DIR="./db_backup"
BACKUP_FILE="${BACKUP_DIR}/climate_litigation_$(date +%Y%m%d_%H%M%S).sql"

# --- Create backup directory ---
mkdir -p "$BACKUP_DIR"

echo "=============================================="
echo "  DATABASE MIGRATION: Local → Railway"
echo "=============================================="
echo ""
echo "Step 1: Exporting local database..."
echo "----------------------------------------------"

# Export database (schema + data)
# --no-owner: Don't set ownership (Railway manages this)
# --no-acl: Don't include access privileges
# --clean: Include DROP statements before CREATE
pg_dump \
    -h "$LOCAL_DB_HOST" \
    -p "$LOCAL_DB_PORT" \
    -U "$LOCAL_DB_USER" \
    -d "$LOCAL_DB_NAME" \
    --no-owner \
    --no-acl \
    --clean \
    --if-exists \
    -f "$BACKUP_FILE"

echo "✓ Database exported to: $BACKUP_FILE"
echo "  Size: $(du -h "$BACKUP_FILE" | cut -f1)"
echo ""

echo "Step 2: Checking export..."
echo "----------------------------------------------"

# Count tables in export
TABLE_COUNT=$(grep -c "CREATE TABLE" "$BACKUP_FILE" || echo "0")
echo "✓ Tables found: $TABLE_COUNT"

# Show first few table names
echo "  Tables:"
grep "CREATE TABLE" "$BACKUP_FILE" | head -10 | sed 's/CREATE TABLE /    - /g' | sed 's/ (.*//g'
echo ""

echo "=============================================="
echo "  NEXT STEPS (Manual)"
echo "=============================================="
echo ""
echo "1. Create PostgreSQL on Railway:"
echo "   railway add --plugin postgresql"
echo ""
echo "2. Get Railway DATABASE_URL:"
echo "   railway variables"
echo ""
echo "3. Import to Railway:"
echo "   psql \"\$DATABASE_URL\" < $BACKUP_FILE"
echo ""
echo "   Or use Railway's web interface to import."
echo ""
echo "=============================================="
