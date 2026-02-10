#!/usr/bin/env python3
"""
Test Tokyo Beta tenant room info query against database.
Compare row counts with Excel file to validate accuracy.
"""

import pymysql
import os
import sys
import pandas as pd

def get_db_connection():
    """Get database connection."""
    host = os.getenv('DB_HOST', 'localhost')
    port = int(os.getenv('DB_PORT', '3306'))
    user = os.getenv('DB_USER', 'root')
    password = os.getenv('DB_PASSWORD', '')
    database = os.getenv('DB_NAME', 'tokyobeta')
    
    print(f"Connecting to: {user}@{host}:{port}/{database}")
    
    conn = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    
    return conn

def test_query(conn):
    """Test the query and compare with Excel."""
    
    print("\n" + "="*80)
    print("TOKYO BETA TENANT ROOM INFO - QUERY VALIDATION")
    print("="*80)
    
    # Query the database with ROW_NUMBER() deduplication
    # This handles duplicate historical movings records
    query = """
    WITH all_active_movings AS (
        SELECT
            t.id as tenant_id,
            t.status as management_status_code,
            t.full_name as tenant_name,
            t.contract_type,
            m.apartment_id,
            m.room_id,
            ROW_NUMBER() OVER (
                PARTITION BY t.id, m.apartment_id, m.room_id 
                ORDER BY m.movein_date DESC, m.updated_at DESC, m.id DESC
            ) as rn
        FROM staging.tenants t
        INNER JOIN staging.movings m ON t.moving_id = m.id
        WHERE 
            t.status IN (4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15)
            AND m.is_moveout = 0
    )
    SELECT COUNT(*) as total FROM all_active_movings WHERE rn = 1;
    """
    
    print("\n[1/3] Querying database...")
    with conn.cursor() as cursor:
        cursor.execute(query)
        result = cursor.fetchone()
        db_count = result['total']
    
    print(f"✓ Database row count: {db_count:,}")
    
    # Load Excel
    print("\n[2/3] Reading Excel file...")
    df = pd.read_excel('data/Tokyo Beta テナント情報.xlsx')
    excel_count = len(df)
    print(f"✓ Excel row count: {excel_count:,}")
    
    # Compare
    print("\n[3/3] Comparing counts...")
    print("="*80)
    print(f"Database: {db_count:,}")
    print(f"Excel:    {excel_count:,}")
    print(f"Deviation: {db_count - excel_count:,} ({(db_count - excel_count) / excel_count * 100:.1f}%)")
    
    if db_count == excel_count:
        print("✅ PERFECT MATCH!")
    elif abs(db_count - excel_count) / excel_count < 0.01:
        print("✅ Within 1% tolerance")
    else:
        print("❌ MISMATCH - Further investigation needed")
    
    # Detailed breakdown by status
    print("\n" + "="*80)
    print("BREAKDOWN BY STATUS")
    print("="*80)
    
    status_query = """
    WITH all_active_movings AS (
        SELECT
            t.status as management_status_code,
            t.contract_type,
            ROW_NUMBER() OVER (
                PARTITION BY t.id, m.apartment_id, m.room_id 
                ORDER BY m.movein_date DESC, m.updated_at DESC, m.id DESC
            ) as rn
        FROM staging.tenants t
        INNER JOIN staging.movings m ON t.moving_id = m.id
        WHERE 
            t.status IN (4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15)
            AND m.is_moveout = 0
    )
    SELECT 
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
        END as status,
        COUNT(*) as db_count
    FROM all_active_movings
    WHERE rn = 1
    GROUP BY management_status_code
    ORDER BY db_count DESC;
    """
    
    with conn.cursor() as cursor:
        cursor.execute(status_query)
        db_status = cursor.fetchall()
    
    excel_status = df['管理ステータス'].value_counts().to_dict()
    
    print(f"\n{'Status':<20} {'Database':<12} {'Excel':<12} {'Deviation':<12}")
    print("-" * 60)
    
    for row in db_status:
        status = row['status']
        db_cnt = row['db_count']
        excel_cnt = excel_status.get(status, 0)
        deviation = db_cnt - excel_cnt
        
        match_symbol = "✓" if deviation == 0 else "✗"
        print(f"{status:<20} {db_cnt:<12,} {excel_cnt:<12,} {deviation:<12,} {match_symbol}")
    
    # Check for statuses in Excel but not in database
    print("\nStatuses in Excel but not in database query:")
    for status, count in excel_status.items():
        if not any(row['status'] == status for row in db_status):
            print(f"  - {status}: {count} rows")
    
    # Additional validation: Check contract_type distribution
    print("\n" + "="*80)
    print("CONTRACT TYPE DISTRIBUTION (using moving_agreement_type)")
    print("="*80)
    
    contract_query = """
    WITH all_active_movings AS (
        SELECT
            m.moving_agreement_type,
            ROW_NUMBER() OVER (
                PARTITION BY t.id, m.apartment_id, m.room_id 
                ORDER BY m.movein_date DESC, m.updated_at DESC, m.id DESC
            ) as rn
        FROM staging.tenants t
        INNER JOIN staging.movings m ON t.moving_id = m.id
        WHERE 
            t.status IN (4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15)
            AND m.is_moveout = 0
    )
    SELECT 
        CASE moving_agreement_type
            WHEN 1 THEN '一般'
            WHEN 2 THEN '法人契約'
            WHEN 3 THEN '法人契約（個人）'
            WHEN 7 THEN '一般（保証会社）'
            WHEN 9 THEN '一般2'
            ELSE 'Unknown'
        END as contract_type,
        COUNT(*) as db_count
    FROM all_active_movings
    WHERE rn = 1
    GROUP BY moving_agreement_type
    ORDER BY db_count DESC;
    """
    
    with conn.cursor() as cursor:
        cursor.execute(contract_query)
        db_contract = cursor.fetchall()
    
    excel_contract = {
        '一般2': 4875,
        '一般': 3525,
        '法人契約': 2231,
        '法人契約（個人）': 989,
        '一般（保証会社）': 443
    }
    
    print(f"\n{'Contract Type':<25} {'Database':<12} {'Excel':<12} {'Deviation':<12}")
    print("-" * 65)
    
    for row in db_contract:
        contract = row['contract_type']
        db_cnt = row['db_count']
        excel_cnt = excel_contract.get(contract, 0)
        deviation = db_cnt - excel_cnt
        
        match_symbol = "✓" if abs(deviation) < excel_cnt * 0.15 else "✗"  # Within 15%
        print(f"{contract:<25} {db_cnt:<12,} {excel_cnt:<12,} {deviation:<12,} {match_symbol}")

if __name__ == "__main__":
    try:
        conn = get_db_connection()
        test_query(conn)
        conn.close()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure:")
        print("1. Database is running")
        print("2. Environment variables set: DB_HOST, DB_USER, DB_PASSWORD, DB_NAME")
        print("3. staging.tenants and staging.movings tables exist")
        sys.exit(1)
