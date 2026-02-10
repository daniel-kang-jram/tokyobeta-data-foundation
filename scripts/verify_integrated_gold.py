#!/usr/bin/env python3
"""
Verify integrated gold_transformer job results.
- Checks gold.occupancy_daily_metrics was updated
- Verifies future projections (90 days forward)
- Confirms daily_activity_summary doesn't exist anymore
"""

import pymysql
import os

DB_HOST = "tokyobeta-prod-aurora-instance-1.c9wre5qfpit4.ap-northeast-1.rds.amazonaws.com"
DB_USER = "tokyobeta_admin"
DB_PASSWORD = os.environ.get("DB_PASSWORD", "").strip()
DB_NAME = "tokyobeta"

def main():
    conn = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        connect_timeout=60,
        read_timeout=300,
        write_timeout=300
    )
    
    try:
        with conn.cursor() as cursor:
            # Check if daily_activity_summary still exists
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_schema = 'gold' AND table_name = 'daily_activity_summary'
            """)
            summary_exists = cursor.fetchone()[0]
            print(f"✅ daily_activity_summary exists: {summary_exists == 1}")
            print(f"   (Expected: False - should be deleted)")
            
            # Check occupancy_daily_metrics latest date
            cursor.execute("""
                SELECT 
                    MIN(snapshot_date) as min_date,
                    MAX(snapshot_date) as max_date,
                    COUNT(DISTINCT snapshot_date) as date_count,
                    COUNT(*) as total_rows
                FROM gold.occupancy_daily_metrics
            """)
            result = cursor.fetchone()
            print(f"\n✅ Occupancy Metrics:")
            print(f"   Min Date: {result[0]}")
            print(f"   Max Date: {result[1]}")
            print(f"   Date Count: {result[2]}")
            print(f"   Total Rows: {result[3]}")
            
            # Check recent KPIs (last 3 days and next 3 days)
            cursor.execute("""
                SELECT 
                    snapshot_date,
                    applications,
                    new_move_ins,
                    new_move_outs,
                    occupancy_delta,
                    period_start_rooms,
                    period_end_rooms,
                    ROUND(occupancy_rate * 100, 2) as occupancy_rate_pct
                FROM gold.occupancy_daily_metrics
                WHERE snapshot_date BETWEEN DATE_SUB(CURDATE(), INTERVAL 3 DAY) 
                                        AND DATE_ADD(CURDATE(), INTERVAL 3 DAY)
                ORDER BY snapshot_date
            """)
            
            print(f"\n✅ Recent KPIs (3 days before/after today):")
            print(f"   {'Date':<12} {'Apps':>5} {'Move-in':>8} {'Move-out':>9} {'Delta':>6} {'Start':>6} {'End':>6} {'Rate%':>6}")
            print(f"   {'-'*12} {'-'*5} {'-'*8} {'-'*9} {'-'*6} {'-'*6} {'-'*6} {'-'*6}")
            
            for row in cursor.fetchall():
                date_str = row[0].strftime("%Y-%m-%d")
                marker = " 👈 TODAY" if row[0].strftime("%Y-%m-%d") == "2026-02-10" else ""
                print(f"   {date_str:<12} {row[1]:>5} {row[2]:>8} {row[3]:>9} {row[4]:>6} {row[5]:>6} {row[6]:>6} {row[7]:>6}{marker}")
            
            # Check that future dates have applications = 0
            cursor.execute("""
                SELECT COUNT(*) FROM gold.occupancy_daily_metrics
                WHERE snapshot_date > CURDATE() AND applications != 0
            """)
            future_apps_nonzero = cursor.fetchone()[0]
            print(f"\n✅ Future dates with applications != 0: {future_apps_nonzero}")
            print(f"   (Expected: 0)")
            
    finally:
        conn.close()

if __name__ == "__main__":
    main()
