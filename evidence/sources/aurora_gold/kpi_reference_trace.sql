SELECT
  as_of_date,
  kpi_definition_version,
  same_day_moveout_policy,
  kpi_model_generated_at,
  occupancy_meta_as_of_snapshot_date,
  calendar_today,
  freshness_lag_days,
  silver_snapshot_max_date,
  silver_snapshot_max_updated_at,
  gold_occupancy_max_snapshot_date,
  gold_occupancy_max_updated_at,
  trace_generated_at
from gold.kpi_reference_trace;
