# Daily Activity Summary - Metric Definitions

## Overview
This document explains how each metric in `gold.daily_activity_summary` is calculated, including the source tables, key fields, and business logic.

## Data Quality Status (as of 2026-02-05)

### ✅ Working Metrics
- `contracts_signed_count` - Accurate daily contract counts
- `confirmed_moveins_count` - Accurate daily move-in counts
- `confirmed_moveouts_count` - Accurate daily move-out counts
- `applications_count` - **FIXED**: Now accurately counts Tentative Reservations (status=4)

### ⚠️ Limited Historical Data
- `inquiries_count` - **Historical data only (2018-2023)**: No new inquiries are being recorded since 2023. This is a data collection gap, not a bug. The metric will show `0` for all dates after 2023-05-02.

---

## Metric Definitions

### 1. Inquiries Count (問い合わせ)
**Definition**: Customer inquiries by date

**Source**: `staging.inquiries` table

**Key Fields**:
- `inquiry_date` - Date of inquiry

**Logic**:
```sql
SELECT
    inquiry_date as activity_date,
    'individual' as tenant_type,  -- Default to individual
    COUNT(*) as inquiry_count
FROM staging.inquiries
WHERE inquiry_date IS NOT NULL
  AND inquiry_date >= '2018-01-01'
GROUP BY inquiry_date
```

**Data Quality Notes**:
- ⚠️ **HISTORICAL DATA ONLY**: Latest inquiry date is 2023-05-02
- No new inquiries are being recorded since 2023
- This is a known data collection gap
- All dates after 2023-05-02 will show `inquiries_count = 0`

---

### 2. Applications Count (申し込み - Tentative Reservations)
**Definition**: Count of tenants who reached "Tentative Reservation" status (仮予約) by date

**Source**: `staging.tenants` table

**Key Fields**:
- `status = 4` - Tentative Reservation status
- `created_at` - Date the tenant record was created (proxy for application date)
- `corporate_name` - Used to determine individual vs corporate

**Logic**:
```sql
SELECT
    DATE(t.created_at) as activity_date,
    CASE 
        WHEN t.corporate_name IS NOT NULL THEN 'corporate'
        ELSE 'individual'
    END as tenant_type,
    COUNT(DISTINCT t.id) as application_count
FROM staging.tenants t
WHERE t.status = 4  -- Status 4 = Tentative Reservation (仮予約)
  AND t.created_at IS NOT NULL
  AND t.created_at >= '2018-01-01'
GROUP BY DATE(t.created_at), tenant_type
```

**Business Logic**:
- Status 4 represents "Tentative Reservation" (仮予約)
- Uses `COUNT(DISTINCT t.id)` to avoid duplicate counting
- Groups by `created_at` date (when the tenant first applied)
- Splits by individual vs corporate based on presence of `corporate_name`

**Data Quality Notes**:
- ✅ Now correctly counts distinct tenants with status=4
- Previous issue: Was incorrectly sourcing from `int_contracts` and counting all created contracts
- **Fix applied**: Changed source to `staging.tenants` with `status = 4` filter

---

### 3. Contracts Signed Count (契約締結)
**Definition**: Number of contracts signed by date (契約締結日)

**Source**: `silver.int_contracts` intermediate table

**Key Fields**:
- `contract_date` (mapped from `movings.movein_decided_date`) - Date contract was signed
- `is_valid_contract` - Filter flag to exclude invalid/test contracts
- `tenant_type` - Individual or corporate classification

**Logic**:
```sql
SELECT
    contract_date as activity_date,
    tenant_type,
    COUNT(*) as contract_signed_count
FROM silver.int_contracts
WHERE contract_date IS NOT NULL
  AND is_valid_contract
  AND contract_date >= '2018-01-01'
GROUP BY contract_date, tenant_type
```

**Business Logic**:
- Counts contracts by their `movein_decided_date` (契約締結日)
- Only includes valid contracts (`is_valid_contract = true`)
- `is_valid_contract` is derived from business rules in `int_contracts`:
  - Has a valid contract date
  - Has a valid apartment/room assignment
  - Not a test or cancelled contract

**Source Table Mapping**:
- `contract_date` ← `staging.movings.movein_decided_date`
- Joined with `staging.tenants` for tenant details
- Joined with `staging.apartments` and `staging.rooms` for property details

---

### 4. Confirmed Move-ins Count (確定入居者)
**Definition**: Number of confirmed move-ins by date (契約開始日/入居日)

**Source**: `silver.int_contracts` intermediate table

**Key Fields**:
- `contract_start_date` (mapped from `movings.contract_start_date`) - Actual move-in date
- `is_valid_contract` - Filter flag to exclude invalid contracts
- `tenant_type` - Individual or corporate classification

**Logic**:
```sql
SELECT
    contract_start_date as activity_date,
    tenant_type,
    COUNT(*) as movein_count
FROM silver.int_contracts
WHERE contract_start_date IS NOT NULL
  AND is_valid_contract
  AND contract_start_date >= '2018-01-01'
GROUP BY contract_start_date, tenant_type
```

**Business Logic**:
- Counts contracts by their `contract_start_date` (actual move-in date)
- Only includes valid contracts
- This represents when a tenant actually moved in (not just signed)

**Source Table Mapping**:
- `contract_start_date` ← `staging.movings.contract_start_date`

---

### 5. Confirmed Move-outs Count (確定退去者)
**Definition**: Number of confirmed move-outs by date (退去日)

**Source**: `silver.int_contracts` intermediate table

**Key Fields**:
- `moveout_date` (mapped from `movings.actual_moveout_date`) - Actual move-out date
- `is_completed_moveout` - Filter flag to exclude partial/planned move-outs
- `tenant_type` - Individual or corporate classification

**Logic**:
```sql
SELECT
    moveout_date as activity_date,
    tenant_type,
    COUNT(*) as moveout_count
FROM silver.int_contracts
WHERE moveout_date IS NOT NULL
  AND is_completed_moveout
  AND moveout_date >= '2018-01-01'
GROUP BY moveout_date, tenant_type
```

**Business Logic**:
- Counts contracts by their `actual_moveout_date` (退去日)
- Only includes completed move-outs (`is_completed_moveout = true`)
- `is_completed_moveout` is derived from business rules in `int_contracts`:
  - Has a valid `actual_moveout_date`
  - Move-out date is in the past
  - Not a planned/future move-out

**Source Table Mapping**:
- `moveout_date` ← `staging.movings.actual_moveout_date`

---

### 6. Net Occupancy Delta (稼働室数増減)
**Definition**: Net change in occupied rooms (move-ins minus move-outs)

**Logic**:
```sql
net_occupancy_delta = confirmed_moveins_count - confirmed_moveouts_count
```

**Business Logic**:
- Positive value = more move-ins than move-outs (occupancy increased)
- Negative value = more move-outs than move-ins (occupancy decreased)
- Zero = equal move-ins and move-outs (no net change)

---

## Data Flow

```
staging.inquiries ─────┐
                        │
staging.tenants ────────┼───> gold.daily_activity_summary
                        │      (aggregated by date + tenant_type)
staging.movings ────┐   │
staging.apartments ─┼───┼───> silver.int_contracts ──┘
staging.rooms ──────┘   │
staging.tenants ────────┘
```

---

## Verification Queries

### Check Applications Count
```sql
SELECT 
    DATE(created_at) as activity_date,
    CASE 
        WHEN corporate_name IS NOT NULL THEN 'corporate'
        ELSE 'individual'
    END as tenant_type,
    COUNT(DISTINCT id) as application_count
FROM staging.tenants
WHERE status = 4
  AND created_at >= '2026-02-01'
  AND created_at <= '2026-02-05'
GROUP BY DATE(created_at), tenant_type
ORDER BY activity_date DESC;
```

### Check Inquiries Count
```sql
SELECT 
    inquiry_date,
    COUNT(*) as inquiry_count
FROM staging.inquiries
WHERE inquiry_date >= '2023-01-01'
GROUP BY inquiry_date
ORDER BY inquiry_date DESC
LIMIT 10;
-- Expected: Latest date should be 2023-05-02
```

### Verify Gold Table
```sql
SELECT * 
FROM gold.daily_activity_summary
WHERE activity_date >= '2026-02-01'
ORDER BY activity_date DESC, tenant_type;
```

---

## Recent Fixes (2026-02-05)

### Issue 1: `inquiries_count` all 0
**Status**: ⚠️ **NOT A BUG** - Historical data limitation
**Root Cause**: The `staging.inquiries` table only contains historical data up to 2023-05-02. No new inquiries are being recorded.
**Action**: Documented limitation in model comments and this file.

### Issue 2: `applications_count` showing abnormally high cumulative values
**Status**: ✅ **FIXED**
**Root Cause**: 
1. Original CTE was sourcing from `int_contracts` instead of `staging.tenants`
2. Was counting all `created_at` records, not filtering by status=4 (Tentative Reservation)
3. Used incorrect column `corporation_id` instead of `corporate_name`
4. S3 path mismatch: local sync was uploading to wrong path, Glue job wasn't picking up changes

**Fix**:
1. Changed source to `staging.tenants` with `status = 4` filter
2. Added `COUNT(DISTINCT t.id)` to avoid duplicates
3. Corrected column name to `corporate_name`
4. Uploaded corrected file to proper S3 path: `s3://jram-gghouse/dbt-project/models/gold/daily_activity_summary.sql`
5. Dropped and rebuilt table with Glue job

**Result**: `applications_count` now shows correct daily counts (0-1 per day) instead of cumulative 54742

---

## Maintenance Notes

### When to Update
- If new inquiry tracking is implemented, update `staging.inquiries` ETL and remove historical data warning
- If tenant status codes change, update status=4 filter in applications CTE
- If contract validation rules change, update `is_valid_contract` and `is_completed_moveout` logic in `int_contracts`

### Testing
- Always test with recent dates (last 7 days) to catch stale data issues
- Verify individual vs corporate split is working correctly
- Cross-check counts with source tables using verification queries above
