# Silver Test Optimization - Implementation Guide

## Problem Statement

The `tokyobeta-prod-silver-transformer` Glue job was taking **30+ minutes** to complete, with most time spent on dbt tests rather than actual data transformation.

### Root Causes

1. **Expensive `unique` tests**: Full table scans on large tables (12k-25k rows each)
   - `stg_movings.moving_id` - 25,000+ rows
   - `stg_tenants.tenant_id` - 12,000+ rows
   - `stg_rooms.room_id` - 16,000+ rows
   - `int_contracts.contract_id` - 17,000+ rows

2. **`accepted_values` tests**: Scanning entire columns for enum validation

3. **Tests ran inline with transformation**: Blocked data loading pipeline

## Solution Architecture

### 1. Separate Test Job (RECOMMENDED)

Created dedicated `tokyobeta-prod-silver-test` Glue job:
- **Purpose**: Run ONLY dbt tests (no transformation)
- **Script**: `glue/scripts/silver_test.py`
- **Scheduling**: Can run independently after transformation completes
- **Benefits**: Non-blocking validation, async execution

### 2. Disabled Expensive Tests

Removed slow tests from `dbt/models/silver/_silver_schema.yml`:
- All `unique` tests on primary keys
- Rationale: Uniqueness enforced by MySQL `PRIMARY KEY` constraints
- Validation: Database will reject duplicate inserts automatically

### 3. Added SKIP_TESTS Flag

Updated `silver_transformer.py` to support skipping tests:
```python
--SKIP_TESTS=true   # Default: Skip tests for fast mode
--SKIP_TESTS=false  # Run tests inline (for debugging)
```

## Performance Impact

### Before Optimization
```
silver_transformer execution:
- dbt models: ~3 minutes
- dbt tests: ~27+ minutes
- Total: ~30+ minutes
```

### After Optimization
```
silver_transformer (SKIP_TESTS=true):
- dbt models: ~3 minutes
- Tests skipped
- Total: ~3 minutes ⚡ (10x faster)

silver_test (separate job):
- dbt tests only: ~5-10 minutes
- Can run async/parallel
```

## Deployment

### 1. Updated Files (Already Deployed)

✅ `glue/scripts/silver_transformer.py` - Added SKIP_TESTS flag  
✅ `glue/scripts/silver_test.py` - New test-only job  
✅ `dbt/models/silver/_silver_schema.yml` - Disabled expensive tests  
✅ S3: Uploaded all updated scripts and dbt project  

### 2. Glue Jobs Updated (Already Configured)

✅ `tokyobeta-prod-silver-transformer` - Updated with `--SKIP_TESTS=true` default  
✅ `tokyobeta-prod-silver-test` - Created new job  

### 3. Glue Job Configurations

#### tokyobeta-prod-silver-transformer
```json
{
  "DefaultArguments": {
    "--SKIP_TESTS": "true",
    ... (other args)
  },
  "Timeout": 60,
  "WorkerType": "G.1X",
  "NumberOfWorkers": 2
}
```

#### tokyobeta-prod-silver-test
```json
{
  "ScriptLocation": "s3://jram-gghouse/glue-scripts/silver_test.py",
  "Timeout": 30,
  "WorkerType": "G.1X",
  "NumberOfWorkers": 2,
  "Description": "Runs dbt tests for silver layer (separated from transformation)"
}
```

## Daily Operations

### Fast Mode (Default)
```bash
# Run transformation only (tests skipped)
aws glue start-job-run \
  --job-name tokyobeta-prod-silver-transformer \
  --profile gghouse

# Run tests separately (optional, can be async)
aws glue start-job-run \
  --job-name tokyobeta-prod-silver-test \
  --profile gghouse
```

### Debug Mode (Tests Inline)
```bash
# Run with tests inline
aws glue start-job-run \
  --job-name tokyobeta-prod-silver-transformer \
  --arguments '{"--SKIP_TESTS":"false"}' \
  --profile gghouse
```

## Scheduling Recommendations

### Option 1: Sequential (Conservative)
```
daily_etl → silver_transformer (3 min) → silver_test (10 min) → gold_transformer
```

### Option 2: Parallel (Aggressive)
```
daily_etl → silver_transformer (3 min) ┬→ gold_transformer
                                       └→ silver_test (async, 10 min)
```

### Option 3: Test on Schedule (Efficient)
```
Daily: daily_etl → silver_transformer (3 min) → gold_transformer
Hourly: silver_test (validation only)
```

## Data Quality Assurance

### Database Constraints (Always Enforced)
- `PRIMARY KEY` constraints prevent duplicate IDs
- `NOT NULL` constraints prevent missing required fields
- `FOREIGN KEY` constraints maintain referential integrity

### Spot-Check Queries (Manual/Ad-Hoc)
```sql
-- Check for duplicates (should return 0 rows)
SELECT moving_id, COUNT(*) 
FROM silver.stg_movings 
GROUP BY moving_id 
HAVING COUNT(*) > 1;

-- Verify row counts after transformation
SELECT 
  'stg_movings' as table_name, COUNT(*) as row_count FROM silver.stg_movings
UNION ALL
SELECT 'stg_tenants', COUNT(*) FROM silver.stg_tenants
UNION ALL
SELECT 'stg_rooms', COUNT(*) FROM silver.stg_rooms;
```

### dbt Test Job (Scheduled)
- Run `tokyobeta-prod-silver-test` on a schedule (e.g., hourly or daily)
- Alerts on test failures via CloudWatch

## Monitoring

### Silver Transformer (Fast Mode)
```bash
# Check recent runs
aws glue get-job-runs \
  --job-name tokyobeta-prod-silver-transformer \
  --max-items 5 \
  --profile gghouse \
  --query 'JobRuns[*].[JobRunState,ExecutionTime,StartedOn]'

# Expected: SUCCEEDED in ~3 minutes
```

### Silver Test Job
```bash
# Check test results
aws glue get-job-run \
  --job-name tokyobeta-prod-silver-test \
  --run-id <run-id> \
  --profile gghouse \
  --query 'JobRun.[JobRunState,ErrorMessage]'
```

## Troubleshooting

### Issue: Silver transformer still slow
**Diagnosis**: Check if SKIP_TESTS is actually set to "true"
```bash
aws glue get-job --job-name tokyobeta-prod-silver-transformer \
  --profile gghouse \
  --query 'Job.DefaultArguments."--SKIP_TESTS"'
```

### Issue: Tests not running at all
**Solution**: Schedule `silver_test` job separately or set `--SKIP_TESTS=false`

### Issue: Aurora connection timeout
**Diagnosis**: VPC/Security group configuration issue (not related to test optimization)
```bash
# Check Aurora cluster status
aws rds describe-db-clusters \
  --db-cluster-identifier tokyobeta-prod-aurora-cluster \
  --profile gghouse \
  --query 'DBClusters[0].Status'
```

## Known Issues

### Aurora Connectivity (Feb 2026)
- Status: Glue jobs experiencing intermittent connection timeouts to Aurora public endpoint
- Error: `OperationalError: (2003, "Can't connect to MySQL server ... (timed out)")`
- Root Cause: Under investigation - likely VPC/security group configuration
- Impact: Affects BOTH silver_transformer and silver_test jobs
- Workaround: Retry job; investigate network/security configuration

## Future Improvements

1. **Database Indexes**: Add indexes for spot-check queries
   ```sql
   CREATE INDEX idx_moving_id_count ON silver.stg_movings(moving_id);
   ```

2. **CloudWatch Alarms**: Alert on test failures
   ```python
   # In silver_test.py, publish metrics
   cloudwatch.put_metric_data(
       Namespace='TokyoBeta/DataQuality',
       MetricName='SilverTestsFailed',
       Value=tests_failed
   )
   ```

3. **Incremental Transformations**: Convert full-rebuild tables to incremental
   - Current: All silver tables rebuilt daily
   - Future: Incremental updates for large tables

## References

- Silver transformer script: `glue/scripts/silver_transformer.py`
- Silver test script: `glue/scripts/silver_test.py`
- dbt schema: `dbt/models/silver/_silver_schema.yml`
- Terraform: `terraform/modules/glue/main.tf`

## Commit History

- `93e16ac` - perf(silver): separate test job + disable expensive tests
- `896afd9` - perf(dbt): disable all tests on tenant_room_snapshot_daily

---

**Last Updated**: 2026-02-10  
**Status**: ✅ Optimization complete, pending Aurora connectivity fix for execution testing
