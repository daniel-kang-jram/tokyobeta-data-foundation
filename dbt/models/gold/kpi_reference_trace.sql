{{
  config(
    materialized='table',
    schema='gold'
  )
}}

WITH latest_kpi AS (
    SELECT
        as_of_date,
        kpi_definition_version,
        same_day_moveout_policy,
        generated_at AS kpi_model_generated_at
    FROM {{ ref('kpi_month_end_metrics') }}
    ORDER BY as_of_date DESC
    LIMIT 1
),

occupancy_meta AS (
    SELECT
        as_of_snapshot_date,
        calendar_today,
        lag_days
    FROM {{ ref('occupancy_kpi_meta') }}
),

silver_trace AS (
    SELECT
        MAX(snapshot_date) AS silver_snapshot_max_date,
        MAX(dbt_updated_at) AS silver_snapshot_max_updated_at
    FROM {{ ref('tenant_room_snapshot_daily') }}
),

gold_trace AS (
    SELECT
        MAX(snapshot_date) AS gold_occupancy_max_snapshot_date,
        MAX(updated_at) AS gold_occupancy_max_updated_at
    FROM {{ source('gold', 'occupancy_daily_metrics') }}
)

SELECT
    lk.as_of_date,
    lk.kpi_definition_version,
    lk.same_day_moveout_policy,
    lk.kpi_model_generated_at,
    om.as_of_snapshot_date AS occupancy_meta_as_of_snapshot_date,
    om.calendar_today,
    CAST(om.lag_days AS SIGNED) AS freshness_lag_days,
    st.silver_snapshot_max_date,
    st.silver_snapshot_max_updated_at,
    gt.gold_occupancy_max_snapshot_date,
    gt.gold_occupancy_max_updated_at,
    CURRENT_TIMESTAMP AS trace_generated_at
FROM latest_kpi lk
CROSS JOIN occupancy_meta om
CROSS JOIN silver_trace st
CROSS JOIN gold_trace gt
