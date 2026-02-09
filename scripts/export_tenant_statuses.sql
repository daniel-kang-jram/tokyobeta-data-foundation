-- Export Tenant Status Lists
-- Run this file in SQL Workbench or via mysql CLI
-- Generated: February 7, 2026

-- ============================================================
-- 1. ACTIVE MOVEOUT NOTICES (621 tenants)
-- ============================================================
-- These tenants have submitted moveout notices and are planning to leave

SELECT 
    tenant_id as 'Tenant ID',
    full_name as 'Full Name',
    contract_type_label as 'Contract Type',
    effective_date as 'Notice Date',
    days_in_status as 'Days Since Notice',
    CASE WHEN is_unpaid = 1 THEN 'Yes' ELSE 'No' END as 'Has Unpaid Balance',
    moving_id as 'Moving ID'
FROM gold.tenant_status_transitions
WHERE is_current = 1
  AND status_label = 'Move-out Notice Received'
ORDER BY effective_date DESC, full_name;

-- ============================================================
-- 2. EXPECTED MOVEOUTS (65 tenants)
-- ============================================================
-- These tenants are scheduled to move out

SELECT 
    tenant_id as 'Tenant ID',
    full_name as 'Full Name',
    contract_type_label as 'Contract Type',
    effective_date as 'Expected Moveout Date',
    moving_id as 'Moving ID'
FROM gold.tenant_status_transitions
WHERE is_current = 1
  AND status_label = 'Expected Move-out'
ORDER BY effective_date DESC, full_name;

-- ============================================================
-- 3. COMPLETED MOVEOUTS (28,366 tenants)
-- ============================================================
-- Top 500 most recent moveouts

SELECT 
    tenant_id as 'Tenant ID',
    full_name as 'Full Name',
    contract_type_label as 'Contract Type',
    effective_date as 'Moveout Date',
    days_in_status as 'Days Since Moveout',
    moving_id as 'Moving ID'
FROM gold.tenant_status_transitions
WHERE is_current = 1
  AND status_label = 'Moved Out'
ORDER BY effective_date DESC, full_name
LIMIT 500;

-- ============================================================
-- 4. CURRENTLY RESIDING (9,955 tenants)
-- ============================================================
-- Active residents

SELECT 
    tenant_id as 'Tenant ID',
    full_name as 'Full Name',
    contract_type_label as 'Contract Type',
    effective_date as 'Residence Start',
    days_in_status as 'Days Residing',
    CASE WHEN is_unpaid = 1 THEN 'Yes' ELSE 'No' END as 'Has Unpaid Balance',
    CASE WHEN is_renewal_ineligible = 1 THEN 'No' ELSE 'Yes' END as 'Renewal Eligible',
    moving_id as 'Moving ID'
FROM gold.tenant_status_transitions
WHERE is_current = 1
  AND status_label = 'In Residence'
ORDER BY effective_date DESC, full_name
LIMIT 1000;

-- ============================================================
-- 5. AT-RISK TENANTS (Unpaid or Ineligible for Renewal)
-- ============================================================

SELECT 
    tenant_id as 'Tenant ID',
    full_name as 'Full Name',
    status_label as 'Current Status',
    contract_type_label as 'Contract Type',
    CASE WHEN is_unpaid = 1 THEN 'Unpaid' ELSE 'Paid' END as 'Payment Status',
    CASE WHEN is_renewal_ineligible = 1 THEN 'Ineligible' ELSE 'Eligible' END as 'Renewal Status',
    effective_date as 'Status Date',
    moving_id as 'Moving ID'
FROM gold.tenant_status_transitions
WHERE is_current = 1
  AND (is_unpaid = 1 OR is_renewal_ineligible = 1)
ORDER BY 
    is_unpaid DESC,
    is_renewal_ineligible DESC,
    effective_date DESC;

-- ============================================================
-- 6. STATUS SUMMARY BY CONTRACT TYPE
-- ============================================================

SELECT 
    contract_type_label as 'Contract Type',
    status_label as 'Status',
    COUNT(*) as 'Count',
    ROUND(AVG(days_in_status), 0) as 'Avg Days in Status'
FROM gold.tenant_status_transitions
WHERE is_current = 1
GROUP BY contract_type_label, status_label
ORDER BY contract_type_label, COUNT(*) DESC;

-- ============================================================
-- NOTES FOR FUTURE USE (Starting Feb 8, 2026)
-- ============================================================

-- Once the ETL runs tomorrow, you can query for ACTUAL status changes:
/*
SELECT 
    tenant_id,
    full_name,
    status_transition,
    previous_status_label as 'From Status',
    status_label as 'To Status',
    effective_date as 'Change Date',
    contract_type_label
FROM gold.tenant_status_transitions
WHERE status_changed = 1
  AND DATE(effective_date) = CURDATE()  -- Today's changes
ORDER BY effective_date DESC;
*/

-- Track moveout trend over time:
/*
SELECT 
    DATE(effective_date) as change_date,
    COUNT(*) as new_moveout_notices
FROM gold.tenant_status_transitions
WHERE status_transition LIKE '%→ Move-out Notice Received'
  AND DATE(effective_date) >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
GROUP BY DATE(effective_date)
ORDER BY change_date DESC;
*/
