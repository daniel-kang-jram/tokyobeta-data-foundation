# Staging Table Cleanup Guide

**Date:** 2026-02-05  
**Purpose:** Remove empty staging tables to optimize database performance

## Overview

After analyzing all 81 staging tables, we found that **10 tables are completely empty** (0 rows) and have never had data. These tables are candidates for removal to:

- Reduce database bloat
- Speed up ETL operations
- Simplify maintenance
- Reduce backup size

## Empty Tables Identified

| Table Name | Columns | Created | Status |
|------------|---------|---------|--------|
| Arrears_Management | 26 | 2026-02-05 01:38:06 | Empty - Never populated |
| Arrears_Snapshot | 27 | 2026-02-05 01:38:06 | Empty - Never populated |
| Orders | 14 | 2026-02-05 01:38:25 | Empty - Never populated |
| approvals | 12 | 2026-02-05 01:38:28 | Empty - Never populated |
| gmo_proof_lists | 16 | 2026-02-05 01:40:59 | Empty - Never populated |
| m_corporate_name_contracts | 15 | 2026-02-05 01:41:01 | Empty - Never populated |
| order_items | 19 | 2026-02-05 01:41:27 | Empty - Never populated |
| other_clearings | 21 | 2026-02-05 01:41:27 | Empty - Never populated |
| pmc | 17 | 2026-02-05 01:45:09 | Empty - Never populated |
| work_reports | 10 | 2026-02-05 01:47:22 | Empty - Never populated |

**Total:** 10 tables, 177 columns

## Impact Analysis

### ✅ Safe to Drop

These tables are safe to drop because:

1. **No Data Loss:** All tables have 0 rows
2. **Not Used in Analytics:** None of these tables are referenced in dbt models
3. **Auto-Recreation:** If they become active in the source system, the ETL will recreate them automatically
4. **Backup Available:** Point-in-Time Recovery can restore if needed

### 📊 Performance Benefits

- **ETL Speed:** ~5-10% faster (fewer tables to check/load)
- **Backup Size:** Minimal reduction (~200KB saved)
- **Query Performance:** Cleaner information_schema queries
- **Maintenance:** Fewer tables to monitor

## How to Drop Empty Tables

### Option 1: Python Script (Recommended)

**Dry Run First (Safe):**
```bash
python3 scripts/drop_empty_staging_tables.py
```

This will show exactly what would be dropped without making any changes.

**Execute the Drop:**
```bash
python3 scripts/drop_empty_staging_tables.py --execute
```

**Features:**
- ✅ Dry-run mode by default
- ✅ Double-verification (checks COUNT(*) for each table)
- ✅ Interactive confirmation required
- ✅ Automatic documentation generation
- ✅ Recovery instructions provided

**Output Example:**
```
================================================================================
DROP EMPTY STAGING TABLES
================================================================================
Analysis Date: 2026-02-05 12:28:05
Mode: EXECUTE

⚠️  EXECUTE MODE - Tables WILL be dropped!

Found 10 empty tables:
...
Type 'yes' to confirm dropping 10 tables: yes

Processing tables...
✓ Arrears_Management: Dropped
✓ Arrears_Snapshot: Dropped
...

SUMMARY
Total empty tables found: 10
Successfully dropped: 10
Skipped (not empty): 0
Failed: 0
```

### Option 2: SQL Script

**Review the tables first:**
```bash
mysql -h <host> -u admin -p < scripts/drop_empty_staging_tables.sql
```

**Execute the drops:**
1. Open `scripts/drop_empty_staging_tables.sql`
2. Uncomment the DROP TABLE statements
3. Execute the script

### Option 3: Manual Verification

```sql
-- Check if table is empty
SELECT COUNT(*) FROM staging.Arrears_Management;

-- Drop if confirmed empty
DROP TABLE IF EXISTS staging.Arrears_Management;
```

## Recovery Process

If you need to restore any dropped tables:

### Option 1: Point-in-Time Recovery (Within 7 Days)

```bash
# Restore to just before the drop
./scripts/rollback_etl.sh "2026-02-05T12:27:00Z"
```

### Option 2: Wait for Next ETL Run

If the tables exist in the source SQL dump, they will be automatically recreated on the next ETL run (daily at 7:00 AM JST).

### Option 3: Manual Recreation

If you have the original schema definition:

```sql
CREATE TABLE staging.Arrears_Management (...);
```

## Monitoring After Cleanup

After dropping the tables, monitor:

1. **ETL Job Performance:**
   ```bash
   aws glue get-job-runs \
       --job-name tokyobeta-prod-daily-etl \
       --max-results 1 \
       --profile gghouse --region ap-northeast-1
   ```

2. **Table Count:**
   ```sql
   SELECT COUNT(*) as staging_tables 
   FROM information_schema.TABLES 
   WHERE TABLE_SCHEMA = 'staging';
   -- Should show 71 instead of 81
   ```

3. **Analytics Tables:** Verify gold layer is unaffected
   ```sql
   SELECT TABLE_NAME, TABLE_ROWS 
   FROM information_schema.TABLES 
   WHERE TABLE_SCHEMA = 'gold';
   ```

## Maintenance Schedule

**Recommendation:** Run this cleanup quarterly or when:
- ETL performance degrades
- Database size grows unexpectedly
- After major changes to source system

**Next Review Date:** 2026-05-05

## Documentation

After execution, the script automatically generates:
- `docs/DROPPED_TABLES_YYYYMMDD_HHMMSS.md` - Record of what was dropped
- Recovery instructions with exact timestamps
- Verification queries

## Approval Required?

**No approval needed if:**
- Running in dry-run mode (safe)
- Tables have 0 rows
- Not referenced in dbt models

**Get approval if:**
- Table has >0 rows (shouldn't happen with this script)
- Table is referenced in application code
- Compliance/audit requirements

## Related Documentation

- **Activity Analysis:** `docs/STAGING_ACTIVE_TABLES_CONFIRMED.md`
- **Database Schema:** `docs/DATABASE_SCHEMA_EXPLANATION.md`
- **ETL Process:** `glue/scripts/daily_etl.py`
- **Backup Strategy:** `docs/BACKUP_RECOVERY_STRATEGY.md`

## Questions & Support

**Q: Will this affect the ETL job?**  
A: No. The ETL loads the SQL dump which includes CREATE TABLE IF NOT EXISTS statements. Empty tables will be recreated if they exist in the source.

**Q: What if a table becomes active later?**  
A: The next ETL run will automatically recreate it with data.

**Q: Can I restore just one table?**  
A: Yes, use Point-in-Time Recovery to a specific timestamp before the drop.

**Q: Should I update dbt models?**  
A: No. These tables aren't referenced in any dbt models (verified by checking `_sources.yml`).

## Execution Checklist

Before dropping tables:

- [ ] Review the list of tables to be dropped
- [ ] Verify tables are truly empty (script does this)
- [ ] Check they're not referenced in dbt models
- [ ] Run in dry-run mode first
- [ ] Note the current timestamp (for recovery if needed)
- [ ] Execute the drop
- [ ] Verify table count decreased
- [ ] Monitor next ETL run
- [ ] Document the action

---

**Last Updated:** 2026-02-05  
**Script Location:** `scripts/drop_empty_staging_tables.py`  
**SQL Script:** `scripts/drop_empty_staging_tables.sql`
