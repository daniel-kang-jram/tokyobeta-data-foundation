"""
Backfill Tenant Status Snapshots from Historical SQL Dumps

One-time script to process 127 daily SQL dumps from S3 (Oct 2025 - Feb 2026)
and extract tenant status snapshots for historical analysis.

For each dump:
1. Download tenants section using byte-range request (~100MB at bytes 760M-860M)
2. Extract CREATE TABLE + INSERT INTO statements
3. Load into temp Aurora table (let MySQL handle all SQL escaping natively)
4. Query and export snapshot: (tenant_id, status, contract_type, full_name, snapshot_date)
5. Upload CSV to s3://jram-gghouse/snapshots/tenant_status/YYYYMMDD.csv
6. Drop temp table

Usage:
    python backfill_tenant_snapshots.py \\
        --bucket jram-gghouse \\
        --aurora-endpoint tokyobeta-prod-aurora-cluster.cluster-xxx.ap-northeast-1.rds.amazonaws.com \\
        --aurora-database tokyobeta \\
        --secret-arn arn:aws:secretsmanager:...
"""

import argparse
import boto3
import pymysql
import json
import re
import logging
from datetime import date, datetime
from typing import List, Tuple, Dict, Any
from io import BytesIO
import csv
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ProgressTracker:
    """Track processing progress to enable resume on failure."""
    
    def __init__(self, progress_file: str = '/tmp/backfill_progress.json'):
        self.progress_file = progress_file
        self.completed = self._load_progress()
    
    def _load_progress(self) -> Dict[str, Any]:
        """Load progress from file."""
        try:
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {'completed_dumps': [], 'rows_by_dump': {}}
    
    def _save_progress(self):
        """Save progress to file."""
        with open(self.progress_file, 'w') as f:
            json.dump(self.completed, f, indent=2)
    
    def is_complete(self, dump_key: str) -> bool:
        """Check if dump has been processed."""
        return dump_key in self.completed['completed_dumps']
    
    def mark_complete(self, dump_key: str, row_count: int):
        """Mark dump as processed."""
        self.completed['completed_dumps'].append(dump_key)
        self.completed['rows_by_dump'][dump_key] = row_count
        self._save_progress()


def list_dump_files(s3_client, bucket: str, prefix: str = 'dumps/') -> List[str]:
    """
    List all SQL dump files from S3.
    
    Returns:
        List of S3 keys sorted by date
    """
    logger.info(f"Listing dumps from s3://{bucket}/{prefix}")
    
    paginator = s3_client.get_paginator('list_objects_v2')
    dump_files = []
    
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        if 'Contents' not in page:
            continue
        
        for obj in page['Contents']:
            key = obj['Key']
            # Filter for gghouse_YYYYMMDD.sql pattern
            if re.match(r'.*gghouse_\d{8}\.sql$', key):
                dump_files.append(key)
    
    # Sort by date (embedded in filename)
    dump_files.sort()
    
    logger.info(f"Found {len(dump_files)} dump files")
    return dump_files


def extract_date_from_filename(dump_key: str) -> date:
    """
    Extract date from dump filename.
    
    Args:
        dump_key: S3 key like 'dumps/gghouse_20251001.sql'
    
    Returns:
        date object
    """
    match = re.search(r'gghouse_(\d{8})\.sql', dump_key)
    if not match:
        raise ValueError(f"Cannot extract date from filename: {dump_key}")
    
    date_str = match.group(1)
    return datetime.strptime(date_str, '%Y%m%d').date()


def download_tenants_section(s3_client, bucket: str, key: str) -> bytes:
    """
    Download only the tenants table section using byte-range request.
    
    For smaller dumps (<700MB), downloads entire file.
    For larger dumps, uses byte-range request starting at 600MB.
    
    Args:
        s3_client: Boto3 S3 client
        bucket: S3 bucket name
        key: S3 object key
    
    Returns:
        Bytes content of tenants section
    """
    logger.info(f"Downloading tenants section from s3://{bucket}/{key}")
    
    # Get file size first
    head_response = s3_client.head_object(Bucket=bucket, Key=key)
    file_size = head_response['ContentLength']
    logger.debug(f"File size: {file_size:,} bytes ({file_size/1024/1024:.1f} MB)")
    
    # If file is small (<700MB), download entire file
    # Otherwise, download last 200MB where tenants table is located
    if file_size < 700 * 1024 * 1024:
        logger.debug("Small file - downloading entire content")
        response = s3_client.get_object(Bucket=bucket, Key=key)
    else:
        # For larger files, download from 600MB to end
        start_byte = 600 * 1024 * 1024
        logger.debug(f"Large file - downloading bytes {start_byte:,} to end")
        response = s3_client.get_object(
            Bucket=bucket,
            Key=key,
            Range=f'bytes={start_byte}-'
        )
    
    content = response['Body'].read()
    logger.debug(f"Downloaded {len(content):,} bytes")
    
    return content


def extract_create_table_statement(content: str, table_name: str = 'tenants') -> str:
    """
    Extract CREATE TABLE statement for specified table.
    
    Args:
        content: SQL dump content
        table_name: Table to extract
    
    Returns:
        CREATE TABLE statement
    """
    # Find CREATE TABLE block
    pattern = rf'CREATE TABLE `{table_name}` \((.*?)\) ENGINE=InnoDB'
    match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
    
    if not match:
        raise ValueError(f"CREATE TABLE for {table_name} not found")
    
    # Return full statement
    return match.group(0) + ';'


def extract_insert_statements(content: str, table_name: str = 'tenants') -> List[str]:
    """
    Extract all INSERT INTO statements for specified table.
    
    Args:
        content: SQL dump content
        table_name: Table to extract
    
    Returns:
        List of INSERT statements
    """
    statements = []
    
    # Pattern to match INSERT INTO statements (may span multiple lines)
    pattern = rf'INSERT INTO `{table_name}` VALUES .*?;'
    matches = re.finditer(pattern, content, re.DOTALL | re.IGNORECASE)
    
    for match in matches:
        statements.append(match.group(0))
    
    logger.debug(f"Extracted {len(statements)} INSERT statements for {table_name}")
    return statements


def get_aurora_credentials(secrets_client, secret_arn: str) -> Tuple[str, str]:
    """Retrieve Aurora credentials from Secrets Manager."""
    response = secrets_client.get_secret_value(SecretId=secret_arn)
    secret = json.loads(response['SecretString'])
    return secret['username'], secret['password']


def create_temp_table(cursor, create_stmt: str, temp_table_name: str = '_tmp_tenants_snapshot'):
    """
    Create temporary table in Aurora.
    
    Args:
        cursor: Database cursor
        create_stmt: CREATE TABLE statement
        temp_table_name: Name for temp table
    """
    # Drop if exists
    cursor.execute(f"DROP TABLE IF EXISTS staging.{temp_table_name}")
    
    # Replace table name and execute
    temp_create_stmt = create_stmt.replace('`tenants`', f'`{temp_table_name}`')
    cursor.execute(temp_create_stmt)
    
    logger.debug(f"Created temp table: staging.{temp_table_name}")


def load_data_into_temp_table(
    conn,
    cursor,
    insert_stmts: List[str],
    temp_table_name: str = '_tmp_tenants_snapshot'
):
    """
    Load INSERT statements into temp table.
    
    Args:
        conn: Database connection
        cursor: Database cursor
        insert_stmts: List of INSERT statements
        temp_table_name: Target temp table
    """
    logger.info(f"Loading {len(insert_stmts)} INSERT statements into {temp_table_name}")
    
    for i, stmt in enumerate(insert_stmts):
        # Replace table name
        temp_stmt = stmt.replace('`tenants`', f'`{temp_table_name}`')
        
        try:
            cursor.execute(temp_stmt)
            
            if (i + 1) % 10 == 0:
                logger.debug(f"Progress: {i + 1}/{len(insert_stmts)} statements")
        
        except Exception as e:
            logger.warning(f"Failed to execute INSERT #{i}: {str(e)[:200]}")
            continue
    
    conn.commit()
    logger.info(f"Loaded data into {temp_table_name}")


def extract_snapshot_from_temp_table(
    cursor,
    temp_table_name: str,
    snapshot_date: date
) -> List[Tuple[int, int, int, str, date]]:
    """
    Extract snapshot data from temp table.
    
    Args:
        cursor: Database cursor
        temp_table_name: Temp table name
        snapshot_date: Date for this snapshot
    
    Returns:
        List of tuples: (tenant_id, status, contract_type, full_name, snapshot_date)
    """
    query = f"""
        SELECT 
            id AS tenant_id,
            status,
            contract_type,
            full_name
        FROM staging.{temp_table_name}
        ORDER BY id
    """
    
    cursor.execute(query)
    rows = cursor.fetchall()
    
    # Add snapshot_date to each row
    snapshot_rows = [
        (row[0], row[1], row[2], row[3], snapshot_date)
        for row in rows
    ]
    
    logger.info(f"Extracted {len(snapshot_rows)} tenant records for {snapshot_date}")
    return snapshot_rows


def validate_snapshot_data(rows: List[Tuple]):
    """
    Validate snapshot data quality.
    
    Args:
        rows: Snapshot rows
    
    Raises:
        ValueError: If validation fails
    """
    if not rows:
        raise ValueError("No snapshot data to validate")
    
    for i, row in enumerate(rows):
        tenant_id, status, contract_type, full_name, snapshot_date = row
        
        if tenant_id is None:
            raise ValueError(f"Row {i}: tenant_id is NULL")
        
        if status is None:
            raise ValueError(f"Row {i}: status is NULL for tenant_id={tenant_id}")
        
        if contract_type is None:
            raise ValueError(f"Row {i}: contract_type is NULL for tenant_id={tenant_id}")
    
    logger.debug(f"Validated {len(rows)} rows")


def deduplicate_snapshots(rows: List[Tuple]) -> List[Tuple]:
    """
    Deduplicate tenant_ids, keeping the last occurrence.
    
    Args:
        rows: Snapshot rows
    
    Returns:
        Deduplicated rows
    """
    seen = {}
    for row in rows:
        tenant_id = row[0]
        seen[tenant_id] = row
    
    deduplicated = list(seen.values())
    
    if len(deduplicated) < len(rows):
        logger.warning(f"Deduplicated {len(rows)} -> {len(deduplicated)} rows")
    
    return deduplicated


def generate_csv_content(rows: List[Tuple]) -> str:
    """
    Generate CSV content from snapshot rows.
    
    Args:
        rows: Snapshot rows (tenant_id, status, contract_type, full_name, snapshot_date)
    
    Returns:
        CSV string with header
    """
    from io import StringIO
    output = StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['tenant_id', 'status', 'contract_type', 'full_name', 'snapshot_date'])
    
    # Data rows
    for row in rows:
        writer.writerow(row)
    
    return output.getvalue()


def upload_snapshot_to_s3(
    s3_client,
    bucket: str,
    csv_content: str,
    snapshot_date: date,
    prefix: str = 'snapshots/tenant_status/'
):
    """
    Upload snapshot CSV to S3.
    
    Args:
        s3_client: Boto3 S3 client
        bucket: S3 bucket
        csv_content: CSV string content
        snapshot_date: Date for snapshot
        prefix: S3 prefix
    """
    date_str = snapshot_date.strftime('%Y%m%d')
    key = f"{prefix}{date_str}.csv"
    
    logger.info(f"Uploading snapshot to s3://{bucket}/{key}")
    
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=csv_content.encode('utf-8'),
        ContentType='text/csv'
    )
    
    logger.info(f"Uploaded {len(csv_content):,} bytes to s3://{bucket}/{key}")


def process_dump_file(
    dump_key: str,
    bucket: str,
    aurora_endpoint: str,
    aurora_database: str,
    secret_arn: str,
    s3_client=None,
    secrets_client=None
) -> Dict[str, Any]:
    """
    Process a single dump file end-to-end.
    
    Args:
        dump_key: S3 key for dump file
        bucket: S3 bucket
        aurora_endpoint: Aurora cluster endpoint
        aurora_database: Database name
        secret_arn: Secrets Manager ARN for credentials
        s3_client: Optional boto3 S3 client (for testing)
        secrets_client: Optional boto3 Secrets Manager client (for testing)
    
    Returns:
        Result dict with status and metrics
    """
    logger.info("="*60)
    logger.info(f"Processing: {dump_key}")
    logger.info("="*60)
    
    try:
        # Initialize clients if not provided
        if s3_client is None:
            s3_client = boto3.client('s3', region_name='ap-northeast-1')
        if secrets_client is None:
            secrets_client = boto3.client('secretsmanager', region_name='ap-northeast-1')
        
        # Extract snapshot date from filename
        snapshot_date = extract_date_from_filename(dump_key)
        logger.info(f"Snapshot date: {snapshot_date}")
        
        # Step 1: Download tenants section
        content_bytes = download_tenants_section(s3_client, bucket, dump_key)
        content = content_bytes.decode('utf-8', errors='ignore')
        
        # Step 2: Extract SQL statements
        create_stmt = extract_create_table_statement(content)
        insert_stmts = extract_insert_statements(content)
        
        if not insert_stmts:
            logger.warning(f"No INSERT statements found in {dump_key}")
            return {
                'status': 'skipped',
                'reason': 'no_inserts',
                'snapshot_date': snapshot_date
            }
        
        # Step 3: Load into Aurora temp table
        username, password = get_aurora_credentials(secrets_client, secret_arn)
        
        connection = pymysql.connect(
            host=aurora_endpoint,
            user=username,
            password=password,
            database=aurora_database,
            charset='utf8mb4'
        )
        
        try:
            with connection.cursor() as cursor:
                temp_table = f'_tmp_tenants_{snapshot_date.strftime("%Y%m%d")}'
                
                # Ensure staging schema exists
                cursor.execute("CREATE SCHEMA IF NOT EXISTS staging")
                cursor.execute("USE staging")
                
                # Create and load temp table
                create_temp_table(cursor, create_stmt, temp_table)
                load_data_into_temp_table(connection, cursor, insert_stmts, temp_table)
                
                # Step 4: Extract snapshot data
                snapshot_rows = extract_snapshot_from_temp_table(cursor, temp_table, snapshot_date)
                
                # Step 5: Validate and deduplicate
                validate_snapshot_data(snapshot_rows)
                snapshot_rows = deduplicate_snapshots(snapshot_rows)
                
                # Step 6: Drop temp table
                cursor.execute(f"DROP TABLE IF EXISTS staging.{temp_table}")
                connection.commit()
        
        finally:
            connection.close()
        
        # Step 7: Generate CSV and upload to S3
        csv_content = generate_csv_content(snapshot_rows)
        upload_snapshot_to_s3(s3_client, bucket, csv_content, snapshot_date)
        
        logger.info(f"✓ Successfully processed {dump_key}: {len(snapshot_rows)} rows")
        
        return {
            'status': 'success',
            'snapshot_date': snapshot_date,
            'rows_processed': len(snapshot_rows),
            'dump_key': dump_key
        }
    
    except Exception as e:
        logger.error(f"✗ Failed to process {dump_key}: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            'status': 'failed',
            'dump_key': dump_key,
            'error': str(e)
        }


def get_dumps_to_process(all_dumps: List[str], completed_dumps: List[str]) -> List[str]:
    """Get list of dumps that still need processing."""
    return [d for d in all_dumps if d not in completed_dumps]


def backfill_all_dumps(
    s3_client,
    connection,
    bucket: str,
    dump_keys: List[str],
    progress_tracker: ProgressTracker = None
) -> Dict[str, Any]:
    """
    Process all dump files with progress tracking.
    
    Args:
        s3_client: Boto3 S3 client
        connection: Database connection (for testing)
        bucket: S3 bucket
        dump_keys: List of dump keys to process
        progress_tracker: Optional progress tracker
    
    Returns:
        Summary dict
    """
    if progress_tracker is None:
        progress_tracker = ProgressTracker()
    
    # Filter out already completed dumps
    completed = progress_tracker.completed['completed_dumps']
    to_process = get_dumps_to_process(dump_keys, completed)
    
    logger.info(f"Total dumps: {len(dump_keys)}")
    logger.info(f"Already completed: {len(completed)}")
    logger.info(f"To process: {len(to_process)}")
    
    results = {
        'total_dumps': len(dump_keys),
        'successful': len(completed),
        'failed': 0,
        'skipped': 0
    }
    
    for i, dump_key in enumerate(to_process, 1):
        logger.info(f"\nProgress: {i}/{len(to_process)} ({i/len(to_process)*100:.1f}%)")
        
        result = process_dump_file(
            dump_key=dump_key,
            bucket=bucket,
            aurora_endpoint=connection.get_host_info() if hasattr(connection, 'get_host_info') else 'localhost',
            aurora_database='tokyobeta',
            secret_arn='',
            s3_client=s3_client
        )
        
        if result['status'] == 'success':
            progress_tracker.mark_complete(dump_key, result['rows_processed'])
            results['successful'] += 1
        elif result['status'] == 'failed':
            results['failed'] += 1
        else:
            results['skipped'] += 1
    
    return results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Backfill tenant status snapshots from historical SQL dumps'
    )
    parser.add_argument('--bucket', required=True, help='S3 bucket name')
    parser.add_argument('--aurora-endpoint', required=True, help='Aurora cluster endpoint')
    parser.add_argument('--aurora-database', default='tokyobeta', help='Database name')
    parser.add_argument('--secret-arn', required=True, help='Secrets Manager ARN for Aurora credentials')
    parser.add_argument('--dry-run', action='store_true', help='List dumps without processing')
    parser.add_argument('--resume', action='store_true', help='Resume from previous run')
    parser.add_argument('--progress-file', default='/tmp/backfill_progress.json', help='Progress file path')
    
    args = parser.parse_args()
    
    # Initialize clients
    s3_client = boto3.client('s3', region_name='ap-northeast-1')
    secrets_client = boto3.client('secretsmanager', region_name='ap-northeast-1')
    
    # List all dump files
    dump_files = list_dump_files(s3_client, args.bucket)
    
    if args.dry_run:
        logger.info("\n=== DRY RUN: Dumps to process ===")
        for dump in dump_files:
            snapshot_date = extract_date_from_filename(dump)
            logger.info(f"  {dump} -> {snapshot_date}")
        logger.info(f"\nTotal: {len(dump_files)} dumps")
        return
    
    # Initialize progress tracker
    progress_tracker = ProgressTracker(args.progress_file)
    
    if args.resume:
        completed = progress_tracker.completed['completed_dumps']
        logger.info(f"Resuming: {len(completed)} dumps already completed")
    
    # Get Aurora credentials
    username, password = get_aurora_credentials(secrets_client, args.secret_arn)
    
    # Process all dumps
    start_time = datetime.now()
    logger.info("\n" + "="*60)
    logger.info("BACKFILL START")
    logger.info("="*60)
    
    successful = 0
    failed = 0
    skipped = 0
    
    for i, dump_key in enumerate(dump_files, 1):
        # Skip if already processed (resume mode)
        if args.resume and progress_tracker.is_complete(dump_key):
            logger.info(f"[{i}/{len(dump_files)}] Skipping {dump_key} (already processed)")
            skipped += 1
            continue
        
        logger.info(f"\n[{i}/{len(dump_files)}] Processing: {dump_key}")
        
        result = process_dump_file(
            dump_key=dump_key,
            bucket=args.bucket,
            aurora_endpoint=args.aurora_endpoint,
            aurora_database=args.aurora_database,
            secret_arn=args.secret_arn,
            s3_client=s3_client,
            secrets_client=secrets_client
        )
        
        if result['status'] == 'success':
            progress_tracker.mark_complete(dump_key, result['rows_processed'])
            successful += 1
        elif result['status'] == 'failed':
            failed += 1
        else:
            skipped += 1
    
    # Summary
    duration = (datetime.now() - start_time).total_seconds()
    
    logger.info("\n" + "="*60)
    logger.info("BACKFILL COMPLETE")
    logger.info("="*60)
    logger.info(f"Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
    logger.info(f"Total dumps: {len(dump_files)}")
    logger.info(f"Successful: {successful}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Skipped: {skipped}")
    logger.info(f"Progress file: {args.progress_file}")
    
    if failed > 0:
        logger.warning(f"\n⚠ {failed} dumps failed - review logs above")
        sys.exit(1)
    
    logger.info("\n✓ Backfill completed successfully")
    logger.info(f"Snapshot CSVs saved to s3://{args.bucket}/snapshots/tenant_status/")


if __name__ == '__main__':
    main()
