# AWS Glue ETL Job - Successful Deployment

**Date**: 2026-01-31  
**Job ID**: `jr_60aa65b15230f4de472686d696e455d00e6cedc9b27056f5cf5b889b4ae68230`  
**Status**: ✅ **SUCCEEDED**  
**Execution Time**: 580 seconds (~9.7 minutes)

## Summary

The AWS Glue ETL job has been successfully deployed and executed end-to-end. The complete data pipeline is now operational:

1. **S3 Dump Download**: ✅ Downloaded `gghouse_20260131.sql` (897MB)
2. **Staging Load**: ✅ Loaded 80 tables, executed 821 SQL statements
3. **dbt Transformations**: ✅ All 4 analytics models created successfully
4. **Data Quality Tests**: ✅ 59/60 tests passed (1 known data quality issue in source)

## Analytics Tables Created

All 4 required tables are now available in the `analytics` database:

### 1. `daily_activity_summary`
- **Rows**: 2,965
- **Purpose**: Daily aggregation of applications, contracts, move-ins, move-outs by individual/corporate
- **Status**: ✅ Created

### 2. `new_contracts`
- **Rows**: 17,573
- **Purpose**: New contract records with demographics and geolocation
- **Columns**: AssetID, Room Number, Contract System, Channel, Dates, Rent, Demographics, Lat/Long
- **Status**: ✅ Created

### 3. `moveouts`
- **Rows**: 15,768
- **Purpose**: Moveout records with full contract history
- **Columns**: All new_contracts columns + Cancellation Notice Date, Moveout Date, Stay Duration
- **Status**: ✅ Created

### 4. `moveout_notices`
- **Rows**: 3,791
- **Purpose**: Rolling 24-month window of moveout notices
- **Type**: Incremental (only processes new/updated records)
- **Status**: ✅ Created

## Key Achievements

1. **Fixed Critical Issues**:
   - Resolved `room_number` vs `room_no` column name mismatch
   - Fixed dbt MySQL profiles configuration (removed conflicting `schema` parameter)
   - Corrected SQL dump loading logic (removed invalid schema prefixing)
   - Resolved dbt/protobuf compatibility by pinning `protobuf==4.25.3`
   - Fixed PATH issue for dbt executable in Glue environment

2. **Data Quality**:
   - 88 rows with future `created_at` dates detected (source data issue)
   - 629 geocoding records outside Tokyo bounds (to be addressed)
   - 614 contracts with $0 or negative rent (to be cleaned)

3. **Infrastructure**:
   - Glue job configured with 2 DPU, 0 retries
   - VPC connection to Aurora established
   - CloudWatch logging enabled
   - S3 integration for dbt files and SQL dumps working

## Known Issues & Next Steps

### Data Quality Issues (Non-Blocking)
1. **Future Dates**: 88 records in `daily_activity_summary` have `created_at` in the future
   - **Impact**: May skew recent activity metrics
   - **Recommendation**: Add filter in BI tool or fix upstream
   
2. **Invalid Geocoding**: 629 contracts outside Tokyo bounds
   - **Impact**: Map visualization may show incorrect locations
   - **Recommendation**: Re-geocode or exclude from map view
   
3. **Zero/Negative Rent**: 614 contracts with rent <= 0
   - **Impact**: Revenue calculations may be inaccurate
   - **Recommendation**: Exclude from financial reports or fix in source

### Next Steps for BI Dashboard
1. **QuickSight Setup** (ID: `enable-quicksight`)
   - Activate QuickSight Enterprise edition
   - Connect to Aurora MySQL cluster
   - Create 4 datasets (one per analytics table)

2. **Dashboard Creation**:
   - Executive Summary (daily metrics, trends)
   - New Contracts (demographics breakdown)
   - Moveout Analysis (reasons, tenure)
   - Tokyo Map (geospatial heatmap)

3. **User Access**:
   - Invite users from Warburg, JRAM, Tosei, GGhouse
   - Configure role-based access if needed

4. **Scheduling**:
   - EventBridge rule already configured for daily 7:00 AM JST
   - QuickSight SPICE refresh to be configured for 8:00 AM JST

## Testing & Validation

To validate the analytics tables manually:

```sql
-- Connect to Aurora
USE analytics;

-- Check row counts
SELECT 'daily_activity_summary' as table_name, COUNT(*) as row_count FROM daily_activity_summary
UNION ALL
SELECT 'new_contracts', COUNT(*) FROM new_contracts
UNION ALL
SELECT 'moveouts', COUNT(*) FROM moveouts
UNION ALL
SELECT 'moveout_notices', COUNT(*) FROM moveout_notices;

-- Sample new contracts
SELECT 
    asset_id_hj,
    room_number,
    contract_date,
    tenant_type,
    monthly_rent,
    age,
    nationality
FROM new_contracts
ORDER BY contract_date DESC
LIMIT 10;

-- Check geocoding
SELECT 
    COUNT(*) as total,
    COUNT(CASE WHEN latitude IS NOT NULL THEN 1 END) as with_geocoding,
    AVG(latitude) as avg_lat,
    AVG(longitude) as avg_long
FROM new_contracts;
```

## Architecture Diagram

```
S3 (jram-gghouse)
  └── dumps/gghouse_YYYYMMDD.sql
  └── dbt-project/
       ├── models/
       ├── macros/
       └── profiles.yml

           ↓ (Daily 7AM JST)

AWS Glue ETL Job
  ├── Download SQL dump
  ├── Load to staging (Aurora MySQL)
  └── Run dbt transformations

           ↓

Aurora MySQL
  ├── staging (80 tables, raw data)
  └── analytics (4 tables, BI-ready)

           ↓

Amazon QuickSight
  ├── Executive Dashboard
  ├── New Contracts View
  ├── Moveout Analysis
  └── Tokyo Map
```

## Lessons Learned

1. **Tool Caching**: The `read_file` and `search_replace` tools had caching issues. Always verify with terminal commands (`cat`, `awk`) when debugging file content issues.

2. **MySQL dbt Profile**: Don't use both `database` and `schema` parameters - MySQL treats them as the same, causing conflicts.

3. **Glue PATH**: User-installed Python packages (via `--user`) go to `/home/spark/.local/bin`, which must be added to PATH manually.

4. **Protobuf Compatibility**: `dbt 1.7.0` requires `protobuf<5`. Explicitly pin to avoid breaking changes.

5. **S3 Upload Verification**: Always verify S3 file content after upload, not just local files, as uploads can fail silently or use cached versions.

## References

- [Glue Job Definition](/terraform/modules/glue/main.tf)
- [dbt Models](/dbt/models/analytics/)
- [Data Validation Assessment](/docs/DATA_VALIDATION_ASSESSMENT.md)
- [Architecture Decision](/docs/ARCHITECTURE_DECISION.md)
- [DMS Vendor Requirements](/docs/DMS_VENDOR_REQUIREMENTS.md) (for future CDC implementation)

---

**Status**: ✅ ETL Pipeline Operational  
**Next Phase**: QuickSight Dashboard Creation  
**Owner**: Daniel Kang  
**Last Updated**: 2026-01-31
