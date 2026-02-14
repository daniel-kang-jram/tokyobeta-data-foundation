{{
  config(
    materialized='table',
    schema='gold',
    indexes=[
      {'columns': ['contract_start_date'], 'type': 'btree'},
      {'columns': ['asset_id_hj'], 'type': 'btree'},
      {'columns': ['tenant_type'], 'type': 'btree'}
    ]
  )
}}

-- Gold Layer: Move-in Analysis (Enriched)
-- Mirrors gold.moveout_analysis with categorical dimensions for move-in profiling.
-- Grain: 1 row per contract_id (move-in contract).

WITH base AS (
    SELECT
        nc.contract_id,
        nc.asset_id_hj,
        nc.room_number,
        nc.contract_date,
        nc.contract_start_date,
        nc.rent_start_date,
        nc.contract_expiration_date,
        nc.original_contract_date,
        nc.monthly_rent,
        nc.tenant_type,
        nc.contract_system,
        nc.contract_channel,
        nc.gender,
        nc.age,
        nc.nationality,
        nc.occupation_company,
        ic.affiliation_type_en AS occupation_industry,
        nc.residence_status,
        nc.prefecture,
        nc.municipality,
        nc.latitude,
        nc.longitude,
        nc.apartment_name
    FROM {{ ref('new_contracts') }} nc
    LEFT JOIN {{ ref('int_contracts') }} ic
        ON ic.contract_id = nc.contract_id
    WHERE nc.contract_start_date IS NOT NULL
      AND nc.contract_start_date >= '{{ var('min_valid_date') }}'
      AND nc.contract_start_date <= CURRENT_DATE
      AND nc.latitude IS NOT NULL
      AND nc.longitude IS NOT NULL
      AND nc.monthly_rent IS NOT NULL
)

SELECT
    contract_id,
    asset_id_hj,
    room_number,
    contract_date,
    contract_start_date,
    rent_start_date,
    contract_expiration_date,
    original_contract_date,
    monthly_rent,
    tenant_type,
    contract_system,
    contract_channel,
    gender,
    age,

    -- Age Group
    CASE
        WHEN age IS NULL THEN 'Unknown'
        WHEN age < 25 THEN 'Under 25'
        WHEN age < 35 THEN '25-34'
        WHEN age < 45 THEN '35-44'
        WHEN age < 55 THEN '45-54'
        ELSE '55+'
    END AS age_group,

    nationality,
    occupation_company,
    occupation_industry,
    residence_status,

    -- Geography
    prefecture,
    municipality,
    latitude,
    longitude,
    apartment_name,

    -- Rent Range Categorization
    CASE
        WHEN monthly_rent < 50000 THEN 'Under 50K'
        WHEN monthly_rent < 70000 THEN '50K-70K'
        WHEN monthly_rent < 100000 THEN '70K-100K'
        WHEN monthly_rent < 150000 THEN '100K-150K'
        ELSE '150K+'
    END AS rent_range,

    CASE
        WHEN monthly_rent < 50000 THEN 1
        WHEN monthly_rent < 70000 THEN 2
        WHEN monthly_rent < 100000 THEN 3
        WHEN monthly_rent < 150000 THEN 4
        ELSE 5
    END AS rent_range_order,

    -- Lead time from contract signing to move-in start
    DATEDIFF(contract_start_date, contract_date) AS lead_time_days,

    CASE
        WHEN contract_date IS NULL THEN 'Unknown'
        WHEN contract_start_date IS NULL THEN 'Unknown'
        WHEN DATEDIFF(contract_start_date, contract_date) < 0 THEN 'Unknown'
        WHEN DATEDIFF(contract_start_date, contract_date) <= 7 THEN '0-7'
        WHEN DATEDIFF(contract_start_date, contract_date) <= 30 THEN '8-30'
        WHEN DATEDIFF(contract_start_date, contract_date) <= 60 THEN '31-60'
        ELSE '61+'
    END AS lead_time_bucket,

    TIMESTAMPDIFF(
        MONTH,
        contract_start_date,
        contract_expiration_date
    ) AS planned_stay_months,

    -- Metadata
    CURRENT_TIMESTAMP AS created_at,
    CURRENT_TIMESTAMP AS updated_at

FROM base
ORDER BY contract_start_date DESC, asset_id_hj, room_number
