#!/usr/bin/env python3
"""Quick cleanup: drop + recreate snapshot table, truncate KPI table."""

import pymysql
import boto3
import json
import sys

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
        database='tokyobeta', cursorclass=pymysql.cursors.Cursor,
        connect_timeout=60, read_timeout=600, write_timeout=600
    )


def main():
    step = sys.argv[1] if len(sys.argv) > 1 else "all"

    conn = get_db_connection()
    cursor = conn.cursor()

    if step in ("test", "all"):
        print("Test: SELECT 1 ...")
        cursor.execute("SELECT 1")
        print(f"  Result: {cursor.fetchone()}")

    if step in ("drop", "all"):
        print("Dropping silver.tenant_room_snapshot_daily ...")
        cursor.execute("DROP TABLE IF EXISTS silver.tenant_room_snapshot_daily")
        conn.commit()
        print("  Dropped.")

    if step in ("kpi", "all"):
        print("Truncating gold.occupancy_daily_metrics ...")
        cursor.execute("TRUNCATE TABLE gold.occupancy_daily_metrics")
        conn.commit()
        print("  Truncated.")

    if step in ("verify", "all"):
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = 'silver' AND TABLE_NAME = 'tenant_room_snapshot_daily'
        """)
        exists = cursor.fetchone()[0]
        print(f"  silver.tenant_room_snapshot_daily exists: {bool(exists)}")
        cursor.execute("SELECT COUNT(*) FROM gold.occupancy_daily_metrics")
        print(f"  gold.occupancy_daily_metrics rows: {cursor.fetchone()[0]}")

    cursor.close()
    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
