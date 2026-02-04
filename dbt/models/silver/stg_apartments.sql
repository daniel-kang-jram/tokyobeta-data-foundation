{{
  config(
    materialized='view',
    schema='silver'
  )
}}

-- Silver Layer: Cleaned apartments with validated geolocation
-- Transforms raw property data with data quality checks

SELECT
    a.id as apartment_id,
    a.unique_number as asset_id_hj,
    
    -- Property names
    a.apartment_name,
    a.apartment_name_en,
    a.apartment_name_old,
    
    -- Location
    a.prefecture,
    a.municipality,
    a.address,
    a.full_address,
    a.zip_code,
    
    -- Geolocation (validated)
    CASE 
        WHEN a.latitude BETWEEN 35.0 AND 36.0 AND a.longitude BETWEEN 139.0 AND 140.5
        THEN a.latitude
        ELSE NULL
    END as latitude,
    CASE 
        WHEN a.latitude BETWEEN 35.0 AND 36.0 AND a.longitude BETWEEN 139.0 AND 140.5
        THEN a.longitude
        ELSE NULL
    END as longitude,
    
    -- Property metadata
    a.room_count,
    a.vacancy_room_count,
    a.apartment_type,
    a.building_type,
    a.status as property_status,
    
    -- Metadata
    a.created_at,
    a.updated_at

FROM {{ source('staging', 'apartments') }} a
WHERE a.id IS NOT NULL
