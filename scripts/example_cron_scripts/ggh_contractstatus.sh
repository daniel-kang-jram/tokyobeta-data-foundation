#!/bin/bash
# Example: Contract status query with Secrets Manager integration
# Schedule: 1 6 * * * (6:01 AM daily)

set -euo pipefail

# Configuration
AWS_REGION="ap-northeast-1"
SECRET_NAME="tokyobeta/prod/rds/cron-credentials"
S3_BUCKET="jram-gghouse"
S3_PREFIX="contractstatus"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
TEMP_DIR="/tmp/mysql_queries"
LOG_FILE="/var/log/ggh_contractstatus.log"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "Starting contract status query"

# Fetch credentials from AWS Secrets Manager
log "Fetching credentials from Secrets Manager..."
SECRET_JSON=$(aws secretsmanager get-secret-value \
    --secret-id "$SECRET_NAME" \
    --region "$AWS_REGION" \
    --query SecretString \
    --output text)

# Parse JSON credentials
DB_HOST=$(echo "$SECRET_JSON" | jq -r '.host')
DB_USER=$(echo "$SECRET_JSON" | jq -r '.username')
DB_PASS=$(echo "$SECRET_JSON" | jq -r '.password')
DB_NAME=$(echo "$SECRET_JSON" | jq -r '.database')
DB_PORT=$(echo "$SECRET_JSON" | jq -r '.port')

# Validate credentials
if [[ -z "$DB_HOST" || -z "$DB_USER" || -z "$DB_PASS" ]]; then
    log "ERROR: Failed to fetch database credentials"
    exit 1
fi

log "Credentials retrieved successfully"

# Create temp directory
mkdir -p "$TEMP_DIR"

# SQL Query for contract status
QUERY_FILE="${TEMP_DIR}/contract_status_query.sql"
cat > "$QUERY_FILE" << 'EOF'
SELECT 
    c.contract_id,
    c.contract_date,
    c.contract_status,
    c.tenant_type,
    t.tenant_name,
    t.tenant_age,
    t.tenant_nationality,
    a.apartment_name,
    a.room_number,
    c.rent_amount,
    c.move_in_date,
    c.contract_start_date,
    c.contract_end_date
FROM contracts c
LEFT JOIN tenants t ON c.tenant_id = t.tenant_id
LEFT JOIN apartments a ON c.apartment_id = a.apartment_id
WHERE c.contract_status IN ('active', 'pending', 'approved')
  AND c.contract_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
ORDER BY c.contract_date DESC;
EOF

# Execute query
OUTPUT_FILE="${TEMP_DIR}/contractstatus_${TIMESTAMP}.csv"
log "Executing contract status query..."

mysql \
    --host="$DB_HOST" \
    --port="$DB_PORT" \
    --user="$DB_USER" \
    --password="$DB_PASS" \
    --database="$DB_NAME" \
    --batch \
    --skip-column-names \
    < "$QUERY_FILE" \
    | sed 's/\t/,/g' > "$OUTPUT_FILE"

if [[ $? -eq 0 ]]; then
    ROW_COUNT=$(wc -l < "$OUTPUT_FILE")
    log "Query executed successfully: $ROW_COUNT rows"
else
    log "ERROR: Query execution failed"
    exit 1
fi

# Upload to S3
S3_PATH="s3://${S3_BUCKET}/${S3_PREFIX}/contractstatus_${TIMESTAMP}.csv"
log "Uploading to S3: $S3_PATH"

aws s3 cp "$OUTPUT_FILE" "$S3_PATH" \
    --region "$AWS_REGION" \
    --storage-class STANDARD_IA

if [[ $? -eq 0 ]]; then
    log "Upload successful"
else
    log "ERROR: S3 upload failed"
    exit 1
fi

# Cleanup
log "Cleaning up temp files"
rm -f "$OUTPUT_FILE" "$QUERY_FILE"

log "Contract status query complete"

# Clear sensitive variables
unset DB_HOST DB_USER DB_PASS DB_NAME DB_PORT SECRET_JSON

exit 0
