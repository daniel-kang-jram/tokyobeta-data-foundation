# Occupancy KPI Pipeline - Deployment Guide

## Overview

New incremental daily snapshot and KPI pipeline for occupancy tracking.

**Components:**
- `silver.tenant_room_snapshot_daily` - Incremental daily snapshot (dbt)
- `gold.occupancy_daily_metrics` - Daily KPI table (Glue SQL)
- `scripts/backfill_occupancy_snapshots.py` - One-time backfill
- `glue/scripts/occupancy_kpi_updater.py` - Daily KPI updater

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

After backfill completes, compute initial KPI values:

```bash
aws glue start-job-run \
  --job-name tokyobeta-prod-occupancy-kpi-updater \
  --arguments='--TARGET_DATE=2026-02-10,--LOOKBACK_DAYS=120' \
  --profile gghouse
```

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

# Step 2: Compute KPIs (today + 3-day lookback)
aws glue start-job-run \
  --job-name tokyobeta-prod-occupancy-kpi-updater \
  --arguments='--TARGET_DATE='$(date +%Y-%m-%d)',--LOOKBACK_DAYS=3' \
  --profile gghouse
```

## Operational Notes

### Daily Runtime

- **Snapshot append:** ~30 seconds (12k rows)
- **KPI computation:** ~10-30 seconds (4 date rows)
- **Total:** Under 2 minutes (constant time)

### Monitoring

Check KPI table freshness:

```sql
SELECT MAX(snapshot_date), MAX(updated_at)
FROM gold.occupancy_daily_metrics;
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

Re-run KPI updater with larger lookback window:

```bash
aws glue start-job-run \
  --job-name tokyobeta-prod-occupancy-kpi-updater \
  --arguments='--TARGET_DATE=2026-02-10,--LOOKBACK_DAYS=30' \
  --profile gghouse
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
