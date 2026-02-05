# Staging Tables - Recent Activity Summary

**Generated:** 2026-02-05  
**Analysis Period:** Last 1 year (since 2025-02-05)

## Quick Summary

Out of **81 staging tables**, based on analysis of date columns and table characteristics:

### Tables Likely With Recent Activity

The following tables have date tracking columns (`created_at`, `updated_at`, or activity dates) and non-zero row counts, indicating they likely have recent activity:

#### Core Analytics Tables (High Confidence - Daily Updates)
1. **movings** (61,147 rows) - Contract lifecycle events
2. **tenants** (47,775 rows) - Tenant information
3. **moveouts** (25,540 rows) - Moveout records
4. **apartments** (1,131 rows) - Property data
5. **rooms** (16,176 rows) - Room information
6. **inquiries** (719 rows) - Customer inquiries

#### Financial/Transaction Tables (High Confidence - Daily Updates)
7. **tenant_histories** (1,199,272 rows) - Tenant activity tracking
8. **payments** (974,555 rows) - Payment records
9. **clearings** (748,076 rows) - Financial clearings
10. **bank_deposits** (282,012 rows) - Deposit transactions
11. **Fundhing_Request** (277,287 rows) - Funding requests
12. **proof_lists** (249,996 rows) - Transaction proofs
13. **Costs** (95,146 rows) - Cost records
14. **Costs_items** (95,553 rows) - Cost line items
15. **payment_deletions** (78,995 rows) - Payment corrections
16. **utility_bills** (76,870 rows) - Utility charges

#### Supporting Tables (Medium Confidence - Regular Updates)
17. **apartment_histories** (12,472 rows) - Property history
18. **introducers** (12,038 rows) - Referral records
19. **bank_accounts** (6,040 rows) - Account information
20. **reports** (10,722 rows) - System reports
21. **gmo_order_numbers** (5,228 rows) - Payment orders
22. **previews** (5,981 rows) - Preview records
23. **tenant_black_lists** (6,955 rows) - Blacklist records
24. **paysle_charges** (13,654 rows) - Payment processing
25. **renewals** (4,240 rows) - Contract renewals
26. **Deposits** (7,712 rows) - Deposit records
27. **pl_actuals_annual** (105,274 rows) - P&L data
28. **cleared_balances** (8,692 rows) - Balance clearings

#### Master Data Tables (Low Confidence - Infrequent Updates)
29. **m_nationalities** (200 rows) - Nationality codes
30. **m_corporate_names** (611 rows) - Corporate names
31. **m_agents** (130 rows) - Agent information
32. **m_agent_tenants** (1,303 rows) - Agent-tenant relationships
33. **m_owners** (164 rows) - Owner information
34. **tenant_counts** (2,605 rows) - Tenant statistics

### Tables Without Recent Activity (10 Empty Tables)

These tables have **0 rows** and therefore no activity:

1. Arrears_Management
2. Arrears_Snapshot
3. Orders
4. gmo_proof_lists
5. approvals
6. m_corporate_name_contracts
7. order_items
8. other_clearings
9. pmc
10. work_reports

### Tables Without Date Columns (Cannot Determine)

These 10 tables have data but no date columns to assess activity:

1. paysle_charge_responses (19,893 rows)
2. bank_account_tenants (12,439 rows)
3. tenant_reports (3,821 rows)
4. prime_one_accounts (1,211 rows)
5. apartment_municipalities (62 rows)
6. proof_list_executions (22 rows)
7. apartment_prefectures (7 rows)
8. m_data_types (6 rows)
9. options (3 rows)
10. apartment_corporate_names (2 rows)

## Estimated Active Tables Count

**Estimated: 60-65 tables** out of 81 have had updates in the recent year.

This is based on:
- 71 tables have date columns (created_at, updated_at, or activity dates)
- 10 tables are empty (0 rows)
- 61 tables have both date columns AND non-zero row counts
- Assuming most non-empty tables with date tracking are actively maintained

## How to Get Exact Count

Due to network security restrictions (Aurora cluster not accessible from current IP), the exact query could not be executed. To get the precise list:

### Option 1: Run SQL Script (Recommended)
```bash
# From a machine with database access:
mysql -h tokyobeta-prod-aurora-cluster-public.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com \
      -u admin -p \
      -D tokyobeta \
      < scripts/check_all_staging_recent_activity.sql > results.txt
```

### Option 2: Run Bash Script
```bash
# Automated script that checks all tables:
./scripts/check_staging_activity_final.sh
```

### Option 3: Whitelist Your IP
Add your current IP (85.115.98.80) to the Aurora security group:
```bash
aws ec2 authorize-security-group-ingress \
    --group-id <security-group-id> \
    --protocol tcp \
    --port 3306 \
    --cidr 85.115.98.80/32 \
    --profile gghouse \
    --region ap-northeast-1
```

## Files Created

1. **`docs/STAGING_TABLES_RECENT_ACTIVITY_ANALYSIS.md`**
   - Comprehensive analysis of all 81 tables
   - Table categorization by activity level
   - Expected results and recommendations

2. **`scripts/check_all_staging_recent_activity.sql`**
   - SQL queries to check core tables for recent activity
   - Can be executed directly via mysql client

3. **`scripts/check_staging_activity_final.sh`**
   - Automated bash script to analyze all tables
   - Generates markdown report with results

4. **`scripts/analyze_staging_activity.py`**
   - Python script for programmatic analysis
   - Requires pymysql library

## Key Insights

### High-Value Tables for Analytics
The core tables used in dbt gold layer all show signs of active use:
- ✓ movings - Used for daily_activity_summary, new_contracts, moveouts
- ✓ tenants - Used for demographics in new_contracts
- ✓ apartments - Used for geolocation and property details
- ✓ rooms - Used for room-level analysis
- ✓ inquiries - Used for lead generation metrics

### Data Freshness
Based on ETL logs from 2026-02-05:
- **Last ETL Run:** 2026-02-05 11:28:38 JST (SUCCEEDED)
- **Staging Load:** 81 tables loaded successfully
- **dbt Transformations:** All gold tables refreshed
- **Data Quality:** 90.8% test pass rate (69/76 tests)

### Recommendations

1. **Archive Empty Tables**: Consider removing the 10 empty tables from future ETL runs to improve performance

2. **Monitor Core Tables**: Set up CloudWatch alerts for row count changes on the 6 core analytics tables

3. **Date Column Standards**: Add created_at/updated_at to the 10 tables without date tracking for better auditability

4. **Quarterly Review**: Assess which tables have had no activity in 90+ days for potential archival

## Related Documentation

- **Full Analysis:** `docs/STAGING_TABLES_RECENT_ACTIVITY_ANALYSIS.md`
- **Database Schema:** `docs/DATABASE_SCHEMA_EXPLANATION.md`
- **ETL Process:** `glue/scripts/daily_etl.py`
- **dbt Sources:** `dbt/models/staging/_sources.yml`
