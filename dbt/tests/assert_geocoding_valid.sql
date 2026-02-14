-- Test: Ensure all geocoded records have valid coordinates.
-- Bounds match silver.stg_apartments validation (broad Kanto/Tokyo area).

SELECT
    'new_contracts' as table_name,
    contract_id,
    latitude,
    longitude
FROM {{ ref('new_contracts') }}
WHERE latitude NOT BETWEEN 35.0 AND 36.0
   OR longitude NOT BETWEEN 139.0 AND 140.5

UNION ALL

SELECT
    'moveouts' as table_name,
    contract_id,
    latitude,
    longitude
FROM {{ ref('moveouts') }}
WHERE latitude NOT BETWEEN 35.0 AND 36.0
   OR longitude NOT BETWEEN 139.0 AND 140.5

UNION ALL

SELECT
    'moveout_notices' as table_name,
    contract_id,
    latitude,
    longitude
FROM {{ ref('moveout_notices') }}
WHERE latitude NOT BETWEEN 35.0 AND 36.0
   OR longitude NOT BETWEEN 139.0 AND 140.5
