# Data Validation Report

**Date**: 2026-01-30  
**Source**: `gghouse_20260130.sql` (897MB)  
**Purpose**: Validate that all required fields exist for 4 BI tables

## Executive Summary

✅ **VALIDATION PASSED** - All critical fields exist in the source database schema.

### Key Findings

1. **All Required Fields Present**: 100% of fields needed for the 4 BI tables exist in the source schema
2. **Minor Issues Fixed**: 
   - Added table aliases to dbt models for clarity
   - Updated `safe_moveout_date` macro to support table aliases
   - Changed applications CTE to use `moving_agreement_type` instead of `tenant_contract_type` for consistency
3. **Data Quality**: Sample data shows expected formats and value ranges

## Table-by-Table Validation

### Table 1: Daily Activity Summary (申し込み・契約)

**Status**: ✅ **PASS**

| Requirement | Field | Status | Notes |
|-------------|-------|--------|-------|
| 申し込み date | `created_at` | ✅ | Present in movings table |
| 申し込み classification | `moving_agreement_type` | ✅ | Using moving_agreement_type (fixed) |
| 契約締結 date | `movein_decided_date` | ✅ | Present |
| 契約締結 classification | `moving_agreement_type` | ✅ | Present |
| 確定入居者 date | `movein_date` | ✅ | Present |
| 確定入居者 classification | `moving_agreement_type` | ✅ | Present |
| 確定退去者 date | `moveout_date_integrated` | ✅ | Present |
| 確定退去者 classification | `moving_agreement_type` | ✅ | Present |
| Filter: valid contracts | `cancel_flag` | ✅ | Present |

**Issues Fixed**:
- Changed applications CTE to use `moving_agreement_type` instead of `tenant_contract_type` for consistency
- Added table alias `m` to all CTEs for clarity

---

### Table 2: New Contracts (新規)

**Status**: ✅ **PASS**

| Requirement | Field | Status | Notes |
|-------------|-------|--------|-------|
| AssetID_HJ | `apartments.unique_number` | ✅ | Present |
| Room Number | `rooms.room_number` | ✅ | Present |
| 契約体系 | `movings.moving_agreement_type` | ✅ | Present |
| 契約チャンネル | `tenants.media_id` | ✅ | Present |
| 原契約締結日 | `movings.original_movein_date` | ✅ | Present |
| 契約締結日 | `movings.movein_decided_date` | ✅ | Present |
| 契約開始日 | `movings.movein_date` | ✅ | Present |
| 賃料発生日 | `movings.rent_start_date` | ✅ | Present |
| 契約満了日 | `movings.expiration_date` | ✅ | Present |
| 再契約フラグ | `movings.move_renew_flag` | ✅ | Present |
| 月額賃料 | `movings.rent` | ✅ | Present |
| 個人・法人フラグ | `movings.moving_agreement_type` | ✅ | Via is_corporate macro |
| 性別 | `tenants.gender_type` | ✅ | Present |
| 年齢 | `tenants.age` or `birth_date` | ✅ | Present (with fallback) |
| 国籍 | `tenants.nationality` or `m_nationalities.nationality_name` | ✅ | Present (with fallback) |
| 職種 | `tenants.affiliation` | ✅ | Present (needs cleaning) |
| 在留資格 | `tenants.personal_identity` | ✅ | Present (needs cleaning) |
| Latitude | `apartments.latitude` | ✅ | Present |
| Longitude | `apartments.longitude` | ✅ | Present |

**Issues**: None

---

### Table 3: Move-outs (退去)

**Status**: ✅ **PASS**

All fields from Table 2 plus:

| Requirement | Field | Status | Notes |
|-------------|-------|--------|-------|
| 解約通知日 | `movings.moveout_receipt_date` | ✅ | Present |
| 退去日 | `movings.moveout_date_integrated` | ✅ | Via safe_moveout_date macro |

**Issues**: None

---

### Table 4: Move-out Notices (退去通知)

**Status**: ✅ **PASS**

All fields from Table 3, with:
- Trigger: `moveout_receipt_date IS NOT NULL`
- Rolling window: 24 months (configurable)

**Issues**: None

---

## Schema Validation

### Field Counts

| Table | Expected Columns | Actual Columns | Status |
|-------|------------------|----------------|--------|
| movings | 90+ | 101 | ✅ |
| tenants | 80+ | 114 | ✅ |
| apartments | 60+ | 87 | ✅ |
| rooms | 20+ | 35 | ✅ |
| m_nationalities | 5+ | 11 | ✅ |

### Critical Fields Verification

All critical fields referenced in dbt models exist in the source schema:

✅ `movings.moving_agreement_type`  
✅ `movings.tenant_contract_type`  
✅ `movings.moveout_receipt_date`  
✅ `movings.move_renew_flag`  
✅ `movings.rent_start_date`  
✅ `movings.expiration_date`  
✅ `movings.moveout_date_integrated`  
✅ `movings.is_moveout`  
✅ `movings.created_at`  
✅ `tenants.media_id`  
✅ `tenants.personal_identity`  
✅ `tenants.affiliation`  
✅ `apartments.unique_number`  
✅ `apartments.latitude`  
✅ `apartments.longitude`  
✅ `rooms.room_number`  
✅ `m_nationalities.nationality_name`  

## Sample Data Analysis

### Data Formats

From sample rows:
- **Dates**: Format `'YYYY-MM-DD'` ✅
- **Timestamps**: Format `'YYYY-MM-DD HH:MM:SS'` ✅
- **Flags**: Values `0` or `1` ✅
- **Contract Types**: Numeric values (e.g., `9`) ✅

### Value Ranges Observed

- `moving_agreement_type`: `9`, `NULL` (needs full dataset validation for corporate types)
- `move_renew_flag`: `0`, `1` ✅
- `cancel_flag`: `0`, `1` ✅
- `is_moveout`: `0`, `1` ✅
- `gender_type`: `1`, `2` (Male, Female) ✅

## Code Changes Made

### 1. Updated `dbt/models/staging/_sources.yml`
- Added missing field definitions:
  - `moving_agreement_type`
  - `tenant_contract_type`
  - `moveout_receipt_date`
  - `move_renew_flag`
  - `rent_start_date`
  - `expiration_date`
  - `created_at`
  - `media_id`
  - `personal_identity`
  - `m_nationalities` table definition

### 2. Updated `dbt/models/analytics/daily_activity_summary.sql`
- Added table alias `m` to all CTEs
- Changed applications CTE to use `moving_agreement_type` instead of `tenant_contract_type`
- Updated all field references to use table alias

### 3. Updated `dbt/macros/safe_moveout_date.sql`
- Added optional `table_alias` parameter
- Supports both aliased and non-aliased usage

### 4. Updated `dbt/models/analytics/moveouts.sql`
- Updated `safe_moveout_date()` calls to use table alias `'m'`

### 5. Updated `dbt/models/analytics/moveout_notices.sql`
- Updated `safe_moveout_date()` calls to use table alias `'m'`

## Recommendations

### Immediate Actions
1. ✅ **COMPLETE**: All field mappings validated
2. ✅ **COMPLETE**: dbt models updated with correct field references
3. ⏭️ **NEXT**: Test dbt models against local database with sample data

### Future Validations
1. **Corporate Contract Types**: Review full dataset to confirm `corporate_contract_types: [2, 3, 4]` is correct
2. **Applications Date**: Validate with business users if `created_at` is the correct field for "申し込み" date
3. **Data Quality Checks**: Run dbt tests to validate data quality rules

## Test Results

### Schema Extraction
- ✅ Successfully extracted schema for 5 key tables
- ✅ Generated `schema_definitions.json` with 348 total columns

### Sample Data Extraction
- ✅ Successfully extracted 100 sample rows from each table
- ✅ Generated CSV files for analysis
- ✅ All files readable and properly formatted

### Field Mapping
- ✅ All expected fields found in source schema
- ✅ No missing critical fields
- ✅ All transformations documented

## Conclusion

**VALIDATION STATUS**: ✅ **PASSED**

All required fields for the 4 BI tables exist in the source database schema. The dbt models have been updated to use correct field references with proper table aliases. The data pipeline is ready for testing with actual data.

**Next Steps**:
1. Set up local MySQL database with sample data
2. Run dbt models to validate transformations
3. Review output data quality
4. Deploy to production environment

---

## Files Generated

1. ✅ `data/samples/gghouse_20260130.sql` - Full SQL dump (897MB)
2. ✅ `data/samples/schema_definitions.json` - Schema definitions
3. ✅ `data/samples/movings_sample.csv` - 100 sample rows
4. ✅ `data/samples/tenants_sample.csv` - 100 sample rows
5. ✅ `data/samples/apartments_sample.csv` - 100 sample rows
6. ✅ `data/samples/rooms_sample.csv` - 100 sample rows
7. ✅ `data/samples/m_nationalities_sample.csv` - 100 sample rows
8. ✅ `docs/FIELD_MAPPING.md` - Field mapping documentation
9. ✅ `docs/DATA_DICTIONARY.md` - Data dictionary
10. ✅ `docs/VALIDATION_REPORT.md` - This report

## Scripts Created

1. ✅ `scripts/extract_schema.py` - Schema extraction tool
2. ✅ `scripts/extract_samples.py` - Sample data extraction tool
