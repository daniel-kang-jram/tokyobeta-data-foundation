"""
AWS Glue ETL Job: Daily SQL Dump to Aurora Staging
Downloads latest SQL dump from S3, parses it, and loads into Aurora staging schema.
Then triggers dbt to transform staging → analytics.
"""

import gzip
import sys
import boto3
import json
import os
import re
import subprocess
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, date
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
import pymysql
import csv
from io import StringIO, BytesIO
from typing import List, Tuple, Dict, Any

# Initialize Glue context
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)

# Get job parameters
args = getResolvedOptions(sys.argv, [
    'JOB_NAME',
    'S3_SOURCE_BUCKET',
    'S3_SOURCE_PREFIX',
    'AURORA_ENDPOINT',
    'AURORA_DATABASE',
    'AURORA_SECRET_ARN',
    'ENVIRONMENT',
    'DBT_PROJECT_PATH'
])

job.init(args['JOB_NAME'], args)

# Initialize clients
s3 = boto3.client('s3')
secretsmanager = boto3.client('secretsmanager')
rds = boto3.client('rds')

TOTAL_PHYSICAL_ROOMS = 16108

@contextmanager
def timed_step(step_name: str, timings: Dict[str, Dict[str, Any]]):
    """
    Emit explicit step timing logs with success/failure status.
    """
    started_at = datetime.now().isoformat(timespec='seconds')
    print(f"\n>>> STEP_START [{step_name}] at {started_at}")
    step_start = time.perf_counter()

    try:
        yield
    except Exception as e:
        elapsed = time.perf_counter() - step_start
        timings[step_name] = {"status": "failed", "seconds": elapsed}
        print(f"<<< STEP_END   [{step_name}] status=failed duration={elapsed:.2f}s error={str(e)[:200]}")
        raise
    else:
        elapsed = time.perf_counter() - step_start
        timings[step_name] = {"status": "success", "seconds": elapsed}
        print(f"<<< STEP_END   [{step_name}] status=success duration={elapsed:.2f}s")


def print_step_timing_summary(timings: Dict[str, Dict[str, Any]]) -> None:
    """Print ordered summary of step durations."""
    if not timings:
        return

    print("\n=== STEP TIMING SUMMARY ===")
    total_timed = 0.0
    for step_name, info in timings.items():
        seconds = float(info.get("seconds", 0.0))
        status = info.get("status", "unknown")
        total_timed += seconds
        print(f"  - {step_name:<40} {seconds:>8.2f}s  ({status})")
    print(f"  - {'TOTAL_TIMED_STEPS':<40} {total_timed:>8.2f}s")


def env_bool(name: str, default: bool) -> bool:
    """Read boolean environment variable with safe defaults."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def env_int(name: str, default: int, minimum: int = 0) -> int:
    """Read integer environment variable with safe defaults and lower bound."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        return default
    return value if value >= minimum else minimum


def optional_argv_value(name: str) -> str | None:
    """
    Read optional Glue argument from sys.argv without requiring it in getResolvedOptions.
    Expected shape: --NAME value
    """
    token = f"--{name}"
    try:
        index = sys.argv.index(token)
    except ValueError:
        return None
    if index + 1 >= len(sys.argv):
        return None
    return sys.argv[index + 1]


def runtime_bool(name: str, default: bool) -> bool:
    """
    Read boolean runtime toggle from environment first, then optional argv, then default.
    """
    if name in os.environ:
        return env_bool(name, default)

    arg_val = optional_argv_value(name)
    if arg_val is None:
        return default
    return arg_val.strip().lower() in {"1", "true", "yes", "y", "on"}


def runtime_date(name: str, default: date) -> date:
    """Read YYYY-MM-DD runtime date from env/argv, else return default."""
    raw = os.environ.get(name)
    if raw is None:
        raw = optional_argv_value(name)
    if raw is None:
        return default
    try:
        return datetime.strptime(raw.strip(), "%Y-%m-%d").date()
    except ValueError:
        print(f"Invalid {name}={raw!r}; using default {default.isoformat()}")
        return default


def normalize_statement(stmt: str) -> str:
    """Normalize SQL statement and skip session-level commands."""
    stmt = stmt.strip()
    if not stmt:
        return ""
    if re.match(r"^(SET|LOCK TABLES|UNLOCK TABLES)", stmt, re.IGNORECASE):
        return ""
    if stmt.upper().startswith("CREATE DATABASE") or stmt.upper().startswith("USE "):
        return ""
    return stmt

def iter_sql_statements(lines):
    """Yield SQL statements without corrupting inline data."""
    statements = []
    buffer = []
    in_block_comment = False

    for line in lines:
        stripped = line.strip()
        if in_block_comment:
            if "*/" in stripped:
                in_block_comment = False
            continue
        if stripped.startswith("/*"):
            if not stripped.endswith("*/"):
                in_block_comment = True
            continue
        if stripped.startswith("--"):
            continue

        buffer.append(line)
        if stripped.endswith(";"):
            raw_stmt = "".join(buffer)
            buffer = []
            stmt = normalize_statement(raw_stmt)
            if stmt:
                statements.append(stmt)

    if buffer:
        stmt = normalize_statement("".join(buffer))
        if stmt:
            statements.append(stmt)

    return statements

def extract_table_name(stmt: str) -> str | None:
    """Extract table name from CREATE TABLE or INSERT INTO."""
    match = re.match(r"^(CREATE TABLE|INSERT INTO)\s+`?(\w+)`?", stmt, re.IGNORECASE)
    if not match:
        return None
    return match.group(2)


def reset_staging_tables(cursor) -> int:
    """
    Drop existing staging tables before loading a full SQL dump.
    This guarantees a clean replace even when dumps omit DROP TABLE statements.
    """
    cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'staging'
    """)
    existing_tables = [row[0] for row in cursor.fetchall()]

    if not existing_tables:
        print("No existing staging tables - clean load")
        return 0

    print(f"Dropping {len(existing_tables)} existing staging tables before load")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
    try:
        for table_name in existing_tables:
            cursor.execute(f"DROP TABLE IF EXISTS `staging`.`{table_name}`")
    finally:
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")

    return len(existing_tables)


def get_latest_dump_key():
    """Find the most recent SQL dump file in S3."""
    response = s3.list_objects_v2(
        Bucket=args['S3_SOURCE_BUCKET'],
        Prefix=args['S3_SOURCE_PREFIX']
    )
    
    if 'Contents' not in response:
        raise ValueError(f"No files found in s3://{args['S3_SOURCE_BUCKET']}/{args['S3_SOURCE_PREFIX']}")
    
    # Sort by LastModified descending
    files = sorted(response['Contents'], key=lambda x: x['LastModified'], reverse=True)
    
    # Filter for gghouse_YYYYMMDD.sql or .sql.gz pattern
    sql_files = [
        f for f in files
        if re.match(r'.*gghouse_\d{8}\.sql(\.gz)?$', f['Key'])
    ]
    
    if not sql_files:
        raise ValueError("No SQL dump files matching pattern gghouse_YYYYMMDD.sql found")
    
    latest_key = sql_files[0]['Key']
    print(f"Latest dump: {latest_key} (modified: {sql_files[0]['LastModified']})")
    return latest_key


def get_processed_dump_key(source_key: str) -> str:
    """Map dumps/ key to processed/ key."""
    if source_key.startswith("dumps/"):
        return source_key.replace("dumps/", "processed/", 1)
    if "/dumps/" in source_key:
        return source_key.replace("/dumps/", "/processed/", 1)
    return f"processed/{source_key}"


def extract_dump_date_from_key(s3_key: str) -> date | None:
    """
    Extract dump date from S3 key like gghouse_YYYYMMDD.sql(.gz).
    Returns None if the key doesn't match expected pattern.
    """
    m = re.search(r"gghouse_(\d{8})\.sql(\.gz)?$", s3_key)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d").date()
    except ValueError:
        return None


def get_aurora_credentials():
    """Retrieve Aurora credentials from Secrets Manager."""
    response = secretsmanager.get_secret_value(SecretId=args['AURORA_SECRET_ARN'])
    secret = json.loads(response['SecretString'])
    return secret['username'], secret['password']

def download_and_parse_dump(s3_key):
    """Download SQL dump from S3 and return local path."""
    local_path = f"/tmp/{s3_key.split('/')[-1]}"
    
    print(f"Downloading {s3_key} to {local_path}...")
    s3.download_file(args['S3_SOURCE_BUCKET'], s3_key, local_path)
    print(f"Downloaded to {local_path}")
    return local_path

def open_dump_file(local_path):
    """Open SQL dump file, supporting optional gzip compression."""
    if local_path.endswith(".gz"):
        return gzip.open(local_path, "rt", encoding="utf-8", errors="ignore")
    return open(local_path, "r", encoding="utf-8", errors="ignore")

def load_to_aurora_staging(dump_path):
    """Load SQL dump into Aurora staging schema."""
    username, password = get_aurora_credentials()
    
    # Connect to Aurora
    connection = pymysql.connect(
        host=args['AURORA_ENDPOINT'],
        user=username,
        password=password,
        database=args['AURORA_DATABASE'],
        charset='utf8mb4'
    )
    
    try:
        cursor = connection.cursor()
        
        # Create all required schemas if they don't exist
        cursor.execute("CREATE SCHEMA IF NOT EXISTS staging")
        cursor.execute("CREATE SCHEMA IF NOT EXISTS analytics")
        cursor.execute("CREATE SCHEMA IF NOT EXISTS seeds")
        cursor.execute("USE staging")
        cursor.execute("SET SESSION sql_mode = 'ALLOW_INVALID_DATES'")
        cursor.execute("SET NAMES utf8mb4")
        
        print("Schemas verified/created: staging, analytics, seeds")
        
        dropped_tables = reset_staging_tables(cursor)
        if dropped_tables > 0:
            print(f"Reset staging schema: dropped {dropped_tables} tables")
        
        connection.commit()
        
        # Stream and execute SQL statements incrementally (900MB+ dump)
        # Uses same buffering logic as local load_dump_key_tables_pymysql.py
        print("Streaming and executing SQL statements...")
        
        executed = 0
        buffer = []
        
        with open_dump_file(dump_path) as dump_file:
            for line in dump_file:
                buffer.append(line)
                
                # Execute when we hit statement terminator (same as local script)
                if line.rstrip().endswith(";"):
                    raw_stmt = "".join(buffer)
                    buffer = []
                    stmt = normalize_statement(raw_stmt)
                    
                    if stmt:
                        try:
                            cursor.execute(stmt)
                            executed += 1
                            
                            if executed % 100 == 0:
                                print(f"Progress: {executed} statements executed")
                                connection.commit()
                        except Exception as e:
                            table_name = extract_table_name(stmt)
                            table_hint = f" table={table_name}" if table_name else ""
                            print(f"Warning: Statement failed:{table_hint} {str(e)[:200]}")
                            continue
        
        connection.commit()
        print(f"Successfully executed {executed} statements")
        
        # Verify tables were created
        cursor.execute("""
            SELECT table_name, table_rows 
            FROM information_schema.tables 
            WHERE table_schema = 'staging'
            ORDER BY table_name
        """)
        
        tables = cursor.fetchall()
        print(f"\nStaging schema now contains {len(tables)} tables:")
        for table_name, row_count in tables:
            print(f"  - {table_name}: {row_count} rows")
        
        return len(tables), executed
        
    finally:
        cursor.close()
        connection.close()

def create_pre_etl_backups():
    """
    Create backup copies of critical tables before ETL transformations.
    This protects against data loss if dbt models fail or produce incorrect results.
    """
    print("\n=== Creating Pre-ETL Backups ===")
    
    CRITICAL_TABLES = [
        'silver.tenant_status_history',
        'silver.int_contracts',
        'gold.daily_activity_summary',
        'gold.new_contracts',
        'gold.moveouts',
        'gold.moveout_notices'
    ]
    
    username, password = get_aurora_credentials()
    connection = pymysql.connect(
        host=args['AURORA_ENDPOINT'],
        user=username,
        password=password,
        database=args['AURORA_DATABASE'],
        charset='utf8mb4'
    )
    
    backup_count = 0
    backup_suffix = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    try:
        cursor = connection.cursor()
        
        for table in CRITICAL_TABLES:
            schema, table_name = table.split('.')
            backup_name = f"{table_name}_backup_{backup_suffix}"
            
            try:
                # Check if table exists
                cursor.execute(f"SHOW TABLES FROM {schema} LIKE '{table_name}'")
                if cursor.fetchone():
                    row_count_result = cursor.execute(f"SELECT COUNT(*) FROM {schema}.{table_name}")
                    cursor.fetchone()
                    
                    print(f"  Backing up {table}...")
                    cursor.execute(f"""
                        CREATE TABLE {schema}.{backup_name} 
                        AS SELECT * FROM {schema}.{table_name}
                    """)
                    
                    # Verify backup
                    cursor.execute(f"SELECT COUNT(*) FROM {schema}.{backup_name}")
                    backup_row_count = cursor.fetchone()[0]
                    print(f"    ✓ Created {schema}.{backup_name} ({backup_row_count} rows)")
                    backup_count += 1
                else:
                    print(f"  ⊘ Skipping {table} (table does not exist)")
                    
            except Exception as e:
                print(f"  ✗ Failed to backup {table}: {str(e)[:200]}")
                # Continue with other backups even if one fails
                continue
        
        connection.commit()
        print(f"\nBackup complete: {backup_count} tables backed up")
        return backup_count
        
    finally:
        cursor.close()
        connection.close()

def cleanup_old_backups(days_to_keep=3, include_staging=True):
    """
    Remove backup tables older than N days to manage storage costs.
    Backup table naming convention: {table_name}_backup_{YYYYMMDD_HHMMSS}

    Args:
        days_to_keep: Retention window in days.
        include_staging: Whether to clean staging.*_backup_* in addition to silver/gold.
    """
    print(f"\n=== Cleaning Up Old Backups (keeping last {days_to_keep} days) ===")
    
    cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).strftime('%Y%m%d')
    
    username, password = get_aurora_credentials()
    connection = pymysql.connect(
        host=args['AURORA_ENDPOINT'],
        user=username,
        password=password,
        database=args['AURORA_DATABASE'],
        charset='utf8mb4'
    )
    
    removed_count = 0
    
    try:
        cursor = connection.cursor()
        
        schemas_to_cleanup = ['silver', 'gold']
        if include_staging:
            schemas_to_cleanup.append('staging')

        for schema in schemas_to_cleanup:
            cursor.execute(f"""
                SELECT TABLE_NAME 
                FROM information_schema.TABLES 
                WHERE TABLE_SCHEMA = '{schema}' 
                AND TABLE_NAME LIKE '%_backup_%'
                ORDER BY TABLE_NAME
            """)
            
            backup_tables = [row[0] for row in cursor.fetchall()]
            
            for table_name in backup_tables:
                # Extract date from backup name (format: tablename_backup_YYYYMMDD_HHMMSS)
                if '_backup_' in table_name:
                    try:
                        date_part = table_name.split('_backup_')[1][:8]
                        if date_part < cutoff_date:
                            print(f"  Removing old backup: {schema}.{table_name} (date: {date_part})")
                            cursor.execute(f"DROP TABLE IF EXISTS {schema}.{table_name}")
                            removed_count += 1
                    except (IndexError, ValueError) as e:
                        print(f"  Warning: Could not parse date from {table_name}: {e}")
                        continue
        
        connection.commit()
        print(f"Cleanup complete: {removed_count} old backups removed")
        return removed_count
        
    finally:
        cursor.close()
        connection.close()

def cleanup_dbt_tmp_tables():
    """
    Clean up leftover dbt temporary tables (*__dbt_tmp) in silver/gold schemas.
    
    Returns:
        Number of tables dropped
    """
    print(f"\n=== Cleaning up dbt temp tables ===")
    
    username, password = get_aurora_credentials()
    connection = pymysql.connect(
        host=args['AURORA_ENDPOINT'],
        user=username,
        password=password,
        database=args['AURORA_DATABASE'],
        charset='utf8mb4'
    )
    
    cursor = connection.cursor()
    dropped_count = 0
    
    try:
        # Check both silver and gold schemas
        for schema in ['silver', 'gold']:
            # Find all tables ending with __dbt_tmp
            cursor.execute(f"""
                SELECT TABLE_NAME 
                FROM information_schema.TABLES 
                WHERE TABLE_SCHEMA = %s 
                AND TABLE_NAME LIKE '%%__dbt_tmp'
            """, (schema,))
            
            tmp_tables = [row[0] for row in cursor.fetchall()]
            
            if not tmp_tables:
                continue
                
            print(f"  Found {len(tmp_tables)} temporary tables in {schema}: {', '.join(tmp_tables)}")
            
            import re
            for table_name in tmp_tables:
                # Validate table name strictly to prevent SQL injection
                if not re.match(r'^[a-zA-Z0-9_]+__dbt_tmp$', table_name):
                    print(f"  ⚠ Skipping invalid table name: {table_name}")
                    continue
                    
                print(f"  Dropping {schema}.{table_name}...")
                cursor.execute(f"DROP TABLE IF EXISTS `{schema}`.`{table_name}`")
                dropped_count += 1
            
        connection.commit()
        if dropped_count > 0:
            print(f"  ✓ Dropped {dropped_count} temporary tables")
        else:
            print("  No temporary tables found.")
            
        return dropped_count
        
    except Exception as e:
        print(f"  ⚠ Warning: Failed to cleanup temp tables: {str(e)}")
        return 0
    finally:
        cursor.close()
        connection.close()

def run_dbt_transformations():
    """Execute dbt models to transform staging → analytics."""
    print("\nRunning dbt transformations...")
    
    # Download dbt project from S3
    dbt_local_path = "/tmp/dbt-project"
    sync_start = time.perf_counter()
    subprocess.run([
        "aws", "s3", "sync",
        f"s3://{args['S3_SOURCE_BUCKET']}/dbt-project/",
        dbt_local_path
    ], check=True)
    print(f"[dbt_timing] s3_sync_seconds={time.perf_counter() - sync_start:.2f}")

    # Guardrail: disable stale model YAML config that can reintroduce delete+insert
    # incremental strategy (unique_key) from S3. Runtime SQL config is the source of truth.
    tenant_snapshot_yaml = os.path.join(
        dbt_local_path, "models", "silver", "tenant_room_snapshot_daily.yml"
    )
    if os.path.exists(tenant_snapshot_yaml):
        disabled_path = tenant_snapshot_yaml + ".disabled"
        os.replace(tenant_snapshot_yaml, disabled_path)
        print(
            "Disabled runtime config file tenant_room_snapshot_daily.yml "
            f"at {disabled_path} to avoid lock-heavy incremental deletes."
        )
    
    # Set environment variables for dbt
    username, password = get_aurora_credentials()
    os.environ['AURORA_ENDPOINT'] = args['AURORA_ENDPOINT']
    os.environ['AURORA_USERNAME'] = username
    os.environ['AURORA_PASSWORD'] = password
    os.environ['DBT_TARGET'] = args['ENVIRONMENT']

    # Anchor dbt's notion of "daily snapshot date" to the dump date (JST),
    # not the Aurora server clock (typically UTC). This avoids off-by-one day
    # snapshots when the job runs at 07:00 JST (22:00 UTC previous day).
    snapshot_date = runtime_date("DAILY_TARGET_DATE", datetime.now().date())
    dbt_vars_payload = json.dumps({"daily_snapshot_date": snapshot_date.isoformat()})
    print(f"[dbt_vars] daily_snapshot_date={snapshot_date.isoformat()}")

    # Exclude optional models from the main graph run.
    # Override via DBT_EXCLUDE_MODELS env var (comma-separated list).
    dbt_excludes_env = os.environ.get("DBT_EXCLUDE_MODELS", "")
    dbt_excludes = [m.strip() for m in dbt_excludes_env.split(",") if m.strip()]
    if dbt_excludes:
        print(f"dbt excludes for this run: {', '.join(dbt_excludes)}")

    # Run lock-sensitive incremental models in serial first to reduce lock contention.
    pre_run_models_env = os.environ.get("DBT_PRE_RUN_MODELS", "silver.tenant_room_snapshot_daily")
    pre_run_models = [m.strip() for m in pre_run_models_env.split(",") if m.strip()]
    pre_run_retries = env_int("DBT_PRE_RUN_RETRIES", 1, minimum=1)
    pre_run_retry_sleep = env_int("DBT_PRE_RUN_RETRY_SLEEP_SECONDS", 30, minimum=0)
    if pre_run_models:
        print(f"dbt pre-run serial models: {', '.join(pre_run_models)}")

    # Run heavy full-rebuild models serially after main graph.
    # Keep default empty: these can be expensive and are not required for core gold outputs.
    # Enable explicitly via DBT_POST_RUN_MODELS (comma-separated).
    post_run_models_env = os.environ.get("DBT_POST_RUN_MODELS", "")
    post_run_models = [m.strip() for m in post_run_models_env.split(",") if m.strip()]
    post_run_retries = env_int("DBT_POST_RUN_RETRIES", 1, minimum=1)
    post_run_retry_sleep = env_int("DBT_POST_RUN_RETRY_SLEEP_SECONDS", 30, minimum=0)
    if post_run_models:
        print(f"dbt post-run serial models: {', '.join(post_run_models)}")
    
    # dbt is installed in /home/spark/.local/bin/ by pip --user in Glue
    dbt_executable = "/home/spark/.local/bin/dbt"
    
    def run_dbt_cmd(cmd: List[str], label: str) -> subprocess.CompletedProcess:
        """Run dbt command and emit stdout/stderr for CloudWatch visibility."""
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(f"=== {label} OUTPUT ===")
        print(result.stdout)
        if result.stderr:
            print(f"=== {label} ERRORS ===")
            print(result.stderr)
        if result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)
        return result

    def kill_stale_dbt_queries(max_age_seconds: int = 600) -> int:
        """
        Kill stale dbt queries left behind by previous failed runs.
        These stale long-running DELETE statements can hold row locks and
        repeatedly cause 1205 lock wait timeouts for new runs.
        """
        print(f"\n=== Checking for stale dbt queries (>{max_age_seconds}s) ===")
        killed = 0
        try:
            username, password = get_aurora_credentials()
            connection = pymysql.connect(
                host=args['AURORA_ENDPOINT'],
                user=username,
                password=password,
                database=args['AURORA_DATABASE'],
                charset='utf8mb4'
            )
            try:
                cursor = connection.cursor()
                cursor.execute("SELECT CONNECTION_ID()")
                current_connection_id = cursor.fetchone()[0]

                cursor.execute("""
                    SELECT
                        ID,
                        TIME,
                        LEFT(INFO, 300)
                    FROM information_schema.PROCESSLIST
                    WHERE COMMAND = 'Query'
                      AND TIME >= %s
                      AND INFO IS NOT NULL
                      AND INFO LIKE '/* {"app": "dbt"%%'
                      AND ID <> %s
                    ORDER BY TIME DESC
                    LIMIT 50
                """, (max_age_seconds, current_connection_id))
                stale_rows = cursor.fetchall()

                if not stale_rows:
                    print("  No stale dbt queries found.")
                    return 0

                print(f"  Found {len(stale_rows)} stale dbt query(ies).")
                for thread_id, query_time, query_snippet in stale_rows:
                    try:
                        print(f"  Killing thread {thread_id} (running {query_time}s): {query_snippet}")
                        cursor.execute(f"KILL QUERY {int(thread_id)}")
                        killed += 1
                    except Exception as kill_error:
                        print(f"  Failed to kill thread {thread_id}: {kill_error}")

                print(f"  Killed stale dbt queries: {killed}")
                return killed
            finally:
                connection.close()
        except Exception as e:
            print(f"  Warning: stale dbt query cleanup failed: {e}")
            return killed

    def log_aurora_lock_diagnostics() -> None:
        """
        Print lock diagnostics to identify blocking transactions when MySQL returns 1205.
        Best-effort only; failures should not mask the original dbt error.
        """
        print("\n=== AURORA LOCK DIAGNOSTICS ===")
        try:
            username, password = get_aurora_credentials()
            connection = pymysql.connect(
                host=args['AURORA_ENDPOINT'],
                user=username,
                password=password,
                database=args['AURORA_DATABASE'],
                charset='utf8mb4'
            )
            try:
                cursor = connection.cursor()

                cursor.execute("""
                    SELECT
                        trx_id,
                        trx_state,
                        trx_started,
                        trx_wait_started,
                        trx_mysql_thread_id,
                        trx_rows_locked,
                        trx_rows_modified,
                        LEFT(trx_query, 300)
                    FROM information_schema.innodb_trx
                    ORDER BY trx_started
                    LIMIT 20
                """)
                trx_rows = cursor.fetchall()
                print("[lock_diag] innodb_trx:")
                if trx_rows:
                    for row in trx_rows:
                        print(f"  {row}")
                else:
                    print("  (none)")

                print("[lock_diag] innodb_lock_waits:")
                try:
                    cursor.execute("""
                        SELECT
                            r.trx_id AS waiting_trx_id,
                            r.trx_mysql_thread_id AS waiting_thread_id,
                            b.trx_id AS blocking_trx_id,
                            b.trx_mysql_thread_id AS blocking_thread_id,
                            LEFT(r.trx_query, 300) AS waiting_query,
                            LEFT(b.trx_query, 300) AS blocking_query
                        FROM information_schema.innodb_lock_waits w
                        JOIN information_schema.innodb_trx r ON r.trx_id = w.requesting_trx_id
                        JOIN information_schema.innodb_trx b ON b.trx_id = w.blocking_trx_id
                        LIMIT 20
                    """)
                    wait_rows = cursor.fetchall()
                    if wait_rows:
                        for row in wait_rows:
                            print(f"  {row}")
                    else:
                        print("  (none)")
                except Exception as lock_wait_error:
                    print(f"  unavailable via information_schema.innodb_lock_waits: {lock_wait_error}")
                    try:
                        cursor.execute("""
                            SELECT
                                w.REQUESTING_ENGINE_TRANSACTION_ID AS waiting_trx_id,
                                w.BLOCKING_ENGINE_TRANSACTION_ID AS blocking_trx_id,
                                rw.THREAD_ID AS waiting_thread_id,
                                bw.THREAD_ID AS blocking_thread_id,
                                rw.OBJECT_SCHEMA AS waiting_schema,
                                rw.OBJECT_NAME AS waiting_object,
                                bw.OBJECT_SCHEMA AS blocking_schema,
                                bw.OBJECT_NAME AS blocking_object
                            FROM performance_schema.data_lock_waits w
                            LEFT JOIN performance_schema.data_locks rw
                                ON rw.ENGINE_TRANSACTION_ID = w.REQUESTING_ENGINE_TRANSACTION_ID
                            LEFT JOIN performance_schema.data_locks bw
                                ON bw.ENGINE_TRANSACTION_ID = w.BLOCKING_ENGINE_TRANSACTION_ID
                            LIMIT 20
                        """)
                        wait_rows = cursor.fetchall()
                        if wait_rows:
                            for row in wait_rows:
                                print(f"  {row}")
                        else:
                            print("  (none in performance_schema.data_lock_waits)")
                    except Exception as pfs_wait_error:
                        print(f"  unavailable via performance_schema.data_lock_waits: {pfs_wait_error}")

                cursor.execute("""
                    SELECT
                        ID,
                        USER,
                        HOST,
                        DB,
                        COMMAND,
                        TIME,
                        STATE,
                        LEFT(INFO, 300)
                    FROM information_schema.PROCESSLIST
                    WHERE COMMAND <> 'Sleep'
                    ORDER BY TIME DESC
                    LIMIT 30
                """)
                process_rows = cursor.fetchall()
                print("[lock_diag] processlist_non_sleep:")
                if process_rows:
                    for row in process_rows:
                        print(f"  {row}")
                else:
                    print("  (none)")
            finally:
                connection.close()
        except Exception as diag_error:
            print(f"[lock_diag] diagnostics failed: {diag_error}")
        print("=== END AURORA LOCK DIAGNOSTICS ===\n")

    # Install dbt dependencies
    deps_start = time.perf_counter()
    subprocess.run([
        dbt_executable, "deps",
        "--profiles-dir", dbt_local_path,
        "--project-dir", dbt_local_path
    ], check=True)
    print(f"[dbt_timing] deps_seconds={time.perf_counter() - deps_start:.2f}")
    
    # Load seed files (code mappings)
    seed_start = time.perf_counter()
    run_dbt_cmd([
        dbt_executable, "seed",
        "--profiles-dir", dbt_local_path,
        "--project-dir", dbt_local_path,
        "--vars", dbt_vars_payload,
        "--target", args['ENVIRONMENT']
    ], "DBT SEED")
    print(f"[dbt_timing] seed_seconds={time.perf_counter() - seed_start:.2f}")

    def run_serial_dbt_phase(
        phase_name: str,
        model_names: List[str],
        retries: int,
        retry_sleep_seconds: int
    ) -> None:
        """Run selected dbt models in serial with retry on lock waits."""
        if not model_names:
            print(f"[dbt_timing] {phase_name}_total_seconds=0.00 (no {phase_name} models configured)")
            return

        phase_start = time.perf_counter()
        phase_cmd = [
            dbt_executable, "run",
            "--profiles-dir", dbt_local_path,
            "--project-dir", dbt_local_path,
            "--target", args['ENVIRONMENT'],
            "--vars", dbt_vars_payload,
            "--fail-fast",
            "--threads", "1",
            "--select",
        ] + model_names

        phase_success = False
        for attempt in range(1, retries + 1):
            attempt_start = time.perf_counter()
            try:
                run_dbt_cmd(phase_cmd, f"DBT RUN {phase_name.upper()} (attempt {attempt}/{retries})")
                phase_success = True
                print(f"[dbt_timing] {phase_name}_attempt_{attempt}_seconds={time.perf_counter() - attempt_start:.2f}")
                break
            except subprocess.CalledProcessError as e:
                combined_output = f"{e.stdout or ''}\n{e.stderr or ''}"
                is_lock_wait = "Lock wait timeout exceeded" in combined_output
                print(f"[dbt_timing] {phase_name}_attempt_{attempt}_seconds={time.perf_counter() - attempt_start:.2f}")
                if is_lock_wait and attempt < retries:
                    log_aurora_lock_diagnostics()
                    print(
                        f"Lock wait timeout detected in {phase_name}; "
                        f"retrying in {retry_sleep_seconds}s (attempt {attempt + 1}/{retries})"
                    )
                    cleanup_dbt_tmp_tables()
                    if retry_sleep_seconds > 0:
                        time.sleep(retry_sleep_seconds)
                    continue
                if is_lock_wait:
                    log_aurora_lock_diagnostics()
                raise

        if not phase_success:
            raise RuntimeError(f"dbt {phase_name} failed unexpectedly")
        print(f"[dbt_timing] {phase_name}_total_seconds={time.perf_counter() - phase_start:.2f}")

    # Phase A: run lock-sensitive incrementals first.
    kill_stale_dbt_queries(max_age_seconds=600)
    run_serial_dbt_phase(
        phase_name="pre_run",
        model_names=pre_run_models,
        retries=pre_run_retries,
        retry_sleep_seconds=pre_run_retry_sleep,
    )

    # Phase B: run remaining dbt graph
    run_start = time.perf_counter()
    run_cmd = [
        dbt_executable, "run",
        "--profiles-dir", dbt_local_path,
        "--project-dir", dbt_local_path,
        "--target", args['ENVIRONMENT'],
        "--vars", dbt_vars_payload,
        "--fail-fast"
    ]
    remaining_excludes = list(dict.fromkeys(dbt_excludes + pre_run_models + post_run_models))
    for model_name in remaining_excludes:
        run_cmd.extend(["--exclude", model_name])

    result = run_dbt_cmd(run_cmd, "DBT RUN MAIN-PHASE")
    print(f"[dbt_timing] run_seconds={time.perf_counter() - run_start:.2f}")

    # Phase C: run heavy full-rebuild models in serial after main graph.
    run_serial_dbt_phase(
        phase_name="post_run",
        model_names=post_run_models,
        retries=post_run_retries,
        retry_sleep_seconds=post_run_retry_sleep,
    )
    
    # Run dbt tests (optional; disabled by default for faster daily SLA)
    run_dbt_tests = env_bool("DAILY_RUN_DBT_TESTS", False)
    if run_dbt_tests:
        test_start = time.perf_counter()
        test_cmd = [
            dbt_executable, "test",
            "--profiles-dir", dbt_local_path,
            "--project-dir", dbt_local_path,
            "--target", args['ENVIRONMENT'],
            "--vars", dbt_vars_payload,
        ]
        for model_name in remaining_excludes:
            test_cmd.extend(["--exclude", model_name])

        test_result = subprocess.run(test_cmd, capture_output=True, text=True)
        print(test_result.stdout)
        if test_result.returncode != 0:
            print(f"WARNING: dbt tests failed:\n{test_result.stderr}")
            # Don't fail job on test failures, just warn
        print(f"[dbt_timing] test_seconds={time.perf_counter() - test_start:.2f}")
    else:
        print("[dbt_timing] test_seconds=0.00 (skipped by DAILY_RUN_DBT_TESTS=false)")
    
    return result.returncode == 0

def cleanup_empty_staging_tables():
    """Drop empty staging tables to optimize database performance."""
    print("\nCleaning up empty staging tables...")
    
    username, password = get_aurora_credentials()
    
    connection = pymysql.connect(
        host=args['AURORA_ENDPOINT'],
        user=username,
        password=password,
        database=args['AURORA_DATABASE'],
        charset='utf8mb4'
    )
    
    try:
        cursor = connection.cursor()
        
        # Find empty tables
        cursor.execute("""
            SELECT TABLE_NAME 
            FROM information_schema.TABLES 
            WHERE TABLE_SCHEMA = 'staging' 
            AND TABLE_ROWS = 0
        """)
        
        empty_tables = [row[0] for row in cursor.fetchall()]
        
        if not empty_tables:
            print("No empty tables found - staging schema is clean")
            return 0
        
        print(f"Found {len(empty_tables)} empty tables to drop")
        
        dropped_count = 0
        for table_name in empty_tables:
            # Double-check it's actually empty
            cursor.execute(f"SELECT COUNT(*) FROM `staging`.`{table_name}`")
            actual_count = cursor.fetchone()[0]
            
            if actual_count == 0:
                try:
                    cursor.execute(f"DROP TABLE IF EXISTS `staging`.`{table_name}`")
                    connection.commit()
                    print(f"  Dropped: {table_name}")
                    dropped_count += 1
                except Exception as e:
                    print(f"  Failed to drop {table_name}: {str(e)}")
            else:
                print(f"  Skipped {table_name}: has {actual_count} rows")
        
        print(f"Cleanup completed: {dropped_count} empty tables dropped")
        return dropped_count
        
    finally:
        cursor.close()
        connection.close()

def query_tenant_snapshot(cursor) -> List[Tuple]:
    """Query current tenant snapshot from staging.tenants."""
    query = """
        SELECT 
            id AS tenant_id,
            status,
            contract_type,
            full_name
        FROM staging.tenants
        ORDER BY id
    """
    cursor.execute(query)
    return cursor.fetchall()


def generate_snapshot_csv(rows: List[Tuple], snapshot_date: date) -> str:
    """Generate CSV content from snapshot rows."""
    output = StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['tenant_id', 'status', 'contract_type', 'full_name', 'snapshot_date'])
    
    # Data rows
    for row in rows:
        tenant_id, status, contract_type, full_name = row
        writer.writerow([tenant_id, status, contract_type, full_name, snapshot_date.strftime('%Y-%m-%d')])
    
    return output.getvalue()


def upload_snapshot_csv(s3_client, bucket: str, csv_content: str, snapshot_date: date):
    """Upload snapshot CSV to S3."""
    date_str = snapshot_date.strftime('%Y%m%d')
    key = f"snapshots/tenant_status/{date_str}.csv"
    
    print(f"Uploading snapshot to s3://{bucket}/{key}")
    
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=csv_content.encode('utf-8'),
        ContentType='text/csv'
    )
    
    print(f"✓ Uploaded snapshot: {len(csv_content):,} bytes")


def export_tenant_snapshot_to_s3(connection, s3_client, bucket: str, snapshot_date: date) -> Dict[str, Any]:
    """
    Export current tenant snapshot to S3.
    
    Called after staging load, ensures S3 always has latest snapshot.
    """
    print("\n" + "="*60)
    print("STEP: Export Tenant Snapshot to S3")
    print("="*60)
    
    try:
        cursor = connection.cursor()
        
        # Query snapshot
        rows = query_tenant_snapshot(cursor)
        print(f"Queried {len(rows)} tenant records")
        
        # Generate CSV
        csv_content = generate_snapshot_csv(rows, snapshot_date)
        
        # Upload to S3
        upload_snapshot_csv(s3_client, bucket, csv_content, snapshot_date)
        
        cursor.close()
        
        return {
            'status': 'success',
            'rows_exported': len(rows),
            'snapshot_date': snapshot_date
        }
    
    except Exception as e:
        print(f"⚠ Warning: Snapshot export failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'status': 'failed',
            'error': str(e)
        }


def list_snapshot_csvs(s3_client, bucket: str, prefix: str = 'snapshots/tenant_status/') -> List[str]:
    """List all snapshot CSV files from S3."""
    print(f"Listing snapshot CSVs from s3://{bucket}/{prefix}")
    
    paginator = s3_client.get_paginator('list_objects_v2')
    csv_keys = []
    
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        if 'Contents' not in page:
            continue
        
        for obj in page['Contents']:
            key = obj['Key']
            if key.endswith('.csv'):
                csv_keys.append(key)
    
    csv_keys.sort()
    print(f"Found {len(csv_keys)} snapshot CSV files")
    
    return csv_keys


def create_tenant_daily_snapshots_table(cursor):
    """Create staging.tenant_daily_snapshots table if it doesn't exist."""
    create_table_sql = """
        CREATE TABLE IF NOT EXISTS staging.tenant_daily_snapshots (
            tenant_id INT NOT NULL,
            status INT NOT NULL,
            contract_type INT NOT NULL,
            full_name VARCHAR(191),
            snapshot_date DATE NOT NULL,
            PRIMARY KEY (tenant_id, snapshot_date),
            INDEX idx_snapshot_date (snapshot_date),
            INDEX idx_tenant_id (tenant_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        COMMENT='Daily tenant status snapshots loaded from S3'
    """
    
    cursor.execute(create_table_sql)
    print("✓ Created/verified staging.tenant_daily_snapshots table")


def download_and_parse_csv(s3_client, bucket: str, key: str) -> List[Tuple]:
    """Download and parse a snapshot CSV from S3."""
    response = s3_client.get_object(Bucket=bucket, Key=key)
    content = response['Body'].read().decode('utf-8')
    
    reader = csv.DictReader(StringIO(content))
    rows = []
    
    for row in reader:
        rows.append((
            int(row['tenant_id']),
            int(row['status']),
            int(row['contract_type']),
            row['full_name'],
            datetime.strptime(row['snapshot_date'], '%Y-%m-%d').date()
        ))
    
    return rows


def bulk_insert_snapshots(connection, cursor, rows: List[Tuple]) -> int:
    """Bulk insert snapshot rows into Aurora."""
    if not rows:
        return 0
    
    insert_sql = """
        INSERT INTO staging.tenant_daily_snapshots
        (tenant_id, status, contract_type, full_name, snapshot_date)
        VALUES (%s, %s, %s, %s, %s)
    """
    
    cursor.executemany(insert_sql, rows)
    connection.commit()
    
    return len(rows)


def load_tenant_snapshots_from_s3(connection, s3_client, bucket: str) -> Dict[str, Any]:
    """
    Load new snapshot CSVs from S3 into staging.tenant_daily_snapshots (INCREMENTAL).
    
    Only loads snapshots that don't already exist in the table.
    First run: loads all historical snapshots (backfill)
    Daily runs: loads only today's new snapshot
    """
    print("\n" + "="*60)
    print("STEP: Load Tenant Snapshots from S3 (Incremental)")
    print("="*60)
    
    try:
        cursor = connection.cursor()
        
        # Create table if not exists
        create_tenant_daily_snapshots_table(cursor)
        
        # Get existing snapshot dates in the table
        print("Checking existing snapshots in database...")
        cursor.execute('SELECT DISTINCT snapshot_date FROM staging.tenant_daily_snapshots')
        existing_dates = {row[0].strftime('%Y%m%d') for row in cursor.fetchall()}
        print(f"Found {len(existing_dates)} existing snapshot dates in table")
        
        # List all snapshot CSVs from S3
        csv_keys = list_snapshot_csvs(s3_client, bucket)
        
        if not csv_keys:
            print("⚠ No snapshot CSVs found in S3")
            return {
                'status': 'success',
                'csv_files_loaded': 0,
                'total_rows_loaded': 0
            }
        
        # Filter to only NEW snapshots (not already loaded)
        new_csv_keys = []
        for key in csv_keys:
            # Extract date from filename: snapshots/tenant_status/YYYYMMDD.csv
            filename = key.split('/')[-1]
            snapshot_date = filename.replace('.csv', '')
            if snapshot_date not in existing_dates:
                new_csv_keys.append(key)
        
        if not new_csv_keys:
            print("✓ All snapshots already loaded - nothing new to import")
            return {
                'status': 'success',
                'csv_files_loaded': 0,
                'csv_files_skipped': len(csv_keys),
                'total_rows_loaded': 0
            }
        
        print(f"\nFound {len(new_csv_keys)} NEW snapshots to load (out of {len(csv_keys)} total)")
        
        # Load each NEW CSV
        total_rows = 0
        loaded_files = 0
        failed_files = 0
        
        for i, key in enumerate(new_csv_keys, 1):
            try:
                print(f"[{i}/{len(new_csv_keys)}] Loading {key}...")
                
                rows = download_and_parse_csv(s3_client, bucket, key)
                inserted = bulk_insert_snapshots(connection, cursor, rows)
                
                total_rows += inserted
                loaded_files += 1
                
                if i % 10 == 0 or i == len(new_csv_keys):
                    print(f"  Progress: {i}/{len(new_csv_keys)} files, {total_rows:,} rows")
            
            except Exception as e:
                print(f"  ✗ Failed to load {key}: {str(e)}")
                failed_files += 1
                continue
        
        # Verify
        cursor.execute('SELECT COUNT(*) FROM staging.tenant_daily_snapshots')
        final_count = cursor.fetchone()[0]
        
        cursor.close()
        
        print(f"\n✓ Snapshot load complete:")
        print(f"  - NEW CSV files loaded: {loaded_files}")
        print(f"  - CSV files skipped (already loaded): {len(csv_keys) - len(new_csv_keys)}")
        print(f"  - CSV files failed: {failed_files}")
        print(f"  - NEW rows loaded: {total_rows:,}")
        print(f"  - Final table count: {final_count:,}")
        
        return {
            'status': 'success',
            'csv_files_loaded': loaded_files,
            'csv_files_skipped': len(csv_keys) - len(new_csv_keys),
            'csv_files_failed': failed_files,
            'total_rows_loaded': total_rows
        }
    
    except Exception as e:
        print(f"⚠ Error loading snapshots: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'status': 'failed',
            'error': str(e)
        }


def validate_snapshot_counts(cursor) -> Dict[str, Any]:
    """Validate snapshot data quality."""
    cursor.execute('SELECT COUNT(*) FROM staging.tenant_daily_snapshots')
    total_rows = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(DISTINCT tenant_id) FROM staging.tenant_daily_snapshots')
    unique_tenants = cursor.fetchone()[0]
    
    cursor.execute('SELECT MIN(snapshot_date), MAX(snapshot_date) FROM staging.tenant_daily_snapshots')
    date_range = cursor.fetchone()
    
    return {
        'total_rows': total_rows,
        'unique_tenants': unique_tenants,
        'date_range': date_range
    }


def detect_missing_dates(cursor) -> List[date]:
    """Detect missing snapshot dates."""
    cursor.execute("""
        SELECT DISTINCT snapshot_date 
        FROM staging.tenant_daily_snapshots 
        ORDER BY snapshot_date
    """)
    
    dates = [row[0] for row in cursor.fetchall()]
    
    if not dates:
        return []
    
    missing = []
    current = dates[0]
    
    for next_date in dates[1:]:
        delta = (next_date - current).days
        if delta > 1:
            # Gap detected
            for i in range(1, delta):
                missing.append(current + timedelta(days=i))
        current = next_date
    
    return missing


def validate_no_future_dates(cursor) -> bool:
    """Validate no snapshots have future dates."""
    cursor.execute("""
        SELECT COUNT(*) 
        FROM staging.tenant_daily_snapshots 
        WHERE snapshot_date > CURDATE()
    """)
    future_count = cursor.fetchone()[0]
    
    return future_count == 0


def ensure_occupancy_kpi_table_exists(cursor) -> None:
    """Create gold.occupancy_daily_metrics table if it does not exist."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gold.occupancy_daily_metrics (
            snapshot_date DATE NOT NULL,
            applications INT COMMENT '申込: First appearance of pairs in status 4 or 5',
            new_moveins INT COMMENT '新規入居者: Pairs with move_in_date = snapshot_date',
            new_moveouts INT COMMENT '新規退去者: Pairs with moveout date = snapshot_date',
            occupancy_delta INT COMMENT '稼働室数増減: new_moveins - new_moveouts',
            period_start_rooms INT COMMENT '期首稼働室数: Occupied count on previous day',
            period_end_rooms INT COMMENT '期末稼働室数: period_start + delta',
            occupancy_rate DECIMAL(5,4) COMMENT '稼働率: period_end / 16108',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (snapshot_date),
            INDEX idx_snapshot_date (snapshot_date),
            INDEX idx_occupancy_rate (occupancy_rate)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        COMMENT='Daily occupancy KPI metrics (incremental upsert)'
    """)


def compute_occupancy_kpis_for_dates(cursor, target_dates: List[date]) -> int:
    """
    Compute occupancy KPIs for historical + projected dates.
    Returns number of processed dates.
    """
    if not target_dates:
        return 0

    calendar_today = date.today()
    cursor.execute("""
        SELECT MAX(snapshot_date) AS max_snapshot_date
        FROM silver.tenant_room_snapshot_daily
    """)
    snapshot_meta = cursor.fetchone()
    as_of_snapshot_date = snapshot_meta["max_snapshot_date"] if snapshot_meta else None
    if as_of_snapshot_date is None:
        raise RuntimeError("No data in silver.tenant_room_snapshot_daily; cannot compute occupancy KPIs")

    lag_days = (calendar_today - as_of_snapshot_date).days
    print(
        f"Computing occupancy KPIs for {len(target_dates)} dates "
        f"(calendar_today={calendar_today}, as_of_snapshot={as_of_snapshot_date}, lag={lag_days}d)"
    )

    for target_date in target_dates:
        is_future = target_date > as_of_snapshot_date
        snapshot_date_filter = as_of_snapshot_date if is_future else target_date

        if is_future:
            applications = 0
        else:
            cursor.execute("""
                SELECT COUNT(DISTINCT CONCAT(tenant_id, '-', apartment_id, '-', room_id)) AS count
                FROM (
                    SELECT
                        tenant_id,
                        apartment_id,
                        room_id,
                        MIN(snapshot_date) AS first_appearance
                    FROM silver.tenant_room_snapshot_daily
                    WHERE management_status_code IN (4, 5)
                    GROUP BY tenant_id, apartment_id, room_id
                ) first_apps
                WHERE first_appearance = %s
            """, (target_date,))
            applications = cursor.fetchone()["count"]

        if is_future:
            cursor.execute("""
                SELECT COUNT(DISTINCT CONCAT(tenant_id, '-', apartment_id, '-', room_id)) AS count
                FROM silver.tenant_room_snapshot_daily
                WHERE snapshot_date = %s
                  AND move_in_date = %s
                  AND management_status_code IN (4, 5)
            """, (snapshot_date_filter, target_date))
        else:
            cursor.execute("""
                SELECT COUNT(DISTINCT CONCAT(tenant_id, '-', apartment_id, '-', room_id)) AS count
                FROM silver.tenant_room_snapshot_daily
                WHERE snapshot_date = %s
                  AND move_in_date = %s
                  AND management_status_code IN (4, 5, 6, 7, 9)
            """, (snapshot_date_filter, target_date))
        new_moveins = cursor.fetchone()["count"]

        if is_future:
            cursor.execute("""
                SELECT COUNT(DISTINCT CONCAT(tenant_id, '-', apartment_id, '-', room_id)) AS count
                FROM silver.tenant_room_snapshot_daily
                WHERE snapshot_date = %s
                  AND moveout_date = %s
            """, (snapshot_date_filter, target_date))
        else:
            cursor.execute("""
                SELECT COUNT(DISTINCT CONCAT(tenant_id, '-', apartment_id, '-', room_id)) AS count
                FROM silver.tenant_room_snapshot_daily
                WHERE snapshot_date = %s
                  AND moveout_plans_date = %s
            """, (snapshot_date_filter, target_date))
        new_moveouts = cursor.fetchone()["count"]

        occupancy_delta = new_moveins - new_moveouts

        previous_date = target_date - timedelta(days=1)
        cursor.execute("""
            SELECT COUNT(DISTINCT CONCAT(tenant_id, '-', apartment_id, '-', room_id)) AS count
            FROM silver.tenant_room_snapshot_daily
            WHERE snapshot_date = %s
              AND management_status_code IN (4,5,6,7,9,10,11,12,13,14,15)
        """, (previous_date,))
        period_start_rooms = cursor.fetchone()["count"]
        period_end_rooms = period_start_rooms + occupancy_delta
        occupancy_rate = period_end_rooms / TOTAL_PHYSICAL_ROOMS

        cursor.execute("""
            INSERT INTO gold.occupancy_daily_metrics
            (snapshot_date, applications, new_moveins, new_moveouts,
             occupancy_delta, period_start_rooms, period_end_rooms, occupancy_rate)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                applications = VALUES(applications),
                new_moveins = VALUES(new_moveins),
                new_moveouts = VALUES(new_moveouts),
                occupancy_delta = VALUES(occupancy_delta),
                period_start_rooms = VALUES(period_start_rooms),
                period_end_rooms = VALUES(period_end_rooms),
                occupancy_rate = VALUES(occupancy_rate),
                updated_at = CURRENT_TIMESTAMP
        """, (
            target_date,
            applications,
            new_moveins,
            new_moveouts,
            occupancy_delta,
            period_start_rooms,
            period_end_rooms,
            occupancy_rate,
        ))

        print(
            f"  KPI {target_date}: apps={applications}, moveins={new_moveins}, "
            f"moveouts={new_moveouts}, delta={occupancy_delta:+d}, "
            f"start={period_start_rooms}, end={period_end_rooms}, rate={occupancy_rate:.2%}"
        )

    return len(target_dates)


def update_gold_occupancy_kpis(target_date: date, lookback_days: int, forward_days: int) -> int:
    """Update gold.occupancy_daily_metrics for target +/- windows."""
    print(
        f"\nUpdating gold.occupancy_daily_metrics "
        f"(target_date={target_date}, lookback_days={lookback_days}, forward_days={forward_days})"
    )

    username, password = get_aurora_credentials()
    connection = pymysql.connect(
        host=args['AURORA_ENDPOINT'],
        user=username,
        password=password,
        database=args['AURORA_DATABASE'],
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    cursor = connection.cursor()
    try:
        ensure_occupancy_kpi_table_exists(cursor)
        dates_to_process = [
            target_date + timedelta(days=i)
            for i in range(-lookback_days, forward_days + 1)
        ]
        processed_dates = compute_occupancy_kpis_for_dates(cursor, dates_to_process)
        connection.commit()
        print(f"Updated occupancy KPI rows for {processed_dates} date(s)")
        return processed_dates
    finally:
        cursor.close()
        connection.close()


def log_layer_freshness() -> Dict[str, Any]:
    """Log silver/gold max dates and row counts for post-run verification."""
    username, password = get_aurora_credentials()
    connection = pymysql.connect(
        host=args['AURORA_ENDPOINT'],
        user=username,
        password=password,
        database=args['AURORA_DATABASE'],
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    cursor = connection.cursor()
    try:
        cursor.execute("""
            SELECT
                (SELECT MAX(snapshot_date) FROM silver.tenant_room_snapshot_daily) AS silver_snapshot_max_date,
                (SELECT COUNT(*) FROM silver.tenant_room_snapshot_daily) AS silver_snapshot_rows,
                (SELECT MAX(valid_from) FROM silver.tenant_status_history) AS silver_status_history_max_date,
                (SELECT COUNT(*) FROM silver.tenant_status_history) AS silver_status_history_rows,
                (SELECT MAX(updated_at) FROM gold.occupancy_daily_metrics) AS gold_occupancy_max_updated_at,
                (SELECT MAX(snapshot_date) FROM gold.occupancy_daily_metrics) AS gold_occupancy_max_snapshot_date,
                (SELECT COUNT(*) FROM gold.occupancy_daily_metrics) AS gold_occupancy_rows
        """)
        freshness = cursor.fetchone()
        print("\n=== LAYER FRESHNESS ===")
        print(
            "silver.tenant_room_snapshot_daily: "
            f"max_snapshot_date={freshness['silver_snapshot_max_date']}, "
            f"rows={freshness['silver_snapshot_rows']}"
        )
        print(
            "silver.tenant_status_history: "
            f"max_valid_from={freshness['silver_status_history_max_date']}, "
            f"rows={freshness['silver_status_history_rows']}"
        )
        print(
            "gold.occupancy_daily_metrics: "
            f"max_updated_at_utc={freshness['gold_occupancy_max_updated_at']}, "
            f"max_snapshot_date={freshness['gold_occupancy_max_snapshot_date']}, "
            f"rows={freshness['gold_occupancy_rows']}"
        )
        print("=== END LAYER FRESHNESS ===")
        return freshness
    finally:
        cursor.close()
        connection.close()


def enrich_nationality_data():
    """
    Enrich missing nationality data using AWS Bedrock LLM.
    Targets records with レソト placeholder, NULL, or empty nationality.
    """
    print("\n" + "="*60)
    print("STEP: LLM Nationality Enrichment")
    print("="*60)
    
    try:
        # Download nationality_enricher.py from S3 and add to path
        import os
        import tempfile
        enricher_path = os.path.join(tempfile.gettempdir(), 'nationality_enricher.py')
        s3.download_file(
            args['S3_SOURCE_BUCKET'],
            'glue-scripts/nationality_enricher.py',
            enricher_path
        )
        
        # Add to Python path
        enricher_dir = os.path.dirname(enricher_path)
        if enricher_dir not in sys.path:
            sys.path.insert(0, enricher_dir)
        
        print(f"✓ Downloaded nationality_enricher.py from S3")
        
        # Import enricher
        from nationality_enricher import NationalityEnricher
        
        # Create enricher instance
        enricher = NationalityEnricher(
            aurora_endpoint=args['AURORA_ENDPOINT'],
            aurora_database=args['AURORA_DATABASE'],
            secret_arn=args['AURORA_SECRET_ARN'],
            bedrock_region='us-east-1',
            max_batch_size=1000,  # Process up to 1000 per day
            requests_per_second=5,  # Rate limit for Bedrock API
            dry_run=False
        )
        
        # Run enrichment
        summary = enricher.enrich_all_missing_nationalities()
        
        print(f"✓ Nationality enrichment completed:")
        print(f"  - Tenants identified: {summary['tenants_identified']}")
        print(f"  - Predictions made: {summary['predictions_made']}")
        print(f"  - Successful updates: {summary['successful_updates']}")
        print(f"  - Failed updates: {summary['failed_updates']}")
        print(f"  - Execution time: {summary['execution_time_seconds']:.1f}s")
        
        return summary['successful_updates']
        
    except Exception as e:
        print(f"⚠ Warning: Nationality enrichment failed: {str(e)}")
        print("  (Continuing with ETL - enrichment is non-critical)")
        import traceback
        traceback.print_exc()
        return 0

def archive_processed_dump(s3_key):
    """Move processed dump to archive folder."""
    source_key = s3_key
    dest_key = get_processed_dump_key(source_key)
    
    s3.copy_object(
        Bucket=args['S3_SOURCE_BUCKET'],
        CopySource={'Bucket': args['S3_SOURCE_BUCKET'], 'Key': source_key},
        Key=dest_key
    )
    
    print(f"Archived dump to {dest_key}")

def main():
    """Main ETL workflow."""
    start_time = datetime.now()
    step_timings: Dict[str, Dict[str, Any]] = {}
    
    try:
        # NOTE: Aurora automated backups enabled with 7-day retention for PITR
        # No manual snapshots created to reduce costs (~$57/month savings)
        # Use scripts/rollback_etl.sh if recovery needed
        skip_enrichment = env_bool("DAILY_SKIP_LLM_ENRICHMENT", True)
        skip_table_backups = env_bool("DAILY_SKIP_TABLE_BACKUPS", True)
        run_backup_cleanup = env_bool("DAILY_RUN_BACKUP_CLEANUP", True)
        include_staging_backup_cleanup = env_bool("DAILY_CLEANUP_STAGING_BACKUPS", True)
        run_occupancy_gold_step = runtime_bool("DAILY_RUN_OCCUPANCY_GOLD_STEP", True)
        occupancy_lookback_days = env_int("DAILY_OCCUPANCY_LOOKBACK_DAYS", 3, minimum=0)
        occupancy_forward_days = env_int("DAILY_OCCUPANCY_FORWARD_DAYS", 90, minimum=0)

        # Initialize counters for summary
        table_count = 0
        stmt_count = 0
        dropped_count = 0
        snapshot_exported = 0
        snapshot_rows_loaded = 0
        enriched_count = 0
        backup_count = 0
        removed_backups = 0
        dropped_tmp_tables = 0
        dbt_success = False
        occupancy_rows_processed = 0
        freshness_snapshot: Dict[str, Any] = {}

        # Step 1: Always find and download latest dump
        latest_key = None
        local_path = None
        dump_date = None
        with timed_step("01_find_and_download_dump", step_timings):
            latest_key = get_latest_dump_key()
            dump_date = extract_dump_date_from_key(latest_key)
            if dump_date is not None and "DAILY_TARGET_DATE" not in os.environ:
                os.environ["DAILY_TARGET_DATE"] = dump_date.isoformat()
                print(f"Anchored DAILY_TARGET_DATE to dump date: {dump_date.isoformat()}")
            local_path = download_and_parse_dump(latest_key)

        occupancy_target_date = runtime_date(
            "DAILY_TARGET_DATE",
            dump_date if dump_date is not None else datetime.now().date(),
        )

        # Step 2: Load to Aurora staging
        with timed_step("02_load_dump_to_aurora_staging", step_timings):
            table_count, stmt_count = load_to_aurora_staging(local_path)

        # Step 3: Clean up empty tables
        with timed_step("03_cleanup_empty_staging_tables", step_timings):
            dropped_count = cleanup_empty_staging_tables()

        # Step 4: Export today's tenant snapshot to S3
        with timed_step("04_export_tenant_snapshot_to_s3", step_timings):
            username, password = get_aurora_credentials()
            connection = pymysql.connect(
                host=args['AURORA_ENDPOINT'],
                user=username,
                password=password,
                database=args['AURORA_DATABASE'],
                charset='utf8mb4'
            )
            try:
                snapshot_date = occupancy_target_date
                snapshot_export_result = export_tenant_snapshot_to_s3(
                    connection,
                    s3,
                    args['S3_SOURCE_BUCKET'],
                    snapshot_date
                )
                snapshot_exported = snapshot_export_result.get('rows_exported', 0)
            finally:
                connection.close()

        # Step 5: Load all historical snapshots from S3
        with timed_step("05_load_snapshot_history_from_s3", step_timings):
            username, password = get_aurora_credentials()
            connection = pymysql.connect(
                host=args['AURORA_ENDPOINT'],
                user=username,
                password=password,
                database=args['AURORA_DATABASE'],
                charset='utf8mb4'
            )
            try:
                snapshot_load_result = load_tenant_snapshots_from_s3(
                    connection,
                    s3,
                    args['S3_SOURCE_BUCKET']
                )
                snapshot_rows_loaded = snapshot_load_result.get('total_rows_loaded', 0)
            finally:
                connection.close()

        # Step 6: Enrich nationality data using LLM (レソト and missing values)
        if skip_enrichment:
            print("\nSkipping LLM enrichment (DAILY_SKIP_LLM_ENRICHMENT=true)")
        else:
            with timed_step("06_llm_nationality_enrichment", step_timings):
                enriched_count = enrich_nationality_data()

        # Step 7: Create backups before dbt transformations
        if skip_table_backups:
            print("\nSkipping table backups (DAILY_SKIP_TABLE_BACKUPS=true)")
        else:
            with timed_step("07_create_pre_etl_backups", step_timings):
                backup_count = create_pre_etl_backups()

        # Step 8: Clean up old backups (keep last 3 days)
        if run_backup_cleanup:
            with timed_step("08_cleanup_old_backups", step_timings):
                removed_backups = cleanup_old_backups(
                    days_to_keep=3,
                    include_staging=include_staging_backup_cleanup
                )
        else:
            print("\nSkipping backup cleanup (DAILY_RUN_BACKUP_CLEANUP=false)")

        # Step 8.5: Clean up dbt temp tables (prevent failures)
        with timed_step("08_5_cleanup_dbt_tmp_tables", step_timings):
            dropped_tmp_tables = cleanup_dbt_tmp_tables()

        # Step 9: Run dbt transformations (silver + dbt gold)
        with timed_step("09_run_dbt_transformations", step_timings):
            dbt_success = run_dbt_transformations()

        # Step 9.5: Update gold occupancy KPI table
        if run_occupancy_gold_step:
            with timed_step("09_5_update_gold_occupancy_metrics", step_timings):
                occupancy_rows_processed = update_gold_occupancy_kpis(
                    target_date=occupancy_target_date,
                    lookback_days=occupancy_lookback_days,
                    forward_days=occupancy_forward_days
                )
        else:
            print("\nSkipping occupancy KPI update (DAILY_RUN_OCCUPANCY_GOLD_STEP=false)")

        # Step 9.6: Log silver/gold freshness after transformations
        with timed_step("09_6_log_layer_freshness", step_timings):
            freshness_snapshot = log_layer_freshness()

        # Step 10: Archive processed dump (archive only; not used for run decisions)
        with timed_step("10_archive_processed_dump", step_timings):
            archive_processed_dump(latest_key)
        
        # Calculate duration
        duration = (datetime.now() - start_time).total_seconds()
        
        # Log success
        print(f"\n{'='*60}")
        print(f"ETL Job Completed Successfully")
        print(f"Duration: {duration:.2f} seconds")
        print(f"Tables loaded: {table_count}")
        print(f"Empty tables dropped: {dropped_count}")
        print(f"Snapshot exported: {snapshot_exported} tenants")
        print(f"Historical snapshots loaded: {snapshot_rows_loaded:,} rows")
        print(f"Nationalities enriched: {enriched_count}")
        print(f"Pre-ETL backups created: {backup_count}")
        print(f"Old backups removed: {removed_backups}")
        print(f"dbt temp tables dropped: {dropped_tmp_tables}")
        print(f"SQL statements executed: {stmt_count}")
        print(f"dbt transformations: {'Success' if dbt_success else 'Failed'}")
        print(f"Gold occupancy KPI dates processed: {occupancy_rows_processed}")
        if freshness_snapshot:
            print(
                "Layer freshness max dates: "
                f"silver_snapshot={freshness_snapshot.get('silver_snapshot_max_date')}, "
                f"silver_status_history={freshness_snapshot.get('silver_status_history_max_date')}, "
                f"gold_occupancy={freshness_snapshot.get('gold_occupancy_max_date')}"
            )
        print(f"{'='*60}\n")
        print(f"Tenant Status History:")
        print(f"  • Today's snapshot: {snapshot_exported} tenants exported to S3")
        print(f"  • Historical data: {snapshot_rows_loaded:,} snapshot rows loaded")
        print(f"  • Wipe-resilient: Full history rebuilt from S3 on every run")
        print(f"Data Quality:")
        print(f"  • LLM nationality enrichment: {enriched_count} records updated")
        print(f"  • Model: Claude 3 Haiku (Bedrock)")
        print(f"Data Protection:")
        print(f"  • S3 snapshots: Daily tenant status backups (unlimited retention)")
        print(f"  • Table-level backups: {backup_count} created (3-day retention)")
        print(f"  • Aurora PITR: 7-day retention for cluster-level recovery")
        print(f"  • Recovery guide: docs/DATA_PROTECTION_STRATEGY.md")
        print_step_timing_summary(step_timings)
        
        job.commit()
        
    except Exception as e:
        print(f"\nERROR: ETL job failed: {str(e)}")
        import traceback
        traceback.print_exc()
        print_step_timing_summary(step_timings)
        job.commit()
        raise

if __name__ == "__main__":
    main()
