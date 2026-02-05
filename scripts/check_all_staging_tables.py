#!/usr/bin/env python3
"""
Check all staging tables for recent activity (last 1 year).
Uses direct database queries to get exact counts.
"""

import subprocess
import sys
from datetime import datetime, timedelta

DB_HOST = "tokyobeta-prod-aurora-cluster-public.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com"
DB_USER = "admin"
DB_PASS = "K6ghcWTq4p-zlidRJ2<AJX<w$zN<a8dU"
DB_NAME = "tokyobeta"

def run_query(query):
    """Run a MySQL query and return the output."""
    cmd = [
        'mysql',
        '-h', DB_HOST,
        '-u', DB_USER,
        f'-p{DB_PASS}',
        '-D', DB_NAME,
        '-N',  # No column names
        '-e', query
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return None
        return result.stdout.strip()
    except Exception as e:
        print(f"Error running query: {e}", file=sys.stderr)
        return None

def get_all_tables_with_date_columns():
    """Get all staging tables and their date columns."""
    query = """
    SELECT 
        t.TABLE_NAME,
        COALESCE(
            GROUP_CONCAT(
                c.COLUMN_NAME 
                ORDER BY c.ORDINAL_POSITION 
                SEPARATOR ','
            ),
            ''
        ) as date_columns
    FROM information_schema.TABLES t
    LEFT JOIN information_schema.COLUMNS c 
        ON t.TABLE_SCHEMA = c.TABLE_SCHEMA 
        AND t.TABLE_NAME = c.TABLE_NAME
        AND c.DATA_TYPE IN ('date', 'datetime', 'timestamp')
    WHERE t.TABLE_SCHEMA = 'staging'
    GROUP BY t.TABLE_NAME
    ORDER BY t.TABLE_NAME;
    """
    
    result = run_query(query)
    if not result:
        return []
    
    tables = []
    for line in result.split('\n'):
        if line:
            parts = line.split('\t')
            table_name = parts[0]
            date_columns = parts[1] if len(parts) > 1 and parts[1] else ''
            tables.append((table_name, date_columns))
    
    return tables

def check_table_activity(table_name, date_columns, cutoff_date):
    """Check if a table has recent activity."""
    
    if not date_columns:
        # No date columns - get row count only
        query = f"SELECT COUNT(*) FROM `staging`.`{table_name}`;"
        result = run_query(query)
        total_count = int(result) if result else 0
        return {
            'total_rows': total_count,
            'recent_records': 'N/A',
            'has_activity': 'NO_DATE_COLS',
            'latest_date': 'N/A'
        }
    
    # Build WHERE clause for date columns
    cols = date_columns.split(',')
    where_parts = [f"`{col}` >= '{cutoff_date}'" for col in cols]
    where_clause = ' OR '.join(where_parts)
    
    # Get total count, recent count, and max date
    max_parts = [f"MAX(`{col}`)" for col in cols]
    max_clause = ', '.join(max_parts)
    
    query = f"""
    SELECT 
        (SELECT COUNT(*) FROM `staging`.`{table_name}`) as total,
        COUNT(*) as recent,
        GREATEST({max_clause}) as max_date
    FROM `staging`.`{table_name}`
    WHERE {where_clause};
    """
    
    result = run_query(query)
    if not result:
        return {
            'total_rows': 0,
            'recent_records': 0,
            'has_activity': False,
            'latest_date': 'N/A'
        }
    
    parts = result.split('\t')
    total_count = int(parts[0]) if len(parts) > 0 else 0
    recent_count = int(parts[1]) if len(parts) > 1 else 0
    latest_date = parts[2] if len(parts) > 2 and parts[2] else 'N/A'
    
    return {
        'total_rows': total_count,
        'recent_records': recent_count,
        'has_activity': recent_count > 0,
        'latest_date': latest_date
    }

def main():
    """Main execution."""
    cutoff_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    
    print("=" * 80)
    print("STAGING TABLES - RECENT ACTIVITY ANALYSIS")
    print("=" * 80)
    print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Cutoff Date: {cutoff_date} (1 year ago)")
    print()
    
    # Get all tables
    print("Fetching table information...")
    tables = get_all_tables_with_date_columns()
    print(f"Found {len(tables)} staging tables")
    print()
    
    # Check each table
    active_tables = []
    inactive_tables = []
    no_date_cols_tables = []
    
    for i, (table_name, date_columns) in enumerate(tables, 1):
        print(f"Checking {i}/{len(tables)}: {table_name}...", end='\r')
        
        result = check_table_activity(table_name, date_columns, cutoff_date)
        
        table_info = {
            'name': table_name,
            'date_columns': date_columns,
            **result
        }
        
        if result['has_activity'] == 'NO_DATE_COLS':
            no_date_cols_tables.append(table_info)
        elif result['has_activity']:
            active_tables.append(table_info)
        else:
            inactive_tables.append(table_info)
    
    print(" " * 80)  # Clear progress line
    print()
    
    # Print results
    print("=" * 80)
    print(f"TABLES WITH RECENT ACTIVITY (LAST 1 YEAR): {len(active_tables)}")
    print("=" * 80)
    print()
    
    for table in sorted(active_tables, key=lambda x: x['recent_records'], reverse=True):
        print(f"✓ {table['name']}")
        print(f"  Total rows: {table['total_rows']:,}")
        print(f"  Recent records: {table['recent_records']:,}")
        print(f"  Latest date: {table['latest_date']}")
        print(f"  Date columns: {table['date_columns']}")
        print()
    
    print("=" * 80)
    print(f"TABLES WITHOUT RECENT ACTIVITY: {len(inactive_tables)}")
    print("=" * 80)
    print()
    
    for table in sorted(inactive_tables, key=lambda x: x['total_rows'], reverse=True):
        print(f"✗ {table['name']}")
        print(f"  Total rows: {table['total_rows']:,}")
        print(f"  Latest date: {table['latest_date']}")
        print(f"  Date columns: {table['date_columns']}")
        print()
    
    print("=" * 80)
    print(f"TABLES WITHOUT DATE COLUMNS: {len(no_date_cols_tables)}")
    print("=" * 80)
    print()
    
    for table in sorted(no_date_cols_tables, key=lambda x: x['total_rows'], reverse=True):
        print(f"○ {table['name']}")
        print(f"  Total rows: {table['total_rows']:,}")
        print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total tables: {len(tables)}")
    print(f"Tables with recent activity: {len(active_tables)}")
    print(f"Tables without recent activity: {len(inactive_tables)}")
    print(f"Tables without date columns: {len(no_date_cols_tables)}")
    print(f"Active percentage: {len(active_tables)/len(tables)*100:.1f}%")
    
    # Save to file
    output_file = '/Users/danielkang/tokyobeta-data-consolidation/docs/STAGING_ACTIVE_TABLES_CONFIRMED.md'
    with open(output_file, 'w') as f:
        f.write(f"# Staging Tables with Recent Activity - CONFIRMED\n\n")
        f.write(f"**Analysis Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Cutoff Date:** {cutoff_date}\n")
        f.write(f"**Method:** Direct database queries\n\n")
        f.write(f"## Summary\n\n")
        f.write(f"- **Total staging tables:** {len(tables)}\n")
        f.write(f"- **Tables with recent activity:** {len(active_tables)}\n")
        f.write(f"- **Tables without recent activity:** {len(inactive_tables)}\n")
        f.write(f"- **Tables without date columns:** {len(no_date_cols_tables)}\n")
        f.write(f"- **Active percentage:** {len(active_tables)/len(tables)*100:.1f}%\n\n")
        
        f.write(f"## Tables with Recent Activity ({len(active_tables)})\n\n")
        f.write("| Table Name | Total Rows | Recent Records | Latest Date | Date Columns |\n")
        f.write("|------------|------------|----------------|-------------|-------------|\n")
        for table in sorted(active_tables, key=lambda x: x['recent_records'], reverse=True):
            f.write(f"| {table['name']} | {table['total_rows']:,} | {table['recent_records']:,} | {table['latest_date']} | {table['date_columns']} |\n")
        
        f.write(f"\n## Tables without Recent Activity ({len(inactive_tables)})\n\n")
        f.write("| Table Name | Total Rows | Latest Date | Date Columns |\n")
        f.write("|------------|------------|-------------|-------------|\n")
        for table in sorted(inactive_tables, key=lambda x: x['total_rows'], reverse=True):
            f.write(f"| {table['name']} | {table['total_rows']:,} | {table['latest_date']} | {table['date_columns']} |\n")
        
        f.write(f"\n## Tables without Date Columns ({len(no_date_cols_tables)})\n\n")
        f.write("| Table Name | Total Rows |\n")
        f.write("|------------|-----------|\n")
        for table in sorted(no_date_cols_tables, key=lambda x: x['total_rows'], reverse=True):
            f.write(f"| {table['name']} | {table['total_rows']:,} |\n")
    
    print(f"\nResults saved to: {output_file}")

if __name__ == "__main__":
    main()
