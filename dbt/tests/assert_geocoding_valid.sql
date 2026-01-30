-- Test: Ensure all geocoded records have valid Tokyo coordinates
-- Tokyo bounds: approximately 35.5-35.9°N, 139.5-140.0°E

SELECT
    'new_contracts' as table_name,
    contract_id,
    latitude,
    longitude
FROM {{ ref('new_contracts') }}
WHERE latitude NOT BETWEEN 35.5 AND 35.9
   OR longitude NOT BETWEEN 139.5 AND 140.0

UNION ALL

SELECT
    'moveouts' as table_name,
    contract_id,
    latitude,
    longitude
FROM {{ ref('moveouts') }}
WHERE latitude NOT BETWEEN 35.5 AND 35.9
   OR longitude NOT BETWEEN 139.5 AND 140.0

UNION ALL

SELECT
    'moveout_notices' as table_name,
    contract_id,
    latitude,
    longitude
FROM {{ ref('moveout_notices') }}
WHERE latitude NOT BETWEEN 35.5 AND 35.9
   OR longitude NOT BETWEEN 139.5 AND 140.0
