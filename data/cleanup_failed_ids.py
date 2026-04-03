#!/usr/bin/env python3
"""Delete summary + citation rows for failed extraction IDs so they get reprocessed."""
import os
import subprocess

# Get DB password from Secret Manager
db_pass = subprocess.check_output(
    ["gcloud", "secrets", "versions", "access", "latest",
     "--secret=phdmutley-db-password",
     "--project=gen-lang-client-0764097936"],
    text=True
).strip()

# Read failed IDs
with open("/tmp/failed_ids.txt") as f:
    ids = [line.strip() for line in f if line.strip()]

print(f"Total failed IDs to clean up: {len(ids)}")

# Connect and delete
import psycopg2
conn = psycopg2.connect(
    host="localhost", port=5432, dbname="climate_litigation",
    user="phdmutley", password=db_pass
)
cur = conn.cursor()

# Check how many exist
cur.execute(
    "SELECT COUNT(*) FROM citation_extraction_phased_summary WHERE document_id = ANY(%s::uuid[])",
    (ids,)
)
existing = cur.fetchone()[0]
print(f"Found {existing} of {len(ids)} failed IDs with summary rows in DB")

# Delete citations first (FK constraint)
cur.execute(
    "DELETE FROM citation_extraction_phased WHERE document_id = ANY(%s::uuid[])",
    (ids,)
)
cit_deleted = cur.rowcount
print(f"Deleted {cit_deleted} citation rows")

# Delete discarded citations
cur.execute(
    "DELETE FROM citation_extraction_discarded WHERE document_id = ANY(%s::uuid[])",
    (ids,)
)
disc_deleted = cur.rowcount
print(f"Deleted {disc_deleted} discarded citation rows")

# Delete summaries
cur.execute(
    "DELETE FROM citation_extraction_phased_summary WHERE document_id = ANY(%s::uuid[])",
    (ids,)
)
sum_deleted = cur.rowcount
print(f"Deleted {sum_deleted} summary rows")

conn.commit()
cur.close()
conn.close()

print(f"\nCleanup complete. {len(ids)} documents will be reprocessed on next pipeline run.")
