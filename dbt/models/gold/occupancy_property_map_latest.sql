{{
  config(
    materialized='table',
    schema='gold',
    indexes=[
      {'columns': ['asset_id_hj'], 'type': 'btree'},
      {'columns': ['municipality'], 'type': 'btree'},
      {'columns': ['prefecture'], 'type': 'btree'}
    ]
  )
}}

-- Gold Layer: Property Occupancy Map (Latest Snapshot + 7D Delta)
-- Grain: 1 row per property for the latest available snapshot_date.

WITH latest AS (
    SELECT MAX(snapshot_date) AS latest_snapshot_date
    FROM {{ ref('occupancy_property_daily') }}
)

SELECT
    o.snapshot_date,
    o.asset_id_hj,
    o.apartment_name,
    o.municipality,
    o.prefecture,
    o.latitude,
    o.longitude,
    o.total_rooms,
    o.occupied_rooms,
    o.occupancy_rate,
    o7.occupancy_rate AS occupancy_rate_7d_ago,
    CASE
        WHEN o7.occupancy_rate IS NULL THEN NULL
        ELSE o.occupancy_rate - o7.occupancy_rate
    END AS occupancy_rate_delta_7d,
    o7.occupied_rooms AS occupied_rooms_7d_ago,
    CASE
        WHEN o7.occupied_rooms IS NULL THEN NULL
        ELSE o.occupied_rooms - o7.occupied_rooms
    END AS occupied_rooms_delta_7d,
    CURRENT_TIMESTAMP AS created_at,
    CURRENT_TIMESTAMP AS updated_at
FROM {{ ref('occupancy_property_daily') }} o
CROSS JOIN latest l
LEFT JOIN {{ ref('occupancy_property_daily') }} o7
    ON o7.asset_id_hj = o.asset_id_hj
   AND o7.snapshot_date = DATE_SUB(o.snapshot_date, INTERVAL 7 DAY)
WHERE o.snapshot_date = l.latest_snapshot_date
