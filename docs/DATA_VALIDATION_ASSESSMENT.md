# Data Validation Assessment (Consolidated)

**Date**: 2026-01-30  
**Source**: `gghouse_20260130.sql` (897MB)  
**Scope**: Field mapping, schema validation, full‑dump coverage, local ETL run, data quality findings

## Executive Summary

✅ All required fields for the 4 BI tables exist and are populated in the source schema.  
✅ Local ETL (dbt) ran successfully on the full dump.  
✅ Room coverage is solid: **16,401 rooms** (expected ~16,000).  
⚠️ Data quality issues detected: geocoding out-of-bounds, non‑positive rent, future dates, and a small number of date inconsistencies.

## Required BI Tables (Validated)

### 1. Daily Activity Summary (申し込み・契約)
**Metrics**: 申し込み, 契約締結, 確定入居者, 確定退去者, 稼働室数増減 (by 個人/法人)

**Key fields**:
- `movings.created_at` (applications)
- `movings.movein_decided_date` (contracts signed)
- `movings.movein_date` (confirmed move‑ins)
- `movings.moveout_date_integrated` (confirmed move‑outs)
- `movings.moving_agreement_type` (individual/corporate)
- `movings.cancel_flag`, `movings.is_moveout`

### 2. New Contracts (新規)
**Fields**: AssetID_HJ, Room Number, 契約体系, 契約チャンネル, 原契約締結日, 契約締結日, 契約開始日, 賃料発生日, 契約満了日, 再契約フラグ, 月額賃料, 個人・法人フラグ, 性別, 年齢, 国籍, 職種, 在留資格

**Key fields**:
- `apartments.unique_number`
- `rooms.room_number`
- `movings.moving_agreement_type`, `movings.movein_decided_date`, `movings.movein_date`
- `movings.rent_start_date`, `movings.expiration_date`, `movings.move_renew_flag`, `movings.rent`
- `tenants.media_id`, `tenants.gender_type`, `tenants.age`, `tenants.nationality`, `tenants.affiliation`, `tenants.personal_identity`
- `apartments.latitude`, `apartments.longitude`

### 3. Moveouts (退去)
Same as New Contracts + 解約通知日, 退去日:
- `movings.moveout_receipt_date`
- `movings.moveout_date_integrated` (via safe_moveout_date)

### 4. Moveout Notices (退去通知)
Same as Moveouts, filtered by `moveout_receipt_date` and 24‑month rolling window.

## Field Mapping Summary

All critical fields exist in source schema:
- `movings.moving_agreement_type`, `movings.moveout_receipt_date`, `movings.move_renew_flag`
- `movings.rent_start_date`, `movings.expiration_date`, `movings.moveout_date_integrated`
- `tenants.media_id`, `tenants.personal_identity`, `tenants.affiliation`
- `apartments.unique_number`, `apartments.latitude`, `apartments.longitude`
- `rooms.room_number`, `m_nationalities.nationality_name`

**Notes**:
- Room number column is **`rooms.room_number`** (not `room_no`).
- `tenant_contract_type` exists but is often NULL; `moving_agreement_type` is more reliable for classification.

## Full‑Dump Coverage (Local Staging)

| Table | Rows | Notes |
|------|------|-------|
| `rooms` | 16,401 | Expected ~16,000 owned rooms → ✅ coverage solid |
| `apartments` | 1,202 | Matches schema description |
| `tenants` | 50,175 | Current + historical |
| `movings` | 62,038 | Contract lifecycle records |
| `m_nationalities` | 200 | Master list |

### Room Status Distribution
- `status = 1` (Available for use): 15,776
- `status = 4` (Living room use): 56
- `status = 6` (Not available for use): 569

### Tenant Status (Active Leases)
Active leases defined as `status IN (7, 9, 10, 13)`:
- **Active Leases**: 11,144
- **Moved out**: 29,167
- **Canceled**: 5,270
- **Awaiting Maintenance**: 3,344
- Others: 1,300+

## Local ETL Run (Full Dump)

dbt run results:
- `daily_activity_summary`: 5,246 rows
- `new_contracts`: 17,573 rows
- `moveouts`: 15,768 rows
- `moveout_notices`: 3,791 rows

### Key Null Rates (new_contracts)
- `contract_channel`: 0 / 17,573
- `rent_start_date`: 17,570 / 17,573 (mostly NULL in source)
- `contract_expiration_date`: 11,156 / 17,573

## Data Quality Findings (Full Data)

- **Geocoding out of Tokyo bounds**:
  - `new_contracts`: 629
  - `moveouts`: 567
  - `moveout_notices`: 115
- **Monthly rent <= 0**: 614 rows in `new_contracts`
- **Moveout before contract start**: 1 row in `moveouts`
- **Negative stay days**: 1 row in `moveouts`
- **Future activity dates**: 100 rows in `daily_activity_summary` (likely bad `created_at`)

## Data Quality Risks (Schema‑Level)

- Null handling on date fields (`moveout_plans_date`, `moveout_date`, etc.)
- String values like `'NULL'` and `'--'` in text/number fields
- No FK constraints; orphan records possible
- Pre‑aggregated columns in `apartments` may be stale

## Additional Fields Available (Not in 4 BI Tables)

From `data/database_schema_description.txt`, available but not modeled:
- `tenants.status` (Active Leases reporting)
- `rooms.status`, `rooms.gender_type`, `rooms.bed_type` (room attributes)

## Fixes Applied During Validation

- Added table aliases for clarity and correctness
- Updated `safe_moveout_date` macro to accept table alias
- `is_corporate` macro now emits valid `IN (2, 3, 4)` SQL
- Removed incompatible `dbt_utils.log_test_results()` hook
- Corrected room number column: `room_number`

## Recommended Next Steps

1. **Decide how to handle out‑of‑bounds geocodes** (filter or fix upstream).
2. **Decide how to handle zero/negative rent** (filter or clean).
3. **Review `created_at` future dates** (exclude or fix).
4. **Optional**: Add an `active_leases` model using `tenants.status`.

---

## References

- Full dump: `data/samples/gghouse_20260130.sql`
- Schema definition: `data/samples/schema_definitions.json`
- Source schema notes: `data/database_schema_description.txt`
- Data dictionary (separate): `docs/DATA_DICTIONARY.md`
