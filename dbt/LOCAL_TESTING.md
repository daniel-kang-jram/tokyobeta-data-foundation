# Local dbt Testing Guide

## Setup

A Python virtual environment with dbt-mysql has been configured for local testing:

```bash
# Activate the virtual environment
source venv/bin/activate

# Verify dbt installation
dbt --version
```

## Testing Models (Syntax Validation Only)

Since we don't have local database credentials, use dummy environment variables for syntax validation:

```bash
# Set dummy credentials
export AURORA_ENDPOINT="dummy.local"
export AURORA_USERNAME="dummy"
export AURORA_PASSWORD="dummy"
export DBT_TARGET="dev"

# Navigate to dbt directory
cd dbt

# Parse all models to validate syntax
dbt parse --profiles-dir .

# Compile specific models to see generated SQL
dbt compile --select moveout_analysis --profiles-dir .
dbt compile --select moveout_summary --profiles-dir .
```

## Compiled SQL Output

After compilation, view the generated SQL:

```bash
# View compiled moveout_analysis
cat target/compiled/tokyobeta_analytics/models/gold/moveout_analysis.sql

# View compiled moveout_summary
cat target/compiled/tokyobeta_analytics/models/gold/moveout_summary.sql
```

## Quick Test Command

Single command to validate our new models:

```bash
source venv/bin/activate && \
cd dbt && \
AURORA_ENDPOINT=dummy.local AURORA_USERNAME=dummy AURORA_PASSWORD=dummy DBT_TARGET=dev \
dbt parse --profiles-dir .
```

## Notes

- **Syntax validation only**: These commands validate Jinja templating and SQL syntax without connecting to a database
- **Full testing**: Complete testing with data happens during the AWS Glue ETL run
- **Python version**: Using Python 3.13.5 with dbt-mysql 1.7.0
- **Dependencies**: dbt_utils package is installed via `dbt deps`

## Production Testing

The models will be fully tested during the next ETL run:

```bash
# Trigger manual ETL run
aws glue start-job-run \
    --job-name tokyobeta-prod-daily-etl \
    --profile gghouse --region ap-northeast-1

# Check run status
aws glue get-job-runs \
    --job-name tokyobeta-prod-daily-etl \
    --max-results 1 \
    --profile gghouse --region ap-northeast-1
```

## Troubleshooting

### Virtual Environment Not Found

```bash
# Create new virtual environment from project root
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install dbt-mysql
```

### Missing dbt_utils Package

```bash
cd dbt
dbt deps --profiles-dir .
```

### Parse Warnings

The warnings about unused configuration paths are expected:
- `models.tokyobeta_analytics.staging` - staging directory has no models
- `seeds.tokyobeta_analytics.asset_geocoding` - seed file doesn't exist

These don't affect functionality.
