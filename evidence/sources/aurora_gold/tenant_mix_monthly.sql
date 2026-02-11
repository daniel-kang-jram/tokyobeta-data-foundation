SELECT
  month_start,
  event_type,
  tenant_type,
  nationality,
  SUM(event_count) AS event_count
FROM (
  SELECT
    DATE_FORMAT(contract_date, '%Y-%m-01') AS month_start,
    'movein' AS event_type,
    tenant_type,
    COALESCE(nationality, 'Unknown') AS nationality,
    COUNT(*) AS event_count
  FROM gold.new_contracts
  WHERE contract_date >= DATE_SUB(CURDATE(), INTERVAL ${lookback_days} DAY)
  GROUP BY
    DATE_FORMAT(contract_date, '%Y-%m-01'),
    tenant_type,
    COALESCE(nationality, 'Unknown')

  UNION ALL

  SELECT
    DATE_FORMAT(moveout_date, '%Y-%m-01') AS month_start,
    'moveout' AS event_type,
    tenant_type,
    COALESCE(nationality, 'Unknown') AS nationality,
    COUNT(*) AS event_count
  FROM gold.moveouts
  WHERE moveout_date >= DATE_SUB(CURDATE(), INTERVAL ${lookback_days} DAY)
  GROUP BY
    DATE_FORMAT(moveout_date, '%Y-%m-01'),
    tenant_type,
    COALESCE(nationality, 'Unknown')
) base
GROUP BY month_start, event_type, tenant_type, nationality
ORDER BY month_start, event_type, event_count DESC;
