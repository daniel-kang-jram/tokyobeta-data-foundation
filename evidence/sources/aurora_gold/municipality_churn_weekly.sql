SELECT *
FROM gold.municipality_churn_weekly
WHERE week_start >= DATE_SUB(CURDATE(), INTERVAL ${lookback_days} DAY)
ORDER BY week_start, net_change DESC;

