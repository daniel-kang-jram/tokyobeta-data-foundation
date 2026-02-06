# Tenant Status History - Implementation Guide

**Date:** 2026-02-05  
**Status:** ✅ Ready to Deploy  
**Type:** New Feature - Historical Status Tracking

## Overview

Added **tenant status history tracking** to enable time-series analysis of tenant status changes. Implements Slowly Changing Dimension (SCD) Type 2 pattern to capture when tenants transition between statuses.

## Business Problem Solved

### Before
- ❌ Only current tenant status available
- ❌ No way to know when status changed
- ❌ Cannot analyze status transition patterns
- ❌ Missing audit trail of tenant lifecycle
- ❌ Cannot calculate time spent in each status

### After
- ✅ Complete history of status changes
- ✅ Know exactly when each transition occurred
- ✅ Analyze status flow patterns (Inquiry → Contract → Active)
- ✅ Full audit trail for compliance
- ✅ Calculate days in each status for KPIs

## Architecture

### New Tables Added

#### 1. Silver Layer: `tenant_status_history`

**Purpose:** Raw historical tracking with SCD Type 2  
**Materialization:** Incremental  
**Update Frequency:** Daily (with ETL)

**Key Columns:**
- `tenant_id` - Tenant identifier
- `status` - Primary status code
- `contract_type` - Individual vs Corporate
- `is_paysle_unpaid` - Payment status
- `is_renewal_ng` - Renewal eligibility
- `valid_from` - Start date of this status
- `valid_to` - End date of this status (NULL if current)
- `is_current` - Boolean flag for active record

**Logic:**
1. Compares daily snapshot with previous day
2. Only inserts new record if status fields changed
3. Automatically closes out previous record (sets `valid_to` and `is_current=FALSE`)
4. Space-efficient: No duplicate rows for unchanged statuses

#### 2. Gold Layer: `tenant_status_transitions`

**Purpose:** Analysis-ready view with business-friendly labels  
**Materialization:** Table  
**Update Frequency:** Daily (with ETL)

**Key Features:**
- Human-readable status labels (e.g., "Active Tenant" instead of "5")
- Status transition descriptions (e.g., "Inquiry → Under Contract")
- Previous status tracking for flow analysis
- Duration calculations (days in each status)
- Payment status change flags
- Renewal eligibility tracking

## Data Flow

```
Daily ETL (7:00 AM JST)
  ↓
1. Load staging.tenants (current snapshot)
  ↓
2. dbt: tenant_status_history
   - Compare with yesterday
   - Detect changes in key fields
   - Insert new records if changed
   - Close previous records (set valid_to)
  ↓
3. dbt: tenant_status_transitions
   - Add human-readable labels
   - Calculate transitions
   - Compute durations
   - Analysis-ready output
```

## Status Fields Tracked

| Field | Description | Example Values |
|-------|-------------|----------------|
| **status** | Primary tenant lifecycle status | 1=Inquiry, 2=Preview, 3=Application, 4=Under Contract, 5=Active, 6=Moveout Notice, 7=Moved Out |
| **contract_type** | Individual vs Corporate | 1=Individual, 2/3=Corporate |
| **affiliation_status** | Employment/company status | Various codes |
| **is_transferred** | Transfer flag | 0/1 |
| **is_renewal_ng** | Renewal eligibility | 0=Eligible, 1=Not Eligible |
| **is_paysle_unpaid** | Payment status | 0=Paid, 1=Unpaid |
| **renewal_priority** | Renewal priority level | Numeric priority |
| **agreement_type** | Agreement type | Various codes |

## Example Queries

### 1. Find All Status Changes in Last 30 Days

```sql
SELECT 
    tenant_id,
    full_name,
    status_transition,
    effective_date,
    days_in_status
FROM gold.tenant_status_transitions
WHERE status_changed = TRUE
AND effective_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
ORDER BY effective_date DESC;
```

### 2. Calculate Average Time from Inquiry to Contract

```sql
WITH inquiry_records AS (
    SELECT tenant_id, MIN(effective_date) as inquiry_date
    FROM gold.tenant_status_transitions
    WHERE status_code = 1  -- Inquiry
    GROUP BY tenant_id
),
contract_records AS (
    SELECT tenant_id, MIN(effective_date) as contract_date
    FROM gold.tenant_status_transitions
    WHERE status_code = 4  -- Under Contract
    GROUP BY tenant_id
)
SELECT AVG(DATEDIFF(c.contract_date, i.inquiry_date)) as avg_days_to_contract
FROM inquiry_records i
INNER JOIN contract_records c ON i.tenant_id = c.tenant_id;
```

### 3. Find Tenants Who Became Unpaid This Month

```sql
SELECT 
    tenant_id,
    full_name,
    payment_status_change,
    effective_date,
    days_in_status
FROM gold.tenant_status_transitions
WHERE payment_status_changed = TRUE
AND payment_status_change = 'Became Unpaid'
AND effective_date >= DATE_FORMAT(CURDATE(), '%Y-%m-01')
ORDER BY effective_date DESC;
```

### 4. Tenant Status Flow Analysis (Sankey Diagram)

```sql
SELECT 
    previous_status_label AS from_status,
    status_label AS to_status,
    COUNT(*) AS transition_count
FROM gold.tenant_status_transitions
WHERE status_changed = TRUE
AND previous_status_label IS NOT NULL
GROUP BY previous_status_label, status_label
ORDER BY transition_count DESC;
```

### 5. Current Status Distribution

```sql
SELECT 
    status_label,
    contract_type_label,
    COUNT(*) AS tenant_count,
    AVG(days_in_status) AS avg_days_in_status
FROM gold.tenant_status_transitions
WHERE is_current = TRUE
GROUP BY status_label, contract_type_label
ORDER BY tenant_count DESC;
```

### 6. Retention Analysis: Days from Active to Moveout Notice

```sql
WITH active_periods AS (
    SELECT 
        tenant_id,
        effective_date AS active_date
    FROM gold.tenant_status_transitions
    WHERE status_code = 5  -- Active Tenant
),
moveout_periods AS (
    SELECT 
        tenant_id,
        effective_date AS moveout_notice_date
    FROM gold.tenant_status_transitions
    WHERE status_code = 6  -- Moveout Notice
)
SELECT 
    a.tenant_id,
    a.active_date,
    m.moveout_notice_date,
    DATEDIFF(m.moveout_notice_date, a.active_date) AS days_active_before_notice
FROM active_periods a
INNER JOIN moveout_periods m ON a.tenant_id = m.tenant_id
WHERE m.moveout_notice_date > a.active_date;
```

## Deployment Steps

### Step 1: Add Models to dbt Project ✅

Files created:
- `dbt/models/silver/tenant_status_history.sql`
- `dbt/models/gold/tenant_status_transitions.sql`
- `dbt/macros/scd_type2_close_records.sql`

Documentation updated:
- `dbt/models/silver/_silver_schema.yml`
- `dbt/models/gold/_gold_schema.yml`

### Step 2: Test Locally (Before Deploying)

```bash
cd dbt/

# Test compilation
dbt compile --select tenant_status_history tenant_status_transitions

# Run with full-refresh to create tables
dbt run --select tenant_status_history tenant_status_transitions --full-refresh

# Verify data
dbt run-operation query --args '{sql: "SELECT COUNT(*) FROM silver.tenant_status_history"}'
dbt run-operation query --args '{sql: "SELECT * FROM gold.tenant_status_transitions WHERE is_current=TRUE LIMIT 10"}'
```

### Step 3: Deploy to Production

```bash
# Upload updated dbt project to S3
aws s3 sync dbt/ s3://jram-gghouse/dbt-project/ \
    --exclude ".user.yml" \
    --exclude "target/*" \
    --exclude "dbt_packages/*" \
    --profile gghouse --region ap-northeast-1

# Next ETL run will pick up new models automatically
```

### Step 4: Monitor First Run

```bash
# Check CloudWatch logs after next ETL (7:00 AM JST)
aws logs tail /aws-glue/jobs/output \
    --follow --profile gghouse --region ap-northeast-1 \
    | grep -i "tenant_status"
```

### Step 5: Verify Data

```sql
-- Check initial load
SELECT COUNT(*) FROM silver.tenant_status_history;
-- Should show ~50,000 records (one per tenant)

-- Check all records are current on first run
SELECT COUNT(*) FROM silver.tenant_status_history WHERE is_current = TRUE;
-- Should equal total count on day 1

-- Check gold table
SELECT status_label, COUNT(*) 
FROM gold.tenant_status_transitions 
WHERE is_current = TRUE 
GROUP BY status_label;
-- Should show distribution of current statuses
```

## Performance Considerations

### Storage

**Initial Load:**
- ~50,000 tenants × 1 record each = 50,000 rows
- Estimated size: ~10-15 MB

**Ongoing Growth:**
- Only inserts when status changes
- Estimated: 100-500 changes per day
- Monthly growth: ~3,000-15,000 rows (~500KB-2MB)
- Annual growth: ~36,000-180,000 rows (~6-30MB)

**Conclusion:** Minimal storage impact

### Query Performance

- Primary key: `(tenant_id, valid_from)`
- Indexes automatically created by dbt
- is_current flag enables fast current-state queries
- Partitioning not needed (table size manageable)

### ETL Impact

- Incremental updates: ~5-10 seconds additional per run
- Only processes changed records
- Post-hook updates previous records efficiently
- **Conclusion:** Negligible ETL impact

## Monitoring

### Daily Checks

```sql
-- 1. Verify incremental updates working
SELECT 
    DATE(dbt_updated_at) AS update_date,
    COUNT(*) AS records_added
FROM silver.tenant_status_history
WHERE dbt_updated_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
GROUP BY DATE(dbt_updated_at)
ORDER BY update_date DESC;

-- 2. Check for orphaned "current" records
SELECT tenant_id, COUNT(*) AS current_count
FROM silver.tenant_status_history
WHERE is_current = TRUE
GROUP BY tenant_id
HAVING COUNT(*) > 1;
-- Should return 0 rows

-- 3. Verify valid_to dates are set correctly
SELECT COUNT(*) 
FROM silver.tenant_status_history
WHERE is_current = FALSE AND valid_to IS NULL;
-- Should be 0

-- 4. Check transition counts
SELECT 
    DATE(effective_date) AS date,
    COUNT(*) AS transitions
FROM gold.tenant_status_transitions
WHERE status_changed = TRUE
AND effective_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
GROUP BY DATE(effective_date)
ORDER BY date DESC;
```

## Use Cases Enabled

### 1. Customer Lifecycle Analysis
- Track time from inquiry to contract to active
- Identify bottlenecks in conversion funnel
- Measure dropout rates at each stage

### 2. Churn Prediction
- Analyze patterns before moveout notices
- Identify status changes correlated with churn
- Calculate average tenure by contract type

### 3. Payment Issue Tracking
- Monitor when tenants become unpaid
- Track payment resolution time
- Identify repeat payment issues

### 4. Renewal Analysis
- Track renewal eligibility changes
- Analyze renewal conversion rates
- Measure time from eligibility to renewal

### 5. Compliance & Audit
- Complete audit trail of status changes
- Verify status transition legitimacy
- Support dispute resolution

### 6. Operational Metrics
- Count status transitions per day/week/month
- Identify seasonal patterns
- Staff workload forecasting

## Dashboard Ideas

### Dashboard 1: Tenant Lifecycle Funnel
- Visualization: Sankey diagram
- Data: Status transitions from inquiry to active
- Metric: Conversion rate at each stage

### Dashboard 2: Status Change Timeline
- Visualization: Timeline/Gantt chart
- Data: Individual tenant status history
- Metric: Days in each status

### Dashboard 3: Payment Status Monitor
- Visualization: Alert table + trend line
- Data: Tenants who became unpaid
- Metric: Count and resolution time

### Dashboard 4: Renewal Pipeline
- Visualization: Stacked bar chart
- Data: Renewal eligibility changes
- Metric: Renewal rate by month

## Troubleshooting

### Issue: No Records After First Run

**Check:**
```sql
SELECT COUNT(*) FROM staging.tenants;
```

**Solution:** Ensure staging.tenants has data before running dbt

### Issue: Duplicate "is_current=TRUE" Records

**Check:**
```sql
SELECT tenant_id, COUNT(*) 
FROM silver.tenant_status_history 
WHERE is_current = TRUE 
GROUP BY tenant_id 
HAVING COUNT(*) > 1;
```

**Solution:** Run post-hook manually:
```sql
UPDATE silver.tenant_status_history
SET valid_to = DATE_SUB(CURDATE(), INTERVAL 1 DAY), is_current = FALSE
WHERE tenant_id IN (
    SELECT tenant_id FROM (
        SELECT tenant_id FROM silver.tenant_status_history 
        WHERE valid_from = CURDATE()
    ) t
)
AND valid_from < CURDATE() 
AND is_current = TRUE;
```

### Issue: Gold Table Not Updating

**Check:**
```sql
SELECT MAX(created_at) FROM gold.tenant_status_transitions;
```

**Solution:** Gold table materializes as "table", so run:
```bash
dbt run --select tenant_status_transitions --full-refresh
```

## Future Enhancements

### Phase 2: Additional Status Fields
- Track `moving_id` changes (contract changes)
- Monitor `under_contract_id` transitions
- Add `affiliation` changes

### Phase 3: Predictive Analytics
- Build churn prediction model using status patterns
- Forecast renewal likelihood based on history
- Identify high-risk tenants early

### Phase 4: Real-Time Alerts
- SNS notification when key statuses change
- Alert on unpaid status transition
- Notify on renewal eligibility changes

## Related Documentation

- **dbt Models:** `dbt/models/silver/tenant_status_history.sql`, `dbt/models/gold/tenant_status_transitions.sql`
- **Schema Docs:** `dbt/models/silver/_silver_schema.yml`, `dbt/models/gold/_gold_schema.yml`
- **ETL Process:** `glue/scripts/daily_etl.py`
- **Architecture:** `docs/UPDATED_ARCHITECTURE.md`

## Success Criteria

✅ **Deployment Successful:**
- [ ] Models compile without errors
- [ ] Initial load creates ~50K records
- [ ] All records have `is_current=TRUE` on day 1
- [ ] Gold table shows current status distribution

✅ **Daily Updates Working:**
- [ ] Incremental updates detect changes
- [ ] Previous records closed out properly
- [ ] Gold table shows new transitions
- [ ] ETL runtime increase <10 seconds

✅ **Data Quality:**
- [ ] No duplicate current records per tenant
- [ ] All historical records have `valid_to` set
- [ ] Status transitions are logical
- [ ] No orphaned records

---

**Status:** Ready to Deploy  
**Next Step:** Run local test, then deploy to production  
**Timeline:** Can deploy with tomorrow's ETL run (2026-02-06 07:00 JST)
