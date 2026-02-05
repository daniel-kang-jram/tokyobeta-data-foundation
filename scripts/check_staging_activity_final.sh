#!/bin/bash
# Check staging tables for activity within the recent 1 year

set -e

DB_HOST="tokyobeta-prod-aurora-cluster-public.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com"
DB_USER="admin"
DB_PASS="K6ghcWTq4p-zlidRJ2<AJX<w$zN<a8dU"
DB_NAME="tokyobeta"

# Calculate cutoff date (1 year ago)
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    CUTOFF_DATE=$(date -v-1y +%Y-%m-%d)
else
    # Linux
    CUTOFF_DATE=$(date -d "1 year ago" +%Y-%m-%d)
fi

echo "==================================================================="
echo "Staging Tables Activity Analysis"
echo "==================================================================="
echo "Cutoff Date: $CUTOFF_DATE (1 year ago)"
echo "Analysis Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# MySQL connection function
run_mysql() {
    mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" -D "$DB_NAME" -N "$@" 2>&1 | grep -v "Using a password"
}

# Get all staging tables with their date columns
echo "Fetching staging table information..."
TABLE_LIST=$(run_mysql -e "
SELECT 
    t.TABLE_NAME,
    COALESCE(GROUP_CONCAT(c.COLUMN_NAME ORDER BY c.ORDINAL_POSITION SEPARATOR ','), 'NO_DATE_COLS') as date_columns
FROM information_schema.TABLES t
LEFT JOIN information_schema.COLUMNS c 
    ON t.TABLE_SCHEMA = c.TABLE_SCHEMA 
    AND t.TABLE_NAME = c.TABLE_NAME
    AND c.DATA_TYPE IN ('date', 'datetime', 'timestamp')
WHERE t.TABLE_SCHEMA = 'staging'
GROUP BY t.TABLE_NAME
ORDER BY t.TABLE_NAME;
")

# Count total tables
TOTAL_TABLES=$(echo "$TABLE_LIST" | wc -l | tr -d ' ')
echo "Found $TOTAL_TABLES staging tables"
echo ""

# Arrays to store results
ACTIVE_TABLES=()
INACTIVE_TABLES=()

# Process each table
COUNTER=0
while IFS=$'\t' read -r table_name date_columns; do
    COUNTER=$((COUNTER + 1))
    echo -ne "Processing table $COUNTER/$TOTAL_TABLES: $table_name\r"
    
    if [ "$date_columns" == "NO_DATE_COLS" ] || [ -z "$date_columns" ]; then
        # No date columns
        INACTIVE_TABLES+=("$table_name|NO_DATE|NO_DATE_COLS")
        continue
    fi
    
    # Build WHERE clause for checking recent activity
    IFS=',' read -ra COLS <<< "$date_columns"
    where_parts=()
    for col in "${COLS[@]}"; do
        where_parts+=("\`$col\` >= '$CUTOFF_DATE'")
    done
    where_clause=$(IFS=' OR '; echo "${where_parts[*]}")
    
    # Check for recent activity and get count
    count_result=$(run_mysql -e "
        SELECT 
            COUNT(*) as recent_count,
            (SELECT COUNT(*) FROM \`staging\`.\`$table_name\`) as total_count
        FROM \`staging\`.\`$table_name\` 
        WHERE $where_clause;
    ")
    
    recent_count=$(echo "$count_result" | awk '{print $1}')
    total_count=$(echo "$count_result" | awk '{print $2}')
    
    # Get max date for the table
    max_date_queries=()
    for col in "${COLS[@]}"; do
        max_date_queries+=("MAX(\`$col\`)")
    done
    max_date_query=$(IFS=','; echo "${max_date_queries[*]}")
    
    max_dates=$(run_mysql -e "
        SELECT $max_date_query
        FROM \`staging\`.\`$table_name\`;
    ")
    
    # Find the latest date
    max_date="NO_DATE"
    IFS=$'\t' read -ra DATES <<< "$max_dates"
    for d in "${DATES[@]}"; do
        if [ -n "$d" ] && [ "$d" != "NULL" ]; then
            if [ "$max_date" == "NO_DATE" ] || [[ "$d" > "$max_date" ]]; then
                max_date=$d
            fi
        fi
    done
    
    if [ "$recent_count" -gt 0 ] 2>/dev/null; then
        ACTIVE_TABLES+=("$table_name|$recent_count|$total_count|$max_date|$date_columns")
    else
        INACTIVE_TABLES+=("$table_name|$total_count|$max_date|$date_columns")
    fi
    
done <<< "$TABLE_LIST"

echo "" # Clear the progress line
echo ""

# Print results
echo "==================================================================="
echo "TABLES WITH ACTIVITY IN RECENT 1 YEAR: ${#ACTIVE_TABLES[@]}"
echo "==================================================================="
echo ""

if [ ${#ACTIVE_TABLES[@]} -gt 0 ]; then
    for entry in "${ACTIVE_TABLES[@]}"; do
        IFS='|' read -r name recent_count total_count max_date cols <<< "$entry"
        echo "✓ $name"
        echo "  - Recent records (since $CUTOFF_DATE): $recent_count"
        echo "  - Total records: $total_count"
        echo "  - Latest date: $max_date"
        echo "  - Date columns: $cols"
        echo ""
    done
else
    echo "No tables found with recent activity."
    echo ""
fi

echo "==================================================================="
echo "TABLES WITHOUT ACTIVITY IN RECENT 1 YEAR: ${#INACTIVE_TABLES[@]}"
echo "==================================================================="
echo ""

if [ ${#INACTIVE_TABLES[@]} -gt 0 ]; then
    for entry in "${INACTIVE_TABLES[@]}"; do
        IFS='|' read -r name total_count max_date cols <<< "$entry"
        if [ "$cols" == "NO_DATE_COLS" ]; then
            echo "✗ $name"
            echo "  - Reason: No date columns found"
            echo "  - Total records: $total_count"
            echo ""
        else
            echo "✗ $name"
            echo "  - Total records: $total_count"
            echo "  - Latest date: $max_date"
            echo "  - Date columns: $cols"
            echo ""
        fi
    done
else
    echo "All tables have recent activity."
    echo ""
fi

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
echo ""

# Save active tables list to a file
OUTPUT_FILE="/Users/danielkang/tokyobeta-data-consolidation/docs/STAGING_ACTIVE_TABLES_$(date +%Y%m%d).md"
echo "# Staging Tables with Recent Activity (Last 1 Year)" > "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
echo "**Analysis Date:** $(date '+%Y-%m-%d %H:%M:%S')" >> "$OUTPUT_FILE"
echo "**Cutoff Date:** $CUTOFF_DATE" >> "$OUTPUT_FILE"
echo "**Total Active Tables:** ${#ACTIVE_TABLES[@]} out of $total_tables" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
echo "## Tables with Activity" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

if [ ${#ACTIVE_TABLES[@]} -gt 0 ]; then
    echo "| Table Name | Recent Records | Total Records | Latest Date | Date Columns |" >> "$OUTPUT_FILE"
    echo "|------------|----------------|---------------|-------------|--------------|" >> "$OUTPUT_FILE"
    for entry in "${ACTIVE_TABLES[@]}"; do
        IFS='|' read -r name recent_count total_count max_date cols <<< "$entry"
        echo "| $name | $recent_count | $total_count | $max_date | $cols |" >> "$OUTPUT_FILE"
    done
else
    echo "No tables found with recent activity." >> "$OUTPUT_FILE"
fi

echo "" >> "$OUTPUT_FILE"
echo "## Summary" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
echo "- **Total tables analyzed:** $total_tables" >> "$OUTPUT_FILE"
echo "- **Tables with recent activity:** ${#ACTIVE_TABLES[@]}" >> "$OUTPUT_FILE"
echo "- **Tables without recent activity:** ${#INACTIVE_TABLES[@]}" >> "$OUTPUT_FILE"
if [ $total_tables -gt 0 ]; then
    echo "- **Active table percentage:** $percentage%" >> "$OUTPUT_FILE"
fi

echo "Results saved to: $OUTPUT_FILE"
