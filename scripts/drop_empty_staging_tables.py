#!/usr/bin/env python3
"""
Drop empty staging tables to clean up the database.
Safely removes tables with 0 rows.

Usage:
    # Dry run (default) - shows what would be dropped
    python3 drop_empty_staging_tables.py
    
    # Actually drop the tables
    python3 drop_empty_staging_tables.py --execute
"""

import subprocess
import sys
import argparse
from datetime import datetime

DB_HOST = "tokyobeta-prod-aurora-cluster-public.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com"
DB_USER = "admin"
DB_PASS = "K6ghcWTq4p-zlidRJ2<AJX<w$zN<a8dU"
DB_NAME = "tokyobeta"


def run_query(query, execute=False):
    """Run a MySQL query."""
    cmd = [
        'mysql',
        '-h', DB_HOST,
        '-u', DB_USER,
        f'-p{DB_PASS}',
        '-D', DB_NAME,
        '-N',
        '-e', query
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            print(f"Error: {result.stderr}", file=sys.stderr)
            return None
        return result.stdout.strip()
    except Exception as e:
        print(f"Error running query: {e}", file=sys.stderr)
        return None


def get_empty_tables():
    """Get all staging tables with 0 rows."""
    query = """
    SELECT 
        t.TABLE_NAME,
        t.TABLE_ROWS,
        t.CREATE_TIME,
        t.UPDATE_TIME,
        COALESCE(
            (SELECT COUNT(*) 
             FROM information_schema.COLUMNS c 
             WHERE c.TABLE_SCHEMA = 'staging' 
             AND c.TABLE_NAME = t.TABLE_NAME),
            0
        ) as column_count
    FROM information_schema.TABLES t
    WHERE t.TABLE_SCHEMA = 'staging'
    AND t.TABLE_ROWS = 0
    ORDER BY t.TABLE_NAME;
    """
    
    result = run_query(query)
    if not result:
        return []
    
    tables = []
    for line in result.split('\n'):
        if line:
            parts = line.split('\t')
            if len(parts) >= 4:
                tables.append({
                    'name': parts[0],
                    'rows': int(parts[1]) if parts[1] else 0,
                    'created': parts[2] if parts[2] else 'N/A',
                    'updated': parts[3] if parts[3] else 'N/A',
                    'columns': int(parts[4]) if len(parts) > 4 and parts[4] else 0
                })
    
    return tables


def verify_table_is_empty(table_name):
    """Double-check that a table is actually empty with exact count."""
    query = f"SELECT COUNT(*) FROM `staging`.`{table_name}`;"
    result = run_query(query)
    if result is None:
        return None
    return int(result) == 0


def drop_table(table_name, dry_run=True):
    """Drop a table (with dry-run support)."""
    if dry_run:
        print(f"  [DRY RUN] Would execute: DROP TABLE IF EXISTS `staging`.`{table_name}`;")
        return True
    
    query = f"DROP TABLE IF EXISTS `staging`.`{table_name}`;"
    result = run_query(query)
    return result is not None


def main():
    """Main execution."""
    parser = argparse.ArgumentParser(
        description='Drop empty staging tables',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (shows what would be dropped)
  python3 drop_empty_staging_tables.py
  
  # Actually drop the tables
  python3 drop_empty_staging_tables.py --execute
        """
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Actually drop the tables (default is dry-run)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Skip confirmation prompt (for automated runs)'
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("DROP EMPTY STAGING TABLES")
    print("=" * 80)
    print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {'EXECUTE' if args.execute else 'DRY RUN'}")
    print()
    
    if not args.execute:
        print("⚠️  DRY RUN MODE - No tables will be dropped")
        print("   Use --execute flag to actually drop tables")
        print()
    else:
        print("⚠️  EXECUTE MODE - Tables WILL be dropped!")
        print()
    
    # Get empty tables
    print("Finding empty tables...")
    empty_tables = get_empty_tables()
    
    if not empty_tables:
        print("✓ No empty tables found")
        return
    
    print(f"Found {len(empty_tables)} empty tables:")
    print()
    
    # List tables to be dropped
    print("Tables to drop:")
    print("-" * 80)
    for table in empty_tables:
        print(f"  • {table['name']:<40} ({table['columns']} columns)")
        print(f"    Created: {table['created']}, Updated: {table['updated']}")
    print()
    
    # If execute mode, ask for confirmation (unless --force)
    if args.execute and not args.force:
        print("=" * 80)
        print("⚠️  WARNING: You are about to DROP these tables permanently!")
        print("=" * 80)
        response = input(f"Type 'yes' to confirm dropping {len(empty_tables)} tables: ")
        if response.lower() != 'yes':
            print("Cancelled.")
            return
        print()
    elif args.execute and args.force:
        print("=" * 80)
        print("⚠️  FORCE MODE: Skipping confirmation (automated run)")
        print("=" * 80)
        print()
    
    # Verify and drop tables
    print("Processing tables...")
    print("-" * 80)
    
    dropped = []
    failed = []
    skipped = []
    
    for table in empty_tables:
        table_name = table['name']
        
        # Double-check it's actually empty
        is_empty = verify_table_is_empty(table_name)
        
        if is_empty is None:
            print(f"✗ {table_name}: Failed to verify")
            failed.append(table_name)
            continue
        
        if not is_empty:
            print(f"⊘ {table_name}: Skipped (not empty - has data now)")
            skipped.append(table_name)
            continue
        
        # Drop the table
        success = drop_table(table_name, dry_run=not args.execute)
        
        if success:
            print(f"✓ {table_name}: {'Would be dropped' if not args.execute else 'Dropped'}")
            dropped.append(table_name)
        else:
            print(f"✗ {table_name}: Failed")
            failed.append(table_name)
    
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total empty tables found: {len(empty_tables)}")
    print(f"{'Would be dropped' if not args.execute else 'Successfully dropped'}: {len(dropped)}")
    print(f"Skipped (not empty): {len(skipped)}")
    print(f"Failed: {len(failed)}")
    print()
    
    if not args.execute and dropped:
        print("=" * 80)
        print("TO EXECUTE:")
        print("=" * 80)
        print("python3 drop_empty_staging_tables.py --execute")
        print()
    
    # Generate documentation
    if args.execute and dropped:
        doc_file = f'/Users/danielkang/tokyobeta-data-consolidation/docs/DROPPED_TABLES_{datetime.now().strftime("%Y%m%d_%H%M%S")}.md'
        with open(doc_file, 'w') as f:
            f.write(f"# Dropped Empty Staging Tables\n\n")
            f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Executed by:** drop_empty_staging_tables.py\n\n")
            f.write(f"## Summary\n\n")
            f.write(f"- **Total tables dropped:** {len(dropped)}\n")
            f.write(f"- **Reason:** All tables had 0 rows\n\n")
            f.write(f"## Dropped Tables\n\n")
            for table_name in sorted(dropped):
                f.write(f"- `staging.{table_name}`\n")
            f.write(f"\n## Recovery\n\n")
            f.write(f"These tables will be recreated automatically on the next ETL run if they exist in the source SQL dump.\n")
            f.write(f"\nIf immediate recovery is needed, use Point-in-Time Recovery:\n")
            f.write(f"```bash\n")
            f.write(f"./scripts/rollback_etl.sh \"{datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}Z\"\n")
            f.write(f"```\n")
        
        print(f"Documentation saved to: {doc_file}")


if __name__ == "__main__":
    main()
