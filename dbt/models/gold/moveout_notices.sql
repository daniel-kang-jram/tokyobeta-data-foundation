{{
  config(
    materialized='incremental',
    unique_key='contract_id',
    on_schema_change='fail',
    schema='gold',
    indexes=[
      {'columns': ['notice_received_date'], 'type': 'btree'},
      {'columns': ['asset_id_hj'], 'type': 'btree'}
    ]
  )
}}

-- Gold Layer: Moveout Notices (Rolling 24-Month Window)
-- 退去通知: Same fields as moveouts table, triggered by moveout_receipt_date
-- 過去24か月分累積。より過去分は別のサマリーページに集計のみ残して、本シートの個別レコードは削除

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
    cancellation_notice_date as notice_received_date,  -- 解約通知日
    moveout_date as planned_moveout_date,     -- 退去日
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
    
    -- Notice-specific metrics
    notice_lead_time_days,
    CASE 
        WHEN is_completed_moveout THEN 'Completed'
        ELSE 'Pending'
    END as moveout_status,
    
    created_at,
    updated_at

FROM {{ ref('int_contracts') }}
WHERE cancellation_notice_date IS NOT NULL
  -- Rolling 24-month window
  AND cancellation_notice_date >= DATE_SUB(CURRENT_DATE, INTERVAL {{ var('moveout_notice_window_months') }} MONTH)
  AND latitude IS NOT NULL
  AND longitude IS NOT NULL

{% if is_incremental() %}
  -- Incremental logic: only new/updated records
  AND cancellation_notice_date > (SELECT COALESCE(MAX(notice_received_date), '2000-01-01') FROM {{ this }})
{% endif %}

ORDER BY notice_received_date DESC, asset_id_hj, room_number
