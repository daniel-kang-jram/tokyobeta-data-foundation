{{
  config(
    materialized='table',
    indexes=[
      {'columns': ['activity_date'], 'type': 'btree'},
      {'columns': ['tenant_type'], 'type': 'btree'}
    ]
  )
}}

-- Table 1: Daily Activity Summary
-- Aggregates daily property management activities by individual/corporate tenant type
-- グラニュラリティ: Daily
-- データ: 申し込み, 契約締結, 確定入居者, 確定退去者, 稼働室数増減 (by 個人 and 法人)

WITH applications AS (
    SELECT
        DATE(created_at) as activity_date,
        {{ is_corporate('tenant_contract_type') }} as tenant_type,
        COUNT(*) as application_count
    FROM {{ source('staging', 'movings') }}
    WHERE created_at IS NOT NULL
      AND created_at >= '{{ var('min_valid_date') }}'
    GROUP BY DATE(created_at), tenant_type
),

contracts_signed AS (
    SELECT
        DATE(movein_decided_date) as activity_date,
        {{ is_corporate('moving_agreement_type') }} as tenant_type,
        COUNT(*) as contract_signed_count
    FROM {{ source('staging', 'movings') }}
    WHERE movein_decided_date IS NOT NULL
      AND cancel_flag = 0
      AND movein_decided_date >= '{{ var('min_valid_date') }}'
    GROUP BY DATE(movein_decided_date), tenant_type
),

confirmed_movein AS (
    SELECT
        DATE(movein_date) as activity_date,
        {{ is_corporate('moving_agreement_type') }} as tenant_type,
        COUNT(*) as movein_count
    FROM {{ source('staging', 'movings') }}
    WHERE movein_date IS NOT NULL
      AND cancel_flag = 0
      AND movein_date >= '{{ var('min_valid_date') }}'
    GROUP BY DATE(movein_date), tenant_type
),

confirmed_moveout AS (
    SELECT
        DATE({{ safe_moveout_date() }}) as activity_date,
        {{ is_corporate('moving_agreement_type') }} as tenant_type,
        COUNT(*) as moveout_count
    FROM {{ source('staging', 'movings') }}
    WHERE {{ safe_moveout_date() }} IS NOT NULL
      AND is_moveout = 1
      AND {{ safe_moveout_date() }} >= '{{ var('min_valid_date') }}'
    GROUP BY DATE({{ safe_moveout_date() }}), tenant_type
),

-- Generate all dates in the range
date_spine AS (
    SELECT DISTINCT
        activity_date,
        tenant_type
    FROM (
        SELECT activity_date, tenant_type FROM applications
        UNION SELECT activity_date, tenant_type FROM contracts_signed
        UNION SELECT activity_date, tenant_type FROM confirmed_movein
        UNION SELECT activity_date, tenant_type FROM confirmed_moveout
    ) all_dates
),

final AS (
    SELECT
        ds.activity_date,
        ds.tenant_type,
        COALESCE(app.application_count, 0) as applications_count,
        COALESCE(cs.contract_signed_count, 0) as contracts_signed_count,
        COALESCE(mi.movein_count, 0) as confirmed_moveins_count,
        COALESCE(mo.moveout_count, 0) as confirmed_moveouts_count,
        COALESCE(mi.movein_count, 0) - COALESCE(mo.moveout_count, 0) as net_occupancy_delta,
        CURRENT_TIMESTAMP as created_at,
        CURRENT_TIMESTAMP as updated_at
    FROM date_spine ds
    LEFT JOIN applications app
        ON ds.activity_date = app.activity_date
        AND ds.tenant_type = app.tenant_type
    LEFT JOIN contracts_signed cs
        ON ds.activity_date = cs.activity_date
        AND ds.tenant_type = cs.tenant_type
    LEFT JOIN confirmed_movein mi
        ON ds.activity_date = mi.activity_date
        AND ds.tenant_type = mi.tenant_type
    LEFT JOIN confirmed_moveout mo
        ON ds.activity_date = mo.activity_date
        AND ds.tenant_type = mo.tenant_type
)

SELECT * FROM final
ORDER BY activity_date DESC, tenant_type
