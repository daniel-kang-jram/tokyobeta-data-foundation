{{ config(severity='error') }}

WITH reference_values AS (
    SELECT
        CAST('2026-01-31' AS DATE) AS jan_month_end_date,
        CAST(0.707 AS DECIMAL(10, 6)) AS jan_occupancy_rate_ref,
        CAST(56195 AS DECIMAL(12, 2)) AS jan_rent_ref,
        CAST(39757 AS DECIMAL(12, 2)) AS jan_revpar_ref,
        CAST(37826 AS DECIMAL(12, 2)) AS jan_recpar_cash_ref,
        CAST('2026-02-01' AS DATE) AS feb_first_date,
        CAST(11271 AS DECIMAL(12, 2)) AS feb_occupancy_rooms_0000_ref,
        CAST(0.020 AS DECIMAL(10, 6)) AS occupancy_rate_tolerance,
        CAST(2500 AS DECIMAL(12, 2)) AS monetary_tolerance,
        CAST(30 AS DECIMAL(12, 2)) AS room_count_tolerance
),

kpi AS (
    SELECT
        as_of_date,
        occupancy_rate,
        rent_jpy,
        revpar_jpy,
        recpar_cash_jpy,
        occupancy_room_count_0000
    FROM {{ ref('kpi_month_end_metrics') }}
),

benchmark_checks AS (
    SELECT
        'jan_2026_month_end_occupancy_rate' AS benchmark_name,
        rv.jan_occupancy_rate_ref AS expected_value,
        k.occupancy_rate AS actual_value,
        rv.occupancy_rate_tolerance AS tolerance
    FROM reference_values rv
    LEFT JOIN kpi k
        ON k.as_of_date = rv.jan_month_end_date

    UNION ALL

    SELECT
        'jan_2026_month_end_rent_jpy' AS benchmark_name,
        rv.jan_rent_ref AS expected_value,
        k.rent_jpy AS actual_value,
        rv.monetary_tolerance AS tolerance
    FROM reference_values rv
    LEFT JOIN kpi k
        ON k.as_of_date = rv.jan_month_end_date

    UNION ALL

    SELECT
        'jan_2026_month_end_revpar_jpy' AS benchmark_name,
        rv.jan_revpar_ref AS expected_value,
        k.revpar_jpy AS actual_value,
        rv.monetary_tolerance AS tolerance
    FROM reference_values rv
    LEFT JOIN kpi k
        ON k.as_of_date = rv.jan_month_end_date

    UNION ALL

    SELECT
        'jan_2026_month_end_recpar_cash_jpy' AS benchmark_name,
        rv.jan_recpar_cash_ref AS expected_value,
        k.recpar_cash_jpy AS actual_value,
        rv.monetary_tolerance AS tolerance
    FROM reference_values rv
    LEFT JOIN kpi k
        ON k.as_of_date = rv.jan_month_end_date

    UNION ALL

    SELECT
        'feb_2026_0000_occupancy_rooms' AS benchmark_name,
        rv.feb_occupancy_rooms_0000_ref AS expected_value,
        k.occupancy_room_count_0000 AS actual_value,
        rv.room_count_tolerance AS tolerance
    FROM reference_values rv
    LEFT JOIN kpi k
        ON k.as_of_date = rv.feb_first_date
)

SELECT
    benchmark_name,
    expected_value,
    actual_value,
    tolerance,
    ABS(ROUND(actual_value, 6) - ROUND(expected_value, 6)) AS absolute_diff
FROM benchmark_checks
WHERE actual_value IS NULL
   OR ABS(ROUND(actual_value, 6) - ROUND(expected_value, 6)) > tolerance
