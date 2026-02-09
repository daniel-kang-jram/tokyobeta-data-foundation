{{
    config(
        materialized='table'
    )
}}

/*
Tenant Status Transitions - Analysis Ready
Provides business-friendly view of tenant status changes over time.

Purpose:
- Identify when tenants change status (e.g., active → inactive)
- Calculate duration in each status
- Track payment status transitions
- Support churn/retention analysis
- Enable status transition flow analysis

Usage Examples:
- Find all tenants who became unpaid in last 30 days
- Calculate average time from inquiry to contract
- Identify seasonal patterns in status changes
- Track renewal acceptance rates
*/

WITH history AS (
    SELECT
        tenant_id,
        full_name,
        status,
        contract_type,
        valid_from,
        valid_to,
        is_current,
        dbt_updated_at
    FROM {{ ref('tenant_status_history') }}
),

-- Calculate previous status for each record (for transition analysis)
with_previous_status AS (
    SELECT
        h.*,
        LAG(status) OVER (PARTITION BY tenant_id ORDER BY valid_from) AS previous_status,
        LAG(valid_from) OVER (PARTITION BY tenant_id ORDER BY valid_from) AS previous_change_date
    FROM history h
),

-- Calculate duration in current status
with_duration AS (
    SELECT
        *,
        CASE
            WHEN valid_to IS NOT NULL THEN DATEDIFF(valid_to, valid_from) + 1
            ELSE DATEDIFF(CURDATE(), valid_from) + 1
        END AS days_in_status,
        CASE
            WHEN previous_status IS NOT NULL AND status != previous_status THEN TRUE
            ELSE FALSE
        END AS status_changed
    FROM with_previous_status
),

-- Add business-friendly status labels using seed table lookups
final AS (
    SELECT
        d.tenant_id,
        d.full_name,
        
        -- Status information (joined with code tables)
        d.status AS status_code,
        COALESCE(ts.label_en, CONCAT('Unknown (', d.status, ')')) AS status_label,
        
        d.previous_status AS previous_status_code,
        COALESCE(pts.label_en, CONCAT('Unknown (', d.previous_status, ')')) AS previous_status_label,
        
        -- Status transition flags
        d.status_changed,
        CASE
            WHEN d.status_changed THEN CONCAT(
                COALESCE(pts.label_en, CONCAT('Unknown (', d.previous_status, ')')),
                ' → ',
                COALESCE(ts.label_en, CONCAT('Unknown (', d.status, ')'))
            )
            ELSE NULL
        END AS status_transition,
        
        -- Contract information
        d.contract_type,
        COALESCE(ct.label_en, 'Unknown') AS contract_type_label,
        
        -- Time dimensions
        d.valid_from AS effective_date,
        d.valid_to AS end_date,
        d.days_in_status,
        d.is_current,
        
        -- Metadata
        d.dbt_updated_at,
        CURRENT_TIMESTAMP AS created_at
        
    FROM with_duration d
    LEFT JOIN {{ ref('code_tenant_status') }} ts ON d.status = ts.code
    LEFT JOIN {{ ref('code_tenant_status') }} pts ON d.previous_status = pts.code
    LEFT JOIN {{ ref('code_contract_type') }} ct ON d.contract_type = ct.code
)

SELECT * FROM final
ORDER BY tenant_id, effective_date
