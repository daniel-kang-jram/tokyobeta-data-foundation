# CRITICAL ISSUE: Inquiry Count Logic is Fundamentally Flawed

**Date:** 2026-02-09  
**Severity:** 🔴 **CRITICAL** - Core metric is incorrect  
**Status:** Requires immediate review and redesign

## Executive Summary

The `inquiries_count` metric in `gold.daily_activity_summary` **does not accurately capture new inquiries**. Investigation reveals that tenants are **NOT registered in the system at inquiry stage**, but rather when they reach 初期賃料 (status 5) or later.

## Current Logic (INCORRECT)

```sql
inquiries AS (
    SELECT
        DATE(t.created_at) as activity_date,
        CASE
            WHEN t.contract_type IN (2, 3) THEN 'corporate'
            WHEN t.contract_type IN (1, 6, 7, 9) THEN 'individual'
            ELSE 'unknown'
        END as tenant_type,
        COUNT(DISTINCT t.id) as inquiry_count
    FROM {{ source('staging', 'tenants') }} t
    WHERE t.created_at IS NOT NULL
      AND t.created_at >= '{{ var('min_valid_date') }}'
    GROUP BY DATE(t.created_at), tenant_type
),
```

**Assumption:** New tenant records = new inquiries  
**Reality:** This assumption is FALSE

## Investigation Findings

### 1. Status Distribution Across ALL Tenants (48,004 total)

| Status | Label | Count | % of Total | Latest Record |
|--------|-------|-------|------------|---------------|
| 1 | お問い合わせ (Inquiry) | 6 | 0.01% | 2025-12-10 |
| 2 | 内見予約 (Viewing Scheduled) | 6 | 0.01% | 2026-01-28 |
| 3 | 内見済み (Viewing Complete) | 26 | 0.05% | 2026-01-24 |
| 4 | 仮予約 (Provisional) | 30 | 0.06% | 2026-02-02 |
| 5 | 初期賃料 (Initial Rent) | 236 | 0.49% | 2026-02-06 |
| **Total early stages** | **(1-5)** | **304** | **0.63%** | - |

**99.37% of all tenant records are at status 6+ (post-application)**

### 2. Recent Tenant Registrations (Last 7 Days)

| Date | New Tenants | Status 1-3 (Inquiry) | Status 4-5 (Application) | Status 6+ (Post-App) |
|------|-------------|----------------------|--------------------------|----------------------|
| 2026-02-06 | 10 | 0 | 9 (90%) | 1 (10%) |
| 2026-02-05 | 9 | 0 | 8 (89%) | 1 (11%) |
| 2026-02-02 | 17 | 0 | 16 (94%) | 1 (6%) |

**0 new inquiries (status 1-3) in the last 7 days**  
**All new registrations are at 初期賃料 (status 5) or higher**

### 3. Property Linkage Issue (Secondary Finding)

**Data Synchronization Lag:**
- `staging.tenants`: Last updated 2026-02-06 23:58 ✅ Current
- `staging.movings`: Last updated 2026-02-02 19:49 ⚠️ 4 days stale

**Impact:**
- 19 tenants registered on Feb 5-6 have `moving_id` values (92409-92486)
- But `staging.movings` only has IDs up to 92148
- 100% of Feb 5-6 registrations have no property linkage (data lag)

## Root Cause Analysis

### Why Tenants Are Not Registered at Inquiry Stage

**Hypothesis 1: Workflow Design**
The source system (likely a CRM/property management system) only creates full tenant records once a prospect reaches 初期賃料 stage. Early-stage inquiries may be tracked in a separate inquiry/lead management table not included in the dump.

**Hypothesis 2: Data Export Scope**
The SQL dump may only export tenants who have progressed past initial inquiry stages, filtering out early-stage prospects.

**Hypothesis 3: Manual Entry Workflow**
Staff may only create tenant records after initial rent payment is confirmed, consolidating inquiry → viewing → application into a single registration event.

## Impact on Metrics

### ❌ Affected Metrics
1. **`inquiries_count`**: Currently counts new tenant registrations, which are NOT inquiries
   - **Severe under-count**: Only capturing 0.08% of actual inquiries
   - **Wrong timing**: Registrations happen at 初期賃料 stage, not inquiry stage

### ✅ Unaffected Metrics (Still Correct)
1. **`applications_count`**: Uses `tenant_status_history` transitions to status 4/5 ✅
2. **`confirmed_moveins_count`**: Uses `tenant_status_history` point-in-time logic ✅
3. **`confirmed_moveouts_count`**: Uses `tenant_status_history` point-in-time logic ✅

## Recommended Solutions

### Option 1: Find True Inquiry Source Table (BEST)
🔍 **Action:** Investigate source system schema for inquiry/lead tracking tables
- Look for tables like: `inquiries`, `leads`, `prospects`, `previews`
- Check if `staging.inquiries` table exists (referenced in foreign key `inquiry_id` in tenants table)
- Request additional tables in daily dump

**SQL to check:**
```sql
-- Check if inquiries table exists
SHOW TABLES LIKE '%inquir%';
SHOW TABLES LIKE '%lead%';
SHOW TABLES LIKE '%prospect%';

-- Check inquiry_id usage
SELECT 
    COUNT(*) as total,
    COUNT(inquiry_id) as has_inquiry_id,
    COUNT(DISTINCT inquiry_id) as unique_inquiries
FROM staging.tenants;
```

### Option 2: Use Status History Transitions (FALLBACK)
If no inquiry source table exists, use first appearance in `tenant_status_history`:

```sql
inquiries AS (
    SELECT
        h.valid_from as activity_date,
        CASE
            WHEN h.contract_type IN (2, 3) THEN 'corporate'
            WHEN h.contract_type IN (1, 6, 7, 9) THEN 'individual'
            ELSE 'unknown'
        END as tenant_type,
        COUNT(DISTINCT h.tenant_id) as inquiry_count
    FROM (
        SELECT 
            tenant_id,
            contract_type,
            MIN(valid_from) as valid_from
        FROM {{ ref('tenant_status_history') }}
        GROUP BY tenant_id, contract_type
    ) h
    WHERE h.valid_from >= '{{ var('min_valid_date') }}'
    GROUP BY h.valid_from, tenant_type
),
```

**Limitation:** This counts "first appearance in system," which still occurs at 初期賃料 stage, not true inquiry.

### Option 3: Redefine Metric (LAST RESORT)
Change the metric definition to match what the data actually represents:
- Rename: `inquiries_count` → `new_registrations_count`
- Update description: "Number of new tenant records created (typically at 初期賃料 stage or later)"

## Verification Queries

### Check for Inquiry Table
```sql
-- Check if inquiry_id is populated
SELECT 
    COUNT(*) as total_tenants,
    COUNT(inquiry_id) as has_inquiry_id,
    ROUND(100.0 * COUNT(inquiry_id) / COUNT(*), 2) as inquiry_id_pct
FROM staging.tenants;

-- Check preview_id (viewing) usage
SELECT 
    COUNT(*) as total_tenants,
    COUNT(preview_id) as has_preview_id,
    ROUND(100.0 * COUNT(preview_id) / COUNT(*), 2) as preview_id_pct
FROM staging.tenants;
```

### Analyze Status Progression Timing
```sql
-- Check typical status at registration
SELECT 
    t.status,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM staging.tenants WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)), 2) as pct
FROM staging.tenants t
WHERE t.created_at >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)
GROUP BY t.status
ORDER BY count DESC;
```

## Action Items

### Immediate (Today)
- [ ] Run verification queries to check for `inquiries` / `previews` / `leads` tables
- [ ] Check `inquiry_id` and `preview_id` column population rates
- [ ] Contact source system admin/vendor for schema documentation

### Short-term (This Week)
- [ ] If inquiry table found: Add to daily dump and update dbt model
- [ ] If no inquiry table: Discuss with stakeholders whether to redefine metric
- [ ] Update `daily_activity_summary.sql` with corrected logic
- [ ] Update `_gold_schema.yml` with accurate metric descriptions

### Long-term
- [ ] Address 4-day data lag in `staging.movings` table
- [ ] Implement referential integrity checks for `moving_id` foreign keys
- [ ] Add data quality tests for staging table freshness

## Related Issues

1. **Movings Table Staleness**: `staging.movings` is 4 days behind `staging.tenants`
   - Last movings record: 2026-02-02 17:54
   - Last tenant record: 2026-02-06 19:21
   - **Impact**: 19 recent tenants (Feb 5-6) have no property linkage
   
2. **Missing Foreign Key Constraints**: `tenants.moving_id` can reference non-existent IDs
   - 21 tenants at 初期賃料 have `moving_id` pointing to deleted/non-existent records
   - See: `docs/APPLICATION_TENANTS_PROPERTY_LINKAGE.md`

## Conclusion

The current `inquiries_count` metric is **not measuring what it claims to measure**. The source data does not contain inquiry-stage records; tenants are only registered once they reach 初期賃料 or later stages.

**Next step:** Verify if a separate inquiry tracking table exists in the source system that can provide true inquiry counts.

---

**Discovered by:** Data quality investigation on 2026-02-09  
**Related to:** `gold.daily_activity_summary` logic fixes (applications, move-ins, move-outs)
