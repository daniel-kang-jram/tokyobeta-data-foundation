#!/usr/bin/env python3
"""Verify future date projections in gold.occupancy_daily_metrics."""

import pymysql
import boto3
import json
from datetime import date

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
    
    today = date.today()
    
    print("=== Future Projections Verification ===\n")
    
    # Check date range
    cursor.execute("""
        SELECT 
            MIN(snapshot_date) as earliest,
            MAX(snapshot_date) as latest,
            COUNT(*) as total_days,
            SUM(CASE WHEN snapshot_date <= CURDATE() THEN 1 ELSE 0 END) as past_days,
            SUM(CASE WHEN snapshot_date > CURDATE() THEN 1 ELSE 0 END) as future_days
        FROM gold.occupancy_daily_metrics
    """)
    row = cursor.fetchone()
    print(f"Date range: {row[0]} to {row[1]}")
    print(f"Total days: {row[2]}")
    print(f"Past/today: {row[3]}")
    print(f"Future: {row[4]}")
    
    # Show sample future projections
    print("\n=== Sample Future Projections (next 10 days) ===")
    print(f"{'Date':<12} {'Apps':>5} {'In':>5} {'Out':>5} {'Delta':>6} {'Start':>7} {'End':>7} {'Rate':>7}")
    print("-" * 66)
    
    cursor.execute("""
        SELECT snapshot_date, applications, new_moveins, new_moveouts,
               occupancy_delta, period_start_rooms, period_end_rooms, occupancy_rate
        FROM gold.occupancy_daily_metrics
        WHERE snapshot_date > CURDATE()
        ORDER BY snapshot_date
        LIMIT 10
    """)
    
    for row in cursor.fetchall():
        d, apps, mi, mo, delta, start, end_r, rate = row
        rate_pct = float(rate) * 100
        print(f"{str(d):<12} {apps:>5} {mi:>5} {mo:>5} {delta:>+6} {start:>7} {end_r:>7} {rate_pct:>6.2f}%")
    
    # Verify arithmetic for future dates
    print("\n=== Arithmetic Validation (Future Dates) ===")
    cursor.execute("""
        SELECT COUNT(*) as violations
        FROM gold.occupancy_daily_metrics
        WHERE snapshot_date > CURDATE()
        AND occupancy_delta != (new_moveins - new_moveouts)
    """)
    v1 = cursor.fetchone()[0]
    print(f"  delta != moveins - moveouts: {v1} violations")
    
    cursor.execute("""
        SELECT COUNT(*) as violations
        FROM gold.occupancy_daily_metrics
        WHERE snapshot_date > CURDATE()
        AND period_end_rooms != (period_start_rooms + occupancy_delta)
    """)
    v2 = cursor.fetchone()[0]
    print(f"  end != start + delta: {v2} violations")
    
    # Check continuity at today boundary
    print("\n=== Continuity Check (around today) ===")
    print(f"{'Date':<12} {'End Rooms':>10} {'Rate':>7}")
    print("-" * 30)
    
    cursor.execute("""
        SELECT snapshot_date, period_end_rooms, occupancy_rate
        FROM gold.occupancy_daily_metrics
        WHERE snapshot_date BETWEEN DATE_SUB(CURDATE(), INTERVAL 2 DAY) 
                                AND DATE_ADD(CURDATE(), INTERVAL 2 DAY)
        ORDER BY snapshot_date
    """)
    
    for row in cursor.fetchall():
        d, end_r, rate = row
        rate_pct = float(rate) * 100
        marker = " <- TODAY" if d == today else ""
        print(f"{str(d):<12} {end_r:>10} {rate_pct:>6.2f}%{marker}")
    
    cursor.close()
    conn.close()
    
    print("\n✓ Verification complete")


if __name__ == "__main__":
    main()
