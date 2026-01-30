#!/bin/bash
# Initialize Aurora database schemas for Tokyo Beta Data Consolidation

set -e

# Get Aurora credentials from Secrets Manager
SECRET_JSON=$(aws secretsmanager get-secret-value \
    --secret-id arn:aws:secretsmanager:ap-northeast-1:343881458651:secret:tokyobeta/prod/aurora/credentials-tlWiUd \
    --query SecretString \
    --output text \
    --profile gghouse \
    --region ap-northeast-1)

DB_USER=$(echo $SECRET_JSON | jq -r '.username')
DB_PASS=$(echo $SECRET_JSON | jq -r '.password')
DB_HOST="tokyobeta-prod-aurora-cluster.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com"
DB_NAME="tokyobeta"

echo "Creating staging and analytics schemas in Aurora..."

mysql -h $DB_HOST -u $DB_USER -p$DB_PASS $DB_NAME << 'EOF'
-- Create staging schema
CREATE SCHEMA IF NOT EXISTS staging;

-- Create analytics schema
CREATE SCHEMA IF NOT EXISTS analytics;

-- Create seeds schema for reference data
CREATE SCHEMA IF NOT EXISTS seeds;

-- Verify schemas
SHOW SCHEMAS;

SELECT 'Schemas created successfully!' as status;
EOF

echo "✅ Database schemas initialized successfully"
echo "   - staging: For raw SQL dump data"
echo "   - analytics: For dbt-transformed tables"
echo "   - seeds: For geocoding and reference data"
