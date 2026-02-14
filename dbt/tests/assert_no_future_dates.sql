-- Test: Ensure contract / move-out dates are not in the future.
-- Note: gold.occupancy_daily_metrics intentionally contains future projection dates,
-- so it is excluded from this check.

SELECT
    'new_contracts' as table_name,
    contract_date as activity_date,
    COUNT(*) as invalid_count
FROM {{ ref('new_contracts') }}
WHERE contract_date > CURRENT_DATE
GROUP BY contract_date

UNION ALL

SELECT
    'moveouts' as table_name,
    moveout_date as activity_date,
    COUNT(*) as invalid_count
FROM {{ ref('moveouts') }}
WHERE moveout_date > CURRENT_DATE
GROUP BY moveout_date
