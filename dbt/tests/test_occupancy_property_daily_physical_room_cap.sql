{{ config(severity='error') }}

-- Contract: property-level occupancy must never exceed physical room capacity.
-- Return violating rows so dbt fails when occupancy_rate > 1.0.
SELECT
    snapshot_date,
    asset_id_hj,
    occupied_rooms,
    total_rooms,
    occupancy_rate
FROM {{ ref('occupancy_property_daily') }}
WHERE occupancy_rate > 1.0
