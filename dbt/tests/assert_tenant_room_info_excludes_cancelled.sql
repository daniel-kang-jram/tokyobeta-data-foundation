-- Test: cancelled contracts must not appear in tenant room info.
-- Returns rows that violate expectation (should be zero rows).

SELECT
    ti.moving_id,
    m.cancel_flag
FROM {{ ref('tokyo_beta_tenant_room_info') }} ti
INNER JOIN {{ source('staging', 'movings') }} m
    ON ti.moving_id = m.id
WHERE COALESCE(m.cancel_flag, 0) = 1
