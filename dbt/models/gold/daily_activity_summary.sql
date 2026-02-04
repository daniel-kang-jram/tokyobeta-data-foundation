{{
  config(
    materialized='table',
    schema='gold',
    indexes=[
      {'columns': ['activity_date'], 'type': 'btree'},
      {'columns': ['tenant_type'], 'type': 'btree'}
    ]
  )
}}

-- Gold Layer: Daily Activity Summary
-- Aggregates daily property management activities by individual/corporate tenant type
-- グラニュラリティ: Daily
-- データ: 問い合わせ, 申し込み, 契約締結, 確定入居者, 確定退去者, 稼働室数増減 (by 個人 and 法人)

WITH inquiries AS (
    -- 問い合わせ: Customer inquiries by date
    SELECT
        inquiry_date as activity_date,
        'individual' as tenant_type,  -- Default to individual
        COUNT(*) as inquiry_count
    FROM {{ ref('stg_inquiries') }}
    WHERE inquiry_date IS NOT NULL
      AND inquiry_date >= '{{ var('min_valid_date') }}'
    GROUP BY inquiry_date
),

applications AS (
    -- 申し込み: Applications (tenant registration date)
    SELECT
        DATE(created_at) as activity_date,
        tenant_type,
        COUNT(*) as application_count
    FROM {{ ref('int_contracts') }}
    WHERE created_at IS NOT NULL
      AND created_at >= '{{ var('min_valid_date') }}'
    GROUP BY DATE(created_at), tenant_type
),

contracts_signed AS (
    SELECT
        contract_date as activity_date,
        tenant_type,
        COUNT(*) as contract_signed_count
    FROM {{ ref('int_contracts') }}
    WHERE contract_date IS NOT NULL
      AND is_valid_contract
      AND contract_date >= '{{ var('min_valid_date') }}'
    GROUP BY contract_date, tenant_type
),

confirmed_movein AS (
    SELECT
        contract_start_date as activity_date,
        tenant_type,
        COUNT(*) as movein_count
    FROM {{ ref('int_contracts') }}
    WHERE contract_start_date IS NOT NULL
      AND is_valid_contract
      AND contract_start_date >= '{{ var('min_valid_date') }}'
    GROUP BY contract_start_date, tenant_type
),

confirmed_moveout AS (
    SELECT
        moveout_date as activity_date,
        tenant_type,
        COUNT(*) as moveout_count
    FROM {{ ref('int_contracts') }}
    WHERE moveout_date IS NOT NULL
      AND is_completed_moveout
      AND moveout_date >= '{{ var('min_valid_date') }}'
    GROUP BY moveout_date, tenant_type
),

-- Generate all dates in the range
date_spine AS (
    SELECT DISTINCT
        activity_date,
        tenant_type
    FROM (
        SELECT activity_date, tenant_type FROM inquiries
        UNION SELECT activity_date, tenant_type FROM applications
        UNION SELECT activity_date, tenant_type FROM contracts_signed
        UNION SELECT activity_date, tenant_type FROM confirmed_movein
        UNION SELECT activity_date, tenant_type FROM confirmed_moveout
    ) all_dates
),

final AS (
    SELECT
        ds.activity_date,
        ds.tenant_type,
        COALESCE(inq.inquiry_count, 0) as inquiries_count,            -- 問い合わせ
        COALESCE(app.application_count, 0) as applications_count,     -- 申し込み
        COALESCE(cs.contract_signed_count, 0) as contracts_signed_count,  -- 契約締結
        COALESCE(mi.movein_count, 0) as confirmed_moveins_count,      -- 確定入居者
        COALESCE(mo.moveout_count, 0) as confirmed_moveouts_count,    -- 確定退去者
        COALESCE(mi.movein_count, 0) - COALESCE(mo.moveout_count, 0) as net_occupancy_delta,  -- 稼働室数増減
        CURRENT_TIMESTAMP as created_at,
        CURRENT_TIMESTAMP as updated_at
    FROM date_spine ds
    LEFT JOIN inquiries inq
        ON ds.activity_date = inq.activity_date
        AND ds.tenant_type = inq.tenant_type
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
