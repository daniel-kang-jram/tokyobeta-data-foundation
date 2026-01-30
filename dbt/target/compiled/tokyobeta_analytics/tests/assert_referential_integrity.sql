-- Test: Check for orphaned tenant_id references in contracts
-- Should be 0 rows if all tenants exist

SELECT 
    nc.contract_id,
    nc.tenant_id,
    'new_contracts' as source_table
FROM `tokyobeta_analytics`.`new_contracts` nc
LEFT JOIN `staging`.`tenants` t
    ON nc.tenant_id = t.id
WHERE t.id IS NULL

UNION ALL

SELECT
    mo.contract_id,
    mo.tenant_id,
    'moveouts' as source_table
FROM `tokyobeta_analytics`.`moveouts` mo
LEFT JOIN `staging`.`tenants` t
    ON mo.tenant_id = t.id
WHERE t.id IS NULL