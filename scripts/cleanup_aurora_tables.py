#!/usr/bin/env python3
"""
Cleanup Aurora Tables Script
Removes unused tables and excessive backups from Aurora MySQL.

Actions:
1. Drop silver.tenant_status_history (not used, slow to build)
2. Drop gold.tenant_status_transitions (depends on history table)
3. Delete all old _backup_ naming tables
4. Clean up _bak_ tables (keep only last 3 per table)
"""

import pymysql
import boto3
import json
import argparse
from datetime import datetime


def get_aurora_credentials():
    """Get Aurora credentials from Secrets Manager."""
    import os
    secret_arn = "arn:aws:secretsmanager:ap-northeast-1:343881458651:secret:tokyobeta/prod/aurora/credentials-tlWiUd"
    
    # Use profile from environment or default to gghouse
    session = boto3.Session(profile_name=os.environ.get('AWS_PROFILE', 'gghouse'))
    client = session.client('secretsmanager', region_name='ap-northeast-1')
    response = client.get_secret_value(SecretId=secret_arn)
    secret = json.loads(response['SecretString'])
    
    return secret['username'], secret['password']


def drop_unused_tables(connection):
    """Drop unused tables from Aurora."""
    cursor = connection.cursor()
    
    print("\n=== Dropping Unused Tables ===")
    
    tables_to_drop = [
        'silver.tenant_status_history',
        'gold.tenant_status_transitions'
    ]
    
    dropped = []
    
    for table_ref in tables_to_drop:
        schema, table_name = table_ref.split('.')
        
        try:
            cursor.execute(f"SHOW TABLES FROM {schema} LIKE '{table_name}'")
            if cursor.fetchone():
                cursor.execute(f"DROP TABLE {schema}.{table_name}")
                print(f"  ✓ Dropped {schema}.{table_name}")
                dropped.append(table_ref)
            else:
                print(f"  ⊘ {schema}.{table_name} does not exist (already removed)")
        except Exception as e:
            print(f"  ✗ Failed to drop {schema}.{table_name}: {str(e)}")
    
    connection.commit()
    cursor.close()
    
    return dropped


def drop_old_backup_naming(connection):
    """
    Drop all tables with old _backup_YYYYMMDD_HHMMSS naming convention.
    New convention is _bak_YYYYMMDD_HHMMSS.
    """
    cursor = connection.cursor()
    
    print("\n=== Deleting Old _backup_ Naming Tables ===")
    
    removed = 0
    for schema in ['silver', 'gold']:
        cursor.execute(f"""
            SELECT TABLE_NAME 
            FROM information_schema.TABLES 
            WHERE TABLE_SCHEMA = '{schema}' 
            AND TABLE_NAME LIKE '%_backup_%'
            ORDER BY TABLE_NAME
        """)
        old_backups = [row[0] for row in cursor.fetchall()]
        
        for table_name in old_backups:
            try:
                cursor.execute(f"DROP TABLE IF EXISTS {schema}.{table_name}")
                print(f"  ✓ Dropped {schema}.{table_name}")
                removed += 1
            except Exception as e:
                print(f"  ✗ Failed to drop {table_name}: {str(e)}")
    
    connection.commit()
    cursor.close()
    return removed


def cleanup_backup_tables(connection, keep_count=3):
    """
    Clean up _bak_ backup tables, keeping only the last N per table.
    
    Args:
        connection: pymysql connection
        keep_count: Number of backups to keep per table (default: 3)
    """
    cursor = connection.cursor()
    
    print(f"\n=== Cleaning Up _bak_ Backup Tables (keeping last {keep_count}) ===")
    
    removed_count = 0
    
    for schema in ['silver', 'gold']:
        # Get only _bak_ tables (new naming)
        cursor.execute(f"""
            SELECT TABLE_NAME 
            FROM information_schema.TABLES 
            WHERE TABLE_SCHEMA = '{schema}' 
            AND TABLE_NAME LIKE '%_bak_%'
            ORDER BY TABLE_NAME
        """)
        
        all_backups = [row[0] for row in cursor.fetchall()]
        
        # Group by base table name
        backup_groups = {}
        for backup_name in all_backups:
            base_name = backup_name.split('_bak_')[0]
            if base_name not in backup_groups:
                backup_groups[base_name] = []
            backup_groups[base_name].append(backup_name)
        
        # For each table, keep only last N backups
        for base_name, backups in backup_groups.items():
            backups.sort(reverse=True)  # Most recent first
            
            if len(backups) > keep_count:
                to_remove = backups[keep_count:]
                print(f"\n  {schema}.{base_name}: {len(backups)} backups found, removing {len(to_remove)}")
                
                for old_backup in to_remove:
                    try:
                        cursor.execute(f"DROP TABLE IF EXISTS {schema}.{old_backup}")
                        print(f"    ✓ Dropped {schema}.{old_backup}")
                        removed_count += 1
                    except Exception as e:
                        print(f"    ✗ Failed to drop {old_backup}: {str(e)}")
            else:
                print(f"  {schema}.{base_name}: {len(backups)} backups (OK)")
    
    connection.commit()
    cursor.close()
    
    print(f"\n✓ Cleanup complete: {removed_count} old backups removed")
    return removed_count


def main():
    parser = argparse.ArgumentParser(description='Cleanup Aurora tables')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--keep-backups', type=int, default=3, help='Number of backups to keep per table (default: 3)')
    
    args = parser.parse_args()
    
    print("="*60)
    print("AURORA TABLE CLEANUP SCRIPT")
    print(f"Timestamp: {datetime.now().isoformat()}")
    if args.dry_run:
        print("MODE: DRY RUN (no changes will be made)")
    print("="*60)
    
    # Get credentials
    print("\nRetrieving Aurora credentials...")
    username, password = get_aurora_credentials()
    
    # Connect
    print("Connecting to Aurora...")
    connection = pymysql.connect(
        host='tokyobeta-prod-aurora-cluster-public.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com',
        user=username,
        password=password,
        database='tokyobeta',
        charset='utf8mb4'
    )
    
    try:
        if args.dry_run:
            cursor = connection.cursor()
            
            # Show what would be dropped
            print("\n=== Would Drop Unused Tables ===")
            for table_ref in ['silver.tenant_status_history', 'gold.tenant_status_transitions']:
                schema, table_name = table_ref.split('.')
                cursor.execute(f"SHOW TABLES FROM {schema} LIKE '{table_name}'")
                if cursor.fetchone():
                    print(f"  - {schema}.{table_name}")
            
            # Show old naming deletion
            print("\n=== Would Delete Old _backup_ Tables ===")
            for schema in ['silver', 'gold']:
                cursor.execute(f"""
                    SELECT TABLE_NAME FROM information_schema.TABLES 
                    WHERE TABLE_SCHEMA = '{schema}' AND TABLE_NAME LIKE '%_backup_%'
                """)
                old = [row[0] for row in cursor.fetchall()]
                for t in old:
                    print(f"  - {schema}.{t}")
            
            # Show backup cleanup
            print(f"\n=== Would Clean Up _bak_ Backups (keep last {args.keep_backups}) ===")
            for schema in ['silver', 'gold']:
                cursor.execute(f"""
                    SELECT TABLE_NAME 
                    FROM information_schema.TABLES 
                    WHERE TABLE_SCHEMA = '{schema}' 
                    AND (TABLE_NAME LIKE '%_backup_%' OR TABLE_NAME LIKE '%_bak_%')
                    ORDER BY TABLE_NAME DESC
                """)
                backups = [row[0] for row in cursor.fetchall()]
                if backups:
                    print(f"\n  {schema}: {len(backups)} total backups")
            
            cursor.close()
        else:
            # Perform actual cleanup
            dropped = drop_unused_tables(connection)
            old_naming_removed = drop_old_backup_naming(connection)
            bak_removed = cleanup_backup_tables(connection, keep_count=args.keep_backups)
            
            print("\n" + "="*60)
            print("CLEANUP COMPLETE")
            print(f"Unused tables dropped: {len(dropped)}")
            print(f"Old _backup_ tables removed: {old_naming_removed}")
            print(f"_bak_ excess removed: {bak_removed}")
            print(f"Total backups removed: {old_naming_removed + bak_removed}")
            print("="*60)
    
    finally:
        connection.close()


if __name__ == "__main__":
    main()
