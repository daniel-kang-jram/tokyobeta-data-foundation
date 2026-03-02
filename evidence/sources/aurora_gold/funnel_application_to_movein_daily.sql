WITH data_max AS (
  SELECT max(activity_date) AS max_activity_date
  FROM gold.funnel_application_to_movein_daily
),
anchored AS (
  SELECT
    d.activity_date,
    d.municipality,
    d.nationality,
    d.tenant_type,
    d.application_count,
    d.movein_count,
    d.application_to_movein_rate,
    date_sub(m.max_activity_date, interval 180 day) AS window_start_180d,
    m.max_activity_date AS data_max_activity_date,
    d.created_at,
    d.updated_at
  FROM gold.funnel_application_to_movein_daily d
  CROSS JOIN data_max m
)
SELECT
  activity_date,
  municipality,
  nationality,
  tenant_type,
  application_count,
  movein_count,
  application_to_movein_rate,
  window_start_180d,
  data_max_activity_date,
  created_at,
  updated_at
FROM anchored
WHERE activity_date >= window_start_180d;
