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
        affiliation_status,
        is_transferred,
        is_renewal_ng,
        is_paysle_unpaid,
        renewal_priority,
        agreement_type,
        moving_id,
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
        LAG(is_paysle_unpaid) OVER (PARTITION BY tenant_id ORDER BY valid_from) AS previous_unpaid_status,
        LAG(is_renewal_ng) OVER (PARTITION BY tenant_id ORDER BY valid_from) AS previous_renewal_ng,
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
        END AS status_changed,
        CASE
            WHEN previous_unpaid_status IS NOT NULL AND is_paysle_unpaid != previous_unpaid_status THEN TRUE
            ELSE FALSE  
        END AS payment_status_changed,
        CASE
            WHEN previous_renewal_ng IS NOT NULL AND is_renewal_ng != previous_renewal_ng THEN TRUE
            ELSE FALSE
        END AS renewal_eligibility_changed
    FROM with_previous_status
),

-- Add business-friendly status labels
final AS (
    SELECT
        tenant_id,
        full_name,
        
        -- Status information
        status AS status_code,
        CASE status
            WHEN 1 THEN 'Inquiry'
            WHEN 2 THEN 'Preview Scheduled'
            WHEN 3 THEN 'Application Submitted'
            WHEN 4 THEN 'Under Contract'
            WHEN 5 THEN 'Active Tenant'
            WHEN 6 THEN 'Moveout Notice'
            WHEN 7 THEN 'Moved Out'
            WHEN 8 THEN 'Cancelled'
            ELSE CONCAT('Unknown (', status, ')')
        END AS status_label,
        
        previous_status AS previous_status_code,
        CASE previous_status
            WHEN 1 THEN 'Inquiry'
            WHEN 2 THEN 'Preview Scheduled'
            WHEN 3 THEN 'Application Submitted'
            WHEN 4 THEN 'Under Contract'
            WHEN 5 THEN 'Active Tenant'
            WHEN 6 THEN 'Moveout Notice'
            WHEN 7 THEN 'Moved Out'
            WHEN 8 THEN 'Cancelled'
            ELSE CONCAT('Unknown (', previous_status, ')')
        END AS previous_status_label,
        
        -- Status transition flags
        status_changed,
        CASE
            WHEN status_changed THEN CONCAT(
                CASE previous_status
                    WHEN 1 THEN 'Inquiry'
                    WHEN 2 THEN 'Preview Scheduled'
                    WHEN 3 THEN 'Application Submitted'
                    WHEN 4 THEN 'Under Contract'
                    WHEN 5 THEN 'Active Tenant'
                    WHEN 6 THEN 'Moveout Notice'
                    WHEN 7 THEN 'Moved Out'
                    WHEN 8 THEN 'Cancelled'
                    ELSE CONCAT('Unknown (', previous_status, ')')
                END,
                ' → ',
                CASE status
                    WHEN 1 THEN 'Inquiry'
                    WHEN 2 THEN 'Preview Scheduled'
                    WHEN 3 THEN 'Application Submitted'
                    WHEN 4 THEN 'Under Contract'
                    WHEN 5 THEN 'Active Tenant'
                    WHEN 6 THEN 'Moveout Notice'
                    WHEN 7 THEN 'Moved Out'
                    WHEN 8 THEN 'Cancelled'
                    ELSE CONCAT('Unknown (', status, ')')
                END
            )
            ELSE NULL
        END AS status_transition,
        
        -- Contract information
        contract_type,
        CASE contract_type
            WHEN 1 THEN 'Individual'
            WHEN 2 THEN 'Corporate - Company'
            WHEN 3 THEN 'Corporate - Other'
            ELSE 'Unknown'
        END AS contract_type_label,
        
        -- Payment status
        COALESCE(is_paysle_unpaid, 0) AS is_unpaid,
        payment_status_changed,
        CASE
            WHEN payment_status_changed AND is_paysle_unpaid = 1 THEN 'Became Unpaid'
            WHEN payment_status_changed AND is_paysle_unpaid = 0 THEN 'Payment Resolved'
            ELSE NULL
        END AS payment_status_change,
        
        -- Renewal information
        COALESCE(is_renewal_ng, 0) AS is_renewal_ineligible,
        renewal_eligibility_changed,
        COALESCE(renewal_priority, 0) AS renewal_priority,
        
        -- Other flags
        COALESCE(is_transferred, 0) AS is_transferred,
        affiliation_status,
        agreement_type,
        
        -- References
        moving_id,
        
        -- Time dimensions
        valid_from AS effective_date,
        valid_to AS end_date,
        days_in_status,
        is_current,
        
        -- Metadata
        dbt_updated_at,
        CURRENT_TIMESTAMP AS created_at
        
    FROM with_duration
)

SELECT * FROM final
ORDER BY tenant_id, effective_date
