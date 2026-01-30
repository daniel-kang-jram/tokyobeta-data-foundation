{{
  config(
    materialized='incremental',
    unique_key='contract_id',
    on_schema_change='fail',
    indexes=[
      {'columns': ['notice_received_date'], 'type': 'btree'},
      {'columns': ['asset_id'], 'type': 'btree'}
    ]
  )
}}

-- Table 4: Moveout Notices (Rolling 24-Month Window)
-- 退去通知: Same fields as moveouts table, triggered by moveout_receipt_date
-- 過去24か月分累積。より過去分は別のサマリーページに集計のみ残して、本シートの個別レコードは削除

WITH moveout_notices_base AS (
    SELECT
        m.id as contract_id,
        m.tenant_id,
        a.unique_number as asset_id_hj,
        r.room_no as room_number,
        m.moving_agreement_type as contract_system,
        t.media_id as contract_channel,
        m.original_movein_date as original_contract_date,
        DATE(m.movein_decided_date) as contract_date,
        m.movein_date as contract_start_date,
        m.rent_start_date as rent_start_date,
        m.expiration_date as contract_expiration_date,
        m.moveout_receipt_date as notice_received_date,
        DATE({{ safe_moveout_date() }}) as planned_moveout_date,
        CASE WHEN m.move_renew_flag = 1 THEN 'Yes' ELSE 'No' END as renewal_flag,
        m.rent as monthly_rent,
        {{ is_corporate('m.moving_agreement_type') }} as tenant_type,
        CASE 
            WHEN t.gender_type = 1 THEN 'Male'
            WHEN t.gender_type = 2 THEN 'Female'
            ELSE 'Other'
        END as gender,
        COALESCE(t.age, TIMESTAMPDIFF(YEAR, t.birth_date, CURRENT_DATE)) as age,
        COALESCE(t.nationality, n.nationality_name) as nationality,
        {{ clean_string_null('t.affiliation') }} as occupation_company,
        {{ clean_string_null('t.personal_identity') }} as residence_status,
        a.latitude,
        a.longitude,
        a.prefecture,
        a.municipality,
        a.full_address,
        -- Notice-specific metrics
        DATEDIFF(DATE({{ safe_moveout_date() }}), m.moveout_receipt_date) as notice_lead_time_days,
        CASE 
            WHEN m.is_moveout = 1 THEN 'Completed'
            ELSE 'Pending'
        END as moveout_status,
        CURRENT_TIMESTAMP as created_at,
        CURRENT_TIMESTAMP as updated_at
    FROM {{ source('staging', 'movings') }} m
    INNER JOIN {{ source('staging', 'tenants') }} t
        ON m.tenant_id = t.id
    INNER JOIN {{ source('staging', 'apartments') }} a
        ON m.apartment_id = a.id
    INNER JOIN {{ source('staging', 'rooms') }} r
        ON m.room_id = r.id
    LEFT JOIN {{ source('staging', 'm_nationalities') }} n
        ON t.m_nationality_id = n.id
    WHERE m.moveout_receipt_date IS NOT NULL
      -- Rolling 24-month window
      AND m.moveout_receipt_date >= DATE_SUB(CURRENT_DATE, INTERVAL {{ var('moveout_notice_window_months') }} MONTH)
)

SELECT *
FROM moveout_notices_base
WHERE latitude IS NOT NULL
  AND longitude IS NOT NULL

{% if is_incremental() %}
  -- Incremental logic: only new/updated records
  AND notice_received_date > (SELECT COALESCE(MAX(notice_received_date), '2000-01-01') FROM {{ this }})
{% endif %}

ORDER BY notice_received_date DESC, asset_id_hj, room_number
