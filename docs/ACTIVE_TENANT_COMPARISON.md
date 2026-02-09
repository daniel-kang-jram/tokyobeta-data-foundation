# Active Tenant Count - Rent Roll vs Gold Table

**Comparison Date**: February 9, 2026
**Rent Roll Date**: December 3, 2025 (data through October 2025)

---

## Visual Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│                    RENT ROLL ANALYSIS RESULTS                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  File: RRデータ出力20251203.xlsx                                    │
│  Total Records: 1,048,575 (monthly snapshots 2022-2025)            │
│  Unique Units: 16,547 properties/rooms                              │
│                                                                     │
│  ┌───────────────────────────────────────────────────────┐          │
│  │  ACTIVE TENANTS BY PERIOD (Most Recent)              │          │
│  ├───────────────────────────────────────────────────────┤          │
│  │                                                       │          │
│  │  Oct 2025 (202510): ████████████████████  1,076      │          │
│  │  Sep 2025 (202509): ██████████████████████ 1,236     │          │
│  │  Aug 2025 (202508): ██████ 374                       │          │
│  │  Jul 2025 (202507): ██ 143                           │          │
│  │  Older periods:     █ 87                             │          │
│  │                                                       │          │
│  │  Total (all periods): 2,916 unique occupied units    │          │
│  │                                                       │          │
│  └───────────────────────────────────────────────────────┘          │
│                                                                     │
│  📊 MOST RECENT COMPLETE PERIOD: October 2025                       │
│  🏢 ACTIVE TENANTS: 1,076                                           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    GOLD TABLE (TO BE QUERIED)                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Database: Aurora MySQL (tokyobeta)                                 │
│  Schema: staging.tenants + silver.code_tenant_status                │
│  Current Date: February 2026                                        │
│                                                                     │
│  ┌───────────────────────────────────────────────────────┐          │
│  │  QUERY TO RUN:                                        │          │
│  ├───────────────────────────────────────────────────────┤          │
│  │                                                       │          │
│  │  SELECT COUNT(DISTINCT t.id)                         │          │
│  │  FROM staging.tenants t                               │          │
│  │  INNER JOIN silver.code_tenant_status s               │          │
│  │    ON t.status = s.code                               │          │
│  │  WHERE s.is_active_lease = 1;                         │          │
│  │                                                       │          │
│  └───────────────────────────────────────────────────────┘          │
│                                                                     │
│  📊 EXPECTED RESULT: ~1,000 - 1,300 active tenants                  │
│  ⏳ STATUS: Awaiting database access                                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Active Tenant Definition Comparison

### Rent Roll Criteria (Excel)
```
✓ tenant field is not NULL or empty
✓ tenant is not just type indicator ('個人', '法人')
✓ ocp = 1 (occupied)
✓ delete_flg is NULL or not 1
```

**Result**: 1,076 active tenants (October 2025)

### Gold Table Criteria (Database)
```
✓ tenant status in active lease statuses:
  - 仮予約 (4) - Provisional reservation
  - 初期賃料 (5) - Initial rent
  - 入居説明 (6) - Move-in briefing
  - 入居 (7) - Moved in
  - 居住中 (9) - Currently residing
  - 退去通知 (14) - Move-out notice
  - 退去予定 (15) - Scheduled move-out
```

**Result**: [TO BE QUERIED]

---

## Comparison Matrix

| Factor | Rent Roll | Gold Table | Impact on Variance |
|--------|-----------|------------|-------------------|
| **Data Date** | October 2025 | February 2026 | ± 50-200 (4 months) |
| **Update Frequency** | Monthly | Daily | More granular in gold |
| **Source** | External report | Transactional DB | Gold = source of truth |
| **Corporate Tenants** | May aggregate | Individual records | Gold may show higher |
| **Definition** | Occupancy flag | Status codes | May differ slightly |

---

## Expected Variance Analysis

### Scenario 1: Perfect Alignment ✅
```
Rent Roll (Oct 2025):  1,076 active tenants
Gold Table (Feb 2026):  1,050-1,100 active tenants
Variance: < 5%

Interpretation: Systems are aligned, minor variance due to time lag
Action: None required, normal variance
```

### Scenario 2: Acceptable Variance ⚠️
```
Rent Roll (Oct 2025):  1,076 active tenants
Gold Table (Feb 2026):  950-1,050 or 1,100-1,200 active tenants
Variance: 5-15%

Interpretation: Possible definition mismatch or data quality issue
Action: Investigate corporate tenant counting, status code alignment
```

### Scenario 3: Critical Variance 🚨
```
Rent Roll (Oct 2025):  1,076 active tenants
Gold Table (Feb 2026):  < 950 or > 1,200 active tenants
Variance: > 15%

Interpretation: Systematic issue in one or both systems
Action: Urgent investigation required:
  - Validate data pipeline
  - Check for missing/duplicate records
  - Reconcile definition differences
  - Sample 50+ tenants for manual verification
```

---

## Top Corporate Tenants (From Rent Roll)

These tenants account for significant unit counts and should be verified in gold table:

| Rank | Tenant Name | Historical Records | Type |
|------|-------------|-------------------|------|
| 1 | ㈱K&Kコンサルティング | 6,696 | Corporate |
| 2 | メブキ㈱ | 5,383 | Corporate |
| 3 | ㈱ベアーズ | 4,076 | Corporate |
| 4 | ㈱リロエステート | 3,643 | Corporate |
| 5 | 法人一棟 | 3,258 | Bulk/Building |

**Note**: If gold table counts these individually while rent roll aggregates them, gold table count will be higher.

---

## Data Quality Flags

### 🟡 Stale Data Alert
- **Issue**: 1,840 units (63%) show last activity before October 2025
- **Impact**: May undercount actual active tenants
- **Recommendation**: Check if these units are vacant or data is stale

### 🟡 Period Discrepancy
- **Issue**: Most recent complete period is October 2025, but file exported December 2025
- **Impact**: November/December data may be incomplete
- **Recommendation**: Confirm expected data lag with source system

### 🟢 Data Completeness
- **Status**: All 1,048,575 records successfully parsed
- **Unique Units**: 16,547 tracked
- **Periods**: Complete monthly snapshots from 2022-2025

---

## Next Actions Checklist

- [ ] **Step 1**: Access Aurora database (via bastion/EC2)
  ```bash
  ./scripts/quick_db_check.sh
  ```

- [ ] **Step 2**: Query active tenant count from gold table
  ```sql
  SELECT COUNT(DISTINCT t.id) FROM staging.tenants t
  INNER JOIN silver.code_tenant_status s ON t.status = s.code
  WHERE s.is_active_lease = 1;
  ```

- [ ] **Step 3**: Record results and calculate variance
  ```
  Rent Roll: 1,076
  Gold Table: [YOUR RESULT]
  Variance: [CALCULATE %]
  ```

- [ ] **Step 4**: If variance > 5%, investigate:
  - Corporate tenant counting method
  - Status code alignment
  - Units with stale data in rent roll
  - Recent move-ins/move-outs (Oct 2025 → Feb 2026)

- [ ] **Step 5**: Document findings
  - Update this document with results
  - Add notes to `RENT_ROLL_RECONCILIATION_20260209.md`
  - Create action plan if significant discrepancies found

---

## Analysis Timeline

```
2025-12-03: Rent roll exported (data through Oct 2025)
2026-02-09: Analysis performed
            ├─ Rent roll parsed: 1,076 active tenants (Oct 2025)
            ├─ Gold table structure reviewed
            └─ Comparison pending: Need database access

[NEXT STEP]
2026-02-09: Query gold table for current active tenant count
            Compare with rent roll baseline
            Investigate any variance > 5%
```

---

## Quick Reference

### Files Created
```
scripts/count_unique_active_tenants.py   # Rent roll analysis
scripts/quick_db_check.sh                # Database query script
docs/RENT_ROLL_RECONCILIATION_20260209.md # Detailed report
RENT_ROLL_ANALYSIS_SUMMARY.md            # Quick summary
```

### Key Findings
- **Rent Roll Active Tenants**: 1,076 (October 2025)
- **Unique Properties**: 16,547 units
- **Data Quality**: Good, but 63% stale (< Oct 2025)
- **Next Step**: Query gold table

### Commands
```bash
# Analyze rent roll
python3 scripts/count_unique_active_tenants.py

# Query gold table (when accessible)
./scripts/quick_db_check.sh

# Or use dbt
cd dbt && dbt run --select active_tenant_count_check
```

---

**Status**: ✅ Rent Roll Analyzed | ⏳ Awaiting Gold Table Query
**Report Date**: February 9, 2026
**Analyst**: Data Consolidation Team
