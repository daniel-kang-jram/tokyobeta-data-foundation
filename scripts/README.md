# Scripts Directory

This directory contains operational, setup, and maintenance scripts for the TokyoBeta Data Consolidation project.

## 📂 Directory Structure

### Setup & Local Development
- **`setup_local_db.sh`**: Sets up a local MySQL database using Docker for testing.
- **`setup_direnv.sh`**: Configures `direnv` for automatic AWS profile management.
- **`install_dependencies.sh`**: Installs Python dependencies.
- **`load_sample_tables.py`**: Loads sample data into local database from SQL dump.
- **`test_dbt_local.sh`**: Runs dbt models and tests against the local database.

### Operations & Maintenance
- **`emergency_staging_fix.py`**: Emergency script to load staging data from S3 if Glue fails.
- **`load_full_dump_to_staging.py`**: Loads a full SQL dump into the staging environment.
- **`check_staging_activity_final.sh`**: Analyzes staging tables for recent activity.
- **`drop_empty_staging_tables.py`**: Identifies and drops empty staging tables.
- **`deploy_freshness_monitoring.sh`**: Deploys CloudWatch alarms and Lambda for monitoring.
- **`deploy_nationality_enrichment.sh`**: Deploys the LLM nationality enrichment components.

### Analysis & Reporting
- **`analyze_rent_roll_vs_gold.py`**: Compares Rent Roll data with Gold tables.
- **`count_unique_active_tenants.py`**: Counts active tenants based on business logic.
- **`query_gold_active_tenants.py`**: Queries Gold tables for active tenant counts.

### Subdirectories
- **`tests/`**: Integration and unit tests for scripts.
- **`quicksight/`**: Scripts for managing QuickSight dashboards.
- **`example_cron_scripts/`**: Templates for EC2 cron jobs.

## 🚀 Quick Start (Local Dev)

1. **Start Local Database** (Docker):
   ```bash
   ./scripts/setup_local_db.sh
   ```

2. **Test dbt Models**:
   ```bash
   ./scripts/test_dbt_local.sh
   ```

## 🛠️ Common Operations

**Check Data Freshness:**
```bash
python3 scripts/emergency_staging_fix.py --check-only
```

**Deploy Monitoring:**
```bash
./scripts/deploy_freshness_monitoring.sh
```

**Setup AWS Profile:**
```bash
./scripts/setup_direnv.sh
```
