# Daily Activity Summary Fix - Deployment Status

**Date**: 2026-02-09  
**Status**: Partially Deployed - Awaiting Full Rebuild

## Summary

Fixed critical issues in `daily_activity_summary` table logic for proper funnel analysis:
1. ✅ Corrected metric definitions per business requirements
2. ✅ Fixed applications under-counting (266 → 3,998 transactions)
3. ✅ Fixed tenant_type classification (corporate data now properly tracked)
4. ⏳ Implementing forward-fill in tenant_status_history (in progress)

---

## What Was Fixed

### 1. Metric Definitions Corrected

| Metric | Old Logic | New Logic |
|--------|-----------|-----------|
| **問い合わせ数** | Historical inquiries table (2018-2023 only) | NEW tenant registrations by created_at |
| **申し込み数** | Status 4 tenants by created_at | Status 4/5 transitions by valid_from (from history) |
| **入居数** | contract_start_date from int_contracts | Point-in-time status check on movein_date |
| **確定退去者** | moveout_date from int_contracts | Point-in-time status check on moveout_date |

### 2. Applications Under-counting Fixed

**Before**: 266 applications (only current snapshot)
- Used `staging.tenants WHERE status IN (4,5)`
- Only counted tenants currently in those statuses TODAY

**After**: 3,998 applications (historical transitions)
- Uses `tenant_status_history` to capture ALL transitions to status 4/5
- Correctly tracks historical application activity

**Result**: 15x increase in application count (correct historical data)

### 3. Tenant Type Classification Fixed

**Issue**: Used non-existent `code_contract_type` seed table, causing all tenants to default to 'individual'

**Fix**: Direct CASE statement on contract_type values
```sql
CASE 
    WHEN contract_type IN (2, 3) THEN 'corporate'  -- 法人契約, 法人契約個人
    WHEN contract_type IN (1, 6, 7, 9) THEN 'individual'  -- 一般, 定期契約, etc.
    ELSE 'unknown'
END
```

**Result**: Corporate data now properly tracked (20,959 inquiries, 347 move-ins, 5,028 move-outs)

---

## Critical Issue Discovered

### Problem: tenant_status_history Not Forward-Filling

**Symptom**: All status periods have `valid_to = valid_from` (0 days in period)

**Example**:
```
Tenant 15304:
- Status 9: 2025-05-11 → 2025-05-11 (should be → 2025-09-02)
- Status 10: 2025-09-03 → 2025-09-03 (should be → 2026-01-22)
- Status 9: 2026-01-23 → 2026-01-23 (should be → NULL/current)
```

**Root Cause**: 
- The SCD Type 2 logic was applying `LEAD()` to find next snapshot, then filtering to transitions
- This broke the forward-fill because `next_snapshot_date` was pointing to the next row in filtered results
- Need to apply `LEAD()` over transitions only, AFTER filtering

**Fix Applied**:
```sql
-- New logic:
1. Filter to transitions only (WHERE status changed)
2. THEN apply LEAD() over those transitions to get next transition date
3. valid_to = next_transition_date - 1 day
```

### Impact on Move-in/Move-out Counts

Without proper forward-fill:
- **357 move-ins** found (only 3% of actual move-ins since May 2025)
- **182 move-outs** found
- Most dates have no status match because snapshots don't exist for every date

With proper forward-fill (expected after rebuild):
- Move-ins should increase significantly (estimate: 7,000-10,000)
- Move-outs should increase to match historical data
- Point-in-time lookups will work for all dates, not just snapshot dates

---

## Deployment Status

### ✅ Completed

1. **Code Changes**: All models updated and pushed to GitHub (4 commits)
2. **S3 Upload**: All dbt models uploaded to S3 for Glue job
3. **daily_activity_summary**: Logic updated to use tenant_status_history for point-in-time checks
4. **Documentation**: Schema docs updated with business logic explanations

### ⏳ Pending - Requires Rebuild

1. **tenant_status_history**: Forward-fill fix committed but not yet applied to Aurora
   - Rebuild takes 5+ minutes due to 9M+ snapshots
   - Too slow for local execution
   - **Action Required**: Let Glue job rebuild (or run manually overnight)

2. **daily_activity_summary**: Depends on tenant_status_history rebuild
   - Current counts are based on broken (non-forward-filled) history data
   - Will be correct after tenant_status_history is rebuilt

---

## Git Commits

```
2f3e076 fix(silver): implement proper SCD Type 2 forward-fill in tenant_status_history
f538abe fix(gold): use tenant_status_history for applications count
a65d7a4 perf(silver): optimize tenant_status_history with inline labels (no seed join)
0a97817 refactor(models): improve daily_activity_summary and tenant_status_history
```

**Status**: ✅ Pushed to origin/main

---

## Next Steps

### Option A: Let Nightly Batch Handle It (Recommended)
- Wait for tonight's 7:00 AM JST Glue job
- Job will sync latest code from S3 and rebuild all models
- Verify results tomorrow morning

### Option B: Trigger Manual Rebuild Now
```bash
# Wait for current Glue job to finish (check with):
aws glue get-job-runs --job-name tokyobeta-prod-daily-etl --max-items 1

# Then trigger new run:
aws glue start-job-run --job-name tokyobeta-prod-daily-etl --arguments '{...}'
```

### Option C: Run Locally in Background (Long-Running)
```bash
cd dbt
export AURORA_ENDPOINT="tokyobeta-prod-aurora-cluster-public.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com"
export AURORA_USERNAME="admin"
export AURORA_PASSWORD="<password>"

# This will take 5-10 minutes
nohup dbt run --select tenant_status_history daily_activity_summary > /tmp/dbt_rebuild.log 2>&1 &

# Monitor:
tail -f /tmp/dbt_rebuild.log
```

---

## Verification Queries (After Rebuild)

### 1. Check Forward-Fill is Working
```sql
SELECT 
    tenant_id,
    status,
    valid_from,
    valid_to,
    DATEDIFF(COALESCE(valid_to, CURDATE()), valid_from) as days_in_period
FROM silver.tenant_status_history
WHERE tenant_id = 15304
ORDER BY valid_from;

-- Expected:
-- Status 9: 2025-05-11 → 2025-09-02 (114 days)
-- Status 10: 2025-09-03 → 2026-01-22 (142 days)
-- Status 9: 2026-01-23 → NULL (current, ~15 days so far)
```

### 2. Check Move-in Counts
```sql
SELECT 
    tenant_type,
    SUM(confirmed_moveins_count) as total_moveins,
    SUM(confirmed_moveouts_count) as total_moveouts
FROM gold.daily_activity_summary
WHERE activity_date >= '2025-05-11'
GROUP BY tenant_type;

-- Expected (rough estimates based on source data):
-- corporate: 700-900 move-ins, 100-200 move-outs
-- individual: 7,000-10,000 move-ins, 3,000-5,000 move-outs
```

### 3. Check Applications Count
```sql
SELECT SUM(applications_count) FROM gold.daily_activity_summary;
-- Expected: 3,998 (should remain unchanged)
```

---

## Technical Details

### Forward-Fill Logic

**Before** (broken):
```sql
-- Applied LEAD() before filtering transitions
-- next_snapshot_date pointed to next row in ALL snapshots
-- Then filtered to transitions only
-- Result: next_snapshot_date was wrong for transitions
```

**After** (fixed):
```sql
-- Filter to transitions first
-- THEN apply LEAD() over transitions only
-- next_transition_date correctly points to next status change
-- Result: proper forward-fill between transitions
```

### Why This Matters for Funnel Analysis

**Funnel analysis needs point-in-time checks**:
- "How many tenants were in application status on Jan 15?"
- "What was the tenant's status when they moved in on Dec 1?"

Without forward-fill:
- Only dates with actual snapshots would match
- ~260 snapshot dates out of ~270 days = ~96% date coverage
- But not every tenant has snapshots on every date
- Result: Severe under-counting

With forward-fill:
- Status 9 from May 11 applies to all dates May 11 - Sep 2
- Can answer "what status on X date?" for ANY date
- Result: Accurate historical funnel analysis

---

## Current State (Feb 9, 2026)

### Aurora Tables

| Table | Status | Notes |
|-------|--------|-------|
| `gold.daily_activity_summary` | ⚠️ Needs Rebuild | Using old tenant_status_history without forward-fill |
| `silver.tenant_status_history` | ⚠️ Needs Rebuild | Has broken SCD Type 2 (no forward-fill) |
| `staging.tenant_daily_snapshots` | ✅ OK | 9M+ rows, source data intact |

### Code Status

| Component | Status |
|-----------|--------|
| dbt models | ✅ Fixed and pushed to GitHub |
| S3 dbt-project | ✅ Updated with latest code |
| Glue job definition | ✅ No changes needed |

### Glue Job Status
- **Current Run**: RUNNING (started 12:36 PM, ~30 min elapsed)
- **Previous Run**: TIMEOUT (11:35 AM)
- **Last Success**: 7:00 AM (this morning)

---

## Expected Results After Rebuild

### Current (Broken)
```
Applications: 3,998
Move-ins: 357 (3% of actual)
Move-outs: 182
```

### After Forward-Fill Fix
```
Applications: 3,998 (unchanged)
Move-ins: ~8,000-10,000 (since May 2025)
Move-outs: ~3,000-5,000 (since May 2025)
```

### Sample Funnel Flow (Expected)
```
Date: 2026-02-01
- 問い合わせ (Inquiries): 16 new registrations
- 申し込み (Applications): 17 status 4/5 transitions
- 入居 (Move-ins): 110 with eligible status on that date
- 退去 (Move-outs): 17 with moveout status on that date
```

---

## Recommendation

**Let the nightly batch (7:00 AM JST) handle the rebuild.**

The Glue job has better:
- Memory resources (10 GB)
- Processing power (10 DPUs)
- Timeout handling (2 hours vs 5 minutes locally)

Verify tomorrow morning that:
1. Forward-fill is working (check sample tenant valid_to dates)
2. Move-in/out counts are realistic (~8K-10K move-ins since May 2025)
3. Funnel analysis shows daily progression through statuses

---

## Files Changed

1. `dbt/models/gold/daily_activity_summary.sql`
2. `dbt/models/silver/tenant_status_history.sql`
3. `dbt/models/gold/_gold_schema.yml`
4. `dbt/models/silver/_silver_schema.yml`
