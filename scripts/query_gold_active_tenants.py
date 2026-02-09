#!/usr/bin/env python3
"""
Query Aurora gold/silver tables for active tenant count.
Compare with rent roll data.
"""

import sys
import os

# Check for required packages
try:
    import pymysql
except ImportError:
    print("Installing pymysql...")
    os.system("pip3 install pymysql --break-system-packages --quiet")
    import pymysql

def get_db_connection():
    """Get Aurora database connection."""
    
    # Get credentials from environment
    host = os.environ.get('AURORA_ENDPOINT')
    user = os.environ.get('AURORA_USERNAME', 'admin')
    password = os.environ.get('AURORA_PASSWORD')
    database = 'tokyobeta'
    
    if not host or not password:
        print("ERROR: Database credentials not set!")
        print("Please set environment variables:")
        print("  export AURORA_ENDPOINT='your-endpoint.rds.amazonaws.com'")
        print("  export AURORA_USERNAME='admin'")
        print("  export AURORA_PASSWORD='your-password'")
        sys.exit(1)
    
    print(f"Connecting to Aurora: {host}")
    print(f"Database: {database}")
    print(f"User: {user}")
    print("="*80)
    
    try:
        conn = pymysql.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            port=3306,
            connect_timeout=10
        )
        print("✓ Connected successfully\n")
        return conn
    except Exception as e:
        print(f"ERROR: Failed to connect to database: {e}")
        sys.exit(1)

def query_active_tenant_count(conn):
    """Query active tenant count from various tables."""
    
    print("="*80)
    print("GOLD TABLE ACTIVE TENANT ANALYSIS")
    print("="*80)
    
    cursor = conn.cursor()
    
    # Query 1: Count from staging.tenants with active status
    print("\n1. Active tenants from staging.tenants (with is_active_lease)")
    query1 = """
    SELECT COUNT(DISTINCT t.id) as active_tenant_count
    FROM staging.tenants t
    INNER JOIN silver.code_tenant_status s ON t.status = s.code
    WHERE s.is_active_lease = 1
    """
    cursor.execute(query1)
    result1 = cursor.fetchone()
    print(f"   Active tenant count: {result1[0]:,}")
    
    # Query 2: Count from silver.stg_tenants view
    print("\n2. Active tenants from silver.stg_tenants view")
    query2 = """
    SELECT COUNT(*) as active_tenant_count
    FROM silver.stg_tenants
    WHERE is_active_lease = 1
    """
    cursor.execute(query2)
    result2 = cursor.fetchone()
    print(f"   Active tenant count: {result2[0]:,}")
    
    # Query 3: Check tenant status distribution
    print("\n3. Tenant count by status (top 10)")
    query3 = """
    SELECT 
        t.status,
        s.label_ja,
        s.label_en,
        s.is_active_lease,
        COUNT(*) as count
    FROM staging.tenants t
    LEFT JOIN silver.code_tenant_status s ON t.status = s.code
    GROUP BY t.status, s.label_ja, s.label_en, s.is_active_lease
    ORDER BY count DESC
    LIMIT 10
    """
    cursor.execute(query3)
    results3 = cursor.fetchall()
    print("   Status | Label (JA) | Label (EN) | Active | Count")
    print("   " + "-"*70)
    for row in results3:
        status, label_ja, label_en, is_active, count = row
        active_flag = "Yes" if is_active else "No"
        print(f"   {status:6} | {label_ja or 'N/A':15} | {label_en or 'N/A':20} | {active_flag:6} | {count:,}")
    
    # Query 4: Count distinct active tenants with move-in but no move-out
    print("\n4. Active tenants with move-in but no move-out")
    query4 = """
    SELECT COUNT(DISTINCT t.id) as active_tenant_count
    FROM staging.tenants t
    INNER JOIN staging.movings m ON t.id = m.tenant_id
    WHERE m.movein_date IS NOT NULL
      AND (m.moveout_date IS NULL OR m.moveout_date > CURRENT_DATE)
    """
    cursor.execute(query4)
    result4 = cursor.fetchone()
    print(f"   Active tenant count (by movings): {result4[0]:,}")
    
    # Query 5: Latest daily activity summary
    print("\n5. Latest entry from gold.daily_activity_summary")
    query5 = """
    SELECT 
        activity_date,
        tenant_type,
        confirmed_moveins_count,
        confirmed_moveouts_count,
        net_occupancy_delta
    FROM gold.daily_activity_summary
    WHERE activity_date >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)
    ORDER BY activity_date DESC, tenant_type
    LIMIT 10
    """
    try:
        cursor.execute(query5)
        results5 = cursor.fetchall()
        if results5:
            print("   Date       | Type       | Move-ins | Move-outs | Net Delta")
            print("   " + "-"*70)
            for row in results5:
                date, ttype, moveins, moveouts, delta = row
                print(f"   {date} | {ttype:10} | {moveins:8} | {moveouts:9} | {delta:+9}")
        else:
            print("   No recent data in daily_activity_summary")
    except Exception as e:
        print(f"   Error querying daily_activity_summary: {e}")
    
    # Query 6: Count active tenants by contract type
    print("\n6. Active tenants by contract type")
    query6 = """
    SELECT 
        CASE 
            WHEN t.contract_type IN (2, 3) THEN 'corporate'
            WHEN t.contract_type IN (1, 6, 7, 9) THEN 'individual'
            ELSE 'unknown'
        END as tenant_type,
        COUNT(*) as count
    FROM staging.tenants t
    INNER JOIN silver.code_tenant_status s ON t.status = s.code
    WHERE s.is_active_lease = 1
    GROUP BY tenant_type
    """
    cursor.execute(query6)
    results6 = cursor.fetchall()
    print("   Tenant Type | Count")
    print("   " + "-"*30)
    total = 0
    for row in results6:
        ttype, count = row
        print(f"   {ttype:11} | {count:,}")
        total += count
    print("   " + "-"*30)
    print(f"   Total       | {total:,}")
    
    cursor.close()
    
    return result1[0], result2[0], result4[0]

def main():
    conn = get_db_connection()
    
    try:
        count_staging, count_view, count_movings = query_active_tenant_count(conn)
        
        print("\n" + "="*80)
        print("SUMMARY - GOLD TABLE ACTIVE TENANTS")
        print("="*80)
        print(f"From staging.tenants (with is_active_lease): {count_staging:,}")
        print(f"From silver.stg_tenants view: {count_view:,}")
        print(f"From movings table (no moveout): {count_movings:,}")
        print("="*80)
        
        # Compare with rent roll
        print("\n" + "="*80)
        print("COMPARISON WITH RENT ROLL")
        print("="*80)
        print(f"Rent roll active tenants (Oct 2025): 1,076")
        print(f"Gold table active tenants (current): {count_staging:,}")
        print(f"Difference: {abs(count_staging - 1076):,}")
        
        if count_staging > 1076:
            print(f"  → Gold table has {count_staging - 1076:,} MORE active tenants than rent roll")
        else:
            print(f"  → Gold table has {1076 - count_staging:,} FEWER active tenants than rent roll")
        
        print("\nNOTE: Rent roll data is from October 2025, while gold table is current.")
        print("Discrepancy may be due to:")
        print("  1. Time difference (Oct 2025 vs current)")
        print("  2. Different definitions of 'active tenant'")
        print("  3. Data sync delays")
        print("="*80)
        
    finally:
        conn.close()
        print("\n✓ Database connection closed")

if __name__ == "__main__":
    main()
