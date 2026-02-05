{{
  config(
    materialized='view',
    schema='silver',
    enabled=true
  )
}}

-- Silver Layer: Cleaned customer inquiries (問い合わせ)
-- Transforms raw inquiry data for analytics

SELECT
    i.id as inquiry_id,
    i.tenant_id,
    
    -- Timestamps
    DATE(i.created_at) as inquiry_date,
    i.created_at as inquiry_timestamp,
    i.updated_at,
    
    -- Conversion tracking
    CASE 
        WHEN t.id IS NOT NULL THEN 1 
        ELSE 0 
    END as converted_to_tenant

FROM {{ source('staging', 'inquiries') }} i
LEFT JOIN {{ source('staging', 'tenants') }} t
    ON i.id = t.inquiry_id
WHERE i.id IS NOT NULL
