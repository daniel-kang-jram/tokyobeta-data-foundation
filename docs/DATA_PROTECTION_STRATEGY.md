# Data Protection Strategy for ETL Failures

## Current Risk Analysis

### High-Risk Scenarios

#### 1. **Incremental Model Failures** (HIGHEST RISK)
Models like `tenant_status_history` that use `materialized='incremental'`:
- **Risk**: Partial updates if SQL succeeds but post-hooks fail
- **Impact**: Data inconsistency, lost historical records
- **Example**: New records inserted, but `valid_to` dates not updated on previous records

#### 2. **Table Model Failures** (MEDIUM RISK)
Models like `daily_activity_summary` that use `materialized='table'`:
- **Risk**: If dbt successfully creates temp table but fails during swap
- **Impact**: Table could be temporarily unavailable or in inconsistent state
- **Protection**: dbt's atomic table swap (create temp → drop old → rename temp)

#### 3. **Post-Hook Failures** (MEDIUM RISK)
Models with complex post-hooks (UPDATE/DELETE statements):
- **Risk**: Main query succeeds, post-hook fails
- **Impact**: Data in inconsistent state
- **Current Example**: `tenant_status_history` post-hook updates `valid_to` dates

### Current Protections (Insufficient)

✅ **Aurora Automated Backups**:
- 7-day retention period
- Daily backups (03:00-04:00 JST)
- Point-in-Time Recovery (PITR)

❌ **Limitations**:
- Cluster-wide recovery only (can't restore individual tables)
- Recovery requires creating a new cluster (30+ minutes)
- No pre-ETL snapshot protection
- Not suitable for quick rollback of a single table

---

## Recommended Protection Strategy

### Layer 1: Pre-ETL Table Backups (IMMEDIATE FIX)

Create backup copies of critical tables before each ETL run.

**Implementation**:

```python
# Add to daily_etl.py before dbt transformations

CRITICAL_TABLES = [
    'silver.tenant_status_history',
    'silver.int_contracts',
    'gold.daily_activity_summary',
    'gold.new_contracts',
    'gold.moveouts',
    'gold.moveout_notices'
]

def create_pre_etl_backups(cursor, tables):
    """Create backup copies of critical tables before ETL"""
    backup_suffix = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    for table in tables:
        schema, table_name = table.split('.')
        backup_name = f"{table_name}_backup_{backup_suffix}"
        
        try:
            # Check if table exists
            cursor.execute(f"SHOW TABLES FROM {schema} LIKE '{table_name}'")
            if cursor.fetchone():
                logger.info(f"Creating backup: {schema}.{backup_name}")
                cursor.execute(f"""
                    CREATE TABLE {schema}.{backup_name} 
                    AS SELECT * FROM {schema}.{table_name}
                """)
                
                # Add metadata
                cursor.execute(f"""
                    ALTER TABLE {schema}.{backup_name} 
                    ADD COLUMN backup_created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                """)
                
                logger.info(f"✓ Backed up {table} → {schema}.{backup_name}")
        except Exception as e:
            logger.warning(f"Failed to backup {table}: {e}")
            
def cleanup_old_backups(cursor, days_to_keep=3):
    """Remove backups older than N days"""
    cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).strftime('%Y%m%d')
    
    for schema in ['silver', 'gold']:
        cursor.execute(f"""
            SELECT TABLE_NAME 
            FROM information_schema.TABLES 
            WHERE TABLE_SCHEMA = '{schema}' 
            AND TABLE_NAME LIKE '%_backup_%'
        """)
        
        for (table_name,) in cursor.fetchall():
            # Extract date from backup name (format: tablename_backup_YYYYMMDD_HHMMSS)
            if '_backup_' in table_name:
                date_part = table_name.split('_backup_')[1][:8]
                if date_part < cutoff_date:
                    logger.info(f"Removing old backup: {schema}.{table_name}")
                    cursor.execute(f"DROP TABLE IF EXISTS {schema}.{table_name}")
```

**Pros**:
- ✅ Fast recovery (just rename tables)
- ✅ Table-specific restoration
- ✅ No cluster downtime
- ✅ Automated cleanup

**Cons**:
- ❌ Additional storage cost (minimal for 3-day retention)
- ❌ Slightly longer ETL time (~5-10 seconds)

---

### Layer 2: dbt Safety Features (CONFIGURE)

Configure dbt to fail fast and provide better error handling.

**A. Use `--fail-fast` Flag**

```python
# In daily_etl.py, modify dbt run command
result = subprocess.run([
    'dbt', 'run',
    '--profiles-dir', dbt_profiles_dir,
    '--project-dir', dbt_project_dir,
    '--target', 'prod',
    '--fail-fast',  # Stop immediately on first error
], ...)
```

**B. Configure Incremental Models with Safety**

```sql
-- In tenant_status_history.sql
{{
    config(
        materialized='incremental',
        unique_key=['tenant_id', 'valid_from'],
        on_schema_change='fail',  -- Changed from 'append_new_columns'
        transient=false,
        incremental_strategy='merge',  -- Use MERGE for atomicity
        post_hook=[
            -- Use transaction-safe UPDATE
            """
            {% if is_incremental() %}
                START TRANSACTION;
                UPDATE {{ this }} 
                SET valid_to = DATE_SUB(CURDATE(), INTERVAL 1 DAY), 
                    is_current = FALSE 
                WHERE tenant_id IN (
                    SELECT DISTINCT tenant_id 
                    FROM {{ this }} 
                    WHERE valid_from = CURDATE()
                ) 
                AND valid_from < CURDATE() 
                AND is_current = TRUE;
                COMMIT;
            {% endif %}
            """
        ]
    )
}}
```

**C. Add Pre/Post-Hook Validation**

```sql
-- Add to dbt_project.yml
on-run-start:
  - "{{ log('Starting ETL run at ' ~ run_started_at.strftime('%Y-%m-%d %H:%M:%S'), info=True) }}"
  - "CALL backup_critical_tables()"  -- Custom stored procedure

on-run-end:
  - "{{ log('Completed ETL run with ' ~ results|length ~ ' models', info=True) }}"
  - "{% if results|selectattr('status', 'eq', 'error')|list|length > 0 %}
       {{ exceptions.raise_compiler_error('ETL failed - review backups for recovery') }}
     {% endif %}"
```

---

### Layer 3: Transaction-Based Recovery (ADVANCED)

Use MySQL transactions to wrap risky operations.

**Stored Procedure for Transactional ETL**:

```sql
DELIMITER $$

CREATE PROCEDURE run_safe_incremental_update(
    IN target_table VARCHAR(255),
    IN update_query TEXT,
    IN validation_query TEXT
)
BEGIN
    DECLARE exit handler for sqlexception
    BEGIN
        -- Rollback on error
        ROLLBACK;
        SIGNAL SQLSTATE '45000' 
        SET MESSAGE_TEXT = 'Incremental update failed, rolled back';
    END;
    
    START TRANSACTION;
    
    -- Execute the update
    SET @sql = update_query;
    PREPARE stmt FROM @sql;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;
    
    -- Validate result
    SET @validation_sql = validation_query;
    PREPARE val_stmt FROM @validation_sql;
    EXECUTE val_stmt INTO @validation_result;
    DEALLOCATE PREPARE val_stmt;
    
    IF @validation_result = 0 THEN
        -- Validation failed
        ROLLBACK;
        SIGNAL SQLSTATE '45000' 
        SET MESSAGE_TEXT = 'Validation failed, rolled back';
    ELSE
        -- Commit if validation passes
        COMMIT;
    END IF;
END$$

DELIMITER ;
```

---

### Layer 4: Monitoring and Alerting

**CloudWatch Alarms** (add to Terraform):

```hcl
resource "aws_cloudwatch_metric_alarm" "glue_job_failure" {
  alarm_name          = "tokyobeta-prod-glue-etl-failure"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "glue.driver.aggregate.numFailedTasks"
  namespace           = "Glue"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Alert when Glue ETL job fails"
  alarm_actions       = [aws_sns_topic.etl_alerts.arn]
  
  dimensions = {
    JobName = "tokyobeta-prod-daily-etl"
  }
}

resource "aws_sns_topic" "etl_alerts" {
  name = "tokyobeta-prod-etl-alerts"
}

resource "aws_sns_topic_subscription" "etl_email_alert" {
  topic_arn = aws_sns_topic.etl_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email  # Add to variables
}
```

---

## Recovery Procedures

### Scenario 1: Incremental Model Failed Partially

```bash
# 1. Check latest backup
mysql> SHOW TABLES FROM silver LIKE 'tenant_status_history_backup_%';

# 2. Compare row counts
mysql> SELECT COUNT(*) FROM silver.tenant_status_history;
mysql> SELECT COUNT(*) FROM silver.tenant_status_history_backup_20260206_070000;

# 3. Restore from backup
mysql> DROP TABLE silver.tenant_status_history;
mysql> RENAME TABLE 
    silver.tenant_status_history_backup_20260206_070000 
    TO silver.tenant_status_history;

# 4. Remove backup column
mysql> ALTER TABLE silver.tenant_status_history 
    DROP COLUMN backup_created_at;
```

### Scenario 2: Multiple Tables Corrupted

```bash
# Use PITR to restore entire cluster
aws rds restore-db-cluster-to-point-in-time \
  --source-db-cluster-identifier tokyobeta-prod-aurora-cluster \
  --db-cluster-identifier tokyobeta-prod-aurora-recovery \
  --restore-to-time "2026-02-06T06:55:00Z" \
  --profile gghouse \
  --region ap-northeast-1

# Then manually copy data from recovery cluster to prod
```

---

## Implementation Priority

### ✅ IMMEDIATE (Today)
1. Add pre-ETL backup function to `daily_etl.py`
2. Add `--fail-fast` to dbt run command
3. Fix `tenant_status_history.sql` syntax (DONE)
4. Upload changes to S3

### 🟡 THIS WEEK
1. Add CloudWatch alarms for Glue failures
2. Configure SNS email alerts
3. Add backup cleanup cron job
4. Document recovery procedures

### 🔵 NEXT SPRINT
1. Implement transaction-based stored procedures
2. Add dbt pre/post-hook validations
3. Set up staging environment for testing dbt models
4. Implement automated rollback on validation failure

---

## Cost Impact

**Storage for 3-day backup retention**:
- Estimated size per backup: ~500 MB (6 tables × ~80 MB avg)
- Daily backups: 500 MB/day
- 3-day retention: 1.5 GB total
- **Cost**: ~$0.15/month (Aurora storage @ $0.10/GB/month)

**Conclusion**: Negligible cost for critical data protection.

---

## Testing Plan

### Test 1: Intentional Syntax Error
```bash
# Introduce error in dbt model
# Run ETL
# Verify table remains unchanged
# Verify backup exists
```

### Test 2: Post-Hook Failure
```bash
# Create invalid post-hook
# Run ETL
# Verify partial rollback
# Restore from backup
```

### Test 3: Recovery from Backup
```bash
# Create backup
# Corrupt table data
# Execute recovery procedure
# Validate data integrity
```

---

## Questions to Consider

1. **Should we implement ALL layers or start with Layer 1?**
   - **Recommendation**: Start with Layer 1 (pre-ETL backups) immediately
   
2. **How many days of backup retention?**
   - **Recommendation**: 3 days (balance between safety and cost)
   
3. **Which tables are "critical" and need backup?**
   - **Recommendation**: All incremental models + gold layer tables
   
4. **Should we test in staging first?**
   - **Recommendation**: Yes, add dev environment dbt testing in CI/CD
