SELECT
  as_of_snapshot_date,
  calendar_today,
  CAST(lag_days AS SIGNED) AS lag_days_num0,
  gold_occupancy_max_updated_at,
  gold_occupancy_max_snapshot_date,
  generated_at,
  CAST(total_physical_rooms AS SIGNED) AS total_physical_rooms_num0
FROM gold.occupancy_kpi_meta;

