# Incident Log

This file tracks all production incidents, root causes, and resolutions.

---

## Incident #1: Staging Table Staleness (Feb 2026)

**Date:** 2026-02-01 to 2026-02-10  
**Detected:** 2026-02-10  
**Severity:** High  
**Status:** ✅ Resolved  
**Resolution Time:** 20 minutes (after detection)

### Summary

Staging tables (`movings`, `tenants`, `rooms`, `inquiries`) became 8-9 days stale due to AWS Glue ETL jobs not running automatically. The issue was detected during a routine status check and resolved by manually loading the latest SQL dump from S3.

### Impact

**Data Staleness:**
- staging.movings: 8 days old (+18,731 missing records)
- staging.tenants: 4 days old (+2,421 missing records)  
- staging.rooms: 8 days old (no new rows, but stale timestamps)
- staging.inquiries: 9 days old

**Downstream Impact:**
- silver.tokyo_beta_tenant_room_info: 920 fewer rows than expected
- gold.daily_activity_summary: 8 days of undercounted metrics
- QuickSight dashboards: Inaccurate occupancy data for 8 days

### Timeline

| Date/Time | Event |
|-----------|-------|
| Feb 1 | staging.inquiries stops updating |
| Feb 2 | staging.movings, staging.rooms stop updating |
| Feb 3-9 | No updates to affected tables |
| Feb 10 02:00 | Issue detected via status check |
| Feb 10 02:30 | Root cause identified: Glue jobs not running |
| Feb 10 02:45 | AWS SSO login completed (gghouse profile) |
| Feb 10 02:50 | Manual dump load initiated |
| Feb 10 03:00 | All staging tables refreshed (< 1 day old) |
| Feb 10 03:10 | tokyo_beta_tenant_room_info redeployed (12,150 rows) |
| Feb 10 03:15 | Silver & gold transformers triggered |
| Feb 10 03:30 | **Issue resolved** - all data fresh |

### Root Cause

**Primary Cause:** AWS Glue ETL jobs existed in Terraform state but were not being triggered automatically.

**Contributing Factors:**
1. No monitoring infrastructure (no alarms for table freshness)
2. EventBridge schedule may not have been configured correctly
3. Multi-account AWS setup caused AccessDenied errors during investigation
4. No dbt freshness tests to catch stale data in CI/CD

### Resolution

**Immediate Fix (Manual):**
1. Performed AWS SSO login to correct account (gghouse, 343881458651)
2. Created Python script to download latest dump from S3
3. Executed `scripts/load_full_dump_to_staging.py` 
   - Loaded gghouse_20260210.sql (947MB)
   - 131,253 rows loaded in 85 seconds
   - Automatic backups created before load
4. Redeployed silver.tokyo_beta_tenant_room_info with fresh data
5. Triggered silver and gold transformers
6. Verified all tables updated

**Permanent Fixes Implemented:**
1. **AWS Profile Enforcement**
   - Created `.envrc` file (forces AWS_PROFILE=gghouse)
   - Uses direnv to auto-load profile
   - Prevents wrong account usage

2. **Data Freshness Monitoring**
   - CloudWatch alarms for table staleness (> 2 days = alert)
   - Lambda function checking freshness daily (9 AM JST)
   - SNS email alerts configured
   - Metrics: `TokyoBeta/DataQuality` namespace

3. **Emergency Recovery Scripts**
   - `scripts/emergency_staging_fix.py` - Quick S3-to-DB loader
   - `scripts/load_full_dump_to_staging.py` - Full dump loader
   - Both tested and documented
   - Target recovery time: < 15 minutes

---

## Incident #2: ETL Pipeline Fixes (Feb 9, 2026)

**Date:** 2026-02-09  
**Severity:** Medium  
**Status:** ✅ Resolved

### Summary
Multiple issues were identified and fixed in the ETL pipeline components (Staging Loader, Silver Transformer, Gold Transformer).

### Issues Fixed
1.  **LLM Nationality Enrichment Not Running**: Enrichment logic was only in the unused monolithic script. Added `enrich_nationality_data()` to `staging_loader.py`.
2.  **Gold Transformer Missing `dbt deps`**: Job failed because dependencies weren't installed. Added `install_dbt_dependencies()`.
3.  **Gold Transformer SQL Syntax Error**: Trailing comma in `tenant_status_transitions.sql`. Fixed syntax.
4.  **Silver Transformer `UnboundLocalError`**: Import issue with `re` module. Fixed scope.
5.  **Timeouts Too Short**: Jobs timing out at 10 mins. Increased to 60 mins via Terraform.

### Resolution
All scripts updated, uploaded to S3, and verified with test runs.

---

## Incident #3: Tenant Room Info Deviation (Feb 9, 2026)

**Date:** 2026-02-09  
**Severity:** Medium  
**Status:** ✅ Resolved (Root Cause Identified)

### Summary
A -7.3% deviation was observed between the Excel export (12,070 rows) and the current database (11,190 rows).

### Root Cause
**Database Schema Consolidation**: `contract_type` codes 3, 6, and 9 were eliminated from the database and merged into code 1 (一般) *after* the Excel export was generated.
-   The Excel file is a historical snapshot.
-   The database is the current source of truth.
-   **Deduplication logic is correct.**

### Resolution
-   Accepted deviation as legitimate schema change.
-   Updated documentation to reflect `moving.moving_agreement_type` as the correct field for contract types (preserves original 5 codes).
-   Updated `.cursorrules` to mandate `moving.moving_agreement_type`.

---

## Incident #4: Inquiry Count Logic Flaw (Feb 9, 2026)

**Date:** 2026-02-09  
**Severity:** Critical  
**Status:** ⚠️ Investigating

### Summary
The `inquiries_count` metric in `gold.daily_activity_summary` is severely undercounting. Investigation reveals that tenants are **NOT registered in the system at inquiry stage**, but rather when they reach "Initial Rent" (status 5) or later.

### Findings
-   99.37% of tenant records are at status 6+ (post-application).
-   0 new inquiries (status 1-3) recorded in the last 7 days, despite new registrations.
-   **Conclusion:** The current `staging.tenants` table does not capture early-stage inquiries.

### Next Steps
1.  Investigate source system for a separate `inquiries` or `leads` table.
2.  If no table exists, redefine metric to "New Registrations" instead of "Inquiries".

---

## Incident #5: Occupancy Data Discrepancy vs Miyago Report (Feb 11, 2026)

**Date:** 2026-02-11  
**Detected:** 2026-02-11 17:30 JST (external report), investigated on 2026-02-13  
**Severity:** High  
**Status:** ✅ Resolved (Logic fixes implemented)

### Summary

Miyago (GG House) reported the following values on 2026-02-11 17:30:
- Feb move-ins: 304 vs our 363 (+59)
- Mar move-ins: 131 vs our 102 (-29)
- Feb move-outs: 549 vs our 511 (-38)
- Mar move-outs: 393 vs our 385 (-8)
- Feb 28 move-outs: 139 vs our 139 (exact match)

We reproduced our numbers directly from `gold.occupancy_daily_metrics` and investigated both occupancy and contract pipelines. The discrepancy was primarily caused by snapshot timing lag and KPI filter semantics, not by a large cancellation population.

### Findings

1. **Our KPI numbers reproduced exactly from `gold.occupancy_daily_metrics`.**
   - 2026-02: move-ins 363, move-outs 511
   - 2026-03: move-ins 102, move-outs 385
   - 2026-02-28 move-outs: 139

2. **Snapshot timing lag was significant at investigation time.**
   - Current date during investigation: 2026-02-13
   - Latest `silver.tenant_room_snapshot_daily.snapshot_date`: 2026-02-10
   - Lag: 3 days

3. **Cancellation impact was small for the target population.**
   - Feb move-ins on as-of snapshot (status 4/5): 171
   - Cancelled inside that set: 2
   - Conclusion: cancellation inclusion alone does not explain +59.

4. **Move-out date field mismatch was not a major driver on as-of snapshot.**
   - As-of snapshot 2026-02-10:
     - Feb `moveout_date`: 405
     - Feb `moveout_plans_date`: 2
     - Feb union (`OR`): 405
     - Mar `moveout_date`: 385
     - Mar `moveout_plans_date`: 0
     - Mar union (`OR`): 385
   - Conclusion: `moveout_plans_date` adds near-zero in this comparison window.

5. **Move-in KPI semantics are hybrid and can diverge from external definitions.**
   - Current logic mixes:
     - Historical dates: status IN (4,5,6,7,9) with `move_in_date = snapshot_date`
     - Future dates: status IN (4,5) from single as-of snapshot
   - This hybrid behavior can create mismatches depending on counterpart definition of "入居予定".

### Resolution

Implemented changes:

1. **Anchored KPI computation to latest available snapshot date**
   - Updated `glue/scripts/gold_transformer.py`
   - Updated `glue/scripts/occupancy_kpi_updater.py`
   - Replaced wall-clock `today` anchoring with `MAX(snapshot_date)` anchoring to prevent stale-snapshot misclassification and zeroing.

2. **Promoted occupancy KPI upsert into daily ETL with explicit runtime toggles**
   - Updated `glue/scripts/daily_etl.py`
   - Added `gold.occupancy_daily_metrics` upsert step (lookback/forward window around the as-of snapshot date)
   - Added runtime flags to enable/disable the step and tune the backfill window

### Validation

- Added/updated unit tests in `glue/tests/test_daily_etl.py` for the new runtime parsing and dbt phase behavior.
- Confirmed KPI anchoring uses `MAX(snapshot_date)` to avoid stale snapshot misclassification.
- Logic patches are in code; production table values will reflect updated behavior after next dbt/Glue run.

### Prevention Measures

1. Use `MAX(snapshot_date)` as KPI as-of anchor for all future projections.
2. Keep occupancy KPI future projections anchored to a single as-of snapshot (not wall-clock date) when snapshot ingestion can lag.

---

## Template for Future Incidents

**Date:**  
**Detected:**  
**Severity:** Critical / High / Medium / Low  
**Status:** Investigating / Resolved  
**Resolution Time:**

### Summary
[Brief description of the incident]

### Impact
[What was affected and how severely]

### Timeline
| Date/Time | Event |
|-----------|-------|
| | |

### Root Cause
[What went wrong and why]

### Resolution
[How it was fixed]

### Lessons Learned
[What we learned and what changes we made]

### Prevention Measures
[Steps taken to prevent recurrence]

---
