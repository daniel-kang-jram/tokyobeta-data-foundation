#!/usr/bin/env python3
"""
Analyze rent roll Excel vs Gold table active tenant count.
Cross-check data consistency.
"""

import sys
import os
from collections import Counter
from datetime import datetime

try:
    import openpyxl
except ImportError:
    print("Installing openpyxl...")
    os.system("pip3 install openpyxl --break-system-packages --quiet")
    import openpyxl

def analyze_rent_roll(file_path):
    """Analyze rent roll Excel file for active tenants."""
    
    print("="*80)
    print("RENT ROLL ANALYSIS")
    print("="*80)
    print(f"File: {file_path}\n")
    
    # Load workbook (read-only for speed with large file)
    print("Loading workbook...")
    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    sheet = wb.active
    
    # Read headers
    rows_iter = sheet.iter_rows(values_only=True)
    headers = next(rows_iter)
    
    print(f"Sheet: {sheet.title}")
    print(f"Columns: {len(headers)}")
    print(f"Key columns: tenant, unit, ocp, delete_flg, period_year_month\n")
    
    # Find column indices
    col_indices = {h: i for i, h in enumerate(headers) if h}
    
    required_cols = ['tenant', 'unit', 'ocp', 'delete_flg', 'period_year_month', 'asset_id']
    for col in required_cols:
        if col not in col_indices:
            print(f"Warning: Column '{col}' not found!")
    
    # Read all data and analyze
    print("Reading all rows...")
    total_rows = 0
    active_tenants = []
    
    tenant_idx = col_indices.get('tenant')
    ocp_idx = col_indices.get('ocp')
    delete_idx = col_indices.get('delete_flg')
    unit_idx = col_indices.get('unit')
    period_idx = col_indices.get('period_year_month')
    asset_idx = col_indices.get('asset_id')
    
    for row in rows_iter:
        total_rows += 1
        
        if tenant_idx is not None:
            tenant = row[tenant_idx]
            ocp = row[ocp_idx] if ocp_idx is not None else None
            delete_flg = row[delete_idx] if delete_idx is not None else None
            unit = row[unit_idx] if unit_idx is not None else None
            period = row[period_idx] if period_idx is not None else None
            asset_id = row[asset_idx] if asset_idx is not None else None
            
            # Determine if this is an active tenant
            # Logic: tenant not null, ocp=1 (occupied), delete_flg not 1
            is_active = (
                tenant is not None and 
                tenant not in ['', ' ', '個人', '法人'] and  # Not just type indicator
                str(tenant).strip() != '' and
                ocp == 1 and  # Occupied
                (delete_flg is None or delete_flg != 1)  # Not deleted
            )
            
            if is_active:
                active_tenants.append({
                    'tenant': tenant,
                    'unit': unit,
                    'ocp': ocp,
                    'delete_flg': delete_flg,
                    'period': period,
                    'asset_id': asset_id
                })
        
        # Progress indicator
        if total_rows % 10000 == 0:
            print(f"  Processed {total_rows} rows... ({len(active_tenants)} active tenants so far)")
    
    wb.close()
    
    print(f"\n✓ Processed {total_rows} total rows")
    print("="*80)
    
    return total_rows, active_tenants

def analyze_tenants(active_tenants):
    """Analyze active tenant data."""
    
    print("\nACTIVE TENANT ANALYSIS")
    print("="*80)
    print(f"Total active tenants: {len(active_tenants)}")
    
    if not active_tenants:
        print("No active tenants found!")
        return
    
    # Analyze by period
    periods = Counter(t['period'] for t in active_tenants)
    print(f"\nBy period/month:")
    for period, count in sorted(periods.items(), reverse=True)[:10]:
        print(f"  {period}: {count} tenants")
    
    # Analyze by asset
    assets = Counter(t['asset_id'] for t in active_tenants)
    print(f"\nBy asset (top 10):")
    for asset, count in assets.most_common(10):
        print(f"  {asset}: {count} tenants")
    
    # Analyze tenant types (if identifiable)
    tenant_values = Counter(t['tenant'] for t in active_tenants)
    print(f"\nUnique tenant values: {len(tenant_values)}")
    print(f"Sample tenant values (top 10):")
    for tenant, count in tenant_values.most_common(10):
        tenant_str = str(tenant)[:50]  # Truncate long names
        print(f"  {tenant_str}: {count}")
    
    # Show sample records
    print(f"\nSample active tenant records (first 5):")
    for i, t in enumerate(active_tenants[:5], 1):
        print(f"\n  {i}. Asset: {t['asset_id']}, Unit: {t['unit']}, Period: {t['period']}")
        print(f"     Tenant: {t['tenant']}, OCP: {t['ocp']}, Delete: {t['delete_flg']}")
    
    print("="*80)

def main():
    file_path = "data/RRデータ出力20251203.xlsx"
    
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        sys.exit(1)
    
    # Analyze rent roll
    total_rows, active_tenants = analyze_rent_roll(file_path)
    analyze_tenants(active_tenants)
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total rows in rent roll: {total_rows}")
    print(f"Active tenants identified: {len(active_tenants)}")
    print(f"\nActive tenant criteria:")
    print(f"  - tenant field is not null/empty")
    print(f"  - ocp = 1 (occupied)")
    print(f"  - delete_flg is null or not 1")
    print("="*80)
    
    print("\n" + "="*80)
    print("NEXT STEPS: Compare with Gold Table")
    print("="*80)
    print("To compare with gold table, run:")
    print("  SELECT COUNT(DISTINCT tenant_id)")
    print("  FROM gold.stg_tenants") 
    print("  WHERE is_active_lease = 1")
    print("")
    print("Or check the most recent data in:")
    print("  - gold.daily_activity_summary")
    print("  - gold.new_contracts")
    print("="*80)

if __name__ == "__main__":
    main()
