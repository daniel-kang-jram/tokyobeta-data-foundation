SELECT *
FROM gold.move_events_weekly
WHERE week_start >= DATE_SUB(CURDATE(), INTERVAL ${lookback_days} DAY)
ORDER BY week_start, event_type, tenant_type, rent_range_order, age_group;

