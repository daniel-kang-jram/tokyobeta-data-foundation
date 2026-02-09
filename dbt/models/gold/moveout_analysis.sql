{{
  config(
    materialized='table',
    schema='gold',
    indexes=[
      {'columns': ['moveout_date'], 'type': 'btree'},
      {'columns': ['rent_range'], 'type': 'btree'},
      {'columns': ['prefecture'], 'type': 'btree'},
      {'columns': ['tenant_type'], 'type': 'btree'}
    ]
  )
}}

-- Gold Layer: Moveout Analysis with Categorical Dimensions
-- Enhanced moveout view with rent ranges, age groups, and tenure categories
-- for demographic and financial analysis

SELECT
    contract_id,
    asset_id_hj,
    room_number,
    moveout_date,
    
    -- Rent Range Categorization
    CASE 
        WHEN monthly_rent < 50000 THEN 'Under 50K'
        WHEN monthly_rent < 70000 THEN '50K-70K'
        WHEN monthly_rent < 100000 THEN '70K-100K'
        WHEN monthly_rent < 150000 THEN '100K-150K'
        ELSE '150K+'
    END AS rent_range,
    
    -- Sort order for rent ranges
    CASE 
        WHEN monthly_rent < 50000 THEN 1
        WHEN monthly_rent < 70000 THEN 2
        WHEN monthly_rent < 100000 THEN 3
        WHEN monthly_rent < 150000 THEN 4
        ELSE 5
    END AS rent_range_order,
    
    monthly_rent,                                 -- 月額賃料 (raw value)
    
    -- Geography
    prefecture,
    municipality,
    latitude,
    longitude,
    full_address,
    apartment_name,
    
    -- Tenant Classification
    tenant_type,                                  -- 個人・法人フラグ
    contract_type_ja as contract_system,          -- 契約体系
    contract_channel,                             -- 契約チャンネル
    
    -- Demographics
    gender,                                       -- 性別
    age,                                          -- 年齢
    
    -- Age Group
    CASE 
        WHEN age IS NULL THEN 'Unknown'
        WHEN age < 25 THEN 'Under 25'
        WHEN age < 35 THEN '25-34'
        WHEN age < 45 THEN '35-44'
        WHEN age < 55 THEN '45-54'
        ELSE '55+'
    END AS age_group,
    
    nationality,                                  -- 国籍
    occupation_company,                           -- 職種
    affiliation_type_en as occupation_industry,   -- 業種
    residence_status,                             -- 在留資格
    
    -- Contract Timeline
    original_contract_date,                       -- 原契約締結日
    contract_date,                                -- 契約締結日
    contract_start_date,                          -- 契約開始日
    rent_start_date,                              -- 賃料発生日
    contract_expiration_date,                     -- 契約満了日
    cancellation_notice_date,                     -- 解約通知日
    is_renewal as renewal_flag,                   -- 再契約フラグ
    
    -- Tenure Metrics
    total_stay_days,
    total_stay_months,
    
    -- Tenure Category
    CASE 
        WHEN total_stay_months IS NULL THEN 'Unknown'
        WHEN total_stay_months < 6 THEN 'Short (<6mo)'
        WHEN total_stay_months < 12 THEN 'Medium (6-12mo)'
        WHEN total_stay_months < 24 THEN 'Long (1-2yr)'
        ELSE 'Very Long (2yr+)'
    END AS tenure_category,
    
    notice_lead_time_days,
    
    -- Moveout Reason
    moveout_reason_ja,
    moveout_reason_en,
    
    -- Metadata
    created_at,
    updated_at

FROM {{ ref('int_contracts') }}
WHERE is_completed_moveout
  AND moveout_date IS NOT NULL
  AND moveout_date >= '{{ var('min_valid_date') }}'
  AND latitude IS NOT NULL
  AND longitude IS NOT NULL
ORDER BY moveout_date DESC, rent_range_order, asset_id_hj
