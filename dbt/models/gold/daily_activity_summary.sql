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
--
-- METRIC DEFINITIONS (CORRECTED):
-- 1. inquiries_count (問い合わせ数): Number of NEW tenants registered with any status that day
-- 2. applications_count (申し込み数): Tenants with status 仮予約(4) or 初期賃料(5) where updated_at is that day
-- 3. contracts_signed_count (契約締結): Contracts signed by contract_date
-- 4. confirmed_moveins_count (確定入居者/入居数): Tenants with status [4,5,6,7,9,14,15] where movein_date is that day
-- 5. confirmed_moveouts_count (確定退去者): Tenants with status [14,15,16,17] where moveout_date is that day
-- 6. net_occupancy_delta (稼働室数増減): Move-ins minus move-outs

WITH inquiries AS (
    -- 問い合わせ数: New tenants registered (any status) by creation date
    SELECT
        DATE(t.created_at) as activity_date,
        COALESCE(ct.tenant_type, 'individual') as tenant_type,
        COUNT(DISTINCT t.id) as inquiry_count
    FROM {{ source('staging', 'tenants') }} t
    LEFT JOIN {{ ref('code_contract_type') }} ct
        ON t.contract_type = ct.code
    WHERE t.created_at IS NOT NULL
      AND t.created_at >= '{{ var('min_valid_date') }}'
    GROUP BY DATE(t.created_at), tenant_type
),

applications AS (
    -- 申し込み数: Tenants with status 仮予約(4) or 初期賃料(5) by updated_at date
    SELECT
        DATE(t.updated_at) as activity_date,
        COALESCE(ct.tenant_type, 'individual') as tenant_type,
        COUNT(DISTINCT t.id) as application_count
    FROM {{ source('staging', 'tenants') }} t
    LEFT JOIN {{ ref('code_contract_type') }} ct
        ON t.contract_type = ct.code
    WHERE t.status IN (4, 5)  -- 4=仮予約, 5=初期賃料
      AND t.updated_at IS NOT NULL
      AND t.updated_at >= '{{ var('min_valid_date') }}'
    GROUP BY DATE(t.updated_at), tenant_type
),

contracts_signed AS (
    -- 契約締結: Contracts signed by contract_date (契約締結日)
    -- Only includes valid contracts (is_valid_contract = true)
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
    -- 確定入居者/入居数: Tenants with status [4,5,6,7,9,14,15] by movein_date
    -- Status: 仮予約(4)、初期賃料(5)、入居説明(6)、入居(7)、居住中(9)、退去通知(14)、退去予定(15)
    SELECT
        DATE(mv.movein_date) as activity_date,
        COALESCE(ct.tenant_type, 'individual') as tenant_type,
        COUNT(DISTINCT t.id) as movein_count
    FROM {{ source('staging', 'tenants') }} t
    INNER JOIN {{ source('staging', 'movings') }} mv ON t.moving_id = mv.id
    LEFT JOIN {{ ref('code_contract_type') }} ct
        ON t.contract_type = ct.code
    WHERE t.status IN (4, 5, 6, 7, 9, 14, 15)
      AND mv.movein_date IS NOT NULL
      AND mv.movein_date >= '{{ var('min_valid_date') }}'
    GROUP BY DATE(mv.movein_date), tenant_type
),

confirmed_moveout AS (
    -- 確定退去者: Tenants with status [14,15,16,17] by moveout_date (NOT moveout_plans_date)
    -- Status: 退去通知(14)、退去予定(15)、メンテ待ち(16)、退去済み(17)
    SELECT
        DATE(mv.moveout_date) as activity_date,
        COALESCE(ct.tenant_type, 'individual') as tenant_type,
        COUNT(DISTINCT t.id) as moveout_count
    FROM {{ source('staging', 'tenants') }} t
    INNER JOIN {{ source('staging', 'movings') }} mv ON t.moving_id = mv.id
    LEFT JOIN {{ ref('code_contract_type') }} ct
        ON t.contract_type = ct.code
    WHERE t.status IN (14, 15, 16, 17)  -- 退去通知、退去予定、メンテ待ち、退去済み
      AND mv.moveout_date IS NOT NULL  -- Using moveout_date, NOT moveout_plans_date
      AND mv.moveout_date >= '{{ var('min_valid_date') }}'
    GROUP BY DATE(mv.moveout_date), tenant_type
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
