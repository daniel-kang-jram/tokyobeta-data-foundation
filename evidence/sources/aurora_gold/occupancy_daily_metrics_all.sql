-- Note: gold.occupancy_daily_metrics currently contains future snapshot_date rows.
-- For future projections, period_start_rooms / period_end_rooms must chain from the
-- previous day's KPI end-room count (silver snapshots don't exist for future dates).
--
-- We compute "fixed" projection fields here so Evidence charts don't collapse to 0.
WITH meta AS (
  SELECT
    as_of_snapshot_date,
    total_physical_rooms
  FROM gold.occupancy_kpi_meta
),
base AS (
  SELECT
    odm.snapshot_date,
    meta.as_of_snapshot_date,
    meta.total_physical_rooms,

    odm.applications,
    odm.new_moveins,
    odm.new_moveouts,
    COALESCE(odm.occupancy_delta, 0) AS occupancy_delta,

    odm.period_start_rooms,
    odm.period_end_rooms,
    odm.updated_at
  FROM gold.occupancy_daily_metrics odm
  CROSS JOIN meta
),
as_of AS (
  SELECT
    period_end_rooms AS as_of_period_end_rooms
  FROM base
  WHERE snapshot_date <= as_of_snapshot_date
  ORDER BY snapshot_date DESC
  LIMIT 1
),
with_fixed_end AS (
  SELECT
    base.*,
    CASE
      WHEN snapshot_date <= as_of_snapshot_date THEN period_end_rooms
      ELSE (SELECT as_of_period_end_rooms FROM as_of)
        + SUM(CASE WHEN snapshot_date > as_of_snapshot_date THEN occupancy_delta ELSE 0 END)
          OVER (ORDER BY snapshot_date)
    END AS period_end_rooms_fixed
  FROM base
),
with_fixed_start AS (
  SELECT
    with_fixed_end.*,
    CASE
      WHEN snapshot_date <= as_of_snapshot_date THEN period_start_rooms
      ELSE LAG(period_end_rooms_fixed) OVER (ORDER BY snapshot_date)
    END AS period_start_rooms_fixed
  FROM with_fixed_end
)
SELECT
  snapshot_date,
  as_of_snapshot_date,
  CASE
    WHEN snapshot_date > as_of_snapshot_date THEN 'projection'
    ELSE 'fact'
  END AS phase,

  applications,
  new_moveins,
  new_moveouts,
  occupancy_delta,

  CAST(period_start_rooms_fixed AS SIGNED) AS period_start_rooms_num0,
  CAST(period_end_rooms_fixed AS SIGNED) AS period_end_rooms_num0,
  CAST(period_end_rooms_fixed / total_physical_rooms AS DECIMAL(10,6)) AS occupancy_rate_pct,

  updated_at
FROM with_fixed_start
ORDER BY snapshot_date DESC;
