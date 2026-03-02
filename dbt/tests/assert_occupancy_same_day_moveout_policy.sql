{{ config(severity='error') }}

WITH kpi AS (
    SELECT
        as_of_date,
        occupancy_room_count_0000,
        occupancy_room_count_eod,
        same_day_moveins,
        same_day_moveouts,
        same_day_moveout_policy
    FROM {{ ref('kpi_month_end_metrics') }}
),

policy_checks AS (
    SELECT
        as_of_date,
        same_day_moveout_policy,
        occupancy_room_count_0000,
        same_day_moveins,
        same_day_moveouts,
        occupancy_room_count_eod,
        CAST(
            occupancy_room_count_0000
            + same_day_moveins
            - same_day_moveouts
            AS SIGNED
        ) AS expected_eod_rooms
    FROM kpi
    WHERE as_of_date BETWEEN CAST('2026-01-01' AS DATE) AND CAST('2026-02-29' AS DATE)
)

SELECT
    as_of_date,
    same_day_moveout_policy,
    occupancy_room_count_0000,
    same_day_moveins,
    same_day_moveouts,
    occupancy_room_count_eod,
    expected_eod_rooms
FROM policy_checks
WHERE same_day_moveout_policy <> 'count_moveout_room_at_0000_exclude_same_day_moveins'
   OR occupancy_room_count_eod <> expected_eod_rooms
