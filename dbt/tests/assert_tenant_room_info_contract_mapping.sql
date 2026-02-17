-- Test: key moving_agreement_type codes map to expected contract labels.
-- Returns rows that violate mapping (should be zero rows).

SELECT
    ti.moving_id,
    m.moving_agreement_type,
    ti.contract_category
FROM {{ ref('tokyo_beta_tenant_room_info') }} ti
INNER JOIN {{ source('staging', 'movings') }} m
    ON ti.moving_id = m.id
WHERE (
        m.moving_agreement_type = 6
        AND ti.contract_category <> '定期契約'
    )
    OR (
        m.moving_agreement_type = 7
        AND ti.contract_category <> '一般（保証会社）'
    )
    OR (
        m.moving_agreement_type = 9
        AND ti.contract_category <> '一般2'
    )
