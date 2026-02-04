{{
  config(
    materialized='view',
    schema='silver',
    enabled=true
  )
}}

-- Silver Layer: Cleaned customer inquiries (問い合わせ)
-- Transforms raw inquiry data for analytics
-- NOTE: Currently disabled as inquiries table is not loaded in staging schema

SELECT
    i.id as inquiry_id,
    i.tenant_id,
    
    -- Inquiry details
    i.apartment_id,
    i.room_id,
    i.inquiry_type,
    i.inquiry_status,
    i.inquiry_source,
    
    -- Timestamps
    DATE(i.created_at) as inquiry_date,
    i.created_at as inquiry_timestamp,
    i.updated_at,
    
    -- Conversion tracking
    CASE 
        WHEN t.id IS NOT NULL THEN 1 
        ELSE 0 
    END as converted_to_tenant,
    
    -- Metadata
    i.remarks

FROM {{ source('staging', 'inquiries') }} i
LEFT JOIN {{ source('staging', 'tenants') }} t
    ON i.id = t.inquiry_id
WHERE i.id IS NOT NULL
