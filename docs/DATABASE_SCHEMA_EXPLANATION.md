# Aurora Database Schema Explanation

## Overview
This document explains all databases/schemas in the Aurora MySQL cluster and identifies which ones are active vs. legacy artifacts.

## Active Databases (Currently Used)

### 1. **staging** (81 tables)
**Purpose**: Raw data loaded from daily SQL dumps  
**Created by**: Glue ETL script (`daily_etl.py`)  
**Data source**: S3 dumps from vendor (`s3://jram-gghouse/dumps/gghouse_YYYYMMDD.sql`)  
**Tables**: All source tables (apartments, tenants, movings, rooms, etc.)  
**Status**: ✅ ACTIVE - Primary landing zone for raw data

### 2. **silver** (2 tables currently, should have more)
**Purpose**: Cleaned, standardized data layer  
**Created by**: dbt models (`dbt/models/silver/*.sql`)  
**Data flow**: `staging` → `silver` (via dbt transformations)  
**Tables**: 
- `stg_apartments` - Cleaned apartment data
- `stg_rooms` - Cleaned room data
- (Should also have: `stg_tenants`, `stg_movings`, `stg_inquiries`, `int_contracts`)  
**Status**: ✅ ACTIVE - Medallion architecture silver layer

### 3. **gold** (0 tables currently - needs investigation)
**Purpose**: Business analytics layer with aggregated/denormalized data  
**Created by**: dbt models (`dbt/models/gold/*.sql`)  
**Data flow**: `silver` → `gold` (via dbt transformations)  
**Expected tables**: 
- `daily_activity_summary` - Daily metrics by individual/corporate
- `new_contracts` - New contract details with demographics
- `moveouts` - Completed moveout records
- `moveout_notices` - 24-month rolling moveout notices  
**Status**: ⚠️ SHOULD BE ACTIVE - Check why tables aren't created

### 4. **seeds** (0 tables - needs investigation)
**Purpose**: Reference data for code-to-semantic value mappings  
**Created by**: dbt seed command (`dbt seed`)  
**Data source**: CSV files in `dbt/seeds/*.csv`  
**Expected tables**: 
- `code_gender` - Gender code mappings
- `code_tenant_status` - Tenant status mappings
- `code_contract_type` - Contract type mappings
- `code_personal_identity` - Personal identity type mappings
- `code_affiliation_type` - Affiliation type mappings
- `code_moveout_reason` - Moveout reason mappings  
**Status**: ⚠️ SHOULD BE ACTIVE - Check why seeds aren't loaded

### 5. **tokyobeta** (0 tables)
**Purpose**: Default schema for dbt profile  
**Created by**: dbt initialization  
**Status**: ✅ ACTIVE - Used as default schema in dbt profile, but no tables expected here

## Legacy/Artifact Databases (Should be Cleaned Up)

### 6. **basis** (80 tables, all EMPTY)
**Purpose**: ❌ ARTIFACT - Vendor's original database name  
**Created by**: SQL dump file contains `CREATE DATABASE basis; USE basis;`  
**Problem**: 
- Dump file was generated from vendor's `basis` database
- Contains `CREATE DATABASE basis` statement
- Creates tables with names like `staging.apartments` (literal dot in name)
- All tables are EMPTY (data correctly loads into our `staging` schema instead)
- Takes up space but serves no purpose  

**Root cause**: 
```sql
-- In vendor's dump file:
CREATE DATABASE /*!32312 IF NOT EXISTS*/ `basis` /*!40100 DEFAULT CHARACTER SET utf8mb4 */;
USE `basis`;
CREATE TABLE `staging.apartments` ...  -- Note the literal "staging." prefix!
```

Our ETL script at `glue/scripts/daily_etl.py` line 52 tries to filter this out:
```python
if stmt.upper().startswith("CREATE DATABASE") or stmt.upper().startswith("USE "):
    return ""  # Skip these statements
```

But the database still gets created somehow (possibly in earlier runs).

**Recommendation**: DROP this database - it's completely redundant  
**Cleanup command**:
```sql
DROP DATABASE IF EXISTS basis;
```

### 7. **_analytics** (4 tables)
**Purpose**: ❌ LEGACY - Old analytics layer before schema naming fix  
**Created by**: dbt runs before `generate_schema_name.sql` macro was added  
**Problem**: dbt's default behavior adds project name prefix to custom schemas  
**Tables**: 
- `daily_activity_summary`
- `moveout_notices`
- `moveouts`
- `new_contracts`

**Root cause**: Before we created the `generate_schema_name` macro, dbt would create schemas like `{target_schema}_{custom_schema}` (e.g., `tokyobeta_analytics` → `_analytics`)  

**Recommendation**: DROP after verifying `gold` schema has correct tables  
**Cleanup command**:
```sql
DROP DATABASE IF EXISTS _analytics;
```

### 8. **_silver** (2 tables)
**Purpose**: ❌ LEGACY - Old silver layer before schema naming fix  
**Created by**: dbt runs before `generate_schema_name.sql` macro was added  
**Tables**: 
- `stg_apartments`
- `stg_rooms`

**Recommendation**: DROP after verifying `silver` schema has all required tables  
**Cleanup command**:
```sql
DROP DATABASE IF EXISTS _silver;
```

### 9. **_gold** (0 tables)
**Purpose**: ❌ LEGACY - Failed attempt to create gold layer  
**Created by**: dbt run with schema naming issue  
**Status**: Empty, can be dropped immediately  
**Cleanup command**:
```sql
DROP DATABASE IF EXISTS _gold;
```

### 10. **_test_results** (60 tables)
**Purpose**: ❌ UNKNOWN - Possibly test artifacts  
**Created by**: Unknown (needs investigation)  
**Status**: 60 tables - need to check if these are important  
**Recommendation**: Investigate contents before dropping

### 11. **analytics** (0 tables)
**Purpose**: ❌ REDUNDANT - Superseded by `gold` schema  
**Created by**: Old ETL script (`daily_etl.py` line 162: `CREATE SCHEMA IF NOT EXISTS analytics`)  
**Problem**: We switched from `analytics` → `gold` naming but script still creates it  
**Status**: Empty, can be dropped  
**Cleanup command**:
```sql
DROP DATABASE IF EXISTS analytics;
```

## Why Both `staging` and `basis`?

**Short answer**: It's NOT intentional - `basis` is a useless artifact.

**Long answer**:
1. Vendor dumps their production database called `basis`
2. Dump file includes `CREATE DATABASE basis;` statement
3. Our ETL tries to filter this out but the database gets created anyway
4. Tables in `basis` have malformed names like `staging.apartments` (literal dot)
5. Our ETL correctly loads data into the `staging` schema (not `basis`)
6. Result: `basis` exists but is completely empty and unused

**Action**: Drop `basis` database - it serves no purpose.

## Recommended Cleanup Actions

### Immediate Cleanup (Safe)
```sql
-- Drop empty/legacy databases
DROP DATABASE IF EXISTS basis;
DROP DATABASE IF EXISTS _gold;
DROP DATABASE IF EXISTS analytics;
```

### After Verification (Check tables first)
```sql
-- Verify silver schema has all required tables first
SHOW TABLES IN silver;  
-- Should have: stg_apartments, stg_rooms, stg_tenants, stg_movings, stg_inquiries, int_contracts

-- Then drop legacy _silver
DROP DATABASE IF EXISTS _silver;

-- Verify gold schema has all required tables first
SHOW TABLES IN gold;
-- Should have: daily_activity_summary, new_contracts, moveouts, moveout_notices

-- Then drop legacy _analytics
DROP DATABASE IF EXISTS _analytics;
```

### Investigate Before Action
```sql
-- Check what's in _test_results
SELECT TABLE_NAME FROM information_schema.TABLES 
WHERE TABLE_SCHEMA = '_test_results' 
LIMIT 10;

-- Decide whether to keep or drop
```

## Root Cause Fixes

### 1. Fix `basis` database creation
**File**: `glue/scripts/daily_etl.py`  
**Current code** (line 52):
```python
if stmt.upper().startswith("CREATE DATABASE") or stmt.upper().startswith("USE "):
    return ""
```

**Issue**: This filters statements during parsing, but doesn't prevent the database from being created if the dump is executed directly.

**Solution**: Add explicit DROP statement before loading:
```python
cursor.execute("DROP DATABASE IF EXISTS basis")
```

### 2. Remove old `analytics` schema creation
**File**: `glue/scripts/daily_etl.py`  
**Line 162**: Remove this line (we use `gold` now, not `analytics`)
```python
# cursor.execute("CREATE SCHEMA IF NOT EXISTS analytics")  # REMOVE THIS
```

### 3. Ensure dbt creates correct schemas
**File**: `dbt/macros/generate_schema_name.sql` ✅ Already fixed
- Prevents `_analytics`, `_silver`, `_gold` from being created
- Ensures clean schema names: `silver`, `gold`, `seeds`

## Database Size & Cost Impact

Current disk usage by schema:
```sql
SELECT 
    table_schema,
    COUNT(*) as table_count,
    ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS size_mb
FROM information_schema.TABLES
WHERE table_schema NOT IN ('mysql', 'information_schema', 'performance_schema', 'sys')
GROUP BY table_schema
ORDER BY size_mb DESC;
```

**Recommendation**: Run this query to quantify wasted space in legacy schemas.

## Summary

| Database | Status | Action | Priority |
|----------|--------|--------|----------|
| `staging` | ✅ Active | Keep | - |
| `silver` | ✅ Active | Keep | - |
| `gold` | ⚠️ Empty | Investigate | HIGH |
| `seeds` | ⚠️ Empty | Investigate | HIGH |
| `tokyobeta` | ✅ Active | Keep | - |
| `basis` | ❌ Artifact | DROP | HIGH |
| `_analytics` | ❌ Legacy | DROP after verification | MEDIUM |
| `_silver` | ❌ Legacy | DROP after verification | MEDIUM |
| `_gold` | ❌ Empty | DROP immediately | LOW |
| `analytics` | ❌ Empty | DROP immediately | LOW |
| `_test_results` | ❓ Unknown | Investigate | MEDIUM |

## Next Steps

1. ✅ Understand database structure (this document)
2. ⚠️ Investigate why `gold` and `seeds` schemas are empty
3. ⚠️ Fix Glue ETL to prevent `basis` creation
4. ⚠️ Run database cleanup after verification
5. ⚠️ Test full ETL pipeline to ensure all schemas populate correctly
