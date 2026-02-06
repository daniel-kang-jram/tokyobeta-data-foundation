# Tenant Status Change Tracking Guide

**Last Updated**: 2026-02-06  
**Status**: ✅ Tracking system is ACTIVE (Day 1 - Baseline established)

---

## Current Tenant Status Snapshot (Baseline)

As of **2026-02-06**, we have captured the initial snapshot of all 50,297 tenants:

| Status Code | Status Label | Total | Individual | Corporate | % of Total |
|------------|--------------|-------|------------|-----------|------------|
| 17 | **Moved Out** | 29,167 | 27,617 | 1,550 | 58.0% |
| 9 | **Active Lease (In Residence)** | 10,543 | 7,308 | 3,235 | 21.0% |
| 8 | **Canceled** | 5,292 | 5,150 | 142 | 10.5% |
| 16 | **Awaiting Maintenance** | 3,510 | 3,087 | 423 | 7.0% |
| 14 | **Move-out Notice Received** | 732 | 593 | 139 | 1.5% |
| 10 | **Active Lease (Contract Renewal)** | 454 | 402 | 52 | 0.9% |
| 5 | **Initial Rent Deposit** | 252 | 241 | 11 | 0.5% |
| Others | (11 other statuses) | 284 | 252 | 32 | 0.6% |

**Key Insights**:
- **Active tenants** (status 9, 10, 13): ~11,006 tenants (21.9%)
- **Moved out** (status 17): ~29,167 tenants (58.0%)
- **Pre-move-in pipeline** (status 0-7): ~377 tenants (0.7%)
- **Move-out in progress** (status 14, 15): ~799 tenants (1.6%)

---

## How Status Change Tracking Works

### System Architecture

```
Daily ETL Run (07:00 JST)
    ↓
[1] Snapshot current tenant statuses from staging.tenants
    ↓
[2] Compare with yesterday's snapshot in silver.tenant_status_history
    ↓
[3] Detect changes in key fields:
    • status (primary tenant status)
    • contract_type (individual/corporate)
    • affiliation_status (employment)
    • is_transferred (transfer flag)
    • is_renewal_ng (renewal eligibility)
    • is_paysle_unpaid (payment status)
    • renewal_priority
    ↓
[4] If changes detected:
    → Create new record with valid_from = today
    → Close previous record (set valid_to = yesterday, is_current = FALSE)
    ↓
[5] Generate gold.tenant_status_transitions for analysis
```

### Status Change Detection Logic

The system tracks **7 key status fields**:

1. **status** - Primary tenant status (17 possible values)
2. **contract_type** - Individual (1) vs Corporate (2/3)
3. **affiliation_status** - Employment/affiliation type
4. **is_transferred** - Whether tenant was transferred
5. **is_renewal_ng** - Renewal ineligibility flag
6. **is_paysle_unpaid** - Payment delinquency status
7. **renewal_priority** - Renewal priority level (0-3)

**Change is recorded when ANY of these fields changes between daily snapshots.**

---

## Querying Status Changes (Starting Tomorrow)

### Query 1: All Status Changes Today

```sql
SELECT 
    tenant_id,
    full_name,
    status_transition,
    effective_date,
    days_in_status,
    contract_type_label,
    payment_status_change
FROM gold.tenant_status_transitions
WHERE status_changed = TRUE
  AND effective_date = CURDATE()
ORDER BY effective_date DESC;
```

**Expected Results (from 2026-02-07 onwards)**:
- Tenants who changed from one status to another
- Example: "Active Lease (In Residence) → Move-out Notice Received"

---

### Query 2: Recent Status Changes (Last 7 Days)

```sql
SELECT 
    tenant_id,
    full_name,
    status_transition,
    effective_date,
    days_in_status,
    is_current
FROM gold.tenant_status_transitions
WHERE status_changed = TRUE
  AND effective_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
ORDER BY effective_date DESC
LIMIT 100;
```

---

### Query 3: Specific Status Transitions

**Example: Find tenants who recently gave move-out notice**

```sql
SELECT 
    tenant_id,
    full_name,
    status_transition,
    effective_date as notice_date,
    contract_type_label,
    is_unpaid
FROM gold.tenant_status_transitions
WHERE status_transition LIKE '%→ Move-out Notice Received%'
  AND effective_date >= '2026-02-01'
ORDER BY effective_date DESC;
```

**Example: Tenants who became unpaid**

```sql
SELECT 
    tenant_id,
    full_name,
    payment_status_change,
    effective_date,
    status_label
FROM gold.tenant_status_transitions
WHERE payment_status_change = 'Became Unpaid'
  AND effective_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
ORDER BY effective_date DESC;
```

**Example: Track renewal decisions**

```sql
SELECT 
    tenant_id,
    full_name,
    status_transition,
    renewal_eligibility_changed,
    effective_date
FROM gold.tenant_status_transitions
WHERE renewal_eligibility_changed = TRUE
  AND effective_date >= '2026-01-01'
ORDER BY effective_date DESC;
```

---

### Query 4: Status Change Frequency by Tenant

**Identify "churning" tenants with frequent status changes**

```sql
SELECT 
    tenant_id,
    full_name,
    COUNT(*) as status_change_count,
    MIN(effective_date) as first_change,
    MAX(effective_date) as latest_change,
    DATEDIFF(MAX(effective_date), MIN(effective_date)) as days_span
FROM gold.tenant_status_transitions
WHERE status_changed = TRUE
GROUP BY tenant_id, full_name
HAVING status_change_count > 3
ORDER BY status_change_count DESC
LIMIT 50;
```

---

### Query 5: Today's Pipeline Movements

**Track movement through the tenant acquisition funnel**

```sql
SELECT 
    DATE(effective_date) as change_date,
    SUBSTRING_INDEX(status_transition, ' → ', 1) as from_status,
    SUBSTRING_INDEX(status_transition, ' → ', -1) as to_status,
    COUNT(*) as transition_count
FROM gold.tenant_status_transitions
WHERE status_changed = TRUE
  AND effective_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
GROUP BY DATE(effective_date), from_status, to_status
ORDER BY change_date DESC, transition_count DESC;
```

---

## Common Status Transition Patterns

### Normal Tenant Lifecycle

```
Under Consideration (0)
    ↓
Scheduled Viewing (2)
    ↓
Viewed (3)
    ↓
Tentative Reservation/仮予約 (4)
    ↓
Initial Rent Deposit (5)
    ↓
Move-in Explanation (6)
    ↓
Active Lease (9)
    ↓
Move-out Notice Received (14)
    ↓
Moved Out (17)
```

### Churn Points to Monitor

1. **Early Cancellation**: Statuses 0-6 → Canceled (8)
2. **Non-renewal**: Active Lease (9) → Move-out Notice (14)
3. **Payment Issues**: Any → is_unpaid flag changes to TRUE
4. **Transfers**: is_transferred flag changes (check reason)

---

## Why No Changes Today?

**Today (2026-02-06) is Day 1** of the status tracking system. Results:

- ✅ **Initial snapshot captured**: 50,297 tenant records
- ✅ **Baseline established**: Current state recorded in `silver.tenant_status_history`
- ⏳ **First changes will appear**: Tomorrow (2026-02-07) after next ETL run
- 📊 **Historical data**: Not available (tracking starts today)

### What Happens Tomorrow?

```
Tomorrow's ETL (2026-02-07 07:00 JST):
1. Takes new snapshot of all tenant statuses
2. Compares with today's baseline
3. Records ANY changes as new rows in tenant_status_history
4. Sets status_changed = TRUE for changed records
5. Updates tenant_status_transitions for analysis
```

**Example of what you'll see tomorrow:**

| tenant_id | full_name | status_transition | effective_date |
|-----------|-----------|-------------------|----------------|
| 12345 | 田中太郎 | Active Lease → Move-out Notice | 2026-02-07 |
| 67890 | 鈴木花子 | Tentative Reservation → Initial Rent Deposit | 2026-02-07 |
| 23456 | 佐藤次郎 | Active Lease → Active Lease (unpaid) | 2026-02-07 |

---

## Business Intelligence Queries

### Monthly Status Change Summary

```sql
SELECT 
    DATE_FORMAT(effective_date, '%Y-%m') as month,
    SUBSTRING_INDEX(status_transition, ' → ', -1) as new_status,
    COUNT(*) as change_count,
    COUNT(DISTINCT tenant_id) as unique_tenants
FROM gold.tenant_status_transitions
WHERE status_changed = TRUE
GROUP BY month, new_status
ORDER BY month DESC, change_count DESC;
```

### Churn Analysis

```sql
-- Tenants who left in the last month
SELECT 
    COUNT(*) as churned_tenants,
    AVG(days_in_status) as avg_tenure_days,
    COUNT(CASE WHEN is_unpaid = 1 THEN 1 END) as unpaid_at_churn
FROM gold.tenant_status_transitions
WHERE status_transition LIKE '%→ Moved Out%'
  AND effective_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY);
```

### Conversion Funnel

```sql
-- Track conversion from inquiry to active lease
WITH funnel AS (
    SELECT 
        tenant_id,
        MAX(CASE WHEN status_label LIKE '%Inquiry%' THEN effective_date END) as inquiry_date,
        MAX(CASE WHEN status_label LIKE '%Active Lease%' THEN effective_date END) as active_date
    FROM gold.tenant_status_transitions
    GROUP BY tenant_id
)
SELECT 
    COUNT(CASE WHEN inquiry_date IS NOT NULL THEN 1 END) as inquiries,
    COUNT(CASE WHEN active_date IS NOT NULL THEN 1 END) as conversions,
    ROUND(COUNT(CASE WHEN active_date IS NOT NULL THEN 1 END) * 100.0 / 
          COUNT(CASE WHEN inquiry_date IS NOT NULL THEN 1 END), 2) as conversion_rate_pct,
    AVG(DATEDIFF(active_date, inquiry_date)) as avg_days_to_convert
FROM funnel
WHERE inquiry_date >= '2026-01-01';
```

---

## Monitoring & Alerts

### Daily Status Change Volume Check

```sql
-- Alert if daily status changes exceed normal range
SELECT 
    DATE(effective_date) as change_date,
    COUNT(*) as total_changes,
    COUNT(DISTINCT tenant_id) as unique_tenants_changed,
    COUNT(CASE WHEN payment_status_change IS NOT NULL THEN 1 END) as payment_changes,
    COUNT(CASE WHEN renewal_eligibility_changed = TRUE THEN 1 END) as renewal_changes
FROM gold.tenant_status_transitions
WHERE status_changed = TRUE
  AND effective_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
GROUP BY DATE(effective_date)
ORDER BY change_date DESC;
```

**Expected Daily Volume** (to be calibrated after 1 week):
- Normal: 50-200 status changes per day
- Alert if: > 500 changes (system issue or bulk update)
- Alert if: < 10 changes (ETL may have failed)

---

## Data Dictionary

### Key Columns in `gold.tenant_status_transitions`

| Column | Type | Description |
|--------|------|-------------|
| `tenant_id` | INT | Unique tenant identifier |
| `full_name` | VARCHAR | Tenant full name |
| `status_code` | INT | Numeric status code (0-17) |
| `status_label` | VARCHAR | Human-readable status name |
| `previous_status_code` | INT | Previous status (NULL if first record) |
| `status_changed` | BOOLEAN | **TRUE if status changed from previous day** |
| `status_transition` | VARCHAR | "Old Status → New Status" format |
| `effective_date` | DATE | Date this status became effective |
| `end_date` | DATE | Date this status ended (NULL if current) |
| `days_in_status` | INT | How many days tenant had this status |
| `is_current` | BOOLEAN | TRUE if this is the current active record |
| `contract_type_label` | VARCHAR | Individual / Corporate |
| `is_unpaid` | BOOLEAN | Whether tenant is currently unpaid |
| `payment_status_changed` | BOOLEAN | Payment status changed |
| `payment_status_change` | VARCHAR | "Became Unpaid" / "Payment Resolved" |
| `renewal_eligibility_changed` | BOOLEAN | Renewal eligibility changed |
| `is_renewal_ineligible` | BOOLEAN | Can't renew contract |
| `renewal_priority` | INT | Renewal priority level (0-3) |
| `is_transferred` | BOOLEAN | Tenant was transferred between units |

---

## Next Steps

### Today (2026-02-06)
- [x] Initial snapshot captured
- [x] Tracking system active
- [x] Baseline established

### Tomorrow (2026-02-07)
- [ ] First status changes will be recorded
- [ ] Validate change detection logic
- [ ] Calibrate expected daily change volume
- [ ] Test status change queries

### This Week
- [ ] Run daily queries to establish baseline metrics
- [ ] Identify common status transition patterns
- [ ] Set up CloudWatch alerts for anomalies
- [ ] Create QuickSight dashboard for status changes
- [ ] Document business rules for each status transition

---

## QuickSight Dashboard Ideas

### Dashboard 1: Daily Status Changes
- Line chart: Daily status change volume
- Bar chart: Top 10 status transitions today
- Metric: % of active tenants who gave move-out notice
- Table: Recent status changes (last 24 hours)

### Dashboard 2: Tenant Lifecycle
- Funnel chart: Inquiry → Active Lease conversion
- Bar chart: Average days in each status
- Heat map: Status transitions by day of week
- Metric: Average tenure before move-out

### Dashboard 3: Payment & Churn
- Line chart: New unpaid tenants per day
- Bar chart: Churn by reason (move-out, cancellation)
- Metric: % of move-outs who were unpaid
- Table: High-risk tenants (frequent status changes)

---

## Troubleshooting

### Q: Why are all `status_changed` values FALSE?

**A**: This is Day 1 (initial snapshot). Changes will appear from tomorrow onwards.

### Q: How do I see historical status changes before today?

**A**: Historical data is not available. The system only tracks changes from 2026-02-06 forward.

### Q: What if I need to backfill historical data?

**A**: Not possible from current data source. Consider:
1. Check if audit logs exist in source system
2. Contact vendor (Nazca) for historical tenant status data
3. Accept that tracking starts from today

### Q: Can I see what a tenant's status was on a specific date?

**A**: Yes, once we have a few days of data:

```sql
SELECT 
    tenant_id,
    full_name,
    status_label,
    effective_date,
    end_date
FROM gold.tenant_status_transitions
WHERE tenant_id = 12345
  AND effective_date <= '2026-02-10'
  AND (end_date >= '2026-02-10' OR end_date IS NULL)
ORDER BY effective_date DESC
LIMIT 1;
```

---

## Contact & Support

For questions about tenant status tracking:
- Documentation: `docs/TENANT_STATUS_TRACKING_GUIDE.md`
- Implementation: `dbt/models/silver/tenant_status_history.sql`
- Analysis view: `dbt/models/gold/tenant_status_transitions.sql`
- Schema: `dbt/models/_silver_schema.yml` and `_gold_schema.yml`
