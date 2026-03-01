{{
  config(
    materialized='table',
    schema='gold',
    indexes=[
      {'columns': ['activity_date'], 'type': 'btree'},
      {'columns': ['municipality'], 'type': 'btree'},
      {'columns': ['nationality'], 'type': 'btree'},
      {'columns': ['tenant_type'], 'type': 'btree'}
    ]
  )
}}

-- Gold Layer: Daily application -> move-in funnel by key segments.
-- Grain: (activity_date, municipality, nationality, tenant_type)

WITH inquiries AS (
    SELECT
        inquiry_id,
        tenant_id,
        inquiry_date
    FROM {{ ref('stg_inquiries') }}
    WHERE inquiry_date IS NOT NULL
),

inquiry_contract_candidates AS (
    SELECT
        i.inquiry_id,
        i.inquiry_date,
        c.contract_id,
        c.contract_start_date AS movein_date,
        COALESCE(NULLIF(TRIM(c.municipality), ''), 'unknown') AS municipality,
        COALESCE(NULLIF(TRIM(c.nationality), ''), 'unknown') AS nationality,
        CASE
            WHEN c.tenant_type IN ('individual', 'corporate') THEN c.tenant_type
            ELSE 'unknown'
        END AS tenant_type,
        ROW_NUMBER() OVER (
            PARTITION BY i.inquiry_id
            ORDER BY
                CASE
                    WHEN c.contract_start_date >= i.inquiry_date THEN 0
                    ELSE 1
                END,
                ABS(DATEDIFF(c.contract_start_date, i.inquiry_date)),
                c.contract_id
        ) AS rn
    FROM inquiries i
    INNER JOIN {{ ref('int_contracts') }} c
        ON i.tenant_id = c.tenant_id
    WHERE c.contract_start_date IS NOT NULL
      AND c.is_valid_contract
),

inquiries_enriched AS (
    SELECT
        i.inquiry_id,
        i.inquiry_date AS activity_date,
        COALESCE(c.municipality, 'unknown') AS municipality,
        COALESCE(c.nationality, 'unknown') AS nationality,
        COALESCE(c.tenant_type, 'unknown') AS tenant_type,
        CASE
            WHEN c.contract_id IS NOT NULL
             AND c.movein_date >= i.inquiry_date THEN 1
            ELSE 0
        END AS movein_conversion_count
    FROM inquiries i
    LEFT JOIN inquiry_contract_candidates c
        ON i.inquiry_id = c.inquiry_id
       AND c.rn = 1
)

SELECT
    activity_date,
    municipality,
    nationality,
    tenant_type,
    COUNT(*) AS application_count,
    SUM(movein_conversion_count) AS movein_count,
    CAST(
        COALESCE(
            SUM(movein_conversion_count) / NULLIF(COUNT(*), 0),
            0
        ) AS DECIMAL(12, 4)
    ) AS application_to_movein_rate,
    CURRENT_TIMESTAMP AS created_at,
    CURRENT_TIMESTAMP AS updated_at
FROM inquiries_enriched
GROUP BY
    activity_date,
    municipality,
    nationality,
    tenant_type
ORDER BY
    activity_date,
    municipality,
    nationality,
    tenant_type
