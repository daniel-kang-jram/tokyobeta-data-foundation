{{ config(severity='error') }}

-- Test: Ensure segmented funnel outputs include required dimensions and
-- expose daily/weekly/monthly grains whenever source inquiries exist.

WITH periodized AS (
    SELECT
        period_grain,
        period_start,
        municipality,
        nationality,
        tenant_type
    FROM {{ ref('funnel_application_to_movein_periodized') }}
),

segment_share AS (
    SELECT
        period_grain,
        period_start,
        tenant_type,
        segment_type,
        segment_value
    FROM {{ ref('funnel_application_to_movein_segment_share') }}
),

source_activity AS (
    SELECT COUNT(*) AS inquiry_rows
    FROM {{ ref('stg_inquiries') }}
    WHERE inquiry_date IS NOT NULL
),

invalid_dimensions AS (
    SELECT
        period_grain,
        period_start,
        municipality,
        nationality,
        tenant_type,
        'invalid_dimension' AS failure_reason
    FROM periodized
    WHERE municipality IS NULL
       OR TRIM(municipality) = ''
       OR nationality IS NULL
       OR TRIM(nationality) = ''
       OR tenant_type NOT IN ('individual', 'corporate', 'unknown')
),

invalid_segment_dimensions AS (
    SELECT
        period_grain,
        period_start,
        segment_value AS municipality,
        segment_type AS nationality,
        tenant_type,
        'invalid_segment_dimension' AS failure_reason
    FROM segment_share
    WHERE segment_type NOT IN ('municipality', 'nationality')
       OR segment_value IS NULL
       OR TRIM(segment_value) = ''
       OR tenant_type NOT IN ('individual', 'corporate', 'unknown')
),

missing_grains AS (
    SELECT
        required_grains.expected_grain AS period_grain,
        NULL AS period_start,
        NULL AS municipality,
        NULL AS nationality,
        NULL AS tenant_type,
        'missing_period_grain' AS failure_reason
    FROM (
        SELECT 'daily' AS expected_grain
        UNION ALL
        SELECT 'weekly' AS expected_grain
        UNION ALL
        SELECT 'monthly' AS expected_grain
    ) required_grains
    LEFT JOIN (
        SELECT DISTINCT period_grain
        FROM periodized
    ) actual_grains
        ON required_grains.expected_grain = actual_grains.period_grain
    WHERE actual_grains.period_grain IS NULL
      AND (SELECT inquiry_rows FROM source_activity) > 0
)

SELECT *
FROM invalid_dimensions

UNION ALL

SELECT *
FROM invalid_segment_dimensions

UNION ALL

SELECT *
FROM missing_grains
