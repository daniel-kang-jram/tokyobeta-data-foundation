SELECT
  period_grain,
  period_start,
  municipality,
  nationality,
  tenant_type,
  application_count,
  movein_count,
  application_to_movein_rate,
  created_at,
  updated_at
from gold.funnel_application_to_movein_periodized;
