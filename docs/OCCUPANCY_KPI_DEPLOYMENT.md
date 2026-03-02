# Occupancy KPI Pipeline - Deployment Guide

**Last Updated:** March 1, 2026

## Overview

**INTEGRATED ARCHITECTURE (as of Feb 2026):**

The occupancy KPI pipeline is now **fully integrated into the `gold_transformer` Glue job**. There is NO separate `occupancy_kpi_updater` job.

**Components:**
- `silver.tenant_room_snapshot_daily` - Incremental daily snapshot (dbt)
- `gold.occupancy_daily_metrics` - Daily KPI table with 90-day forward projections (SQL in gold_transformer.py)
- `scripts/backfill_occupancy_snapshots.py` - One-time backfill
- `glue/scripts/gold_transformer.py` - Unified gold job (dbt models + occupancy KPIs + tests)

**Key Features:**
- Historical metrics from actual snapshots (Oct 2025 - today)
- Future projections (today + 90 days) based on scheduled move-ins/move-outs
- **Single job execution**: dbt gold models → occupancy KPIs → dbt tests
- Runtime: ~10 minutes (includes all gold models + KPIs + tests)

## Canonical KPI Contract (March 2026 Refresh)

The dashboard KPI cards now read from `gold.kpi_month_end_metrics` and metadata from
`gold.kpi_reference_trace`.

### KPI Definition Version Ownership
- `gold.kpi_month_end_metrics` is the source-of-truth owner of KPI formulas and emits
  `kpi_definition_version` as the canonical version token.
- `gold.kpi_reference_trace` carries the same `kpi_definition_version` for dashboard
  metadata/trace checks (freshness and time-basis visibility).
- Deployment verification must confirm version alignment across both models before release
  sign-off:

```sql
SELECT
    metrics.kpi_definition_version AS metrics_version,
    trace.kpi_definition_version AS trace_version,
    CASE
        WHEN metrics.kpi_definition_version = trace.kpi_definition_version
            THEN 'aligned'
        ELSE 'mismatch'
    END AS deployment_verification
FROM (
    SELECT kpi_definition_version
    FROM gold.kpi_month_end_metrics
    ORDER BY as_of_date DESC
    LIMIT 1
) metrics
CROSS JOIN (
    SELECT kpi_definition_version
    FROM gold.kpi_reference_trace
    ORDER BY trace_generated_at DESC
    LIMIT 1
) trace;
```

### Same-Day Move-Out Policy
- Policy token: `count_moveout_room_at_0000_exclude_same_day_moveins`
- 00:00 occupancy (`occupancy_room_count_0000`) excludes same-day move-ins.
- Same-day move-out rooms remain counted at 00:00 and are removed through daily move-out flow.
- End-of-day identity is enforced in dbt tests:
  `occupancy_room_count_eod = occupancy_room_count_0000 + same_day_moveins - same_day_moveouts`.

### Benchmark Interpretation Notes
- Benchmark checks are automated via:
  - `dbt/tests/assert_kpi_reference_feb2026.sql`
  - `dbt/tests/assert_occupancy_same_day_moveout_policy.sql`
- Feb 2026 references are treated as guardrails with explicit tolerances:
  - 2026-01-31 occupancy rate reference `70.7%`
  - 2026-01 KPI references `RENT 56,195 / RevPAR 39,757 / RecPAR(Cash) 37,826`
  - 2026-02-01 00:00 occupancy rooms reference `11,271`
- Tolerance-based assertions are intentional to keep tests deterministic across
  upstream snapshot revisions while still alerting on meaningful regressions.

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

### 2. Update Gold Transformer Job

**The KPI logic is now integrated into `gold_transformer.py`.** No separate job needed.

Upload the updated gold_transformer script:

```bash
aws s3 cp glue/scripts/gold_transformer.py \
  s3://jram-gghouse/glue-scripts/gold_transformer.py \
  --profile gghouse
```

Update Glue job parameters (via AWS Console or Terraform):

```bash
# Option A: AWS CLI (update existing job)
aws glue update-job \
  --job-name tokyobeta-prod-gold-transformer \
  --job-update '{
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
# KPI computation now integrated into gold_transformer
aws glue start-job-run \
  --job-name tokyobeta-prod-gold-transformer \
  --arguments='{"--LOOKBACK_DAYS":"120","--FORWARD_DAYS":"90"}' \
  --profile gghouse
```

This will:
1. Build all dbt gold models
2. Compute KPIs for Oct 2025 - May 2026 (historical + 90-day projections)
3. Run dbt gold tests

### 4. Daily Schedule

**SIMPLIFIED (Integrated Architecture):**

```bash
# Single daily trigger: gold_transformer (includes KPI computation)
aws glue start-job-run \
  --job-name tokyobeta-prod-gold-transformer \
  --profile gghouse

# Default arguments (set in job definition):
# --LOOKBACK_DAYS=3
# --FORWARD_DAYS=90
```

**EventBridge schedule:**
- Trigger `tokyobeta-prod-gold-transformer` after staging/silver jobs complete
- Frequency: Daily at 8:00 AM JST (after staging is fresh)
- No need for separate KPI job or orchestration

## Operational Notes

### Daily Runtime

**Integrated `gold_transformer` job:**
- **dbt gold models:** ~10 seconds (6 models)
- **KPI computation:** ~8 minutes (~94 dates: 3 lookback + 90 forward + 1 today)
- **dbt tests:** ~1 minute
- **Total:** ~10 minutes (constant time regardless of history size)

**Note:** Runtime scales with `LOOKBACK_DAYS + FORWARD_DAYS`, not with total history.

### Future Projections

The `gold_transformer` job computes 90-day forward projections using today's snapshot:

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
