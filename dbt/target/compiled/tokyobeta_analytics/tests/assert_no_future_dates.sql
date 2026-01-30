-- Test: Ensure no activity dates are in the future
-- This could indicate data quality issues or incorrect date parsing

SELECT
    'daily_activity_summary' as table_name,
    activity_date,
    COUNT(*) as invalid_count
FROM `tokyobeta_analytics`.`daily_activity_summary`
WHERE activity_date > CURRENT_DATE
GROUP BY activity_date

UNION ALL

SELECT
    'new_contracts' as table_name,
    contract_date as activity_date,
    COUNT(*) as invalid_count
FROM `tokyobeta_analytics`.`new_contracts`
WHERE contract_date > CURRENT_DATE
GROUP BY contract_date

UNION ALL

SELECT
    'moveouts' as table_name,
    moveout_date as activity_date,
    COUNT(*) as invalid_count
FROM `tokyobeta_analytics`.`moveouts`
WHERE moveout_date > CURRENT_DATE
GROUP BY moveout_date