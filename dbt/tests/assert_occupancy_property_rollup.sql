{{ config(severity='warn') }}

-- Test: Property occupancy rollup should reconcile to portfolio occupancy KPI
-- Compare the latest silver snapshot date across:
-- - SUM(occupied_rooms) from gold.occupancy_property_daily
-- - period_end_rooms from gold.occupancy_daily_metrics
--
-- This is a warn-only test (tolerance-based) to catch regressions without blocking daily SLA.

WITH meta AS (
    SELECT MAX(snapshot_date) AS as_of_snapshot_date
    FROM {{ ref('tenant_room_snapshot_daily') }}
),

portfolio AS (
    SELECT
        odm.snapshot_date,
        odm.period_end_rooms AS portfolio_occupied_rooms
    FROM gold.occupancy_daily_metrics odm
    INNER JOIN meta m
        ON odm.snapshot_date = m.as_of_snapshot_date
),

property_rollup AS (
    SELECT
        opd.snapshot_date,
        SUM(opd.occupied_rooms) AS property_occupied_rooms
    FROM {{ ref('occupancy_property_daily') }} opd
    INNER JOIN meta m
        ON opd.snapshot_date = m.as_of_snapshot_date
    GROUP BY opd.snapshot_date
)

SELECT
    p.snapshot_date,
    p.portfolio_occupied_rooms,
    r.property_occupied_rooms,
    (r.property_occupied_rooms - p.portfolio_occupied_rooms) AS diff_rooms
FROM portfolio p
INNER JOIN property_rollup r
    ON p.snapshot_date = r.snapshot_date
WHERE ABS(r.property_occupied_rooms - p.portfolio_occupied_rooms) > 50;

