{{
  config(
    materialized='view',
    schema='silver'
  )
}}

-- Silver Layer: Cleaned movings with semantic code values
-- Transforms raw contract lifecycle data with human-readable labels

SELECT
    m.id as moving_id,
    m.tenant_id,
    m.apartment_id,
    m.room_id,
    
    -- Contract type with semantic labels
    m.moving_agreement_type as contract_type_code,
    ct.label_ja as contract_type_ja,
    ct.label_en as contract_type_en,
    ct.tenant_type,
    
    -- Dates (standardized naming)
    DATE(m.movein_decided_date) as contract_date,
    m.movein_date as contract_start_date,
    m.rent_start_date,
    m.expiration_date as contract_expiration_date,
    m.original_movein_date as original_contract_date,
    m.moveout_receipt_date as cancellation_notice_date,
    
    -- Integrated moveout date (priority: moveout_date_integrated > moveout_plans_date > moveout_date)
    COALESCE(m.moveout_date_integrated, m.moveout_plans_date, m.moveout_date) as moveout_date,
    m.moveout_date_integrated,
    m.moveout_plans_date,
    m.moveout_date as moveout_final_rent_date,
    
    -- Flags (semantic values)
    CASE WHEN m.move_renew_flag = 1 THEN 'Yes' WHEN m.move_renew_flag = 0 THEN 'No' ELSE NULL END as is_renewal,
    m.cancel_flag = 0 as is_valid_contract,
    m.is_moveout = 1 as is_completed_moveout,
    
    -- Financial
    m.rent as monthly_rent,
    m.condo_fee,
    m.administrative_fee,
    m.moveout_fee,
    
    -- Metadata
    m.created_at,
    m.updated_at

FROM {{ source('staging', 'movings') }} m
LEFT JOIN {{ ref('code_contract_type') }} ct
    ON m.moving_agreement_type = ct.code
WHERE m.id IS NOT NULL
