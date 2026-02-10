{{
  config(
    materialized='table',
    schema='silver',
    indexes=[
      {'columns': ['contract_id'], 'type': 'btree'},
      {'columns': ['contract_date'], 'type': 'btree'},
      {'columns': ['tenant_type'], 'type': 'btree'},
      {'columns': ['asset_id_hj'], 'type': 'btree'}
    ]
  )
}}

-- Silver Layer: Intermediate Contracts Fact Table
-- Denormalized contract data with all semantic values - single source of truth for analytics
-- 
-- JOIN STRATEGY: Uses stg_movings (which has tenant_id) to capture ALL contracts
-- DEDUPLICATION: ROW_NUMBER() per tenant-room to eliminate duplicate historical records
--   - Handles data entry errors where same tenant-room has multiple "active" movings
--   - Selects most recent moving per tenant-room combination
--
-- NOTE: This captures ALL movings (not just current). For current snapshot, 
--       use tenant.moving_id join (see tokyo_beta_tenant_room_info.sql)

WITH deduplicated_movings AS (
    SELECT 
        m.*,
        ROW_NUMBER() OVER (
            PARTITION BY m.tenant_id, m.apartment_id, m.room_id 
            ORDER BY m.contract_start_date DESC, m.updated_at DESC, m.moving_id DESC
        ) as rn
    FROM {{ ref('stg_movings') }} m
)
SELECT
    m.moving_id as contract_id,
    
    -- Property identifiers
    a.asset_id_hj,
    a.apartment_name,
    a.apartment_name_en,
    r.room_number,
    
    -- Contract dates (standardized naming)
    m.contract_date,              -- 契約締結日 (movein_decided_date)
    m.contract_start_date,        -- 契約開始日 (movein_date)
    m.rent_start_date,            -- 賃料発生日
    m.contract_expiration_date,   -- 契約満了日
    m.original_contract_date,     -- 原契約締結日
    m.cancellation_notice_date,   -- 解約通知日
    m.moveout_date,               -- 退去日 (integrated)
    
    -- Contract type with semantic labels
    m.contract_type_code,
    m.contract_type_ja,           -- 契約体系
    m.contract_type_en,
    m.tenant_type,                -- 個人・法人フラグ (individual/corporate)
    
    -- Flags
    m.is_renewal,                 -- 再契約フラグ
    m.is_valid_contract,
    m.is_completed_moveout,
    
    -- Financial
    m.monthly_rent,               -- 月額賃料
    m.condo_fee,
    m.administrative_fee,
    m.moveout_fee,
    
    -- Tenant demographics (from stg_tenants with semantic labels)
    t.tenant_id,
    t.full_name,
    t.gender_code,
    t.gender,                     -- 性別 (Male/Female/Other)
    t.age,                        -- 年齢
    t.birth_date,
    t.nationality,                -- 国籍
    t.affiliation as occupation_company,  -- 職種
    t.affiliation_type_ja,
    t.affiliation_type_en,
    t.personal_identity_ja as residence_status_ja,  -- 在留資格
    t.personal_identity_en as residence_status,
    t.contract_channel,           -- 契約チャンネル (media_id)
    t.tenant_status_code,
    t.tenant_status_en,
    t.is_active_lease,
    t.moveout_reason_code,
    t.moveout_reason_ja,
    t.moveout_reason_en,
    
    -- Geolocation
    a.latitude,
    a.longitude,
    a.prefecture,
    a.municipality,
    a.full_address,
    
    -- Property metadata
    a.room_count as property_total_rooms,
    a.vacancy_room_count as property_vacant_rooms,
    
    -- Calculated metrics
    DATEDIFF(m.moveout_date, m.contract_start_date) as total_stay_days,
    TIMESTAMPDIFF(MONTH, m.contract_start_date, m.moveout_date) as total_stay_months,
    DATEDIFF(m.moveout_date, m.cancellation_notice_date) as notice_lead_time_days,
    
    -- Metadata
    CURRENT_TIMESTAMP as created_at,
    CURRENT_TIMESTAMP as updated_at

FROM deduplicated_movings m
INNER JOIN {{ ref('stg_tenants') }} t
    ON m.tenant_id = t.tenant_id
INNER JOIN {{ ref('stg_apartments') }} a
    ON m.apartment_id = a.apartment_id
INNER JOIN {{ ref('stg_rooms') }} r
    ON m.room_id = r.room_id
WHERE m.rn = 1  -- Only most recent moving per tenant-room
