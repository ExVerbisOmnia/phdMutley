#!/bin/bash

# =============================================================================
# DATABASE STRUCTURE AND POPULATION ANALYSIS SCRIPT
# =============================================================================
# INPUT: PostgreSQL connection parameters (modify variables below)
# ALGORITHM: Executes queries to analyze database structure and data population
# OUTPUT: HTML file with complete database analysis
# =============================================================================

# -------------------- CONFIGURATION --------------------
# Modify these variables according to your database connection
DB_NAME="climate_litigation"
DB_USER="phdmutley"
DB_HOST="localhost"
DB_PORT="5432"
OUTPUT_FILE="database_analysis_$(date +%Y%m%d_%H%M%S).html"

# -------------------- HTML HEADER --------------------
cat > "$OUTPUT_FILE" << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Database Structure Analysis</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 20px; background: #1a1a1a; color: #e0e0e0; }
        h1 { color: #4a9eff; }
        h2 { color: #ff8c42; margin-top: 30px; }
        table { border-collapse: collapse; width: 100%; margin: 20px 0; background: #2a2a2a; }
        th { background: #3a3a3a; color: #4a9eff; padding: 12px; text-align: left; border: 1px solid #444; }
        td { padding: 10px; border: 1px solid #444; }
        tr:nth-child(even) { background: #252525; }
        .summary { background: #2a2a2a; padding: 15px; border-radius: 5px; margin: 20px 0; }
        .populated { color: #4ade80; }
        .empty { color: #f87171; }
        .partial { color: #fbbf24; }
    </style>
</head>
<body>
    <h1>PostgreSQL Database Structure and Population Analysis</h1>
    <div class="summary">
        <strong>Generated:</strong> $(date)<br>
        <strong>Database:</strong> $DB_NAME
    </div>
EOF

# -------------------- SECTION 1: TABLE OVERVIEW --------------------
echo "<h2>1. Tables Overview</h2>" >> "$OUTPUT_FILE"
echo "<table><tr><th>Schema</th><th>Table Name</th><th>Row Count</th><th>Status</th></tr>" >> "$OUTPUT_FILE"

psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -A -F"|" << 'EOSQL' | while IFS="|" read -r schema table rows status; do
    echo "<tr><td>$schema</td><td>$table</td><td>$rows</td><td class='$status'>$status</td></tr>" >> "$OUTPUT_FILE"
done
SELECT 
    schemaname,
    tablename,
    COALESCE(n_live_tup::text, '0'),
    CASE 
        WHEN COALESCE(n_live_tup, 0) = 0 THEN 'empty'
        ELSE 'populated'
    END as status
FROM pg_stat_user_tables
ORDER BY schemaname, tablename;
EOSQL

echo "</table>" >> "$OUTPUT_FILE"

# -------------------- SECTION 2: DETAILED COLUMN STRUCTURE --------------------
echo "<h2>2. Detailed Column Structure by Table</h2>" >> "$OUTPUT_FILE"

psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -A -F"|" << 'EOSQL' | while IFS="|" read -r table_name; do
    echo "<h3>Table: $table_name</h3>" >> "$OUTPUT_FILE"
    echo "<table><tr><th>Column</th><th>Data Type</th><th>Nullable</th><th>Default</th></tr>" >> "$OUTPUT_FILE"
    
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -A -F"|" << EOSQL2
        SELECT 
            column_name,
            data_type,
            is_nullable,
            COALESCE(column_default, 'N/A')
        FROM information_schema.columns
        WHERE table_name = '$table_name'
        AND table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY ordinal_position;
EOSQL2
    | while IFS="|" read -r col dtype nullable def; do
        echo "<tr><td>$col</td><td>$dtype</td><td>$nullable</td><td>$def</td></tr>" >> "$OUTPUT_FILE"
    done
    
    echo "</table>" >> "$OUTPUT_FILE"
done
SELECT DISTINCT table_name
FROM information_schema.columns
WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
ORDER BY table_name;
EOSQL

# -------------------- SECTION 3: COLUMN POPULATION ANALYSIS --------------------
echo "<h2>3. Column Population Statistics</h2>" >> "$OUTPUT_FILE"
echo "<p>Shows which columns have data and their fill rates</p>" >> "$OUTPUT_FILE"

# Generate and execute population analysis for each table
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -A -F"|" << 'EOSQL' | while IFS="|" read -r schema table; do
    echo "<h3>Table: $table</h3>" >> "$OUTPUT_FILE"
    echo "<table><tr><th>Column</th><th>Total Rows</th><th>Populated</th><th>Nulls</th><th>Fill %</th></tr>" >> "$OUTPUT_FILE"
    
    # Get columns for this table
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -A -F"|" << EOSQL2
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = '$schema' AND table_name = '$table'
        ORDER BY ordinal_position;
EOSQL2
    | while IFS="|" read -r column; do
        # Query population for this column
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -A -F"|" << EOSQL3
            SELECT 
                '$column',
                COUNT(*),
                COUNT($column),
                COUNT(*) - COUNT($column),
                ROUND(100.0 * COUNT($column) / NULLIF(COUNT(*), 0), 2)
            FROM $schema.$table;
EOSQL3
        | while IFS="|" read -r col total pop nulls pct; do
            class="empty"
            if (( $(echo "$pct > 0" | bc -l) )); then class="partial"; fi
            if (( $(echo "$pct == 100" | bc -l) )); then class="populated"; fi
            echo "<tr><td>$col</td><td>$total</td><td>$pop</td><td>$nulls</td><td class='$class'>$pct%</td></tr>" >> "$OUTPUT_FILE"
        done
    done
    
    echo "</table>" >> "$OUTPUT_FILE"
done
SELECT DISTINCT table_schema, table_name
FROM information_schema.columns
WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
ORDER BY table_schema, table_name;
EOSQL

# -------------------- HTML FOOTER --------------------
cat >> "$OUTPUT_FILE" << 'EOF'
</body>
</html>
EOF

echo "✅ Analysis complete! Output saved to: $OUTPUT_FILE"
echo "📤 Upload this file to Claude to analyze your database structure."