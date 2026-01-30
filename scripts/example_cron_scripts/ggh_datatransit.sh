#!/bin/bash
# Example: Full mysqldump with Secrets Manager integration
# Replaces hardcoded credentials with AWS Secrets Manager
# Schedule: 30 5 * * * (5:30 AM daily)

set -euo pipefail

# Configuration
AWS_REGION="ap-northeast-1"
SECRET_NAME="tokyobeta/prod/rds/cron-credentials"
S3_BUCKET="jram-gghouse"
S3_PREFIX="dumps"
TIMESTAMP=$(date +%Y%m%d)
TEMP_DIR="/tmp/mysql_dumps"
LOG_FILE="/var/log/ggh_datatransit.log"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "Starting full database dump"

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

# Validate credentials were fetched
if [[ -z "$DB_HOST" || -z "$DB_USER" || -z "$DB_PASS" ]]; then
    log "ERROR: Failed to fetch database credentials from Secrets Manager"
    exit 1
fi

log "Credentials retrieved successfully"

# Create temp directory
mkdir -p "$TEMP_DIR"

# Perform mysqldump
DUMP_FILE="${TEMP_DIR}/gghouse_${TIMESTAMP}.sql"
log "Creating database dump: $DUMP_FILE"

mysqldump \
    --host="$DB_HOST" \
    --port="$DB_PORT" \
    --user="$DB_USER" \
    --password="$DB_PASS" \
    --single-transaction \
    --quick \
    --lock-tables=false \
    --routines \
    --triggers \
    --events \
    "$DB_NAME" > "$DUMP_FILE"

if [[ $? -eq 0 ]]; then
    DUMP_SIZE=$(du -h "$DUMP_FILE" | cut -f1)
    log "Dump created successfully: $DUMP_SIZE"
else
    log "ERROR: mysqldump failed"
    exit 1
fi

# Compress dump
log "Compressing dump file..."
gzip "$DUMP_FILE"
COMPRESSED_FILE="${DUMP_FILE}.gz"

if [[ -f "$COMPRESSED_FILE" ]]; then
    COMPRESSED_SIZE=$(du -h "$COMPRESSED_FILE" | cut -f1)
    log "Compression complete: $COMPRESSED_SIZE"
else
    log "ERROR: Compression failed"
    exit 1
fi

# Upload to S3
S3_PATH="s3://${S3_BUCKET}/${S3_PREFIX}/gghouse_${TIMESTAMP}.sql.gz"
log "Uploading to S3: $S3_PATH"

aws s3 cp "$COMPRESSED_FILE" "$S3_PATH" \
    --region "$AWS_REGION" \
    --storage-class STANDARD_IA \
    --metadata "created=$(date -Iseconds),host=$DB_HOST,database=$DB_NAME"

if [[ $? -eq 0 ]]; then
    log "Upload successful"
else
    log "ERROR: S3 upload failed"
    exit 1
fi

# Cleanup
log "Cleaning up temp files"
rm -f "$COMPRESSED_FILE"

# Verify S3 upload
S3_SIZE=$(aws s3 ls "$S3_PATH" --region "$AWS_REGION" | awk '{print $3}')
log "Verified S3 file size: $S3_SIZE bytes"

log "Database dump complete"

# Clear sensitive variables
unset DB_HOST DB_USER DB_PASS DB_NAME DB_PORT SECRET_JSON

exit 0
