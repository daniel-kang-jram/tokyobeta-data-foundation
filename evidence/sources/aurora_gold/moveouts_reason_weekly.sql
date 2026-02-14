SELECT *
FROM gold.moveouts_reason_weekly
WHERE week_start >= DATE_SUB(CURDATE(), INTERVAL ${lookback_days} DAY)
ORDER BY week_start, moveout_count DESC;

