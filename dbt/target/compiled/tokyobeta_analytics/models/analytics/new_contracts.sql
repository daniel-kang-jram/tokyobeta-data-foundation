

-- Table 2: New Contracts with Demographics + Geolocation
-- 新規: AssetID_HJ, Room Number, 契約体系, 契約チャンネル, 原契約締結日, 契約締結日, 契約開始日,
--      賃料発生日, 契約満了日, 再契約フラグ, 月額賃料, 個人・法人フラグ, 性別, 年齢, 
--      国籍, 職種, 在留資格, latitude, longitude

WITH new_contracts_base AS (
    SELECT
        m.id as contract_id,
        m.tenant_id,
        a.unique_number as asset_id_hj,
        r.room_number as room_number,
        m.moving_agreement_type as contract_system,
        t.media_id as contract_channel,
        m.original_movein_date as original_contract_date,
        DATE(m.movein_decided_date) as contract_date,
        m.movein_date as contract_start_date,
        m.rent_start_date as rent_start_date,
        m.expiration_date as contract_expiration_date,
        CASE WHEN m.move_renew_flag = 1 THEN 'Yes' ELSE 'No' END as renewal_flag,
        m.rent as monthly_rent,
        
    CASE 
        WHEN m.moving_agreement_type IN (2, 3, 4) THEN 'corporate'
        ELSE 'individual'
    END
 as tenant_type,
        CASE 
            WHEN t.gender_type = 1 THEN 'Male'
            WHEN t.gender_type = 2 THEN 'Female'
            ELSE 'Other'
        END as gender,
        COALESCE(t.age, TIMESTAMPDIFF(YEAR, t.birth_date, CURRENT_DATE)) as age,
        COALESCE(t.nationality, n.nationality_name) as nationality,
        
    CASE 
        WHEN t.affiliation IN ('NULL', '--', 'null', '') THEN NULL
        ELSE t.affiliation
    END
 as occupation_company,
        
    CASE 
        WHEN t.personal_identity IN ('NULL', '--', 'null', '') THEN NULL
        ELSE t.personal_identity
    END
 as residence_status,
        a.latitude,
        a.longitude,
        a.prefecture,
        a.municipality,
        a.full_address,
        CURRENT_TIMESTAMP as created_at,
        CURRENT_TIMESTAMP as updated_at
    FROM `staging`.`movings` m
    INNER JOIN `staging`.`tenants` t
        ON m.tenant_id = t.id
    INNER JOIN `staging`.`apartments` a
        ON m.apartment_id = a.id
    INNER JOIN `staging`.`rooms` r
        ON m.room_id = r.id
    LEFT JOIN `staging`.`m_nationalities` n
        ON t.m_nationality_id = n.id
    WHERE m.movein_decided_date IS NOT NULL
      AND m.cancel_flag = 0
      AND DATE(m.movein_decided_date) >= '2018-01-01'
)

SELECT *
FROM new_contracts_base
WHERE latitude IS NOT NULL  -- Only contracts with valid geocoding
  AND longitude IS NOT NULL
ORDER BY contract_date DESC, asset_id_hj, room_number