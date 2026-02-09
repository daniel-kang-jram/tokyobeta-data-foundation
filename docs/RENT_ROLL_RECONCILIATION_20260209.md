# Rent Roll vs Gold Table Reconciliation Report

**Date**: February 9, 2026
**Analyst**: Data Consolidation Team
**Rent Roll File**: `data/RRデータ出力20251203.xlsx` (exported December 3, 2025)

---

## Executive Summary

Analyzed rent roll Excel file containing historical property management data and identified discrepancies with expected active tenant counts. The rent roll contains **1,048,575 total records** spanning multiple periods (2022-2025) with monthly snapshots for each unit.

### Key Findings

| Metric | Value | Notes |
|--------|-------|-------|
| **Total Rent Roll Records** | 1,048,575 | Historical snapshots (monthly) |
| **Unique Asset+Unit Combinations** | 16,547 | Unique properties/rooms tracked |
| **Active Tenants (Most Recent Period)** | 1,076 | October 2025 (202510) |
| **Total Active Tenants (All Periods)** | 2,916 | Includes units with last activity in older periods |

---

## Rent Roll Data Structure

### File Metadata
- **Sheet Name**: RR全履歴 (All Rent Roll History)
- **Columns**: 36 fields
- **Period Range**: January 2022 (202201) to October 2025 (202510)
- **Export Date**: December 3, 2025

### Key Columns Identified

| Column Name | Description | Data Type |
|-------------|-------------|-----------|
| `tenant` | Tenant name or identifier | String |
| `unit` | Unit/room number | String/Integer |
| `asset_id` | Property asset ID (e.g., J0083979) | String |
| `ocp` | Occupancy flag (1 = occupied, 0 = vacant) | Integer |
| `delete_flg` | Deletion flag (1 = deleted, NULL = active) | Integer |
| `period_year_month` | Period (YYYYMM format) | Integer |
| `contract_start_date` | Contract start date | DateTime |
| `contract_end_date` | Contract end date | DateTime |
| `base_rent_amt` | Base rent amount | Decimal |

---

## Active Tenant Definition

For reconciliation purposes, we defined **active tenants** as records meeting ALL criteria:

1. ✅ `tenant` field is not NULL or empty
2. ✅ `tenant` is not just a type indicator ('個人', '法人')
3. ✅ `ocp` = 1 (occupied)
4. ✅ `delete_flg` is NULL or not 1 (not deleted)

---

## Active Tenant Analysis by Period

### Most Recent Periods (Last 12 Months)

| Period | Year-Month | Active Tenants | % of Total |
|--------|------------|----------------|------------|
| 202510 | 2025-10 | **1,076** | 36.9% |
| 202509 | 2025-09 | 1,236 | 42.4% |
| 202508 | 2025-08 | 374 | 12.8% |
| 202507 | 2025-07 | 143 | 4.9% |
| 202506 | 2025-06 | 49 | 1.7% |
| 202505 | 2025-05 | 14 | 0.5% |
| 202504 | 2025-04 | 6 | 0.2% |
| 202503 | 2025-03 | 2 | 0.1% |
| 202501 | 2025-01 | 4 | 0.1% |
| Older | 2022-2024 | 12 | 0.4% |
| **Total** | | **2,916** | **100%** |

### Key Observations

1. **October 2025 is the most recent complete period** with 1,076 active tenants
2. **September 2025 shows higher count** (1,236) - may indicate data lag or November/December incomplete
3. **Older periods still show active tenants** - suggests some units haven't been updated in recent months

---

## Top Properties by Active Tenants

Based on most recent period data:

| Asset ID | Active Tenant Records | % of Total |
|----------|----------------------|------------|
| J0083436 | 1,568 | 0.5% |
| J0084032 | 1,341 | 0.4% |
| J0083437 | 1,279 | 0.4% |
| J0084656 | 1,256 | 0.4% |
| J0083520 | 1,243 | 0.4% |
| J0083528 | 1,213 | 0.4% |
| J0083508 | 1,190 | 0.4% |
| J0083902 | 1,126 | 0.4% |
| J0084371 | 1,118 | 0.4% |
| J0084060 | 1,115 | 0.4% |

**Note**: These are historical record counts, not unique active tenants.

---

## Top Tenants (Corporate/Bulk Contracts)

The rent roll shows several corporate/bulk tenants with multiple units:

| Tenant Name | Unit Count | Type |
|-------------|-----------|------|
| ㈱K&Kコンサルティング | 6,696 | Corporate |
| メブキ㈱ | 5,383 | Corporate |
| ㈱ベアーズ | 4,076 | Corporate |
| ㈱リロエステート | 3,643 | Corporate |
| 法人一棟 | 3,258 | Corporate Bulk |
| ㈱インフォレント | 2,647 | Corporate |
| ㈱フジ国際交流センター | 1,667 | Corporate |
| ㈱ケイ・マックス | 1,637 | Corporate |
| タイヨー㈱ | 1,493 | Corporate |
| (合)Ｓｉｍｐｌｉｃｉｔｙ | 1,319 | Corporate |

**Total unique tenant identifiers**: 17,641

---

## Comparison with Gold Table (Expected)

### Gold Table Definition of Active Tenants

According to the dbt model `stg_tenants.sql`, active tenants are defined as:

```sql
FROM staging.tenants t
INNER JOIN code_tenant_status s ON t.status = s.code
WHERE s.is_active_lease = 1
```

Active lease statuses include:
- 仮予約 (4) - Provisional reservation
- 初期賃料 (5) - Initial rent
- 入居説明 (6) - Move-in briefing
- 入居 (7) - Moved in
- 居住中 (9) - Currently residing
- 退去通知 (14) - Move-out notice (still occupying)
- 退去予定 (15) - Scheduled move-out (still occupying)

### Reconciliation Gaps

| Source | Active Tenant Count | Date/Period | Notes |
|--------|---------------------|-------------|-------|
| **Rent Roll** | **1,076** | October 2025 | Most recent complete period |
| **Gold Table** | **[TO BE QUERIED]** | Current (Feb 2026) | Requires database access |
| **Expected Difference** | ± 50-200 | Time lag | 4 months between RR and current |

---

## Potential Discrepancy Causes

### 1. Time Difference (4 Months)
- Rent roll: October 2025
- Current date: February 2026
- **Expected impact**: ±50-200 tenants (move-ins/move-outs over 4 months)

### 2. Definition Mismatch
- **Rent roll**: Uses `ocp=1` (occupancy flag)
- **Gold table**: Uses tenant status codes (4,5,6,7,9,14,15)
- **Potential impact**: Discrepancies if status codes don't perfectly align with occupancy

### 3. Data Update Frequency
- Rent roll may update monthly (by period)
- Gold table updates daily from source system
- **Potential impact**: More granular updates in gold table

### 4. Corporate/Bulk Contracts
- Some corporate entries (e.g., "法人一棟") represent entire buildings
- Gold table may break these into individual tenant records
- **Potential impact**: Gold table could show higher counts

### 5. Data Quality Issues
- 2,916 total active units across all periods (not just October)
- 1,840 units (63%) show last activity before October 2025
- **Potential impact**: Stale data in older periods

---

## Recommended Actions

### 1. Query Gold Table for Current Active Count ✅
**Priority**: HIGH
**Action**: Run the following query on Aurora:

```sql
-- Option 1: Count from staging.tenants
SELECT COUNT(DISTINCT t.id) as active_tenant_count
FROM staging.tenants t
INNER JOIN silver.code_tenant_status s ON t.status = s.code
WHERE s.is_active_lease = 1;

-- Option 2: Count from stg_tenants view
SELECT COUNT(*) as active_tenant_count
FROM silver.stg_tenants
WHERE is_active_lease = 1;

-- Option 3: Breakdown by contract type
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
GROUP BY tenant_type;
```

### 2. Investigate Stale Rent Roll Data 📊
**Priority**: MEDIUM
**Issue**: 1,840 units showing last activity before October 2025

**Actions**:
- Identify which properties/units have stale data
- Determine if these units are truly vacant or data hasn't been updated
- Cross-reference with gold table for these specific units

**Query for investigation**:
```sql
-- Find units in rent roll with stale data
-- (Last activity before October 2025)
SELECT asset_id, unit, MAX(period) as last_period
FROM rent_roll
GROUP BY asset_id, unit
HAVING MAX(period) < 202510
ORDER BY last_period;
```

### 3. Reconcile Corporate Tenant Counts 🏢
**Priority**: MEDIUM
**Issue**: Top 10 corporate tenants represent ~31,000 historical records

**Actions**:
- Verify if corporate bulk contracts are properly broken down in gold table
- Check if "法人一棟" (corporate entire building) entries are counted correctly
- Ensure consistency between rent roll aggregation and gold table individual records

### 4. Establish Monthly Reconciliation Process 🔄
**Priority**: MEDIUM-HIGH
**Objective**: Regular cross-checks to catch discrepancies early

**Process**:
1. Monthly rent roll export from source system
2. Compare active tenant count with gold table
3. Investigate any variances > 5%
4. Document findings and corrections

### 5. Validate Occupancy Flag Logic 🚩
**Priority**: LOW-MEDIUM
**Issue**: Ensure `ocp=1` in rent roll matches `is_active_lease=1` in gold table

**Actions**:
- Sample 20-30 random tenants
- Check status in both systems
- Document any mismatches
- Update business rules if needed

---

## Next Steps

1. **Immediate** (Today):
   - [ ] Connect to Aurora database (via bastion/SSM)
   - [ ] Run active tenant count queries
   - [ ] Compare with rent roll October 2025 count (1,076)

2. **Short-term** (This Week):
   - [ ] Investigate units with stale data (last activity < Oct 2025)
   - [ ] Analyze corporate tenant record aggregation
   - [ ] Document any systematic discrepancies

3. **Medium-term** (This Month):
   - [ ] Set up automated monthly reconciliation
   - [ ] Create dashboard for active tenant tracking
   - [ ] Implement alerts for count variance > 5%

---

## Technical Notes

### Rent Roll Analysis Script
- **Location**: `scripts/count_unique_active_tenants.py`
- **Runtime**: ~58 seconds for 1M+ rows
- **Method**: De-duplicate by `(asset_id, unit)` keeping most recent period

### Gold Table Query Script
- **Location**: `scripts/query_gold_active_tenants.py`
- **Status**: Requires VPN/bastion access to Aurora
- **Alternative**: Use dbt run for ad-hoc queries

### Analysis Model
- **Location**: `dbt/models/analysis/active_tenant_count_check.sql`
- **Purpose**: Temporary dbt model for reconciliation
- **Output**: Summary metrics for comparison

---

## Appendix: Sample Rent Roll Records

**Row 1** (Active):
```
Asset: J0083973, Unit: 206, Period: 202305
Tenant: 法人 93141
OCP: 1 (Occupied)
Delete Flag: NULL (Active)
Rent: ¥50,000
```

**Row 2** (Active):
```
Asset: J0083973, Unit: 203, Period: 202310
Tenant: 法人 93135
OCP: 1 (Occupied)
Delete Flag: NULL (Active)
Rent: ¥50,000
```

---

## Contact

For questions about this reconciliation report:
- **Data Team**: data-team@tokyobeta.com
- **Source**: Rent Roll Excel Analysis + Gold Table Schema Review

---

**Report Generated**: February 9, 2026
**Last Updated**: February 9, 2026
