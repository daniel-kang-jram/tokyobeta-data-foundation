# Aurora Backup & Recovery Strategy

## Overview

Cost-effective, robust backup strategy using Aurora's built-in automated backups instead of expensive manual snapshots.

## Backup Configuration (Terraform)

```hcl
# terraform/modules/aurora/main.tf
resource "aws_rds_cluster" "aurora" {
  backup_retention_period      = 7
  preferred_backup_window      = "03:00-04:00"  # Before ETL run at 07:00 JST
}
```

### Features Enabled:
- ✅ **Automated daily backups** (included in RDS pricing)
- ✅ **7-day retention period**
- ✅ **Point-in-Time Recovery (PITR)** to any second in the last 7 days
- ✅ **No extra cost** beyond standard RDS storage

## Cost Comparison

| Strategy | Monthly Cost | Pros | Cons |
|----------|--------------|------|------|
| **Manual snapshots before each ETL** | ~$57/month | Explicit pre-ETL state | Expensive, clutters console |
| **Automated backups + PITR** ✅ | $0 extra | Free, automatic, flexible | Requires knowing restore time |

**Savings: ~$57/month by using PITR**

## Recovery Scenarios

### Scenario 1: ETL Failed, Need to Rollback

**Problem**: Glue job failed during dbt transformations, data corrupted

**Solution**: Use Point-in-Time Recovery (PITR)

```bash
# Restore to 1 hour ago (before ETL started)
./scripts/rollback_etl.sh "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)"

# Or restore to specific time
./scripts/rollback_etl.sh "2026-02-04T10:00:00Z"
```

**Steps**:
1. Run rollback script with target timestamp
2. Wait 5-10 minutes for cluster creation
3. Create new instance on restored cluster
4. Update Glue/Terraform with new endpoint
5. Test data integrity
6. Delete old broken cluster

### Scenario 2: Need to Check What Data Looked Like Yesterday

**Problem**: Need to investigate data state from previous day

**Solution**: Create read-only clone from automated backup

```bash
aws rds restore-db-cluster-to-point-in-time \
    --db-cluster-identifier tokyobeta-prod-aurora-cluster-public-investigation \
    --source-db-cluster-identifier tokyobeta-prod-aurora-cluster-public \
    --restore-to-time "2026-02-04T00:00:00Z" \
    --profile gghouse
```

### Scenario 3: Need Pre-ETL Snapshot for Critical Production Run

**Problem**: About to run major schema migration, want explicit snapshot

**Solution**: Create manual snapshot (rare case)

```bash
aws rds create-db-cluster-snapshot \
    --db-cluster-snapshot-identifier tokyobeta-prod-pre-migration-2026-02-04 \
    --db-cluster-identifier tokyobeta-prod-aurora-cluster-public \
    --profile gghouse

# Cost: ~$0.095/GB-month
```

## ETL Safety Improvements

### Before (Vulnerable):
```python
# Drop all staging tables before load
for table in existing_tables:
    cursor.execute(f"DROP TABLE IF EXISTS staging.{table}")
# If dbt fails → ALL DATA LOST
```

### After (Robust):
```python
# Don't drop tables - SQL dump has DROP TABLE IF EXISTS
# If dbt fails → staging data preserved
# Can re-run dbt without full reload
```

### Additional Protections:

1. **Transaction-based loading**:
   - Staging load commits every 100 statements
   - Partial progress saved even if job crashes

2. **SQL dump includes schema**:
   - Each dump has `DROP TABLE IF EXISTS` + `CREATE TABLE`
   - Safe to re-run multiple times

3. **dbt runs after staging**:
   - If dbt fails, staging data intact
   - Can debug and re-run dbt separately

## Recovery Commands Quick Reference

```bash
# List available restore windows
aws rds describe-db-clusters \
    --db-cluster-identifier tokyobeta-prod-aurora-cluster-public \
    --profile gghouse \
    --query 'DBClusters[0].{Earliest:EarliestRestorableTime,Latest:LatestRestorableTime}'

# Restore to specific time (creates new cluster)
./scripts/rollback_etl.sh "2026-02-04T06:00:00Z"

# Create manual snapshot (if critical operation)
aws rds create-db-cluster-snapshot \
    --db-cluster-snapshot-identifier tokyobeta-prod-manual-backup-$(date +%Y%m%d) \
    --db-cluster-identifier tokyobeta-prod-aurora-cluster-public \
    --profile gghouse

# List all snapshots
aws rds describe-db-cluster-snapshots \
    --db-cluster-identifier tokyobeta-prod-aurora-cluster-public \
    --profile gghouse \
    --query 'DBClusterSnapshots[*].{ID:DBClusterSnapshotIdentifier,Type:SnapshotType,Created:SnapshotCreateTime}' \
    --output table
```

## Monitoring & Alerts

**CloudWatch Alarms** (recommended):
- ETL job failures → SNS notification
- Aurora CPU > 80% during ETL
- Aurora free storage < 10GB

**Backup Monitoring**:
```bash
# Verify automated backups are working
aws rds describe-db-clusters \
    --db-cluster-identifier tokyobeta-prod-aurora-cluster-public \
    --profile gghouse \
    --query 'DBClusters[0].{BackupRetention:BackupRetentionPeriod,LatestBackup:LatestRestorableTime}'
```

## Best Practices

1. **Test restores quarterly** - Verify PITR works as expected
2. **Document ETL start times** - Know when to restore to (e.g., 06:30 JST daily)
3. **Monitor backup retention** - Ensure it stays at 7 days
4. **Before major changes** - Create manual snapshot if changing schema significantly
5. **Separate staging from gold** - Gold layer failures don't affect staging

## Cost Optimization Summary

**What We're Doing**:
- ✅ Using automated backups (included)
- ✅ 7-day PITR window (included)
- ✅ Non-destructive ETL (preserves staging)
- ✅ No manual snapshots for routine ETL

**What We're NOT Doing** (cost savings):
- ❌ Manual snapshots before each ETL (~$57/month saved)
- ❌ Dropping staging tables preemptively (safer)
- ❌ Storing duplicate data

**Result**: Robust, enterprise-grade backup with $0 additional cost
