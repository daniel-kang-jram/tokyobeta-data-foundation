{{
  config(
    materialized='table',
    schema='gold',
    indexes=[
      {'columns': ['period_grain', 'period_start'], 'type': 'btree'},
      {'columns': ['tenant_type'], 'type': 'btree'},
      {'columns': ['segment_type'], 'type': 'btree'},
      {'columns': ['segment_rank'], 'type': 'btree'}
    ]
  )
}}

-- Gold Layer: Segment-share view for pie/segment visuals.
-- Grain: (period_grain, period_start, tenant_type, segment_type, segment_value)

WITH base AS (
    SELECT
        period_grain,
        period_start,
        municipality,
        nationality,
        tenant_type,
        application_count,
        movein_count
    FROM {{ ref('funnel_application_to_movein_periodized') }}
),

segments AS (
    SELECT
        period_grain,
        period_start,
        tenant_type,
        'municipality' AS segment_type,
        municipality AS segment_value,
        application_count,
        movein_count
    FROM base

    UNION ALL

    SELECT
        period_grain,
        period_start,
        tenant_type,
        'nationality' AS segment_type,
        nationality AS segment_value,
        application_count,
        movein_count
    FROM base
),

segment_totals AS (
    SELECT
        period_grain,
        period_start,
        tenant_type,
        segment_type,
        SUM(application_count) AS total_application_count,
        SUM(movein_count) AS total_movein_count
    FROM segments
    GROUP BY
        period_grain,
        period_start,
        tenant_type,
        segment_type
),

ranked_segments AS (
    SELECT
        s.period_grain,
        s.period_start,
        s.tenant_type,
        s.segment_type,
        s.segment_value,
        s.application_count,
        s.movein_count,
        t.total_application_count,
        t.total_movein_count,
        ROW_NUMBER() OVER (
            PARTITION BY s.period_grain, s.period_start, s.tenant_type, s.segment_type
            ORDER BY s.application_count DESC, s.movein_count DESC, s.segment_value
        ) AS segment_rank
    FROM segments s
    INNER JOIN segment_totals t
        ON s.period_grain = t.period_grain
       AND s.period_start = t.period_start
       AND s.tenant_type = t.tenant_type
       AND s.segment_type = t.segment_type
)

SELECT
    period_grain,
    period_start,
    tenant_type,
    segment_type,
    segment_value,
    application_count,
    movein_count,
    CAST(
        COALESCE(application_count / NULLIF(total_application_count, 0), 0) AS DECIMAL(12, 4)
    ) AS application_share,
    CAST(
        COALESCE(movein_count / NULLIF(total_movein_count, 0), 0) AS DECIMAL(12, 4)
    ) AS movein_share,
    CAST(
        COALESCE(movein_count / NULLIF(application_count, 0), 0) AS DECIMAL(12, 4)
    ) AS application_to_movein_rate,
    segment_rank,
    CURRENT_TIMESTAMP AS created_at,
    CURRENT_TIMESTAMP AS updated_at
FROM ranked_segments
ORDER BY
    period_grain,
    period_start,
    tenant_type,
    segment_type,
    segment_rank
