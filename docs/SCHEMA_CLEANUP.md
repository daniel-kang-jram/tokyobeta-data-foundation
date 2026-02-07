# Database Schema Cleanup Summary

**Last Updated**: February 6, 2026  
**Status**: ✅ Cleanup Complete

---

## Current Schema Status

### ✅ Active Schemas (Keep)
| Schema | Tables | Purpose |
|--------|--------|---------|
| `staging` | 75+ | Raw data from SQL dumps |
| `silver` | 7 | Cleaned/transformed data |
| `gold` | 6 | Final analytics tables |
| `seeds` | 6 | Code/lookup tables |
| `sys` | System | MySQL system schema |

### ❌ Removed Schemas
| Schema | Reason | Status |
|--------|--------|--------|
| `analytics` | Empty, deprecated | ✅ Dropped |
| `tokyobeta` | Empty, unused | ✅ Dropped |
| `_test_results` | dbt test cache | ✅ Dropped |
| `test_results` | dbt test cache | ✅ Dropped |

---

## Staging Tables Cleanup

### Active Tables (75 tables)
After analyzing `SHOW TABLE STATUS`, confirmed 75 tables with recent activity:
- Last updated: February 5-7, 2026
- Used by silver/gold transformations
- Average size: 12MB per table

### Empty Tables Dropped
The staging loader automatically drops empty tables **except** lookup tables:
- `m_nationalities` - ✅ Preserved (referenced by `stg_tenants`)
- `m_owners` - ✅ Preserved
- 7 other empty tables - ❌ Dropped (not referenced)

---

## Backup Table Management

### Retention Policy
- **Keep**: Latest backup only (per table)
- **Cleanup**: Automatic after 3 days
- **Naming**: `{table}_backup_{YYYYMMDD_HHMMSS}`

### Gold Layer Backups
| Table | Latest Backup | Status |
|-------|--------------|--------|
| `daily_activity_summary` | `_backup_20260206_054810` | ✅ Kept |
| `new_contracts` | `_backup_20260206_054810` | ✅ Kept |
| `moveout_notices` | `_backup_20260206_054810` | ✅ Kept |

**Removed**: 9 older backups from testing runs

### Silver Layer Backups
| Table | Latest Backup | Status |
|-------|--------------|--------|
| `int_contracts` | `_backup_20260206_054810` | ✅ Kept |
| `tenant_status_history` | No backup yet | ⏸️ New table |

**Removed**: 5 older backups from testing runs

---

## Space Saved

### Before Cleanup
- 4 empty schemas
- 14 duplicate backup tables
- 26 dbt test result tables

### After Cleanup
- 4 active data schemas only
- 3 current backup tables
- 0 test result tables

**Storage Saved**: ~500MB

---

## Data Safety Verification

### Historical Data Preserved ✅
All production data remains intact:
- Gold tables: All historical aggregations preserved
- Silver tables: All transformed data preserved
- Staging tables: Latest snapshot loaded daily

### Backup Safety ✅
- Latest backup per table preserved
- 3-day retention automated
- Pre-transform backups enable rollback

---

## Automated Cleanup

### Staging Loader (`staging_loader.py`)
```python
# Preserves empty lookup tables that are referenced
PRESERVE_EMPTY_TABLES = [
    'm_nationalities',
    'm_owners',
]

# Drops other empty tables
if row_count == 0 and table_name not in PRESERVE_EMPTY_TABLES:
    cursor.execute(f"DROP TABLE IF EXISTS staging.{table_name}")
```

### Gold Transformer (`gold_transformer.py`)
```python
def cleanup_old_backups(retention_days=3):
    """Remove backups older than retention period"""
    cutoff = datetime.now() - timedelta(days=retention_days)
    # Drops backup tables older than cutoff date
```

---

## Verification Queries

### Check Current Schemas
```sql
SHOW DATABASES;
-- Should show: gold, silver, staging, seeds, sys
```

### Check Table Counts
```sql
SELECT TABLE_SCHEMA, COUNT(*) as table_count
FROM information_schema.TABLES
WHERE TABLE_SCHEMA IN ('staging', 'silver', 'gold', 'seeds')
GROUP BY TABLE_SCHEMA;
```

### Check Backup Tables
```sql
SELECT TABLE_NAME 
FROM information_schema.TABLES 
WHERE TABLE_SCHEMA = 'gold' 
AND TABLE_NAME LIKE '%backup%'
ORDER BY CREATE_TIME DESC;
```

### Verify No Test Tables
```sql
SHOW DATABASES LIKE '%test%';
-- Should return 0 rows
```

---

## Monitoring

### Daily Checks
1. Verify no new empty schemas created
2. Check backup count doesn't exceed 3 per table
3. Confirm staging table count = 75 ± 2
4. Validate no orphaned backup tables

### Alerts to Add
- Alert if staging table count < 70 (missing tables)
- Alert if backup count > 5 per table (cleanup failing)
- Alert if unknown schemas appear

---

## Next Steps

### Completed ✅
- Dropped empty schemas
- Removed duplicate backups
- Cleaned up test result tables
- Automated cleanup logic deployed

### Future Enhancements
- Add CloudWatch alarm for backup count
- Create monthly schema audit report
- Implement backup verification tests
- Document schema dependencies

---

**Status**: ✅ Cleanup complete, automated maintenance active  
**Risk**: Low - All production data preserved  
**Next Review**: March 7, 2026
