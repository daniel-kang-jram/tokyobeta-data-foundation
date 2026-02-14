{{
  config(
    materialized='table',
    schema='gold',
    indexes=[
      {'columns': ['asset_id_hj'], 'type': 'btree'},
      {'columns': ['municipality'], 'type': 'btree'},
      {'columns': ['latitude', 'longitude'], 'type': 'btree'}
    ]
  )
}}

-- Gold Layer: Property Dimension
-- Centralized, gold-accessible property attributes and validated geolocation.

SELECT
    apartment_id,
    asset_id_hj,
    apartment_name,
    apartment_name_en,
    prefecture,
    municipality,
    full_address,
    zip_code,
    latitude,
    longitude,
    room_count,
    vacancy_room_count,
    property_status,
    apartment_type,
    building_type,
    created_at,
    updated_at
FROM {{ ref('stg_apartments') }}
WHERE apartment_id IS NOT NULL
  AND asset_id_hj IS NOT NULL
