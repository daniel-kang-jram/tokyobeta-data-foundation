#!/usr/bin/env bash
# Production dump script example.
# Schedule: 30 5 * * *

set -Eeuo pipefail

AWS_REGION="${AWS_REGION:-ap-northeast-1}"
SECRET_NAME="${SECRET_NAME:-tokyobeta/prod/rds/cron-credentials}"
SNS_TOPIC_ARN="${SNS_TOPIC_ARN:-}"
S3_BUCKET="${S3_BUCKET:-jram-gghouse}"
S3_DUMP_PREFIX="${S3_DUMP_PREFIX:-dumps}"
S3_MANIFEST_PREFIX="${S3_MANIFEST_PREFIX:-dumps-manifest}"
TIMESTAMP="${TIMESTAMP_OVERRIDE:-$(date +%Y%m%d)}"
RUN_ID="${TIMESTAMP}-$$"
RUN_TS="$(date -Iseconds)"
WORK_DIR_BASE="${WORK_DIR_BASE:-/tmp/mysql_dumps}"
WORK_DIR="${WORK_DIR_BASE}/gghouse_${TIMESTAMP}_$$"
SECRET_FETCH_ERR_FILE="/tmp/ggh_secret_fetch_error_${RUN_ID}.log"
S3_HEAD_ERR_FILE="/tmp/ggh_head_error_${RUN_ID}.log"
LOG_FILE="${LOG_FILE_PATH:-/var/log/ggh_datatransit.log}"
LOCK_FILE="${LOCK_FILE_PATH:-/tmp/ggh_datatransit.lock}"
MIN_DUMP_BYTES="${MIN_DUMP_BYTES:-10485760}"
MAX_RETRIES="${MAX_RETRIES:-3}"
RETRY_BASE_SECONDS="${RETRY_BASE_SECONDS:-10}"
MYSQL_CONNECT_TIMEOUT="${MYSQL_CONNECT_TIMEOUT:-8}"
REQUIRED_TABLES_CSV="${REQUIRED_TABLES_CSV:-movings,tenants,rooms,inquiries,apartments}"
FORBIDDEN_HOST_REGEX="${FORBIDDEN_HOST_REGEX:-(^localhost$|^127\\.0\\.0\\.1$|^invalid\\.host\\.example$|^tokyobeta-prod-aurora.*)}"
FORBIDDEN_DB_REGEX="${FORBIDDEN_DB_REGEX:-(^mysql$|^information_schema$|^performance_schema$|^sys$)}"
ALERT_SENT=0

# Force EC2 instance-role credentials.
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_PROFILE AWS_DEFAULT_PROFILE
export AWS_SHARED_CREDENTIALS_FILE=/dev/null
export AWS_CONFIG_FILE=/dev/null
export AWS_EC2_METADATA_DISABLED=false

log() {
  printf '[%s] [%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$RUN_ID" "$*" | tee -a "$LOG_FILE"
}

build_alert_message() {
  local reason="$1"
  printf '[tokyobeta-dump] %s\nRun ID: %s\nTimestamp: %s\nLog: %s\n' \
    "$reason" "$RUN_ID" "$RUN_TS" "$LOG_FILE"
}

notify_failure() {
  local reason="$1"
  local payload

  if [[ -z "$SNS_TOPIC_ARN" ]]; then
    return 1
  fi

  payload="$(build_alert_message "$reason")"
  aws sns publish \
    --region "$AWS_REGION" \
    --topic-arn "$SNS_TOPIC_ARN" \
    --subject "Dump failure for ${TIMESTAMP}" \
    --message "$payload" >/dev/null

  ALERT_SENT=1
}

fail() {
  local reason="$1"
  trap - ERR
  log "ERROR: ${reason}"
  if ! notify_failure "$reason"; then
    log "ERROR: Failed to publish SNS failure alert"
  fi
  exit 1
}

cleanup() {
  rm -f "$SECRET_FETCH_ERR_FILE" "$S3_HEAD_ERR_FILE"
  rm -rf "$WORK_DIR"
}

on_exit() {
  local exit_code=$?
  if (( exit_code != 0 )) && (( ALERT_SENT == 0 )); then
    notify_failure "Dump run failed with exit code ${exit_code}" || true
  fi
  cleanup
  exit "$exit_code"
}

trap on_exit EXIT
trap 'fail "Unhandled error at line ${LINENO}"' ERR

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "Required command not found: $1"
  fi
}

run_with_retries() {
  local description="$1"
  shift

  local attempt=1
  while true; do
    if "$@"; then
      return 0
    fi

    if (( attempt >= MAX_RETRIES )); then
      return 1
    fi

    local sleep_seconds=$(( RETRY_BASE_SECONDS * attempt ))
    log "WARN: ${description} failed (attempt ${attempt}/${MAX_RETRIES}); retrying in ${sleep_seconds}s"
    sleep "$sleep_seconds"
    attempt=$((attempt + 1))
  done
}

for bin in aws jq mysql mysqladmin mysqldump sha256sum stat flock getent timeout; do
  require_command "$bin"
done

if [[ -z "$SNS_TOPIC_ARN" ]]; then
  echo "SNS_TOPIC_ARN must be set" >&2
  exit 1
fi

if [[ "$SECRET_NAME" == *"manual-"* ]]; then
  fail "Refusing manual secret name: ${SECRET_NAME}"
fi

mkdir -p "$WORK_DIR"
mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE" || fail "Unable to write log file: ${LOG_FILE}"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  fail "Another dump process is already running (lock=${LOCK_FILE})"
fi

log "Starting dump run"

if ! SECRET_JSON="$(aws secretsmanager get-secret-value \
  --secret-id "$SECRET_NAME" \
  --region "$AWS_REGION" \
  --query SecretString \
  --output text 2>"$SECRET_FETCH_ERR_FILE")"; then
  fail "Failed to fetch secret ${SECRET_NAME}: $(cat "$SECRET_FETCH_ERR_FILE")"
fi

DB_HOST="$(echo "$SECRET_JSON" | jq -r '.host // empty')"
DB_PORT="$(echo "$SECRET_JSON" | jq -r '.port // 3306')"
DB_USER="$(echo "$SECRET_JSON" | jq -r '.username // empty')"
DB_PASS="$(echo "$SECRET_JSON" | jq -r '.password // empty')"
DB_NAME="$(echo "$SECRET_JSON" | jq -r '.database // .dbname // empty')"

if [[ -z "$DB_HOST" || -z "$DB_NAME" || -z "$DB_USER" || -z "$DB_PASS" ]]; then
  fail "Secret ${SECRET_NAME} must include host/database/username/password"
fi

if [[ "$DB_HOST" =~ $FORBIDDEN_HOST_REGEX ]]; then
  fail "Refusing forbidden host from secret: ${DB_HOST}"
fi

if [[ "$DB_NAME" =~ $FORBIDDEN_DB_REGEX ]]; then
  fail "Refusing forbidden database from secret: ${DB_NAME}"
fi

log "Source resolved from secret host=${DB_HOST} db=${DB_NAME}"

if ! getent hosts "$DB_HOST" >/dev/null; then
  fail "DNS lookup failed for ${DB_HOST}"
fi

if ! timeout 5 bash -c "</dev/tcp/${DB_HOST}/${DB_PORT}"; then
  fail "TCP connectivity failed to ${DB_HOST}:${DB_PORT}"
fi

if ! timeout "$MYSQL_CONNECT_TIMEOUT" mysqladmin \
  --host="$DB_HOST" \
  --port="$DB_PORT" \
  --user="$DB_USER" \
  --password="$DB_PASS" \
  ping >/dev/null 2>&1; then
  fail "mysqladmin ping failed for ${DB_HOST}:${DB_PORT}"
fi

DUMP_FILE="${WORK_DIR}/gghouse_${TIMESTAMP}.sql"

create_dump() {
  MYSQL_PWD="$DB_PASS" mysqldump \
    --host="$DB_HOST" \
    --port="$DB_PORT" \
    --user="$DB_USER" \
    -B "$DB_NAME" \
    --single-transaction \
    --quick \
    --lock-tables=false \
    --set-gtid-purged=OFF \
    --triggers \
    --routines \
    --events \
    --extended-insert=true \
    --compact > "$DUMP_FILE"
}

if ! run_with_retries "mysqldump" create_dump; then
  fail "mysqldump failed after ${MAX_RETRIES} attempts"
fi

if ! DUMP_SIZE_BYTES="$(stat -c%s "$DUMP_FILE")"; then
  fail "Unable to stat dump file ${DUMP_FILE}"
fi

if (( DUMP_SIZE_BYTES < MIN_DUMP_BYTES )); then
  fail "Dump size too small: ${DUMP_SIZE_BYTES} bytes (min ${MIN_DUMP_BYTES})"
fi

DUMP_SHA256="$(sha256sum "$DUMP_FILE" | awk '{print $1}')"
log "Dump generated (${DUMP_SIZE_BYTES} bytes, sha256=${DUMP_SHA256})"

S3_KEY="${S3_DUMP_PREFIX%/}/gghouse_${TIMESTAMP}.sql"
S3_URI="s3://${S3_BUCKET}/${S3_KEY}"

upload_dump() {
  aws s3 cp "$DUMP_FILE" "$S3_URI" \
    --region "$AWS_REGION" \
    --metadata run_id="$RUN_ID",source_host="$DB_HOST",source_db="$DB_NAME",source_port="$DB_PORT",sha256="$DUMP_SHA256",created_at="$RUN_TS" \
    >/dev/null
}

if ! run_with_retries "s3 upload" upload_dump; then
  fail "Failed to upload dump to ${S3_URI}"
fi

if ! REMOTE_SIZE="$(aws s3api head-object --bucket "$S3_BUCKET" --key "$S3_KEY" --region "$AWS_REGION" --query 'ContentLength' --output text 2>"$S3_HEAD_ERR_FILE")"; then
  fail "Failed to verify dump object ${S3_KEY}: $(cat "$S3_HEAD_ERR_FILE")"
fi

if (( REMOTE_SIZE < MIN_DUMP_BYTES )) || (( REMOTE_SIZE != DUMP_SIZE_BYTES )); then
  fail "S3 object size check failed: local=${DUMP_SIZE_BYTES}, remote=${REMOTE_SIZE}, min=${MIN_DUMP_BYTES}"
fi

TABLE_LINES_FILE="${WORK_DIR}/table_max_updated_at.tsv"
: > "$TABLE_LINES_FILE"
IFS=',' read -r -a REQUIRED_TABLES <<< "$REQUIRED_TABLES_CSV"

for table_name in "${REQUIRED_TABLES[@]}"; do
  table_name="$(echo "$table_name" | xargs)"
  if [[ -z "$table_name" ]]; then
    continue
  fi

  if ! max_updated_at="$(MYSQL_PWD="$DB_PASS" mysql \
    --host="$DB_HOST" \
    --port="$DB_PORT" \
    --user="$DB_USER" \
    --database="$DB_NAME" \
    --batch --skip-column-names \
    --execute "SELECT DATE_FORMAT(CONVERT_TZ(MAX(updated_at), @@session.time_zone, '+09:00'), '%Y-%m-%dT%H:%i:%s+09:00') FROM ${table_name};")"; then
    fail "Failed to query MAX(updated_at) for table ${table_name}"
  fi

  max_updated_at="${max_updated_at//$'\n'/}"
  if [[ -z "$max_updated_at" || "$max_updated_at" == "NULL" ]]; then
    fail "MAX(updated_at) is NULL for table ${table_name}"
  fi

  printf '%s\t%s\n' "$table_name" "$max_updated_at" >> "$TABLE_LINES_FILE"
done

TABLE_MAX_JSON="$(jq -Rn '[inputs | select(length > 0) | split("\t") | {(.[0]): .[1]}] | add // {}' < "$TABLE_LINES_FILE")"

MANIFEST_FILE="${WORK_DIR}/gghouse_${TIMESTAMP}.manifest.json"
MANIFEST_KEY="${S3_MANIFEST_PREFIX%/}/gghouse_${TIMESTAMP}.json"

jq -n \
  --arg run_id "$RUN_ID" \
  --arg generated_at "$RUN_TS" \
  --arg dump_date "$TIMESTAMP" \
  --arg dump_key "$S3_KEY" \
  --arg dump_sha256 "$DUMP_SHA256" \
  --arg source_host "$DB_HOST" \
  --arg source_database "$DB_NAME" \
  --argjson source_port "$DB_PORT" \
  --argjson dump_size_bytes "$DUMP_SIZE_BYTES" \
  --argjson max_updated_at_by_table "$TABLE_MAX_JSON" \
  '{
    run_id: $run_id,
    generated_at: $generated_at,
    dump_date: $dump_date,
    dump_key: $dump_key,
    dump_sha256: $dump_sha256,
    dump_size_bytes: $dump_size_bytes,
    source_host: $source_host,
    source_database: $source_database,
    source_port: $source_port,
    source_valid: true,
    valid_for_etl: true,
    max_updated_at_by_table: $max_updated_at_by_table,
    source_table_max_updated_at: $max_updated_at_by_table
  }' > "$MANIFEST_FILE"

aws s3 cp "$MANIFEST_FILE" "s3://${S3_BUCKET}/${MANIFEST_KEY}" --region "$AWS_REGION" >/dev/null

if ! aws s3api head-object --bucket "$S3_BUCKET" --key "$MANIFEST_KEY" --region "$AWS_REGION" >/dev/null 2>&1; then
  fail "Manifest head-object check failed for ${MANIFEST_KEY}"
fi

DUMP_TAGS_FILE="${WORK_DIR}/dump_tags.json"
cat > "$DUMP_TAGS_FILE" <<JSON
{
  "TagSet": [
    {"Key": "valid_for_etl", "Value": "true"},
    {"Key": "source_valid", "Value": "true"},
    {"Key": "run_id", "Value": "${RUN_ID}"}
  ]
}
JSON

aws s3api put-object-tagging \
  --bucket "$S3_BUCKET" \
  --key "$S3_KEY" \
  --tagging "file://${DUMP_TAGS_FILE}" \
  --region "$AWS_REGION" >/dev/null

log "Dump and manifest publish succeeded (dump=${S3_KEY}, manifest=${MANIFEST_KEY})"
log "Run complete"

unset SECRET_JSON DB_HOST DB_PORT DB_USER DB_PASS DB_NAME
