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
- **`flash_report_fill/`**: Isolated module to compute and fill the monthly occupancy flash report template from Aurora.

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

## February Flash Report Automation

Use the dedicated module under `scripts/flash_report_fill/`:

```bash
python3 scripts/flash_report_fill/fill_flash_report.py \
  --template-path "/Users/danielkang/Downloads/March Occupancy Flash Report_02282026.xlsx" \
  --sheet-name "Flash Report（2月28日）" \
  --output-dir "/Users/danielkang/Downloads" \
  --snapshot-start-jst "2026-02-01 00:00:00 JST" \
  --snapshot-asof-jst "2026-02-28 05:00:00 JST" \
  --feb-end-jst "2026-02-28 23:59:59 JST" \
  --mar-start-jst "2026-03-01 00:00:00 JST" \
  --mar-end-jst "2026-03-31 23:59:59 JST" \
  --movein-prediction-date-column original_movein_date \
  --moveout-prediction-date-column moveout_date \
  --d5-benchmark 11271 \
  --d5-tolerance 10 \
  --aws-profile gghouse \
  --db-host tokyobeta-prod-aurora-cluster-public.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com \
  --db-port 3306
```

Check-only run (CSV + diagnostics only):

```bash
python3 scripts/flash_report_fill/fill_flash_report.py \
  --template-path "/Users/danielkang/Downloads/March Occupancy Flash Report_02282026.xlsx" \
  --sheet-name "Flash Report（2月28日）" \
  --output-dir "/Users/danielkang/Downloads" \
  --db-host tokyobeta-prod-aurora-cluster-public.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com \
  --check-only \
  --emit-flags-csv
```

Notes:
- Supports both workbook profiles:
  - `Flash Report（2月）` (legacy)
  - `Flash Report（2月28日）` / `Flash Report（3月～）` (updated)
- D5 occupancy is fact-aligned only (strict mode archived).
- For updated sheets, `D14/E14` (March planned move-ins) are intentionally left blank.
- Writes only input cells and preserves profile-specific formula cells (`E5`, `H*` or `I*`, etc.).
- Workbook denominator remains fixed at `16109` by business rule.
- Exports:
  - filled workbook (`February_Occupancy_FlashReport_filled_YYYYMMDD_HHMM.xlsx`)
  - metrics CSV
  - reconciliation CSV (includes `d5_fact_aligned` vs benchmark + fact-aligned diagnostic categories)
  - optional anomaly flag CSVs
