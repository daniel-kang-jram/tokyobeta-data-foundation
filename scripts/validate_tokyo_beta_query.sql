-- Validation query to reproduce Tokyo Beta テナント情報.xlsx structure
-- Expected output: 12,070 rows

-- First, let's test the basic query
WITH tenant_room_assignments AS (
    SELECT
        t.id as tenant_id,
        t.status as management_status_code,
        t.full_name as tenant_name,
        t.contract_type,
        m.apartment_id,
        m.room_id,
        m.id as moving_id,
        m.rent as fixed_rent,
        m.movein_date,
        m.moveout_date,
        m.moveout_plans_date
    FROM staging.tenants t
    INNER JOIN staging.movings m
        ON t.id = m.tenant_id
    WHERE t.status IN (4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15)
)

SELECT COUNT(*) as total_rows,
       'Expected: 12,070' as expected
FROM tenant_room_assignments;

-- Breakdown by status
SELECT 
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
    END as status_label,
    COUNT(*) as row_count
FROM tenant_room_assignments
GROUP BY management_status_code
ORDER BY row_count DESC;

-- Compare with Excel counts
SELECT 'Excel' as source, '入居中' as status, 10379 as count
UNION ALL SELECT 'Excel', '退去届受領', 763
UNION ALL SELECT 'Excel', '契約更新', 481
UNION ALL SELECT 'Excel', '初回家賃入金', 275
UNION ALL SELECT 'Excel', '退去予定', 67
UNION ALL SELECT 'Excel', '移動届受領', 43
UNION ALL SELECT 'Excel', '入居説明', 38
UNION ALL SELECT 'Excel', '入居', 12
UNION ALL SELECT 'Excel', '仮予約', 7
UNION ALL SELECT 'Excel', '移動手続き', 4
UNION ALL SELECT 'Excel', '移動', 1;
