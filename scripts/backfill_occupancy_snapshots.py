#!/usr/bin/env python3
"""
Backfill silver.tenant_room_snapshot_daily from staging.tenant_daily_snapshots

One-time script to populate historical snapshots for occupancy tracking.
After backfill, switch to incremental daily append via dbt.

Usage:
    python3 scripts/backfill_occupancy_snapshots.py --start-date 2025-10-01 --end-date 2026-02-10
    python3 scripts/backfill_occupancy_snapshots.py --dry-run  # Preview only
"""

import pymysql
import boto3
import json
import argparse
from datetime import datetime, date, timedelta

# Configuration
DB_SECRET_ARN = 'arn:aws:secretsmanager:ap-northeast-1:343881458651:secret:tokyobeta/prod/aurora/credentials-tlWiUd'
REGION = 'ap-northeast-1'
DB_HOST = 'tokyobeta-prod-aurora-cluster-public.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com'

def get_db_connection():
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=REGION)
    
    try:
        get_secret_value_response = client.get_secret_value(SecretId=DB_SECRET_ARN)
        secret = json.loads(get_secret_value_response['SecretString'])
        
        user = secret.get('username') or secret.get('user')
        password = secret.get('password')
        
        connection = pymysql.connect(
            host=DB_HOST,
            user=user,
            password=password,
            database='tokyobeta',
            cursorclass=pymysql.cursors.Cursor,
            connect_timeout=30,
            read_timeout=300,
            write_timeout=300
        )
        return connection
    except Exception as e:
        print(f"Error connecting to database: {e}")
        raise


def ensure_snapshot_table_exists(cursor):
    """Create silver.tenant_room_snapshot_daily if not exists."""
    print("Checking if silver.tenant_room_snapshot_daily exists...")
    
    cursor.execute("""
        SELECT COUNT(*) 
        FROM information_schema.TABLES 
        WHERE TABLE_SCHEMA = 'silver' 
        AND TABLE_NAME = 'tenant_room_snapshot_daily'
    """)
    
    exists = cursor.fetchone()[0] > 0
    
    if not exists:
        print("WARNING: Table does not exist. Please run dbt model first to create it.")
        print("  cd dbt && dbt run --select silver.tenant_room_snapshot_daily --target prod")
        raise RuntimeError("Table silver.tenant_room_snapshot_daily does not exist")
    
    print("✓ Table exists")


def get_snapshot_dates_to_backfill(cursor, start_date, end_date):
    """
    Get list of snapshot dates that need backfilling.
    
    Args:
        cursor: pymysql cursor
        start_date: date object
        end_date: date object
        
    Returns:
        List of date objects
    """
    print(f"Checking existing snapshots between {start_date} and {end_date}...")
    
    # Get existing snapshot dates in target table
    cursor.execute("""
        SELECT DISTINCT snapshot_date
        FROM silver.tenant_room_snapshot_daily
        WHERE snapshot_date BETWEEN %s AND %s
    """, (start_date, end_date))
    
    existing_dates = {row[0] for row in cursor.fetchall()}
    print(f"  Found {len(existing_dates)} existing snapshot dates")
    
    # Get available dates in staging.tenant_daily_snapshots
    cursor.execute("""
        SELECT DISTINCT snapshot_date
        FROM staging.tenant_daily_snapshots
        WHERE snapshot_date BETWEEN %s AND %s
        ORDER BY snapshot_date
    """, (start_date, end_date))
    
    available_dates = [row[0] for row in cursor.fetchall()]
    print(f"  Found {len(available_dates)} available source dates")
    
    # Dates to backfill = available - existing
    dates_to_backfill = [d for d in available_dates if d not in existing_dates]
    print(f"  Need to backfill: {len(dates_to_backfill)} dates")
    
    return dates_to_backfill


def backfill_snapshot_for_date(cursor, snapshot_date, dry_run=False):
    """
    Backfill snapshot for a specific date.
    
    Runs the same SQL logic as the dbt incremental model.
    """
    # IMPORTANT: Use tds.status (historical snapshot status), NOT t.status (current).
    # Remove m.is_moveout = 0 filter because a tenant active in Oct 2025
    # may have is_moveout=1 now after moving out in Jan 2026.
    # The snapshot already tells us who was active on each date.
    insert_sql = """
        INSERT INTO silver.tenant_room_snapshot_daily
        (snapshot_date, management_status_code, management_status, tenant_id, tenant_name,
         apartment_id, room_id, property, room_number, contract_category,
         move_in_date, moveout_date, moveout_plans_date, moving_id, dbt_updated_at)
        
        WITH snapshot_tenants AS (
            -- Get tenants who were ACTIVE on this snapshot date
            -- using their HISTORICAL status from tenant_daily_snapshots
            SELECT
                tds.tenant_id,
                tds.status as management_status_code,
                tds.contract_type as snapshot_contract_type,
                t.full_name as tenant_name,
                t.moving_id
            FROM staging.tenant_daily_snapshots tds
            INNER JOIN staging.tenants t ON tds.tenant_id = t.id
            WHERE tds.snapshot_date = %s
            AND tds.status IN (4,5,6,7,9,10,11,12,13,14,15)
        ),
        with_moving AS (
            -- Join to movings for room/apartment/date info
            -- Do NOT filter on is_moveout since we already know they were active
            SELECT
                st.tenant_id,
                st.management_status_code,
                st.tenant_name,
                st.snapshot_contract_type,
                m.moving_agreement_type as contract_type,
                m.movein_date as move_in_date,
                m.moveout_date as moveout_date,
                m.moveout_plans_date as moveout_plans_date,
                m.apartment_id,
                m.room_id,
                m.id as moving_id,
                ROW_NUMBER() OVER (
                    PARTITION BY st.tenant_id, m.apartment_id, m.room_id 
                    ORDER BY m.movein_date DESC, m.updated_at DESC, m.id DESC
                ) as rn
            FROM snapshot_tenants st
            INNER JOIN staging.movings m ON st.moving_id = m.id
        ),
        tenant_room_assignments AS (
            SELECT
                tenant_id,
                management_status_code,
                tenant_name,
                snapshot_contract_type,
                contract_type,
                move_in_date,
                moveout_date,
                moveout_plans_date,
                apartment_id,
                room_id,
                moving_id
            FROM with_moving
            WHERE rn = 1
        ),
        with_property_room AS (
            SELECT
                tra.*,
                a.apartment_name as property,
                r.room_number
            FROM tenant_room_assignments tra
            LEFT JOIN staging.apartments a ON tra.apartment_id = a.id
            LEFT JOIN staging.rooms r ON tra.room_id = r.id
        )
        SELECT
            %s as snapshot_date,
            management_status_code,
            CASE management_status_code
                WHEN 4 THEN '仮予約'
                WHEN 5 THEN '初回家賃入金'
                WHEN 6 THEN '入居説明'
                WHEN 7 THEN '入居'
                WHEN 9 THEN '入居中'
                WHEN 10 THEN '契約更新'
                WHEN 11 THEN '移動届受領'
                WHEN 12 THEN '移動手続き'
                WHEN 13 THEN '移動'
                WHEN 14 THEN '退去届受領'
                WHEN 15 THEN '退去予定'
                ELSE 'Unknown'
            END as management_status,
            tenant_id,
            tenant_name,
            apartment_id,
            room_id,
            property,
            room_number,
            CASE COALESCE(contract_type, snapshot_contract_type)
                WHEN 1 THEN '一般'
                WHEN 2 THEN '法人契約'
                WHEN 3 THEN '法人契約（個人）'
                WHEN 6 THEN '一般（保証会社）'
                ELSE '一般2'
            END as contract_category,
            move_in_date,
            moveout_date,
            moveout_plans_date,
            moving_id,
            CURRENT_TIMESTAMP as dbt_updated_at
        FROM with_property_room
    """
    
    if dry_run:
        print(f"  [DRY RUN] Would insert snapshot for {snapshot_date}")
        return 0
    
    cursor.execute(insert_sql, (snapshot_date, snapshot_date))
    rows_inserted = cursor.rowcount
    
    return rows_inserted


def main():
    parser = argparse.ArgumentParser(description='Backfill occupancy snapshot table')
    parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD)', default='2025-10-01')
    parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD)', default=str(date.today()))
    parser.add_argument('--dry-run', action='store_true', help='Preview without inserting')
    parser.add_argument('--batch-size', type=int, default=10, help='Commit every N dates')
    args = parser.parse_args()
    
    start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
    end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()
    
    print(f"=== Occupancy Snapshot Backfill ===")
    print(f"Date range: {start_date} to {end_date}")
    print(f"Dry run: {args.dry_run}")
    print("")
    
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        
        # Ensure target table exists
        ensure_snapshot_table_exists(cursor)
        
        # Get dates to backfill
        dates_to_backfill = get_snapshot_dates_to_backfill(cursor, start_date, end_date)
        
        if not dates_to_backfill:
            print("✓ All dates already backfilled. Nothing to do.")
            return
        
        print(f"\nBackfilling {len(dates_to_backfill)} dates...")
        
        total_rows = 0
        
        for i, snapshot_date in enumerate(dates_to_backfill, 1):
            rows = backfill_snapshot_for_date(cursor, snapshot_date, dry_run=args.dry_run)
            total_rows += rows
            
            if not args.dry_run and i % args.batch_size == 0:
                conn.commit()
                print(f"  Progress: {i}/{len(dates_to_backfill)} dates, {total_rows:,} rows inserted")
        
        if not args.dry_run:
            conn.commit()
            print(f"\n✓ Backfill complete: {total_rows:,} total rows inserted")
        else:
            print(f"\n[DRY RUN] Would insert {total_rows:,} total rows")
        
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
