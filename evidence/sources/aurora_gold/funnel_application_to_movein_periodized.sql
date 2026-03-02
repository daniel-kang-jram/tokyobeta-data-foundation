WITH data_max AS (
  SELECT
    max(CASE WHEN period_grain = 'daily' THEN period_start END) AS max_daily_period_start,
    max(CASE WHEN period_grain = 'weekly' THEN period_start END) AS max_weekly_period_start,
    max(CASE WHEN period_grain = 'monthly' THEN period_start END) AS max_monthly_period_start
  FROM gold.funnel_application_to_movein_periodized
),
anchored AS (
  SELECT
    p.period_grain,
    p.period_start,
    p.municipality,
    p.nationality,
    p.tenant_type,
    p.application_count,
    p.movein_count,
    p.application_to_movein_rate,
    CASE
      WHEN p.period_grain = 'daily' THEN date_sub(m.max_daily_period_start, interval 90 day)
      WHEN p.period_grain = 'weekly' THEN date_sub(m.max_weekly_period_start, interval 365 day)
      WHEN p.period_grain = 'monthly' THEN date_sub(m.max_monthly_period_start, interval 730 day)
    END AS window_start,
    CASE
      WHEN p.period_grain = 'daily' THEN m.max_daily_period_start
      WHEN p.period_grain = 'weekly' THEN m.max_weekly_period_start
      WHEN p.period_grain = 'monthly' THEN m.max_monthly_period_start
    END AS data_max_period_start,
    p.created_at,
    p.updated_at
  FROM gold.funnel_application_to_movein_periodized p
  CROSS JOIN data_max m
)
SELECT
  period_grain,
  period_start,
  municipality,
  nationality,
  tenant_type,
  application_count,
  movein_count,
  application_to_movein_rate,
  window_start,
  data_max_period_start,
  created_at,
  updated_at
FROM anchored
WHERE period_start >= window_start;
