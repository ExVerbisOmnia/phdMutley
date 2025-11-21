#!/bin/bash

# =============================================================================
# DATABASE STRUCTURE AND POPULATION ANALYSIS SCRIPT
# =============================================================================

# -------------------- LOAD ENVIRONMENT VARIABLES --------------------
# Load credentials from .env file if it exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# -------------------- CONFIGURATION --------------------
# Use the correct database name
DB_NAME="climate_litigation"
DB_USER="${POSTGRES_USER:-phdmutley}"
DB_PASSWORD="${POSTGRES_PASSWORD}"
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"
OUTPUT_FILE="database_analysis_$(date +%Y%m%d_%H%M%S).html"

# Set password for psql to avoid prompts
export PGPASSWORD="$DB_PASSWORD"

# -------------------- TEST CONNECTION --------------------
echo "Testing database connection..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT version();" > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "❌ Failed to connect to database. Check your credentials in .env"
    exit 1
fi
echo "✅ Connected successfully to $DB_NAME!"

# -------------------- START HTML --------------------
cat > "$OUTPUT_FILE" << 'HTMLHEADER'
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
        h3 { color: #fbbf24; margin-top: 20px; }
        table { border-collapse: collapse; width: 100%; margin: 20px 0; background: #2a2a2a; }
        th { background: #3a3a3a; color: #4a9eff; padding: 12px; text-align: left; border: 1px solid #444; }
        td { padding: 10px; border: 1px solid #444; }
        tr:nth-child(even) { background: #252525; }
        .summary { background: #2a2a2a; padding: 15px; border-radius: 5px; margin: 20px 0; }
        .populated { color: #4ade80; font-weight: bold; }
        .empty { color: #f87171; font-weight: bold; }
        .partial { color: #fbbf24; font-weight: bold; }
    </style>
</head>
<body>
HTMLHEADER

# Add timestamp and database info
cat >> "$OUTPUT_FILE" << HTMLINFO
    <h1>PostgreSQL Database Structure and Population Analysis</h1>
    <div class="summary">
        <strong>Generated:</strong> $(date)<br>
        <strong>Database:</strong> $DB_NAME<br>
        <strong>User:</strong> $DB_USER<br>
        <strong>Host:</strong> $DB_HOST:$DB_PORT
    </div>
HTMLINFO

# -------------------- SECTION 1: TABLES OVERVIEW --------------------
echo "<h2>1. Tables Overview</h2>" >> "$OUTPUT_FILE"
echo "<table><tr><th>Table Name</th><th>Row Count</th><th>Status</th></tr>" >> "$OUTPUT_FILE"

# Get list of tables and count rows
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -A -c "
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
ORDER BY table_name;
" | while read -r table; do
    # Get row count for this table
    row_count=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -A -c "SELECT COUNT(*) FROM public.\"$table\";")
    
    if [ "$row_count" -eq 0 ]; then
        status="empty"
        status_text="Empty"
    else
        status="populated"
        status_text="Has Data"
    fi
    
    echo "<tr><td>$table</td><td>$row_count</td><td class='$status'>$status_text</td></tr>" >> "$OUTPUT_FILE"
done

echo "</table>" >> "$OUTPUT_FILE"

# -------------------- SECTION 2: COLUMN STRUCTURE --------------------
echo "<h2>2. Detailed Column Structure</h2>" >> "$OUTPUT_FILE"

# Get all tables
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -A -c "
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
ORDER BY table_name;
" | while read -r table; do
    echo "<h3>Table: $table</h3>" >> "$OUTPUT_FILE"
    echo "<table><tr><th>Column</th><th>Data Type</th><th>Nullable</th><th>Default</th></tr>" >> "$OUTPUT_FILE"
    
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -A -F"|" -c "
    SELECT 
        column_name,
        data_type,
        is_nullable,
        COALESCE(column_default, 'N/A')
    FROM information_schema.columns
    WHERE table_name = '$table' AND table_schema = 'public'
    ORDER BY ordinal_position;
    " | while IFS="|" read -r col dtype nullable def; do
        echo "<tr><td>$col</td><td>$dtype</td><td>$nullable</td><td>$def</td></tr>" >> "$OUTPUT_FILE"
    done
    
    echo "</table>" >> "$OUTPUT_FILE"
done

# -------------------- SECTION 3: POPULATION STATISTICS --------------------
echo "<h2>3. Column Population Statistics</h2>" >> "$OUTPUT_FILE"
echo "<p>This shows which columns contain data and their fill rates</p>" >> "$OUTPUT_FILE"

psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -A -c "
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
ORDER BY table_name;
" | while read -r table; do
    # Get row count first
    total_rows=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -A -c "SELECT COUNT(*) FROM public.\"$table\";")
    
    echo "<h3>Table: $table (Total rows: $total_rows)</h3>" >> "$OUTPUT_FILE"
    echo "<table><tr><th>Column</th><th>Populated Rows</th><th>Null Rows</th><th>Fill %</th></tr>" >> "$OUTPUT_FILE"
    
    # Get columns for this table
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -A -c "
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = '$table' AND table_schema = 'public'
    ORDER BY ordinal_position;
    " | while read -r column; do
        # Get population stats for this column
        stats=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -A -F"|" -c "
        SELECT 
            COUNT(\"$column\")::text,
            (COUNT(*) - COUNT(\"$column\"))::text,
            CASE 
                WHEN COUNT(*) = 0 THEN '0'
                ELSE ROUND(100.0 * COUNT(\"$column\") / COUNT(*), 2)::text
            END
        FROM public.\"$table\";
        ")
        
        IFS="|" read -r pop nulls pct <<< "$stats"
        
        # Determine CSS class based on percentage
        if [ "$pct" = "0" ] || [ "$pct" = "0.00" ]; then
            class="empty"
        elif [ "$pct" = "100" ] || [ "$pct" = "100.00" ]; then
            class="populated"
        else
            class="partial"
        fi
        
        echo "<tr><td>$column</td><td>$pop</td><td>$nulls</td><td class='$class'>$pct%</td></tr>" >> "$OUTPUT_FILE"
    done
    
    echo "</table>" >> "$OUTPUT_FILE"
done

# -------------------- CLOSE HTML --------------------
cat >> "$OUTPUT_FILE" << 'HTMLFOOTER'
</body>
</html>
HTMLFOOTER

# Clear password from environment
unset PGPASSWORD

echo ""
echo "✅ Analysis complete!"
echo "📄 Output saved to: $OUTPUT_FILE"
echo "📤 Upload this file to Claude to analyze your database structure."