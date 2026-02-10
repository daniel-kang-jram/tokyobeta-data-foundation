#!/usr/bin/env python3
"""Verify snapshot counts are stable across dates."""

import pymysql
import boto3
import json

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
        connect_timeout=30, read_timeout=120
    )


def main():
    conn = get_db_connection()
    cursor = conn.cursor()

    print("=== Unique Room Counts by Snapshot Date ===")
    print(f"{'Date':<15} {'Unique Rooms':<15} {'Total Rows':<15}")
    print("-" * 45)

    cursor.execute("""
        SELECT
            snapshot_date,
            COUNT(DISTINCT apartment_id, room_id) AS unique_room_count,
            COUNT(*) AS total_rows
        FROM silver.tenant_room_snapshot_daily
        GROUP BY snapshot_date
        ORDER BY snapshot_date DESC
    """)

    rows = cursor.fetchall()
    prev_count = None
    for row in rows:
        sd, unique_rooms, total = row
        delta = ""
        if prev_count is not None:
            diff = unique_rooms - prev_count
            if diff != 0:
                delta = f"  ({'+' if diff > 0 else ''}{diff})"
        print(f"{str(sd):<15} {unique_rooms:<15} {total:<15}{delta}")
        prev_count = unique_rooms

    # Summary stats
    counts = [r[1] for r in rows]
    print(f"\nMin: {min(counts):,}  Max: {max(counts):,}  Range: {max(counts)-min(counts):,}")
    print(f"Avg: {sum(counts)/len(counts):,.0f}")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
