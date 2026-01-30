# Data Coverage Report (Full Dump)

**Dump**: `data/samples/gghouse_20260130.sql`  
**Date**: 2026-01-30  
**Scope**: Core tables used by analytics pipeline

## Row Counts (Source Dump → Local Staging)

| Table | Rows | Notes |
|------|------|-------|
| `rooms` | 16,401 | Expected ~16,000 owned rooms → ✅ coverage solid |
| `apartments` | 1,202 | Matches expectation from schema description |
| `tenants` | 50,175 | Current tenants + historical |
| `movings` | 62,038 | Contract lifecycle records |
| `m_nationalities` | 200 | Master list |

## Rooms Coverage

- **Total rooms**: 16,401 (meets expected 16,000+)
- **Room status distribution**:
  - `1` (Available for use): 15,776
  - `4` (Living room use): 56
  - `6` (Not available for use): 569

## Tenant Status Coverage (Active Leases)

Active lease definition from `data/database_schema_description.txt`:
`status IN (7, 9, 10, 13)`

| Status Label | Count |
|------------|-------|
| Active Leases | 11,144 |
| Moved out | 29,167 |
| Canceled | 5,270 |
| Awaiting Maintenance | 3,344 |
| Move-out Notice Received | 700 |
| Initial Rent Deposit | 212 |
| Move-in Notice Received | 130 |
| Expected Move-out | 77 |
| Tentative Reservation | 35 |
| Move-in Explanation | 32 |
| Viewed | 26 |
| Move-in Procedure | 17 |
| Under Consideration | 10 |
| Terminated | 6 |
| Scheduled Viewing | 5 |

## ETL Pipeline Execution (Full Data)

### dbt Run (Local)

| Model | Rows Created |
|-------|--------------|
| `daily_activity_summary` | 5,246 |
| `new_contracts` | 17,573 |
| `moveouts` | 15,768 |
| `moveout_notices` | 3,791 |

### Key Observations

1. **Room number column** is `rooms.room_number` (not `room_no`).
2. **Active lease status** exists in `tenants.status` but is not yet modeled.
3. **Geocoding bounds**: ~3–4% of records fall outside Tokyo bounds.

## Data Quality Findings (dbt Tests on Full Data)

### Failing Tests (Data Quality)

- **Geocoding outside Tokyo bounds**:
  - `new_contracts`: 629 rows
  - `moveouts`: 567 rows
  - `moveout_notices`: 115 rows
- **Monthly rent <= 0**:
  - `new_contracts`: 614 rows
- **Moveout date before contract start**:
  - `moveouts`: 1 row
- **Negative stay days**:
  - `moveouts`: 1 row
- **Future activity dates**:
  - `daily_activity_summary`: 100 rows (created_at in future)

### Actionable Implications

1. **Rooms coverage is solid** (16,401 rows).
2. **Geocoding issues** likely due to legacy or malformed lat/long in `apartments`.
3. **Monthly rent anomalies** should be filtered or corrected in ETL.
4. **Future dates** likely due to data entry errors in `movings.created_at`.

## Key Field Null Rates (new_contracts)

| Field | Null Count | Total | Notes |
|------|------------|-------|------|
| `contract_channel` | 0 | 17,573 | Complete |
| `rent_start_date` | 17,570 | 17,573 | Mostly NULL (expected per source) |
| `contract_expiration_date` | 11,156 | 17,573 | High NULL rate |

## Missing vs. Expected Fields

No missing fields for the 4 required BI tables.  
Additional fields from schema description that are **not yet modeled**:

- `tenants.status` (for Active Leases reporting)
- `rooms.status` (room availability)
- `rooms.gender_type`, `rooms.bed_type` (room attributes)

These can be added as separate analytical models if needed.
