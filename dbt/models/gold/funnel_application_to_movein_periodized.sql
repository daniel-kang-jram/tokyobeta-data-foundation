{{
  config(
    materialized='table',
    schema='gold',
    indexes=[
      {'columns': ['period_grain', 'period_start'], 'type': 'btree'},
      {'columns': ['municipality'], 'type': 'btree'},
      {'columns': ['nationality'], 'type': 'btree'},
      {'columns': ['tenant_type'], 'type': 'btree'}
    ]
  )
}}

-- Gold Layer: Periodized application -> move-in funnel.
-- Grain: (period_grain, period_start, municipality, nationality, tenant_type)

WITH daily AS (
    SELECT
        activity_date,
        municipality,
        nationality,
        tenant_type,
        application_count,
        movein_count
    FROM {{ ref('funnel_application_to_movein_daily') }}
),

periodized AS (
    SELECT
        'daily' AS period_grain,
        activity_date AS period_start,
        municipality,
        nationality,
        tenant_type,
        application_count,
        movein_count
    FROM daily

    UNION ALL

    SELECT
        'weekly' AS period_grain,
        DATE_SUB(activity_date, INTERVAL WEEKDAY(activity_date) DAY) AS period_start,
        municipality,
        nationality,
        tenant_type,
        application_count,
        movein_count
    FROM daily

    UNION ALL

    SELECT
        'monthly' AS period_grain,
        CAST(DATE_FORMAT(activity_date, '%Y-%m-01') AS DATE) AS period_start,
        municipality,
        nationality,
        tenant_type,
        application_count,
        movein_count
    FROM daily
),

aggregated AS (
    SELECT
        period_grain,
        period_start,
        municipality,
        nationality,
        tenant_type,
        SUM(application_count) AS application_count,
        SUM(movein_count) AS movein_count
    FROM periodized
    GROUP BY
        period_grain,
        period_start,
        municipality,
        nationality,
        tenant_type
)

SELECT
    period_grain,
    period_start,
    municipality,
    nationality,
    tenant_type,
    application_count,
    movein_count,
    CAST(
        COALESCE(movein_count / NULLIF(application_count, 0), 0) AS DECIMAL(12, 4)
    ) AS application_to_movein_rate,
    CURRENT_TIMESTAMP AS created_at,
    CURRENT_TIMESTAMP AS updated_at
FROM aggregated
ORDER BY
    period_grain,
    period_start,
    municipality,
    nationality,
    tenant_type
