# ETL Issue Resolution Log

## Issue: Glue ETL Job Failing with `Unknown column 'r.room_no'`

**Date**: 2026-01-31  
**Status**: ✅ RESOLVED  
**Duration**: ~3 hours of troubleshooting

## Problem Summary

The AWS Glue ETL job was consistently failing with the error:
```
Database Error in model new_contracts (models/analytics/new_contracts.sql)
1054 (42S22): Unknown column 'r.room_no' in 'field list'
```

This occurred for all 3 models that reference the `rooms` table: `new_contracts`, `moveouts`, and `moveout_notices`.

## Root Cause

**The actual column name in the database is `room_number`, not `room_no`.**

However, the dbt SQL files contained `r.room_no as room_number`, which is incorrect.

### Why This Was Confusing

1. **Tool Caching Issue**: The `read_file` tool was showing cached/incorrect content (`room_number`), while the actual files on disk had `room_no`
2. **Multiple Failed Fix Attempts**: The `search_replace` tool appeared to work but didn't actually modify the files
3. **S3 Upload Confusion**: Local and S3 file hashes matched, both containing the wrong value

## Resolution Steps

### 1. Verified Actual Column Name
```bash
# Checked the rooms CSV sample
head -3 /Users/danielkang/tokyobeta-data-consolidation/data/samples/rooms_sample.csv
# Result: Column header is "room_number" (3rd column)
```

### 2. Used `sed` to Fix Files
```bash
sed -i '' 's/r\.room_no as room_number/r.room_number as room_number/g' \
    /Users/danielkang/tokyobeta-data-consolidation/dbt/models/analytics/new_contracts.sql
sed -i '' 's/r\.room_no as room_number/r.room_number as room_number/g' \
    /Users/danielkang/tokyobeta-data-consolidation/dbt/models/analytics/moveouts.sql
sed -i '' 's/r\.room_no as room_number/r.room_number as room_number/g' \
    /Users/danielkang/tokyobeta-data-consolidation/dbt/models/analytics/moveout_notices.sql
```

### 3. Uploaded Fixed Files to S3
```bash
AWS_PROFILE=gghouse aws s3 cp \
    dbt/models/analytics/new_contracts.sql \
    s3://jram-gghouse/dbt-project/models/analytics/new_contracts.sql \
    --region ap-northeast-1
# (Repeated for moveouts.sql and moveout_notices.sql)
```

### 4. Re-ran Glue Job
```bash
AWS_PROFILE=gghouse aws glue start-job-run \
    --job-name tokyobeta-prod-daily-etl \
    --region ap-northeast-1
```

**Result**: ✅ **SUCCEEDED** after 580 seconds (~9.7 minutes)

## Final State

### Glue Job Output
```
============================================================
ETL Job Completed Successfully
Duration: 530.74 seconds
Tables loaded: 80
SQL statements executed: 821
dbt transformations: Success
============================================================
```

### Analytics Tables Created

| Table | Rows | Status |
|-------|------|--------|
| `daily_activity_summary` | 2,965 | ✅ |
| `new_contracts` | 17,573 | ✅ |
| `moveouts` | 15,768 | ✅ |
| `moveout_notices` | 3,791 | ✅ |

### Test Results
- **59/60 tests passed**
- **1 failure**: `assert_no_future_dates` (88 rows with future dates - data quality issue in source, not code)

## Lessons Learned

1. **Always verify with terminal commands** (`cat`, `awk`, `grep`) when file content seems inconsistent with tool outputs
2. **Check source data directly** (CSV files, schema documentation) before assuming column names
3. **Use `sed` or direct file editing** when `search_replace` tool behaves unexpectedly
4. **Verify S3 uploads** by downloading and checking content, not just looking at upload success messages
5. **Database schema documentation can be outdated** - always validate against actual data samples

## Files Modified

- `/Users/danielkang/tokyobeta-data-consolidation/dbt/models/analytics/new_contracts.sql`
- `/Users/danielkang/tokyobeta-data-consolidation/dbt/models/analytics/moveouts.sql`
- `/Users/danielkang/tokyobeta-data-consolidation/dbt/models/analytics/moveout_notices.sql`
- `/Users/danielkang/tokyobeta-data-consolidation/dbt/models/staging/_sources.yml` (updated source definition)

### Changed Lines
```sql
-- BEFORE (incorrect):
        r.room_no as room_number,

-- AFTER (correct):
        r.room_number as room_number,
```

## Next Actions

- [x] ETL job successfully running
- [x] Analytics tables populated
- [ ] QuickSight setup (next phase)
- [ ] Address data quality issues (88 future dates, 629 invalid geocodes, 614 zero rents)

## Related Documents

- [ETL Success Summary](/docs/ETL_SUCCESS_SUMMARY.md)
- [Data Validation Assessment](/docs/DATA_VALIDATION_ASSESSMENT.md)
- [Database Schema Description](/data/database_schema_description.txt)

---

**Resolved By**: AI Agent (Claude Sonnet 4.5)  
**Verified By**: Daniel Kang  
**Date**: 2026-01-31 14:40 JST
