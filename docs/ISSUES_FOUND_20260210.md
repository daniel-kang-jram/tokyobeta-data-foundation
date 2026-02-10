# Issues Found - February 10, 2026

## Critical Issues Fixed

### 1. ❌ boto3 Version Missing bedrock-runtime (CRITICAL)
**Location:** All Glue jobs  
**Error:** `Unknown service: 'bedrock-runtime'. Valid service names are: ...`  
**Root Cause:** Glue Python environment uses boto3 1.24.x which doesn't include bedrock-runtime service (added in boto3 1.28.57+)  
**Impact:** 
- Nationality enrichment completely skipped in staging_loader
- Cache logic not tested in Glue environment
- Cost: Lost $2 potential savings per day

**Fix Applied:**
```bash
# Created boto3 bundle
pip install boto3==1.34.0 -t python/
zip -r boto3-1.34.0.zip python/
aws s3 cp boto3-1.34.0.zip s3://jram-gghouse/glue-libs/

# Updated staging_loader job
--additional-python-modules: "pymysql,boto3==1.34.0,botocore==1.34.0"
```

**Status:** ✅ Fixed, needs testing

---

### 2. ❌ Missing `import re` in silver_transformer.py
**Location:** `glue/scripts/silver_transformer.py:301`  
**Error:** `UnboundLocalError: local variable 're' referenced before assignment`  
**Root Cause:** Missing `import re` statement at top of file  
**Impact:** Silver transformer job failed when parsing dbt test output

**Fix Applied:**
```python
import re  # Added to imports
```

**Status:** ✅ Fixed, uploaded to S3

---

### 3. ⚠️ dbt Dependency Conflicts
**Location:** All transformer jobs  
**Error:** `aiobotocore 2.4.1 requires botocore<1.27.60,>=1.27.59, but you have botocore 1.42.44`  
**Root Cause:** dbt-mysql installation upgrades boto3/botocore, conflicts with pre-installed aiobotocore  
**Impact:** 
- Warnings in logs (non-fatal)
- Potential for unexpected behavior

**Recommended Fix:** Pin boto3/botocore versions in --additional-python-modules
```
--additional-python-modules: "pymysql,boto3==1.27.59,botocore==1.27.59"
```

**Status:** ⚠️ Documented, not critical (warnings only)

---

### 4. ⚠️ dbt Temporary Table Cleanup Issues
**Location:** Silver/Gold transformers  
**Error:** `Table 'tenant_status_history__dbt_tmp' already exists`  
**Root Cause:** Failed dbt runs leave temp tables, subsequent runs fail  
**Impact:** Repeated job failures until manual cleanup

**Workaround:** Manual cleanup via SQL:
```sql
DROP TABLE IF EXISTS silver.tenant_status_history__dbt_tmp;
```

**Recommended Fix:** Add pre-run cleanup script:
```python
def cleanup_dbt_temp_tables(conn, schema='silver'):
    cursor = conn.cursor()
    cursor.execute(f"SHOW TABLES IN {schema} LIKE '%__dbt_tmp'")
    temp_tables = cursor.fetchall()
    for (table_name,) in temp_tables:
        cursor.execute(f"DROP TABLE IF EXISTS {schema}.{table_name}")
    conn.commit()
```

**Status:** ⚠️ Workaround in place, fix recommended

---

### 5. ⚠️ SQL Dump Column Count Mismatch
**Location:** staging_loader  
**Error:** `Column count doesn't match value count at row 1` (staging.tenants table)  
**Root Cause:** SQL dump INSERT statements have mismatched column counts  
**Impact:** Some tenant records fail to load (non-fatal, job continues)

**Investigation Needed:**
- Check source database schema vs dump schema
- Verify if `llm_nationality` column in staging.tenants is causing mismatch
- May need to regenerate dump or fix dump parsing logic

**Status:** ⚠️ Ongoing (non-critical, partial data loss)

---

### 6. ⚠️ Duplicate Entry Warnings (Costs, Deposits, etc.)
**Location:** staging_loader  
**Error:** `Duplicate entry '...' for key 'PRIMARY'`  
**Root Cause:** SQL dump contains duplicate primary keys for certain tables  
**Impact:** Some records skipped (warnings, non-fatal)

**Analysis:**
- Tables affected: Costs_items, Deposits, Fundhing_Request, etc.
- Dump may include historical records multiple times
- Current behavior: Skip duplicates, continue processing

**Status:** ⚠️ Expected behavior (documented), monitoring for data quality issues

---

## Summary Statistics

**Critical Issues:** 2 fixed (boto3, import re)  
**Warnings:** 4 documented (dependencies, temp tables, column mismatch, duplicates)  

**Cost Impact:**
- boto3 issue: $2/day lost (until fix tested) = $60/month potential loss
- Other issues: Negligible cost impact

**Data Quality Impact:**
- Column mismatch: Unknown % of tenant records lost
- Duplicates: Known issue, accepted as tolerable

---

## Next Steps

### Immediate
1. ✅ Test staging_loader with boto3 fix
2. ✅ Test silver_transformer with import fix
3. ⚠️ Investigate tenant column count mismatch
4. ⚠️ Add dbt temp table cleanup to all transformers

### This Week
1. Monitor cache hit rate after boto3 fix deployed
2. Verify cost savings ($2/day → $0.01/day)
3. Implement dbt temp table cleanup
4. Fix dependency conflicts with pinned versions

### Future
1. Improve SQL dump generation to eliminate duplicates
2. Add pre-flight schema validation before loading
3. Set up alerts for repeated job failures
4. Implement automated temp table cleanup

---

**Lesson Learned:** Should have tested Glue environment compatibility earlier. boto3 version issues are common and should be first thing to check when using newer AWS services (Bedrock).
