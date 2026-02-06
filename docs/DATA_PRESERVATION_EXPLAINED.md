# Data Preservation in Medallion Architecture

**Question:** Aren't we wiping the entire database every day? How is historical data preserved?

**Answer:** No! Only the `staging` schema gets refreshed. The `silver` and `gold` schemas preserve historical data.

## Schema Separation Strategy

### Daily ETL Flow

```
5:30 AM JST - EC2 Cron Job
  ↓
  Generates SQL dump from source system
  ↓
7:00 AM JST - AWS Glue ETL
  ↓
┌─────────────────────────────────────────────────────────┐
│ STEP 1: Load SQL Dump into STAGING Schema              │
│                                                         │
│ Connection: USE staging;                                │
│ SQL Dump contains:                                      │
│   DROP TABLE IF EXISTS tenants;                         │
│   CREATE TABLE tenants (...);                           │
│   INSERT INTO tenants VALUES (...);                     │
│                                                         │
│ Result: staging.tenants REPLACED with today's snapshot │
│         (Only current state, no history)                │
└─────────────────────────────────────────────────────────┘
  ↓
  STAGING tables now have today's data only
  ↓
┌─────────────────────────────────────────────────────────┐
│ STEP 2: dbt Runs - Transforms staging → silver         │
│                                                         │
│ tenant_status_history (INCREMENTAL materialization):    │
│   1. Read current snapshot from staging.tenants         │
│   2. Compare with yesterday's silver.tenant_status_history │
│   3. Detect changes in status fields                    │
│   4. IF changed:                                        │
│      - INSERT new row with today's date                 │
│      - UPDATE previous row (close it out)               │
│   5. IF NOT changed:                                    │
│      - Do nothing (preserve existing row)               │
│                                                         │
│ Result: silver.tenant_status_history GROWS over time   │
│         (Appends new rows, never drops old ones)        │
└─────────────────────────────────────────────────────────┘
  ↓
  SILVER tables have cumulative historical data
  ↓
┌─────────────────────────────────────────────────────────┐
│ STEP 3: dbt Runs - Transforms silver → gold            │
│                                                         │
│ tenant_status_transitions (TABLE materialization):      │
│   Rebuilds from silver.tenant_status_history            │
│   Adds business labels and calculations                 │
│   All historical data preserved in source               │
└─────────────────────────────────────────────────────────┘
```

## Concrete Example: 3-Day Timeline

### Day 1: February 6, 2026

**Morning:**
```sql
-- STAGING (after SQL dump load)
SELECT id, status FROM staging.tenants WHERE id = 12345;
-- Result: 12345, 3 (Application)
```

**After dbt runs:**
```sql
-- SILVER (incremental insert)
SELECT * FROM silver.tenant_status_history WHERE tenant_id = 12345;
```
| tenant_id | status | valid_from | valid_to | is_current |
|-----------|--------|------------|----------|------------|
| 12345     | 3      | 2026-02-06 | NULL     | TRUE       |

### Day 2: February 7, 2026 (Status CHANGED)

**Morning:**
```sql
-- STAGING (after SQL dump load - replaces yesterday's data)
SELECT id, status FROM staging.tenants WHERE id = 12345;
-- Result: 12345, 4 (Under Contract) ← CHANGED!
```

**After dbt runs:**
```sql
-- SILVER (incremental - previous row UPDATED, new row INSERTED)
SELECT * FROM silver.tenant_status_history WHERE tenant_id = 12345;
```
| tenant_id | status | valid_from | valid_to   | is_current |
|-----------|--------|------------|------------|------------|
| 12345     | 3      | 2026-02-06 | 2026-02-06 | FALSE      | ← Updated (closed)
| 12345     | 4      | 2026-02-07 | NULL       | TRUE       | ← Inserted (new)

### Day 3: February 8, 2026 (Status UNCHANGED)

**Morning:**
```sql
-- STAGING (after SQL dump load - replaces yesterday's data)
SELECT id, status FROM staging.tenants WHERE id = 12345;
-- Result: 12345, 4 (Under Contract) ← NO CHANGE
```

**After dbt runs:**
```sql
-- SILVER (no change detected, no insert)
SELECT * FROM silver.tenant_status_history WHERE tenant_id = 12345;
```
| tenant_id | status | valid_from | valid_to   | is_current |
|-----------|--------|------------|------------|------------|
| 12345     | 3      | 2026-02-06 | 2026-02-06 | FALSE      | ← Preserved
| 12345     | 4      | 2026-02-07 | NULL       | TRUE       | ← Preserved

**Notice:** Historical record from Day 1 is still there!

### Day 30: March 7, 2026 (Status CHANGED Again)

**Morning:**
```sql
-- STAGING (after SQL dump load)
SELECT id, status FROM staging.tenants WHERE id = 12345;
-- Result: 12345, 5 (Active Tenant) ← CHANGED!
```

**After dbt runs:**
```sql
-- SILVER (incremental - Day 2 record closed, new record inserted)
SELECT * FROM silver.tenant_status_history WHERE tenant_id = 12345;
```
| tenant_id | status | valid_from | valid_to   | is_current |
|-----------|--------|------------|------------|------------|
| 12345     | 3      | 2026-02-06 | 2026-02-06 | FALSE      | ← Day 1 preserved
| 12345     | 4      | 2026-02-07 | 2026-03-06 | FALSE      | ← Day 2 closed
| 12345     | 5      | 2026-03-07 | NULL       | TRUE       | ← Day 30 new

**Complete history preserved!** We can see:
- Was in Application for 1 day (Feb 6)
- Was Under Contract for 28 days (Feb 7 - Mar 6)
- Is now Active Tenant (Mar 7 onwards)

## How dbt Incremental Materialization Works

### Configuration
```sql
{{
    config(
        materialized='incremental',  ← Key setting
        unique_key=['tenant_id', 'valid_from']
    )
}}
```

### What "incremental" Means

**First Run (Full Refresh):**
```sql
-- dbt creates table and inserts all rows
CREATE TABLE silver.tenant_status_history AS
SELECT ... FROM staging.tenants;
```

**Subsequent Runs (Incremental):**
```sql
-- dbt does NOT drop table
-- Instead, it detects new/changed data and inserts only those rows
INSERT INTO silver.tenant_status_history
SELECT ... FROM staging.tenants
WHERE <conditions detect changes>;

-- Plus post-hook updates to close old records
UPDATE silver.tenant_status_history
SET valid_to = ..., is_current = FALSE
WHERE <conditions for superseded records>;
```

### Key Points

✅ **Table is NEVER dropped** (unless you run `--full-refresh` manually)  
✅ **Old rows are NEVER deleted**  
✅ **Only new rows are INSERTED**  
✅ **Old rows are UPDATED** to set valid_to and is_current=FALSE  
✅ **Complete audit trail preserved**

## Schema-Level Protection

Our database has **3 separate schemas** that are managed differently:

| Schema | Managed By | Refresh Strategy | Historical Data? |
|--------|-----------|------------------|------------------|
| **staging** | SQL Dump | ❌ DROP & RECREATE daily | NO - only current snapshot |
| **silver** | dbt | ✅ INCREMENTAL append | YES - accumulates history |
| **gold** | dbt | ✅ TABLE rebuild from silver | YES - rebuilt from history |
| **seeds** | dbt | ✅ SEED files | YES - static reference data |

### Why This Is Safe

1. **SQL Dump scoped to staging only**
   ```python
   cursor.execute("USE staging")  # All dump statements run here
   ```

2. **dbt creates separate schemas**
   ```sql
   CREATE SCHEMA IF NOT EXISTS silver;  -- Independent from staging
   CREATE SCHEMA IF NOT EXISTS gold;    -- Independent from staging
   ```

3. **No cross-schema drops**
   - Staging SQL dump can't affect silver/gold (different schema)
   - dbt incremental models never drop their own tables

## Verification Queries

### Check Historical Data Preserved

```sql
-- 1. Count total historical records
SELECT COUNT(*) as total_history
FROM silver.tenant_status_history;
-- Should grow over time, never shrink

-- 2. Check records per day
SELECT 
    DATE(dbt_updated_at) as load_date,
    COUNT(*) as records_added
FROM silver.tenant_status_history
GROUP BY DATE(dbt_updated_at)
ORDER BY load_date DESC;
-- Should show records from all past dates

-- 3. Verify old records not deleted
SELECT 
    tenant_id,
    status,
    valid_from,
    valid_to,
    is_current
FROM silver.tenant_status_history
WHERE tenant_id = 12345  -- Example tenant
ORDER BY valid_from;
-- Should show complete history for this tenant

-- 4. Count closed (historical) records
SELECT COUNT(*) as historical_records
FROM silver.tenant_status_history
WHERE is_current = FALSE;
-- Should be > 0 after Day 2, and grow over time
```

## What Could Go Wrong (And Safeguards)

### Scenario 1: Someone Runs --full-refresh

**Command:**
```bash
dbt run --select tenant_status_history --full-refresh
```

**What Happens:**
- ❌ Table is dropped and recreated
- ❌ All historical data lost

**Safeguard:**
- Don't run `--full-refresh` on historical tables
- Only run it on initial deployment or after major schema changes
- Always backup before full-refresh

### Scenario 2: Schema Gets Dropped

**Command:**
```sql
DROP SCHEMA silver CASCADE;
```

**What Happens:**
- ❌ All silver tables deleted, including history

**Safeguard:**
- RDS permissions restrict DROP SCHEMA
- Aurora automated backups (7-day PITR)
- Can restore to any point in time within 7 days

### Scenario 3: dbt Materialization Misconfigured

**Wrong Config:**
```sql
config(materialized='table')  -- Wrong! Should be 'incremental'
```

**What Happens:**
- ❌ Table dropped and recreated every run
- ❌ History lost

**Safeguard:**
- Code review before deployment
- Test locally first
- Documentation clearly states 'incremental'

## Backup & Recovery

### Aurora Automated Backups

- **Retention:** 7 days (Point-in-Time Recovery)
- **Cost:** $0 (included in Aurora pricing)
- **Recovery Time:** 5-10 minutes

### Recovery Example

If historical data is accidentally deleted:

```bash
# Check available restore window
./scripts/rollback_etl.sh

# Restore to yesterday (before deletion)
./scripts/rollback_etl.sh "2026-02-06T06:00:00Z"
```

## Best Practices

### ✅ DO

1. **Use incremental for historical tables**
   ```sql
   config(materialized='incremental')
   ```

2. **Run normal incremental updates**
   ```bash
   dbt run --select tenant_status_history
   ```

3. **Monitor historical record growth**
   ```sql
   SELECT COUNT(*) FROM silver.tenant_status_history;
   ```

### ❌ DON'T

1. **Don't run full-refresh on historical tables**
   ```bash
   # BAD: dbt run --select tenant_status_history --full-refresh
   ```

2. **Don't use 'table' materialization for history**
   ```sql
   # BAD: config(materialized='table')
   ```

3. **Don't manually drop silver/gold schemas**
   ```sql
   # BAD: DROP SCHEMA silver CASCADE;
   ```

## Summary

### Key Takeaways

✅ **Staging gets wiped daily** - by design, it's just a landing zone  
✅ **Silver/Gold preserve history** - dbt incremental models accumulate data  
✅ **Schema separation protects data** - staging drops don't affect silver/gold  
✅ **Audit trail is complete** - every status change recorded  
✅ **Recovery available** - 7-day PITR backup if needed

### Data Flow Recap

```
Source System → Daily Dump → STAGING (transient)
                                ↓
                            dbt transforms
                                ↓
                        SILVER (historical, accumulates)
                                ↓
                            dbt transforms
                                ↓
                        GOLD (analytical, rebuilt from history)
```

**The medallion architecture is specifically designed to preserve history while refreshing source data!**

---

**Questions?**
- See `dbt/models/silver/tenant_status_history.sql` for incremental logic
- See `docs/TENANT_STATUS_HISTORY_IMPLEMENTATION.md` for full details
- Run verification queries above to confirm history preserved
