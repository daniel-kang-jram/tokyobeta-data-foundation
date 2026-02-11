SELECT
  DATE_FORMAT(contract_date, '%Y-%m-01') AS month_start,
  tenant_type,
  COALESCE(nationality, 'Unknown') AS nationality,
  COALESCE(municipality, 'Unknown') AS municipality,
  COALESCE(apartment_name, 'Unknown') AS apartment_name,
  COUNT(*) AS movein_count
FROM gold.new_contracts
WHERE contract_date >= DATE_SUB(CURDATE(), INTERVAL ${lookback_days} DAY)
GROUP BY
  DATE_FORMAT(contract_date, '%Y-%m-01'),
  tenant_type,
  COALESCE(nationality, 'Unknown'),
  COALESCE(municipality, 'Unknown'),
  COALESCE(apartment_name, 'Unknown')
ORDER BY month_start, tenant_type, nationality;
