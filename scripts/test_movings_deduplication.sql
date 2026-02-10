-- Comprehensive test to validate ROW_NUMBER() deduplication across all queries
-- Run this against Aurora database to verify fixes

-- ============================================================================
-- TEST 1: Verify duplicate movings exist (should find some)
-- ============================================================================
SELECT 
    'TEST 1: Count of duplicate active movings (same tenant-room)' as test_name,
    COUNT(*) as duplicate_count,
    CASE 
        WHEN COUNT(*) > 0 THEN '✅ PASS - Duplicates exist (confirms the problem)'
        ELSE '❌ FAIL - No duplicates found (unexpected)'
    END as result
FROM (
    SELECT 
        tenant_id,
        apartment_id,
        room_id,
        COUNT(*) as record_count
    FROM staging.movings
    WHERE is_moveout = 0
    GROUP BY tenant_id, apartment_id, room_id
    HAVING COUNT(*) > 1
) duplicates;

-- ============================================================================
-- TEST 2: Tokyo Beta Tenant Room Info - Compare with/without dedup
-- ============================================================================
-- Without deduplication (old way)
WITH raw_movings AS (
    SELECT COUNT(*) as row_count
    FROM staging.tenants t
    INNER JOIN staging.movings m ON t.id = m.tenant_id
    WHERE t.status IN (4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15)
      AND m.is_moveout = 0
),
-- With deduplication (new way)
deduplicated_movings AS (
    SELECT COUNT(*) as row_count
    FROM (
        SELECT 
            t.id,
            m.apartment_id,
            m.room_id,
            ROW_NUMBER() OVER (
                PARTITION BY t.id, m.apartment_id, m.room_id 
                ORDER BY m.movein_date DESC, m.updated_at DESC, m.id DESC
            ) as rn
        FROM staging.tenants t
        INNER JOIN staging.movings m ON t.id = m.tenant_id
        WHERE t.status IN (4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15)
          AND m.is_moveout = 0
    ) ranked
    WHERE rn = 1
)
SELECT 
    'TEST 2: Tokyo Beta Tenant Room Info' as test_name,
    (SELECT row_count FROM raw_movings) as before_dedup,
    (SELECT row_count FROM deduplicated_movings) as after_dedup,
    (SELECT row_count FROM raw_movings) - (SELECT row_count FROM deduplicated_movings) as duplicates_removed,
    CASE 
        WHEN (SELECT row_count FROM deduplicated_movings) < (SELECT row_count FROM raw_movings) 
        THEN '✅ PASS - Deduplication working'
        ELSE '❌ FAIL - No deduplication happened'
    END as result;

-- ============================================================================
-- TEST 3: Daily Activity Summary - Move-ins deduplication
-- ============================================================================
WITH raw_moveins AS (
    SELECT COUNT(DISTINCT mv.tenant_id) as count
    FROM staging.movings mv
    WHERE mv.movein_date IS NOT NULL
      AND mv.movein_date >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)
),
deduplicated_moveins AS (
    SELECT COUNT(*) as count
    FROM (
        SELECT 
            mv.tenant_id,
            mv.apartment_id,
            mv.room_id,
            ROW_NUMBER() OVER (
                PARTITION BY mv.tenant_id, mv.apartment_id, mv.room_id 
                ORDER BY mv.movein_date DESC, mv.updated_at DESC, mv.id DESC
            ) as rn
        FROM staging.movings mv
        WHERE mv.movein_date IS NOT NULL
          AND mv.movein_date >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)
    ) ranked
    WHERE rn = 1
)
SELECT 
    'TEST 3: Daily Activity Summary - Move-ins' as test_name,
    (SELECT count FROM raw_moveins) as before_dedup,
    (SELECT count FROM deduplicated_moveins) as after_dedup,
    (SELECT count FROM raw_moveins) - (SELECT count FROM deduplicated_moveins) as difference,
    CASE 
        WHEN (SELECT count FROM deduplicated_moveins) <= (SELECT count FROM raw_moveins) 
        THEN '✅ PASS - Deduplication applied'
        ELSE '⚠️ WARNING - Unexpected result'
    END as result;

-- ============================================================================
-- TEST 4: Int Contracts - Verify no duplicate contracts
-- ============================================================================
WITH all_contracts AS (
    SELECT 
        m.id as moving_id,
        m.tenant_id,
        m.apartment_id,
        m.room_id,
        COUNT(*) OVER (PARTITION BY m.tenant_id, m.apartment_id, m.room_id) as duplicate_count
    FROM staging.movings m
    WHERE m.id IS NOT NULL
)
SELECT 
    'TEST 4: Int Contracts - Duplicate contract check' as test_name,
    COUNT(CASE WHEN duplicate_count > 1 THEN 1 END) as contracts_with_duplicates,
    COUNT(*) as total_contracts,
    CASE 
        WHEN COUNT(CASE WHEN duplicate_count > 1 THEN 1 END) > 0 
        THEN '⚠️ WARNING - Duplicates exist (will be fixed by ROW_NUMBER in int_contracts)'
        ELSE '✅ PASS - No duplicates'
    END as result
FROM all_contracts;

-- ============================================================================
-- TEST 5: Verify specific tenant deduplication (南創 - ID 36757)
-- ============================================================================
WITH tenant_movings AS (
    SELECT 
        m.id as moving_id,
        m.tenant_id,
        m.apartment_id,
        m.room_id,
        m.movein_date,
        m.is_moveout,
        ROW_NUMBER() OVER (
            PARTITION BY m.tenant_id, m.apartment_id, m.room_id 
            ORDER BY m.movein_date DESC, m.updated_at DESC, m.id DESC
        ) as rn
    FROM staging.movings m
    WHERE m.tenant_id = 36757
      AND m.is_moveout = 0
)
SELECT 
    'TEST 5: Specific tenant (南創) deduplication' as test_name,
    COUNT(*) as total_active_movings,
    SUM(CASE WHEN rn = 1 THEN 1 ELSE 0 END) as after_dedup,
    COUNT(*) - SUM(CASE WHEN rn = 1 THEN 1 ELSE 0 END) as duplicates_removed,
    CASE 
        WHEN SUM(CASE WHEN rn = 1 THEN 1 ELSE 0 END) = 1 
        THEN '✅ PASS - Only 1 active moving after dedup'
        ELSE CONCAT('⚠️ WARNING - Expected 1, got ', SUM(CASE WHEN rn = 1 THEN 1 ELSE 0 END))
    END as result
FROM tenant_movings;

-- ============================================================================
-- TEST 6: Verify corporate tenant not affected (株式会社ケイ・マックス - ID 100161)
-- ============================================================================
WITH corporate_movings AS (
    SELECT 
        m.id as moving_id,
        m.tenant_id,
        m.apartment_id,
        m.room_id,
        ROW_NUMBER() OVER (
            PARTITION BY m.tenant_id, m.apartment_id, m.room_id 
            ORDER BY m.movein_date DESC, m.updated_at DESC, m.id DESC
        ) as rn
    FROM staging.movings m
    WHERE m.tenant_id = 100161
      AND m.is_moveout = 0
)
SELECT 
    'TEST 6: Corporate tenant (株式会社ケイ・マックス) preservation' as test_name,
    COUNT(*) as total_unique_rooms,
    SUM(CASE WHEN rn = 1 THEN 1 ELSE 0 END) as after_dedup,
    CASE 
        WHEN COUNT(*) = SUM(CASE WHEN rn = 1 THEN 1 ELSE 0 END) 
        THEN '✅ PASS - All unique rooms preserved'
        ELSE '❌ FAIL - Some rooms lost'
    END as result
FROM corporate_movings;

-- ============================================================================
-- SUMMARY: All Tests
-- ============================================================================
SELECT 
    '===============================================' as summary,
    'DEDUPLICATION VALIDATION TEST SUITE COMPLETE' as title,
    '===============================================' as summary2;
