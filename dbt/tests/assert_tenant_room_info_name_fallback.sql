-- Test: tenant_name should be populated when full_name or first/last name exists.
-- Returns rows that violate expectation (should be zero rows).

SELECT
    ti.moving_id,
    t.id AS tenant_id,
    t.full_name,
    t.last_name,
    t.first_name,
    ti.tenant_name
FROM {{ ref('tokyo_beta_tenant_room_info') }} ti
INNER JOIN {{ source('staging', 'movings') }} m
    ON ti.moving_id = m.id
INNER JOIN {{ source('staging', 'tenants') }} t
    ON t.moving_id = m.id
WHERE COALESCE(
        NULLIF(TRIM(t.full_name), ''),
        NULLIF(CONCAT_WS(' ', NULLIF(TRIM(t.last_name), ''), NULLIF(TRIM(t.first_name), '')), '')
    ) IS NOT NULL
  AND COALESCE(NULLIF(TRIM(ti.tenant_name), ''), '') = ''
