{{
    config(
        materialized='incremental',
        incremental_strategy='append',
        pre_hook="SET SESSION innodb_lock_wait_timeout = 120",
        on_schema_change='append_new_columns',
        schema='silver'
    )
}}

/*
Daily Tenant-Room Snapshot (Incremental)

Captures daily snapshots of all active tenant-room pairs for occupancy tracking and KPI calculation.
Stores only core fields. Demographic/contact enrichment happens in downstream marts via joins.

Data Sources:
- staging.tenants: Status, tenant info
- staging.movings: Room assignments, dates
- staging.apartments: Property names
- staging.rooms: Room numbers

Grain: One row per (snapshot_date, tenant_id, apartment_id, room_id) combination.

Two levels of deduplication:
  1. Per (tenant_id, apartment_id, room_id): rn = 1 keeps the most recent moving record,
     eliminating ~3,500 duplicate historical corporate contract entries.
  2. Per (apartment_id, room_id): is_room_primary = TRUE marks the single authoritative
     tenant for each physical room. Used for physical-room occupancy counting (1 room = 1).
     Rooms in turnover have both outgoing and incoming tenants; only one row is primary.

Physical occupancy counting (business owner definition: 1 if occupied, 0 if not):
  SELECT COUNT(*) FROM ... WHERE is_room_primary = TRUE
  -- gives unique room count, matching "その日に入居していれば1、入居していなければ0"

Incremental Strategy:
- Daily: append only today's snapshot_date rows
- No full rebuild needed
- 12-month retention (older archived monthly)

Expected volume: ~12,000 rows/day (~4.4M rows/year)
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
        m.moving_agreement_type as contract_type,  -- Use moving_agreement_type (original), not tenant.contract_type
        
        m.rent as fixed_rent,
        m.movein_date as move_in_date,
        COALESCE(m.moveout_date_integrated, m.moveout_plans_date, m.moveout_date) as moveout_date,  -- 最終賃料日 (forecast)
        m.moveout_plans_date as moveout_plans_date,  -- 実退去日 (actual)
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
        -- Filter 3: Exclude cancelled contracts
        AND COALESCE(m.cancel_flag, 0) = 0
),

{% set daily_snapshot_date = var('daily_snapshot_date', none) %}

tenant_room_assignments AS (
    -- Take only the most recent moving per tenant-room combination
    -- This eliminates duplicate historical records
    SELECT
        tenant_id,
        management_status_code,
        tenant_name,
        contract_type,
        move_in_date,
        moveout_date,
        moveout_plans_date,
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

with_room_priority AS (
    -- Assign priority rank within each physical room (apartment_id, room_id).
    -- When a room has multiple tenant records (outgoing + incoming during turnover),
    -- this identifies the single authoritative tenant for physical-room occupancy counting.
    --
    -- Priority logic: tenants physically present today outrank scheduled arrivals.
    --   1. 入居中 (9)       — confirmed resident
    --   2. 契約更新 (10)    — renewing, still resident
    --   3. 移動届受領 (11)  — room transfer, still resident
    --   4. 移動手続き (12)  — transfer in progress
    --   5. 移動 (13)        — transferring
    --   6. 退去届受領 (14)  — notice submitted, still resident
    --   7. 退去予定 (15)    — scheduled departure, still resident
    --   8. 入居 (7)         — move-in day
    --   9. 入居説明 (6)     — briefing done
    --  10. 初回家賃入金 (5) — first rent paid, not yet arrived
    --  11. 仮予約 (4)       — tentative reservation
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY apartment_id, room_id
            ORDER BY
                CASE management_status_code
                    WHEN 9  THEN 1
                    WHEN 10 THEN 2
                    WHEN 11 THEN 3
                    WHEN 12 THEN 4
                    WHEN 13 THEN 5
                    WHEN 14 THEN 6
                    WHEN 15 THEN 7
                    WHEN 7  THEN 8
                    WHEN 6  THEN 9
                    WHEN 5  THEN 10
                    WHEN 4  THEN 11
                    ELSE        12
                END
        ) AS room_priority_rn
    FROM with_property_room
),

final AS (
    SELECT
        -- Snapshot date (anchored to dump date via dbt vars; fallback to server date)
        {% if daily_snapshot_date is not none %}
            CAST('{{ daily_snapshot_date }}' AS DATE) as snapshot_date,
        {% else %}
            CURDATE() as snapshot_date,
        {% endif %}
        
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
        
        -- Property/Room
        apartment_id,
        room_id,
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
        
        -- Dates
        move_in_date,
        moveout_date,
        moveout_plans_date,
        
        -- Physical room occupancy flag (business owner definition: 1 room = 1)
        -- TRUE for exactly one row per (apartment_id, room_id) per snapshot_date,
        -- but ONLY when the top-priority tenant is physically present.
        --
        -- Gated by physically-present statuses (7, 9–15):
        --   7=入居, 9=入居中, 10=契約更新, 11=移動届受領, 12=移動手続き,
        --   13=移動, 14=退去届受領, 15=退去予定
        -- Excluded pre-move-in statuses (4=仮予約, 5=初回家賃入金, 6=入居説明):
        --   These tenants have not physically arrived; rooms reserved-only are NOT occupied.
        --
        -- Rooms with only pre-move-in tenants get is_room_primary = FALSE on all rows,
        -- correctly counting as 0 (vacant) per "入居していなければ0" rule.
        (
            room_priority_rn = 1
            AND management_status_code IN (7, 9, 10, 11, 12, 13, 14, 15)
        ) AS is_room_primary,
        
        -- Metadata
        moving_id,
        CURRENT_TIMESTAMP as dbt_updated_at
        
    FROM with_room_priority
)

SELECT * FROM final

{% if is_incremental() %}
  -- Append only when today's snapshot date is newer than the latest loaded date
  WHERE snapshot_date > COALESCE((SELECT MAX(snapshot_date) FROM {{ this }}), CAST('1900-01-01' AS DATE))
{% endif %}

ORDER BY snapshot_date, tenant_name, property, room_number
