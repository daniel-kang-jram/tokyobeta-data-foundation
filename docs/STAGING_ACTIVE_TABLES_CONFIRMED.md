# Staging Tables with Recent Activity - CONFIRMED

**Analysis Date:** 2026-02-05 11:37:20
**Cutoff Date:** 2025-02-05
**Method:** Direct database queries

## Summary

- **Total staging tables:** 81
- **Tables with recent activity:** 45
- **Tables without recent activity:** 26
- **Tables without date columns:** 10
- **Active percentage:** 55.6%

## Tables with Recent Activity (45)

| Table Name | Total Rows | Recent Records | Latest Date | Date Columns |
|------------|------------|----------------|-------------|-------------|
| payments | 990,735 | 679,445 | 2203-12-01 00:00:00 | target_month,payment_plan_date,created_at,updated_at,latest_payment_date |
| clearings | 751,096 | 578,667 | 2026-12-01 00:00:00 | target_month,payment_date,created_at,updated_at |
| Fundhing_Request | 278,696 | 278,696 | 2025-03-03 20:27:21 | cost_date,payment_plan_date,created_at,updated_at |
| proof_lists | 254,358 | 110,604 | 2026-02-04 15:13:45 | transaction_date,terms_date,created_at,updated_at |
| pl_actuals_annual | 105,672 | 105,672 | 2025-09-01 00:00:00 | month,created_at,updated_at |
| Costs_items | 96,465 | 96,465 | NULL | work_date,created_at,updated_at |
| Costs | 95,472 | 95,472 | 2025-03-25 00:00:00 | cost_date,payment_plan_date,payment_date,created_at,updated_at |
| utility_bills | 79,043 | 79,043 | 2025-12-31 00:00:00 | bill_date,payment_date,billing_month,billing_period_start_date,billing_period_end_date,created_at,updated_at |
| bank_deposits | 283,853 | 76,951 | NULL | deposit_date,created_at,updated_at,deleted_at |
| tenants | 50,297 | 50,185 | 2200-01-01 00:00:00 | birth_date,bitkey_date,created_at,updated_at,visa_expiration_date,contact_birth_date_1,renewal_deadline_date,first_movein_date,renewal_movein_date |
| movings | 62,280 | 37,697 | 2302-01-28 00:00:00 | movein_exposition_date,movein_date,key_receipt_date,moveout_date,moveout_plans_date,first_month_pay_date,last_month_pay_date,key_return_date,moveout_receipt_date,mainte_plans_date,mainte_done_date,created_at,updated_at,rent_start_date,movein_decided_date,original_movein_date,expiration_date,expiration_deadline_date,answer_deadline_date,answer_notice_date,termination_notice_date,renewal_deadline_date,renewal_notice_date,cloud_send_date,cloud_registration_date,renewal_contract_date,move_receipt_date,move_procedure_date,next_movein_date,moveout_date_integrated,ac_plans_date,ac_done_date |
| rooms | 16,401 | 16,389 | 2030-12-31 00:00:00 | prohibition_date,release_date,created_at,updated_at,movein_plan_date |
| paysle_charges | 13,843 | 13,843 | 2026-02-01 00:00:00 | target_month,receipt_CreatedDate,receipt_CVSCollectDate,receipt_ScheduledTransferDate,created_at,updated_at |
| reports | 12,111 | 9,182 | 2026-02-04 23:41:16 | date,created_at,updated_at |
| Deposits | 7,744 | 7,744 | 2025-03-25 00:00:00 | deposit_date,received_date,created_at,updated_at |
| moveouts | 25,256 | 7,150 | 2026-12-31 00:00:00 | moveout_date,created_at,updated_at |
| apartment_histories | 12,413 | 4,476 | 2026-02-12 00:00:00 | date_done,date_completed,created_at,updated_at |
| bank_accounts | 6,040 | 2,701 | 2026-02-04 20:49:12 | moving_moveout_plans_date,created_at,updated_at |
| cleared_balances | 8,925 | 2,013 | 5300-11-12 00:00:00 | payment_date,created_at,updated_at |
| introducers | 11,563 | 1,882 | 2026-02-04 18:22:13 | approval_application_datetime,president_approval_datetime,voucher_printed_datetime,transferred_date |
| m_agent_tenants | 1,312 | 1,260 | 2026-02-04 18:55:10 | created_at,updated_at |
| apartments | 1,202 | 1,200 | 2100-01-01 00:00:00 | completion_date,handover_date,open_date,contract_start_date,contract_end_date,created_at,updated_at,application_start_date |
| deposit_accounts | 1,202 | 1,185 | NULL | created_at,updated_at,deleted_at |
| withdrawal_accounts | 1,201 | 984 | 2026-02-04 16:18:33 | created_at,updated_at |
| suppliers_items | 819 | 819 | 2025-03-02 09:41:41 | created_at,updated_at |
| refunds | 836 | 722 | 2026-02-04 18:21:25 | approval_application_datetime,president_approval_datetime,voucher_printed_datetime,transferred_date |
| ry | 4,593 | 569 | NULL | date_created,date_receipt,created_at,updated_at,deleted_at |
| m_corporate_names | 615 | 561 | NULL | created_at,updated_at,deleted_at |
| gmo_order_numbers | 5,271 | 384 | 2025-04-28 00:00:00 | ordered_at,url_due_date,settle_date,created_at,updated_at |
| ju | 2,617 | 356 | 2026-02-03 12:33:52 | date_created,date_receipt,created_at,updated_at |
| suppliers | 218 | 218 | 2025-03-03 16:25:34 | created_at,updated_at |
| previews | 6,092 | 200 | 2026-02-03 18:15:06 | preview_datetime,updated_at,created_at |
| applications | 135 | 135 | 2026-02-04 17:36:01 | post_datetime,created_at,updated_at |
| m_agents | 131 | 131 | 2026-02-04 09:58:11 | created_at,updated_at,deleted_at |
| mapping_definition | 113 | 113 | 2025-03-02 10:01:00 | created_at,updated_at |
| inquiries | 719 | 105 | NULL | inquiry_date,wish_movein_date,movein_date,updated_at,created_at,abort_date |
| tenant_black_lists | 6,975 | 58 | 2025-10-15 02:42:22 | created_at,updated_at |
| items | 29 | 29 | 2025-03-02 09:41:00 | created_at,updated_at |
| renewals | 4,252 | 27 | 2026-08-31 | moveout_date,renewal_movein_date |
| apartment_owners | 205 | 9 | 2047-04-30 00:00:00 | agreement_start_date,agreement_end_date,non_rejection_deadline,created_at,updated_at |
| m_apartment_history_services | 8 | 8 | NULL | created_at,updated_at,deleted_at |
| m_owners | 164 | 8 | NULL | created_at,updated_at,deleted_at |
| m_apartment_history_corporations | 11 | 5 | NULL | created_at,updated_at,deleted_at |
| m_sales_types | 35 | 2 | 2025-11-19 11:55:43 | created_at,updated_at |
| approvers | 1 | 1 | 2025-03-02 09:33:45 | created_at,updated_at |

## Tables without Recent Activity (26)

| Table Name | Total Rows | Latest Date | Date Columns |
|------------|------------|-------------|-------------|
| apartment_payees | 204 | NULL | created_at,updated_at,deleted_at |
| m_nationalities | 200 | NULL | created_at,updated_at,deleted_at |
| m_black_list_reasons | 13 | NULL | created_at,updated_at,deleted_at |
| m_moving_sites | 10 | NULL | created_at,updated_at,deleted_at |
| m_personal_identities | 8 | NULL | created_at,updated_at,deleted_at |
| m_moving_reasons | 7 | NULL | created_at,updated_at,deleted_at |
| m_next_apartments | 4 | NULL | created_at,updated_at,deleted_at |
| cash | 2 | NULL | date_receipt,created_at,updated_at,deleted_at |
| currency | 1 | NULL | created_at,updated_at |
| m_systems | 1 | NULL | present_closing_date,present_closing_date_prime_one,created_at,updated_at,deleted_at |
| Arrears_Management | 0 | NULL | target_month,deposit_plan_date,deposit_date,created_at,updated_at |
| Arrears_Snapshot | 0 | NULL | snapshot_date,target_month,deposit_plan_date,deposit_date,created_at,updated_at |
| Orders | 0 | NULL | request_date,created_at,updated_at |
| api_requests | 0 | N/A | created_at |
| approvals | 0 | NULL | request_date,response_date,created_at,updated_at |
| gmo_proof_lists | 0 | NULL | ordered_at,settlement_date,created_at,updated_at |
| m_corporate_name_contracts | 0 | NULL | start_date,end_date,created_at,updated_at |
| moves | 0 | N/A | first_movein_date |
| order_items | 0 | NULL | created_at,updated_at |
| other_clearings | 0 | NULL | deposit_date,created_at,updated_at |
| payment_deletions | 0 | N/A | target_month |
| paysle_csv_lines | 0 | N/A | created_at |
| pmc | 0 | NULL | TRANSACTION_DATE,created_at,updated_at |
| tenant_counts | 0 | N/A | date |
| tenant_histories | 0 | N/A | created_at |
| work_reports | 0 | NULL | completion_date,created_at,updated_at |

## Tables without Date Columns (10)

| Table Name | Total Rows |
|------------|-----------|
| paysle_charge_responses | 20,269 |
| bank_account_tenants | 12,380 |
| tenant_reports | 3,833 |
| prime_one_accounts | 1,211 |
| apartment_municipalities | 62 |
| proof_list_executions | 22 |
| apartment_prefectures | 7 |
| m_data_types | 6 |
| options | 3 |
| apartment_corporate_names | 2 |
