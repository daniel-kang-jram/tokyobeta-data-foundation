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
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import datetime, timedelta, date, timezone
from botocore.exceptions import ClientError
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
TOKYO_TIMEZONE = timezone(timedelta(hours=9))
_AURORA_CREDENTIALS = None
LEGACY_VALID_OVERRIDE_START = date(2026, 2, 4)
LEGACY_VALID_OVERRIDE_END = date(2026, 2, 10)
CORRUPTED_GAP_START = date(2026, 2, 11)
CORRUPTED_GAP_END = date(2026, 2, 18)
VALID_GEO_LAT_MIN = 35.0
VALID_GEO_LAT_MAX = 36.0
VALID_GEO_LON_MIN = 139.0
VALID_GEO_LON_MAX = 140.5
DEFAULT_PROPERTY_GEO_BACKUP_PREFIX = "reference/property_geo_latlon"
STAGING_PERSISTENT_TABLES = {
    "llm_enrichment_cache",
    "llm_property_municipality_cache",
    "property_geo_latlon_backup",
}
REQUIRED_STAGING_TABLES = {
    "tenants",
    "movings",
    "apartments",
    "rooms",
    "llm_enrichment_cache",
    "property_geo_latlon_backup",
}

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


def runtime_int(name: str, default: int, minimum: int = 0) -> int:
    """Read integer runtime setting from env/argv, applying minimum bound."""
    if name in os.environ:
        return env_int(name, default, minimum=minimum)

    arg_val = optional_argv_value(name)
    if arg_val is None:
        return default
    try:
        value = int(arg_val.strip())
    except ValueError:
        return default
    return value if value >= minimum else minimum


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


def runtime_optional_date(name: str) -> date | None:
    """Read YYYY-MM-DD runtime date from env/argv, else return None."""
    raw = os.environ.get(name)
    if raw is None:
        raw = optional_argv_value(name)
    if raw is None:
        return None
    try:
        return datetime.strptime(raw.strip(), "%Y-%m-%d").date()
    except ValueError:
        print(f"Invalid {name}={raw!r}; ignoring override")
        return None


def get_artifact_release() -> str | None:
    """
    Resolve artifact release SHA/version from runtime args.
    Priority:
      1) --ARTIFACT_RELEASE
      2) Parse from --DBT_PROJECT_PATH (.../releases/<sha>/)
    """
    explicit = optional_argv_value("ARTIFACT_RELEASE")
    if explicit:
        value = explicit.strip()
        if value:
            return value

    dbt_project_path = str(args.get("DBT_PROJECT_PATH") or "").strip()
    match = re.search(r"/releases/([^/]+)(?:/|$)", dbt_project_path)
    if match:
        return match.group(1)
    return None


def get_nationality_enricher_s3_keys() -> List[str]:
    """Build ordered candidate S3 keys for nationality_enricher.py."""
    keys: List[str] = []
    artifact_release = get_artifact_release()
    if artifact_release:
        keys.append(f"glue-scripts/releases/{artifact_release}/nationality_enricher.py")

    # Backward-compatible fallback for legacy unversioned deployments.
    keys.append("glue-scripts/nationality_enricher.py")

    # Deduplicate while preserving order.
    return list(dict.fromkeys(keys))


def download_nationality_enricher_script(local_path: str | None = None) -> Tuple[str, str]:
    """
    Download nationality_enricher.py from S3 using release-aware path first.

    Returns:
        Tuple of (downloaded_local_path, selected_s3_key)
    """
    import tempfile

    target_path = local_path or os.path.join(tempfile.gettempdir(), "nationality_enricher.py")
    bucket = args["S3_SOURCE_BUCKET"]
    attempted: List[str] = []

    for s3_key in get_nationality_enricher_s3_keys():
        attempted.append(s3_key)
        try:
            s3.download_file(bucket, s3_key, target_path)
            return target_path, s3_key
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code in {"NoSuchKey", "404", "NotFound"}:
                print(f"Nationality enricher not found at s3://{bucket}/{s3_key}; trying fallback")
                continue
            raise

    attempted_str = ", ".join(attempted)
    raise FileNotFoundError(
        f"Could not download nationality_enricher.py from any candidate key in bucket={bucket}: "
        f"{attempted_str}"
    )


def default_skip_llm_enrichment(environment: str | None) -> bool:
    """Default enrichment policy: enabled in prod, disabled elsewhere."""
    return str(environment or "").strip().lower() != "prod"


def resolve_llm_runtime_settings() -> Dict[str, Any]:
    """Resolve all LLM runtime settings from env/argv with safe defaults."""
    skip_enrichment = runtime_bool(
        "DAILY_SKIP_LLM_ENRICHMENT",
        default_skip_llm_enrichment(args.get("ENVIRONMENT")),
    )
    return {
        "skip_enrichment": skip_enrichment,
        "nationality_max_batch": runtime_int(
            "DAILY_LLM_NATIONALITY_MAX_BATCH",
            300,
            minimum=1,
        ),
        "municipality_max_batch": runtime_int(
            "DAILY_LLM_MUNICIPALITY_MAX_BATCH",
            150,
            minimum=0,
        ),
        "requests_per_second": runtime_int(
            "DAILY_LLM_REQUESTS_PER_SECOND",
            3,
            minimum=1,
        ),
        "fail_on_error": runtime_bool("DAILY_LLM_FAIL_ON_ERROR", False),
    }


def normalize_statement(stmt: str) -> str:
    """Normalize SQL statement and skip session-level commands."""
    stmt = stmt.strip()
    if not stmt:
        return ""
    if re.match(r"^SET", stmt, re.IGNORECASE):
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
    tables_to_keep = [
        table_name for table_name in existing_tables
        if table_name in STAGING_PERSISTENT_TABLES
    ]
    tables_to_drop = [
        table_name for table_name in existing_tables
        if table_name not in STAGING_PERSISTENT_TABLES
    ]

    if not tables_to_drop:
        print("No existing staging tables - clean load")
        return 0

    print(f"Dropping {len(tables_to_drop)} existing staging tables before load")
    if tables_to_keep:
        print(
            "Preserving persistent staging tables: "
            + ", ".join(sorted(tables_to_keep))
        )
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
    try:
        for table_name in tables_to_drop:
            cursor.execute(f"DROP TABLE IF EXISTS `staging`.`{table_name}`")
    finally:
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")

    return len(tables_to_drop)


def _extract_first_value(row: Any) -> Any:
    """Extract first scalar from tuple/dict row for cursor portability."""
    if row is None:
        return None
    if isinstance(row, dict):
        values = list(row.values())
        return values[0] if values else None
    if isinstance(row, (list, tuple)):
        return row[0] if row else None
    return row


def ensure_llm_enrichment_cache_table(cursor) -> None:
    """Ensure persistent LLM cache table exists in staging schema."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS `staging`.`llm_enrichment_cache` (
            `tenant_id` BIGINT NOT NULL,
            `full_name` VARCHAR(255) NULL,
            `full_name_hash` CHAR(64) NULL,
            `llm_nationality` VARCHAR(255) NULL,
            `llm_confidence` DECIMAL(6,5) NULL,
            `enriched_at` DATETIME NULL,
            `model_version` VARCHAR(128) NULL,
            `created_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP
                ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`tenant_id`),
            KEY `idx_llm_enriched_at` (`enriched_at`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )


def assert_llm_enrichment_cache_table_exists(cursor) -> None:
    """Fail fast if mandatory persistent LLM cache table is missing."""
    assert_required_staging_tables_exist(cursor, {"llm_enrichment_cache"})


def ensure_property_geo_latlon_backup_table(cursor) -> None:
    """Ensure persistent property geolocation backup table exists in staging schema."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS `staging`.`property_geo_latlon_backup` (
            `apartment_id` BIGINT NOT NULL,
            `asset_id_hj` VARCHAR(255) NULL,
            `apartment_name` VARCHAR(255) NULL,
            `full_address` VARCHAR(1024) NULL,
            `prefecture` VARCHAR(128) NULL,
            `municipality` VARCHAR(128) NULL,
            `latitude` DECIMAL(11,8) NOT NULL,
            `longitude` DECIMAL(11,8) NOT NULL,
            `source_updated_at` DATETIME NULL,
            `source_table` VARCHAR(64) NOT NULL DEFAULT 'staging.apartments',
            `created_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP
                ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`apartment_id`),
            KEY `idx_property_geo_coords` (`latitude`, `longitude`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )


def upsert_property_geo_latlon_backup(cursor) -> int:
    """Upsert valid geolocation rows from staging.apartments into persistent backup table."""
    cursor.execute(
        f"""
        INSERT INTO `staging`.`property_geo_latlon_backup` (
            `apartment_id`,
            `asset_id_hj`,
            `apartment_name`,
            `full_address`,
            `prefecture`,
            `municipality`,
            `latitude`,
            `longitude`,
            `source_updated_at`,
            `source_table`
        )
        SELECT
            a.`id`,
            a.`unique_number`,
            a.`apartment_name`,
            a.`full_address`,
            a.`prefecture`,
            a.`municipality`,
            a.`latitude`,
            a.`longitude`,
            a.`updated_at`,
            'staging.apartments'
        FROM `staging`.`apartments` a
        WHERE a.`id` IS NOT NULL
          AND a.`latitude` BETWEEN {VALID_GEO_LAT_MIN} AND {VALID_GEO_LAT_MAX}
          AND a.`longitude` BETWEEN {VALID_GEO_LON_MIN} AND {VALID_GEO_LON_MAX}
        ON DUPLICATE KEY UPDATE
            `asset_id_hj` = VALUES(`asset_id_hj`),
            `apartment_name` = VALUES(`apartment_name`),
            `full_address` = VALUES(`full_address`),
            `prefecture` = VALUES(`prefecture`),
            `municipality` = VALUES(`municipality`),
            `latitude` = VALUES(`latitude`),
            `longitude` = VALUES(`longitude`),
            `source_updated_at` = VALUES(`source_updated_at`),
            `source_table` = VALUES(`source_table`)
        """
    )
    return int(cursor.rowcount or 0)


def query_property_geo_latlon_backup_rows(cursor) -> List[Tuple]:
    """Fetch persisted property geolocation backup rows for S3 export."""
    cursor.execute(
        """
        SELECT
            `apartment_id`,
            `asset_id_hj`,
            `apartment_name`,
            `full_address`,
            `prefecture`,
            `municipality`,
            `latitude`,
            `longitude`,
            DATE_FORMAT(`source_updated_at`, '%Y-%m-%d %H:%i:%s') AS source_updated_at
        FROM `staging`.`property_geo_latlon_backup`
        ORDER BY `apartment_id`
        """
    )
    return cursor.fetchall()


def generate_property_geo_backup_csv(rows: List[Tuple]) -> str:
    """Generate CSV payload for property lat/lon backup rows."""
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "apartment_id",
        "asset_id_hj",
        "apartment_name",
        "full_address",
        "prefecture",
        "municipality",
        "latitude",
        "longitude",
        "source_updated_at",
    ])

    for row in rows:
        if isinstance(row, dict):
            writer.writerow([
                row.get("apartment_id"),
                row.get("asset_id_hj"),
                row.get("apartment_name"),
                row.get("full_address"),
                row.get("prefecture"),
                row.get("municipality"),
                row.get("latitude"),
                row.get("longitude"),
                row.get("source_updated_at"),
            ])
        else:
            writer.writerow(row)
    return output.getvalue()


def get_property_geo_backup_prefix() -> str:
    """Resolve S3 prefix for property geolocation backup artifacts."""
    prefix = (
        os.environ.get("DAILY_PROPERTY_GEO_BACKUP_PREFIX")
        or optional_argv_value("DAILY_PROPERTY_GEO_BACKUP_PREFIX")
        or DEFAULT_PROPERTY_GEO_BACKUP_PREFIX
    )
    return prefix.rstrip("/")


def upload_property_geo_backup_csv(
    s3_client,
    bucket: str,
    csv_content: str,
    snapshot_date: date,
) -> Dict[str, Any]:
    """Upload property geolocation backup CSV to both dated and latest keys."""
    date_str = snapshot_date.strftime("%Y%m%d")
    prefix = get_property_geo_backup_prefix()
    dated_key = f"{prefix}/dt={date_str}/property_geo_latlon_backup.csv"
    latest_key = f"{prefix}/latest/property_geo_latlon_backup.csv"
    body = csv_content.encode("utf-8")

    for key in (dated_key, latest_key):
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType="text/csv",
        )

    return {
        "dated_key": dated_key,
        "latest_key": latest_key,
        "bytes_uploaded": len(body),
    }


def sync_property_geo_latlon_backup_to_s3(
    connection,
    s3_client,
    bucket: str,
    snapshot_date: date,
) -> Dict[str, Any]:
    """
    Persist valid apartment geolocation rows and export complete backup CSV to S3.

    Returns:
        Dict with upsert count, total backup rows, and uploaded S3 keys.
    """
    cursor = connection.cursor()
    try:
        ensure_property_geo_latlon_backup_table(cursor)
        upserted_rows = upsert_property_geo_latlon_backup(cursor)
        connection.commit()

        cursor.execute("SELECT COUNT(*) FROM `staging`.`property_geo_latlon_backup`")
        total_rows = int(_extract_first_value(cursor.fetchone()) or 0)
        rows = query_property_geo_latlon_backup_rows(cursor)
        csv_content = generate_property_geo_backup_csv(rows)
        upload_result = upload_property_geo_backup_csv(
            s3_client=s3_client,
            bucket=bucket,
            csv_content=csv_content,
            snapshot_date=snapshot_date,
        )

        return {
            "upserted_rows": upserted_rows,
            "total_rows": total_rows,
            "dated_key": upload_result["dated_key"],
            "latest_key": upload_result["latest_key"],
            "bytes_uploaded": upload_result["bytes_uploaded"],
        }
    finally:
        cursor.close()


def assert_required_staging_tables_exist(
    cursor,
    required_tables: set[str] | None = None,
) -> None:
    """Fail fast if required staging tables are missing after dump load."""
    required = set(required_tables or REQUIRED_STAGING_TABLES)
    required_sql = ", ".join(f"'{name}'" for name in sorted(required))
    cursor.execute(
        f"""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'staging'
          AND table_name IN ({required_sql})
        """
    )
    rows = cursor.fetchall()
    existing = {str(_extract_first_value(row)) for row in rows}
    missing = sorted(required - existing)
    if missing:
        missing_labels = ", ".join(f"staging.{name}" for name in missing)
        raise RuntimeError(
            f"Mandatory staging table(s) missing after load: {missing_labels}"
        )


def get_staging_table_row_count(table_name: str) -> int:
    """Return row count for a staging table."""
    connection = create_aurora_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM `staging`.`{table_name}`")
        row = cursor.fetchone()
        value = _extract_first_value(row)
        return int(value or 0)
    finally:
        connection.close()


def get_dump_manifest_key(dump_date: date) -> str:
    """Build manifest key for a dump date."""
    prefix = (
        os.environ.get("DAILY_DUMP_MANIFEST_PREFIX")
        or optional_argv_value("DAILY_DUMP_MANIFEST_PREFIX")
        or "dumps-manifest/"
    )
    clean_prefix = prefix.rstrip("/")
    return f"{clean_prefix}/gghouse_{dump_date.strftime('%Y%m%d')}.json"


def load_dump_manifest(dump_date: date) -> dict | None:
    """Load per-date dump manifest from S3."""
    manifest_key = get_dump_manifest_key(dump_date)
    try:
        response = s3.get_object(
            Bucket=args['S3_SOURCE_BUCKET'],
            Key=manifest_key,
        )
    except ClientError as err:
        code = str(err.response.get("Error", {}).get("Code", ""))
        if code in {"NoSuchKey", "404", "NotFound"}:
            return None
        raise

    body = response["Body"].read().decode("utf-8")
    return json.loads(body)


def manifest_is_valid_for_etl(manifest: dict | None) -> bool:
    """Manifest flag gate for ETL eligibility."""
    if not isinstance(manifest, dict):
        return False
    if "valid_for_etl" in manifest:
        return bool(manifest["valid_for_etl"])
    if "source_valid" in manifest:
        return bool(manifest["source_valid"])
    return False


def parse_manifest_datetime(raw_value: str) -> datetime | None:
    """Parse ISO8601-ish timestamp from manifest."""
    if not raw_value:
        return None
    candidate = raw_value.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(TOKYO_TIMEZONE)


def extract_manifest_max_source_date(manifest: dict) -> date | None:
    """Extract latest source date from table-level source freshness map."""
    table_map = (
        manifest.get("max_updated_at_by_table")
        if isinstance(manifest.get("max_updated_at_by_table"), dict)
        else manifest.get("source_table_max_updated_at")
    )
    if not isinstance(table_map, dict):
        return None

    parsed_dates: list[date] = []
    for value in table_map.values():
        if not isinstance(value, str):
            continue
        parsed = parse_manifest_datetime(value)
        if parsed is None:
            continue
        parsed_dates.append(parsed.date())

    if not parsed_dates:
        return None
    return max(parsed_dates)


def validate_dump_manifest(
    manifest: dict,
    expected_date: date,
    max_source_stale_days: int,
) -> None:
    """Validate dump manifest source identity and freshness contract."""
    if not manifest_is_valid_for_etl(manifest):
        raise ValueError(
            "Manifest validity check failed: valid_for_etl/source_valid is not true."
        )

    source_host = str(manifest.get("source_host", "")).strip()
    source_database = str(manifest.get("source_database", "")).strip()
    if not source_host or not source_database:
        raise ValueError(
            "Manifest source contract failed: source_host/source_database must be non-empty."
        )

    max_source_date = extract_manifest_max_source_date(manifest)
    if max_source_date is None:
        raise ValueError(
            "Manifest source freshness check failed: max_updated_at_by_table/source_table_max_updated_at missing or invalid."
        )

    stale_days = (expected_date - max_source_date).days
    if stale_days > max_source_stale_days:
        raise ValueError(
            "Manifest source freshness check failed: "
            f"source max date={max_source_date} is {stale_days} day(s) "
            f"behind expected date={expected_date} "
            f"(max allowed={max_source_stale_days})."
        )

    print(
        "Manifest validated: "
        f"host={source_host}, database={source_database}, "
        f"source_max_date={max_source_date}, stale_days={stale_days}"
    )


def classify_manifest_status(manifest: dict | None) -> tuple[str, str | None]:
    """Classify manifest into ETL-valid or gap status."""
    if manifest is None:
        return "invalid_or_missing", "manifest_missing"

    if manifest_is_valid_for_etl(manifest):
        return "valid", None

    reason = str(manifest.get("reason", "")).strip()
    if not reason:
        reason = "manifest_invalid"
    return "invalid_or_missing", reason


def build_data_quality_calendar_entries(
    expected_date: date,
    lookback_days: int,
) -> list[dict[str, Any]]:
    """Build data-quality calendar rows from per-day manifest validity."""
    rows: list[dict[str, Any]] = []

    for offset in range(lookback_days + 1):
        target_date = expected_date - timedelta(days=offset)
        manifest = load_dump_manifest(target_date)
        status, reason = classify_manifest_status(manifest)

        source_host = ""
        source_database = ""
        if isinstance(manifest, dict):
            source_host = str(manifest.get("source_host", "")).strip()
            source_database = str(manifest.get("source_database", "")).strip()

        rows.append(
            {
                "check_date": target_date,
                "dump_status": status,
                "reason": reason,
                "source_host": source_host,
                "source_database": source_database,
                "manifest_key": get_dump_manifest_key(target_date),
                "is_gap": 0 if status == "valid" else 1,
            }
        )

    return rows


def build_manual_quality_calendar_overrides() -> list[dict[str, Any]]:
    """Build hard overrides for known-valid and quarantined historical dates."""
    rows: list[dict[str, Any]] = []

    current = LEGACY_VALID_OVERRIDE_START
    while current <= LEGACY_VALID_OVERRIDE_END:
        rows.append(
            {
                "check_date": current,
                "dump_status": "valid",
                "reason": "manual_valid_override_pre_gap",
                "source_host": "",
                "source_database": "",
                "manifest_key": get_dump_manifest_key(current),
                "is_gap": 0,
            }
        )
        current += timedelta(days=1)

    current = CORRUPTED_GAP_START
    while current <= CORRUPTED_GAP_END:
        rows.append(
            {
                "check_date": current,
                "dump_status": "invalid_or_missing",
                "reason": "corrupted_snapshot_window",
                "source_host": "",
                "source_database": "",
                "manifest_key": get_dump_manifest_key(current),
                "is_gap": 1,
            }
        )
        current += timedelta(days=1)

    return rows


def ensure_data_quality_calendar_table_exists(cursor) -> None:
    """Create gold.data_quality_calendar table if missing."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gold.data_quality_calendar (
            check_date DATE NOT NULL,
            dump_status VARCHAR(32) NOT NULL,
            reason VARCHAR(255),
            source_host VARCHAR(255),
            source_database VARCHAR(128),
            manifest_key VARCHAR(255) NOT NULL,
            is_gap TINYINT(1) NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (check_date),
            INDEX idx_dump_status (dump_status),
            INDEX idx_is_gap (is_gap)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        COMMENT='Calendar of valid vs invalid/missing dump dates for downstream filtering'
    """)


def upsert_data_quality_calendar_entries(
    cursor,
    rows: list[dict[str, Any]],
) -> int:
    """Upsert data-quality calendar rows into gold schema."""
    if not rows:
        return 0

    payload = [
        (
            row["check_date"],
            row["dump_status"],
            row["reason"],
            row["source_host"],
            row["source_database"],
            row["manifest_key"],
            row["is_gap"],
        )
        for row in rows
    ]

    cursor.executemany(
        """
        INSERT INTO gold.data_quality_calendar (
            check_date,
            dump_status,
            reason,
            source_host,
            source_database,
            manifest_key,
            is_gap
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            dump_status = VALUES(dump_status),
            reason = VALUES(reason),
            source_host = VALUES(source_host),
            source_database = VALUES(source_database),
            manifest_key = VALUES(manifest_key),
            is_gap = VALUES(is_gap),
            updated_at = CURRENT_TIMESTAMP
        """,
        payload,
    )
    return len(payload)


def get_gap_dates_for_window(cursor, start_date: date, end_date: date) -> List[date]:
    """Return gap dates from data quality calendar within inclusive bounds."""
    if start_date > end_date:
        return []

    cursor.execute(
        """
        SELECT check_date
        FROM gold.data_quality_calendar
        WHERE is_gap = 1
          AND check_date BETWEEN %s AND %s
        ORDER BY check_date
        """,
        (start_date, end_date),
    )
    try:
        rows = cursor.fetchall()
    except TypeError:
        return []
    if rows is None:
        return []

    try:
        return [
            dt for dt in (_row_date_value(row, "check_date") for row in rows)
            if dt is not None
        ]
    except TypeError:
        return []


def purge_gold_occupancy_gap_rows(
    cursor,
    start_date: date,
    end_date: date,
) -> int:
    """Delete existing occupancy rows for gap dates in the requested window.

    Keeping these rows from previous successful runs would reintroduce corrupted
    intervals even when the occupancy calculation skips gap days.
    """
    if start_date > end_date:
        return 0

    try:
        cursor.execute(
            """
            DELETE g
            FROM gold.occupancy_daily_metrics g
            INNER JOIN gold.data_quality_calendar c
              ON c.check_date = g.snapshot_date
             AND c.is_gap = 1
            WHERE c.check_date BETWEEN %s AND %s
            """,
            (start_date, end_date),
        )
    except Exception as exc:
        # If the data-quality calendar has not been provisioned yet, do not
        # block the run. The caller may still proceed and re-emit fresh rows.
        if "doesn't exist" in str(exc).lower() or "not found" in str(exc).lower():
            print(f"WARN: skipping gap-row purge because data quality calendar unavailable: {exc}")
            return 0
        raise

    deleted_rows = cursor.rowcount or 0
    if deleted_rows:
        print(
            f"Removed {deleted_rows} pre-existing gold occupancy rows "
            f"for data-quality gaps in {start_date}..{end_date}"
        )
    return int(deleted_rows)


def get_latest_dump_key_with_manifest(
    dump_candidates: list[dict] | None = None,
    require_manifest: bool = False,
    expected_date: date | None = None,
    max_source_stale_days: int = 14,
):
    """Find the most recent SQL dump key, optionally requiring a valid manifest."""
    if dump_candidates is None:
        dump_candidates = list_dump_candidates()

    if not dump_candidates:
        raise ValueError("No SQL dump files matching pattern gghouse_YYYYMMDD.sql found")

    if not require_manifest:
        latest_key = dump_candidates[0]['Key']
        print(
            f"Latest dump: {latest_key} (modified: "
            f"{dump_candidates[0].get('LastModified')})"
        )
        return latest_key

    manifest_expected_date = expected_date or tokyo_today()
    rejected_reasons: list[str] = []

    for candidate in dump_candidates:
        candidate_key = candidate['Key']
        candidate_date = extract_dump_date_from_key(candidate_key)
        if candidate_date is None:
            rejected_reasons.append(f"{candidate_key}:unparseable_date")
            continue

        try:
            manifest = load_dump_manifest(candidate_date)
        except Exception as err:
            rejected_reasons.append(
                f"{candidate_key}:manifest_load_error:{type(err).__name__}:{str(err)}"
            )
            continue

        if manifest is None:
            rejected_reasons.append(f"{candidate_key}:manifest_missing")
            continue

        try:
            validate_dump_manifest(
                manifest=manifest,
                expected_date=manifest_expected_date,
                max_source_stale_days=max_source_stale_days,
            )
        except ValueError as err:
            rejected_reasons.append(f"{candidate_key}:{str(err)}")
            continue

        print(
            f"Latest manifest-valid dump: {candidate_key} "
            f"(modified: {candidate.get('LastModified')})"
        )
        return candidate_key

    reason_text = "; ".join(rejected_reasons[-10:]) if rejected_reasons else "no_candidates"
    raise ValueError(f"No manifest-valid SQL dump files available. rejected={reason_text}")


def get_latest_dump_key(
    dump_candidates: list[dict] | None = None,
    require_manifest: bool = False,
    expected_date: date | None = None,
    max_source_stale_days: int = 14,
):
    """Find latest dump key with optional manifest validation gate."""
    return get_latest_dump_key_with_manifest(
        dump_candidates=dump_candidates,
        require_manifest=require_manifest,
        expected_date=expected_date,
        max_source_stale_days=max_source_stale_days,
    )


def list_dump_candidates() -> list[dict]:
    """List and sort S3 dump candidates from the configured prefix."""
    response = s3.list_objects_v2(
        Bucket=args['S3_SOURCE_BUCKET'],
        Prefix=args['S3_SOURCE_PREFIX']
    )
    
    if 'Contents' not in response:
        raise ValueError(f"No files found in s3://{args['S3_SOURCE_BUCKET']}/{args['S3_SOURCE_PREFIX']}")
    
    files = sorted(response['Contents'], key=lambda x: x['LastModified'], reverse=True)
    sql_files = [
        f for f in files
        if extract_dump_date_from_key(f['Key']) is not None and f.get('Key')
    ]
    
    return sql_files


def get_dump_dates(dump_candidates: list[dict]) -> set[date]:
    """Extract all dump dates from a list of candidate dump objects."""
    return {
        extract_dump_date_from_key(item['Key'])
        for item in dump_candidates
        if item.get('Key') and extract_dump_date_from_key(item['Key']) is not None
    }


def validate_dump_continuity(
    available_dump_dates: set[date],
    expected_date: date,
    max_stale_days: int
) -> None:
    """
    Ensure there are dumps for the required recency window.

    Required window is every date from expected_date down to:
    expected_date - max_stale_days.
    """
    missing_dates = []
    for offset in range(max_stale_days + 1):
        candidate = expected_date - timedelta(days=offset)
        if candidate not in available_dump_dates:
            missing_dates.append(candidate)

    if missing_dates:
        formatted_missing = ", ".join(d.isoformat() for d in missing_dates)
        raise ValueError(
            "Dump continuity check failed: missing dump file(s) for date(s): "
            f"{formatted_missing}"
        )


def check_dump_continuity(
    available_dump_dates: set[date],
    expected_date: date,
    max_stale_days: int,
    strict: bool,
) -> list[date]:
    """
    Continuity check with optional "warn only" mode.

    Args:
        available_dump_dates: Dump dates present in S3.
        expected_date: The date the ETL expects to process.
        max_stale_days: How far back we require a continuous window.
        strict: If True, raise on gaps. If False, print a warning and continue.

    Returns:
        List of missing dates (empty if continuous).
    """
    missing_dates: list[date] = []
    for offset in range(max_stale_days + 1):
        candidate = expected_date - timedelta(days=offset)
        if candidate not in available_dump_dates:
            missing_dates.append(candidate)

    if missing_dates:
        formatted_missing = ", ".join(d.isoformat() for d in missing_dates)
        msg = (
            "Dump continuity check failed: missing dump file(s) for date(s): "
            f"{formatted_missing}"
        )
        if strict:
            raise ValueError(msg)
        print(f"WARN: {msg} (strict mode disabled; continuing)")

    return missing_dates


def validate_dump_freshness(
    latest_key: str,
    latest_dump_date: date | None,
    expected_date: date,
    max_stale_days: int
) -> None:
    """
    Ensure the latest dump is recent enough for expected processing date.

    This blocks the ETL if the dump stream silently skipped days, preventing
    false-confidence runs when upstream dump generation is delayed or missing.
    """
    if latest_dump_date is None:
        raise ValueError(
            f"Could not extract date from latest dump key: {latest_key}"
        )

    stale_days = (expected_date - latest_dump_date).days
    if stale_days < 0:
        raise ValueError(
            "Dump freshness check failed: "
            f"latest dump date={latest_dump_date} is in the future "
            f"relative to expected_date={expected_date}."
        )

    if stale_days > max_stale_days:
        raise ValueError(
            "Dump freshness check failed: "
            f"latest dump date={latest_dump_date} is {stale_days} day(s) "
            f"older than expected_date={expected_date} "
            f"(max allowed age={max_stale_days})."
        )

    if stale_days == 0:
        print("Latest dump date matches expected date.")
    else:
        print(
            f"Latest dump is {stale_days} day(s) behind expected date "
            f"({latest_dump_date} vs {expected_date}) but within tolerance."
        )


def tokyo_today() -> date:
    """Current date in Tokyo local time."""
    return datetime.now(TOKYO_TIMEZONE).date()


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


def get_aurora_credentials(
    secret_client=None,
    secret_arn: str | None = None,
):
    """Retrieve Aurora credentials from Secrets Manager.

    Some environments intermittently return non-standard secret payload shapes or stale
    secret versions with missing credentials; this helper validates and returns the first
    non-empty username/password pair from current then previous version.
    """
    global _AURORA_CREDENTIALS
    if _AURORA_CREDENTIALS is not None:
        return _AURORA_CREDENTIALS

    client = secret_client or secretsmanager
    resolved_secret_arn = secret_arn or args['AURORA_SECRET_ARN']
    last_error = None
    version_stages = [None, "AWSCURRENT", "AWSPREVIOUS"]

    for version_stage in version_stages:
        if version_stage is None:
            request_kwargs = {"SecretId": resolved_secret_arn}
        else:
            request_kwargs = {
                "SecretId": resolved_secret_arn,
                "VersionStage": version_stage,
            }

        try:
            response = client.get_secret_value(**request_kwargs)
        except Exception as exc:
            if version_stage is None:
                # If no explicit stage works, still try stage-aware retrieval.
                last_error = exc
                continue
            last_error = exc
            continue

        secret_string = response.get("SecretString")
        if secret_string is None:
            secret_binary = response.get("SecretBinary")
            if not secret_binary:
                continue
            secret_string = base64.b64decode(secret_binary).decode("utf-8")

        try:
            secret = json.loads(secret_string)
        except (TypeError, json.JSONDecodeError):
            continue

        username = (
            secret.get("username")
            or secret.get("user")
            or secret.get("db_username")
            or secret.get("dbUser")
        )
        password = (
            secret.get("password")
            or secret.get("pass")
            or secret.get("db_password")
            or secret.get("dbPassword")
        )

        username = str(username).strip() if username is not None else ""
        password = str(password).strip() if password is not None else ""

        if username and password:
            _AURORA_CREDENTIALS = (username, password)
            print(
                f"[aurora_credentials] Loaded credentials for {resolved_secret_arn} "
                f"(stage={version_stage or 'Default'})"
            )
            return _AURORA_CREDENTIALS

    raise RuntimeError(
        f"Failed to resolve Aurora credentials from {resolved_secret_arn}: "
        f"{last_error}"
    )

def download_and_parse_dump(s3_key):
    """Download SQL dump from S3 and return local path."""
    local_path = f"/tmp/{s3_key.split('/')[-1]}"
    
    print(f"Downloading {s3_key} to {local_path}...")
    s3.download_file(args['S3_SOURCE_BUCKET'], s3_key, local_path)
    print(f"Downloaded to {local_path}")
    return local_path


def create_aurora_connection(
    database: str | None = None,
    cursorclass: Any | None = None,
    **connection_kwargs: Any,
):
    """Create a validated Aurora connection with explicit auth diagnostics."""
    username, password = get_aurora_credentials()
    if not username:
        raise RuntimeError(f"Empty Aurora username resolved from {args['AURORA_SECRET_ARN']}")
    if not password:
        raise RuntimeError(
            f"Empty Aurora password resolved from {args['AURORA_SECRET_ARN']} "
            f"for user {username}"
        )

    target_db = database or args['AURORA_DATABASE']
    try:
        connect_kwargs = {
            "host": args['AURORA_ENDPOINT'],
            "user": username,
            "password": password,
            "database": target_db,
            "charset": "utf8mb4",
        }
        if cursorclass is not None:
            connect_kwargs["cursorclass"] = cursorclass

        return pymysql.connect(**connect_kwargs, **connection_kwargs)
    except pymysql.err.OperationalError as exc:
        if exc.args and exc.args[0] == 1045:
            print(
                "[aurora_connection] Access denied while connecting to Aurora. "
                f"secret={args['AURORA_SECRET_ARN']} user={username} "
                f"password_length={len(password)} db={target_db}"
            )
        raise

def open_dump_file(local_path):
    """Open SQL dump file, supporting optional gzip compression."""
    if local_path.endswith(".gz"):
        return gzip.open(local_path, "rt", encoding="utf-8", errors="ignore")
    return open(local_path, "r", encoding="utf-8", errors="ignore")


def is_recoverable_dbt_hook_auth_error(output: str) -> bool:
    """
    Return True when dbt failed only because on-run-end hook hit auth error.

    This keeps pipeline progress when all models succeed and only the non-critical
    run-end hook reconnect fails with MySQL 1045.
    """
    if not output:
        return False

    normalized = output.lower()
    has_hook_failure = "on-run-end failed" in normalized
    has_auth_error = (
        "1045 (28000): access denied" in normalized
        or "access denied for user" in normalized
    )
    has_single_error_summary = re.search(
        r"done\.\s+pass=\d+\s+warn=\d+\s+error=1\b",
        normalized,
    ) is not None
    has_model_failure = (
        "database error in model" in normalized
        or "runtime error in model" in normalized
    )

    return (
        has_hook_failure
        and has_auth_error
        and has_single_error_summary
        and not has_model_failure
    )

def load_to_aurora_staging(dump_path):
    """Load SQL dump into Aurora staging schema."""
    # Connect to Aurora
    connection = create_aurora_connection()
    cursor = None
    
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

        ensure_llm_enrichment_cache_table(cursor)
        ensure_property_geo_latlon_backup_table(cursor)
        assert_required_staging_tables_exist(
            cursor,
            {"llm_enrichment_cache", "property_geo_latlon_backup"},
        )
        print(
            "Verified persistent tables: "
            "staging.llm_enrichment_cache, staging.property_geo_latlon_backup"
        )
        
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

        # Re-create and verify mandatory persistent table in case dump statements dropped it.
        ensure_llm_enrichment_cache_table(cursor)
        ensure_property_geo_latlon_backup_table(cursor)
        assert_required_staging_tables_exist(cursor)
        connection.commit()
        print(
            "Verified required staging tables after dump load: "
            + ", ".join(f"staging.{name}" for name in sorted(REQUIRED_STAGING_TABLES))
        )
        
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
        if cursor is not None:
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
    
    connection = create_aurora_connection()
    
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
    
    connection = create_aurora_connection()
    
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
    
    connection = create_aurora_connection()
    
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
    dbt_project_s3_path = args.get("DBT_PROJECT_PATH") or f"s3://{args['S3_SOURCE_BUCKET']}/dbt-project/"
    if not dbt_project_s3_path.startswith("s3://"):
        raise ValueError(f"Invalid DBT_PROJECT_PATH: {dbt_project_s3_path}")
    sync_start = time.perf_counter()
    subprocess.run([
        "aws", "s3", "sync",
        dbt_project_s3_path,
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
    force_rebuild_snapshot_date = runtime_optional_date("DAILY_FORCE_REBUILD_SNAPSHOT_DATE")
    effective_snapshot_date = snapshot_date
    if force_rebuild_snapshot_date is not None:
        # Keep delete/reinsert on the same partition when force rebuild is used.
        # This prevents deleting one snapshot_date while inserting another.
        effective_snapshot_date = force_rebuild_snapshot_date
        if force_rebuild_snapshot_date != snapshot_date:
            print(
                "INFO: DAILY_FORCE_REBUILD_SNAPSHOT_DATE differs from DAILY_TARGET_DATE; "
                "overriding dbt daily_snapshot_date to force rebuild date for safe partition alignment "
                f"(target={snapshot_date.isoformat()}, force={force_rebuild_snapshot_date.isoformat()})"
            )

    dbt_vars: Dict[str, str] = {"daily_snapshot_date": effective_snapshot_date.isoformat()}
    if force_rebuild_snapshot_date is not None:
        dbt_vars["force_rebuild_snapshot_date"] = force_rebuild_snapshot_date.isoformat()
    dbt_vars_payload = json.dumps(dbt_vars)
    print(f"[dbt_vars] daily_snapshot_date={effective_snapshot_date.isoformat()}")
    if force_rebuild_snapshot_date is not None:
        print(
            "[dbt_vars] force_rebuild_snapshot_date="
            f"{force_rebuild_snapshot_date.isoformat()}"
        )

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
    
    def run_dbt_cmd(
        cmd: List[str],
        label: str,
        allow_recoverable_hook_auth_error: bool = False,
    ) -> subprocess.CompletedProcess:
        """Run dbt command and emit stdout/stderr for CloudWatch visibility."""
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(f"=== {label} OUTPUT ===")
        print(result.stdout)
        if result.stderr:
            print(f"=== {label} ERRORS ===")
            print(result.stderr)
        if result.returncode != 0:
            combined_output = f"{result.stdout or ''}\n{result.stderr or ''}"
            if (
                allow_recoverable_hook_auth_error
                and is_recoverable_dbt_hook_auth_error(combined_output)
            ):
                print(
                    "WARNING: dbt reported on-run-end auth failure (1045), "
                    "but model execution completed; continuing run."
                )
                return subprocess.CompletedProcess(
                    args=result.args,
                    returncode=0,
                    stdout=result.stdout,
                    stderr=result.stderr,
                )
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
            connection = create_aurora_connection()
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
            connection = create_aurora_connection()
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
                run_dbt_cmd(
                    phase_cmd,
                    f"DBT RUN {phase_name.upper()} (attempt {attempt}/{retries})",
                    allow_recoverable_hook_auth_error=True,
                )
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

    result = run_dbt_cmd(
        run_cmd,
        "DBT RUN MAIN-PHASE",
        allow_recoverable_hook_auth_error=True,
    )
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
    
    connection = create_aurora_connection()
    
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
        preserved_tables = [
            table_name for table_name in empty_tables
            if table_name in STAGING_PERSISTENT_TABLES
        ]
        empty_tables = [
            table_name for table_name in empty_tables
            if table_name not in STAGING_PERSISTENT_TABLES
        ]

        if preserved_tables:
            print(
                "Skipping persistent empty tables: "
                + ", ".join(sorted(preserved_tables))
            )
        
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
        SELECT id, status, contract_type, full_name
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

    csv_keys = []

    if hasattr(s3_client, 'list_objects_v2'):
        response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
        pages = [response]
    else:
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

    for page in pages:
        if 'Contents' not in page:
            continue

        for obj in page['Contents']:
            key = obj['Key']
            if key.endswith('.csv'):
                csv_keys.append(key)

    csv_keys.sort()
    print(f"Found {len(csv_keys)} snapshot CSV files")

    return csv_keys


def _extract_snapshot_date_from_key(snapshot_key: str) -> date:
    """Extract date suffix from a snapshot S3 key."""
    match = re.search(r"(\d{8})\.csv$", snapshot_key)
    if not match:
        raise ValueError(f"Invalid snapshot key: {snapshot_key}")
    return datetime.strptime(match.group(1), '%Y%m%d').date()

def _first_fetch_scalar(row: Any, default: int | str | date = 0) -> Any:
    """Return the first meaningful scalar value from a DB cursor row."""
    if row is None:
        return default
    if isinstance(row, dict):
        if 'count' in row:
            return row['count']
        if row:
            return next(iter(row.values()))
    if isinstance(row, (tuple, list)):
        if not row:
            return default
        return row[0]
    try:
        return row[0]
    except (TypeError, IndexError, KeyError):
        return default


def load_new_snapshots_only(connection, s3_client, bucket: str) -> Dict[str, Any]:
    """Load only snapshot CSVs newer than the table's max snapshot date."""
    print("\n" + "="*60)
    print("STEP: Load Only New Snapshots")
    print("="*60)

    cursor = connection.cursor()
    try:
        create_tenant_daily_snapshots_table(cursor)

        cursor.execute('SELECT MAX(snapshot_date) FROM staging.tenant_daily_snapshots')
        max_snapshot_row = cursor.fetchone()
        max_snapshot = _first_fetch_scalar(max_snapshot_row, None)

        csv_keys = list_snapshot_csvs(s3_client, bucket)
        if not csv_keys:
            return {
                'status': 'success',
                'csv_files_loaded': 0,
                'csv_files_skipped': 0,
                'total_rows_loaded': 0,
            }

        new_csv_keys = []
        for key in csv_keys:
            try:
                snapshot_date = _extract_snapshot_date_from_key(key.split('/')[-1])
            except ValueError:
                continue

            if max_snapshot is None or snapshot_date > max_snapshot:
                new_csv_keys.append(key)

        loaded_count = 0
        loaded_files = 0
        failed_count = 0

        for key in new_csv_keys:
            try:
                rows = download_and_parse_csv(s3_client, bucket, key)
                loaded_count += bulk_insert_snapshots(connection, cursor, rows)
                loaded_files += 1
            except Exception:
                failed_count += 1

        return {
            'status': 'success',
            'csv_files_loaded': loaded_files,
            'csv_files_failed': failed_count,
            'csv_files_skipped': len(csv_keys) - len(new_csv_keys),
            'skipped_existing': len(csv_keys) - len(new_csv_keys),
            'total_rows_loaded': loaded_count,
        }
    except Exception as exc:
        return {
            'status': 'failed',
            'error': str(exc),
        }
    finally:
        cursor.close()


def download_csvs_parallel(s3_client, bucket: str, csv_keys: List[str], max_workers: int = 4) -> List[Dict[str, Any]]:
    """Download snapshot CSVs in parallel and parse each file."""

    def _download(csv_key: str) -> Dict[str, Any]:
        try:
            rows = download_and_parse_csv(s3_client, bucket, csv_key)
            return {
                'csv_key': csv_key,
                'status': 'success',
                'rows': rows,
            }
        except Exception as exc:  # pragma: no cover - exercised in wrapper tests
            return {
                'csv_key': csv_key,
                'status': 'failed',
                'error': str(exc),
            }

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_download, csv_key)
            for csv_key in csv_keys
        ]

        return [future.result() for future in as_completed(futures)]


class SnapshotLoader:
    """Simple snapshot loader helper exposing batch size tuning for tests and callers."""

    def __init__(self, batch_size: int = 100):
        self.batch_size = int(batch_size)


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
    if isinstance(response, dict):
        body = response.get('Body')
    else:
        try:
            body = response['Body']
        except Exception:
            body = getattr(response, 'Body', None)

    if body is None:
        return []

    if hasattr(body, 'seek'):
        try:
            body.seek(0)
        except (AttributeError, OSError):
            pass
    raw_content = body.read()
    if isinstance(raw_content, bytes):
        content = raw_content.decode('utf-8')
    elif isinstance(raw_content, str):
        content = raw_content
    else:
        content = str(raw_content)
    
    reader = csv.DictReader(StringIO(content))
    rows = []
    
    required_headers = {'tenant_id', 'status', 'contract_type', 'full_name', 'snapshot_date'}
    if not reader.fieldnames or not required_headers.issubset(reader.fieldnames):
        return rows

    for row in reader:
        try:
            rows.append((
                int(row['tenant_id']),
                int(row['status']),
                int(row['contract_type']),
                row['full_name'],
                datetime.strptime(row['snapshot_date'], '%Y-%m-%d').date()
            ))
        except (KeyError, TypeError, ValueError):
            continue
    
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
        
        # Rebuild table each run to keep deterministic full history.
        print("Refreshing tenant_daily_snapshots for full historical load...")
        cursor.execute('TRUNCATE TABLE staging.tenant_daily_snapshots')

        # Get existing snapshot dates in the table (for compatibility when table pre-exists)
        print("Checking existing snapshots in database...")
        cursor.execute('SELECT DISTINCT snapshot_date FROM staging.tenant_daily_snapshots')
        try:
            fetched_dates = cursor.fetchall()
            existing_dates = {
                _row_date_value({"snapshot_date": row[0]}, "snapshot_date")
                for row in fetched_dates
            }
            existing_dates = {snapshot for snapshot in existing_dates if snapshot is not None}
        except TypeError:
            existing_dates = set()
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
        
        # Determine snapshot dates and known gap window.
        # Snapshot history load should intentionally skip invalid/gap days to preserve
        # fact continuity policy for downstream occupancy KPIs.
        snapshot_dates: list[date] = []
        for key in csv_keys:
            filename = key.split('/')[-1]
            try:
                snapshot_dates.append(_extract_snapshot_date_from_key(filename))
            except ValueError:
                pass

        gap_dates: list[date] = []
        if snapshot_dates:
            gap_dates = get_gap_dates_for_window(
                cursor,
                min(snapshot_dates),
                max(snapshot_dates),
            )
        gap_dates_set = set(gap_dates)

        # Filter to only NEW snapshots (not already loaded)
        new_csv_keys = []
        skipped_by_gap = 0
        skipped_by_manifest = 0
        for key in csv_keys:
            # Extract date from filename: snapshots/tenant_status/YYYYMMDD.csv
            filename = key.split('/')[-1]
            try:
                snapshot_date = _extract_snapshot_date_from_key(filename)
            except ValueError:
                continue

            snapshot_date_str = snapshot_date.strftime('%Y%m%d')
            if snapshot_date in existing_dates:
                continue
            if snapshot_date in gap_dates_set:
                print(
                    "Skipping snapshot due to data-quality gap: "
                    f"{snapshot_date_str} (gold.data_quality_calendar is_gap=1)"
                )
                skipped_by_gap += 1
                continue

            try:
                manifest = load_dump_manifest(snapshot_date)
            except Exception as err:
                print(
                    f"WARN: Could not load manifest for snapshot {snapshot_date_str} "
                    f"(treating as unavailable): {err}"
                )
                manifest = None

            if manifest is not None and not manifest_is_valid_for_etl(manifest):
                reason = (
                    str(manifest.get("reason", "manifest_missing"))
                    if isinstance(manifest, dict)
                    else "manifest_missing"
                )
                print(
                    "Skipping snapshot due to invalid source manifest: "
                    f"{snapshot_date_str} (reason={reason})"
                )
                skipped_by_manifest += 1
                continue

            new_csv_keys.append(key)
        
        if not new_csv_keys:
            print("✓ All snapshots already loaded - nothing new to import")
            return {
                'status': 'success',
                'csv_files_loaded': 0,
                'csv_files_skipped': len(csv_keys),
                'csv_files_skipped_gap': skipped_by_gap,
                'csv_files_skipped_manifest': skipped_by_manifest,
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
        final_count = _first_fetch_scalar(cursor.fetchone())
        
        cursor.close()
        
        print(f"\n✓ Snapshot load complete:")
        print(f"  - NEW CSV files loaded: {loaded_files}")
        print(f"  - CSV files skipped (already loaded): {len(csv_keys) - len(new_csv_keys)}")
        if skipped_by_gap:
            print(f"  - CSV files skipped (gap dates): {skipped_by_gap}")
        if skipped_by_manifest:
            print(f"  - CSV files skipped (invalid manifest): {skipped_by_manifest}")
        print(f"  - CSV files failed: {failed_files}")
        print(f"  - NEW rows loaded: {total_rows:,}")
        print(f"  - Final table count: {final_count:,}")
        
        return {
            'status': 'success',
            'csv_files_loaded': loaded_files,
            'csv_files_skipped': len(csv_keys) - len(new_csv_keys),
            'csv_files_skipped_gap': skipped_by_gap,
            'csv_files_skipped_manifest': skipped_by_manifest,
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

    target_dates = sorted(set(target_dates))
    gap_dates = set(
        get_gap_dates_for_window(
            cursor,
            target_dates[0],
            target_dates[-1],
        )
    )
    if gap_dates:
        print(
            "Skipping data-quality gap dates in occupancy KPI calculation: "
            f"{len(gap_dates)} dates, first={sorted(gap_dates)[0]}, "
            f"last={sorted(gap_dates)[-1]}"
        )

    period_end_by_date: Dict[date, int] = {}
    processed_count = 0

    def snapshot_exists(snapshot_date: date) -> bool:
        if snapshot_date in gap_dates:
            return False
        cursor.execute(
            """
            SELECT 1
            FROM silver.tenant_room_snapshot_daily
            WHERE snapshot_date = %s
            LIMIT 1
            """,
            (snapshot_date,),
        )
        return cursor.fetchone() is not None

    def next_available_snapshot_date(from_date: date) -> date | None:
        cursor.execute(
            """
            SELECT MIN(snapshot_date) AS next_snapshot_date
            FROM silver.tenant_room_snapshot_daily s
            LEFT JOIN gold.data_quality_calendar g
              ON g.check_date = s.snapshot_date
             AND g.is_gap = 1
            WHERE s.snapshot_date >= %s
              AND g.check_date IS NULL
            """,
            (from_date,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return row.get("next_snapshot_date")

    def count_occupied_rooms(snapshot_date: date) -> int:
        cursor.execute(
            """
            SELECT COUNT(DISTINCT CONCAT(apartment_id, '-', room_id)) AS count
            FROM silver.tenant_room_snapshot_daily
            WHERE snapshot_date = %s
              AND management_status_code IN (7, 9, 10, 11, 12, 13, 14, 15)
            """,
            (snapshot_date,),
        )
        return int(cursor.fetchone()["count"])

    def get_prior_valid_period_end(target_date: date) -> int:
        if target_date in period_end_by_date:
            del period_end_by_date[target_date]

        in_memory_dates = sorted(period_end_by_date.keys(), reverse=True)
        for prior_date in in_memory_dates:
            if prior_date < target_date and prior_date not in gap_dates:
                return period_end_by_date[prior_date]

        cursor.execute(
            """
            SELECT g.period_end_rooms
            FROM gold.occupancy_daily_metrics g
            LEFT JOIN gold.data_quality_calendar c
              ON c.check_date = g.snapshot_date
             AND c.is_gap = 1
            WHERE g.snapshot_date < %s
              AND c.check_date IS NULL
            ORDER BY g.snapshot_date DESC
            LIMIT 1
            """,
            (target_date,),
        )
        result = cursor.fetchone()
        if result and result.get("period_end_rooms") is not None:
            return int(result["period_end_rooms"])
        return 0

    for target_date in target_dates:
        if target_date in gap_dates:
            print(f"SKIP: occupancy KPI for gap date {target_date} (data quality gap)")
            continue

        is_future = target_date > as_of_snapshot_date
        # For missing fact-day snapshots, forward-fill occupancy from the next available snapshot
        # to avoid 0% spikes. Movements/applications cannot be reliably recovered, so set them to 0.
        missing_fact_snapshot = False
        filled_from_snapshot: date | None = None

        if is_future:
            snapshot_date_filter = as_of_snapshot_date
        else:
            if snapshot_exists(target_date):
                snapshot_date_filter = target_date
            else:
                missing_fact_snapshot = True
                filled_from_snapshot = next_available_snapshot_date(target_date) or as_of_snapshot_date
                snapshot_date_filter = filled_from_snapshot
                print(
                    "WARN: Missing silver snapshot for "
                    f"{target_date}; forward-filling occupancy from {snapshot_date_filter}. "
                    "Setting movements/applications to 0 for this date."
                )

        if is_future or missing_fact_snapshot:
            applications = 0
        else:
            cursor.execute("""
                SELECT COUNT(DISTINCT CONCAT(apartment_id, '-', room_id)) AS count
                FROM (
                    SELECT
                        apartment_id,
                        room_id,
                        MIN(snapshot_date) AS first_appearance
                    FROM silver.tenant_room_snapshot_daily
                    WHERE management_status_code IN (4, 5)
                    GROUP BY apartment_id, room_id
                ) first_apps
                WHERE first_appearance = %s
            """, (target_date,))
            applications = cursor.fetchone()["count"]

        if missing_fact_snapshot:
            new_moveins = 0
        else:
            cursor.execute("""
                SELECT COUNT(DISTINCT CONCAT(apartment_id, '-', room_id)) AS count
                FROM silver.tenant_room_snapshot_daily
                WHERE snapshot_date = %s
                  AND move_in_date = %s
                  AND management_status_code IN (4, 5, 6, 7, 9)
            """, (snapshot_date_filter, target_date))
            new_moveins = cursor.fetchone()["count"]

        if missing_fact_snapshot:
            new_moveouts = 0
        else:
            cursor.execute(
                """
                SELECT COUNT(DISTINCT CONCAT(apartment_id, '-', room_id)) AS count
                FROM silver.tenant_room_snapshot_daily
                WHERE snapshot_date = %s
                  AND moveout_date = %s
                  AND management_status_code IN (14, 15, 16, 17)
                """,
                (snapshot_date_filter, target_date),
            )
            new_moveouts = cursor.fetchone()["count"]

        occupancy_delta = int(new_moveins) - int(new_moveouts)

        previous_date = target_date - timedelta(days=1)
        if is_future:
            # Future projections must chain from the previous day's KPI end-room count.
            # Silver snapshots do not exist for future dates, so counting from silver would reset to 0.
            period_start_rooms = get_prior_valid_period_end(target_date)
        else:
            # Fact days: compute end rooms from same-day snapshot if present (or forward-filled snapshot if missing),
            # then derive start rooms from delta. This avoids collapsing to 0 when previous day snapshot is missing.
            period_end_rooms = count_occupied_rooms(snapshot_date_filter)
            if previous_date in gap_dates:
                period_start_rooms = None
            else:
                period_start_rooms = int(period_end_rooms) - int(occupancy_delta)
                if period_start_rooms < 0:
                    print(
                        "WARN: Derived period_start_rooms < 0; clamping. "
                        f"date={target_date} end={period_end_rooms} delta={occupancy_delta}"
                    )
                    period_start_rooms = 0
            if period_end_rooms < 0:
                period_end_rooms = 0
        if is_future:
            period_end_rooms = period_start_rooms + occupancy_delta
        period_end_by_date[target_date] = int(period_end_rooms)
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

        processed_count += 1

    return processed_count


def _row_date_value(row: Any, key: str = "snapshot_date") -> date | None:
    """Extract a DATE value from dict/tuple cursor rows."""
    if row is None:
        return None

    value: Any = None
    if isinstance(row, dict):
        value = row.get(key)
        if value is None and row:
            value = next(iter(row.values()))
    elif isinstance(row, (tuple, list)):
        if row:
            value = row[0]
    else:
        try:
            value = row[0]
        except (TypeError, IndexError, KeyError):
            value = None

    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%Y%m%d"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
    return None


def get_missing_silver_snapshot_dates(
    cursor,
    start_date: date,
    end_date: date,
) -> List[date]:
    """
    Find missing dates in silver snapshots within a bounded window.
    Only checks between the earliest/latest observed dates in the window.
    """
    if start_date > end_date:
        return []

    cursor.execute(
        """
        SELECT DISTINCT snapshot_date
        FROM silver.tenant_room_snapshot_daily
        WHERE snapshot_date BETWEEN %s AND %s
        ORDER BY snapshot_date
        """,
        (start_date, end_date),
    )
    observed_rows = cursor.fetchall() or []
    observed_dates = sorted(
        {
            dt
            for dt in (_row_date_value(row, "snapshot_date") for row in observed_rows)
            if dt is not None
        }
    )
    if not observed_dates:
        return []

    effective_start = max(start_date, observed_dates[0])
    effective_end = min(end_date, observed_dates[-1])

    missing: List[date] = []
    current = effective_start
    observed_set = set(observed_dates)
    while current <= effective_end:
        if current not in observed_set:
            missing.append(current)
        current += timedelta(days=1)
    return missing


def get_stale_gold_occupancy_dates(
    cursor,
    start_date: date,
    end_date: date,
) -> List[date]:
    """
    Find historical fact dates that likely carry stale KPI artifacts.
    """
    if start_date > end_date:
        return []

    cursor.execute(
        """
        SELECT snapshot_date
        FROM gold.occupancy_daily_metrics
        WHERE snapshot_date BETWEEN %s AND %s
          AND (
                period_end_rooms IS NULL
                OR period_end_rooms <= 0
                OR occupancy_rate IS NULL
                OR occupancy_rate <= 0
          )
        ORDER BY snapshot_date
        """,
        (start_date, end_date),
    )
    rows = cursor.fetchall() or []
    return [
        dt
        for dt in (_row_date_value(row, "snapshot_date") for row in rows)
        if dt is not None
    ]


def update_gold_occupancy_kpis(target_date: date, lookback_days: int, forward_days: int) -> int:
    """Update gold.occupancy_daily_metrics for target +/- windows."""
    print(
        f"\nUpdating gold.occupancy_daily_metrics "
        f"(target_date={target_date}, lookback_days={lookback_days}, forward_days={forward_days})"
    )

    connection = create_aurora_connection(
        cursorclass=pymysql.cursors.DictCursor
    )
    cursor = connection.cursor()
    try:
        ensure_occupancy_kpi_table_exists(cursor)
        base_start_date = target_date - timedelta(days=lookback_days)
        rebuild_start_override = runtime_optional_date(
            "DAILY_OCCUPANCY_REBUILD_START_DATE"
        )
        if rebuild_start_override is not None:
            base_start_date = min(base_start_date, rebuild_start_override)
            print(
                "Applying occupancy rebuild start override: "
                f"{rebuild_start_override.isoformat()}"
            )
        base_end_date = target_date + timedelta(days=forward_days)
        base_dates = [
            base_start_date + timedelta(days=i)
            for i in range((base_end_date - base_start_date).days + 1)
        ]
        cursor.execute(
            """
            SELECT MAX(snapshot_date) AS max_snapshot_date
            FROM silver.tenant_room_snapshot_daily
            """
        )
        snapshot_meta = cursor.fetchone()
        as_of_snapshot_date = snapshot_meta["max_snapshot_date"] if snapshot_meta else None
        if as_of_snapshot_date is None:
            raise RuntimeError("No data in silver.tenant_room_snapshot_daily; cannot compute occupancy KPIs")

        repair_lookback_days = env_int("DAILY_OCCUPANCY_REPAIR_LOOKBACK_DAYS", 30, minimum=0)
        repair_start_date = min(
            base_dates[0],
            as_of_snapshot_date - timedelta(days=repair_lookback_days),
        )
        # Also repair forward-projected dates in the same run window, not only
        # up to the latest available snapshot date.
        repair_end_date = max(base_dates[-1], as_of_snapshot_date)

        missing_fact_dates = get_missing_silver_snapshot_dates(
            cursor,
            repair_start_date,
            repair_end_date,
        )
        stale_fact_dates = get_stale_gold_occupancy_dates(
            cursor,
            repair_start_date,
            repair_end_date,
        )

        extra_gap_dates = get_gap_dates_for_window(
            cursor,
            repair_start_date,
            repair_end_date,
        )

        extra_repair_dates = sorted(
            set(missing_fact_dates + stale_fact_dates)
            - set(extra_gap_dates)
        )
        purged_rows = purge_gold_occupancy_gap_rows(
            cursor,
            repair_start_date,
            repair_end_date,
        )
        if purged_rows:
            print(f"Purged {purged_rows} gap rows before occupancy KPI recomputation")
        if extra_repair_dates:
            print(
                "Including occupancy repair dates outside primary window: "
                f"{len(extra_repair_dates)} date(s), "
                f"first={extra_repair_dates[0]}, last={extra_repair_dates[-1]}"
            )

        dates_to_process = sorted(
            set(base_dates + extra_repair_dates)
            - set(extra_gap_dates)
        )
        if not dates_to_process:
            print("No non-gap occupancy dates to process after data-quality filtering")
            return 0

        processed_dates = compute_occupancy_kpis_for_dates(cursor, dates_to_process)
        connection.commit()
        print(f"Updated occupancy KPI rows for {processed_dates} date(s)")
        return processed_dates
    finally:
        cursor.close()
        connection.close()


def log_layer_freshness() -> Dict[str, Any]:
    """Log silver/gold max dates and row counts for post-run verification."""
    connection = create_aurora_connection(
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


def enrich_nationality_data(
    nationality_max_batch: int = 300,
    municipality_max_batch: int = 150,
    requests_per_second: int = 3,
    fail_on_error: bool = False,
):
    """
    Enrich missing nationality data using AWS Bedrock LLM.
    Targets records with レソト placeholder, NULL, or empty nationality.
    """
    print("\n" + "="*60)
    print("STEP: LLM Nationality Enrichment")
    print("="*60)
    
    try:
        # Download nationality_enricher.py from release path first, then legacy fallback.
        enricher_path, enricher_s3_key = download_nationality_enricher_script()
        
        # Add to Python path
        enricher_dir = os.path.dirname(enricher_path)
        if enricher_dir not in sys.path:
            sys.path.insert(0, enricher_dir)
        
        print(f"✓ Downloaded nationality_enricher.py from s3://{args['S3_SOURCE_BUCKET']}/{enricher_s3_key}")
        
        # Import enricher
        from nationality_enricher import NationalityEnricher
        
        # Create enricher instance
        enricher = NationalityEnricher(
            aurora_endpoint=args['AURORA_ENDPOINT'],
            aurora_database=args['AURORA_DATABASE'],
            secret_arn=args['AURORA_SECRET_ARN'],
            bedrock_region='us-east-1',
            max_batch_size=nationality_max_batch,
            requests_per_second=requests_per_second,
            dry_run=False
        )

        # Run nationality enrichment first (tenant cache)
        nationality_summary = enricher.enrich_all_missing_nationalities()

        municipality_summary = {
            "properties_identified": 0,
            "predictions_made": 0,
            "successful_updates": 0,
            "failed_updates": 0,
            "execution_time_seconds": 0,
        }
        # Then run municipality enrichment with smaller cap (property cache), if available.
        if hasattr(enricher, "enrich_missing_municipalities"):
            municipality_summary = enricher.enrich_missing_municipalities(
                max_batch_size=municipality_max_batch
            )
        else:
            print(
                "⚠ Downloaded nationality_enricher.py does not support municipality enrichment; "
                "skipping municipality step."
            )

        print(f"✓ LLM enrichment completed:")
        print(f"  - Nationality candidates: {nationality_summary['tenants_identified']}")
        print(f"  - Nationality updated: {nationality_summary['successful_updates']}")
        print(f"  - Municipality candidates: {municipality_summary['properties_identified']}")
        print(f"  - Municipality updated: {municipality_summary['successful_updates']}")

        return {
            "nationality_summary": nationality_summary,
            "municipality_summary": municipality_summary,
        }
        
    except Exception as e:
        print(f"⚠ Warning: Nationality enrichment failed: {str(e)}")
        print("  (Continuing with ETL - enrichment is non-critical by default)")
        import traceback
        traceback.print_exc()
        if fail_on_error:
            raise
        return {
            "nationality_summary": {
                "tenants_identified": 0,
                "predictions_made": 0,
                "successful_updates": 0,
                "failed_updates": 0,
                "execution_time_seconds": 0,
            },
            "municipality_summary": {
                "properties_identified": 0,
                "predictions_made": 0,
                "successful_updates": 0,
                "failed_updates": 0,
                "execution_time_seconds": 0,
            },
        }

def archive_processed_dump(s3_key, fail_on_error=False):
    """Move processed dump to archive folder.

    Args:
        s3_key: Source dump key under the configured source bucket.
        fail_on_error: When True, re-raise archival errors.

    Returns:
        bool: True if archived successfully, False if skipped due to archive error.
    """
    source_key = s3_key
    dest_key = get_processed_dump_key(source_key)

    try:
        s3.copy_object(
            Bucket=args['S3_SOURCE_BUCKET'],
            CopySource={'Bucket': args['S3_SOURCE_BUCKET'], 'Key': source_key},
            Key=dest_key
        )
    except Exception as exc:
        error_code = "Unknown"
        error_message = str(exc)
        if isinstance(exc, ClientError):
            error = exc.response.get("Error", {})
            error_code = error.get("Code", "Unknown")
            error_message = error.get("Message", str(exc))
        print(
            "WARN: Failed to archive processed dump "
            f"{source_key} -> {dest_key}: {error_code} ({error_message})"
        )
        if fail_on_error:
            raise
        return False

    print(f"Archived dump to {dest_key}")
    return True

def main():
    """Main ETL workflow."""
    start_time = datetime.now()
    step_timings: Dict[str, Dict[str, Any]] = {}
    
    try:
        # NOTE: Aurora automated backups enabled with 7-day retention for PITR
        # No manual snapshots created to reduce costs (~$57/month savings)
        # Use scripts/rollback_etl.sh if recovery needed
        llm_settings = resolve_llm_runtime_settings()
        skip_enrichment = llm_settings["skip_enrichment"]
        llm_nationality_max_batch = llm_settings["nationality_max_batch"]
        llm_municipality_max_batch = llm_settings["municipality_max_batch"]
        llm_requests_per_second = llm_settings["requests_per_second"]
        llm_fail_on_error = llm_settings["fail_on_error"]
        skip_table_backups = env_bool("DAILY_SKIP_TABLE_BACKUPS", True)
        run_backup_cleanup = env_bool("DAILY_RUN_BACKUP_CLEANUP", True)
        include_staging_backup_cleanup = env_bool("DAILY_CLEANUP_STAGING_BACKUPS", True)
        run_occupancy_gold_step = runtime_bool("DAILY_RUN_OCCUPANCY_GOLD_STEP", True)
        fail_on_archive_error = runtime_bool("DAILY_FAIL_ON_ARCHIVE_ERROR", False)
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
        quality_calendar_rows = 0
        quality_calendar_gap_days = 0
        dump_archive_success = False
        municipality_enriched_count = 0
        llm_cache_before = 0
        llm_cache_after = 0
        llm_cache_inserted_this_run = 0
        geo_backup_upserted = 0
        geo_backup_total_rows = 0
        geo_backup_latest_key = ""

        # Step 1: Always find and download latest dump
        latest_key = None
        local_path = None
        dump_date = None
        max_stale_days = runtime_int("DAILY_MAX_DUMP_STALE_DAYS", 1, minimum=0)
        max_source_stale_days = runtime_int("DAILY_MAX_SOURCE_STALE_DAYS", 14, minimum=0)
        require_dump_manifest = runtime_bool("DAILY_REQUIRE_DUMP_MANIFEST", True)
        strict_dump_continuity = runtime_bool("DAILY_STRICT_DUMP_CONTINUITY", False)
        data_quality_lookback_days = runtime_int("DAILY_QUALITY_LOOKBACK_DAYS", 14, minimum=0)
        expected_dump_date = runtime_date("DAILY_TARGET_DATE", tokyo_today())
        with timed_step("01_find_and_download_dump", step_timings):
            dump_candidates = list_dump_candidates()
            dump_dates = get_dump_dates(dump_candidates)
            latest_key = get_latest_dump_key(
                dump_candidates=dump_candidates,
                require_manifest=require_dump_manifest,
                expected_date=expected_dump_date,
                max_source_stale_days=max_source_stale_days,
            )
            dump_date = extract_dump_date_from_key(latest_key)
            validate_dump_freshness(
                latest_key=latest_key,
                latest_dump_date=dump_date,
                expected_date=expected_dump_date,
                max_stale_days=max_stale_days,
            )
            check_dump_continuity(
                available_dump_dates=dump_dates,
                expected_date=expected_dump_date,
                max_stale_days=max_stale_days,
                strict=strict_dump_continuity,
            )
            if dump_date is not None and "DAILY_TARGET_DATE" not in os.environ:
                os.environ["DAILY_TARGET_DATE"] = dump_date.isoformat()
                print(f"Anchored DAILY_TARGET_DATE to dump date: {dump_date.isoformat()}")
            local_path = download_and_parse_dump(latest_key)

        # Step 1.5: Keep explicit valid/invalid dump calendar for downstream filtering
        with timed_step("01_5_update_data_quality_calendar", step_timings):
            quality_rows = build_data_quality_calendar_entries(
                expected_date=expected_dump_date,
                lookback_days=data_quality_lookback_days,
            )
            quality_rows.extend(build_manual_quality_calendar_overrides())
            # Apply last-write-wins semantics on check_date so manual overrides
            # deterministically supersede manifest-derived status.
            quality_rows = list(
                {row["check_date"]: row for row in quality_rows}.values()
            )
            quality_calendar_gap_days = sum(row["is_gap"] for row in quality_rows)

            connection = create_aurora_connection()
            try:
                cursor = connection.cursor()
                ensure_data_quality_calendar_table_exists(cursor)
                quality_calendar_rows = upsert_data_quality_calendar_entries(cursor, quality_rows)
                connection.commit()
            finally:
                connection.close()

            print(
                "Data quality calendar updated: "
                f"rows={quality_calendar_rows}, gap_days={quality_calendar_gap_days}, "
                f"window={data_quality_lookback_days + 1} days"
            )

        occupancy_target_date = runtime_date(
            "DAILY_TARGET_DATE",
            dump_date if dump_date is not None else expected_dump_date,
        )

        # Step 2: Load to Aurora staging
        with timed_step("02_load_dump_to_aurora_staging", step_timings):
            table_count, stmt_count = load_to_aurora_staging(local_path)

        # Step 3: Clean up empty tables
        with timed_step("03_cleanup_empty_staging_tables", step_timings):
            dropped_count = cleanup_empty_staging_tables()

        # Step 4: Export today's tenant snapshot to S3
        with timed_step("04_export_tenant_snapshot_to_s3", step_timings):
            connection = create_aurora_connection()
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
            connection = create_aurora_connection()
            try:
                snapshot_load_result = load_tenant_snapshots_from_s3(
                    connection,
                    s3,
                    args['S3_SOURCE_BUCKET']
                )
                snapshot_rows_loaded = snapshot_load_result.get('total_rows_loaded', 0)
            finally:
                connection.close()

        # Step 5.5: Persist property geolocation backup and export to S3 (dated + latest).
        with timed_step("05_5_sync_property_geo_backup_to_s3", step_timings):
            connection = create_aurora_connection()
            try:
                geo_backup_result = sync_property_geo_latlon_backup_to_s3(
                    connection=connection,
                    s3_client=s3,
                    bucket=args["S3_SOURCE_BUCKET"],
                    snapshot_date=occupancy_target_date,
                )
                geo_backup_upserted = int(geo_backup_result.get("upserted_rows", 0))
                geo_backup_total_rows = int(geo_backup_result.get("total_rows", 0))
                geo_backup_latest_key = str(geo_backup_result.get("latest_key", ""))
                print(
                    "Property geo backup synced: "
                    f"upserted={geo_backup_upserted}, total={geo_backup_total_rows}, "
                    f"latest=s3://{args['S3_SOURCE_BUCKET']}/{geo_backup_latest_key}"
                )
            finally:
                connection.close()

        # Step 6: Enrich nationality data using LLM (レソト and missing values)
        if skip_enrichment:
            print("\nSkipping LLM enrichment (DAILY_SKIP_LLM_ENRICHMENT=true)")
        else:
            llm_cache_before = get_staging_table_row_count("llm_enrichment_cache")
            print(f"llm_cache_before={llm_cache_before}")
            with timed_step("06_llm_nationality_enrichment", step_timings):
                enrichment_result = enrich_nationality_data(
                    nationality_max_batch=llm_nationality_max_batch,
                    municipality_max_batch=llm_municipality_max_batch,
                    requests_per_second=llm_requests_per_second,
                    fail_on_error=llm_fail_on_error,
                )
                nationality_summary = enrichment_result["nationality_summary"]
                municipality_summary = enrichment_result["municipality_summary"]
                enriched_count = int(nationality_summary.get("successful_updates", 0))
                municipality_enriched_count = int(
                    municipality_summary.get("successful_updates", 0)
                )
            llm_cache_after = get_staging_table_row_count("llm_enrichment_cache")
            llm_cache_inserted_this_run = max(0, llm_cache_after - llm_cache_before)
            print(f"llm_cache_after={llm_cache_after}")
            print(f"llm_cache_inserted_this_run={llm_cache_inserted_this_run}")

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
            dump_archive_success = archive_processed_dump(
                latest_key,
                fail_on_error=fail_on_archive_error,
            )
        
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
        print(f"Property geo backup rows upserted: {geo_backup_upserted}")
        print(f"Property geo backup total rows: {geo_backup_total_rows}")
        print(f"Property geo backup latest key: {geo_backup_latest_key}")
        print(f"Nationalities enriched: {enriched_count}")
        print(f"Municipalities enriched: {municipality_enriched_count}")
        print(f"llm_cache_before={llm_cache_before}")
        print(f"llm_cache_after={llm_cache_after}")
        print(f"llm_cache_inserted_this_run={llm_cache_inserted_this_run}")
        print(f"Pre-ETL backups created: {backup_count}")
        print(f"Old backups removed: {removed_backups}")
        print(f"dbt temp tables dropped: {dropped_tmp_tables}")
        print(f"SQL statements executed: {stmt_count}")
        print(f"dbt transformations: {'Success' if dbt_success else 'Failed'}")
        print(f"Gold occupancy KPI dates processed: {occupancy_rows_processed}")
        print(
            "Processed dump archived: "
            f"{'Success' if dump_archive_success else 'Skipped due to archive warning'}"
        )
        print(f"Data quality calendar rows upserted: {quality_calendar_rows}")
        print(f"Data quality gap days in window: {quality_calendar_gap_days}")
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
