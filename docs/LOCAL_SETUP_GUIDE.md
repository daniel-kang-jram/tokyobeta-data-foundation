# Local Database Setup Guide

This guide explains how to set up a local MySQL database for testing dbt models with sample data.

## Prerequisites

- MySQL 8.0+ (via Docker or local installation)
- Python 3.8+
- dbt-core with mysql adapter: `pip install dbt-mysql`

## Option 1: Using Docker (Recommended)

### Step 1: Start MySQL Container

```bash
docker run -d \
  --name tokyobeta-mysql \
  -e MYSQL_ROOT_PASSWORD=localdev \
  -e MYSQL_DATABASE=tokyobeta \
  -p 3307:3306 \
  mysql:8.0 \
  --character-set-server=utf8mb4 \
  --collation-server=utf8mb4_unicode_ci
```

Wait 10-15 seconds for MySQL to initialize.

### Step 2: Run Setup Script

```bash
./scripts/setup_local_db_simple.sh
```

This will:
- Create `staging`, `analytics`, and `seeds` schemas
- Load sample data from the SQL dump (if available)
- Or create minimal test schema with sample data

## Option 2: Using Local MySQL Installation

### Step 1: Ensure MySQL is Running

```bash
# macOS with Homebrew
brew services start mysql

# Or check if already running
mysql -u root -p -e "SELECT 1"
```

### Step 2: Update Connection Details

Edit `scripts/setup_local_db_simple.sh` and set:
```bash
export DB_HOST=127.0.0.1
export DB_PORT=3306  # Default MySQL port
export DB_USER=root
export DB_PASSWORD=your_password
```

### Step 3: Run Setup Script

```bash
./scripts/setup_local_db_simple.sh
```

## Verify Setup

```bash
mysql -h 127.0.0.1 -P 3307 -u root -plocaldev tokyobeta -e "SHOW TABLES IN staging;"
```

You should see:
- `movings`
- `tenants`
- `apartments`
- `rooms`
- `m_nationalities`

## Running dbt Models

### Step 1: Set Target to Local

```bash
cd dbt
export DBT_TARGET=local
```

### Step 2: Run dbt Models

```bash
# Run all models
dbt run --target local

# Run specific model
dbt run --select daily_activity_summary --target local

# Run tests
dbt test --target local
```

### Step 3: Verify Outputs

```bash
mysql -h 127.0.0.1 -P 3307 -u root -plocaldev tokyobeta -e "SELECT * FROM analytics.daily_activity_summary LIMIT 10;"
mysql -h 127.0.0.1 -P 3307 -u root -plocaldev tokyobeta -e "SELECT * FROM analytics.new_contracts LIMIT 10;"
mysql -h 127.0.0.1 -P 3307 -u root -plocaldev tokyobeta -e "SELECT * FROM analytics.moveouts LIMIT 10;"
mysql -h 127.0.0.1 -P 3307 -u root -plocaldev tokyobeta -e "SELECT * FROM analytics.moveout_notices LIMIT 10;"
```

## Troubleshooting

### Docker Not Running

```bash
# Start Docker Desktop, then retry
docker ps
```

### Connection Refused

- Check if MySQL container is running: `docker ps | grep tokyobeta-mysql`
- Check port: `docker port tokyobeta-mysql`
- Try restarting: `docker restart tokyobeta-mysql`

### dbt Connection Errors

- Verify `dbt/profiles.yml` has correct `local` target settings
- Test connection: `mysql -h 127.0.0.1 -P 3307 -u root -plocaldev tokyobeta`
- Check dbt debug: `dbt debug --target local`

### Missing Tables

If tables are missing, the setup script will create a minimal schema. For full data:

1. Ensure `data/samples/gghouse_20260130.sql` exists
2. Run: `python3 scripts/load_sample_tables.py data/samples/gghouse_20260130.sql`

## Cleanup

To stop and remove the Docker container:

```bash
docker stop tokyobeta-mysql
docker rm tokyobeta-mysql
```

## Next Steps

After successful local testing:
1. Review output data quality
2. Validate all 4 BI tables have expected columns
3. Check row counts match expectations
4. Proceed with production deployment
