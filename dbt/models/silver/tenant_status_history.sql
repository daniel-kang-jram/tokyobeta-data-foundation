{{
    config(
        materialized='incremental',
        unique_key=['tenant_id', 'valid_from'],
        on_schema_change='append_new_columns',
        post_hook=[
            """
            UPDATE {{ this }} t1
            INNER JOIN (
                SELECT DISTINCT tenant_id 
                FROM {{ this }} 
                WHERE valid_from = CURDATE()
            ) t2 ON t1.tenant_id = t2.tenant_id
            SET t1.valid_to = DATE_SUB(CURDATE(), INTERVAL 1 DAY), 
                t1.is_current = FALSE 
            WHERE t1.valid_from < CURDATE() 
              AND t1.is_current = TRUE
            """
        ]
    )
}}

/*
Tenant Status History - Slowly Changing Dimension (SCD Type 2)
Tracks historical changes in tenant status fields on a daily basis.

Purpose:
- Enable historical analysis of tenant status transitions
- Track when tenants changed status (e.g., active -> inactive)
- Support time-series analysis of tenant attributes
- Provide audit trail of status changes

Approach:
- Daily snapshot with change detection
- Only creates new rows when key status fields change
- Maintains valid_from and valid_to date ranges
- is_current flag for latest record

Key Status Fields Tracked:
- status: Primary tenant status
- contract_type: Individual vs Corporate
- affiliation_status: Employment status
- is_transferred: Transfer flag
- is_renewal_ng: Renewal eligibility
- is_paysle_unpaid: Payment status
- renewal_priority: Renewal priority level
*/

WITH current_snapshot AS (
    SELECT
        id AS tenant_id,
        full_name,
        
        -- Key status fields to track
        status,
        contract_type,
        affiliation_status,
        is_transferred,
        is_renewal_ng,
        is_paysle_unpaid,
        renewal_priority,
        agreement_type,
        
        -- Additional context
        moving_id,
        under_contract_id,
        first_movein_date,
        renewal_movein_date,
        renewal_deadline_date,
        
        -- Metadata
        updated_at,
        CURRENT_DATE AS snapshot_date
        
    FROM {{ source('staging', 'tenants') }}
)

{% if is_incremental() %},
    -- Get previous snapshot to detect changes
    previous_snapshot AS (
        SELECT
            tenant_id,
            status,
            contract_type,
            affiliation_status,
            is_transferred,
            is_renewal_ng,
            is_paysle_unpaid,
            renewal_priority,
            agreement_type,
            valid_to
        FROM {{ this }}
        WHERE is_current = TRUE
    ),
    
    -- Detect changes by comparing current vs previous
    changes_detected AS (
        SELECT
            c.tenant_id,
            c.full_name,
            c.status,
            c.contract_type,
            c.affiliation_status,
            c.is_transferred,
            c.is_renewal_ng,
            c.is_paysle_unpaid,
            c.renewal_priority,
            c.agreement_type,
            c.moving_id,
            c.under_contract_id,
            c.first_movein_date,
            c.renewal_movein_date,
            c.renewal_deadline_date,
            c.updated_at,
            c.snapshot_date,
            
            -- Flag if any tracked field changed
            CASE
                WHEN p.tenant_id IS NULL THEN TRUE  -- New tenant
                WHEN c.status != p.status THEN TRUE
                WHEN c.contract_type != p.contract_type THEN TRUE
                WHEN c.affiliation_status != p.affiliation_status THEN TRUE
                WHEN COALESCE(c.is_transferred, 0) != COALESCE(p.is_transferred, 0) THEN TRUE
                WHEN COALESCE(c.is_renewal_ng, 0) != COALESCE(p.is_renewal_ng, 0) THEN TRUE
                WHEN COALESCE(c.is_paysle_unpaid, 0) != COALESCE(p.is_paysle_unpaid, 0) THEN TRUE
                WHEN COALESCE(c.renewal_priority, 0) != COALESCE(p.renewal_priority, 0) THEN TRUE
                WHEN COALESCE(c.agreement_type, 0) != COALESCE(p.agreement_type, 0) THEN TRUE
                ELSE FALSE
            END AS has_changed
            
        FROM current_snapshot c
        LEFT JOIN previous_snapshot p
            ON c.tenant_id = p.tenant_id
    ),
    
    -- Only include records with changes
    new_records AS (
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
            under_contract_id,
            first_movein_date,
            renewal_movein_date,
            renewal_deadline_date,
            updated_at,
            snapshot_date AS valid_from,
            CAST(NULL AS DATE) AS valid_to,
            TRUE AS is_current,
            snapshot_date AS dbt_updated_at
        FROM changes_detected
        WHERE has_changed = TRUE
    )
    
    SELECT * FROM new_records

{% else %}
    -- Initial load: all current tenant records
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
        under_contract_id,
        first_movein_date,
        renewal_movein_date,
        renewal_deadline_date,
        updated_at,
        snapshot_date AS valid_from,
        CAST(NULL AS DATE) AS valid_to,
        TRUE AS is_current,
        snapshot_date AS dbt_updated_at
    FROM current_snapshot
{% endif %}
