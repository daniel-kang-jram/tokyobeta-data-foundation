{{
  config(
    materialized='table',
    schema='gold',
    indexes=[
      {'columns': ['event_date'], 'type': 'btree'},
      {'columns': ['week_start'], 'type': 'btree'},
      {'columns': ['event_type'], 'type': 'btree'}
    ]
  )
}}

-- Gold Layer: Unified Move Events (Weekly-first)
-- Union of move-ins and move-outs at the contract grain.
-- Grain: 1 row per (event_type, contract_id).

WITH moveins AS (
    SELECT
        CONCAT('movein-', CAST(contract_id AS CHAR)) AS event_id,
        'movein' AS event_type,
        contract_start_date AS event_date,
        DATE_SUB(contract_start_date, INTERVAL WEEKDAY(contract_start_date) DAY) AS week_start,
        DATE_FORMAT(contract_start_date, '%Y-%m-01') AS month_start,

        asset_id_hj,
        apartment_name,
        prefecture,
        municipality,
        latitude,
        longitude,

        tenant_type,
        gender,
        age,
        age_group,
        nationality,

        monthly_rent,
        rent_range,
        rent_range_order,

        lead_time_bucket,
        NULL AS tenure_category,
        NULL AS moveout_reason_en,
        NULL AS notice_lead_time_days,

        1 AS event_count
    FROM {{ ref('movein_analysis') }}
),

moveouts AS (
    SELECT
        CONCAT('moveout-', CAST(contract_id AS CHAR)) AS event_id,
        'moveout' AS event_type,
        moveout_date AS event_date,
        DATE_SUB(moveout_date, INTERVAL WEEKDAY(moveout_date) DAY) AS week_start,
        DATE_FORMAT(moveout_date, '%Y-%m-01') AS month_start,

        asset_id_hj,
        apartment_name,
        prefecture,
        municipality,
        latitude,
        longitude,

        tenant_type,
        gender,
        age,
        age_group,
        nationality,

        monthly_rent,
        rent_range,
        rent_range_order,

        NULL AS lead_time_bucket,
        tenure_category,
        moveout_reason_en,
        notice_lead_time_days,

        1 AS event_count
    FROM {{ ref('moveout_analysis') }}
    WHERE moveout_date <= CURRENT_DATE
)

SELECT
    event_id,
    event_type,
    event_date,
    week_start,
    month_start,
    asset_id_hj,
    apartment_name,
    prefecture,
    municipality,
    latitude,
    longitude,
    tenant_type,
    gender,
    age,
    age_group,
    nationality,
    monthly_rent,
    rent_range,
    rent_range_order,
    lead_time_bucket,
    tenure_category,
    moveout_reason_en,
    notice_lead_time_days,
    event_count,
    CURRENT_TIMESTAMP AS created_at,
    CURRENT_TIMESTAMP AS updated_at
FROM moveins

UNION ALL

SELECT
    event_id,
    event_type,
    event_date,
    week_start,
    month_start,
    asset_id_hj,
    apartment_name,
    prefecture,
    municipality,
    latitude,
    longitude,
    tenant_type,
    gender,
    age,
    age_group,
    nationality,
    monthly_rent,
    rent_range,
    rent_range_order,
    lead_time_bucket,
    tenure_category,
    moveout_reason_en,
    notice_lead_time_days,
    event_count,
    CURRENT_TIMESTAMP AS created_at,
    CURRENT_TIMESTAMP AS updated_at
FROM moveouts
