#!/usr/bin/env python3
"""
Count unique active tenants from rent roll as of most recent period.
De-duplicate by asset_id + unit combination.
"""

import sys
import os
from collections import defaultdict

try:
    import openpyxl
except ImportError:
    print("Installing openpyxl...")
    os.system("pip3 install openpyxl --break-system-packages --quiet")
    import openpyxl

def count_unique_active_tenants(file_path):
    """Count unique active tenants as of most recent period."""
    
    print("="*80)
    print("UNIQUE ACTIVE TENANT COUNT")
    print("="*80)
    print(f"File: {file_path}\n")
    
    # Load workbook
    print("Loading workbook...")
    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    sheet = wb.active
    
    # Read headers
    rows_iter = sheet.iter_rows(values_only=True)
    headers = next(rows_iter)
    col_indices = {h: i for i, h in enumerate(headers) if h}
    
    # Get column indices
    tenant_idx = col_indices.get('tenant')
    ocp_idx = col_indices.get('ocp')
    delete_idx = col_indices.get('delete_flg')
    unit_idx = col_indices.get('unit')
    period_idx = col_indices.get('period_year_month')
    asset_idx = col_indices.get('asset_id')
    
    print("Reading all rows and tracking most recent period per unit...")
    
    # Track most recent record for each asset+unit combination
    # Key: (asset_id, unit), Value: (period, tenant, ocp, delete_flg)
    unit_records = {}
    total_rows = 0
    max_period_global = 0
    
    for row in rows_iter:
        total_rows += 1
        
        tenant = row[tenant_idx] if tenant_idx is not None else None
        ocp = row[ocp_idx] if ocp_idx is not None else None
        delete_flg = row[delete_idx] if delete_idx is not None else None
        unit = row[unit_idx] if unit_idx is not None else None
        period = row[period_idx] if period_idx is not None else None
        asset_id = row[asset_idx] if asset_idx is not None else None
        
        # Convert period to int for comparison
        try:
            period_int = int(period) if period else 0
        except (ValueError, TypeError):
            period_int = 0
        
        # Track max period
        if period_int > max_period_global:
            max_period_global = period_int
        
        # Create unique key for this unit
        key = (asset_id, unit)
        
        # Keep only the most recent record for each unit
        if key not in unit_records or period_int > unit_records[key][0]:
            unit_records[key] = (period_int, tenant, ocp, delete_flg)
        
        if total_rows % 100000 == 0:
            print(f"  Processed {total_rows} rows... ({len(unit_records)} unique units)")
    
    wb.close()
    
    print(f"\n✓ Processed {total_rows} total rows")
    print(f"✓ Found {len(unit_records)} unique asset+unit combinations")
    print(f"✓ Most recent period in data: {max_period_global}")
    print("="*80)
    
    # Now count active tenants from most recent records
    print("\nCounting active tenants from most recent records...")
    
    active_count = 0
    active_by_period = defaultdict(int)
    
    for (asset_id, unit), (period, tenant, ocp, delete_flg) in unit_records.items():
        # Same criteria as before
        is_active = (
            tenant is not None and 
            tenant not in ['', ' ', '個人', '法人'] and
            str(tenant).strip() != '' and
            ocp == 1 and
            (delete_flg is None or delete_flg != 1)
        )
        
        if is_active:
            active_count += 1
            active_by_period[period] += 1
    
    print(f"\n✓ Active tenants (unique units): {active_count}")
    print("="*80)
    
    # Show distribution by period
    print("\nActive tenant distribution by most recent period:")
    for period in sorted(active_by_period.keys(), reverse=True)[:20]:
        count = active_by_period[period]
        print(f"  {period}: {count} units")
    
    # Count for most recent period only
    most_recent_period = max(active_by_period.keys()) if active_by_period else 0
    most_recent_count = active_by_period[most_recent_period]
    
    print("="*80)
    print(f"\nMOST RECENT PERIOD: {most_recent_period}")
    print(f"Active tenants: {most_recent_count}")
    print("="*80)
    
    return active_count, most_recent_count, most_recent_period, unit_records

def analyze_by_period(unit_records):
    """Analyze active count by specific periods."""
    
    print("\nANALYSIS BY SPECIFIC PERIODS")
    print("="*80)
    
    # Count active units for each period
    period_counts = defaultdict(int)
    
    for (asset_id, unit), (period, tenant, ocp, delete_flg) in unit_records.items():
        is_active = (
            tenant is not None and 
            tenant not in ['', ' ', '個人', '法人'] and
            str(tenant).strip() != '' and
            ocp == 1 and
            (delete_flg is None or delete_flg != 1)
        )
        
        if is_active:
            period_counts[period] += 1
    
    # Show last 6 months
    print("Active tenant count by month (most recent 12 months):")
    for period in sorted(period_counts.keys(), reverse=True)[:12]:
        count = period_counts[period]
        year = period // 100
        month = period % 100
        print(f"  {year}-{month:02d}: {count:,} active tenants")
    
    print("="*80)

def main():
    file_path = "data/RRデータ出力20251203.xlsx"
    
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        sys.exit(1)
    
    active_count, recent_count, recent_period, unit_records = count_unique_active_tenants(file_path)
    analyze_by_period(unit_records)
    
    print("\n" + "="*80)
    print("SUMMARY - UNIQUE ACTIVE TENANTS")
    print("="*80)
    print(f"Total unique occupied units: {active_count}")
    print(f"Most recent period: {recent_period}")
    print(f"Active tenants in most recent period: {recent_count}")
    print("="*80)
    
    print("\n" + "="*80)
    print("NEXT: Query Gold Table for Comparison")
    print("="*80)
    print("Connect to Aurora and run:")
    print("")
    print("-- Current active tenant count")
    print("SELECT COUNT(DISTINCT t.id) as active_tenant_count")
    print("FROM staging.tenants t")
    print("INNER JOIN silver.code_tenant_status s ON t.status = s.code")
    print("WHERE s.is_active_lease = 1;")
    print("")
    print("-- Or check stg_tenants view")
    print("SELECT COUNT(*) FROM silver.stg_tenants")
    print("WHERE is_active_lease = 1;")
    print("="*80)

if __name__ == "__main__":
    main()
