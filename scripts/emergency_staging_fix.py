#!/usr/bin/env python3
"""
EMERGENCY STAGING FIX SCRIPT
=============================
Manually loads dumps from S3 to fix staging.movings, staging.rooms, staging.inquiries staleness.

This script:
1. Downloads latest dumps from S3 (jram-gghouse bucket)
2. Loads them into staging schema  
3. Updates the 8-day gap (Feb 3-10, 2026)

USAGE:
    python3 scripts/emergency_staging_fix.py --tables movings rooms inquiries

REQUIREMENTS:
    - AWS credentials with S3 read access to jram-gghouse
    - Database credentials (uses hardcoded from analyze_staging_activity.py)
    - boto3, pymysql libraries
"""

import argparse
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import boto3
import pymysql

# S3 Configuration
S3_BUCKET = "jram-gghouse"
S3_PREFIX = "dumps/"

# Database Configuration (from analyze_staging_activity.py)
DB_CONFIG = {
    "host": "tokyobeta-prod-aurora-cluster-public.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com",
    "port": 3306,
    "user": "admin",
    "password": "K6ghcWTq4p-zlidRJ2<AJX<w$zN<a8dU",
    "database": "tokyobeta",
    "charset": "utf8mb4",
}

# Target tables to fix
TARGET_TABLES = {"movings", "rooms", "inquiries", "tenants", "apartments"}


def normalize_statement(stmt: str) -> str:
    """Normalize SQL statement and skip session-level commands."""
    stmt = stmt.strip()
    if not stmt:
        return ""
    
    # Skip session-level commands
    if re.match(r"^(SET|LOCK TABLES|UNLOCK TABLES)", stmt, re.IGNORECASE):
        return ""
    
    # Skip database commands (we set schema explicitly)
    if stmt.upper().startswith("CREATE DATABASE") or stmt.upper().startswith("USE "):
        return ""
    
    # Skip CREATE/DROP DATABASE
    if "CREATE DATABASE" in stmt.upper() or "DROP DATABASE" in stmt.upper():
        return ""
    
    return stmt


def extract_table_name(stmt: str) -> str | None:
    """Extract table name from SQL statement."""
    # Match CREATE TABLE, INSERT INTO, or DROP TABLE
    match = re.match(
        r"^(CREATE TABLE|INSERT INTO|DROP TABLE IF EXISTS|DROP TABLE)\s+`?(\w+)`?",
        stmt,
        re.IGNORECASE
    )
    if not match:
        return None
    return match.group(2)


def rewrite_statement(stmt: str, table_name: str, schema: str = "staging") -> str:
    """Rewrite statement to target the staging schema."""
    # Replace table name with schema.table
    stmt = re.sub(
        rf"^(CREATE TABLE|INSERT INTO|DROP TABLE IF EXISTS|DROP TABLE)\s+`?{table_name}`?",
        rf"\1 `{schema}`.`{table_name}`",
        stmt,
        flags=re.IGNORECASE,
    )
    return stmt


def download_latest_dump(s3_client, table_name: str) -> Path:
    """Download latest dump file for a table from S3."""
    print(f"\n🔍 Searching for {table_name} dumps in S3...")
    
    try:
        # List all objects with the table name prefix
        response = s3_client.list_objects_v2(
            Bucket=S3_BUCKET,
            Prefix=f"{S3_PREFIX}{table_name}"
        )
        
        if 'Contents' not in response:
            print(f"  ❌ No dumps found for {table_name}")
            return None
        
        # Sort by LastModified descending (most recent first)
        objects = sorted(response['Contents'], key=lambda x: x['LastModified'], reverse=True)
        
        if not objects:
            print(f"  ❌ No dumps found for {table_name}")
            return None
        
        latest = objects[0]
        print(f"  ✅ Found: {latest['Key']}")
        print(f"     Last Modified: {latest['LastModified']}")
        print(f"     Size: {latest['Size'] / (1024*1024):.2f} MB")
        
        # Download to temp file
        temp_file = tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.sql')
        temp_path = Path(temp_file.name)
        
        print(f"  📥 Downloading to {temp_path}...")
        s3_client.download_file(S3_BUCKET, latest['Key'], str(temp_path))
        print(f"  ✅ Downloaded successfully")
        
        return temp_path
        
    except Exception as e:
        print(f"  ❌ Error downloading {table_name}: {e}")
        return None


def backup_table(cursor, table_name: str):
    """Create a backup of the table before updating."""
    backup_name = f"staging.{table_name}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"  💾 Creating backup: {backup_name}")
    
    try:
        cursor.execute(f"CREATE TABLE {backup_name} AS SELECT * FROM staging.{table_name}")
        row_count = cursor.execute(f"SELECT COUNT(*) FROM {backup_name}")
        cursor.fetchone()
        print(f"  ✅ Backup created with {row_count} rows")
        return backup_name
    except Exception as e:
        print(f"  ⚠️ Backup failed: {e}")
        return None


def load_dump_file(connection, dump_path: Path, table_name: str, dry_run: bool = False):
    """Load a dump file into the staging schema."""
    print(f"\n📂 Loading {table_name} from {dump_path}")
    
    cursor = connection.cursor()
    
    # Create backup first
    if not dry_run:
        backup_name = backup_table(cursor, table_name)
    
    # Set MySQL modes for compatibility
    cursor.execute("SET SESSION sql_mode = 'ALLOW_INVALID_DATES'")
    cursor.execute("SET NAMES utf8mb4")
    
    # Drop and recreate table
    if not dry_run:
        print(f"  🗑️ Dropping staging.{table_name}...")
        cursor.execute(f"DROP TABLE IF EXISTS staging.{table_name}")
    
    statement = []
    statements_executed = 0
    inserts_executed = 0
    
    print(f"  📖 Reading dump file...")
    
    with open(dump_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line_num, line in enumerate(f, 1):
            statement.append(line)
            
            # Check if statement is complete
            if line.rstrip().endswith(';'):
                raw_stmt = ''.join(statement)
                statement = []
                
                stmt = normalize_statement(raw_stmt)
                if not stmt:
                    continue
                
                # Extract and check table name
                stmt_table = extract_table_name(stmt)
                if stmt_table and stmt_table.lower() != table_name.lower():
                    continue
                
                # Rewrite to use staging schema
                if stmt_table:
                    stmt = rewrite_statement(stmt, stmt_table, "staging")
                
                # Execute statement
                if not dry_run:
                    try:
                        cursor.execute(stmt)
                        statements_executed += 1
                        
                        if stmt.upper().startswith("INSERT"):
                            inserts_executed += 1
                            if inserts_executed % 1000 == 0:
                                print(f"    Loaded {inserts_executed} batches...")
                                connection.commit()
                    except Exception as e:
                        print(f"  ⚠️ Error at line {line_num}: {e}")
                        print(f"     Statement: {stmt[:200]}...")
                else:
                    statements_executed += 1
                    if stmt.upper().startswith("INSERT"):
                        inserts_executed += 1
    
    if not dry_run:
        connection.commit()
    
    # Get final row count
    if not dry_run:
        cursor.execute(f"SELECT COUNT(*) FROM staging.{table_name}")
        row_count = cursor.fetchone()[0]
        cursor.execute(f"SELECT MAX(updated_at) FROM staging.{table_name}")
        last_updated = cursor.fetchone()[0]
        
        print(f"\n  ✅ {table_name} loaded successfully!")
        print(f"     Total rows: {row_count:,}")
        print(f"     Last updated: {last_updated}")
        print(f"     Statements executed: {statements_executed}")
        print(f"     Insert batches: {inserts_executed}")
    else:
        print(f"\n  ℹ️ DRY RUN: Would have executed {statements_executed} statements ({inserts_executed} inserts)")


def check_staleness(connection):
    """Check current staleness of staging tables."""
    cursor = connection.cursor()
    
    print("\n📊 Current Staging Table Status:")
    print("=" * 80)
    
    tables = ["tenants", "movings", "rooms", "inquiries", "apartments"]
    for table in tables:
        try:
            cursor.execute(f"""
                SELECT 
                    COUNT(*) as row_count,
                    MAX(updated_at) as last_updated,
                    DATEDIFF(CURRENT_DATE, DATE(MAX(updated_at))) as days_old
                FROM staging.{table}
            """)
            row_count, last_updated, days_old = cursor.fetchone()
            
            status = "✅" if days_old < 2 else "⚠️" if days_old < 5 else "🔴"
            print(f"{status} staging.{table:15s} | {row_count:7,} rows | Last: {last_updated} ({days_old} days old)")
        except Exception as e:
            print(f"❌ staging.{table:15s} | Error: {e}")
    
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Emergency staging fix - load dumps from S3")
    parser.add_argument(
        '--tables',
        nargs='+',
        choices=list(TARGET_TABLES),
        default=['movings', 'rooms', 'inquiries'],
        help='Tables to reload (default: movings rooms inquiries)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Dry run - show what would be done without executing'
    )
    parser.add_argument(
        '--check-only',
        action='store_true',
        help='Only check current staleness, do not load'
    )
    
    args = parser.parse_args()
    
    print("🚨 EMERGENCY STAGING FIX SCRIPT")
    print("=" * 80)
    print(f"Target: {', '.join(args.tables)}")
    print(f"S3 Bucket: {S3_BUCKET}")
    print(f"S3 Prefix: {S3_PREFIX}")
    print(f"Database: {DB_CONFIG['host']}")
    print("=" * 80)
    
    # Connect to database
    print("\n🔌 Connecting to database...")
    try:
        connection = pymysql.connect(**DB_CONFIG)
        print("  ✅ Connected successfully")
    except Exception as e:
        print(f"  ❌ Connection failed: {e}")
        sys.exit(1)
    
    # Check current staleness
    check_staleness(connection)
    
    if args.check_only:
        print("\n✅ Check complete (--check-only mode)")
        return
    
    # Initialize S3 client
    print("\n☁️ Initializing S3 client...")
    try:
        s3_client = boto3.client('s3', region_name='ap-northeast-1')
        print("  ✅ S3 client initialized")
    except Exception as e:
        print(f"  ❌ S3 initialization failed: {e}")
        sys.exit(1)
    
    # Process each table
    for table in args.tables:
        print(f"\n{'='*80}")
        print(f"Processing: {table}")
        print(f"{'='*80}")
        
        # Download latest dump
        dump_path = download_latest_dump(s3_client, table)
        if not dump_path:
            print(f"  ⚠️ Skipping {table} - no dump file found")
            continue
        
        # Load dump
        try:
            load_dump_file(connection, dump_path, table, dry_run=args.dry_run)
        except Exception as e:
            print(f"  ❌ Error loading {table}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Clean up temp file
            if dump_path and dump_path.exists():
                dump_path.unlink()
    
    # Final staleness check
    check_staleness(connection)
    
    connection.close()
    
    print("\n✅ Emergency fix completed!")
    print("\nNext steps:")
    print("1. Verify tables are fresh (< 1 day old)")
    print("2. Re-run downstream models (silver, gold)")
    print("3. Re-deploy tokyo_beta_tenant_room_info table")
    print("4. Set up Terraform Glue infrastructure for automated loads")


if __name__ == "__main__":
    main()
