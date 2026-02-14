{{
  config(
    materialized='table',
    schema='gold',
    indexes=[
      {'columns': ['week_start'], 'type': 'btree'},
      {'columns': ['municipality'], 'type': 'btree'}
    ]
  )
}}

-- Gold Layer: Municipality Churn (Weekly)
-- Grain: (week_start, municipality)

SELECT
    week_start,
    COALESCE(municipality, 'Unknown') AS municipality,
    SUM(CASE WHEN event_type = 'movein' THEN event_count ELSE 0 END) AS movein_count,
    SUM(CASE WHEN event_type = 'moveout' THEN event_count ELSE 0 END) AS moveout_count,
    SUM(CASE WHEN event_type = 'movein' THEN event_count ELSE 0 END)
      - SUM(CASE WHEN event_type = 'moveout' THEN event_count ELSE 0 END) AS net_change
FROM {{ ref('move_events') }}
GROUP BY
    week_start,
    COALESCE(municipality, 'Unknown')
ORDER BY
    week_start DESC,
    net_change DESC
