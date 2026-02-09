#!/bin/bash
# Quick database check for active tenant count
# Usage: ./quick_db_check.sh

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=============================================================================="
echo "  Quick Database Check - Active Tenant Count"
echo "=============================================================================="
echo ""

# Get Aurora endpoint from terraform
cd terraform/environments/prod
AURORA_ENDPOINT=$(terraform output -raw aurora_cluster_endpoint 2>/dev/null || echo "")

if [ -z "$AURORA_ENDPOINT" ]; then
    echo "❌ Could not get Aurora endpoint from terraform"
    echo "   Please set AURORA_ENDPOINT manually:"
    echo "   export AURORA_ENDPOINT='your-endpoint.rds.amazonaws.com'"
    exit 1
fi

echo "📡 Aurora Endpoint: $AURORA_ENDPOINT"
echo ""

# Get credentials from AWS Secrets Manager
echo "🔐 Retrieving credentials from Secrets Manager..."
SECRET_JSON=$(aws secretsmanager get-secret-value \
    --secret-id tokyobeta/prod/aurora/credentials \
    --profile gghouse \
    --query SecretString \
    --output text)

DB_USER=$(echo $SECRET_JSON | python3 -c "import sys, json; print(json.load(sys.stdin)['username'])")
DB_PASS=$(echo $SECRET_JSON | python3 -c "import sys, json; print(json.load(sys.stdin)['password'])")

echo "✓ Credentials retrieved"
echo ""

# Check if we can connect
echo "🔌 Testing database connection..."
echo ""

# Query 1: Active tenant count from staging.tenants
echo "${BLUE}Query 1: Active Tenants (from staging.tenants)${NC}"
mysql -h $AURORA_ENDPOINT -u $DB_USER -p$DB_PASS tokyobeta \
    -e "SELECT COUNT(DISTINCT t.id) as active_tenant_count 
        FROM staging.tenants t 
        INNER JOIN silver.code_tenant_status s ON t.status = s.code 
        WHERE s.is_active_lease = 1;" \
    2>/dev/null || {
        echo "❌ Cannot connect to database directly"
        echo ""
        echo "💡 The database is likely in a private subnet."
        echo "   Options to connect:"
        echo "   1. Use AWS Systems Manager Session Manager"
        echo "   2. Connect via bastion host/EC2 instance"
        echo "   3. Use dbt run with proper tunnel"
        echo ""
        exit 1
    }

echo ""

# Query 2: Breakdown by contract type
echo "${BLUE}Query 2: Active Tenants by Contract Type${NC}"
mysql -h $AURORA_ENDPOINT -u $DB_USER -p$DB_PASS tokyobeta \
    -e "SELECT 
            CASE 
                WHEN t.contract_type IN (2, 3) THEN 'corporate'
                WHEN t.contract_type IN (1, 6, 7, 9) THEN 'individual'
                ELSE 'unknown'
            END as tenant_type,
            COUNT(*) as count
        FROM staging.tenants t
        INNER JOIN silver.code_tenant_status s ON t.status = s.code
        WHERE s.is_active_lease = 1
        GROUP BY tenant_type;" \
    2>/dev/null

echo ""

# Query 3: Top 5 tenant statuses
echo "${BLUE}Query 3: Tenant Count by Status (Top 5)${NC}"
mysql -h $AURORA_ENDPOINT -u $DB_USER -p$DB_PASS tokyobeta \
    -e "SELECT 
            t.status,
            s.label_ja,
            s.is_active_lease,
            COUNT(*) as count
        FROM staging.tenants t
        LEFT JOIN silver.code_tenant_status s ON t.status = s.code
        GROUP BY t.status, s.label_ja, s.is_active_lease
        ORDER BY count DESC
        LIMIT 5;" \
    2>/dev/null

echo ""
echo "=============================================================================="
echo "${GREEN}✓ Database check complete${NC}"
echo "=============================================================================="
echo ""
echo "${YELLOW}Compare with Rent Roll:${NC}"
echo "  Rent Roll (Oct 2025): 1,076 active tenants"
echo "  Gold Table (Current): [see results above]"
echo ""
