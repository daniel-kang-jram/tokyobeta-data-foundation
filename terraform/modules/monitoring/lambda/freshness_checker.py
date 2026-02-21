"""
Lambda Function: Data Freshness Checker
Checks staging table freshness and dump availability in S3.
Sends SNS alert if table data or dump continuity degrades.
"""

import json
import os
from datetime import datetime, timedelta, timezone

from botocore.exceptions import ClientError
import boto3
try:
    import pymysql
except ImportError:
    pymysql = None

# Environment variables
AURORA_ENDPOINT = os.environ['AURORA_ENDPOINT']
AURORA_SECRET_ARN = os.environ['AURORA_SECRET_ARN']
SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']
S3_BUCKET = os.environ['S3_BUCKET']
S3_PREFIXES = [
    p.strip()
    for p in os.environ.get('S3_DUMP_PREFIXES', 'dumps').split(',')
    if p.strip()
]
if not S3_PREFIXES:
    S3_PREFIXES = ['dumps']

DUMP_MIN_BYTES = int(os.environ.get('S3_DUMP_MIN_BYTES', '10485760'))
DUMP_ERROR_DAYS = int(os.environ.get('S3_DUMP_ERROR_DAYS', '2'))
REQUIRE_ALL_DUMP_PREFIXES = os.environ.get(
    'S3_DUMP_REQUIRE_ALL_PREFIXES', 'true'
).lower() in ('1', 'true', 'yes', 'y')
UPSTREAM_SYNC_CHECK_ENABLED = os.environ.get(
    'UPSTREAM_SYNC_CHECK_ENABLED', 'false'
).lower() in ('1', 'true', 'yes', 'y')
UPSTREAM_SYNC_STALE_HOURS = int(os.environ.get('UPSTREAM_SYNC_STALE_HOURS', '24'))
UPSTREAM_SYNC_TABLES = [
    table.strip()
    for table in os.environ.get(
        'UPSTREAM_SYNC_TABLES',
        'movings,tenants,rooms,apartments',
    ).split(',')
    if table.strip()
]
S3_MANIFEST_PREFIX = os.environ.get('S3_MANIFEST_PREFIX', 'dumps-manifest').rstrip('/')


# AWS clients
secretsmanager = boto3.client('secretsmanager')
s3 = boto3.client('s3')
cloudwatch = boto3.client('cloudwatch')
sns = boto3.client('sns')

TABLES_TO_CHECK = ${jsonencode(tables)}
WARN_DAYS = 1
ERROR_DAYS = 2


def get_db_credentials():
    """Retrieve database credentials from Secrets Manager."""
    secret = secretsmanager.get_secret_value(SecretId=AURORA_SECRET_ARN)
    return json.loads(secret['SecretString'])


def check_table_freshness(cursor, table_name):
    """Check how old a table's data is."""
    cursor.execute(
        f"""
        SELECT
            COUNT(*) as row_count,
            MAX(updated_at) as last_updated,
            DATEDIFF(CURRENT_DATE, DATE(MAX(updated_at))) as days_old
        FROM staging.{table_name}
    """
    )

    result = cursor.fetchone()
    return {
        'table': table_name,
        'row_count': result[0],
        'last_updated': result[1].isoformat() if result[1] else None,
        'days_old': result[2] if result[2] is not None else 999,
    }


def current_jst_date():
    """Return the current date in UTC+9 for daily dump checks."""
    return (datetime.now(timezone.utc) + timedelta(hours=9)).date()


def check_dump_file(prefix, date_str):
    """Check existence and size for one dump file."""
    base_key = f"{prefix.rstrip('/')}/gghouse_{date_str}"
    candidate_keys = [f"{base_key}.sql", f"{base_key}.sql.gz"]
    last_error_code = None

    for key in candidate_keys:
        try:
            response = s3.head_object(Bucket=S3_BUCKET, Key=key)
            size = int(response.get('ContentLength', 0))
            return {
                'prefix': prefix,
                'key': key,
                'size_bytes': size,
                'ok': size >= DUMP_MIN_BYTES,
                'missing': False,
                'error': None,
            }
        except ClientError as err:
            error_code = str(err.response['Error'].get('Code'))
            if error_code not in {'404', 'NoSuchKey', 'NotFound'}:
                return {
                    'prefix': prefix,
                    'key': key,
                    'size_bytes': 0,
                    'ok': False,
                    'missing': True,
                    'error': error_code,
                }
            last_error_code = error_code

    return {
        'prefix': prefix,
        'key': candidate_keys[0],
        'size_bytes': 0,
        'ok': False,
        'missing': True,
        'error': last_error_code or 'NotFound',
    }


def publish_metric(table_name, days_old):
    """Publish staging-table freshness metric to CloudWatch."""
    cloudwatch.put_metric_data(
        Namespace='TokyoBeta/DataQuality',
        MetricData=[
            {
                'MetricName': f'Staging{table_name.capitalize()}DaysOld',
                'Value': days_old,
                'Unit': 'None',
                'Timestamp': datetime.utcnow(),
            }
        ],
    )


def safe_publish_metric(table_name, days_old):
    """Publish staging-table metric with best-effort behavior."""
    try:
        publish_metric(table_name, days_old)
    except Exception as error:  # pragma: no cover - defensive runtime guard
        print(
            f"WARN: Failed to publish staging metric for {table_name}: {type(error).__name__}: {error}"
        )


def publish_dump_metric(prefix, metric_name, value):
    """Publish dump metric to CloudWatch."""
    cloudwatch.put_metric_data(
        Namespace='TokyoBeta/DataQuality',
        MetricData=[
            {
                'MetricName': metric_name,
                'Dimensions': [
                    {
                        'Name': 'DumpPrefix',
                        'Value': prefix,
                    }
                ],
                'Value': value,
                'Unit': 'None',
                'Timestamp': datetime.utcnow(),
            }
        ],
    )


def safe_publish_dump_metric(prefix, metric_name, value):
    """Publish dump metric with best-effort behavior."""
    try:
        publish_dump_metric(prefix, metric_name, value)
    except Exception as error:  # pragma: no cover - defensive runtime guard
        print(
            "WARN: Failed to publish dump metric "
            f"(prefix={prefix}, metric={metric_name}): {type(error).__name__}: {error}"
        )


def send_alert(stale_tables):
    """Send SNS alert for stale tables."""
    message = '⚠️ STAGING TABLE FRESHNESS ALERT\n\n'
    message += 'The following staging tables are stale:\n\n'

    for table_info in stale_tables:
        status = '🔴 CRITICAL' if table_info['days_old'] >= ERROR_DAYS else '⚠️ WARNING'
        message += f"{status} staging.{table_info['table']}\n"
        message += f"  Last updated: {table_info['last_updated']}\n"
        message += f"  Days old: {table_info['days_old']}\n"
        message += f"  Row count: {table_info['row_count']:,}\n\n"

    message += 'Action required:\n'
    message += '1. Check if EC2 dump job is running\n'
    message += '2. Verify Glue staging_loader job is healthy\n'
    message += '3. Check S3 for recent dump files\n\n'
    message += 'Manual fix command:\n'
    message += 'python3 scripts/emergency_staging_fix.py --tables movings tenants rooms\n'

    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject=f'⚠️ Staging Table Freshness Alert - {len(stale_tables)} tables stale',
        Message=message,
    )


def send_dump_alert(stale_dumps):
    """Send SNS alert for raw dump issues."""
    message = '⚠️ RAW DUMP CHECK FAILED\n\n'
    message += 'The following raw dump checks failed:\n\n'
    for entry in stale_dumps[:25]:
        message += (
            f"- date={entry['date']} prefix={entry['prefix']} "
            f"size={entry['size_bytes']} error={entry['error']}\n"
        )

    message += '\nAction required:\n'
    message += '1. Validate EC2 dump job logs and IAM access to S3\n'
    message += '2. Verify upstream script wrote both dump channels\n'
    message += '3. Trigger downstream Glue staging job if raw dump is present\n'

    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject='⚠️ Raw Dump Freshness Alert',
        Message=message,
    )


def send_runtime_alert(message):
    """Send SNS alert for freshness-checker runtime failures."""
    payload = '⚠️ FRESHNESS CHECKER RUNTIME FAILURE\n\n'
    payload += f'{message}\n\n'
    payload += 'Action required:\n'
    payload += '1. Validate Lambda package dependencies (pymysql)\n'
    payload += '2. Verify VPC access to Aurora endpoint\n'
    payload += '3. Re-run freshness checker after fixing runtime dependency/config\n'

    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject='⚠️ Freshness Checker Runtime Failure',
        Message=payload,
    )


def parse_manifest_datetime(raw_value):
    """Parse ISO datetime string from manifest into JST-aware datetime."""
    if not raw_value or not isinstance(raw_value, str):
        return None
    candidate = raw_value.strip()
    if candidate.endswith('Z'):
        candidate = candidate[:-1] + '+00:00'
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone(timedelta(hours=9)))


def load_latest_dump_manifest():
    """Load the most recent dump manifest from S3."""
    prefix = f'{S3_MANIFEST_PREFIX}/gghouse_'
    latest = None
    continuation_token = None

    while True:
        request = {'Bucket': S3_BUCKET, 'Prefix': prefix}
        if continuation_token is not None:
            request['ContinuationToken'] = continuation_token

        response = s3.list_objects_v2(**request)
        for item in response.get('Contents', []):
            if latest is None:
                latest = item
                continue

            latest_modified = latest.get('LastModified')
            item_modified = item.get('LastModified')
            if latest_modified is None and item_modified is not None:
                latest = item
                continue
            if item_modified is not None and item_modified > latest_modified:
                latest = item

        if not response.get('IsTruncated'):
            break
        continuation_token = response.get('NextContinuationToken')
        if continuation_token is None:
            break

    if latest is None:
        return None, None

    manifest_key = latest['Key']
    manifest_obj = s3.get_object(Bucket=S3_BUCKET, Key=manifest_key)
    manifest = json.loads(manifest_obj['Body'].read().decode('utf-8'))
    return manifest_key, manifest


def evaluate_upstream_sync_staleness(
    manifest,
    now_jst=None,
    stale_hours=24,
    tables=None,
):
    """Evaluate upstream manifest timestamps and return stale table entries."""
    if not isinstance(manifest, dict):
        return []

    target_tables = tables or UPSTREAM_SYNC_TABLES
    if now_jst is None:
        now_jst = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=9)))

    table_map = manifest.get('max_updated_at_by_table')
    if not isinstance(table_map, dict):
        table_map = manifest.get('source_table_max_updated_at')
    if not isinstance(table_map, dict):
        return []

    stale_entries = []
    for table in target_tables:
        raw_value = table_map.get(table)
        parsed = parse_manifest_datetime(raw_value)
        if parsed is None:
            stale_entries.append(
                {
                    'table': table,
                    'max_updated_at': raw_value,
                    'lag_hours': None,
                    'reason': 'missing_or_invalid_timestamp',
                }
            )
            continue

        lag_hours = round((now_jst - parsed).total_seconds() / 3600, 2)
        if lag_hours > stale_hours:
            stale_entries.append(
                {
                    'table': table,
                    'max_updated_at': parsed.isoformat(),
                    'lag_hours': lag_hours,
                    'reason': 'stale_upstream_sync',
                }
            )

    return stale_entries


def check_upstream_sync_staleness():
    """Check manifest table timestamps for upstream sync staleness."""
    if not UPSTREAM_SYNC_CHECK_ENABLED:
        return {'manifest_key': None, 'stale_entries': []}

    manifest_key, manifest = load_latest_dump_manifest()
    stale_entries = evaluate_upstream_sync_staleness(
        manifest=manifest,
        stale_hours=UPSTREAM_SYNC_STALE_HOURS,
        tables=UPSTREAM_SYNC_TABLES,
    )
    return {'manifest_key': manifest_key, 'stale_entries': stale_entries}


def send_upstream_sync_alert(stale_entries, manifest_key):
    """Send SNS alert for stale upstream sync state."""
    message = '⚠️ UPSTREAM SYNC STALE\n\n'
    message += f'Manifest key: {manifest_key or "N/A"}\n\n'
    message += 'The following upstream tables are stale based on manifest timestamps:\n\n'
    for entry in stale_entries:
        message += (
            f"- table={entry['table']} "
            f"max_updated_at={entry.get('max_updated_at')} "
            f"lag_hours={entry.get('lag_hours')} "
            f"reason={entry.get('reason')}\n"
        )

    message += '\nAction required:\n'
    message += '1. Verify V3 -> basis upstream sync job execution\n'
    message += '2. Confirm basis allowlist still includes V3 source IP\n'
    message += '3. Re-run upstream sync and validate MAX(updated_at) recovery\n'

    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject='⚠️ Upstream Sync Stale',
        Message=message,
    )


def lambda_handler(event, context):
    """Main Lambda handler."""
    print(f'Checking table freshness for: {TABLES_TO_CHECK}')

    connection = None
    db_checks_skipped = pymysql is None

    if db_checks_skipped:
        message = (
            "pymysql dependency is missing. DB freshness checks are required; "
            "aborting instead of running partial dump-only checks."
        )
        print(f"ERROR: {message}")
        send_runtime_alert(message)
        raise RuntimeError(message)
    else:
        creds = get_db_credentials()
        connection = pymysql.connect(
            host=AURORA_ENDPOINT.split(':')[0],
            user=creds['username'],
            password=creds['password'],
            database=creds.get('dbname', 'tokyobeta'),
            charset='utf8mb4',
        )

    try:
        stale_tables = []
        warning_tables = []
        results = []
        stale_dumps = []
        stale_upstream = []
        upstream_manifest_key = None

        if connection is not None:
            cursor = connection.cursor()
            for table in TABLES_TO_CHECK:
                try:
                    table_info = check_table_freshness(cursor, table)
                    results.append(table_info)

                    safe_publish_metric(table, table_info['days_old'])

                    if table_info['days_old'] >= ERROR_DAYS:
                        stale_tables.append(table_info)
                        print(
                            f"⚠️ Table {table} is critically stale "
                            f"({table_info['days_old']} days old)"
                        )
                    elif table_info['days_old'] >= WARN_DAYS:
                        warning_tables.append(table_info)
                        print(
                            f"⚠️ Table {table} is nearing stale threshold "
                            f"({table_info['days_old']} days old)"
                        )
                    else:
                        print(
                            f"✅ Table {table} is fresh ({table_info['days_old']} days old)"
                        )
                except Exception as error:
                    print(f'Error checking {table}: {error}')
                    safe_publish_metric(table, 999)

        today = current_jst_date()
        for day_shift in range(0, DUMP_ERROR_DAYS + 1):
            date_str = (today - timedelta(days=day_shift)).strftime('%Y%m%d')
            issues = []
            healthy_prefixes = 0

            for prefix in S3_PREFIXES:
                dump_check = check_dump_file(prefix, date_str)
                if dump_check['missing']:
                    safe_publish_dump_metric(prefix, 'DumpFileMissing', 1)
                    issues.append(dump_check)
                    print(
                        f'⚠️ Missing dump file on {date_str} for {prefix}: '
                        f"{dump_check['error']}"
                    )
                    continue

                if not dump_check['ok']:
                    safe_publish_dump_metric(prefix, 'DumpFileTooSmall', 1)
                    dump_check['error'] = 'size_below_min'
                    issues.append(dump_check)
                    print(
                        f'⚠️ Dump too small on {date_str} for {prefix}: '
                        f"{dump_check['size_bytes']} bytes"
                    )
                    continue

                safe_publish_dump_metric(prefix, 'DumpFileMissing', 0)
                healthy_prefixes += 1

            date_failed = False
            if REQUIRE_ALL_DUMP_PREFIXES:
                date_failed = len(issues) > 0
            else:
                date_failed = healthy_prefixes == 0

            if date_failed:
                for issue in issues:
                    stale_dumps.append(
                        {
                            'date': date_str,
                            'prefix': issue['prefix'],
                            'size_bytes': issue['size_bytes'],
                            'error': issue['error'] or 'no_issue_recorded',
                        }
                    )
                print(f'⚠️ No healthy dump found for {date_str}')

                if not REQUIRE_ALL_DUMP_PREFIXES:
                    safe_publish_dump_metric('global', 'NoHealthyDump', 1)
                else:
                    safe_publish_dump_metric('global', 'DumpPrefixIssue', len(issues))
        if stale_dumps:
            safe_publish_dump_metric('global', 'StaleDumpEntries', len(stale_dumps))
            send_dump_alert(stale_dumps)

        upstream_result = check_upstream_sync_staleness()
        upstream_manifest_key = upstream_result.get('manifest_key')
        stale_upstream = upstream_result.get('stale_entries', [])
        if stale_upstream:
            print(
                f"⚠️ Upstream sync stale entries detected: {len(stale_upstream)} "
                f"(manifest={upstream_manifest_key})"
            )
            send_upstream_sync_alert(stale_upstream, upstream_manifest_key)

        if stale_tables:
            send_alert(stale_tables)
            print(f'Alert sent for {len(stale_tables)} stale tables')

        return {
            'statusCode': 200 if (not stale_tables and not stale_dumps and not stale_upstream) else 400,
            'body': json.dumps(
                {
                    'message': 'Freshness check complete',
                    'stale_count': len(stale_tables),
                    'warning_count': len(warning_tables),
                    'stale_dump_count': len(stale_dumps),
                    'stale_upstream_count': len(stale_upstream),
                    'db_checks_skipped': db_checks_skipped,
                    'results': results,
                    'warning_tables': warning_tables,
                    'stale_dumps': stale_dumps,
                    'stale_upstream': stale_upstream,
                    'upstream_manifest_key': upstream_manifest_key,
                }
            ),
        }
    finally:
        if connection is not None:
            connection.close()
