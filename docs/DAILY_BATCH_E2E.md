# Daily Batch ETL - End-to-End Process

## Overview

The Tokyo Beta Data Consolidation pipeline runs daily to transform raw SQL dumps into analytics-ready data for QuickSight dashboards. This document describes the complete end-to-end flow.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        DAILY BATCH ETL PIPELINE                          │
│                         (Runs at 7:00 AM JST)                            │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   EXTERNAL   │     │    BRONZE    │     │    SILVER    │     │     GOLD     │
│   (EC2 Dump) │────▶│   (Staging)  │────▶│  (Cleaned)   │────▶│  (Analytics) │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
    5:30 AM              7:00 AM              7:05 AM              7:08 AM
```

---

## Phase 1: Source Data Generation (EXTERNAL)

**Time:** 5:30 AM JST  
**Owner:** External stakeholder (EC2 cron job)  
**Location:** External EC2 instance → S3

### Process

```bash
# External EC2 cron job (managed by stakeholders)
30 5 * * * /path/to/dump_script.sh
```

**What Happens:**
1. MySQL dumps generated from production database
2. Four dump files created:
   - `movings_YYYYMMDD.sql` (~25k contracts)
   - `tenants_YYYYMMDD.sql` (~12k tenants)
   - `rooms_YYYYMMDD.sql` (~16k rooms)
   - `inquiries_YYYYMMDD.sql` (~variable inquiries)

3. Files uploaded to S3:
   ```
   s3://jram-gghouse/dumps/
   ├── movings_20260210.sql
   ├── tenants_20260210.sql
   ├── rooms_20260210.sql
   └── inquiries_20260210.sql
   ```

**Duration:** ~15 minutes  
**Output:** Fresh SQL dumps in S3

**Monitoring:**
```bash
# Check if today's dumps exist
aws s3 ls s3://jram-gghouse/dumps/ --profile gghouse | grep $(date +%Y%m%d)
```

---

## Phase 2: Bronze Layer - Staging Load (AURORA)

**Time:** 7:00 AM JST  
**Trigger:** EventBridge scheduled rule  
**Job:** `tokyobeta-prod-staging-loader` (Glue)  
**Duration:** ~3-5 minutes

### Process

```python
# glue/scripts/staging_loader.py
1. Download SQL dumps from S3
2. Parse and validate SQL structure
3. Truncate staging tables (clean slate)
4. Load data into Aurora staging schema
5. Create tenant_daily_snapshots (for SCD tracking)
```

**Tables Loaded:**
```sql
staging.movings          -- Contract/move history
staging.tenants          -- Tenant demographics
staging.rooms            -- Room inventory
staging.inquiries        -- Customer inquiries
staging.tenant_daily_snapshots -- Daily snapshot for history
```

**Example:**
```bash
# Trigger manually
aws glue start-job-run \
  --job-name tokyobeta-prod-staging-loader \
  --profile gghouse

# Check status
aws glue get-job-run \
  --job-name tokyobeta-prod-staging-loader \
  --run-id <run-id> \
  --profile gghouse
```

**Output:**
- Staging tables populated with raw data
- Snapshot captured for SCD Type 2 tracking

**Monitoring:**
```sql
-- Verify staging freshness
SELECT 
  'movings' as table_name, 
  COUNT(*) as row_count,
  MAX(updated_at) as last_updated
FROM staging.movings
UNION ALL
SELECT 'tenants', COUNT(*), MAX(updated_at) FROM staging.tenants
UNION ALL
SELECT 'rooms', COUNT(*), MAX(updated_at) FROM staging.rooms;
```

---

## Phase 3: Silver Layer - Data Cleaning & Transformation

**Time:** 7:05 AM JST (after staging completes)  
**Trigger:** EventBridge (after staging success)  
**Job:** `tokyobeta-prod-silver-transformer` (Glue + dbt)  
**Duration:** ~3 minutes (with tests skipped)

### Process

```python
# glue/scripts/silver_transformer.py
1. Download dbt project from S3
2. Install dbt dependencies
3. Run dbt seed (load code mappings)
4. Run dbt silver models
5. Skip tests (SKIP_TESTS=true) → Run separately in silver_test job
6. Create backups of previous versions
```

**dbt Models Built:**
```
silver/
├── stg_movings          -- Cleaned contracts (25k rows)
├── stg_tenants          -- Cleaned demographics (12k rows)
├── stg_apartments       -- Cleaned properties (700 properties)
├── stg_rooms            -- Cleaned room inventory (16k rooms)
├── int_contracts        -- Denormalized fact table (17k contracts)
├── tenant_status_history -- SCD Type 2 (historical status changes)
└── tenant_room_snapshot_daily -- Daily snapshots (12k rows/day, incremental)
```

**Key Transformations:**
- **Code Enrichment:** Numeric codes → Human-readable labels (Japanese + English)
- **Data Cleaning:** NULL handling, type casting, validation
- **Deduplication:** ROW_NUMBER() for handling duplicate movings
- **SCD Type 2:** Tenant status history tracking (valid_from/valid_to)
- **Incremental Snapshots:** Daily tenant-room pairs for occupancy tracking

**Example:**
```bash
# Run silver transformation (fast mode, tests skipped)
aws glue start-job-run \
  --job-name tokyobeta-prod-silver-transformer \
  --profile gghouse

# Run tests separately (optional, can be async)
aws glue start-job-run \
  --job-name tokyobeta-prod-silver-test \
  --profile gghouse
```

**Output:**
- Clean, standardized tables in `silver` schema
- Historical change tracking (SCD)
- Daily incremental snapshots

**Performance Optimization:**
- **Before:** 30+ minutes (with inline tests)
- **After:** ~3 minutes (tests separated)
- Tests can run async/independently for validation

---

## Phase 4: Gold Layer - Analytics Aggregation

**Time:** 7:08 AM JST (after silver completes)  
**Trigger:** EventBridge (after silver success)  
**Job:** `tokyobeta-prod-gold-transformer` (Glue + dbt + SQL)  
**Duration:** ~10 minutes

### Process

```python
# glue/scripts/gold_transformer.py
1. Download dbt project from S3
2. Run dbt gold models (analytics aggregations)
3. Compute occupancy KPIs (integrated, replaces old kpi-updater job)
   - Historical KPIs (last 3 days)
   - Future projections (next 90 days)
4. Run dbt gold tests (validation)
5. Create backups
```

**dbt Models Built:**
```
gold/
├── new_contracts         -- Daily new contracts (demographics + geolocation)
├── moveouts              -- Completed moveouts with tenant history
├── moveout_notices       -- Rolling 24-month moveout notices
├── moveout_analysis      -- Moveout trends and patterns
├── moveout_summary       -- Aggregated moveout metrics
├── tenant_status_transitions -- Status change events
└── occupancy_daily_metrics -- **NEW** Daily occupancy KPIs (replaces daily_activity_summary)
```

**Occupancy KPI Metrics (Integrated Logic):**
```sql
-- Computed for each snapshot_date (past + future 90 days)
SELECT 
  snapshot_date,
  applications,           -- 申込 (Applications)
  new_moveins,            -- 新規入居者 (New move-ins)
  new_moveouts,           -- 新規退去者 (New move-outs)
  occupancy_delta,        -- 稼働室数増減 (net change)
  period_start_rooms,     -- 期首稼働室数 (start count)
  period_end_rooms,       -- 期末稼働室数 (end count)
  occupancy_rate          -- 稼働率 (occupancy %)
FROM gold.occupancy_daily_metrics
WHERE snapshot_date BETWEEN CURDATE() - INTERVAL 3 DAY 
                        AND CURDATE() + INTERVAL 90 DAY
ORDER BY snapshot_date;
```

**Future Projections Logic:**
- For **future dates** (> today):
  - Uses **today's snapshot** (`snapshot_date = CURDATE()`)
  - Filters by `move_in_date` and `moveout_date` for projections
  - `applications` set to 0 (cannot predict)
  - `new_moveins`: Status 4/5 with `move_in_date = future_date`
  - `new_moveouts`: Any status with `moveout_date = future_date`

- For **past/today dates**:
  - Uses **actual historical snapshots**
  - `new_moveins`: Status 4/5/6/7/9 with `move_in_date = date`
  - `new_moveouts`: Uses `moveout_plans_date = date` (actual moveouts)

**Example:**
```bash
# Run gold transformation (includes occupancy KPIs)
aws glue start-job-run \
  --job-name tokyobeta-prod-gold-transformer \
  --profile gghouse

# Check occupancy metrics
mysql -h $AURORA_ENDPOINT -u admin -p tokyobeta -e "
  SELECT 
    snapshot_date,
    period_end_rooms,
    ROUND(occupancy_rate * 100, 2) as occupancy_pct
  FROM gold.occupancy_daily_metrics
  WHERE snapshot_date BETWEEN CURDATE() - 7 AND CURDATE() + 7
  ORDER BY snapshot_date;
"
```

**Output:**
- Analytics-ready aggregations in `gold` schema
- Daily occupancy KPIs (historical + 90-day forecast)
- QuickSight-ready dimensional models

---

## Phase 5: Data Quality & Monitoring

### Real-Time Monitoring (CloudWatch)

**Freshness Checker Lambda:**
- **Schedule:** Daily at 9:00 AM JST (after ETL completes)
- **Function:** Checks table freshness
- **Alarms:** Triggered if any table > 2 days old

```python
# Monitored tables
tables_to_check = [
    'staging.movings',
    'staging.tenants',
    'silver.tenant_room_snapshot_daily',
    'gold.occupancy_daily_metrics'
]

# SLA: WARN if > 1 day old, CRITICAL if > 2 days old
```

**CloudWatch Alarms:**
1. **Glue Job Failures:** Any job failure triggers SNS alert
2. **Glue Job Duration:** Alert if > 60 minutes (indicates issue)
3. **Aurora CPU:** Alert if > 80% for 5 minutes
4. **Data Staleness:** Alert if tables not updated in 2 days

**SNS Notifications:**
- Email: `jram-ggh@outlook.com`
- Topic: `tokyobeta-prod-dashboard-etl-alerts`

### Manual Validation (Optional)

```bash
# 1. Check all jobs completed
aws glue get-job-runs --job-name tokyobeta-prod-staging-loader --max-items 1 --profile gghouse
aws glue get-job-runs --job-name tokyobeta-prod-silver-transformer --max-items 1 --profile gghouse
aws glue get-job-runs --job-name tokyobeta-prod-gold-transformer --max-items 1 --profile gghouse

# 2. Verify data freshness
python3 scripts/check_data_freshness.py

# 3. Check row counts
mysql -h $AURORA_ENDPOINT -u admin -p tokyobeta < scripts/verify_row_counts.sql

# 4. Run silver tests (optional)
aws glue start-job-run --job-name tokyobeta-prod-silver-test --profile gghouse
```

---

## Phase 6: QuickSight Refresh

**Time:** 8:00 AM JST (after gold completes)  
**Trigger:** Manual or scheduled SPICE refresh  
**Duration:** ~5 minutes

### Process

```bash
# Option 1: Auto-refresh (if configured in QuickSight)
# - QuickSight SPICE refresh scheduled for 8:00 AM JST

# Option 2: Manual trigger via AWS Console
# - Navigate to QuickSight Datasets
# - Select "Tokyo Beta Occupancy" dataset
# - Click "Refresh Now"

# Option 3: CLI refresh
aws quicksight create-ingestion \
  --aws-account-id 343881458651 \
  --data-set-id <dataset-id> \
  --ingestion-id $(date +%Y%m%d-%H%M%S) \
  --profile gghouse
```

**Datasets Refreshed:**
- Occupancy metrics (daily KPIs)
- New contracts (demographic trends)
- Moveout analysis (churn metrics)
- Property performance (portfolio view)

---

## Complete Timeline

```
05:30 AM JST  │ EC2 Dump Generation          │ ~15 min │ External
──────────────┼──────────────────────────────┼─────────┼─────────
07:00 AM JST  │ Staging Load                 │ ~5 min  │ staging_loader
07:05 AM JST  │ Silver Transformation        │ ~3 min  │ silver_transformer
07:08 AM JST  │ Gold Aggregation + KPIs      │ ~10 min │ gold_transformer
07:18 AM JST  │ Pipeline Complete            │         │
──────────────┼──────────────────────────────┼─────────┼─────────
08:00 AM JST  │ QuickSight SPICE Refresh     │ ~5 min  │ QuickSight
09:00 AM JST  │ Freshness Monitoring         │ ~1 min  │ Lambda
──────────────┴──────────────────────────────┴─────────┴─────────

Total ETL Duration: ~18 minutes (down from 45+ minutes before optimization)
```

---

## Data Flow Summary

### Row Counts (Typical Daily Batch)

| Layer | Table | Rows | Operation | Duration |
|-------|-------|------|-----------|----------|
| **Staging** | movings | 25,000 | Full reload | 2 min |
| | tenants | 12,000 | Full reload | 1 min |
| | rooms | 16,000 | Full reload | 1 min |
| | tenant_daily_snapshots | +1 | Append daily | <1 sec |
| **Silver** | stg_movings | 25,000 | Full rebuild | 30 sec |
| | stg_tenants | 12,000 | Full rebuild | 20 sec |
| | int_contracts | 17,000 | Full rebuild | 30 sec |
| | tenant_status_history | ~50,000 | Full rebuild (SCD) | 60 sec |
| | tenant_room_snapshot_daily | +12,000 | **Incremental** | 10 sec |
| **Gold** | new_contracts | 17,000 | Full rebuild | 20 sec |
| | moveouts | 15,000 | Full rebuild | 20 sec |
| | occupancy_daily_metrics | +94 | **Incremental** (3 past + 90 future + 1 today) | 480 sec |
| | (others) | Variable | Full rebuild | 60 sec |

### Storage Growth

- **Staging:** Static (~50 MB, replaced daily)
- **Silver:** Grows slowly (~1 GB/year)
  - `tenant_room_snapshot_daily`: ~12k rows/day = 4.4M rows/year
  - `tenant_status_history`: Changes only
- **Gold:** Grows daily (~500 MB/year)
  - `occupancy_daily_metrics`: 1 row/day = 365 rows/year
  - Historical metrics retained indefinitely

---

## Error Handling & Recovery

### Common Failure Scenarios

#### 1. Staging Load Fails (S3 dumps missing)

**Symptom:** `staging_loader` job fails with "S3 object not found"

**Root Cause:** External EC2 dump didn't run

**Recovery:**
```bash
# 1. Check if dumps exist
aws s3 ls s3://jram-gghouse/dumps/ --profile gghouse | grep $(date +%Y%m%d)

# 2. If missing, contact external stakeholder

# 3. If exists, retry staging load
aws glue start-job-run --job-name tokyobeta-prod-staging-loader --profile gghouse
```

#### 2. Silver Transformation Fails (dbt error)

**Symptom:** `silver_transformer` job fails with dbt compilation error

**Root Cause:** Schema change, bad data, or dbt syntax error

**Recovery:**
```bash
# 1. Check logs
aws logs tail /aws-glue/jobs/error --profile gghouse --follow

# 2. Identify failing model
# Look for "Compilation Error" or "Database Error" in logs

# 3. Fix dbt model, upload to S3
aws s3 cp dbt/models/silver/<model>.sql s3://jram-gghouse/dbt-project/models/silver/ --profile gghouse

# 4. Retry transformation
aws glue start-job-run --job-name tokyobeta-prod-silver-transformer --profile gghouse
```

#### 3. Gold Job Timeout (> 60 minutes)

**Symptom:** `gold_transformer` times out during KPI computation

**Root Cause:** Large date range, inefficient query, or database lock

**Recovery:**
```bash
# 1. Check for database locks
python3 scripts/check_aurora_locks.py

# 2. Reduce LOOKBACK_DAYS if needed
aws glue start-job-run \
  --job-name tokyobeta-prod-gold-transformer \
  --arguments '{"--LOOKBACK_DAYS":"1","--FORWARD_DAYS":"30"}' \
  --profile gghouse

# 3. If persistent, check KPI query performance
mysql -h $AURORA_ENDPOINT -u admin -p tokyobeta -e "EXPLAIN ..."
```

#### 4. Data Staleness Alert

**Symptom:** CloudWatch alarm: "tokyobeta-prod-staging-movings-stale"

**Root Cause:** ETL pipeline didn't run or failed

**Recovery:**
```bash
# 1. Run emergency staging fix
python3 scripts/emergency_staging_fix.py --check-only

# 2. If S3 dumps are fresh, load them
python3 scripts/emergency_staging_fix.py --tables movings tenants rooms

# 3. Trigger downstream transforms
aws glue start-job-run --job-name tokyobeta-prod-silver-transformer --profile gghouse
aws glue start-job-run --job-name tokyobeta-prod-gold-transformer --profile gghouse
```

---

## Performance Optimization History

### Before Optimization (Jan 2026)

```
07:00  Staging Load           ~5 min  ✓
07:05  Silver Transform       ~30 min ✗ (tests inline)
07:35  Gold Transform         ~15 min ✗ (no KPI integration)
07:50  KPI Updater (separate) ~10 min ✗ (redundant job)
────────────────────────────────────────
Total: ~60 minutes
```

**Issues:**
- Silver tests scanning 1.5M+ rows (relationships, unique, accepted_values)
- Gold and KPI as separate jobs (redundant dbt setup)
- No test separation (blocking pipeline)

### After Optimization (Feb 2026)

```
07:00  Staging Load           ~5 min  ✓
07:05  Silver Transform       ~3 min  ✓ (tests skipped)
07:08  Gold Transform + KPIs  ~10 min ✓ (integrated)
────────────────────────────────────────
Total: ~18 minutes (70% faster)

Tests (async, non-blocking):
09:00  Silver Test            ~10 min ✓ (optional)
```

**Improvements:**
1. **Silver tests separated**: Disabled expensive dbt tests, rely on DB constraints
2. **Gold/KPI integrated**: Single job, shared dbt setup, no redundancy
3. **Test job created**: `silver_test` runs independently for validation
4. **Glue connections added**: Fixed Aurora connectivity issues

---

## Key Lessons Learned (Feb 2026 Incident)

### Issue: 8-Day Data Staleness

**Timeline:**
- Feb 2: Staging tables last updated
- Feb 10: Discovered 8 days stale
- Root Cause: Glue ETL jobs existed but weren't triggered automatically

**Prevention Measures Implemented:**

1. **Automated Freshness Monitoring**
   - Lambda checks every table daily at 9 AM JST
   - CloudWatch alarms if > 2 days old
   - SNS alerts sent immediately

2. **Pipeline Validation**
   - Always verify FULL pipeline: Dump → S3 → Glue → Tables
   - Don't assume one part working means all parts work

3. **Emergency Recovery Scripts**
   - `emergency_staging_fix.py`: Quick reload from S3
   - `check_data_freshness.py`: Manual verification
   - Recovery time < 15 minutes

---

## Monitoring Commands Cheat Sheet

```bash
# Check if today's batch ran
aws glue get-job-runs \
  --job-name tokyobeta-prod-staging-loader \
  --max-items 1 \
  --profile gghouse \
  --query 'JobRuns[0].[JobRunState,StartedOn,ExecutionTime]'

# Verify table freshness
python3 scripts/check_data_freshness.py

# Check occupancy metrics
mysql -h $AURORA_ENDPOINT -u admin -p tokyobeta -e "
  SELECT snapshot_date, period_end_rooms, 
         ROUND(occupancy_rate*100,2) as occ_pct
  FROM gold.occupancy_daily_metrics 
  WHERE snapshot_date = CURDATE();
"

# Trigger full pipeline manually
aws glue start-job-run --job-name tokyobeta-prod-staging-loader --profile gghouse
# Wait for completion, then:
aws glue start-job-run --job-name tokyobeta-prod-silver-transformer --profile gghouse
# Wait for completion, then:
aws glue start-job-run --job-name tokyobeta-prod-gold-transformer --profile gghouse
```

---

## Architecture Documentation

- **Pipeline Code:** `/glue/scripts/`
- **dbt Models:** `/dbt/models/`
- **Terraform:** `/terraform/modules/glue/`
- **Monitoring:** `/terraform/modules/monitoring/`
- **Operations:** `/docs/OPERATIONS.md`
- **KPI Details:** `/docs/OCCUPANCY_KPI_DEPLOYMENT.md`
- **Test Optimization:** `/docs/SILVER_TEST_OPTIMIZATION.md`

---

**Last Updated:** 2026-02-10  
**Pipeline Version:** v2.0 (Optimized)  
**Maintainer:** Data Engineering Team
