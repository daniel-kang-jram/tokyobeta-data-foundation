{{
  config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['snapshot_date', 'asset_id_hj'],
    schema='gold',
    indexes=[
      {'columns': ['snapshot_date', 'asset_id_hj'], 'type': 'btree'},
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
        (
            SELECT COALESCE(
                MIN(CASE WHEN occupancy_rate > 1 THEN snapshot_date END),
                DATE_SUB(MAX(snapshot_date), INTERVAL 2 DAY)
            )
            FROM {{ this }}
        ),
        CAST('1900-01-01' AS DATE)
      )
    {% endif %}
),

occupied_by_property AS (
    SELECT
        s.snapshot_date,
        s.apartment_id,
        COUNT(
            DISTINCT CASE
                WHEN s.is_room_primary THEN CONCAT(s.apartment_id, '-', s.room_id)
                ELSE NULL
            END
        ) AS occupied_rooms
    FROM {{ ref('tenant_room_snapshot_daily') }} s
    INNER JOIN snapshots_to_process d
        ON s.snapshot_date = d.snapshot_date
    WHERE s.apartment_id IS NOT NULL
      AND s.room_id IS NOT NULL
    GROUP BY s.snapshot_date, s.apartment_id
),

room_capacity_by_property AS (
    SELECT
        r.apartment_id,
        COUNT(DISTINCT r.id) AS total_rooms_physical
    FROM {{ source('staging', 'rooms') }} r
    WHERE r.apartment_id IS NOT NULL
      AND r.id IS NOT NULL
    GROUP BY r.apartment_id
),

occupancy_enriched AS (
    SELECT
        o.snapshot_date,
        p.apartment_id,
        p.asset_id_hj,
        p.apartment_name,
        p.prefecture,
        p.municipality,
        p.latitude,
        p.longitude,
        GREATEST(
            COALESCE(rc.total_rooms_physical, 0),
            COALESCE(p.room_count, 0)
        ) AS total_rooms,
        o.occupied_rooms
    FROM occupied_by_property o
    INNER JOIN {{ ref('dim_property') }} p
        ON p.apartment_id = o.apartment_id
    LEFT JOIN room_capacity_by_property rc
        ON rc.apartment_id = o.apartment_id
)

SELECT
    o.snapshot_date,
    o.apartment_id,
    o.asset_id_hj,
    o.apartment_name,
    o.prefecture,
    o.municipality,
    o.latitude,
    o.longitude,
    o.total_rooms,
    o.occupied_rooms,
    CAST(o.occupied_rooms / NULLIF(o.total_rooms, 0) AS DECIMAL(10,6)) AS occupancy_rate,
    CURRENT_TIMESTAMP AS created_at,
    CURRENT_TIMESTAMP AS updated_at
FROM occupancy_enriched o
WHERE o.total_rooms > 0
