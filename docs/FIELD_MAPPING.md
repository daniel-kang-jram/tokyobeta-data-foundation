# Field Mapping: Expected vs Actual Schema

**Date**: 2026-01-30  
**Source**: `gghouse_20260130.sql` (897MB)  
**Purpose**: Validate that all required fields exist for the 4 BI tables

## Summary

✅ **All critical fields exist in the source database!**  
⚠️ **Minor issues found**: Some field references need table aliases, and one field (`created_at` for applications) may need validation.

## Table 1: Daily Activity Summary (申し込み・契約)

### Expected Metrics
- 申し込み (Applications) - by date, 個人/法人
- 契約締結 (Contracts Signed) - by date, 個人/法人  
- 確定入居者 (Confirmed Move-ins) - by date, 個人/法人
- 確定退去者 (Confirmed Move-outs) - by date, 個人/法人
- 稼働室数増減 (Net Occupancy Delta) - calculated

### Field Mappings

| Expected Field (dbt) | Actual Field (Source) | Status | Notes |
|----------------------|----------------------|--------|-------|
| `created_at` | `movings.created_at` | ✅ | Used for applications date |
| `tenant_contract_type` | `movings.tenant_contract_type` | ✅ | Line 42 in movings table |
| `movein_decided_date` | `movings.movein_decided_date` | ✅ | Contract signing date |
| `moving_agreement_type` | `movings.moving_agreement_type` | ✅ | Line 41 in movings table |
| `movein_date` | `movings.movein_date` | ✅ | Confirmed move-in date |
| `moveout_date_integrated` | `movings.moveout_date_integrated` | ✅ | Line 90 in movings table |
| `is_moveout` | `movings.is_moveout` | ✅ | Line 91 in movings table |
| `cancel_flag` | `movings.cancel_flag` | ✅ | Filter for valid contracts |

### Issues Found

1. **Applications CTE** (line 19 in `daily_activity_summary.sql`):
   - Uses `tenant_contract_type` without table alias
   - Should be `m.tenant_contract_type` or ensure proper context
   - **Fix**: Add table alias `m` to the FROM clause

2. **Applications Date Field**:
   - Currently uses `created_at` for applications
   - Need to verify if `created_at` represents application date or contract creation
   - **Recommendation**: Validate with business users if `created_at` is correct for "申し込み"

## Table 2: New Contracts (新規)

### Expected Fields
AssetID_HJ, Room Number, 契約体系, 契約チャンネル, 原契約締結日, 契約締結日, 契約開始日, 賃料発生日, 契約満了日, 再契約フラグ, 月額賃料, 個人・法人フラグ, 性別, 年齢, 国籍, 職種, 在留資格

### Field Mappings

| Expected Field (dbt) | Actual Field (Source) | Status | Notes |
|----------------------|----------------------|--------|-------|
| `a.unique_number` | `apartments.unique_number` | ✅ | AssetID_HJ |
| `r.room_number` | `rooms.room_number` | ✅ | Room Number (DB column is `room_number`) |
| `m.moving_agreement_type` | `movings.moving_agreement_type` | ✅ | 契約体系 |
| `t.media_id` | `tenants.media_id` | ✅ | 契約チャンネル (line 53) |
| `m.original_movein_date` | `movings.original_movein_date` | ✅ | 原契約締結日 |
| `m.movein_decided_date` | `movings.movein_decided_date` | ✅ | 契約締結日 |
| `m.movein_date` | `movings.movein_date` | ✅ | 契約開始日 |
| `m.rent_start_date` | `movings.rent_start_date` | ✅ | 賃料発生日 (line 43) |
| `m.expiration_date` | `movings.expiration_date` | ✅ | 契約満了日 (line 61) |
| `m.move_renew_flag` | `movings.move_renew_flag` | ✅ | 再契約フラグ (line 27) |
| `m.rent` | `movings.rent` | ✅ | 月額賃料 |
| `m.moving_agreement_type` | `movings.moving_agreement_type` | ✅ | For 個人・法人 classification |
| `t.gender_type` | `tenants.gender_type` | ✅ | 性別 (line 9) |
| `t.age` | `tenants.age` | ✅ | 年齢 (line 51) |
| `t.nationality` | `tenants.nationality` | ✅ | 国籍 (line 52) |
| `t.affiliation` | `tenants.affiliation` | ✅ | 職種 (line 25) |
| `t.personal_identity` | `tenants.personal_identity` | ✅ | 在留資格 (line 11) |
| `a.latitude` | `apartments.latitude` | ✅ | Geolocation |
| `a.longitude` | `apartments.longitude` | ✅ | Geolocation |

### Issues Found

**None** - All fields exist and are correctly referenced!

## Table 3: Move-outs (退去)

### Expected Fields
Same as Table 2 + 解約通知日, 退去日

### Additional Field Mappings

| Expected Field (dbt) | Actual Field (Source) | Status | Notes |
|----------------------|----------------------|--------|-------|
| `m.moveout_receipt_date` | `movings.moveout_receipt_date` | ✅ | 解約通知日 (line 26) |
| `moveout_date_integrated` | `movings.moveout_date_integrated` | ✅ | 退去日 (via safe_moveout_date macro) |

### Issues Found

**None** - All fields exist!

## Table 4: Move-out Notices (退去通知)

### Expected Fields
Same as Table 3, rolling 24-month window

### Field Mappings

| Expected Field (dbt) | Actual Field (Source) | Status | Notes |
|----------------------|----------------------|--------|-------|
| `m.moveout_receipt_date` | `movings.moveout_receipt_date` | ✅ | Trigger field for notices |
| All other fields | Same as Table 3 | ✅ | Same structure |

### Issues Found

**None** - All fields exist!

## Master Data Tables

### m_nationalities

| Expected Field (dbt) | Actual Field (Source) | Status | Notes |
|----------------------|----------------------|--------|-------|
| `n.nationality_name` | `m_nationalities.nationality_name` | ✅ | Used as fallback for nationality |

## Data Quality Observations

### Sample Data Analysis

From `movings_sample.csv`:
- `moving_agreement_type`: Values observed: `9`, `NULL` (needs validation of corporate types)
- `tenant_contract_type`: Values observed: `NULL` (may need alternative field)
- `moveout_receipt_date`: Format: `'2018-12-01'` (date format correct)
- `move_renew_flag`: Values: `0`, `1` (boolean flag correct)
- `moveout_date_integrated`: Format: `'2018-12-15'` (date format correct)

### Recommendations

1. **Validate Corporate Contract Types**:
   - Current dbt variable: `corporate_contract_types: [2, 3, 4]`
   - Sample shows `moving_agreement_type = 9`
   - **Action**: Review actual values in full dataset to confirm corporate types

2. **Applications Date Field**:
   - Verify if `created_at` is the correct field for "申し込み" date
   - Alternative: May need `movein_exposition_date` or another field

3. **Tenant Contract Type**:
   - `tenant_contract_type` exists but may be NULL in many rows
   - `moving_agreement_type` is more populated
   - **Current approach**: Using `moving_agreement_type` for most classifications (correct)

## Summary of Required Fixes

### Critical (Must Fix)
1. ✅ **None** - All critical fields exist

### Important (Should Fix)
1. **daily_activity_summary.sql line 19**: Add table alias for `tenant_contract_type`
2. **Validate applications date field**: Confirm `created_at` is correct for 申し込み

### Nice to Have
1. Review corporate contract type codes in full dataset
2. Document any business logic differences between `tenant_contract_type` and `moving_agreement_type`

## Next Steps

1. ✅ Schema extraction complete
2. ✅ Sample data extracted
3. ✅ Field mapping validated
4. ⏭️ Update dbt models with fixes
5. ⏭️ Test with local database
6. ⏭️ Create data dictionary

## Additional Fields from Schema Description

The following fields are present in the source schema (per `data/database_schema_description.txt`) but are **not used** in the 4 required BI tables:

- `tenants.status` → useful for Active Leases reporting
- `rooms.status` → room availability classification
- `rooms.gender_type`, `rooms.bed_type` → room attributes

These can be added as separate models if needed.
