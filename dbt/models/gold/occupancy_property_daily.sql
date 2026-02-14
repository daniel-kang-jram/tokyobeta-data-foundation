{{
  config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['snapshot_date', 'asset_id_hj'],
    schema='gold',
    indexes=[
      {'columns': ['snapshot_date'], 'type': 'btree'},
      {'columns': ['asset_id_hj'], 'type': 'btree'},
      {'columns': ['municipality'], 'type': 'btree'}
    ]
  )
}}

-- Gold Layer: Property Occupancy (Daily, Facts Only)
-- Derived from silver.tenant_room_snapshot_daily and dim_property.
-- Grain: (snapshot_date, asset_id_hj)

WITH snapshots_to_process AS (
    SELECT DISTINCT snapshot_date
    FROM {{ ref('tenant_room_snapshot_daily') }}
    {% if is_incremental() %}
      WHERE snapshot_date >= COALESCE(
        (SELECT DATE_SUB(MAX(snapshot_date), INTERVAL 1 DAY) FROM {{ this }}),
        CAST('1900-01-01' AS DATE)
      )
    {% endif %}
),

occupied_by_property AS (
    SELECT
        s.snapshot_date,
        s.apartment_id,
        COUNT(
            DISTINCT CONCAT(s.tenant_id, '-', s.apartment_id, '-', s.room_id)
        ) AS occupied_rooms
    FROM {{ ref('tenant_room_snapshot_daily') }} s
    INNER JOIN snapshots_to_process d
        ON s.snapshot_date = d.snapshot_date
    WHERE s.tenant_id IS NOT NULL
      AND s.apartment_id IS NOT NULL
      AND s.room_id IS NOT NULL
    GROUP BY s.snapshot_date, s.apartment_id
)

SELECT
    o.snapshot_date,
    p.apartment_id,
    p.asset_id_hj,
    p.apartment_name,
    p.prefecture,
    p.municipality,
    p.latitude,
    p.longitude,
    p.room_count AS total_rooms,
    o.occupied_rooms,
    CAST(o.occupied_rooms / NULLIF(p.room_count, 0) AS DECIMAL(10,6)) AS occupancy_rate,
    CURRENT_TIMESTAMP AS created_at,
    CURRENT_TIMESTAMP AS updated_at
FROM occupied_by_property o
INNER JOIN {{ ref('dim_property') }} p
    ON p.apartment_id = o.apartment_id
WHERE p.room_count IS NOT NULL
  AND p.room_count > 0
