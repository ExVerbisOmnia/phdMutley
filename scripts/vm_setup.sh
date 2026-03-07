#!/usr/bin/env bash
# vm_setup.sh — Run ON the VM to configure PostgreSQL auth and restore DB.
# Upload to VM then: sudo bash /opt/phdMutley/scripts/vm_setup.sh

set -euo pipefail

echo "=== Configuring PostgreSQL auth ==="
PG_HBA=$(sudo -u postgres psql -t -c 'SHOW hba_file;' | tr -d ' ')
echo "PG_HBA: $PG_HBA"

# Add md5 auth for phdmutley before the default peer entries
if ! grep -q 'phdmutley' "$PG_HBA"; then
    sed -i '/^local.*all.*all.*peer/i local   all   phdmutley   md5' "$PG_HBA"
    sed -i '/^host.*all.*all.*127/s/scram-sha-256/md5/' "$PG_HBA" 2>/dev/null || true
    echo "host   all   phdmutley   127.0.0.1/32   md5" >> "$PG_HBA"
    systemctl restart postgresql
    sleep 2
    echo "Auth rules added and PG restarted"
else
    echo "Auth rules already configured"
fi

echo "=== Testing connection ==="
PGPASSWORD=197230 psql -U phdmutley -h 127.0.0.1 -d climate_litigation -c 'SELECT 1 as test;'

echo "=== Restoring database ==="
if [ -f /tmp/db.sql ]; then
    PGPASSWORD=197230 psql -U phdmutley -h 127.0.0.1 -d climate_litigation -f /tmp/db.sql > /tmp/db_restore.log 2>&1
    echo "Restore complete (check /tmp/db_restore.log for details)"
else
    echo "No dump file at /tmp/db.sql — skipping restore"
fi

echo "=== Verifying ==="
PGPASSWORD=197230 psql -U phdmutley -h 127.0.0.1 -d climate_litigation -c "
  SELECT 'docs' as tbl, COUNT(*) as cnt FROM documents
  UNION ALL SELECT 'cases', COUNT(*) FROM cases
  UNION ALL SELECT 'extracted', COUNT(*) FROM extracted_text;
"

echo "=== Downloading PDFs ==="
mkdir -p /opt/phdMutley/pdfs/downloaded
cd /opt/phdMutley/pdfs/downloaded
EXISTING=$(ls *.pdf 2>/dev/null | wc -l)
if [ "$EXISTING" -lt 1000 ]; then
    echo "Downloading PDFs from GCS (this may take a few minutes)..."
    gsutil -m -q cp gs://phdmutley-pipeline-transfer/pdfs/* . 2>&1 | tail -3
    echo "PDFs downloaded: $(ls *.pdf | wc -l) files"
else
    echo "PDFs already present: $EXISTING files"
fi

echo "=== Setup complete ==="
