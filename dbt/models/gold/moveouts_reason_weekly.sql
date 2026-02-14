{{
  config(
    materialized='table',
    schema='gold',
    indexes=[
      {'columns': ['week_start'], 'type': 'btree'},
      {'columns': ['moveout_reason_en'], 'type': 'btree'}
    ]
  )
}}

-- Gold Layer: Move-out Reasons (Weekly)
-- Grain: (week_start, moveout_reason_en, tenant_type, rent_range)

SELECT
    week_start,
    COALESCE(moveout_reason_en, 'Unknown') AS moveout_reason_en,
    tenant_type,
    rent_range,
    rent_range_order,
    SUM(event_count) AS moveout_count,
    CURRENT_TIMESTAMP AS generated_at
FROM {{ ref('move_events') }}
WHERE event_type = 'moveout'
GROUP BY
    week_start,
    COALESCE(moveout_reason_en, 'Unknown'),
    tenant_type,
    rent_range,
    rent_range_order
ORDER BY
    week_start DESC,
    moveout_count DESC
