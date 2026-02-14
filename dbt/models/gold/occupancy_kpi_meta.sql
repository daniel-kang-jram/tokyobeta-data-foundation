{{
  config(
    materialized='table',
    schema='gold'
  )
}}

-- Gold Layer: Occupancy KPI Meta (1 row)
-- Provides the "as-of" boundary date for Fact vs Projection coloring in dashboards,
-- plus basic freshness signals for occupancy_daily_metrics.

SELECT
    (SELECT MAX(snapshot_date) FROM {{ ref('tenant_room_snapshot_daily') }}) AS as_of_snapshot_date,
    CURDATE() AS calendar_today,
    DATEDIFF(
        CURDATE(),
        (SELECT MAX(snapshot_date) FROM {{ ref('tenant_room_snapshot_daily') }})
    ) AS lag_days,
    (SELECT MAX(updated_at) FROM {{ source('gold', 'occupancy_daily_metrics') }}) AS gold_occupancy_max_updated_at,
    (SELECT MAX(snapshot_date) FROM {{ source('gold', 'occupancy_daily_metrics') }}) AS gold_occupancy_max_snapshot_date,
    CURRENT_TIMESTAMP AS generated_at,
    16108 AS total_physical_rooms
