# Occupancy KPI Pipeline - Deployment Guide

## Overview

Incremental daily snapshot and KPI pipeline for occupancy tracking with future projections.

**Components:**
- `silver.tenant_room_snapshot_daily` - Incremental daily snapshot (dbt)
- `gold.occupancy_daily_metrics` - Daily KPI table with 90-day forward projections (Glue SQL)
- `scripts/backfill_occupancy_snapshots.py` - One-time backfill
- `glue/scripts/occupancy_kpi_updater.py` - Daily KPI updater (past + future)

**Key Features:**
- Historical metrics from actual snapshots (Oct 2025 - today)
- Future projections (today + 90 days) based on scheduled move-ins/move-outs
- Constant runtime (~2 minutes daily regardless of history size)

## Deployment Steps

### 1. Deploy dbt Model

Upload updated dbt project to S3:

```bash
cd dbt
aws s3 sync . s3://jram-gghouse/dbt-project/ \
  --exclude "target/*" \
  --exclude "dbt_packages/*" \
  --exclude "logs/*" \
  --profile gghouse
```

### 2. Create Glue Job for KPI Updater

Upload the KPI updater script:

```bash
aws s3 cp glue/scripts/occupancy_kpi_updater.py \
  s3://jram-gghouse/glue-scripts/occupancy_kpi_updater.py \
  --profile gghouse
```

Create Glue job (via AWS Console or Terraform):

```bash
# Option A: AWS CLI
aws glue create-job \
  --name tokyobeta-prod-occupancy-kpi-updater \
  --role arn:aws:iam::343881458651:role/tokyobeta-prod-glue-service-role \
  --command '{
    "Name": "glueetl",
    "ScriptLocation": "s3://jram-gghouse/glue-scripts/occupancy_kpi_updater.py",
    "PythonVersion": "3"
  }' \
  --default-arguments '{
    "--AURORA_ENDPOINT": "tokyobeta-prod-aurora-cluster-public.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com",
    "--AURORA_DATABASE": "tokyobeta",
    "--AURORA_SECRET_ARN": "arn:aws:secretsmanager:ap-northeast-1:343881458651:secret:tokyobeta/prod/aurora/credentials-tlWiUd",
    "--TARGET_DATE": "2026-02-10",
    "--LOOKBACK_DAYS": "3",
    "--FORWARD_DAYS": "90",
    "--job-bookmark-option": "job-bookmark-disable",
    "--TempDir": "s3://jram-gghouse/glue-temp/kpi/",
    "--enable-metrics": "true",
    "--enable-continuous-cloudwatch-log": "true"
  }' \
  --connections Connections=tokyobeta-prod-aurora-connection \
  --glue-version 4.0 \
  --worker-type G.1X \
  --number-of-workers 2 \
  --timeout 15 \
  --profile gghouse
```

### 3. Initial Backfill

Run one-time backfill for historical data:

```bash
# First, create the table via dbt (empty shell)
cd dbt
dbt run --select silver.tenant_room_snapshot_daily --target prod

# Then backfill historical data
cd ..
python3 scripts/backfill_occupancy_snapshots.py \
  --start-date 2025-10-01 \
  --end-date 2026-02-10

# Verify backfill
# Check row count: should be ~12k * number_of_days
```

After backfill completes, compute initial KPI values (historical + future projections):

```bash
aws glue start-job-run \
  --job-name tokyobeta-prod-occupancy-kpi-updater \
  --arguments='--TARGET_DATE=2026-02-10,--LOOKBACK_DAYS=120,--FORWARD_DAYS=90' \
  --profile gghouse
```

This will compute:
- Historical metrics: Oct 2025 - Feb 2026 (from actual snapshots)
- Future projections: Feb 2026 - May 2026 (90 days forward)

### 4. Daily Schedule

Modify existing EventBridge schedule or create new:

```bash
# Option A: Extend daily_etl schedule
# After daily_etl completes, trigger:
# 1. silver snapshot append
# 2. KPI updater

# Option B: Create separate schedule for occupancy pipeline
# 8:00 AM JST daily:
# 1. dbt snapshot append (via silver_transformer with --DBT_SELECT)
# 2. KPI updater
```

Example daily trigger sequence:

```bash
# Step 1: Append today's snapshot
aws glue start-job-run \
  --job-name tokyobeta-prod-silver-transformer \
  --arguments='--DBT_SELECT=silver.tenant_room_snapshot_daily' \
  --profile gghouse

# Step 2: Compute KPIs (3-day lookback + 90-day forward)
aws glue start-job-run \
  --job-name tokyobeta-prod-occupancy-kpi-updater \
  --arguments='--TARGET_DATE='$(date +%Y-%m-%d)',--LOOKBACK_DAYS=3,--FORWARD_DAYS=90' \
  --profile gghouse
```

## Operational Notes

### Daily Runtime

- **Snapshot append:** ~30 seconds (12k rows)
- **KPI computation:** ~10-15 minutes (~94 dates: 3 lookback + 90 forward + 1 today)
- **Total:** ~12-15 minutes (constant time regardless of history size)

**Note:** Runtime scales with `LOOKBACK_DAYS + FORWARD_DAYS`, not with total history.

### Future Projections

The KPI updater computes 90-day forward projections using today's snapshot:

**For future dates (> today):**
- **申込 (Applications):** Set to 0 (cannot predict)
- **新規入居者 (New move-ins):** Count status 4/5 pairs with `move_in_date = future_date`
- **新規退去者 (New move-outs):** Count pairs with `moveout_date = future_date`
- **Occupancy metrics:** Calculated normally (delta, start, end, rate)

**For past/today dates:**
- Uses actual snapshot data for that date
- **新規入居者:** Status 4/5/6/7/9 with `move_in_date = date`
- **新規退去者:** Uses `moveout_plans_date = date`

### Monitoring

Check KPI table freshness and date range:

```sql
-- Check date range covered
SELECT 
    MIN(snapshot_date) as earliest,
    MAX(snapshot_date) as latest,
    COUNT(*) as total_days,
    SUM(CASE WHEN snapshot_date > CURDATE() THEN 1 ELSE 0 END) as future_days
FROM gold.occupancy_daily_metrics;

-- Check recent updates
SELECT MAX(snapshot_date), MAX(updated_at)
FROM gold.occupancy_daily_metrics;

-- Sample future projections
SELECT snapshot_date, applications, new_moveins, new_moveouts, 
       period_end_rooms, occupancy_rate
FROM gold.occupancy_daily_metrics
WHERE snapshot_date > CURDATE()
ORDER BY snapshot_date
LIMIT 30;
```

Verify arithmetic invariants:

```sql
SELECT snapshot_date,
       period_end_rooms,
       period_start_rooms + occupancy_delta as calculated_end,
       period_end_rooms - (period_start_rooms + occupancy_delta) as delta_error
FROM gold.occupancy_daily_metrics
WHERE ABS(period_end_rooms - (period_start_rooms + occupancy_delta)) > 0
LIMIT 10;
```

### Monthly Maintenance

Archive rows older than 12 months:

```bash
# TODO: Create scripts/archive_old_snapshots.py
# 1. Export old rows to S3 Parquet
# 2. DELETE FROM silver.tenant_room_snapshot_daily WHERE snapshot_date < DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
# 3. OPTIMIZE TABLE / ANALYZE TABLE
```

## Troubleshooting

### Backfill fails with "Table does not exist"

Run dbt first to create the table:

```bash
cd dbt
dbt run --select silver.tenant_room_snapshot_daily --target prod --full-refresh
```

### KPI values look wrong

Re-run KPI updater with larger lookback window and/or extend forward projections:

```bash
# Recompute last 30 days + next 90 days
aws glue start-job-run \
  --job-name tokyobeta-prod-occupancy-kpi-updater \
  --arguments='--TARGET_DATE=2026-02-10,--LOOKBACK_DAYS=30,--FORWARD_DAYS=90' \
  --profile gghouse
```

### Future projections are flat/zero

Check that today's snapshot has scheduled move-ins/move-outs:

```sql
-- Check scheduled move-ins in today's snapshot
SELECT 
    DATE(move_in_date) as scheduled_date,
    COUNT(DISTINCT CONCAT(tenant_id, '-', apartment_id, '-', room_id)) as count
FROM silver.tenant_room_snapshot_daily
WHERE snapshot_date = CURDATE()
  AND move_in_date > CURDATE()
  AND management_status_code IN (4, 5)
GROUP BY DATE(move_in_date)
ORDER BY scheduled_date
LIMIT 30;

-- Check scheduled move-outs
SELECT 
    DATE(moveout_date) as scheduled_date,
    COUNT(DISTINCT CONCAT(tenant_id, '-', apartment_id, '-', room_id)) as count
FROM silver.tenant_room_snapshot_daily
WHERE snapshot_date = CURDATE()
  AND moveout_date > CURDATE()
GROUP BY DATE(moveout_date)
ORDER BY scheduled_date
LIMIT 30;
```

### Snapshot has duplicate rows for same date

Check unique key constraint. If violated, run:

```sql
-- Find duplicates
SELECT snapshot_date, tenant_id, apartment_id, room_id, COUNT(*)
FROM silver.tenant_room_snapshot_daily
GROUP BY snapshot_date, tenant_id, apartment_id, room_id
HAVING COUNT(*) > 1;

-- If found, rebuild from scratch
TRUNCATE TABLE silver.tenant_room_snapshot_daily;
-- Then re-run backfill
```

## Testing

Run dbt tests:

```bash
cd dbt
dbt test --select silver.tenant_room_snapshot_daily --target prod
dbt test --select occupancy_daily_metrics --target prod
```

## Rollback

If issues arise:

1. KPI table is small and can be rebuilt quickly from snapshots.
2. Snapshot table can be rebuilt from `staging.tenant_daily_snapshots` using backfill script.
3. No impact on existing `silver.tokyo_beta_tenant_room_info` or other gold tables.
