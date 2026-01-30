#!/bin/bash
# Simplified local database setup - creates minimal test schema
# Use this if Docker is not available or for quick testing

set -euo pipefail

DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3307}"
DB_USER="${DB_USER:-root}"
DB_PASSWORD="${DB_PASSWORD:-localdev}"
DB_NAME="${DB_NAME:-tokyobeta}"

echo "Setting up local MySQL database for testing..."
echo "Host: ${DB_HOST}:${DB_PORT}"
echo ""

# Test connection
if ! mysql -h${DB_HOST} -P${DB_PORT} -u${DB_USER} -p${DB_PASSWORD} -e "SELECT 1" > /dev/null 2>&1; then
    echo "ERROR: Cannot connect to MySQL at ${DB_HOST}:${DB_PORT}"
    echo ""
    echo "Please ensure:"
    echo "  1. MySQL is running (Docker or local installation)"
    echo "  2. Connection details are correct"
    echo ""
    echo "To start with Docker:"
    echo "  docker run -d --name tokyobeta-mysql -e MYSQL_ROOT_PASSWORD=localdev -e MYSQL_DATABASE=tokyobeta -p 3307:3306 mysql:8.0"
    echo ""
    exit 1
fi

echo "✅ Connected to MySQL"
echo ""

# Create schemas
echo "Creating schemas..."
mysql -h${DB_HOST} -P${DB_PORT} -u${DB_USER} -p${DB_PASSWORD} <<EOF
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS seeds;
EOF

echo "✅ Schemas created"
echo ""

# Load sample data using Python script
if [ -f "scripts/load_sample_tables.py" ] && [ -f "data/samples/gghouse_20260130.sql" ]; then
    echo "Loading sample tables from SQL dump..."
    python3 scripts/load_sample_tables.py data/samples/gghouse_20260130.sql
else
    echo "⚠️  Sample data loader not available or dump file missing"
    echo "   Creating minimal test schema instead..."
    
    mysql -h${DB_HOST} -P${DB_PORT} -u${DB_USER} -p${DB_PASSWORD} staging <<'EOSQL'
-- Minimal test schema for dbt testing
-- This creates basic table structures without data

SET FOREIGN_KEY_CHECKS=0;

-- movings table (simplified)
CREATE TABLE IF NOT EXISTS movings (
    id INT PRIMARY KEY,
    tenant_id INT NOT NULL,
    apartment_id INT NOT NULL,
    room_id INT NOT NULL,
    movein_date DATE,
    moveout_date DATE,
    moveout_plans_date DATE,
    moveout_date_integrated DATE,
    cancel_flag TINYINT DEFAULT 0,
    is_moveout TINYINT DEFAULT 0,
    rent DECIMAL(10,2),
    movein_decided_date DATETIME,
    original_movein_date DATE,
    moving_agreement_type INT,
    tenant_contract_type INT,
    moveout_receipt_date DATE,
    move_renew_flag TINYINT DEFAULT 0,
    rent_start_date DATE,
    expiration_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- tenants table (simplified)
CREATE TABLE IF NOT EXISTS tenants (
    id INT PRIMARY KEY,
    last_name VARCHAR(191),
    first_name VARCHAR(191),
    gender_type TINYINT,
    birth_date DATE,
    age INT,
    nationality VARCHAR(191),
    m_nationality_id INT,
    personal_identity VARCHAR(191),
    affiliation VARCHAR(191),
    media_id INT,
    reason_moveout INT,
    contract_type INT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- apartments table (simplified)
CREATE TABLE IF NOT EXISTS apartments (
    id INT PRIMARY KEY,
    unique_number VARCHAR(191),
    apartment_name VARCHAR(191),
    prefecture VARCHAR(191),
    municipality VARCHAR(191),
    address VARCHAR(191),
    full_address VARCHAR(191),
    latitude DECIMAL(8,6),
    longitude DECIMAL(9,6),
    zip_code VARCHAR(191),
    room_count INT,
    vacancy_room_count INT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- rooms table (simplified)
CREATE TABLE IF NOT EXISTS rooms (
    id INT PRIMARY KEY,
    apartment_id INT NOT NULL,
    room_number VARCHAR(191)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- m_nationalities table (simplified)
CREATE TABLE IF NOT EXISTS m_nationalities (
    id INT PRIMARY KEY,
    nationality_name VARCHAR(191)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS=1;

-- Insert minimal test data
INSERT INTO movings (id, tenant_id, apartment_id, room_id, movein_date, movein_decided_date, moving_agreement_type, rent, cancel_flag, created_at) VALUES
(1, 1, 1, 1, '2024-01-15', '2024-01-10 10:00:00', 1, 50000.00, 0, '2024-01-05 09:00:00'),
(2, 2, 1, 2, '2024-01-20', '2024-01-15 11:00:00', 2, 60000.00, 0, '2024-01-10 10:00:00'),
(3, 3, 2, 1, '2024-02-01', '2024-01-25 12:00:00', 1, 55000.00, 0, '2024-01-20 11:00:00');

INSERT INTO tenants (id, last_name, first_name, gender_type, age, nationality, media_id, personal_identity, affiliation, reason_moveout) VALUES
(1, 'Tanaka', 'Taro', 1, 30, 'Japanese', 1, 'Permanent Resident', 'Company A', NULL),
(2, 'Smith', 'John', 1, 28, 'American', 2, 'Work Visa', 'Company B', NULL),
(3, 'Yamada', 'Hanako', 2, 25, 'Japanese', 1, 'Citizen', 'Student', NULL);

INSERT INTO apartments (id, unique_number, apartment_name, prefecture, municipality, latitude, longitude) VALUES
(1, 'APT001', 'Test Apartment 1', 'Tokyo', 'Shibuya', 35.6580, 139.7016),
(2, 'APT002', 'Test Apartment 2', 'Tokyo', 'Shinjuku', 35.6896, 139.6917);

INSERT INTO rooms (id, apartment_id, room_number) VALUES
(1, 1, '101'),
(2, 1, '102'),
(3, 2, '201');

INSERT INTO m_nationalities (id, nationality_name) VALUES
(1, 'Japanese'),
(2, 'American'),
(3, 'Chinese');

EOSQL

    echo "✅ Minimal test schema created with sample data"
fi

echo ""
echo "✅ Local database setup complete!"
echo ""
echo "Connection details:"
echo "  Host: ${DB_HOST}"
echo "  Port: ${DB_PORT}"
echo "  Database: ${DB_NAME}"
echo "  User: ${DB_USER}"
echo ""
echo "To test dbt models:"
echo "  cd dbt"
echo "  export DBT_TARGET=local"
echo "  dbt run --target local"
echo "  dbt test --target local"
