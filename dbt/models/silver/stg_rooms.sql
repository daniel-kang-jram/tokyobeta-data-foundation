{{
  config(
    materialized='view',
    schema='silver'
  )
}}

-- Silver Layer: Cleaned rooms
-- Transforms raw room data

SELECT
    r.id as room_id,
    r.apartment_id,
    r.room_number,
    
    -- Room details
    r.rent,
    r.condo_fee,
    r.room_floor as floor_number,
    r.capacity,
    r.gender_type,
    r.bed_type,
    
    -- Status
    r.status as room_status,
    r.moving_id as current_lease_id,
    
    -- Metadata
    r.created_at,
    r.updated_at

FROM {{ source('staging', 'rooms') }} r
WHERE r.id IS NOT NULL
