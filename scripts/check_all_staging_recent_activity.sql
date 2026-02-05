-- ============================================================================
-- Check All Staging Tables for Recent Activity (Last 1 Year)
-- ============================================================================
-- This script checks each staging table with date columns for records 
-- with dates >= 1 year ago from today
--
-- Usage: mysql -h <host> -u <user> -p < check_all_staging_recent_activity.sql
-- ============================================================================

SET @cutoff_date = DATE_SUB(CURDATE(), INTERVAL 1 YEAR);

SELECT 
    'Analysis Date' as info_type,
    CURDATE() as value
UNION ALL
SELECT 
    'Cutoff Date (1 year ago)',
    @cutoff_date;

-- ============================================================================
-- HIGH ACTIVITY TABLES
-- ============================================================================

-- tenant_histories
SELECT 
    'tenant_histories' as table_name,
    COUNT(*) as total_rows,
    SUM(CASE WHEN created_at >= @cutoff_date THEN 1 ELSE 0 END) as recent_records,
    MAX(created_at) as latest_date
FROM staging.tenant_histories;

-- payments
SELECT 
    'payments' as table_name,
    COUNT(*) as total_rows,
    SUM(CASE WHEN target_month >= @cutoff_date 
             OR payment_plan_date >= @cutoff_date
             OR created_at >= @cutoff_date 
             OR updated_at >= @cutoff_date 
             OR latest_payment_date >= @cutoff_date THEN 1 ELSE 0 END) as recent_records,
    GREATEST(
        COALESCE(MAX(target_month), '1900-01-01'),
        COALESCE(MAX(payment_plan_date), '1900-01-01'),
        COALESCE(MAX(created_at), '1900-01-01'),
        COALESCE(MAX(updated_at), '1900-01-01'),
        COALESCE(MAX(latest_payment_date), '1900-01-01')
    ) as latest_date
FROM staging.payments;

-- clearings
SELECT 
    'clearings' as table_name,
    COUNT(*) as total_rows,
    SUM(CASE WHEN target_month >= @cutoff_date 
             OR payment_date >= @cutoff_date
             OR created_at >= @cutoff_date 
             OR updated_at >= @cutoff_date THEN 1 ELSE 0 END) as recent_records,
    GREATEST(
        COALESCE(MAX(target_month), '1900-01-01'),
        COALESCE(MAX(payment_date), '1900-01-01'),
        COALESCE(MAX(created_at), '1900-01-01'),
        COALESCE(MAX(updated_at), '1900-01-01')
    ) as latest_date
FROM staging.clearings;

-- Fundhing_Request
SELECT 
    'Fundhing_Request' as table_name,
    COUNT(*) as total_rows,
    SUM(CASE WHEN cost_date >= @cutoff_date 
             OR payment_plan_date >= @cutoff_date
             OR created_at >= @cutoff_date 
             OR updated_at >= @cutoff_date THEN 1 ELSE 0 END) as recent_records,
    GREATEST(
        COALESCE(MAX(cost_date), '1900-01-01'),
        COALESCE(MAX(payment_plan_date), '1900-01-01'),
        COALESCE(MAX(created_at), '1900-01-01'),
        COALESCE(MAX(updated_at), '1900-01-01')
    ) as latest_date
FROM staging.Fundhing_Request;

-- bank_deposits
SELECT 
    'bank_deposits' as table_name,
    COUNT(*) as total_rows,
    SUM(CASE WHEN deposit_date >= @cutoff_date 
             OR created_at >= @cutoff_date 
             OR updated_at >= @cutoff_date THEN 1 ELSE 0 END) as recent_records,
    GREATEST(
        COALESCE(MAX(deposit_date), '1900-01-01'),
        COALESCE(MAX(created_at), '1900-01-01'),
        COALESCE(MAX(updated_at), '1900-01-01')
    ) as latest_date
FROM staging.bank_deposits;

-- proof_lists
SELECT 
    'proof_lists' as table_name,
    COUNT(*) as total_rows,
    SUM(CASE WHEN transaction_date >= @cutoff_date 
             OR terms_date >= @cutoff_date
             OR created_at >= @cutoff_date 
             OR updated_at >= @cutoff_date THEN 1 ELSE 0 END) as recent_records,
    GREATEST(
        COALESCE(MAX(transaction_date), '1900-01-01'),
        COALESCE(MAX(terms_date), '1900-01-01'),
        COALESCE(MAX(created_at), '1900-01-01'),
        COALESCE(MAX(updated_at), '1900-01-01')
    ) as latest_date
FROM staging.proof_lists;

-- movings (CORE TABLE)
SELECT 
    'movings' as table_name,
    COUNT(*) as total_rows,
    SUM(CASE WHEN created_at >= @cutoff_date 
             OR updated_at >= @cutoff_date 
             OR movein_date >= @cutoff_date
             OR moveout_date >= @cutoff_date
             OR rent_start_date >= @cutoff_date
             OR movein_decided_date >= @cutoff_date THEN 1 ELSE 0 END) as recent_records,
    GREATEST(
        COALESCE(MAX(created_at), '1900-01-01'),
        COALESCE(MAX(updated_at), '1900-01-01'),
        COALESCE(MAX(movein_date), '1900-01-01'),
        COALESCE(MAX(moveout_date), '1900-01-01'),
        COALESCE(MAX(rent_start_date), '1900-01-01'),
        COALESCE(MAX(movein_decided_date), '1900-01-01')
    ) as latest_date
FROM staging.movings;

-- tenants (CORE TABLE)
SELECT 
    'tenants' as table_name,
    COUNT(*) as total_rows,
    SUM(CASE WHEN created_at >= @cutoff_date 
             OR updated_at >= @cutoff_date THEN 1 ELSE 0 END) as recent_records,
    GREATEST(
        COALESCE(MAX(created_at), '1900-01-01'),
        COALESCE(MAX(updated_at), '1900-01-01')
    ) as latest_date
FROM staging.tenants;

-- moveouts (CORE TABLE)
SELECT 
    'moveouts' as table_name,
    COUNT(*) as total_rows,
    SUM(CASE WHEN moveout_date >= @cutoff_date 
             OR created_at >= @cutoff_date 
             OR updated_at >= @cutoff_date THEN 1 ELSE 0 END) as recent_records,
    GREATEST(
        COALESCE(MAX(moveout_date), '1900-01-01'),
        COALESCE(MAX(created_at), '1900-01-01'),
        COALESCE(MAX(updated_at), '1900-01-01')
    ) as latest_date
FROM staging.moveouts;

-- apartments (CORE TABLE)
SELECT 
    'apartments' as table_name,
    COUNT(*) as total_rows,
    SUM(CASE WHEN created_at >= @cutoff_date 
             OR updated_at >= @cutoff_date THEN 1 ELSE 0 END) as recent_records,
    GREATEST(
        COALESCE(MAX(created_at), '1900-01-01'),
        COALESCE(MAX(updated_at), '1900-01-01')
    ) as latest_date
FROM staging.apartments;

-- rooms (CORE TABLE)
SELECT 
    'rooms' as table_name,
    COUNT(*) as total_rows,
    SUM(CASE WHEN created_at >= @cutoff_date 
             OR updated_at >= @cutoff_date THEN 1 ELSE 0 END) as recent_records,
    GREATEST(
        COALESCE(MAX(created_at), '1900-01-01'),
        COALESCE(MAX(updated_at), '1900-01-01')
    ) as latest_date
FROM staging.rooms;

-- inquiries (CORE TABLE)
SELECT 
    'inquiries' as table_name,
    COUNT(*) as total_rows,
    SUM(CASE WHEN inquiry_date >= @cutoff_date 
             OR created_at >= @cutoff_date 
             OR updated_at >= @cutoff_date THEN 1 ELSE 0 END) as recent_records,
    GREATEST(
        COALESCE(MAX(inquiry_date), '1900-01-01'),
        COALESCE(MAX(created_at), '1900-01-01'),
        COALESCE(MAX(updated_at), '1900-01-01')
    ) as latest_date
FROM staging.inquiries;

-- apartment_histories
SELECT 
    'apartment_histories' as table_name,
    COUNT(*) as total_rows,
    SUM(CASE WHEN date_done >= @cutoff_date 
             OR date_completed >= @cutoff_date
             OR created_at >= @cutoff_date 
             OR updated_at >= @cutoff_date THEN 1 ELSE 0 END) as recent_records,
    GREATEST(
        COALESCE(MAX(date_done), '1900-01-01'),
        COALESCE(MAX(date_completed), '1900-01-01'),
        COALESCE(MAX(created_at), '1900-01-01'),
        COALESCE(MAX(updated_at), '1900-01-01')
    ) as latest_date
FROM staging.apartment_histories;

-- reports
SELECT 
    'reports' as table_name,
    COUNT(*) as total_rows,
    SUM(CASE WHEN date >= @cutoff_date 
             OR created_at >= @cutoff_date 
             OR updated_at >= @cutoff_date THEN 1 ELSE 0 END) as recent_records,
    GREATEST(
        COALESCE(MAX(date), '1900-01-01'),
        COALESCE(MAX(created_at), '1900-01-01'),
        COALESCE(MAX(updated_at), '1900-01-01')
    ) as latest_date
FROM staging.reports;

-- ============================================================================
-- SUMMARY: Count tables with recent activity
-- ============================================================================

SELECT 
    'SUMMARY' as section,
    'See results above for detailed table-by-table analysis' as note,
    'Tables with recent_records > 0 have activity in last year' as interpretation;
