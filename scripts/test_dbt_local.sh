#!/bin/bash
# Test dbt models against local database
# Run this after setting up local database

set -euo pipefail

cd "$(dirname "$0")/../dbt" || exit 1

export DBT_TARGET=local

echo "Testing dbt models against local database..."
echo "Target: ${DBT_TARGET}"
echo ""

# Check connection
echo "1. Testing database connection..."
if ! dbt debug --target local > /dev/null 2>&1; then
    echo "❌ Database connection failed"
    echo ""
    echo "Please ensure:"
    echo "  1. Local database is running (see docs/LOCAL_SETUP_GUIDE.md)"
    echo "  2. Connection details in dbt/profiles.yml are correct"
    echo ""
    exit 1
fi

echo "✅ Database connection successful"
echo ""

# Run dbt models
echo "2. Running dbt models..."
if dbt run --target local; then
    echo ""
    echo "✅ dbt models executed successfully"
else
    echo ""
    echo "❌ dbt models failed"
    exit 1
fi

echo ""

# Run tests
echo "3. Running dbt tests..."
if dbt test --target local; then
    echo ""
    echo "✅ dbt tests passed"
else
    echo ""
    echo "⚠️  Some dbt tests failed (check output above)"
fi

echo ""

# Validate outputs
echo "4. Validating output tables..."
echo ""

DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3307}"
DB_USER="${DB_USER:-root}"
DB_PASSWORD="${DB_PASSWORD:-localdev}"
DB_NAME="${DB_NAME:-tokyobeta}"

check_table() {
    local table=$1
    local count=$(mysql -h${DB_HOST} -P${DB_PORT} -u${DB_USER} -p${DB_PASSWORD} ${DB_NAME} -sN -e "SELECT COUNT(*) FROM analytics.${table}" 2>/dev/null || echo "0")
    
    if [ "$count" != "0" ]; then
        echo "  ✅ ${table}: ${count} rows"
        return 0
    else
        echo "  ⚠️  ${table}: 0 rows (table may be empty or not created)"
        return 1
    fi
}

check_table "daily_activity_summary"
check_table "new_contracts"
check_table "moveouts"
check_table "moveout_notices"

echo ""
echo "✅ Validation complete!"
echo ""
echo "To inspect data:"
echo "  mysql -h ${DB_HOST} -P ${DB_PORT} -u ${DB_USER} -p${DB_PASSWORD} ${DB_NAME}"
echo ""
echo "Sample queries:"
echo "  SELECT * FROM analytics.daily_activity_summary LIMIT 10;"
echo "  SELECT * FROM analytics.new_contracts LIMIT 10;"
echo "  SELECT * FROM analytics.moveouts LIMIT 10;"
echo "  SELECT * FROM analytics.moveout_notices LIMIT 10;"
