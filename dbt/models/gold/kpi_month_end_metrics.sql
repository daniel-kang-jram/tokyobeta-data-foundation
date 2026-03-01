{{
  config(
    materialized='table',
    schema='gold',
    indexes=[
      {'columns': ['as_of_date'], 'type': 'btree'},
      {'columns': ['is_month_end'], 'type': 'btree'}
    ]
  )
}}

WITH snapshot_room_primary AS (
    SELECT
        s.snapshot_date AS as_of_date,
        COUNT(
            DISTINCT CASE
                WHEN s.is_room_primary = TRUE
                    THEN CONCAT(s.apartment_id, '-', s.room_id)
                ELSE NULL
            END
        ) AS room_primary_occupied_rooms_eod,
        COUNT(
            DISTINCT CASE
                WHEN s.is_room_primary = TRUE
                 AND (s.move_in_date IS NULL OR s.move_in_date < s.snapshot_date)
                    THEN CONCAT(s.apartment_id, '-', s.room_id)
                ELSE NULL
            END
        ) AS room_primary_occupied_rooms_0000,
        COUNT(
            DISTINCT CASE
                WHEN s.is_room_primary = TRUE
                 AND s.move_in_date = s.snapshot_date
                    THEN CONCAT(s.apartment_id, '-', s.room_id)
                ELSE NULL
            END
        ) AS room_primary_same_day_moveins,
        COUNT(
            DISTINCT CASE
                WHEN s.is_room_primary = TRUE
                 AND COALESCE(s.moveout_plans_date, s.moveout_date) = s.snapshot_date
                    THEN CONCAT(s.apartment_id, '-', s.room_id)
                ELSE NULL
            END
        ) AS room_primary_same_day_moveouts,
        SUM(
            CASE
                WHEN s.is_room_primary = TRUE
                 AND (s.move_in_date IS NULL OR s.move_in_date < s.snapshot_date)
                    THEN COALESCE(m.rent, 0)
                ELSE 0
            END
        ) AS room_primary_rent_sum_jpy_0000
    FROM {{ ref('tenant_room_snapshot_daily') }} s
    LEFT JOIN {{ source('staging', 'movings') }} m
        ON m.id = s.moving_id
    GROUP BY s.snapshot_date
),

occupancy_daily_metrics AS (
    SELECT
        odm.snapshot_date AS as_of_date,
        CAST(odm.period_start_rooms AS SIGNED) AS occupancy_room_count_0000_gold,
        CAST(odm.period_end_rooms AS SIGNED) AS occupancy_room_count_eod_gold,
        CAST(odm.new_moveins AS SIGNED) AS same_day_moveins_gold,
        CAST(odm.new_moveouts AS SIGNED) AS same_day_moveouts_gold
    FROM {{ source('gold', 'occupancy_daily_metrics') }} odm
),

kpi_meta AS (
    SELECT
        CAST(total_physical_rooms AS SIGNED) AS total_physical_rooms
    FROM {{ ref('occupancy_kpi_meta') }}
    LIMIT 1
),

merged AS (
    SELECT
        srp.as_of_date,
        (srp.as_of_date = LAST_DAY(srp.as_of_date)) AS is_month_end,
        meta.total_physical_rooms,
        COALESCE(odm.occupancy_room_count_0000_gold, srp.room_primary_occupied_rooms_0000)
            AS occupancy_room_count_0000,
        COALESCE(odm.occupancy_room_count_eod_gold, srp.room_primary_occupied_rooms_eod)
            AS occupancy_room_count_eod,
        COALESCE(odm.same_day_moveins_gold, srp.room_primary_same_day_moveins) AS same_day_moveins,
        COALESCE(odm.same_day_moveouts_gold, srp.room_primary_same_day_moveouts)
            AS same_day_moveouts,
        CAST(
            ROUND(
                srp.room_primary_rent_sum_jpy_0000
                / NULLIF(srp.room_primary_occupied_rooms_0000, 0),
                0
            ) AS DECIMAL(12, 2)
        ) AS rent_jpy
    FROM snapshot_room_primary srp
    LEFT JOIN occupancy_daily_metrics odm
        ON srp.as_of_date = odm.as_of_date
    CROSS JOIN kpi_meta meta
),

final AS (
    SELECT
        as_of_date,
        is_month_end,
        total_physical_rooms,
        occupancy_room_count_0000,
        occupancy_room_count_eod,
        same_day_moveins,
        same_day_moveouts,
        CAST(
            occupancy_room_count_eod / NULLIF(total_physical_rooms, 0)
            AS DECIMAL(10, 6)
        ) AS occupancy_rate,
        rent_jpy,
        CAST(
            ROUND(
                rent_jpy
                * (occupancy_room_count_eod / NULLIF(total_physical_rooms, 0)),
                0
            ) AS DECIMAL(12, 2)
        ) AS revpar_jpy,
        CAST(
            ROUND(
                rent_jpy
                * (occupancy_room_count_eod / NULLIF(total_physical_rooms, 0))
                * 0.952000,
                0
            ) AS DECIMAL(12, 2)
        ) AS recpar_cash_jpy,
        CAST(0.952000 AS DECIMAL(10, 6)) AS cash_realization_rate,
        'count_moveout_room_at_0000_exclude_same_day_moveins' AS same_day_moveout_policy,
        'kpi_definition_v2026_03_room_primary' AS kpi_definition_version,
        CURRENT_TIMESTAMP AS generated_at
    FROM merged
)

SELECT *
FROM final
ORDER BY as_of_date
