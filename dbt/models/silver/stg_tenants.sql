{{
  config(
    materialized='view',
    schema='silver'
  )
}}

-- Silver Layer: Cleaned tenants with demographic labels
-- Transforms raw tenant data with semantic values and cleaned NULL strings

SELECT
    t.id as tenant_id,
    
    -- Name fields (cleaned)
    {{ clean_string_null('t.full_name') }} as full_name,
    t.last_name,
    t.first_name,
    t.full_name_kana,
    
    -- Demographics with semantic labels
    t.gender_type as gender_code,
    g.label_ja as gender_ja,
    g.label_en as gender,
    
    -- Age (prefer calculated from birth_date)
    t.birth_date,
    COALESCE(t.age, TIMESTAMPDIFF(YEAR, t.birth_date, CURRENT_DATE)) as age,
    
    -- Nationality with LLM enrichment fallback
    t.m_nationality_id,
    CASE 
        -- Priority 1: Use original nationality if valid (not placeholder)
        WHEN {{ clean_string_null('t.nationality') }} IS NOT NULL 
             AND t.nationality != 'レソト'
        THEN {{ clean_string_null('t.nationality') }}
        
        -- Priority 2: Use lookup table nationality_name (but not if it's レソト)
        WHEN n.nationality_name IS NOT NULL
             AND n.nationality_name != 'レソト'
        THEN n.nationality_name
        
        -- Priority 3: Fallback to "その他 (Unknown)"
        ELSE 'その他'
    END as nationality,
    
    -- LLM-predicted nationality (from cache table)
    llm_cache.llm_nationality,
    llm_cache.llm_confidence,
    llm_cache.enriched_at as llm_enriched_at,
    
    -- Data quality flag for nationality (matches priority order above)
    CASE 
        WHEN {{ clean_string_null('t.nationality') }} IS NOT NULL 
             AND t.nationality != 'レソト'
        THEN 'original'
        WHEN n.nationality_name IS NOT NULL
             AND n.nationality_name != 'レソト'
        THEN 'lookup_table'
        WHEN t.nationality = 'レソト' OR n.nationality_name = 'レソト'
        THEN 'lesotho_placeholder'
        ELSE 'missing'
    END as nationality_data_source,
    
    -- Personal identity with semantic label
    t.personal_identity as personal_identity_raw,
    pi.label_ja as personal_identity_ja,
    pi.label_en as personal_identity_en,
    
    -- Employment/affiliation
    {{ clean_string_null('t.affiliation') }} as affiliation,
    t.affiliation_type as affiliation_type_code,
    at.label_ja as affiliation_type_ja,
    at.label_en as affiliation_type_en,
    
    -- Tenant status with active lease flag
    t.status as tenant_status_code,
    ts.label_ja as tenant_status_ja,
    ts.label_en as tenant_status_en,
    ts.is_active_lease,
    
    -- Contract metadata
    t.contract_type,
    t.media_id as contract_channel,
    
    -- Moveout reason
    t.reason_moveout as moveout_reason_code,
    mr.label_ja as moveout_reason_ja,
    mr.label_en as moveout_reason_en,
    
    -- Metadata
    t.created_at,
    t.updated_at

FROM {{ source('staging', 'tenants') }} t
LEFT JOIN {{ ref('code_gender') }} g
    ON t.gender_type = g.code
LEFT JOIN {{ ref('code_tenant_status') }} ts
    ON t.status = ts.code
LEFT JOIN {{ ref('code_personal_identity') }} pi
    ON CAST(t.personal_identity AS UNSIGNED) = pi.code
LEFT JOIN {{ ref('code_affiliation_type') }} at
    ON t.affiliation_type = at.code
LEFT JOIN {{ ref('code_moveout_reason') }} mr
    ON t.reason_moveout = mr.code
LEFT JOIN {{ source('staging', 'm_nationalities') }} n
    ON t.m_nationality_id = n.id
-- Join with LLM enrichment cache (persistent across staging reloads)
LEFT JOIN {{ source('staging', 'llm_enrichment_cache') }} llm_cache
    ON t.id = llm_cache.tenant_id
WHERE t.id IS NOT NULL
