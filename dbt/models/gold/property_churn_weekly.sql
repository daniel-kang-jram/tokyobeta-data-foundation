{{
  config(
    materialized='table',
    schema='gold',
    indexes=[
      {'columns': ['week_start'], 'type': 'btree'},
      {'columns': ['asset_id_hj'], 'type': 'btree'}
    ]
  )
}}

-- Gold Layer: Property Churn (Weekly)
-- Grain: (week_start, asset_id_hj)

SELECT
    week_start,
    asset_id_hj,
    COALESCE(apartment_name, 'Unknown') AS apartment_name,
    SUM(CASE WHEN event_type = 'movein' THEN event_count ELSE 0 END) AS movein_count,
    SUM(CASE WHEN event_type = 'moveout' THEN event_count ELSE 0 END) AS moveout_count,
    SUM(CASE WHEN event_type = 'movein' THEN event_count ELSE 0 END)
      - SUM(CASE WHEN event_type = 'moveout' THEN event_count ELSE 0 END) AS net_change
FROM {{ ref('move_events') }}
GROUP BY
    week_start,
    asset_id_hj,
    COALESCE(apartment_name, 'Unknown')
ORDER BY
    week_start DESC,
    net_change DESC
