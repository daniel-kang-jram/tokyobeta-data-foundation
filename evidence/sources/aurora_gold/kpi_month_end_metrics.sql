SELECT
  as_of_date,
  is_month_end,
  total_physical_rooms,
  occupancy_room_count_0000,
  occupancy_room_count_eod,
  same_day_moveins,
  same_day_moveouts,
  occupancy_rate,
  rent_jpy,
  revpar_jpy,
  recpar_cash_jpy,
  cash_realization_rate,
  same_day_moveout_policy,
  kpi_definition_version,
  generated_at
from gold.kpi_month_end_metrics;
