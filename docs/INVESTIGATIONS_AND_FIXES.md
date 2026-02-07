# Investigations & Fixes

**Project**: TokyoBeta Data Consolidation  
**Period**: February 5-7, 2026  
**Status**: ✅ All Critical Issues Resolved

---

## Issue 1: Split-Brain Database (Feb 7)

### Problem
ETL jobs reported SUCCESS but users saw stale data (Feb 5) instead of current data (Feb 7).

### Root Cause
Two Aurora clusters existed:
- **Private cluster**: ETL wrote here ✅ (current data)
- **Public cluster**: Users queried here ❌ (stale data)

During earlier troubleshooting, a new cluster was accidentally created instead of modifying the existing one.

### Impact
- Users saw 2-day-old data
- QuickSight dashboards were stale
- Business decisions based on incorrect data

### Solution
1. **Data Migration** (19 minutes)
   - Created `migrate_private_to_public.py` Glue job
   - Migrated 4 schemas: staging, silver, gold, seeds
   - Total rows migrated: ~2.5 million
   
2. **Configuration Update**
   - Updated all Glue jobs to use public cluster endpoint
   - Changed from: `tokyobeta-prod-aurora-cluster.cluster-*`
   - To: `tokyobeta-prod-aurora-cluster-public.cluster-*`

3. **Verification**
   - Confirmed all staging tables show Feb 7 data ✅
   - Verified gold tables updated to Feb 7 06:41 ✅
   - Tested end-to-end ETL pipeline ✅

### Prevention
- Add CloudWatch alarm for stale data detection
- Monitor data freshness (alert if > 48 hours old)
- Document cluster endpoints in Terraform

---

## Issue 2: Hardcoded Status Mappings (Feb 7)

### Problem
59% of tenant records showed status as "Unknown (17)", "Unknown (9)", etc.

### Root Cause
The `tenant_status_transitions` dbt model used hardcoded CASE statements mapping only status codes 1-8, but actual data contains codes 0-17.

```sql
-- Old hardcoded approach
CASE status
    WHEN 1 THEN 'Inquiry'
    WHEN 2 THEN 'Preview Scheduled'
    ...
    WHEN 8 THEN 'Cancelled'
    ELSE CONCAT('Unknown (', status, ')')
END
```

### Impact
- 28,366 "Moved Out" tenants (code 17) showed as "Unknown (17)"
- 9,955 "In Residence" tenants (code 9) showed as "Unknown (9)"
- Analytics dashboards showed incorrect status distribution
- Status transition analysis was meaningless

### Solution
Updated to use seed table joins:
```sql
-- New dynamic mapping
LEFT JOIN {{ ref('code_tenant_status') }} ts ON d.status = ts.code
...
COALESCE(ts.label_en, CONCAT('Unknown (', d.status, ')')) AS status_label
```

### Benefits
- All 18 status codes now properly labeled
- Uses authoritative `seeds/code_tenant_status.csv` mapping
- Easier to maintain (update CSV, not SQL)
- Consistent with data warehouse best practices

### Before/After
```
Before Fix:
  Unknown (17): 28,366 (59%)
  Unknown (9): 9,955 (21%)
  Cancelled: 5,029 (10%)

After Fix:
  Moved Out: 28,366 (59%)
  In Residence: 9,955 (21%)
  Cancelled: 5,029 (10%)
```

---

## Issue 3: Empty Lookup Tables (Feb 6)

### Problem
Silver transformer failed with error:
```
Database Error in model stg_tenants
Table 'staging.m_nationalities' doesn't exist
```

### Root Cause
- Staging loader dropped empty tables as cleanup optimization
- `m_nationalities` table exists in source but has 0 rows
- dbt model `stg_tenants` performs LEFT JOIN on this table
- Cleanup deleted a referenced lookup table

### Solution
Added `PRESERVE_EMPTY_TABLES` list in `staging_loader.py`:
```python
PRESERVE_EMPTY_TABLES = [
    'm_nationalities',
    'm_owners',
]

if row_count == 0:
    if table_name not in PRESERVE_EMPTY_TABLES:
        cursor.execute(f"DROP TABLE IF EXISTS staging.{table_name}")
    else:
        print(f"Preserved empty table: {table_name}")
```

### Prevention
- Document all lookup table dependencies
- Add dbt tests to verify required tables exist
- Consider populating empty lookup tables with default values

---

## Issue 4: Daily Activity Summary Metrics (Feb 5-6)

### Problem
Daily activity summary showed inconsistent aggregation logic and missing contract type splits.

### Investigation
- Analyzed `daily_activity_summary` gold table
- Found mixing of individual and corporate contracts
- Missing breakdown by contract type
- No clear distinction between new contracts and renewals

### Solution
1. Updated `daily_activity_summary.sql` to:
   - Split by `contract_type` (individual vs corporate)
   - Add renewal flag tracking
   - Separate inquiry/preview/application counts
   
2. Added data quality tests:
   - No negative counts
   - Date consistency checks
   - Contract type validation

### Verification
```sql
SELECT 
    activity_date,
    contract_type,
    SUM(new_contract_count) as total_contracts
FROM gold.daily_activity_summary
WHERE activity_date >= '2026-01-01'
GROUP BY activity_date, contract_type
ORDER BY activity_date DESC;
```

---

## Issue 5: Lesotho Flag Investigation (Feb 7)

### Problem
Nationality enrichment showed unexpected number of Lesotho (LS) nationals.

### Investigation
- Examined tenant records with nationality_id mapping
- Checked LLM enrichment results
- Analyzed nationality distribution

### Findings
See detailed report: `docs/LESOTHO_FLAG_INVESTIGATION.md`

**Summary**:
- 173 tenants flagged with Lesotho nationality
- Root cause: Incorrect nationality_id mapping in source data
- LLM enrichment correctly flagged data quality issue

### Solution
1. Add nationality validation tests
2. Flag suspicious nationality distributions
3. Implement confidence scoring for LLM enrichments
4. Manual review process for outliers

---

## Cluster Consolidation (Feb 7)

### Current State
Two Aurora clusters in production:

| Cluster | Status | Cost | Action |
|---------|--------|------|--------|
| Private | ❌ Deprecated | ~$200/month | Delete after 30 days |
| Public | ✅ Active | ~$200/month | Keep as primary |

### Timeline
- **Feb 7**: Migration complete, all jobs using public cluster
- **Mar 7**: Delete private cluster (30-day safety window)
- **Cost savings**: $200/month after deletion

### Verification Checklist
- [x] All Glue jobs point to public cluster
- [x] Data migration complete (2.5M rows)
- [x] End-to-end ETL tested and working
- [x] QuickSight connected to public cluster
- [ ] 30 days stability confirmed
- [ ] Private cluster deleted

---

## Data Quality Improvements

### Implemented
1. **Seed Table Mappings**
   - Status codes
   - Contract types
   - Nationality codes
   - Prefecture codes

2. **dbt Tests**
   - NULL checks on required fields
   - Referential integrity
   - Date range validation
   - Status code validation

3. **Automated Validation**
   - Empty table detection
   - Backup verification
   - Row count anomaly detection

### Planned
1. **Advanced Tests**
   - Cross-table consistency checks
   - Statistical anomaly detection
   - Time-series validation

2. **Monitoring**
   - Data freshness dashboard
   - Quality score tracking
   - Automated alerting

---

## Lessons Learned

### Infrastructure
1. **Always verify database targets** - Check which cluster/endpoint is being used
2. **Terraform plan carefully** - Unintended resource creation is easy
3. **Document network topology** - Public vs private accessibility matters

### Data Quality
1. **Seed tables > hardcoded logic** - More maintainable, authoritative source
2. **Empty tables are valid** - Preserve referenced lookup tables
3. **Test assumptions** - 59% "Unknown" status should have been caught earlier

### Process
1. **End-to-end testing critical** - Success status ≠ correct behavior
2. **Monitor data, not just jobs** - Job success but stale data is still failure
3. **TDD prevents issues** - Tests would have caught hardcoded mapping issue

### Communication
1. **Document changes immediately** - Don't wait until issues arise
2. **Architecture diagrams help** - Visual representation speeds debugging
3. **Runbooks save time** - Standard procedures for common issues

---

## Impact Summary

### Before Fixes
- ❌ Users saw 2-day-old data
- ❌ 59% of tenant statuses incorrect
- ❌ ETL wrote to wrong cluster
- ❌ Hardcoded mappings created technical debt

### After Fixes
- ✅ Users see current data (< 24 hours old)
- ✅ All tenant statuses properly labeled
- ✅ ETL writes to correct cluster
- ✅ Seed tables provide authoritative mappings
- ✅ Automated cleanup and validation

---

## Technical Debt Remaining

### High Priority
1. **Delete private cluster** (Mar 7, 2026)
2. **Remove migration script** after cluster deletion
3. **Add data freshness alerting**

### Medium Priority
1. **Enhance dbt tests** - Add more data quality checks
2. **Implement CI/CD** for dbt models
3. **Create data quality dashboard**

### Low Priority
1. **Optimize backup retention** - Consider longer retention for critical tables
2. **Add performance monitoring** - Track ETL execution patterns
3. **Document all edge cases** - Known data quality issues

---

**Status**: ✅ All critical issues resolved  
**Risk Level**: Low  
**Next Review**: February 14, 2026
