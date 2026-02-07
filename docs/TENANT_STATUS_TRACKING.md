# Tenant Status History Tracking

**Feature**: Historical Status Tracking (SCD Type 2)  
**Deployed**: February 6, 2026  
**Status**: ✅ Production Active

---

## Overview

Implemented **tenant status history tracking** using Slowly Changing Dimension (SCD) Type 2 pattern to capture complete audit trail of tenant status transitions over time.

---

## Business Value

### Before
- ❌ Only current tenant status available
- ❌ No way to know when status changed
- ❌ Cannot analyze status transition patterns
- ❌ Missing audit trail

### After
- ✅ Complete history of status changes
- ✅ Exact transition timestamps
- ✅ Status flow pattern analysis
- ✅ Full compliance audit trail
- ✅ KPI calculations (time in status)

---

## Architecture

### Tables

#### 1. Silver Layer: `tenant_status_history`
**Purpose**: Raw historical tracking with SCD Type 2  
**Materialization**: Incremental  
**Update**: Daily with ETL

**Key Columns**:
- `tenant_id` - Tenant identifier
- `status` - Primary status code
- `contract_type` - Individual vs Corporate
- `is_paysle_unpaid` - Payment status
- `is_renewal_ng` - Renewal eligibility
- `valid_from` - Start date of status
- `valid_to` - End date (NULL if current)
- `is_current` - Boolean flag for active record

**Logic**:
1. Compare daily snapshot with previous day
2. Insert new record only if status fields changed
3. Close previous record (set `valid_to`, `is_current=FALSE`)
4. Space-efficient (no duplicates for unchanged statuses)

#### 2. Gold Layer: `tenant_status_transitions`
**Purpose**: Analysis-ready view with business labels  
**Materialization**: Table  
**Update**: Daily with ETL

**Features**:
- Human-readable status labels ("Active Tenant" not "5")
- Status transition descriptions ("Inquiry → Under Contract")
- Previous status tracking
- Duration calculations (days in status)
- Payment status change flags
- Renewal eligibility tracking

---

## Status Fields Tracked

| Field | Description | Example Values |
|-------|-------------|----------------|
| `status` | Primary tenant lifecycle | 1=Inquiry, 5=Active, 7=Moved Out |
| `contract_type` | Individual vs Corporate | 1=Individual, 2/3=Corporate |
| `affiliation_status` | Employment status | Various codes |
| `is_transferred` | Transfer flag | 0/1 |
| `is_renewal_ng` | Renewal eligibility | 0=Eligible, 1=Not Eligible |
| `is_paysle_unpaid` | Payment status | 0=Paid, 1=Unpaid |
| `renewal_priority` | Renewal priority | Numeric priority |
| `agreement_type` | Agreement type | Various codes |

---

## Common Queries

### 1. Recent Status Changes (Last 30 Days)
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

### 2. Average Time Inquiry → Contract
```sql
WITH inquiry_records AS (
    SELECT tenant_id, MIN(effective_date) as inquiry_date
    FROM gold.tenant_status_transitions
    WHERE status_code = 1
    GROUP BY tenant_id
),
contract_records AS (
    SELECT tenant_id, MIN(effective_date) as contract_date
    FROM gold.tenant_status_transitions
    WHERE status_code = 4
    GROUP BY tenant_id
)
SELECT AVG(DATEDIFF(c.contract_date, i.inquiry_date)) as avg_days_to_contract
FROM inquiry_records i
INNER JOIN contract_records c ON i.tenant_id = c.tenant_id;
```

### 3. Current Status Distribution
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

### 4. Status Flow Analysis (for Sankey Diagram)
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

### 5. Tenants Who Became Unpaid This Month
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

### 6. Retention Analysis: Active → Moveout Notice
```sql
WITH active_periods AS (
    SELECT tenant_id, effective_date AS active_date
    FROM gold.tenant_status_transitions
    WHERE status_code = 5
),
moveout_periods AS (
    SELECT tenant_id, effective_date AS moveout_notice_date
    FROM gold.tenant_status_transitions
    WHERE status_code = 6
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

---

## Data Analysis (Feb 7, 2026)

### Status Distribution (After Fix)
| Status | Count | % |
|--------|-------|---|
| Moved Out | 28,366 | 59% |
| In Residence | 9,955 | 21% |
| Cancelled | 5,029 | 10% |
| Awaiting Maintenance | 3,023 | 6% |
| Others | 2,631 | 4% |

### Key Insights
- **59% moved out** - Large historical tenant base
- **21% current residents** - Active tenant population
- **10% cancelled** - Churn during application/preview
- **Average days in status**: 247 days (8.2 months)

---

## Use Cases

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

---

## Dashboard Ideas

### 1. Tenant Lifecycle Funnel
- **Visualization**: Sankey diagram
- **Data**: Status transitions from inquiry to active
- **Metric**: Conversion rate at each stage

### 2. Status Change Timeline
- **Visualization**: Timeline/Gantt chart
- **Data**: Individual tenant status history
- **Metric**: Days in each status

### 3. Payment Status Monitor
- **Visualization**: Alert table + trend line
- **Data**: Tenants who became unpaid
- **Metric**: Count and resolution time

### 4. Renewal Pipeline
- **Visualization**: Stacked bar chart
- **Data**: Renewal eligibility changes
- **Metric**: Renewal rate by month

---

## Performance

### Storage
**Initial Load**: ~50,000 tenants × 1 record = 50,000 rows (~10-15 MB)

**Growth Rate**:
- Daily changes: 100-500 records
- Monthly: ~3,000-15,000 rows (~500KB-2MB)
- Annual: ~36,000-180,000 rows (~6-30MB)

**Conclusion**: Minimal storage impact

### Query Performance
- Primary key: `(tenant_id, valid_from)`
- Indexes auto-created by dbt
- `is_current` flag enables fast current-state queries
- No partitioning needed (manageable size)

### ETL Impact
- Incremental updates: ~5-10 seconds per run
- Only processes changed records
- **Conclusion**: Negligible ETL impact

---

## Monitoring

### Daily Health Checks
```sql
-- 1. Verify incremental updates
SELECT 
    DATE(dbt_updated_at) AS update_date,
    COUNT(*) AS records_added
FROM silver.tenant_status_history
WHERE dbt_updated_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
GROUP BY DATE(dbt_updated_at);

-- 2. Check for orphaned "current" records
SELECT tenant_id, COUNT(*) AS current_count
FROM silver.tenant_status_history
WHERE is_current = TRUE
GROUP BY tenant_id
HAVING COUNT(*) > 1;
-- Should return 0 rows

-- 3. Verify valid_to dates
SELECT COUNT(*) 
FROM silver.tenant_status_history
WHERE is_current = FALSE AND valid_to IS NULL;
-- Should be 0

-- 4. Check recent transitions
SELECT 
    DATE(effective_date) AS date,
    COUNT(*) AS transitions
FROM gold.tenant_status_transitions
WHERE status_changed = TRUE
AND effective_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
GROUP BY DATE(effective_date);
```

---

## Troubleshooting

### Issue: No Records After First Run
**Check**: `SELECT COUNT(*) FROM staging.tenants;`  
**Solution**: Ensure staging has data before dbt runs

### Issue: Duplicate Current Records
**Check**: Look for tenants with multiple `is_current=TRUE`  
**Solution**: Run post-hook manually to close old records

### Issue: Gold Table Not Updating
**Check**: `SELECT MAX(created_at) FROM gold.tenant_status_transitions;`  
**Solution**: Run `dbt run --select tenant_status_transitions --full-refresh`

---

## Future Enhancements

### Phase 2: Additional Tracking
- Track `moving_id` changes (contract changes)
- Monitor `under_contract_id` transitions
- Add `affiliation` changes

### Phase 3: Predictive Analytics
- Build churn prediction model
- Forecast renewal likelihood
- Identify high-risk tenants early

### Phase 4: Real-Time Alerts
- SNS notification on key status changes
- Alert on unpaid status transition
- Notify on renewal eligibility changes

---

## Files

### dbt Models
- `dbt/models/silver/tenant_status_history.sql`
- `dbt/models/gold/tenant_status_transitions.sql`
- `dbt/macros/scd_type2_close_records.sql`

### Schema Documentation
- `dbt/models/silver/_silver_schema.yml`
- `dbt/models/gold/_gold_schema.yml`

### Tests
- `dbt/tests/` (unit tests for status tracking logic)

---

**Status**: ✅ Production active, tracking all changes  
**Next Review**: March 7, 2026
