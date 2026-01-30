

-- Table 1: Daily Activity Summary
-- Aggregates daily property management activities by individual/corporate tenant type
-- グラニュラリティ: Daily
-- データ: 申し込み, 契約締結, 確定入居者, 確定退去者, 稼働室数増減 (by 個人 and 法人)

WITH applications AS (
    SELECT
        DATE(m.created_at) as activity_date,
        
    CASE 
        WHEN m.moving_agreement_type IN (2, 3, 4) THEN 'corporate'
        ELSE 'individual'
    END
 as tenant_type,
        COUNT(*) as application_count
    FROM `staging`.`movings` m
    WHERE m.created_at IS NOT NULL
      AND m.created_at >= '2018-01-01'
    GROUP BY DATE(m.created_at), tenant_type
),

contracts_signed AS (
    SELECT
        DATE(m.movein_decided_date) as activity_date,
        
    CASE 
        WHEN m.moving_agreement_type IN (2, 3, 4) THEN 'corporate'
        ELSE 'individual'
    END
 as tenant_type,
        COUNT(*) as contract_signed_count
    FROM `staging`.`movings` m
    WHERE m.movein_decided_date IS NOT NULL
      AND m.cancel_flag = 0
      AND m.movein_decided_date >= '2018-01-01'
    GROUP BY DATE(m.movein_decided_date), tenant_type
),

confirmed_movein AS (
    SELECT
        DATE(m.movein_date) as activity_date,
        
    CASE 
        WHEN m.moving_agreement_type IN (2, 3, 4) THEN 'corporate'
        ELSE 'individual'
    END
 as tenant_type,
        COUNT(*) as movein_count
    FROM `staging`.`movings` m
    WHERE m.movein_date IS NOT NULL
      AND m.cancel_flag = 0
      AND m.movein_date >= '2018-01-01'
    GROUP BY DATE(m.movein_date), tenant_type
),

confirmed_moveout AS (
    SELECT
        DATE(
    
        COALESCE(m.moveout_date_integrated, m.moveout_plans_date, m.moveout_date)
    
) as activity_date,
        
    CASE 
        WHEN m.moving_agreement_type IN (2, 3, 4) THEN 'corporate'
        ELSE 'individual'
    END
 as tenant_type,
        COUNT(*) as moveout_count
    FROM `staging`.`movings` m
    WHERE 
    
        COALESCE(m.moveout_date_integrated, m.moveout_plans_date, m.moveout_date)
    
 IS NOT NULL
      AND m.is_moveout = 1
      AND DATE(
    
        COALESCE(m.moveout_date_integrated, m.moveout_plans_date, m.moveout_date)
    
) >= '2018-01-01'
    GROUP BY DATE(
    
        COALESCE(m.moveout_date_integrated, m.moveout_plans_date, m.moveout_date)
    
), tenant_type
),

-- Generate all dates in the range
date_spine AS (
    SELECT DISTINCT
        activity_date,
        tenant_type
    FROM (
        SELECT activity_date, tenant_type FROM applications
        UNION SELECT activity_date, tenant_type FROM contracts_signed
        UNION SELECT activity_date, tenant_type FROM confirmed_movein
        UNION SELECT activity_date, tenant_type FROM confirmed_moveout
    ) all_dates
),

final AS (
    SELECT
        ds.activity_date,
        ds.tenant_type,
        COALESCE(app.application_count, 0) as applications_count,
        COALESCE(cs.contract_signed_count, 0) as contracts_signed_count,
        COALESCE(mi.movein_count, 0) as confirmed_moveins_count,
        COALESCE(mo.moveout_count, 0) as confirmed_moveouts_count,
        COALESCE(mi.movein_count, 0) - COALESCE(mo.moveout_count, 0) as net_occupancy_delta,
        CURRENT_TIMESTAMP as created_at,
        CURRENT_TIMESTAMP as updated_at
    FROM date_spine ds
    LEFT JOIN applications app
        ON ds.activity_date = app.activity_date
        AND ds.tenant_type = app.tenant_type
    LEFT JOIN contracts_signed cs
        ON ds.activity_date = cs.activity_date
        AND ds.tenant_type = cs.tenant_type
    LEFT JOIN confirmed_movein mi
        ON ds.activity_date = mi.activity_date
        AND ds.tenant_type = mi.tenant_type
    LEFT JOIN confirmed_moveout mo
        ON ds.activity_date = mo.activity_date
        AND ds.tenant_type = mo.tenant_type
)

SELECT * FROM final
ORDER BY activity_date DESC, tenant_type