{{
  config(
    materialized='table',
    schema='gold',
    indexes=[
      {'columns': ['moveout_date', 'rent_range'], 'type': 'btree'},
      {'columns': ['moveout_year_month'], 'type': 'btree'},
      {'columns': ['prefecture', 'tenant_type'], 'type': 'btree'}
    ]
  )
}}

-- Gold Layer: Moveout Summary (Pre-aggregated)
-- Daily aggregated moveout counts by rent range, geography, and tenant type
-- Optimized for dashboard queries and landscape analysis

SELECT
    moveout_date,
    DATE_FORMAT(moveout_date, '%Y-%m') as moveout_year_month,
    
    -- Grouping dimensions
    rent_range,
    rent_range_order,
    prefecture,
    tenant_type,
    
    -- Aggregate metrics
    COUNT(*) as moveout_count,
    
    -- Financial averages
    AVG(monthly_rent) as avg_monthly_rent,
    MIN(monthly_rent) as min_monthly_rent,
    MAX(monthly_rent) as max_monthly_rent,
    
    -- Tenure averages
    AVG(total_stay_months) as avg_tenure_months,
    AVG(total_stay_days) as avg_tenure_days,
    
    -- Gender breakdown
    SUM(CASE WHEN gender = 'Male' THEN 1 ELSE 0 END) as gender_male_count,
    SUM(CASE WHEN gender = 'Female' THEN 1 ELSE 0 END) as gender_female_count,
    SUM(CASE WHEN gender NOT IN ('Male', 'Female') OR gender IS NULL THEN 1 ELSE 0 END) as gender_other_count,
    
    -- Age group breakdown
    SUM(CASE WHEN age_group = 'Under 25' THEN 1 ELSE 0 END) as age_under_25_count,
    SUM(CASE WHEN age_group = '25-34' THEN 1 ELSE 0 END) as age_25_34_count,
    SUM(CASE WHEN age_group = '35-44' THEN 1 ELSE 0 END) as age_35_44_count,
    SUM(CASE WHEN age_group = '45-54' THEN 1 ELSE 0 END) as age_45_54_count,
    SUM(CASE WHEN age_group = '55+' THEN 1 ELSE 0 END) as age_55_plus_count,
    
    -- Tenure category breakdown
    SUM(CASE WHEN tenure_category = 'Short (<6mo)' THEN 1 ELSE 0 END) as tenure_short_count,
    SUM(CASE WHEN tenure_category = 'Medium (6-12mo)' THEN 1 ELSE 0 END) as tenure_medium_count,
    SUM(CASE WHEN tenure_category = 'Long (1-2yr)' THEN 1 ELSE 0 END) as tenure_long_count,
    SUM(CASE WHEN tenure_category = 'Very Long (2yr+)' THEN 1 ELSE 0 END) as tenure_very_long_count,
    
    -- Renewal breakdown
    SUM(CASE WHEN renewal_flag = 'Yes' THEN 1 ELSE 0 END) as renewal_yes_count,
    SUM(CASE WHEN renewal_flag = 'No' THEN 1 ELSE 0 END) as renewal_no_count,
    
    -- Top moveout reasons (as arrays for drill-down)
    COUNT(DISTINCT moveout_reason_en) as distinct_moveout_reasons,
    
    -- Metadata
    CURRENT_TIMESTAMP as created_at,
    CURRENT_TIMESTAMP as updated_at

FROM {{ ref('moveout_analysis') }}
GROUP BY 
    moveout_date,
    moveout_year_month,
    rent_range,
    rent_range_order,
    prefecture,
    tenant_type
ORDER BY 
    moveout_date DESC,
    rent_range_order,
    prefecture,
    tenant_type
