# Automated Empty Table Cleanup

**Implemented:** 2026-02-05  
**Status:** ✅ Active in Production

## Overview

The daily ETL job now automatically drops empty staging tables after each data load. This keeps the database clean and optimized without manual intervention.

## Implementation

### Integration Point

The cleanup runs as **Step 3** in the ETL pipeline:

```
Daily ETL Flow (7:00 AM JST):
1. Download SQL dump from S3
2. Load to Aurora staging schema
3. 🆕 Drop empty tables (automated)
4. Run dbt transformations
5. Archive processed dump
```

### What Gets Dropped

Tables are dropped if they meet ALL criteria:
- Located in `staging` schema
- Have 0 rows (verified twice: once via information_schema, once via COUNT(*))
- Successfully pass DROP TABLE command

### Safety Features

✅ **Double-verification:** Each table is counted twice before dropping  
✅ **Non-blocking:** If drop fails, ETL continues  
✅ **Logged:** All drops are logged in CloudWatch  
✅ **Recoverable:** Tables recreate automatically if source data appears  
✅ **PITR backup:** 7-day recovery window available

## Code Changes

### Updated File: `glue/scripts/daily_etl.py`

**New Function:**
```python
def cleanup_empty_staging_tables():
    """Drop empty staging tables to optimize database performance."""
    # Finds tables with TABLE_ROWS = 0
    # Double-checks with COUNT(*)
    # Drops if confirmed empty
    # Returns count of dropped tables
```

**Integration:**
```python
# Step 3: Clean up empty tables
dropped_count = cleanup_empty_staging_tables()
```

**S3 Location:** `s3://jram-gghouse/glue-scripts/daily_etl.py`

### Supporting Script: `scripts/drop_empty_staging_tables.py`

Can also be run manually:
```bash
# Dry run
python3 scripts/drop_empty_staging_tables.py

# Execute manually
python3 scripts/drop_empty_staging_tables.py --execute --force
```

## Monitoring

### CloudWatch Logs

Check cleanup results in CloudWatch:
```bash
aws logs filter-log-events \
    --log-group-name /aws-glue/jobs/output \
    --filter-pattern "empty tables" \
    --profile gghouse --region ap-northeast-1
```

Example log output:
```
Cleaning up empty staging tables...
Found 3 empty tables to drop
  Dropped: Orders
  Dropped: approvals
  Dropped: work_reports
Cleanup completed: 3 empty tables dropped
```

### Daily Report

The ETL completion log now includes:
```
ETL Job Completed Successfully
Duration: 243.45 seconds
Tables loaded: 71
Empty tables dropped: 3  ← New metric
SQL statements executed: 15847
dbt transformations: Success
```

### Metrics to Track

| Metric | Location | What to Monitor |
|--------|----------|-----------------|
| Tables dropped per run | CloudWatch logs | Should be 0-3 typically |
| Total staging tables | Aurora | Should stay around 71 |
| ETL duration | Glue metrics | Should not increase |
| Failures | CloudWatch errors | Should be 0 |

## Historical Cleanup (2026-02-05)

Initial manual cleanup dropped 10 empty tables:
1. Arrears_Management
2. Arrears_Snapshot
3. Orders
4. approvals
5. gmo_proof_lists
6. m_corporate_name_contracts
7. order_items
8. other_clearings
9. pmc
10. work_reports

**Result:** 81 → 71 tables

**Documentation:** `docs/DROPPED_TABLES_20260205_123010.md`

## Expected Behavior

### Normal Operations

- **Day 1:** ETL loads 81 tables from dump, drops 10 empty → 71 remain
- **Day 2:** ETL loads 71 tables (empty ones not in dump), drops 0 → 71 remain
- **Ongoing:** Stays at ~71 tables unless source system changes

### If Source System Adds Data

**Scenario:** Table `Orders` gets data in source system

```
Day X:     SQL dump includes Orders with 5 rows
           ETL loads → Orders created with 5 rows
           Cleanup runs → Orders kept (has data)
Day X+1:   Orders persists with updated data
```

### If Temporary Table Appears

**Scenario:** Source creates temp table `test_data`

```
Day Y:     SQL dump includes test_data (empty)
           ETL loads → test_data created (0 rows)
           Cleanup runs → test_data dropped
Day Y+1:   test_data not in dump → not recreated
           Database stays clean
```

## Recovery Procedures

### Restore Accidentally Dropped Table

If a table with data was mistakenly dropped:

**1. Point-in-Time Recovery (< 7 days ago)**
```bash
# Restore to just before the drop
./scripts/rollback_etl.sh "2026-02-05T11:30:00Z"
```

**2. Wait for Next ETL Run**
If table exists in source dump, it will recreate automatically.

**3. Manual Recreation**
If you have the schema:
```sql
CREATE TABLE staging.table_name (...);
-- Data will populate on next ETL run
```

## Troubleshooting

### Issue: Cleanup Fails

**Symptom:** CloudWatch shows "Failed to drop {table}"

**Cause:** Table might be locked or referenced

**Solution:**
```sql
-- Check for locks
SHOW PROCESSLIST;

-- Check for foreign key references
SELECT * FROM information_schema.KEY_COLUMN_USAGE 
WHERE REFERENCED_TABLE_NAME = 'table_name';

-- Manual drop if needed
DROP TABLE IF EXISTS staging.table_name;
```

### Issue: Too Many Tables Being Dropped

**Symptom:** 20+ tables dropped in single run

**Cause:** Unusual - might indicate source dump issue

**Solution:**
1. Check source S3 dump is complete
2. Review CloudWatch logs for load errors
3. Consider disabling cleanup temporarily:
   ```python
   # Comment out in daily_etl.py:
   # dropped_count = cleanup_empty_staging_tables()
   dropped_count = 0
   ```

### Issue: Cleanup Never Runs

**Symptom:** Empty tables persist after ETL runs

**Cause:** Glue script not updated or failed before cleanup

**Solution:**
1. Verify S3 script location:
   ```bash
   aws s3 ls s3://jram-gghouse/glue-scripts/daily_etl.py --profile gghouse
   ```
2. Check ETL completed successfully:
   ```bash
   aws glue get-job-runs --job-name tokyobeta-prod-daily-etl --max-results 1 --profile gghouse
   ```
3. Review CloudWatch for errors before cleanup step

## Performance Impact

### Before Automation
- Manual cleanup required
- Empty tables accumulated
- information_schema queries slower
- ETL checked 81 tables every run

### After Automation
- Zero manual intervention
- Database stays clean
- Faster information_schema queries
- ETL only processes active tables
- **Estimated savings:** 2-3 seconds per ETL run

## Rollback Plan

If cleanup causes issues, rollback is simple:

**1. Disable in Glue Script**
```python
# In daily_etl.py, comment out:
# Step 3: Clean up empty tables
# dropped_count = cleanup_empty_staging_tables()
dropped_count = 0  # Cleanup disabled
```

**2. Upload to S3**
```bash
aws s3 cp glue/scripts/daily_etl.py s3://jram-gghouse/glue-scripts/daily_etl.py \
    --profile gghouse --region ap-northeast-1
```

**3. Restore Tables**
Tables will recreate on next ETL run from source dump.

## Testing

### Local Test
```bash
# Test the standalone script
python3 scripts/drop_empty_staging_tables.py  # dry run
python3 scripts/drop_empty_staging_tables.py --execute --force  # execute
```

### Verify in Aurora
```sql
-- Check table count
SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA = 'staging';

-- List empty tables
SELECT TABLE_NAME, TABLE_ROWS 
FROM information_schema.TABLES 
WHERE TABLE_SCHEMA = 'staging' AND TABLE_ROWS = 0;
```

## Related Documentation

- **Implementation Guide:** `docs/STAGING_TABLE_CLEANUP_GUIDE.md`
- **Initial Cleanup Report:** `docs/DROPPED_TABLES_20260205_123010.md`
- **Activity Analysis:** `docs/STAGING_ACTIVE_TABLES_CONFIRMED.md`
- **ETL Script:** `glue/scripts/daily_etl.py`

## Questions?

**Q: Will this delete tables with data?**  
A: No. Double-verification ensures only tables with 0 rows are dropped.

**Q: What if I need an empty table to persist?**  
A: Add it to a skip list in the cleanup function, or ensure it has at least 1 row.

**Q: Can I run cleanup manually?**  
A: Yes, use `scripts/drop_empty_staging_tables.py --execute --force`

**Q: How do I see what was dropped?**  
A: Check CloudWatch logs: `/aws-glue/jobs/output` with filter "empty tables"

---

**Last Updated:** 2026-02-05  
**Maintained by:** Data Engineering Team  
**Glue Job:** tokyobeta-prod-daily-etl
