-- ============================================================================
-- Drop Empty Staging Tables
-- ============================================================================
-- This script drops all staging tables that have 0 rows
-- Generated: 2026-02-05
-- 
-- IMPORTANT: Review this script before executing!
-- These tables will be recreated on the next ETL run if they exist in the
-- source SQL dump.
-- ============================================================================

-- Show what will be dropped
SELECT 
    'Empty tables to be dropped:' as info,
    COUNT(*) as count
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'staging'
AND TABLE_ROWS = 0;

-- List the tables
SELECT 
    TABLE_NAME,
    TABLE_ROWS,
    CREATE_TIME
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'staging'
AND TABLE_ROWS = 0
ORDER BY TABLE_NAME;

-- ============================================================================
-- DROP STATEMENTS (uncomment to execute)
-- ============================================================================

-- DROP TABLE IF EXISTS `staging`.`Arrears_Management`;
-- DROP TABLE IF EXISTS `staging`.`Arrears_Snapshot`;
-- DROP TABLE IF EXISTS `staging`.`Orders`;
-- DROP TABLE IF EXISTS `staging`.`approvals`;
-- DROP TABLE IF EXISTS `staging`.`gmo_proof_lists`;
-- DROP TABLE IF EXISTS `staging`.`m_corporate_name_contracts`;
-- DROP TABLE IF EXISTS `staging`.`order_items`;
-- DROP TABLE IF EXISTS `staging`.`other_clearings`;
-- DROP TABLE IF EXISTS `staging`.`pmc`;
-- DROP TABLE IF EXISTS `staging`.`work_reports`;

-- Verify results
SELECT 
    'Tables remaining after drop:' as info,
    COUNT(*) as count
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'staging';
