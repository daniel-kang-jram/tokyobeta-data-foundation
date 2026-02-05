#!/bin/bash
# Check staging tables for activity within the recent 1 year
# For each table with date columns, check if there are records with dates >= 1 year ago

DB_HOST="tokyobeta-prod-aurora-cluster-public.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com"
DB_USER="admin"
DB_PASS="K6ghcWTq4p-zlidRJ2<AJX<w$zN<a8dU"
DB_NAME="tokyobeta"

# Calculate cutoff date (1 year ago)
CUTOFF_DATE=$(date -v-1y +%Y-%m-%d 2>/dev/null || date -d "1 year ago" +%Y-%m-%d)

echo "==================================================================="
echo "Staging Tables Activity Analysis"
echo "==================================================================="
echo "Cutoff Date: $CUTOFF_DATE (1 year ago)"
echo "Analysis Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Create temporary SQL file
TEMP_SQL=$(mktemp)

# Get all staging tables with their date columns
mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" -D "$DB_NAME" -N -e "
SELECT 
    t.TABLE_NAME,
    GROUP_CONCAT(c.COLUMN_NAME ORDER BY c.ORDINAL_POSITION SEPARATOR ',') as date_columns
FROM information_schema.TABLES t
LEFT JOIN information_schema.COLUMNS c 
    ON t.TABLE_SCHEMA = c.TABLE_SCHEMA 
    AND t.TABLE_NAME = c.TABLE_NAME
    AND c.DATA_TYPE IN ('date', 'datetime', 'timestamp')
WHERE t.TABLE_SCHEMA = 'staging'
GROUP BY t.TABLE_NAME
ORDER BY t.TABLE_NAME;
" 2>/dev/null > "$TEMP_SQL"

# Arrays to store results
declare -a ACTIVE_TABLES
declare -a INACTIVE_TABLES

echo "Analyzing $(wc -l < "$TEMP_SQL" | tr -d ' ') staging tables..."
echo ""

# Process each table
while IFS=$'\t' read -r table_name date_columns; do
    if [ "$date_columns" == "NULL" ] || [ -z "$date_columns" ]; then
        # No date columns
        INACTIVE_TABLES+=("$table_name (no date columns)")
        continue
    fi
    
    # Build WHERE clause
    IFS=',' read -ra COLS <<< "$date_columns"
    where_parts=()
    for col in "${COLS[@]}"; do
        where_parts+=("\`$col\` >= '$CUTOFF_DATE'")
    done
    where_clause=$(IFS=' OR '; echo "${where_parts[*]}")
    
    # Check for recent activity
    count=$(mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" -D "$DB_NAME" -N -e "
        SELECT COUNT(*) 
        FROM \`staging\`.\`$table_name\` 
        WHERE $where_clause 
        LIMIT 1;
    " 2>/dev/null)
    
    # Get max date for the table
    max_date_queries=()
    for col in "${COLS[@]}"; do
        max_date_queries+=("MAX(\`$col\`)")
    done
    max_date_query=$(IFS=','; echo "${max_date_queries[*]}")
    
    max_dates=$(mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" -D "$DB_NAME" -N -e "
        SELECT $max_date_query
        FROM \`staging\`.\`$table_name\`;
    " 2>/dev/null)
    
    # Find the latest date
    max_date=""
    IFS=$'\t' read -ra DATES <<< "$max_dates"
    for d in "${DATES[@]}"; do
        if [ -n "$d" ] && [ "$d" != "NULL" ]; then
            if [ -z "$max_date" ] || [[ "$d" > "$max_date" ]]; then
                max_date=$d
            fi
        fi
    done
    
    if [ "$count" -gt 0 ]; then
        ACTIVE_TABLES+=("$table_name|$count|$max_date|$date_columns")
    else
        INACTIVE_TABLES+=("$table_name|$max_date|$date_columns")
    fi
    
done < "$TEMP_SQL"

# Print results
echo "==================================================================="
echo "TABLES WITH ACTIVITY IN RECENT 1 YEAR: ${#ACTIVE_TABLES[@]}"
echo "==================================================================="
echo ""

for entry in "${ACTIVE_TABLES[@]}"; do
    IFS='|' read -r name count max_date cols <<< "$entry"
    echo "✓ $name"
    echo "  - Recent records: $count"
    echo "  - Latest date: $max_date"
    echo "  - Date columns: $cols"
    echo ""
done

echo ""
echo "==================================================================="
echo "TABLES WITHOUT ACTIVITY IN RECENT 1 YEAR: ${#INACTIVE_TABLES[@]}"
echo "==================================================================="
echo ""

for entry in "${INACTIVE_TABLES[@]}"; do
    if [[ "$entry" == *"no date columns"* ]]; then
        name="${entry% (no date columns)}"
        echo "✗ $name"
        echo "  - Reason: No date columns found"
        echo ""
    else
        IFS='|' read -r name max_date cols <<< "$entry"
        echo "✗ $name"
        echo "  - Latest date: ${max_date:-No dates found}"
        if [ -n "$cols" ]; then
            echo "  - Date columns: $cols"
        fi
        echo ""
    fi
done

echo ""
echo "==================================================================="
echo "SUMMARY"
echo "==================================================================="
total_tables=$((${#ACTIVE_TABLES[@]} + ${#INACTIVE_TABLES[@]}))
echo "Total tables analyzed: $total_tables"
echo "Tables with recent activity: ${#ACTIVE_TABLES[@]}"
echo "Tables without recent activity: ${#INACTIVE_TABLES[@]}"
if [ $total_tables -gt 0 ]; then
    percentage=$(awk "BEGIN {printf \"%.1f\", (${#ACTIVE_TABLES[@]} / $total_tables * 100)}")
    echo "Active table percentage: $percentage%"
fi

# Cleanup
rm -f "$TEMP_SQL"
