# Staging Tables - Recent Activity Analysis (Last 1 Year)

**Analysis Date:** 2026-02-05  
**Cutoff Date:** 2025-02-05 (1 year ago)  
**Total Tables:** 81 in staging schema

## Overview

This document analyzes all 81 staging tables to identify which have had at least one update in the recent 1 year based on date columns (created_at, updated_at, activity dates, etc.).

## Tables with Date Columns

Based on information_schema analysis, the following tables have date/datetime/timestamp columns that can be used to check for recent activity:

### High Activity Tables (>10,000 rows)

| Table Name | Row Count | Date Columns |
|------------|-----------|--------------|
| tenant_histories | 1,199,272 | created_at |
| payments | 974,555 | target_month, payment_plan_date, created_at, updated_at, latest_payment_date |
| clearings | 748,076 | target_month, payment_date, created_at, updated_at |
| Fundhing_Request | 277,287 | cost_date, payment_plan_date, created_at, updated_at |
| bank_deposits | 282,012 | deposit_date, created_at, updated_at, deleted_at |
| proof_lists | 249,996 | transaction_date, terms_date, created_at, updated_at |
| pl_actuals_annual | 105,274 | month, created_at, updated_at |
| Costs | 95,146 | cost_date, payment_plan_date, payment_date, created_at, updated_at |
| Costs_items | 95,553 | work_date, created_at, updated_at |
| payment_deletions | 78,995 | target_month |
| utility_bills | 76,870 | bill_date, payment_date, billing_month, billing_period_start_date, billing_period_end_date, created_at, updated_at |
| movings | 61,147 | movein_exposition_date, movein_date, key_receipt_date, moveout_date, moveout_plans_date, first_month_pay_date, last_month_pay_date, key_return_date, moveout_receipt_date, mainte_plans_date, mainte_done_date, created_at, updated_at, rent_start_date, movein_decided_date, original_movein_date, expiration_date, expiration_deadline_date, answer_deadline_date, answer_notice_date, termination_notice_date, renewal_deadline_date, renewal_notice_date, cloud_send_date, cloud_registration_date, renewal_contract_date, move_receipt_date, move_procedure_date, next_movein_date, moveout_date_integrated, ac_plans_date, ac_done_date |
| tenants | 47,775 | birth_date, bitkey_date, created_at, updated_at, visa_expiration_date, contact_birth_date_1, renewal_deadline_date, first_movein_date, renewal_movein_date |
| moveouts | 25,540 | moveout_date, created_at, updated_at |
| paysle_charge_responses | 19,893 | NULL |
| rooms | 16,176 | prohibition_date, release_date, created_at, updated_at, movein_plan_date |
| paysle_charges | 13,654 | target_month, receipt_CreatedDate, receipt_CVSCollectDate, receipt_ScheduledTransferDate, created_at, updated_at |
| bank_account_tenants | 12,439 | NULL |
| apartment_histories | 12,472 | date_done, date_completed, created_at, updated_at |
| introducers | 12,038 | approval_application_datetime, president_approval_datetime, voucher_printed_datetime, transferred_date |
| reports | 10,722 | date, created_at, updated_at |

### Medium Activity Tables (1,000 - 10,000 rows)

| Table Name | Row Count | Date Columns |
|------------|-----------|--------------|
| Deposits | 7,712 | deposit_date, received_date, created_at, updated_at |
| tenant_black_lists | 6,955 | created_at, updated_at |
| bank_accounts | 6,040 | moving_moveout_plans_date, created_at, updated_at |
| previews | 5,981 | preview_datetime, updated_at, created_at |
| gmo_order_numbers | 5,228 | ordered_at, url_due_date, settle_date, created_at, updated_at |
| ry | 4,493 | date_created, date_receipt, created_at, updated_at, deleted_at |
| renewals | 4,240 | moveout_date, renewal_movein_date |
| tenant_reports | 3,821 | NULL |
| tenant_counts | 2,605 | date |
| ju | 2,597 | date_created, date_receipt, created_at, updated_at |
| paysle_csv_lines | 2,316 | created_at |
| api_requests | 2,013 | created_at |
| m_agent_tenants | 1,303 | created_at, updated_at |
| deposit_accounts | 1,202 | created_at, updated_at, deleted_at |
| withdrawal_accounts | 1,201 | created_at, updated_at |
| prime_one_accounts | 1,211 | NULL |
| apartments | 1,131 | completion_date, handover_date, open_date, contract_start_date, contract_end_date, created_at, updated_at, application_start_date |

### Low Activity Tables (<1,000 rows)

| Table Name | Row Count | Date Columns |
|------------|-----------|--------------|
| refunds | 834 | approval_application_datetime, president_approval_datetime, voucher_printed_datetime, transferred_date |
| suppliers_items | 819 | created_at, updated_at |
| inquiries | 719 | inquiry_date, wish_movein_date, movein_date, updated_at, created_at, abort_date |
| m_corporate_names | 611 | created_at, updated_at, deleted_at |
| suppliers | 218 | created_at, updated_at |
| apartment_owners | 205 | agreement_start_date, agreement_end_date, non_rejection_deadline, created_at, updated_at |
| apartment_payees | 204 | created_at, updated_at, deleted_at |
| m_nationalities | 200 | created_at, updated_at, deleted_at |
| moves | 188 | first_movein_date |
| m_owners | 164 | created_at, updated_at, deleted_at |
| m_agents | 130 | created_at, updated_at, deleted_at |
| applications | 120 | post_datetime, created_at, updated_at |
| mapping_definition | 113 | created_at, updated_at |
| apartment_municipalities | 62 | NULL |
| m_sales_types | 35 | created_at, updated_at |
| items | 29 | created_at, updated_at |
| proof_list_executions | 22 | NULL |
| m_black_list_reasons | 13 | created_at, updated_at, deleted_at |
| m_apartment_history_corporations | 11 | created_at, updated_at, deleted_at |
| m_moving_sites | 10 | created_at, updated_at, deleted_at |
| m_apartment_history_services | 8 | created_at, updated_at, deleted_at |
| m_personal_identities | 8 | created_at, updated_at, deleted_at |
| apartment_prefectures | 7 | NULL |
| m_moving_reasons | 7 | created_at, updated_at, deleted_at |
| m_data_types | 6 | NULL |
| m_next_apartments | 4 | created_at, updated_at, deleted_at |
| options | 3 | NULL |
| apartment_corporate_names | 2 | NULL |
| cash | 2 | date_receipt, created_at, updated_at, deleted_at |
| cleared_balances | 8,692 | payment_date, created_at, updated_at |
| currency | 1 | created_at, updated_at |
| m_systems | 1 | present_closing_date, present_closing_date_prime_one, created_at, updated_at, deleted_at |
| approvers | 1 | created_at, updated_at |

### Empty Tables (0 rows)

| Table Name | Date Columns |
|------------|--------------|
| Arrears_Management | target_month, deposit_plan_date, deposit_date, created_at, updated_at |
| Arrears_Snapshot | snapshot_date, target_month, deposit_plan_date, deposit_date, created_at, updated_at |
| Orders | request_date, created_at, updated_at |
| gmo_proof_lists | ordered_at, settlement_date, created_at, updated_at |
| approvals | request_date, response_date, created_at, updated_at |
| m_corporate_name_contracts | start_date, end_date, created_at, updated_at |
| order_items | created_at, updated_at |
| other_clearings | deposit_date, created_at, updated_at |
| pmc | TRANSACTION_DATE, created_at, updated_at |
| work_reports | completion_date, created_at, updated_at |

### Tables Without Date Columns

| Table Name | Row Count |
|------------|-----------|
| paysle_charge_responses | 19,893 |
| bank_account_tenants | 12,439 |
| tenant_reports | 3,821 |
| prime_one_accounts | 1,211 |
| apartment_municipalities | 62 |
| proof_list_executions | 22 |
| apartment_prefectures | 7 |
| m_data_types | 6 |
| options | 3 |
| apartment_corporate_names | 2 |

## SQL Query to Check Recent Activity

To identify tables with activity in the last year, you can run this SQL query:

```sql
-- Set cutoff date (1 year ago)
SET @cutoff_date = DATE_SUB(CURDATE(), INTERVAL 1 YEAR);

-- For each table with date columns, check for recent activity
-- Example for movings table:
SELECT 
    'movings' as table_name,
    COUNT(*) as recent_records,
    MAX(GREATEST(
        COALESCE(created_at, '1900-01-01'),
        COALESCE(updated_at, '1900-01-01'),
        COALESCE(movein_date, '1900-01-01'),
        COALESCE(moveout_date, '1900-01-01')
    )) as latest_date
FROM staging.movings
WHERE created_at >= @cutoff_date
   OR updated_at >= @cutoff_date
   OR movein_date >= @cutoff_date
   OR moveout_date >= @cutoff_date;
```

## Automated Analysis Script

A bash script has been created to automatically check all tables:

**Location:** `scripts/check_staging_activity_final.sh`

**Usage:**
```bash
# Run the analysis
./scripts/check_staging_activity_final.sh

# Note: Requires database access from your current IP
# If running from outside VPC, ensure security group allows your IP
```

## Expected Results

Based on the nature of the data and the presence of `created_at` and `updated_at` columns on most tables, we expect the following tables to have recent activity (within last year):

### Likely Active (Daily Updates)
- **tenant_histories** - Activity tracking table
- **payments** - Payment records
- **clearings** - Financial clearings
- **bank_deposits** - Deposit transactions
- **movings** - Move-in/out events
- **tenants** - Tenant information
- **moveouts** - Moveout records
- **inquiries** - New inquiries
- **reports** - Daily reports

### Likely Active (Regular Updates)
- **apartments** - Property updates
- **rooms** - Room status changes
- **apartment_histories** - Property history
- **proof_lists** - Financial proofs
- **utility_bills** - Monthly bills
- **paysle_charges** - Payment processing

### Likely Inactive (Historical/Master Data)
- **m_nationalities** - Master data (rarely changes)
- **m_data_types** - Master data
- **apartment_prefectures** - Master data
- **apartment_municipalities** - Master data
- **m_sales_types** - Master data
- All tables with 0 rows

## Recommendations

1. **Focus on Core Tables**: The key tables for analytics are:
   - `movings` - Contract lifecycle
   - `tenants` - Tenant demographics
   - `apartments` - Property information
   - `rooms` - Room details
   - `inquiries` - Lead generation

2. **Archive Candidates**: Consider archiving tables with no activity in 1+ year to S3 Glacier

3. **Monitoring**: Set up CloudWatch metrics to track table growth rates for capacity planning

4. **Data Quality**: Tables with `created_at` and `updated_at` columns should be monitored for data freshness

## Next Steps

To get the exact list of active tables:

1. **Option A - Direct Query**: Connect to Aurora from within VPC or whitelist your IP in security group, then run `check_staging_activity_final.sh`

2. **Option B - Via Glue Job**: Modify the Glue ETL script to include activity analysis after data load

3. **Option C - QuickSight**: Create a dataset to visualize table activity patterns over time

## References

- **Database Schema**: See `docs/DATABASE_SCHEMA_EXPLANATION.md`
- **ETL Process**: See `glue/scripts/daily_etl.py`
- **dbt Models**: See `dbt/models/staging/_sources.yml`
