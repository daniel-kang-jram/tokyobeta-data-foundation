# Tenant Status History - Deployment Checklist

**Date:** 2026-02-05  
**Status:** Ready to Deploy  
**Deployment Target:** Next ETL run (2026-02-06 07:00 JST)

## Summary

Added **2 new tables** to track tenant status changes historically:
1. **Silver:** `tenant_status_history` - SCD Type 2 historical tracking
2. **Gold:** `tenant_status_transitions` - Analysis-ready with business labels

## Files Created/Modified

### New Files ✅
- `dbt/models/silver/tenant_status_history.sql` - Core history table
- `dbt/models/gold/tenant_status_transitions.sql` - Analysis view
- `dbt/macros/scd_type2_close_records.sql` - SCD helper macro
- `docs/TENANT_STATUS_HISTORY_IMPLEMENTATION.md` - Full documentation

### Modified Files ✅
- `dbt/models/silver/_silver_schema.yml` - Added documentation
- `dbt/models/gold/_gold_schema.yml` - Added documentation

## Pre-Deployment Checklist

- [x] Models created with proper config
- [x] Schema documentation added
- [x] Implementation guide written
- [x] Example queries documented
- [ ] Upload to S3 (pending)
- [ ] Verify first ETL run (pending)

## Deployment Steps

### Step 1: Upload to S3

```bash
# Navigate to project root
cd /Users/danielkang/tokyobeta-data-consolidation

# Sync dbt project to S3
aws s3 sync dbt/ s3://jram-gghouse/dbt-project/ \
    --exclude ".user.yml" \
    --exclude "target/*" \
    --exclude "dbt_packages/*" \
    --exclude "logs/*" \
    --profile gghouse --region ap-northeast-1

# Verify upload
aws s3 ls s3://jram-gghouse/dbt-project/models/silver/tenant_status_history.sql \
    --profile gghouse --region ap-northeast-1

aws s3 ls s3://jram-gghouse/dbt-project/models/gold/tenant_status_transitions.sql \
    --profile gghouse --region ap-northeast-1
```

### Step 2: Monitor ETL Run

**Next Run:** 2026-02-06 07:00 JST (automatic)

**Watch CloudWatch Logs:**
```bash
# Start watching logs at 7:00 AM JST
aws logs tail /aws-glue/jobs/output \
    --follow --profile gghouse --region ap-northeast-1 \
    | grep -E "tenant_status|Building|Completed"
```

**Expected Log Output:**
```
Building model silver.tenant_status_history
Completed model silver.tenant_status_history (full refresh)
Building model gold.tenant_status_transitions
Completed model gold.tenant_status_transitions
```

### Step 3: Verify Data

```sql
-- 1. Check silver table created
SELECT COUNT(*) as total_records,
       SUM(CASE WHEN is_current THEN 1 ELSE 0 END) as current_records
FROM silver.tenant_status_history;
-- Expected: ~50,000 total, ~50,000 current (Day 1)

-- 2. Check gold table created
SELECT COUNT(*) as total_records
FROM gold.tenant_status_transitions;
-- Expected: ~50,000 records

-- 3. Verify status distribution
SELECT status_label, COUNT(*) as count
FROM gold.tenant_status_transitions
WHERE is_current = TRUE
GROUP BY status_label
ORDER BY count DESC;
-- Should show realistic distribution

-- 4. Check no duplicates
SELECT tenant_id, COUNT(*) as current_count
FROM silver.tenant_status_history
WHERE is_current = TRUE
GROUP BY tenant_id
HAVING COUNT(*) > 1;
-- Expected: 0 rows
```

### Step 4: Test Incremental Updates (Day 2)

**After 2026-02-07 ETL run:**

```sql
-- 1. Check for status changes
SELECT 
    DATE(dbt_updated_at) as date,
    COUNT(*) as new_records
FROM silver.tenant_status_history
GROUP BY DATE(dbt_updated_at)
ORDER BY date DESC
LIMIT 7;
-- Should show records added on 2/7

-- 2. Verify transitions tracked
SELECT 
    status_transition,
    COUNT(*) as count
FROM gold.tenant_status_transitions
WHERE status_changed = TRUE
AND effective_date = CURDATE()
GROUP BY status_transition;
-- Should show any status changes from today

-- 3. Verify old records closed
SELECT COUNT(*) 
FROM silver.tenant_status_history
WHERE is_current = FALSE 
AND valid_to IS NOT NULL
AND valid_to = DATE_SUB(CURDATE(), INTERVAL 1 DAY);
-- Should show records that were closed out
```

## Rollback Plan

If issues occur, rollback is simple:

### Option 1: Remove from dbt Project
```bash
# Delete the new models
rm dbt/models/silver/tenant_status_history.sql
rm dbt/models/gold/tenant_status_transitions.sql
rm dbt/macros/scd_type2_close_records.sql

# Upload to S3
aws s3 sync dbt/ s3://jram-gghouse/dbt-project/ --delete \
    --profile gghouse --region ap-northeast-1
```

### Option 2: Drop Tables in Database
```sql
DROP TABLE IF EXISTS gold.tenant_status_transitions;
DROP TABLE IF EXISTS silver.tenant_status_history;
```

## Expected Impact

### Storage
- **Day 1:** ~50,000 records (10-15 MB)
- **Monthly:** +3,000-15,000 records (~0.5-2 MB)
- **Annual:** +36,000-180,000 records (~6-30 MB)
- **Conclusion:** Minimal storage impact

### ETL Performance
- **Initial load:** +30-60 seconds (full refresh)
- **Daily incremental:** +5-10 seconds
- **Conclusion:** Negligible performance impact

### Query Performance
- **Current status queries:** Fast (is_current index)
- **Historical queries:** Fast (tenant_id, valid_from index)
- **Transition analysis:** Moderate (gold table pre-computed)

## Success Metrics

### Day 1 (Initial Load)
- [  ] ETL completes successfully
- [ ] ~50,000 records in silver.tenant_status_history
- [ ] All records have is_current = TRUE
- [ ] ~50,000 records in gold.tenant_status_transitions
- [ ] Status distribution looks realistic
- [ ] No duplicate current records per tenant

### Day 2 (First Incremental)
- [ ] New records added for status changes
- [ ] Old records properly closed (valid_to set)
- [ ] Only changed tenants have new records
- [ ] Gold table shows transitions correctly
- [ ] ETL runtime increase <10 seconds

### Week 1 (Steady State)
- [ ] Daily incremental updates working smoothly
- [ ] Status transition patterns make sense
- [ ] No data quality issues
- [ ] Ready for dashboard integration

## Quick Start Queries

Once deployed, try these queries:

```sql
-- Current tenant status distribution
SELECT status_label, contract_type_label, COUNT(*) 
FROM gold.tenant_status_transitions 
WHERE is_current = TRUE 
GROUP BY status_label, contract_type_label 
ORDER BY COUNT(*) DESC;

-- Recent status changes
SELECT tenant_id, full_name, status_transition, effective_date
FROM gold.tenant_status_transitions
WHERE status_changed = TRUE 
AND effective_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
ORDER BY effective_date DESC
LIMIT 20;

-- Payment issues this month
SELECT tenant_id, full_name, payment_status_change, effective_date
FROM gold.tenant_status_transitions
WHERE payment_status_changed = TRUE
AND effective_date >= DATE_FORMAT(CURDATE(), '%Y-%m-01')
ORDER BY effective_date DESC;
```

## Monitoring Schedule

### Daily (First Week)
- Check ETL logs for errors
- Verify incremental updates working
- Check for duplicate current records
- Monitor ETL runtime

### Weekly (After Stabilization)
- Review status transition patterns
- Validate data quality
- Check storage growth
- Monitor query performance

### Monthly
- Analyze usage patterns
- Plan dashboard integrations
- Review performance metrics
- Document insights

## Documentation

- **Full Implementation Guide:** `docs/TENANT_STATUS_HISTORY_IMPLEMENTATION.md`
- **dbt Models:** `dbt/models/silver/tenant_status_history.sql`, `dbt/models/gold/tenant_status_transitions.sql`
- **Schema Docs:** `dbt/models/silver/_silver_schema.yml`, `dbt/models/gold/_gold_schema.yml`

## Next Steps

1. ✅ Code complete
2. ✅ Documentation complete
3. ⏳ **Deploy to S3** (run Step 1 above)
4. ⏳ **Monitor first ETL run** (2026-02-06 07:00 JST)
5. ⏳ **Verify data** (run Step 3 queries)
6. ⏳ **Test incremental** (check Day 2)
7. ⏳ **Enable for dashboards** (QuickSight integration)

## Support

**Questions?** See full documentation in `docs/TENANT_STATUS_HISTORY_IMPLEMENTATION.md`

**Issues?** Check troubleshooting section in implementation guide

---

**Ready to Deploy:** Yes ✅  
**Risk Level:** Low (new tables, no impact on existing models)  
**Estimated Time:** 5 minutes to deploy, 1 day to verify
