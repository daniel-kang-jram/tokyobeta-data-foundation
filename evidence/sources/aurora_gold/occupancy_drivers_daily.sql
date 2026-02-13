SELECT
  snapshot_date,
  applications,
  new_moveins,
  new_moveouts,
  occupancy_delta,

  -- Force full integer display in Evidence (no k/m abbreviations)
  CAST(period_start_rooms AS SIGNED) AS period_start_rooms_num0,
  CAST(period_end_rooms AS SIGNED) AS period_end_rooms_num0,

  -- Evidence treats *_pct columns as percentages (multiplies by 100 for display)
  -- so keep this as a 0-1 fraction.
  CAST(occupancy_rate AS DECIMAL(10,6)) AS occupancy_rate_pct
FROM gold.occupancy_daily_metrics
WHERE snapshot_date >= DATE_SUB(CURDATE(), INTERVAL ${lookback_days} DAY)
ORDER BY snapshot_date;
