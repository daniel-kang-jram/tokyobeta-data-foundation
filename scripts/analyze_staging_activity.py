#!/usr/bin/env python3
"""
Analyze staging tables to find those with activity in the recent 1 year.
Checks all date/datetime columns in each staging table.
"""

import pymysql
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Tuple

# Database connection details
DB_HOST = "tokyobeta-prod-aurora-cluster-public.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com"
DB_USER = "admin"
DB_PASSWORD = "K6ghcWTq4p-zlidRJ2<AJX<w$zN<a8dU"
DB_NAME = "tokyobeta"
DB_PORT = 3306


def get_staging_tables(cursor) -> List[str]:
    """Get all table names in the staging schema."""
    cursor.execute("""
        SELECT TABLE_NAME 
        FROM information_schema.TABLES 
        WHERE TABLE_SCHEMA = 'staging'
        ORDER BY TABLE_NAME
    """)
    return [row[0] for row in cursor.fetchall()]


def get_date_columns(cursor, table_name: str) -> List[Tuple[str, str]]:
    """Get all date/datetime columns for a given table."""
    cursor.execute("""
        SELECT COLUMN_NAME, DATA_TYPE
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = 'staging'
        AND TABLE_NAME = %s
        AND DATA_TYPE IN ('date', 'datetime', 'timestamp')
        ORDER BY ORDINAL_POSITION
    """, (table_name,))
    return cursor.fetchall()


def check_recent_activity(cursor, table_name: str, date_columns: List[Tuple[str, str]], 
                         cutoff_date: str) -> Dict:
    """Check if table has any records with dates within the last year."""
    
    if not date_columns:
        return {
            'has_activity': False,
            'reason': 'No date columns found',
            'checked_columns': [],
            'max_date': None,
            'row_count': None
        }
    
    # Build a query to check each date column
    conditions = []
    for col_name, col_type in date_columns:
        conditions.append(f"`{col_name}` >= '{cutoff_date}'")
    
    where_clause = " OR ".join(conditions)
    
    try:
        # Check if there's any recent activity
        query = f"""
            SELECT COUNT(*) as recent_count
            FROM `staging`.`{table_name}`
            WHERE {where_clause}
            LIMIT 1
        """
        cursor.execute(query)
        result = cursor.fetchone()
        recent_count = result[0] if result else 0
        
        # Also get the maximum date from all date columns
        max_date_queries = []
        for col_name, col_type in date_columns:
            max_date_queries.append(f"MAX(`{col_name}`)")
        
        max_date_query = f"""
            SELECT {", ".join(max_date_queries)}
            FROM `staging`.`{table_name}`
        """
        cursor.execute(max_date_query)
        max_dates = cursor.fetchone()
        
        # Find the overall maximum date
        max_date = None
        if max_dates:
            max_date = max(d for d in max_dates if d is not None) if any(max_dates) else None
        
        # Get total row count
        cursor.execute(f"SELECT COUNT(*) FROM `staging`.`{table_name}`")
        total_count = cursor.fetchone()[0]
        
        return {
            'has_activity': recent_count > 0,
            'reason': f'{recent_count} records found' if recent_count > 0 else 'No recent records',
            'checked_columns': [col[0] for col in date_columns],
            'max_date': max_date,
            'row_count': total_count,
            'recent_count': recent_count
        }
        
    except Exception as e:
        return {
            'has_activity': False,
            'reason': f'Error: {str(e)}',
            'checked_columns': [col[0] for col in date_columns],
            'max_date': None,
            'row_count': None
        }


def main():
    """Main execution function."""
    
    # Calculate cutoff date (1 year ago from today)
    cutoff_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    
    print(f"=== Staging Table Activity Analysis ===")
    print(f"Cutoff Date: {cutoff_date} (1 year ago)")
    print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        # Connect to database
        connection = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            port=DB_PORT,
            connect_timeout=10
        )
        
        with connection.cursor() as cursor:
            # Get all staging tables
            tables = get_staging_tables(cursor)
            print(f"Found {len(tables)} tables in staging schema")
            print()
            
            # Analyze each table
            active_tables = []
            inactive_tables = []
            
            for table_name in tables:
                date_columns = get_date_columns(cursor, table_name)
                activity = check_recent_activity(cursor, table_name, date_columns, cutoff_date)
                
                table_info = {
                    'name': table_name,
                    'activity': activity
                }
                
                if activity['has_activity']:
                    active_tables.append(table_info)
                else:
                    inactive_tables.append(table_info)
            
            # Print results
            print(f"{'='*80}")
            print(f"TABLES WITH ACTIVITY IN RECENT 1 YEAR: {len(active_tables)}")
            print(f"{'='*80}")
            print()
            
            if active_tables:
                for table in active_tables:
                    print(f"✓ {table['name']}")
                    print(f"  - Recent records: {table['activity']['recent_count']}")
                    print(f"  - Total rows: {table['activity']['row_count']}")
                    print(f"  - Latest date: {table['activity']['max_date']}")
                    print(f"  - Checked columns: {', '.join(table['activity']['checked_columns'])}")
                    print()
            
            print(f"{'='*80}")
            print(f"TABLES WITHOUT ACTIVITY IN RECENT 1 YEAR: {len(inactive_tables)}")
            print(f"{'='*80}")
            print()
            
            if inactive_tables:
                for table in inactive_tables:
                    print(f"✗ {table['name']}")
                    print(f"  - Reason: {table['activity']['reason']}")
                    print(f"  - Total rows: {table['activity']['row_count']}")
                    if table['activity']['max_date']:
                        print(f"  - Latest date: {table['activity']['max_date']}")
                    if table['activity']['checked_columns']:
                        print(f"  - Checked columns: {', '.join(table['activity']['checked_columns'])}")
                    print()
            
            # Summary
            print(f"{'='*80}")
            print(f"SUMMARY")
            print(f"{'='*80}")
            print(f"Total tables analyzed: {len(tables)}")
            print(f"Tables with recent activity: {len(active_tables)}")
            print(f"Tables without recent activity: {len(inactive_tables)}")
            print(f"Active table percentage: {(len(active_tables)/len(tables)*100):.1f}%")
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if 'connection' in locals():
            connection.close()


if __name__ == "__main__":
    main()
