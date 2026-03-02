WITH data_max AS (
  SELECT
    max(CASE WHEN period_grain = 'weekly' THEN period_start END) AS max_weekly_period_start,
    max(CASE WHEN period_grain = 'monthly' THEN period_start END) AS max_monthly_period_start
  FROM gold.funnel_application_to_movein_segment_share
),
anchored AS (
  SELECT
    s.period_grain,
    s.period_start,
    s.tenant_type,
    s.segment_type,
    s.segment_value,
    s.application_count,
    s.movein_count,
    s.application_share,
    s.movein_share,
    s.application_to_movein_rate,
    s.segment_rank,
    CASE
      WHEN s.period_grain = 'weekly' THEN date_sub(m.max_weekly_period_start, interval 365 day)
      WHEN s.period_grain = 'monthly' THEN date_sub(m.max_monthly_period_start, interval 365 day)
    END AS window_start,
    CASE
      WHEN s.period_grain = 'weekly' THEN m.max_weekly_period_start
      WHEN s.period_grain = 'monthly' THEN m.max_monthly_period_start
    END AS data_max_period_start,
    s.created_at,
    s.updated_at
  FROM gold.funnel_application_to_movein_segment_share s
  CROSS JOIN data_max m
)
SELECT
  period_grain,
  period_start,
  tenant_type,
  segment_type,
  segment_value,
  application_count,
  movein_count,
  application_share,
  movein_share,
  application_to_movein_rate,
  segment_rank,
  window_start,
  data_max_period_start,
  created_at,
  updated_at
FROM anchored
WHERE period_grain NOT IN ('weekly', 'monthly')
   OR period_start >= window_start;
