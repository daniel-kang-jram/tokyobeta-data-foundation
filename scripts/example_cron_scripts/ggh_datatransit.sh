#!/usr/bin/env bash
# Example: Full mysqldump with Secrets Manager integration
# Schedule: 30 5 * * * (5:30 AM daily)

set -euo pipefail

# Configuration
AWS_REGION="ap-northeast-1"
SECRET_NAME="tokyobeta/prod/rds/cron-credentials"
S3_BUCKET="jram-gghouse"
S3_PREFIXES_CONFIG="${S3_PREFIXES_CSV:-dumps,dumps-managed}"
IFS=',' read -r -a S3_PREFIXES <<< "${S3_PREFIXES_CONFIG}"
S3_PREFIX_PRIMARY="dumps"
TIMESTAMP=$(date +%Y%m%d)
RUN_TS=$(date -Iseconds)
WORK_DIR="/tmp/mysql_dumps/gghouse_${TIMESTAMP}_$$"
LOG_FILE="/var/log/ggh_datatransit.log"
LOCK_FILE="/tmp/ggh_datatransit.lock"

RUN_ID="${TIMESTAMP}-$$"
MIN_DUMP_BYTES=52428800
MAX_RETRIES=3
RETRY_BASE_SECONDS=10
SNS_TOPIC_ARN="${SNS_TOPIC_ARN:-}"

# Logging and notifications
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

notify_failure() {
    local message="$1"

    if [[ -n "${SNS_TOPIC_ARN}" ]]; then
        aws sns publish \
            --region "$AWS_REGION" \
            --topic-arn "$SNS_TOPIC_ARN" \
            --subject "Dump failure for ${TIMESTAMP}" \
            --message "$message" >/dev/null
    fi
}

fail() {
    local message="$1"
    log "ERROR: ${message}"
    notify_failure "[tokyobeta-dump] ${message}\nRun ID: ${RUN_ID}\nTimestamp: ${RUN_TS}\nLog: ${LOG_FILE}"
    exit 1
}

require_command() {
    local binary="$1"
    if ! command -v "$binary" >/dev/null 2>&1; then
        fail "Required command not found: ${binary}"
    fi
}

run_with_retries() {
    local attempt=1
    local command_text="$1"

    while (( attempt <= MAX_RETRIES )); do
        log "Attempt ${attempt}/${MAX_RETRIES}: ${command_text}"
        if eval "$command_text"; then
            return 0
        fi

        if (( attempt >= MAX_RETRIES )); then
            return 1
        fi

        local delay=$(( RETRY_BASE_SECONDS * attempt ))
        log "Command failed, retrying in ${delay}s: ${command_text}"
        sleep "$delay"
        attempt=$((attempt + 1))
    done
}

cleanup() {
    log "Cleaning up local temp files"
    rm -rf "$WORK_DIR"
}

trap cleanup EXIT

for cmd in aws jq mysqldump gzip numfmt sha256sum flock stat; do
    require_command "$cmd"
done

# Serialize runs in case cron overlaps
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    fail "Another dump process is already running. Refusing to run concurrently."
fi

log "Starting dump run id=${RUN_ID}"

mkdir -p "$WORK_DIR"

log "Fetching credentials from Secrets Manager (${SECRET_NAME})"
if ! SECRET_JSON=$(aws secretsmanager get-secret-value \
    --secret-id "$SECRET_NAME" \
    --region "$AWS_REGION" \
    --query SecretString \
    --output text 2>/tmp/secret_fetch_error.log); then
    fail "Failed to fetch credentials from Secrets Manager: $(cat /tmp/secret_fetch_error.log)"
fi

DB_HOST=$(echo "$SECRET_JSON" | jq -r '.host')
DB_USER=$(echo "$SECRET_JSON" | jq -r '.username')
DB_PASS=$(echo "$SECRET_JSON" | jq -r '.password')
DB_NAME=$(echo "$SECRET_JSON" | jq -r '.database')
DB_PORT=$(echo "$SECRET_JSON" | jq -r '.port')

if [[ -z "$DB_HOST" || -z "$DB_USER" || -z "$DB_PASS" ]]; then
    fail "Invalid credentials returned from Secrets Manager"
fi

# Step 1: Generate and compress dump
DUMP_FILE="${WORK_DIR}/gghouse_${TIMESTAMP}.sql"
COMPRESSED_FILE="${DUMP_FILE}.gz"
log "Creating database dump: ${DUMP_FILE}"

if ! run_with_retries "mysqldump" \
    "mysqldump \
        --host='${DB_HOST}' \
        --port='${DB_PORT}' \
        --user='${DB_USER}' \
        --password='${DB_PASS}' \
        --single-transaction \
        --quick \
        --lock-tables=false \
        --routines \
        --triggers \
        --events \
        ${DB_NAME} > ${DUMP_FILE}"; then
    fail "mysqldump failed after ${MAX_RETRIES} attempts"
fi

DUMP_SIZE_BYTES=$(stat -c%s "$DUMP_FILE")
if (( DUMP_SIZE_BYTES < MIN_DUMP_BYTES )); then
    fail "Dump too small (${DUMP_SIZE_BYTES} bytes)."
fi

log "Dump created: $(numfmt --to=iec ${DUMP_SIZE_BYTES})"

log "Compressing dump..."
if ! gzip -c "$DUMP_FILE" > "$COMPRESSED_FILE"; then
    fail "Compression failed"
fi

if ! COMPRESSED_SIZE_BYTES=$(stat -c%s "$COMPRESSED_FILE"); then
    fail "Failed to stat compressed dump"
fi
log "Compression complete: $(numfmt --to=iec ${COMPRESSED_SIZE_BYTES})"

DUMP_SHA256=$(sha256sum "$COMPRESSED_FILE" | cut -d' ' -f1)

# Step 2: upload to every configured channel, with strict verification
UPLOAD_OK=1
UPLOAD_REPORT="${WORK_DIR}/gghouse_${TIMESTAMP}_upload_report.json"
printf '{"run_id":"%s","timestamp":"%s","dump_file":"gghouse_%s.sql.gz","sha256":"%s","channels":[' \
    "$RUN_ID" "$RUN_TS" "$TIMESTAMP" "$DUMP_SHA256" > "$UPLOAD_REPORT"
FIRST_CHANNEL=1

for PREFIX in "${S3_PREFIXES[@]}"; do
    CLEAN_PREFIX="${PREFIX%/}"
    DEST_KEY="${CLEAN_PREFIX}/gghouse_${TIMESTAMP}.sql.gz"
    DEST_URI="s3://${S3_BUCKET}/${DEST_KEY}"

    if ! run_with_retries "S3 upload ${DEST_URI}" \
        "aws s3 cp \"${COMPRESSED_FILE}\" \"${DEST_URI}\" \
            --region ${AWS_REGION} \
            --storage-class STANDARD_IA \
            --metadata created=${RUN_TS},host=${DB_HOST},database=${DB_NAME},run_id=${RUN_ID}"; then
        UPLOAD_OK=0
        log "Upload failed for ${DEST_URI}"
        if [[ $FIRST_CHANNEL -eq 1 ]]; then
            printf '{"prefix":"%s","status":"upload_failed","error":"upload_failed"}' \
                "$CLEAN_PREFIX" >> "$UPLOAD_REPORT"
            FIRST_CHANNEL=0
        else
            printf ',{"prefix":"%s","status":"upload_failed","error":"upload_failed"}' \
                "$CLEAN_PREFIX" >> "$UPLOAD_REPORT"
        fi
        continue
    fi

    if ! UPLOAD_SIZE=$(aws s3api head-object --bucket "$S3_BUCKET" --key "$DEST_KEY" --region "$AWS_REGION" --query 'ContentLength' --output text 2>/tmp/s3_head_error.log); then
        UPLOAD_OK=0
        log "S3 HEAD failed for ${DEST_URI}: $(cat /tmp/s3_head_error.log)"
        if [[ $FIRST_CHANNEL -eq 1 ]]; then
            printf '{"prefix":"%s","status":"head_failed","error":"head_failed"}' \
                "$CLEAN_PREFIX" >> "$UPLOAD_REPORT"
            FIRST_CHANNEL=0
        else
            printf ',{"prefix":"%s","status":"head_failed","error":"head_failed"}' \
                "$CLEAN_PREFIX" >> "$UPLOAD_REPORT"
        fi
        continue
    fi

    if (( UPLOAD_SIZE < MIN_DUMP_BYTES )); then
        UPLOAD_OK=0
        if [[ $FIRST_CHANNEL -eq 1 ]]; then
            printf '{"prefix":"%s","status":"size_too_small","size":%s}' \
                "$CLEAN_PREFIX" "$UPLOAD_SIZE" >> "$UPLOAD_REPORT"
            FIRST_CHANNEL=0
        else
            printf ',{"prefix":"%s","status":"size_too_small","size":%s}' \
                "$CLEAN_PREFIX" "$UPLOAD_SIZE" >> "$UPLOAD_REPORT"
        fi
        continue
    fi

    if [[ $FIRST_CHANNEL -eq 1 ]]; then
        printf '{"prefix":"%s","status":"ok","size":%s,"s3_key":"%s","run_id":"%s"}' \
            "$CLEAN_PREFIX" "$UPLOAD_SIZE" "$DEST_KEY" "$RUN_ID" >> "$UPLOAD_REPORT"
        FIRST_CHANNEL=0
    else
        printf ',{"prefix":"%s","status":"ok","size":%s,"s3_key":"%s","run_id":"%s"}' \
            "$CLEAN_PREFIX" "$UPLOAD_SIZE" "$DEST_KEY" "$RUN_ID" >> "$UPLOAD_REPORT"
    fi
done

printf ']}' >> "$UPLOAD_REPORT"
aws s3 cp "$UPLOAD_REPORT" "s3://${S3_BUCKET}/${S3_PREFIX_PRIMARY}/_run_reports/gghouse_${TIMESTAMP}_upload_report.json" \
    --region "$AWS_REGION" >/dev/null

if [[ $UPLOAD_OK -ne 1 ]]; then
    fail "One or more S3 uploads failed or are invalid."
fi

log "All S3 uploads verified"

# Step 3: continuity check for last 3 days in both channels
MISSING_DUMPS=0
for LOOKBACK in 0 1 2; do
    CHECK_TS=$(date -d "${LOOKBACK} days ago" +%Y%m%d)
    for PREFIX in "${S3_PREFIXES[@]}"; do
        CLEAN_PREFIX="${PREFIX%/}"
        CONTINUITY_KEY="${CLEAN_PREFIX}/gghouse_${CHECK_TS}.sql.gz"
        if ! aws s3api head-object --bucket "$S3_BUCKET" --key "$CONTINUITY_KEY" --region "$AWS_REGION" >/dev/null 2>&1; then
            MISSING_DUMPS=$((MISSING_DUMPS + 1))
            log "Continuity warning: missing ${CONTINUITY_KEY}"
        fi
    done
done

if (( MISSING_DUMPS > 0 )); then
    notify_failure "Continuity issue in dump pipeline. Missing ${MISSING_DUMPS} expected dump copies for ${TIMESTAMP} and prior 2 days. Run ID: ${RUN_ID}."
fi

log "Dump run complete"

# Clear sensitive variables
unset DB_HOST DB_USER DB_PASS DB_NAME DB_PORT SECRET_JSON
