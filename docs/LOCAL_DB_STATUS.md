# Local Database Status

**Date**: 2026-01-30  
**Status**: ✅ **RUNNING**

## Container Information

- **Container Name**: `tokyobeta-mysql`
- **Image**: `mysql:8.0`
- **Port**: `3307` (host) → `3306` (container)
- **Database**: `tokyobeta`
- **Root Password**: `localdev`

## Connection Details

```bash
Host: 127.0.0.1
Port: 3307
User: root
Password: localdev
Database: tokyobeta
```

## Database Structure

### Schemas Created
- ✅ `staging` - Source data tables
- ✅ `analytics` - Output tables (for dbt models)
- ✅ `seeds` - Seed data (if needed)

### Tables in `staging` Schema
- ✅ `movings` - 5 test rows
- ✅ `tenants` - 5 test rows
- ✅ `apartments` - 2 test rows
- ✅ `rooms` - 5 test rows
- ✅ `m_nationalities` - 3 test rows

## Test Results

### SQL Query Tests
All dbt model logic tested successfully with direct SQL:

1. ✅ **Daily Activity Summary - Applications**: Working
   - Groups by date and tenant type (individual/corporate)
   - Counts applications correctly

2. ✅ **Daily Activity Summary - Contracts Signed**: Working
   - Filters valid contracts (cancel_flag = 0)
   - Groups by date and tenant type

3. ✅ **New Contracts**: Working
   - Joins all required tables correctly
   - Includes all expected fields
   - Handles NULL values properly
   - Filters for valid geocoding

4. ✅ **Moveouts**: Working
   - Uses safe_moveout_date logic correctly
   - Filters completed moveouts (is_moveout = 1)
   - Includes all required fields

## Sample Output

### New Contracts Sample
```
contract_id | asset_id_hj | room_number | tenant_type | gender | age | nationality
------------|-------------|------------|-------------|--------|-----|------------
3           | APT002      | 101        | individual  | Female | 25  | Japanese
2           | APT001      | 102        | corporate   | Male   | 28  | American
1           | APT001      | 101        | individual  | Male   | 30  | Japanese
```

### Moveouts Sample
```
contract_id | asset_id_hj | moveout_date | tenant_type | monthly_rent
------------|-------------|--------------|-------------|-------------
4           | APT002      | 2024-01-31   | individual  | 52000.00
5           | APT001      | 2024-01-15   | corporate   | 58000.00
```

## Next Steps

### To Run Full dbt Models

1. **Install dbt**:
   ```bash
   pip install dbt-mysql
   ```

2. **Run dbt**:
   ```bash
   cd dbt
   export DBT_TARGET=local
   dbt run --target local
   dbt test --target local
   ```

### To Stop Container

```bash
docker stop tokyobeta-mysql
```

### To Remove Container

```bash
docker stop tokyobeta-mysql
docker rm tokyobeta-mysql
```

### To Restart Container

```bash
docker start tokyobeta-mysql
```

## Validation Summary

✅ **Database**: Running and accessible  
✅ **Schemas**: Created successfully  
✅ **Tables**: Created with test data  
✅ **SQL Logic**: All dbt model queries working correctly  
✅ **Field Mappings**: All fields accessible and correct  
✅ **Data Quality**: Test data validates transformations  

**Conclusion**: The local database setup is complete and all dbt model logic has been validated with direct SQL queries. The models are ready for full dbt execution once dbt-mysql is installed.
