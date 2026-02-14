{{
  config(
    materialized='table',
    schema='gold',
    indexes=[
      {'columns': ['week_start'], 'type': 'btree'},
      {'columns': ['event_type'], 'type': 'btree'},
      {'columns': ['tenant_type'], 'type': 'btree'}
    ]
  )
}}

-- Gold Layer: Move Events (Weekly Aggregation)
-- Grain: (week_start, event_type, tenant_type, rent_range, age_group)

SELECT
    week_start,
    event_type,
    tenant_type,
    rent_range,
    rent_range_order,
    age_group,
    SUM(event_count) AS event_count,
    AVG(monthly_rent) AS avg_monthly_rent,
    CURRENT_TIMESTAMP AS generated_at
FROM {{ ref('move_events') }}
GROUP BY
    week_start,
    event_type,
    tenant_type,
    rent_range,
    rent_range_order,
    age_group
ORDER BY
    week_start,
    event_type,
    tenant_type,
    rent_range_order,
    age_group
