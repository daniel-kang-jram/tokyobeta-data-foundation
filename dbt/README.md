# dbt Project: Tokyo Beta Analytics

This dbt project transforms raw staging data from the GGhouse PMS into analytics-ready tables for QuickSight dashboards.

## Project Structure

```
dbt/
├── dbt_project.yml          # Project configuration
├── profiles.yml             # Database connection profiles
├── models/
│   ├── staging/             # Source definitions
│   │   └── _sources.yml    # staging.* table definitions
│   ├── intermediate/        # Business logic layers (future)
│   └── analytics/           # Final dashboard tables
│       ├── daily_activity_summary.sql
│       ├── new_contracts.sql
│       ├── moveouts.sql
│       ├── moveout_notices.sql
│       └── _analytics_schema.yml
├── tests/                   # Custom SQL tests
│   ├── assert_no_future_dates.sql
│   ├── assert_geocoding_valid.sql
│   └── assert_referential_integrity.sql
├── macros/                  # Reusable SQL macros
│   ├── clean_string_null.sql
│   ├── safe_moveout_date.sql
│   └── is_corporate.sql
└── seeds/                   # Static CSV data
    └── asset_geocoding.csv  # Manual geocoding overrides
```

## Analytics Tables

### 1. daily_activity_summary
**Purpose**: Daily KPIs by tenant type (個人/法人)  
**Granularity**: One row per (date, tenant_type)  
**Metrics**: Applications, contracts signed, move-ins, move-outs, net occupancy change

### 2. new_contracts  
**Purpose**: New contract details with demographics  
**Granularity**: One row per contract  
**Key Fields**: AssetID, Room, Demographics (age, gender, nationality), Geolocation

### 3. moveouts
**Purpose**: Completed moveouts with contract history  
**Granularity**: One row per moveout  
**Key Fields**: Same as new_contracts + stay duration, moveout reason

### 4. moveout_notices
**Purpose**: Rolling 24-month window of moveout notices for projections  
**Materialization**: Incremental (only new notices added)  
**Purge Logic**: Records older than 24 months are automatically excluded

## Running dbt

### Prerequisites
```bash
pip install dbt-mysql
export AURORA_ENDPOINT="<cluster-endpoint>"
export AURORA_USERNAME="admin"
export AURORA_PASSWORD="<from-secrets-manager>"
export DBT_TARGET="prod"
```

### Commands

```bash
# Install dbt dependencies
dbt deps

# Run all models
dbt run

# Run tests
dbt test

# Run specific model
dbt run --select daily_activity_summary

# Run with full refresh (drop and recreate tables)
dbt run --full-refresh

# Generate documentation
dbt docs generate
dbt docs serve
```

## Data Quality Tests

dbt runs these tests automatically:

1. **Schema tests** (in `_analytics_schema.yml`)
   - Uniqueness constraints
   - NOT NULL checks
   - Accepted values
   - Custom expressions

2. **Custom SQL tests** (in `tests/`)
   - No future dates
   - Valid Tokyo geocoding
   - Referential integrity

## Deployment

dbt is invoked by the AWS Glue ETL job after staging data is loaded:

```python
# In Glue script
import subprocess
subprocess.run([
    "dbt", "run",
    "--profiles-dir", "/opt/dbt",
    "--target", "prod"
], check=True)
```

## Troubleshooting

### Test Failures
```bash
# See which tests failed
dbt test --store-failures

# Query failed test results
SELECT * FROM test_results.assert_no_future_dates;
```

### Model Failures
```bash
# Run with debug logging
dbt --debug run --select <model_name>
```

## Development Workflow (TDD)

1. **Write test first** (add to `_analytics_schema.yml` or `tests/`)
2. **Run test** (should fail): `dbt test --select <model_name>`
3. **Write/update model** (SQL in `models/analytics/`)
4. **Run model**: `dbt run --select <model_name>`
5. **Run test again** (should pass): `dbt test --select <model_name>`
6. **Commit changes**
