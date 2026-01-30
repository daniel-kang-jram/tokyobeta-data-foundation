# Local Database Setup Scripts

Scripts for setting up and testing a local MySQL database with dbt models.

## Quick Start

1. **Start MySQL** (Docker):
   ```bash
   docker run -d --name tokyobeta-mysql -e MYSQL_ROOT_PASSWORD=localdev -e MYSQL_DATABASE=tokyobeta -p 3307:3306 mysql:8.0
   ```

2. **Setup Database**:
   ```bash
   ./scripts/setup_local_db_simple.sh
   ```

3. **Test dbt Models**:
   ```bash
   ./scripts/test_dbt_local.sh
   ```

## Scripts

### `setup_local_db_simple.sh`
Sets up local MySQL database with schemas and sample data.

**Usage**:
```bash
./scripts/setup_local_db_simple.sh
```

**What it does**:
- Tests MySQL connection
- Creates `staging`, `analytics`, and `seeds` schemas
- Loads sample data from SQL dump (if available)
- Or creates minimal test schema with sample data

**Environment Variables**:
- `DB_HOST` (default: 127.0.0.1)
- `DB_PORT` (default: 3307)
- `DB_USER` (default: root)
- `DB_PASSWORD` (default: localdev)
- `DB_NAME` (default: tokyobeta)

### `setup_local_db.sh`
Full setup script with Docker container management.

**Usage**:
```bash
./scripts/setup_local_db.sh
```

**Requirements**: Docker daemon must be running

### `load_sample_tables.py`
Python script to extract and load key tables from SQL dump.

**Usage**:
```bash
python3 scripts/load_sample_tables.py data/samples/gghouse_20260130.sql
```

**What it does**:
- Extracts CREATE TABLE statements for key tables
- Extracts INSERT statements (limited to 1000 rows per table)
- Loads into local MySQL database

### `test_dbt_local.sh`
Tests dbt models against local database.

**Usage**:
```bash
./scripts/test_dbt_local.sh
```

**What it does**:
- Tests database connection
- Runs all dbt models
- Runs dbt tests
- Validates output tables exist and have data

## Troubleshooting

See `docs/LOCAL_SETUP_GUIDE.md` for detailed troubleshooting.
