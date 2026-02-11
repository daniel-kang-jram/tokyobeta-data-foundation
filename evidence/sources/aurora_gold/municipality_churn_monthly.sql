SELECT
  month_start,
  municipality,
  SUM(movein_count) AS movein_count,
  SUM(moveout_count) AS moveout_count,
  SUM(movein_count) - SUM(moveout_count) AS net_change
FROM (
  SELECT
    DATE_FORMAT(contract_date, '%Y-%m-01') AS month_start,
    COALESCE(municipality, 'Unknown') AS municipality,
    COUNT(*) AS movein_count,
    0 AS moveout_count
  FROM gold.new_contracts
  WHERE contract_date >= DATE_SUB(CURDATE(), INTERVAL ${lookback_days} DAY)
  GROUP BY DATE_FORMAT(contract_date, '%Y-%m-01'), COALESCE(municipality, 'Unknown')

  UNION ALL

  SELECT
    DATE_FORMAT(moveout_date, '%Y-%m-01') AS month_start,
    COALESCE(municipality, 'Unknown') AS municipality,
    0 AS movein_count,
    COUNT(*) AS moveout_count
  FROM gold.moveouts
  WHERE moveout_date >= DATE_SUB(CURDATE(), INTERVAL ${lookback_days} DAY)
  GROUP BY DATE_FORMAT(moveout_date, '%Y-%m-01'), COALESCE(municipality, 'Unknown')
) base
GROUP BY month_start, municipality
ORDER BY month_start, net_change DESC;
