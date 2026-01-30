# Data Dictionary - GGhouse PMS Database

**Last Updated**: 2026-01-30  
**Source**: `gghouse_20260130.sql` (897MB, 81 tables)

## Overview

This document describes the key tables and fields used for the BI analytics pipeline. The source database contains 81 tables; this dictionary focuses on the 5 core tables used for analytics transformations.

## Core Tables

### 1. movings (101 columns)
**Purpose**: Contract lifecycle data - move-ins, move-outs, renewals  
**Primary Key**: `id`  
**Row Count**: ~50,000+ (estimated from 897MB dump)

#### Key Fields for Analytics

| Field Name | Type | Description | Japanese | Usage |
|------------|------|-------------|----------|-------|
| `id` | INT | Primary key - contract/moving ID | - | Join key |
| `tenant_id` | INT | Foreign key to tenants | - | Join to tenant demographics |
| `apartment_id` | INT | Foreign key to apartments | - | Join to property data |
| `room_id` | INT | Foreign key to rooms | - | Join to room data |
| `movein_date` | DATE | Actual move-in date | 契約開始日 | Confirmed move-ins metric |
| `movein_decided_date` | DATETIME | Contract signing date | 契約締結日 | Contracts signed metric |
| `original_movein_date` | DATE | Original contract date (for renewals) | 原契約締結日 | Renewal tracking |
| `moveout_date` | DATE | Final rent date | 最終賃料日 | Moveout calculation |
| `moveout_plans_date` | DATE | Actual moveout date | 実退去日 | Moveout calculation |
| `moveout_date_integrated` | DATE | Computed moveout date | 退去日 | Primary moveout field |
| `moveout_receipt_date` | DATE | Moveout notice received date | 解約通知日 | Moveout notices trigger |
| `rent_start_date` | DATE | Rent start date | 賃料発生日 | Contract details |
| `expiration_date` | DATE | Contract expiration date | 契約満了日 | Contract details |
| `rent` | DECIMAL | Monthly rent amount | 月額賃料 | Financial metrics |
| `moving_agreement_type` | INT | Contract agreement type | 契約体系 | Individual/corporate classification |
| `tenant_contract_type` | INT | Tenant contract type | - | Alternative classification (often NULL) |
| `move_renew_flag` | TINYINT | Renewal flag (0=no, 1=yes) | 再契約フラグ | Renewal tracking |
| `cancel_flag` | TINYINT | Cancellation flag (0=active, 1=cancelled) | - | Filter for valid contracts |
| `is_moveout` | TINYINT | Moveout completion (0=active, 1=completed) | - | Filter for completed moveouts |
| `created_at` | TIMESTAMP | Record creation timestamp | - | Applications date (申し込み) |

#### Business Logic

- **Individual vs Corporate**: Determined by `moving_agreement_type` values
  - Corporate types: `[2, 3, 4]` (configurable in `dbt_project.yml`)
  - Individual: All other values
- **Moveout Date Priority**: `moveout_date_integrated` > `moveout_plans_date` > `moveout_date`
- **Valid Contracts**: `cancel_flag = 0` AND `movein_decided_date IS NOT NULL`

---

### 2. tenants (114 columns)
**Purpose**: Tenant demographics and contact information  
**Primary Key**: `id`  
**Row Count**: ~50,000+ (estimated)

#### Key Fields for Analytics

| Field Name | Type | Description | Japanese | Usage |
|------------|------|-------------|----------|-------|
| `id` | INT | Primary key - tenant ID | - | Join key |
| `last_name` | VARCHAR | Last name | 姓 | Name display |
| `first_name` | VARCHAR | First name | 名 | Name display |
| `full_name` | VARCHAR | Full name (may contain string 'NULL') | 氏名 | Name display (needs cleaning) |
| `gender_type` | TINYINT | Gender code | 性別 | Demographics |
| `birth_date` | DATE | Date of birth | 生年月日 | Age calculation |
| `age` | INT | Current age (may be stale) | 年齢 | Demographics |
| `nationality` | VARCHAR | Nationality text | 国籍 | Demographics |
| `m_nationality_id` | INT | Foreign key to nationalities master | - | Join to master data |
| `personal_identity` | VARCHAR | Residence status | 在留資格 | Demographics (may contain 'NULL' string) |
| `affiliation` | VARCHAR | Company/school name | 職種 | Demographics (may contain 'NULL' string) |
| `media_id` | INT | Contract channel ID | 契約チャンネル | Marketing attribution |
| `contract_type` | INT | Contract type (1=individual, 2/3=corporate) | - | Alternative classification |
| `reason_moveout` | INT | Moveout reason ID | 退去理由 | Moveout analysis |
| `status` | INT | Tenant status code | ステータス設定 | Active lease classification |

#### Data Quality Notes

- **String NULLs**: `full_name`, `personal_identity`, `affiliation` may contain literal string `'NULL'` instead of SQL NULL
- **Age Calculation**: Prefer `TIMESTAMPDIFF(YEAR, birth_date, CURRENT_DATE)` over `age` column if available
- **Gender Mapping**: `1 = Male`, `2 = Female`, other = `Other`

---

### 3. apartments (87 columns)
**Purpose**: Property/building master data  
**Primary Key**: `id`  
**Row Count**: ~1,000+ (estimated)

#### Key Fields for Analytics

| Field Name | Type | Description | Japanese | Usage |
|------------|------|-------------|----------|-------|
| `id` | INT | Primary key - apartment ID | - | Join key |
| `unique_number` | VARCHAR | Property ID from GUI system | AssetID_HJ | Property identifier |
| `apartment_name` | VARCHAR | Property name (Japanese) | 物件名 | Property display |
| `apartment_name_en` | VARCHAR | Property name (English) | - | Property display |
| `prefecture` | VARCHAR | Prefecture (都道府県) | 都道府県 | Location |
| `municipality` | VARCHAR | Municipality (市区町村) | 市区町村 | Location |
| `address` | VARCHAR | Street address | 住所 | Location |
| `full_address` | VARCHAR | Complete address | 住所（完全） | Location |
| `zip_code` | VARCHAR | Postal code | 郵便番号 | Location |
| `latitude` | DECIMAL(8,6) | Latitude from geocoding | 緯度 | Geolocation |
| `longitude` | DECIMAL(9,6) | Longitude from geocoding | 経度 | Geolocation |
| `room_count` | INT | Total number of rooms | 総部屋数 | Property metrics |
| `vacancy_room_count` | INT | Current vacant room count | 空室数 | Property metrics |

#### Data Quality Notes

- **Geocoding**: Latitude/longitude already present from Google Maps API
- **Validation**: Coordinates should be within Tokyo bounds (35.5-35.9°N, 139.5-140°E)
- **Required for Analytics**: Only contracts with valid geocoding (`latitude IS NOT NULL AND longitude IS NOT NULL`)

---

### 4. rooms (35 columns)
**Purpose**: Individual room data  
**Primary Key**: `id`  
**Row Count**: ~10,000+ (estimated)

#### Key Fields for Analytics

| Field Name | Type | Description | Japanese | Usage |
|------------|------|-------------|----------|-------|
| `id` | INT | Primary key - room ID | - | Join key |
| `apartment_id` | INT | Foreign key to apartments | - | Join to property |
| `room_number` | VARCHAR | Room number | 部屋番号 | Room identifier |

---

### 5. m_nationalities (11 columns)
**Purpose**: Nationalities master data  
**Primary Key**: `id`  
**Row Count**: ~200 (estimated)

#### Key Fields for Analytics

| Field Name | Type | Description | Japanese | Usage |
|------------|------|-------------|----------|-------|
| `id` | INT | Primary key - nationality ID | - | Join key |
| `nationality_name` | VARCHAR | Nationality name (English) | 国籍名 | Fallback for nationality field |

---

## Field Mappings & Transformations

### Individual vs Corporate Classification

**Primary Method**: Use `moving_agreement_type` from `movings` table
```sql
CASE 
    WHEN moving_agreement_type IN (2, 3, 4) THEN 'corporate'
    ELSE 'individual'
END
```

**Alternative**: `tenant_contract_type` (often NULL, not recommended)

### Gender Mapping

```sql
CASE 
    WHEN gender_type = 1 THEN 'Male'
    WHEN gender_type = 2 THEN 'Female'
    ELSE 'Other'
END
```

### String NULL Cleaning

Fields that may contain literal string `'NULL'`:
- `tenants.full_name`
- `tenants.personal_identity`
- `tenants.affiliation`

**Macro**: `{{ clean_string_null('column_name') }}`
```sql
CASE 
    WHEN column_name IN ('NULL', '--', 'null', '') THEN NULL
    ELSE column_name
END
```

### Moveout Date Integration

**Macro**: `{{ safe_moveout_date('table_alias') }}`
```sql
COALESCE(m.moveout_date_integrated, m.moveout_plans_date, m.moveout_date)
```

### Age Calculation

**Preferred**: Calculate from `birth_date`
```sql
COALESCE(t.age, TIMESTAMPDIFF(YEAR, t.birth_date, CURRENT_DATE))
```

---

## Data Quality Rules

### Required Validations

1. **Geocoding**: All analytics records must have valid `latitude` and `longitude`
2. **Date Ranges**: All dates should be >= `2018-01-01` (configurable via `min_valid_date`)
3. **Contract Validity**: Only include contracts where `cancel_flag = 0`
4. **Moveout Completion**: Only include moveouts where `is_moveout = 1`

### Known Issues

1. **String NULLs**: Several text fields contain literal `'NULL'` strings
2. **Stale Age**: `tenants.age` may be outdated; prefer calculation from `birth_date`
3. **NULL Contract Types**: `tenant_contract_type` is often NULL; use `moving_agreement_type` instead
4. **Applications Date**: `created_at` used for applications; may need validation with business users

---

## Code Mappings

### Contract Agreement Types (`moving_agreement_type`)
- Values: `1, 2, 3, 4, 9, ...` (varies)
- Corporate: `[2, 3, 4]` (configurable)
- Individual: All other values

### Gender Types (`gender_type`)
- `1` = Male
- `2` = Female
- Other = Other/Unknown

### Flags
- `0` = False/No/Active
- `1` = True/Yes/Completed

---

## Sample Data Statistics

From `gghouse_20260130.sql`:
- **Total Size**: 897MB
- **Tables**: 81
- **Key Tables**:
  - `movings`: 101 columns
  - `tenants`: 114 columns
  - `apartments`: 87 columns
  - `rooms`: 35 columns
  - `m_nationalities`: 11 columns

---

## References

- **Field Mapping**: See `docs/FIELD_MAPPING.md`
- **Schema Definitions**: `data/samples/schema_definitions.json`
- **Sample Data**: `data/samples/*_sample.csv`
