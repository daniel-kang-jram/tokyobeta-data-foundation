"""
AWS Glue ETL Job: Staging Loader
Downloads latest SQL dump from S3 and loads into Aurora staging schema.

Part of the resilient ETL architecture: Staging → Silver → Gold
This job focuses ONLY on the bronze/staging layer.
"""

import sys
import boto3
import json
import re
import gzip
from datetime import datetime
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
import pymysql

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
    'ENVIRONMENT'
])

job.init(args['JOB_NAME'], args)

# Initialize clients
s3 = boto3.client('s3')
secretsmanager = boto3.client('secretsmanager')


def normalize_statement(stmt: str) -> str:
    """
    Normalize SQL statement and skip session-level commands.
    
    Args:
        stmt: Raw SQL statement
        
    Returns:
        Normalized statement or empty string if should be skipped
    """
    stmt = stmt.strip()
    if not stmt:
        return ""
    
    # Skip session-level commands
    if re.match(r"^(SET|LOCK TABLES|UNLOCK TABLES)", stmt, re.IGNORECASE):
        return ""
    
    # Skip database commands (we set schema explicitly)
    if stmt.upper().startswith("CREATE DATABASE") or stmt.upper().startswith("USE "):
        return ""
    
    return stmt


def extract_table_name(stmt: str) -> str | None:
    """
    Extract table name from SQL statement.
    
    Args:
        stmt: SQL statement
        
    Returns:
        Table name or None if not a table statement
    """
    # Match CREATE TABLE, INSERT INTO, or DROP TABLE
    match = re.match(
        r"^(CREATE TABLE|INSERT INTO|DROP TABLE IF EXISTS|DROP TABLE)\s+`?(\w+)`?",
        stmt,
        re.IGNORECASE
    )
    if not match:
        return None
    return match.group(2)


def iter_sql_statements(lines):
    """
    Yield SQL statements from lines without corrupting inline data.
    
    Args:
        lines: Iterable of SQL dump lines
        
    Yields:
        Normalized SQL statements
    """
    buffer = []
    in_block_comment = False

    for line in lines:
        stripped = line.strip()
        
        # Handle block comments
        if in_block_comment:
            if "*/" in stripped:
                in_block_comment = False
            continue
        
        if stripped.startswith("/*"):
            if not stripped.endswith("*/"):
                in_block_comment = True
            continue
        
        # Skip single-line comments
        if stripped.startswith("--"):
            continue

        buffer.append(line)
        
        # Statement complete when we hit semicolon at end of line
        if stripped.endswith(";"):
            raw_stmt = "".join(buffer)
            buffer = []
            stmt = normalize_statement(raw_stmt)
            if stmt:
                yield stmt

    # Handle any remaining buffer
    if buffer:
        stmt = normalize_statement("".join(buffer))
        if stmt:
            yield stmt


def get_latest_dump_key(s3_client, bucket, prefix):
    """
    Find the most recent SQL dump file in S3.
    
    Args:
        s3_client: boto3 S3 client
        bucket: S3 bucket name
        prefix: S3 prefix (folder path)
        
    Returns:
        S3 key of latest dump file
        
    Raises:
        ValueError: If no dump files found
    """
    response = s3_client.list_objects_v2(
        Bucket=bucket,
        Prefix=prefix
    )
    
    if 'Contents' not in response:
        raise ValueError(f"No files found in s3://{bucket}/{prefix}")
    
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


def get_aurora_credentials(secretsmanager_client, secret_arn):
    """
    Retrieve Aurora credentials from Secrets Manager.
    
    Args:
        secretsmanager_client: boto3 Secrets Manager client
        secret_arn: ARN of the secret
        
    Returns:
        Tuple of (username, password)
    """
    response = secretsmanager_client.get_secret_value(SecretId=secret_arn)
    secret = json.loads(response['SecretString'])
    return secret['username'], secret['password']


def download_dump_file(s3_client, bucket, s3_key):
    """
    Download SQL dump from S3 and return local path.
    
    Args:
        s3_client: boto3 S3 client
        bucket: S3 bucket name
        s3_key: S3 object key
        
    Returns:
        Local file path
    """
    local_path = f"/tmp/{s3_key.split('/')[-1]}"
    
    print(f"Downloading {s3_key} to {local_path}...")
    s3_client.download_file(bucket, s3_key, local_path)
    print(f"Downloaded to {local_path}")
    return local_path


def open_dump_file(local_path):
    """
    Open SQL dump file, supporting optional gzip compression.
    
    Args:
        local_path: Path to dump file
        
    Returns:
        File object
    """
    if local_path.endswith(".gz"):
        return gzip.open(local_path, "rt", encoding="utf-8", errors="ignore")
    return open(local_path, "r", encoding="utf-8", errors="ignore")


def parse_dump_file(dump_path):
    """
    Parse SQL dump file and return statements.
    
    Args:
        dump_path: Path to SQL dump file
        
    Returns:
        List of SQL statements
    """
    statements = []
    with open_dump_file(dump_path) as dump_file:
        for stmt in iter_sql_statements(dump_file):
            statements.append(stmt)
    return statements


def load_to_aurora_staging(connection, statements, schema='staging'):
    """
    Load SQL statements into Aurora staging schema.
    
    Args:
        connection: pymysql connection
        statements: List of SQL statements
        schema: Target schema name
        
    Returns:
        Tuple of (table_count, statement_count)
    """
    cursor = connection.cursor()
    
    try:
        # Create required schemas
        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        cursor.execute("CREATE SCHEMA IF NOT EXISTS analytics")
        cursor.execute("CREATE SCHEMA IF NOT EXISTS seeds")
        cursor.execute(f"USE {schema}")
        cursor.execute("SET SESSION sql_mode = 'ALLOW_INVALID_DATES'")
        cursor.execute("SET NAMES utf8mb4")
        
        print(f"Schemas verified/created: {schema}, analytics, seeds")
        
        # Check existing tables
        cursor.execute(f"""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = '{schema}'
        """)
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        if existing_tables:
            print(f"Found {len(existing_tables)} existing {schema} tables - SQL dump will handle recreation")
        else:
            print(f"No existing {schema} tables - clean load")
        
        connection.commit()
        
        # Execute SQL statements incrementally
        print("Streaming and executing SQL statements...")
        
        executed = 0
        for stmt in statements:
            try:
                cursor.execute(stmt)
                executed += 1
                
                # Commit every 100 statements
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
        
        # Count tables created
        cursor.execute(f"""
            SELECT table_name, table_rows 
            FROM information_schema.tables 
            WHERE table_schema = '{schema}'
            ORDER BY table_name
        """)
        
        tables = cursor.fetchall()
        print(f"\n{schema.capitalize()} schema now contains {len(tables)} tables:")
        for table_name, row_count in tables:
            print(f"  - {table_name}: {row_count} rows")
        
        return len(tables), executed
        
    finally:
        cursor.close()


def cleanup_empty_staging_tables(connection, schema='staging'):
    """
    Drop empty staging tables to optimize database performance.
    
    Args:
        connection: pymysql connection
        schema: Schema to clean up
        
    Returns:
        Number of tables dropped
    """
    print(f"\nCleaning up empty {schema} tables...")
    
    cursor = connection.cursor()
    
    try:
        # Find empty tables
        cursor.execute(f"""
            SELECT TABLE_NAME 
            FROM information_schema.TABLES 
            WHERE TABLE_SCHEMA = '{schema}' 
            AND TABLE_ROWS = 0
        """)
        
        empty_tables = [row[0] for row in cursor.fetchall()]
        
        if not empty_tables:
            print(f"No empty tables found - {schema} schema is clean")
            return 0
        
        print(f"Found {len(empty_tables)} empty tables to drop")
        
        dropped_count = 0
        for table_name in empty_tables:
            # Double-check it's actually empty
            cursor.execute(f"SELECT COUNT(*) FROM `{schema}`.`{table_name}`")
            actual_count = cursor.fetchone()[0]
            
            if actual_count == 0:
                try:
                    cursor.execute(f"DROP TABLE IF EXISTS `{schema}`.`{table_name}`")
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


def archive_processed_dump(s3_client, bucket, source_key):
    """
    Move processed dump to archive folder.
    
    Args:
        s3_client: boto3 S3 client
        bucket: S3 bucket name
        source_key: Source S3 key
    """
    # Handle both 'dumps/' and '/dumps/' patterns
    dest_key = source_key.replace('/dumps/', '/processed/').replace('dumps/', 'processed/')
    
    s3_client.copy_object(
        Bucket=bucket,
        CopySource={'Bucket': bucket, 'Key': source_key},
        Key=dest_key
    )
    
    print(f"Archived dump to {dest_key}")


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
            max_batch_size=2500,  # Process up to 2500 per day (covers all 2,001 target records)
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


def main():
    """Main staging loader workflow."""
    start_time = datetime.now()
    
    try:
        print("="*60)
        print("STAGING LOADER JOB STARTED")
        print(f"Environment: {args['ENVIRONMENT']}")
        print("="*60)
        
        # Step 1: Find and download latest dump
        latest_key = get_latest_dump_key(
            s3,
            args['S3_SOURCE_BUCKET'],
            args['S3_SOURCE_PREFIX']
        )
        local_path = download_dump_file(s3, args['S3_SOURCE_BUCKET'], latest_key)
        
        # Step 2: Parse dump file
        print("\nParsing SQL dump file...")
        statements = parse_dump_file(local_path)
        print(f"Parsed {len(statements)} SQL statements")
        
        # Step 3: Get database credentials
        username, password = get_aurora_credentials(secretsmanager, args['AURORA_SECRET_ARN'])
        
        # Step 4: Connect to Aurora and load data
        connection = pymysql.connect(
            host=args['AURORA_ENDPOINT'],
            user=username,
            password=password,
            database=args['AURORA_DATABASE'],
            charset='utf8mb4'
        )
        
        try:
            table_count, stmt_count = load_to_aurora_staging(connection, statements)
            
            # Step 5: Clean up empty tables
            dropped_count = cleanup_empty_staging_tables(connection)
            
        finally:
            connection.close()
        
        # Step 6: LLM Nationality Enrichment
        enriched_count = enrich_nationality_data()
        
        # Step 7: Archive processed dump
        archive_processed_dump(s3, args['S3_SOURCE_BUCKET'], latest_key)
        
        # Calculate duration
        duration = (datetime.now() - start_time).total_seconds()
        
        # Log success
        result = {
            'status': 'SUCCESS',
            'dump_key': latest_key,
            'table_count': table_count,
            'statements_executed': stmt_count,
            'empty_tables_dropped': dropped_count,
            'nationalities_enriched': enriched_count,
            'duration_seconds': int(duration)
        }
        
        print(f"\n{'='*60}")
        print("STAGING LOADER COMPLETED SUCCESSFULLY")
        print(f"Duration: {duration:.2f} seconds")
        print(f"Tables loaded: {table_count}")
        print(f"Empty tables dropped: {dropped_count}")
        print(f"Nationalities enriched: {enriched_count}")
        print(f"SQL statements executed: {stmt_count}")
        print(f"{'='*60}\n")
        
        # Output result for Step Functions
        print(f"RESULT_JSON: {json.dumps(result)}")
        
        job.commit()
        return result
        
    except Exception as e:
        print(f"\nERROR: Staging loader job failed: {str(e)}")
        import traceback
        traceback.print_exc()
        
        result = {
            'status': 'FAILED',
            'error': str(e),
            'error_type': type(e).__name__
        }
        print(f"RESULT_JSON: {json.dumps(result)}")
        
        job.commit()
        raise


if __name__ == "__main__":
    main()
