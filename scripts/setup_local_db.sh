#!/bin/bash
# Setup local MySQL database for testing dbt models
# This script sets up a Docker MySQL container and loads sample data

set -euo pipefail

# Configuration
DB_NAME="tokyobeta"
DB_USER="root"
DB_PASSWORD="localdev"
DB_PORT="3307"
CONTAINER_NAME="tokyobeta-mysql"
DUMP_FILE="data/samples/gghouse_20260130.sql"

echo "Setting up local MySQL database for testing..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "ERROR: Docker daemon is not running. Please start Docker Desktop and try again."
    exit 1
fi

# Check if container already exists
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Container ${CONTAINER_NAME} already exists. Removing..."
    docker rm -f ${CONTAINER_NAME} > /dev/null 2>&1 || true
fi

# Start MySQL container
echo "Starting MySQL container..."
docker run -d \
    --name ${CONTAINER_NAME} \
    -e MYSQL_ROOT_PASSWORD=${DB_PASSWORD} \
    -e MYSQL_DATABASE=${DB_NAME} \
    -p ${DB_PORT}:3306 \
    mysql:8.0 \
    --character-set-server=utf8mb4 \
    --collation-server=utf8mb4_unicode_ci

# Wait for MySQL to be ready
echo "Waiting for MySQL to be ready..."
sleep 10
for i in {1..30}; do
    if docker exec ${CONTAINER_NAME} mysqladmin ping -h localhost --silent; then
        echo "MySQL is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "ERROR: MySQL failed to start after 30 attempts"
        exit 1
    fi
    sleep 2
done

# Create schemas
echo "Creating schemas..."
docker exec -i ${CONTAINER_NAME} mysql -u${DB_USER} -p${DB_PASSWORD} <<EOF
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS seeds;
USE staging;
EOF

# Load sample data from CSV files (faster than full dump)
echo "Loading sample data from CSV files..."

# Function to load CSV into table
load_csv() {
    local table=$1
    local csv_file=$2
    
    if [ ! -f "$csv_file" ]; then
        echo "  WARNING: $csv_file not found, skipping $table"
        return
    fi
    
    echo "  Loading $table from $csv_file..."
    
    # Get column names from first line
    local columns=$(head -1 "$csv_file" | tr ',' '`,' | sed 's/^/`/' | sed 's/$/`/')
    
    # Create table structure (simplified - we'll use the actual schema)
    docker exec -i ${CONTAINER_NAME} mysql -u${DB_USER} -p${DB_PASSWORD} staging <<EOF
SET FOREIGN_KEY_CHECKS=0;
DROP TABLE IF EXISTS \`${table}\`;
EOF

    # For now, we'll create a simple approach: load a subset of the SQL dump
    echo "  Note: Loading full table structure from SQL dump would be better"
    echo "  For testing, we'll create minimal tables with sample data"
}

# Alternative: Extract and load just the key tables from SQL dump
echo "Extracting key tables from SQL dump..."
if [ -f "$DUMP_FILE" ]; then
    echo "  Extracting CREATE TABLE and INSERT statements for key tables..."
    
    # Extract movings table
    docker exec -i ${CONTAINER_NAME} mysql -u${DB_USER} -p${DB_PASSWORD} staging <<'EOSQL'
-- This is a placeholder - we'll use a Python script to extract and load
-- For now, create minimal test tables
EOSQL

    echo "  Using Python script to extract and load tables..."
    python3 scripts/load_sample_tables.py ${DUMP_FILE} || {
        echo "  WARNING: Python loader not available, creating minimal test schema"
        create_minimal_schema
    }
else
    echo "  WARNING: SQL dump file not found at $DUMP_FILE"
    echo "  Creating minimal test schema instead..."
    create_minimal_schema
fi

echo ""
echo "✅ Local database setup complete!"
echo ""
echo "Connection details:"
echo "  Host: localhost"
echo "  Port: ${DB_PORT}"
echo "  Database: ${DB_NAME}"
echo "  User: ${DB_USER}"
echo "  Password: ${DB_PASSWORD}"
echo ""
echo "To connect:"
echo "  mysql -h 127.0.0.1 -P ${DB_PORT} -u ${DB_USER} -p${DB_PASSWORD} ${DB_NAME}"
echo ""
echo "To stop the container:"
echo "  docker stop ${CONTAINER_NAME}"
echo ""
echo "To remove the container:"
echo "  docker rm -f ${CONTAINER_NAME}"
