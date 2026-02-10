-- Temporary analysis query to count active tenants
-- This will be used for rent roll reconciliation

-- Active tenants from staging.tenants
WITH active_from_staging AS (
    SELECT COUNT(DISTINCT t.id) as count
    FROM {{ source('staging', 'tenants') }} t
    INNER JOIN {{ ref('code_tenant_status') }} s ON t.status = s.code
    WHERE s.is_active_lease = 1
),

-- Active tenants from movings (no moveout)
-- Use tenant.moving_id as the primary link to get CURRENT room assignment
active_from_movings AS (
    SELECT COUNT(DISTINCT t.id) as count
    FROM {{ source('staging', 'tenants') }} t
    INNER JOIN {{ source('staging', 'movings') }} m 
        ON t.moving_id = m.id  -- Use tenant.moving_id for current assignment
    WHERE m.movein_date IS NOT NULL
      AND (m.moveout_date IS NULL OR m.moveout_date > CURRENT_DATE)
),

-- Status breakdown
status_breakdown AS (
    SELECT 
        t.status,
        s.label_ja,
        s.label_en,
        s.is_active_lease,
        COUNT(*) as count
    FROM {{ source('staging', 'tenants') }} t
    LEFT JOIN {{ ref('code_tenant_status') }} s ON t.status = s.code
    GROUP BY t.status, s.label_ja, s.label_en, s.is_active_lease
),

-- Contract type breakdown for active tenants
contract_type_breakdown AS (
    SELECT 
        CASE 
            WHEN t.contract_type IN (2, 3) THEN 'corporate'
            WHEN t.contract_type IN (1, 6, 7, 9) THEN 'individual'
            ELSE 'unknown'
        END as tenant_type,
        COUNT(*) as count
    FROM {{ source('staging', 'tenants') }} t
    INNER JOIN {{ ref('code_tenant_status') }} s ON t.status = s.code
    WHERE s.is_active_lease = 1
    GROUP BY tenant_type
)

-- Output summary
SELECT 
    'Active Tenants (is_active_lease)' as metric,
    (SELECT count FROM active_from_staging) as value
UNION ALL
SELECT 
    'Active Tenants (no moveout)',
    (SELECT count FROM active_from_movings)
UNION ALL
SELECT 
    'Corporate Active Tenants',
    COALESCE((SELECT count FROM contract_type_breakdown WHERE tenant_type = 'corporate'), 0)
UNION ALL
SELECT 
    'Individual Active Tenants',
    COALESCE((SELECT count FROM contract_type_breakdown WHERE tenant_type = 'individual'), 0)
UNION ALL
SELECT 
    'Unknown Active Tenants',
    COALESCE((SELECT count FROM contract_type_breakdown WHERE tenant_type = 'unknown'), 0)
