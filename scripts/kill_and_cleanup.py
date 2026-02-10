#!/usr/bin/env python3
"""Kill blocking processes, then cleanup tables."""

import pymysql
import boto3
import json
import time

DB_SECRET_ARN = 'arn:aws:secretsmanager:ap-northeast-1:343881458651:secret:tokyobeta/prod/aurora/credentials-tlWiUd'
REGION = 'ap-northeast-1'
DB_HOST = 'tokyobeta-prod-aurora-cluster-public.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com'


def get_db_connection():
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=REGION)
    get_secret_value_response = client.get_secret_value(SecretId=DB_SECRET_ARN)
    secret = json.loads(get_secret_value_response['SecretString'])
    user = secret.get('username') or secret.get('user')
    password = secret.get('password')
    return pymysql.connect(
        host=DB_HOST, user=user, password=password,
        database='tokyobeta', cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=30, read_timeout=600, write_timeout=600
    )


def main():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Step 1: Kill all blocking admin connections (from stopped Glue job)
    print("=== Killing blocking connections ===")
    kill_ids = [60908, 60964, 60965, 61066, 61078, 61108, 61169]
    for pid in kill_ids:
        try:
            cursor.execute(f"KILL {pid}")
            print(f"  Killed process {pid}")
        except Exception as e:
            print(f"  Process {pid}: {e}")

    conn.commit()
    time.sleep(3)

    # Verify
    print("\n=== Remaining long processes ===")
    cursor.execute("SHOW PROCESSLIST")
    for row in cursor.fetchall():
        t = row.get('Time', 0)
        if t and int(t) > 10 and row.get('User') == 'admin':
            print(f"  ID={row['Id']} Time={t}s State={row.get('State')} Info={str(row.get('Info', ''))[:80]}")

    # Step 2: Drop snapshot table
    print("\n=== Dropping silver.tenant_room_snapshot_daily ===")
    cursor.execute("DROP TABLE IF EXISTS silver.tenant_room_snapshot_daily")
    conn.commit()
    print("  Dropped.")

    # Step 3: Truncate KPI table
    print("\n=== Truncating gold.occupancy_daily_metrics ===")
    cursor.execute("TRUNCATE TABLE gold.occupancy_daily_metrics")
    conn.commit()
    print("  Truncated.")

    # Step 4: Verify
    cursor.execute("""
        SELECT COUNT(*) as cnt FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = 'silver' AND TABLE_NAME = 'tenant_room_snapshot_daily'
    """)
    exists = cursor.fetchone()['cnt']
    print(f"\n  silver.tenant_room_snapshot_daily exists: {bool(exists)}")

    cursor.execute("SELECT COUNT(*) as cnt FROM gold.occupancy_daily_metrics")
    print(f"  gold.occupancy_daily_metrics rows: {cursor.fetchone()['cnt']}")

    cursor.close()
    conn.close()
    print("\nCleanup complete!")


if __name__ == "__main__":
    main()
