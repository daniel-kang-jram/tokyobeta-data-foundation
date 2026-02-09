{{
    config(
        materialized='table',
        indexes=[
            {'columns': ['tenant_id', 'valid_from']},
            {'columns': ['tenant_id', 'is_current']},
            {'columns': ['valid_from']},
            {'columns': ['status']}
        ]
    )
}}

/*
Tenant Status History - Slowly Changing Dimension (SCD Type 2)
Tracks historical changes in tenant status using daily snapshots from S3.

WIPE-RESILIENT DESIGN:
- Built from staging.tenant_daily_snapshots (loaded from S3 daily)
- Fully rebuilt on each run (materialized='table')
- S3 is the source of truth - Aurora wipes don't lose history
- Historical data goes back to Oct 2025 (127+ days of snapshots)

Purpose:
- Enable historical analysis of tenant status transitions
- Track when tenants changed status (e.g., active -> inactive)
- Support time-series analysis of tenant attributes
- Survive Aurora database wipes without data loss

Approach:
- Daily snapshots show tenant status on each date
- LAG() window functions detect changes between consecutive dates
- Only creates history records when status actually changed
- Computes valid_from (first date of status) and valid_to (last date before change)
- is_current flag marks the latest status for each tenant

Key Fields Tracked:
- status: Primary tenant status
- contract_type: Individual vs Corporate
*/

WITH daily_snapshots AS (
    -- Source: Daily tenant snapshots loaded from S3
    -- Each row represents a tenant's status on a specific date
    SELECT
        tenant_id,
        status,
        contract_type,
        full_name,
        snapshot_date
    FROM {{ source('staging', 'tenant_daily_snapshots') }}
),

-- Enrich with previous values to detect changes
with_previous AS (
    SELECT
        tenant_id,
        status,
        contract_type,
        full_name,
        snapshot_date,
        
        -- Look back to previous snapshot for this tenant
        LAG(status) OVER (PARTITION BY tenant_id ORDER BY snapshot_date) AS prev_status,
        LAG(contract_type) OVER (PARTITION BY tenant_id ORDER BY snapshot_date) AS prev_contract_type,
        LAG(snapshot_date) OVER (PARTITION BY tenant_id ORDER BY snapshot_date) AS prev_snapshot_date,
        
        -- Look ahead to next snapshot
        LEAD(snapshot_date) OVER (PARTITION BY tenant_id ORDER BY snapshot_date) AS next_snapshot_date
        
    FROM daily_snapshots
),

-- Identify transition points (where status or contract_type changed)
transitions AS (
    SELECT
        tenant_id,
        status,
        contract_type,
        full_name,
        snapshot_date,
        prev_status,
        prev_contract_type,
        next_snapshot_date,
        
        -- Flag if this is a new status period (first snapshot or status changed)
        CASE
            WHEN prev_status IS NULL THEN TRUE  -- First snapshot for this tenant
            WHEN status != prev_status THEN TRUE
            WHEN contract_type != prev_contract_type THEN TRUE
            ELSE FALSE
        END AS is_transition
        
    FROM with_previous
),

-- Filter to only keep transition points
status_periods AS (
    SELECT
        tenant_id,
        status,
        contract_type,
        full_name,
        snapshot_date AS valid_from,
        
        -- valid_to is the day before the next transition
        CASE
            WHEN next_snapshot_date IS NOT NULL 
            THEN DATE_SUB(next_snapshot_date, INTERVAL 1 DAY)
            ELSE NULL  -- Current status has no end date
        END AS valid_to,
        
        -- is_current if this is the latest status (no next snapshot)
        CASE
            WHEN next_snapshot_date IS NULL THEN TRUE
            ELSE FALSE
        END AS is_current,
        
        -- Metadata
        CURRENT_TIMESTAMP AS dbt_updated_at
        
    FROM transitions
    WHERE is_transition = TRUE  -- Only keep rows where status actually changed
),

-- Add semantic labels for status and contract_type
final AS (
    SELECT
        sp.tenant_id,
        sp.full_name,
        
        -- Status information with semantic labels
        sp.status,
        ts.label_ja as status_label_ja,
        ts.label_en as status_label_en,
        ts.is_active_lease,
        
        -- Contract type with semantic labels
        sp.contract_type,
        CASE 
            WHEN sp.contract_type IN (2, 3) THEN 'corporate'
            WHEN sp.contract_type IN (1, 6, 7, 9) THEN 'individual'
            ELSE 'unknown'
        END as tenant_type,
        CASE
            WHEN sp.contract_type = 1 THEN '一般'
            WHEN sp.contract_type = 2 THEN '法人契約'
            WHEN sp.contract_type = 3 THEN '法人契約個人'
            WHEN sp.contract_type = 6 THEN '定期契約'
            WHEN sp.contract_type = 7 THEN '一般保証人'
            WHEN sp.contract_type = 9 THEN '一般2'
            ELSE '未設定'
        END as contract_type_label_ja,
        
        -- Time dimensions
        sp.valid_from,
        sp.valid_to,
        sp.is_current,
        
        -- Calculate days in this status
        CASE
            WHEN sp.valid_to IS NOT NULL 
            THEN DATEDIFF(sp.valid_to, sp.valid_from) + 1
            ELSE DATEDIFF(CURDATE(), sp.valid_from) + 1
        END AS days_in_status,
        
        -- Metadata
        sp.dbt_updated_at
        
    FROM status_periods sp
    LEFT JOIN {{ ref('code_tenant_status') }} ts
        ON sp.status = ts.code
)

SELECT 
    tenant_id,
    full_name,
    status,
    status_label_ja,
    status_label_en,
    is_active_lease,
    contract_type,
    tenant_type,
    contract_type_label_ja,
    valid_from,
    valid_to,
    is_current,
    days_in_status,
    dbt_updated_at
FROM final
ORDER BY tenant_id, valid_from
