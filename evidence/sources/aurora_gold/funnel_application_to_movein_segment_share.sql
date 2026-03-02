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
  created_at,
  updated_at
from gold.funnel_application_to_movein_segment_share;
