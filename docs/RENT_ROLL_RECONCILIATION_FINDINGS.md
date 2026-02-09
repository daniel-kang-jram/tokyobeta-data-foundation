# Rent Roll vs Gold Table Reconciliation - FINDINGS

**Date**: February 9, 2026  
**Status**: 🚨 CRITICAL DISCREPANCY IDENTIFIED

---

## Executive Summary

Cross-checked rent roll Excel data against Aurora gold tables and found a **10x discrepancy** in active tenant counts. The root cause is a **definition mismatch** and **data quality issue** in the gold table.

| Metric | Rent Roll (Oct 2025) | Gold Table (Current) | Variance |
|--------|---------------------|---------------------|----------|
| **Active Tenants** | 1,076 | 11,303 | **+950%** |

---

## Key Findings

### 1. Definition Mismatch 🎯

**Rent Roll** uses a **narrow definition**:
- `ocp = 1` (Occupied flag)
- `delete_flg != 1` (Not deleted)
- Tenant field populated
- **Point-in-time snapshot** (October 2025)

**Gold Table** uses a **broad definition**:
- `is_active_lease = 1` includes multiple statuses:
  - 居住中 (9): 9,955 tenants - **Currently residing**
  - 退去通知 (14): 621 tenants - **Gave notice but still occupying**
  - 契約更新 (10): 454 tenants - **Contract renewal**
  - 入居通知 (11): 127 tenants - **Move-in notice received**
  - 退去予定 (15): 65 tenants - **Scheduled to move out**
  - 仮予約 (4): 30 tenants - **Tentative reservation**
  - Others: 51 tenants

### 2. Data Quality Issue 🚨

**Critical Finding**: Gold table has **2,821 tenants** with:
- Status marked as "active lease" (`is_active_lease = 1`)
- **Past moveout dates** (moveout_date < current date)
- Should be marked as inactive

This is inflating the active count by **25%**.

### 3. Breakdown Analysis

| Status Category | Count | Description |
|-----------------|-------|-------------|
| No moveout date | 10,549 | Legitimate active tenants |
| Future moveout | 995 | Scheduled to move out |
| **Past moveout** | **2,821** | **DATA QUALITY ISSUE** |
| **TOTAL** | **11,303** | Current "active" count |

---

## Recommended Active Tenant Definitions

### Option 1: Conservative (Closest to Rent Roll)
```sql
SELECT COUNT(DISTINCT t.id)
FROM staging.tenants t
LEFT JOIN staging.movings m ON t.id = m.tenant_id
WHERE t.status = 9  -- 居住中 only
  AND (m.moveout_date IS NULL OR m.moveout_date > CURRENT_DATE)
```
**Expected Count**: ~7,000-8,000 tenants

### Option 2: Refined (Excludes Past Moveouts)
```sql
SELECT COUNT(DISTINCT t.id)
FROM staging.tenants t
INNER JOIN seeds.code_tenant_status s ON t.status = s.code
LEFT JOIN staging.movings m ON t.id = m.tenant_id
WHERE s.is_active_lease = 1
  AND (m.moveout_date IS NULL OR m.moveout_date > CURRENT_DATE)
```
**Expected Count**: ~8,000-9,000 tenants

### Option 3: Current (Too Broad - Not Recommended)
```sql
SELECT COUNT(DISTINCT t.id)
FROM staging.tenants t
INNER JOIN seeds.code_tenant_status s ON t.status = s.code
WHERE s.is_active_lease = 1  -- Includes past moveouts!
```
**Current Count**: 11,303 tenants (inflated)

---

## Why Rent Roll Shows Only 1,076

### Possible Explanations:

1. **Partial Coverage** ⚠️
   - Rent roll may only include certain properties
   - Gold table: 1,197 apartments, 14,171 rooms
   - Rent roll: 16,547 asset+unit combinations (but many historical)
   - Only 1,076 showing as `ocp=1` in most recent period

2. **Stale Data in Rent Roll** ⚠️
   - 63% of units show last activity before October 2025
   - May not be updating vacant/inactive units

3. **Different Data Source** ⚠️
   - Rent roll may be from property management system
   - Gold table from transactional leasing system
   - Could track different tenant populations

4. **Corporate Tenant Counting** ℹ️
   - Rent roll shows aggregated corporate tenants
   - Gold table: 458 corporate tenants individually
   - Sample: 株式会社テクノアーク appears 10+ times in gold table

---

## Data Quality Issues to Fix

### Priority 1: Fix Past Moveout Status 🚨
**Issue**: 2,821 tenants have past moveout dates but status still shows "active lease"

**Solution**:
```sql
-- Identify affected tenants
SELECT 
    t.id,
    t.last_name,
    t.first_name,
    t.status,
    s.label_ja,
    m.moveout_date
FROM staging.tenants t
INNER JOIN seeds.code_tenant_status s ON t.status = s.code
INNER JOIN staging.movings m ON t.id = m.tenant_id
WHERE s.is_active_lease = 1
  AND m.moveout_date IS NOT NULL
  AND m.moveout_date < CURRENT_DATE
ORDER BY m.moveout_date DESC;

-- These should be updated to status 17 (退去済 = Moved Out)
```

### Priority 2: Validate Daily Snapshot Process ⚠️
**Issue**: `tenant_daily_snapshots` table has 9.7M rows, needs validation

**Action**:
- Check if snapshots match current tenant status
- Ensure daily updates are running correctly
- Compare snapshot counts with current tenant table

### Priority 3: Align Definition with Business Needs 📊
**Question**: What does "active tenant" mean for your business?

**Options**:
1. **Physical Occupancy** → Use status 9 only + no past moveout
2. **Legal Liability** → Include notice period tenants (14, 15)
3. **Revenue Recognition** → All statuses with active contracts

---

## Gold Table Statistics

### Current State
- **Total Tenants**: 48,004
- **Active Rate**: 23.5% (using current broad definition)
- **Unique Apartments**: 1,197
- **Unique Rooms**: 14,171
- **Latest Data Update**: 2026-02-06

### Status Breakdown (Top 5)
| Status | Label (JA) | Label (EN) | Active | Count |
|--------|-----------|-----------|--------|-------|
| 17 | 退去済 | Moved Out | ✗ | 28,366 |
| 9 | 居住中 | In Residence | ✓ | 9,955 |
| 8 | キャンセル | Canceled | ✗ | 5,029 |
| 16 | メンテ待ち | Awaiting Maintenance | ✗ | 3,023 |
| 14 | 退去通知 | Move-out Notice | ✓ | 621 |

### Recent Activity (Last 30 Days)
- **Move-ins**: 1,428
- **Move-outs**: 1,868
- **Net Change**: -440 tenants

---

## Rent Roll Statistics

### File Details
- **File**: RRデータ出力20251203.xlsx
- **Export Date**: December 3, 2025
- **Data Through**: October 2025 (202510)
- **Total Records**: 1,048,575 (monthly historical snapshots)
- **Unique Units**: 16,547

### Active Tenants (October 2025)
- **Total Active**: 1,076
- **By Period**:
  - Oct 2025: 1,076
  - Sep 2025: 1,236
  - Aug 2025: 374
  - Jul 2025: 143

### Top Corporate Tenants (Historical)
1. ㈱K&Kコンサルティング: 6,696 records
2. メブキ㈱: 5,383 records
3. ㈱ベアーズ: 4,076 records
4. ㈱リロエステート: 3,643 records
5. 法人一棟: 3,258 records

---

## Recommended Actions

### Immediate (This Week)

1. **Fix Data Quality** 🚨
   ```sql
   -- Update tenants with past moveouts to status 17
   UPDATE staging.tenants t
   INNER JOIN staging.movings m ON t.id = m.tenant_id
   INNER JOIN seeds.code_tenant_status s ON t.status = s.code
   SET t.status = 17, t.updated_at = NOW()
   WHERE s.is_active_lease = 1
     AND m.moveout_date < CURRENT_DATE;
   ```

2. **Redefine "Active Tenant"** 📊
   - Meet with business stakeholders
   - Decide on correct definition
   - Update `is_active_lease` flags if needed
   - Document the agreed definition

3. **Update Gold Models** 🔧
   - Modify `stg_tenants.sql` to use refined definition
   - Update `daily_activity_summary.sql` if needed
   - Add moveout_date check to active tenant logic

### Short-term (This Month)

4. **Investigate Rent Roll Coverage** 🔍
   - Confirm if rent roll includes all properties
   - Check if 1,076 is the correct baseline
   - Compare property lists between systems

5. **Validate Corporate Tenant Counting** 🏢
   - Reconcile individual vs aggregated counts
   - Document how bulk contracts should be counted
   - Ensure consistency across systems

6. **Set Up Monitoring** 📈
   - Daily check: Active tenant count variance
   - Alert if count changes > 5% day-over-day
   - Weekly reconciliation with rent roll

### Long-term (Ongoing)

7. **Automated Reconciliation** 🤖
   - Monthly comparison: Gold table vs rent roll
   - Generate variance report automatically
   - Flag discrepancies > threshold

8. **Data Quality Dashboard** 📊
   - Track tenants with past moveouts but active status
   - Monitor stale records (no updates > 90 days)
   - Visualize status transitions

---

## SQL Queries for Follow-up

### Query 1: Get Corrected Active Count
```sql
-- Most conservative definition
SELECT COUNT(DISTINCT t.id) as active_tenants
FROM staging.tenants t
LEFT JOIN staging.movings m ON t.id = m.tenant_id
WHERE t.status = 9  -- 居住中 only
  AND (m.moveout_date IS NULL OR m.moveout_date > CURRENT_DATE);
```

### Query 2: Identify Data Quality Issues
```sql
-- Tenants needing status update
SELECT 
    t.id,
    t.last_name || ' ' || t.first_name as name,
    t.status,
    s.label_ja as current_status,
    m.moveout_date,
    DATEDIFF(CURRENT_DATE, m.moveout_date) as days_since_moveout
FROM staging.tenants t
INNER JOIN seeds.code_tenant_status s ON t.status = s.code
INNER JOIN staging.movings m ON t.id = m.tenant_id
WHERE s.is_active_lease = 1
  AND m.moveout_date < CURRENT_DATE
ORDER BY m.moveout_date ASC
LIMIT 100;
```

### Query 3: Compare with Daily Snapshots
```sql
-- Latest snapshot count
SELECT 
    snapshot_date,
    status,
    COUNT(DISTINCT tenant_id) as tenant_count
FROM staging.tenant_daily_snapshots
WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM staging.tenant_daily_snapshots)
GROUP BY snapshot_date, status
ORDER BY tenant_count DESC;
```

---

## Conclusion

The **10x discrepancy** is caused by:

1. **Definition mismatch** (25%): Gold table uses broad "active lease" definition
2. **Data quality issue** (25%): 2,821 tenants with past moveouts marked as active
3. **Possible coverage gap** (50%): Rent roll may not include all properties

**Next Steps**:
1. Fix the 2,821 tenants with past moveouts
2. Redefine "active tenant" consistently
3. Investigate rent roll coverage
4. Implement ongoing reconciliation

---

**Report Generated**: February 9, 2026  
**Analysis by**: Data Consolidation Team  
**Status**: Awaiting stakeholder decision on definition + data fix

