{{
  config(
    materialized='table',
    indexes=[
      {'columns': ['moveout_date'], 'type': 'btree'},
      {'columns': ['asset_id'], 'type': 'btree'},
      {'columns': ['tenant_type'], 'type': 'btree'}
    ]
  )
}}

-- Table 3: Moveouts with Full Contract History
-- 退去: AssetID_HJ, Room Number, 契約体系, 契約チャンネル, 原契約締結日, 契約締結日, 契約開始日,
--      賃料発生日, 契約満了日, 解約通知日, 退去日, 再契約フラグ, 月額賃料, 個人・法人フラグ,
--      性別, 年齢, 国籍, 職種, 在留資格, latitude, longitude

WITH moveouts_base AS (
    SELECT
        m.id as contract_id,
        m.tenant_id,
        a.unique_number as asset_id_hj,
        r.room_number as room_number,
        m.moving_agreement_type as contract_system,
        t.media_id as contract_channel,
        m.original_movein_date as original_contract_date,
        DATE(m.movein_decided_date) as contract_date,
        m.movein_date as contract_start_date,
        m.rent_start_date as rent_start_date,
        m.expiration_date as contract_expiration_date,
        m.moveout_receipt_date as cancellation_notice_date,
        DATE({{ safe_moveout_date('m') }}) as moveout_date,
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
        -- Contract duration metrics
        DATEDIFF(DATE({{ safe_moveout_date('m') }}), m.movein_date) as total_stay_days,
        TIMESTAMPDIFF(MONTH, m.movein_date, DATE({{ safe_moveout_date('m') }})) as total_stay_months,
        t.reason_moveout as moveout_reason_id,
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
    WHERE {{ safe_moveout_date('m') }} IS NOT NULL
      AND m.is_moveout = 1
      AND DATE({{ safe_moveout_date('m') }}) >= '{{ var('min_valid_date') }}'
)

SELECT *
FROM moveouts_base
WHERE latitude IS NOT NULL
  AND longitude IS NOT NULL
ORDER BY moveout_date DESC, asset_id_hj, room_number
