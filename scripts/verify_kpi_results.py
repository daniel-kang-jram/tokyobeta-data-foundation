#!/usr/bin/env python3
"""Verify KPI results from gold.occupancy_daily_metrics."""

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

    # Total rows
    cursor.execute("SELECT COUNT(*) FROM gold.occupancy_daily_metrics")
    print(f"Total KPI rows: {cursor.fetchone()[0]}")

    # Sample recent data
    print("\n=== Recent 15 days ===")
    print(f"{'Date':<12} {'Apps':>5} {'In':>5} {'Out':>5} {'Delta':>6} {'Start':>7} {'End':>7} {'Rate':>7}")
    print("-" * 66)
    cursor.execute("""
        SELECT snapshot_date, applications, new_moveins, new_moveouts,
               occupancy_delta, period_start_rooms, period_end_rooms, occupancy_rate
        FROM gold.occupancy_daily_metrics
        ORDER BY snapshot_date DESC
        LIMIT 15
    """)
    for row in cursor.fetchall():
        d, apps, mi, mo, delta, start, end_r, rate = row
        rate_pct = float(rate) * 100
        print(f"{str(d):<12} {apps:>5} {mi:>5} {mo:>5} {delta:>+6} {start:>7} {end_r:>7} {rate_pct:>6.2f}%")

    # Arithmetic validation
    print("\n=== Arithmetic Validation ===")
    cursor.execute("""
        SELECT COUNT(*) as violations
        FROM gold.occupancy_daily_metrics
        WHERE occupancy_delta != (new_moveins - new_moveouts)
    """)
    v1 = cursor.fetchone()[0]
    print(f"  delta != moveins - moveouts: {v1} violations")

    cursor.execute("""
        SELECT COUNT(*) as violations
        FROM gold.occupancy_daily_metrics
        WHERE period_end_rooms != (period_start_rooms + occupancy_delta)
    """)
    v2 = cursor.fetchone()[0]
    print(f"  end != start + delta: {v2} violations")

    cursor.execute("""
        SELECT COUNT(*) as violations
        FROM gold.occupancy_daily_metrics
        WHERE ABS(occupancy_rate - (period_end_rooms / 16108.0)) > 0.001
    """)
    v3 = cursor.fetchone()[0]
    print(f"  rate != end/16108: {v3} violations")

    # Monthly summary
    print("\n=== Monthly Summary ===")
    print(f"{'Month':<10} {'Avg Apps':>9} {'Avg In':>8} {'Avg Out':>8} {'Avg Rate':>9}")
    print("-" * 48)
    cursor.execute("""
        SELECT
            DATE_FORMAT(snapshot_date, '%Y-%m') as month,
            ROUND(AVG(applications), 1) as avg_apps,
            ROUND(AVG(new_moveins), 1) as avg_mi,
            ROUND(AVG(new_moveouts), 1) as avg_mo,
            ROUND(AVG(occupancy_rate) * 100, 2) as avg_rate
        FROM gold.occupancy_daily_metrics
        GROUP BY DATE_FORMAT(snapshot_date, '%Y-%m')
        ORDER BY month
    """)
    for row in cursor.fetchall():
        month, avg_apps, avg_mi, avg_mo, avg_rate = row
        print(f"{month:<10} {avg_apps:>9} {avg_mi:>8} {avg_mo:>8} {avg_rate:>8.2f}%")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
