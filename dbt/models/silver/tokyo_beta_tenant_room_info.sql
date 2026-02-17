{{
    config(
        materialized='table',
        schema='silver'
    )
}}

/*
Tokyo Beta Tenant-Room Information (Reproduced from Database)

This model reproduces the structure of the Excel export "Tokyo Beta テナント情報.xlsx"
by querying staging tables. It creates one row per tenant-room assignment.

Data Sources:
- staging.tenants: Demographics, contact info, status
- staging.movings: Tenant-room assignments, dates
- staging.apartments: Property/building names
- staging.rooms: Room numbers

Expected output: ~12,000 rows (filtered by active status)

Corporate tenants naturally get multiple rows (one per unique room).
Individual tenants get one row (most recent moving per room).

IMPORTANT: is_moveout flag is unreliable due to historical data entry errors.
We use ROW_NUMBER() to select the most recent moving per tenant-room combination.
*/

WITH all_active_movings AS (
    -- Get all movings for tenants in target statuses
    -- Include is_moveout=0 to filter out definite moveouts
    SELECT
        t.id as tenant_id,
        t.status as management_status_code,
        COALESCE(
            NULLIF(TRIM(t.full_name), ''),
            NULLIF(
                CONCAT_WS(
                    ' ',
                    NULLIF(TRIM(t.last_name), ''),
                    NULLIF(TRIM(t.first_name), '')
                ),
                ''
            )
        ) as tenant_name,
        t.full_name_kana as tenant_name_kana,
        m.moving_agreement_type as contract_type,  -- Use moving_agreement_type (original), not tenant.contract_type
        t.gender_type as gender_code,
        t.age,
        t.nationality,
        -- Contact info (found in schema)
        t.email_1,
        t.email_2,
        t.tel_1,
        t.tel_2,
        t.account_number,
        t.m_language_id_1,
        
        m.rent as fixed_rent,
        m.movein_date as move_in_date,
        m.moveout_date as moveout_date,  -- 最終賃料日
        m.moveout_date_integrated as moveout_date_integrated,
        m.moveout_plans_date as moveout_plans_date,  -- 実退去日
        DATEDIFF(
            COALESCE(m.moveout_date, CURDATE()),
            m.movein_date
        ) as days_stayed,
        m.apartment_id,
        m.room_id,
        m.id as moving_id,
        m.created_at,
        m.updated_at,
        -- Rank movings per tenant-room: most recent first
        -- This handles duplicate historical records that weren't properly closed
        ROW_NUMBER() OVER (
            PARTITION BY t.id, m.apartment_id, m.room_id 
            ORDER BY m.movein_date DESC, m.updated_at DESC, m.id DESC
        ) as rn
    FROM {{ source('staging', 'tenants') }} t
    INNER JOIN {{ source('staging', 'movings') }} m
        ON t.moving_id = m.id  -- Use tenant.moving_id as primary link (matches Excel logic)
    WHERE 
        -- Filter 1: Current tenant status matches target statuses
        t.status IN (
            4,   -- 仮予約 (Tentative Reservation)
            5,   -- 初回家賃入金 (Initial Rent) - DB: 初期賃料
            6,   -- 入居説明 (Move-in Explanation)
            7,   -- 入居 (Move-in)
            9,   -- 入居中 (In Residence) - DB: 居住中
            10,  -- 契約更新 (Contract Renewal)
            11,  -- 移動届受領 (Transfer Notice Received) - DB: 入居通知
            12,  -- 移動手続き (Transfer Procedure) - DB: 入居手続き
            13,  -- 移動 (Move/Transfer)
            14,  -- 退去届受領 (Move-out Notice Received) - DB: 退去通知
            15   -- 退去予定 (Expected Move-out)
        )
        -- Filter 2: Only movings marked as active (is_moveout = 0)
        AND m.is_moveout = 0
        -- Filter 3: Exclude cancelled contracts for UI parity
        AND COALESCE(m.cancel_flag, 0) = 0
),

tenant_room_assignments AS (
    -- Take only the most recent moving per tenant-room combination
    -- This eliminates duplicate historical records
    SELECT
        tenant_id,
        management_status_code,
        tenant_name,
        tenant_name_kana,
        -- Nickname not in database, will be NULL
        NULL as nickname,
        contract_type,
        gender_code,
        age,
        nationality,
        -- Languages
        m_language_id_1,
        NULL as language_1, -- Placeholder as m_languages table is missing
        NULL as language_2,
        -- Contact info
        tel_1 as phone_1,
        tel_2 as phone_2,
        email_1,
        email_2,
        -- Financial
        account_number,
        fixed_rent,
        -- Dates
        move_in_date,
        COALESCE(moveout_date_integrated, moveout_plans_date, moveout_date) AS moveout_date,
        moveout_plans_date,
        days_stayed,
        -- Foreign keys for joins
        apartment_id,
        room_id,
        moving_id
    FROM all_active_movings
    WHERE rn = 1  -- Only the most recent moving per tenant-room
),

with_property_room AS (
    -- Add property and room information
    SELECT
        tra.*,
        a.apartment_name as property,
        r.room_number
    FROM tenant_room_assignments tra
    LEFT JOIN {{ source('staging', 'apartments') }} a
        ON tra.apartment_id = a.id
    LEFT JOIN {{ source('staging', 'rooms') }} r
        ON tra.room_id = r.id
),

final AS (
    SELECT
        -- Status
        management_status_code,
        CASE management_status_code
            WHEN 4 THEN '仮予約'
            WHEN 5 THEN '初回家賃入金'
            WHEN 6 THEN '入居説明'
            WHEN 7 THEN '入居'
            WHEN 9 THEN '入居中'
            WHEN 10 THEN '契約更新'
            WHEN 11 THEN '移動届受領'
            WHEN 12 THEN '移動手続き'
            WHEN 13 THEN '移動'
            WHEN 14 THEN '退去届受領'
            WHEN 15 THEN '退去予定'
            ELSE 'Unknown'
        END as management_status,
        
        -- Tenant identification
        tenant_id,
        tenant_name,
        tenant_name_kana,
        nickname,
        
        -- Property/Room
        property,
        room_number,
        
        -- Contract category
        CASE contract_type
            WHEN 1 THEN '一般'
            WHEN 2 THEN '法人契約'
            WHEN 3 THEN '法人契約（個人）'
            WHEN 6 THEN '定期契約'
            WHEN 7 THEN '一般（保証会社）'  -- Current source code for guarantor contracts
            WHEN 9 THEN '一般2'
            ELSE '一般2'  -- Default fallback
        END as contract_category,
        
        -- Demographics
        CASE gender_code
            WHEN 1 THEN '男性'
            WHEN 2 THEN '女性'
            ELSE NULL
        END as gender,
        CONCAT(age, '歳') as age_display,
        nationality,
        
        -- Contact
        language_1, -- Currently NULL as m_languages missing
        language_2,
        phone_1,
        phone_2,
        email_1,
        email_2,
        
        -- Financial
        account_number,
        fixed_rent,
        
        -- Dates
        move_in_date,
        moveout_date,
        moveout_plans_date,
        days_stayed,
        
        -- Metadata
        moving_id,
        CURRENT_TIMESTAMP as dbt_updated_at
        
    FROM with_property_room
)

SELECT * FROM final
ORDER BY tenant_name, property, room_number
