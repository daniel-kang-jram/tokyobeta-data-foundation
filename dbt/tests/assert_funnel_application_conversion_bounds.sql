{{ config(severity='error') }}

-- Test: Ensure conversion rate is bounded [0, 1] and derived with a safe denominator.

WITH periodized AS (
    SELECT
        period_grain,
        period_start,
        municipality,
        nationality,
        tenant_type,
        application_count,
        movein_count,
        application_to_movein_rate
    FROM {{ ref('funnel_application_to_movein_periodized') }}
),

segment_share AS (
    SELECT
        period_grain,
        period_start,
        segment_type AS municipality,
        segment_value AS nationality,
        tenant_type,
        application_count,
        movein_count,
        application_to_movein_rate
    FROM {{ ref('funnel_application_to_movein_segment_share') }}
),

combined AS (
    SELECT * FROM periodized
    UNION ALL
    SELECT * FROM segment_share
)

SELECT
    period_grain,
    period_start,
    municipality,
    nationality,
    tenant_type,
    application_count,
    movein_count,
    application_to_movein_rate
FROM combined
WHERE application_count < 0
   OR movein_count < 0
   OR movein_count > application_count
   OR application_to_movein_rate IS NULL
   OR application_to_movein_rate < 0
   OR application_to_movein_rate > 1
   OR (application_count = 0 AND application_to_movein_rate <> 0)
   OR (
       application_count > 0
       AND ABS(
           application_to_movein_rate - (movein_count / application_count)
       ) > 0.0001
   )
