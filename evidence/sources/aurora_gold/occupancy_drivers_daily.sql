SELECT
  odm.snapshot_date,
  meta.as_of_snapshot_date,
  CASE
    WHEN odm.snapshot_date > meta.as_of_snapshot_date THEN 'projection'
    ELSE 'fact'
  END AS phase,

  odm.applications,
  odm.new_moveins,
  odm.new_moveouts,
  odm.occupancy_delta,

  -- Force full integer display in Evidence (no k/m abbreviations)
  CAST(odm.period_start_rooms AS SIGNED) AS period_start_rooms_num0,
  CAST(odm.period_end_rooms AS SIGNED) AS period_end_rooms_num0,

  -- Evidence treats *_pct columns as percentages (multiplies by 100 for display)
  -- so keep this as a 0-1 fraction.
  CAST(odm.occupancy_rate AS DECIMAL(10,6)) AS occupancy_rate_pct
FROM gold.occupancy_daily_metrics odm
CROSS JOIN gold.occupancy_kpi_meta meta
WHERE odm.snapshot_date >= DATE_SUB(CURDATE(), INTERVAL ${lookback_days} DAY)
ORDER BY odm.snapshot_date;
