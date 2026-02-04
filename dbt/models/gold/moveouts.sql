{{
  config(
    materialized='table',
    schema='gold',
    indexes=[
      {'columns': ['moveout_date'], 'type': 'btree'},
      {'columns': ['asset_id_hj'], 'type': 'btree'},
      {'columns': ['tenant_type'], 'type': 'btree'}
    ]
  )
}}

-- Gold Layer: Moveouts with Full Contract History
-- 退去: AssetID_HJ, Room Number, 契約体系, 契約チャンネル, 原契約締結日, 契約締結日, 契約開始日,
--      賃料発生日, 契約満了日, 解約通知日, 退去日, 再契約フラグ, 月額賃料, 個人・法人フラグ,
--      性別, 年齢, 国籍, 職種, 在留資格, latitude, longitude

SELECT
    contract_id,
    asset_id_hj,
    room_number,
    contract_type_ja as contract_system,      -- 契約体系
    contract_channel,                         -- 契約チャンネル
    original_contract_date,                   -- 原契約締結日
    contract_date,                            -- 契約締結日
    contract_start_date,                      -- 契約開始日
    rent_start_date,                          -- 賃料発生日
    contract_expiration_date,                 -- 契約満了日
    cancellation_notice_date,                 -- 解約通知日
    moveout_date,                             -- 退去日
    is_renewal as renewal_flag,               -- 再契約フラグ
    monthly_rent,                             -- 月額賃料
    tenant_type,                              -- 個人・法人フラグ
    gender,                                   -- 性別
    age,                                      -- 年齢
    nationality,                              -- 国籍
    occupation_company,                       -- 職種
    residence_status,                         -- 在留資格
    latitude,
    longitude,
    prefecture,
    municipality,
    full_address,
    apartment_name,
    
    -- Moveout-specific metrics
    total_stay_days,
    total_stay_months,
    notice_lead_time_days,
    moveout_reason_ja,
    moveout_reason_en,
    
    created_at,
    updated_at

FROM {{ ref('int_contracts') }}
WHERE is_completed_moveout
  AND moveout_date IS NOT NULL
  AND moveout_date >= '{{ var('min_valid_date') }}'
  AND latitude IS NOT NULL
  AND longitude IS NOT NULL
ORDER BY moveout_date DESC, asset_id_hj, room_number
