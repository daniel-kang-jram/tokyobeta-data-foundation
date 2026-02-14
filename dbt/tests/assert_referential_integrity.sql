-- Test: Check referential integrity for contract-based gold tables.
-- gold.new_contracts / gold.moveouts use contract_id (= staging.movings.id) as their key,
-- so validate:
-- 1) contract_id exists in staging.movings
-- 2) staging.movings.tenant_id exists in staging.tenants

SELECT
    nc.contract_id,
    'new_contracts_missing_moving' as failure_reason
FROM {{ ref('new_contracts') }} nc
LEFT JOIN {{ source('staging', 'movings') }} m
    ON nc.contract_id = m.id
WHERE m.id IS NULL

UNION ALL

SELECT
    nc.contract_id,
    'new_contracts_missing_tenant' as failure_reason
FROM {{ ref('new_contracts') }} nc
INNER JOIN {{ source('staging', 'movings') }} m
    ON nc.contract_id = m.id
LEFT JOIN {{ source('staging', 'tenants') }} t
    ON m.tenant_id = t.id
WHERE t.id IS NULL

UNION ALL

SELECT
    mo.contract_id,
    'moveouts_missing_moving' as failure_reason
FROM {{ ref('moveouts') }} mo
LEFT JOIN {{ source('staging', 'movings') }} m
    ON mo.contract_id = m.id
WHERE m.id IS NULL

UNION ALL

SELECT
    mo.contract_id,
    'moveouts_missing_tenant' as failure_reason
FROM {{ ref('moveouts') }} mo
INNER JOIN {{ source('staging', 'movings') }} m
    ON mo.contract_id = m.id
LEFT JOIN {{ source('staging', 'tenants') }} t
    ON m.tenant_id = t.id
WHERE t.id IS NULL
