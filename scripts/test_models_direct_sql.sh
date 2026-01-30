#!/bin/bash
# Test dbt model logic using direct SQL queries
# Useful when dbt is not installed

set -euo pipefail

DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3307}"
DB_USER="${DB_USER:-root}"
DB_PASSWORD="${DB_PASSWORD:-localdev}"
DB_NAME="${DB_NAME:-tokyobeta}"

echo "Testing dbt model logic with direct SQL queries..."
echo ""

# Test 1: Daily Activity Summary - Applications
echo "1. Testing Daily Activity Summary - Applications:"
mysql -h${DB_HOST} -P${DB_PORT} -u${DB_USER} -p${DB_PASSWORD} ${DB_NAME} <<'EOSQL'
USE staging;

SELECT 
    DATE(created_at) as activity_date,
    CASE 
        WHEN moving_agreement_type IN (2, 3, 4) THEN 'corporate'
        ELSE 'individual'
    END as tenant_type,
    COUNT(*) as application_count
FROM movings
WHERE created_at IS NOT NULL
  AND created_at >= '2018-01-01'
GROUP BY DATE(created_at), tenant_type
ORDER BY activity_date DESC;
EOSQL

echo ""

# Test 2: Daily Activity Summary - Contracts Signed
echo "2. Testing Daily Activity Summary - Contracts Signed:"
mysql -h${DB_HOST} -P${DB_PORT} -u${DB_USER} -p${DB_PASSWORD} ${DB_NAME} <<'EOSQL'
USE staging;

SELECT 
    DATE(movein_decided_date) as activity_date,
    CASE 
        WHEN moving_agreement_type IN (2, 3, 4) THEN 'corporate'
        ELSE 'individual'
    END as tenant_type,
    COUNT(*) as contract_signed_count
FROM movings
WHERE movein_decided_date IS NOT NULL
  AND cancel_flag = 0
  AND movein_decided_date >= '2018-01-01'
GROUP BY DATE(movein_decided_date), tenant_type
ORDER BY activity_date DESC;
EOSQL

echo ""

# Test 3: New Contracts
echo "3. Testing New Contracts model:"
mysql -h${DB_HOST} -P${DB_PORT} -u${DB_USER} -p${DB_PASSWORD} ${DB_NAME} <<'EOSQL'
USE staging;

SELECT 
    m.id as contract_id,
    a.unique_number as asset_id_hj,
    r.room_number as room_number,
    m.moving_agreement_type as contract_system,
    t.media_id as contract_channel,
    m.original_movein_date as original_contract_date,
    DATE(m.movein_decided_date) as contract_date,
    m.movein_date as contract_start_date,
    m.rent_start_date as rent_start_date,
    m.expiration_date as contract_expiration_date,
    CASE WHEN m.move_renew_flag = 1 THEN 'Yes' ELSE 'No' END as renewal_flag,
    m.rent as monthly_rent,
    CASE 
        WHEN m.moving_agreement_type IN (2, 3, 4) THEN 'corporate'
        ELSE 'individual'
    END as tenant_type,
    CASE 
        WHEN t.gender_type = 1 THEN 'Male'
        WHEN t.gender_type = 2 THEN 'Female'
        ELSE 'Other'
    END as gender,
    COALESCE(t.age, TIMESTAMPDIFF(YEAR, t.birth_date, CURRENT_DATE)) as age,
    COALESCE(t.nationality, n.nationality_name) as nationality,
    CASE 
        WHEN t.affiliation IN ('NULL', '--', 'null', '') THEN NULL
        ELSE t.affiliation
    END as occupation_company,
    CASE 
        WHEN t.personal_identity IN ('NULL', '--', 'null', '') THEN NULL
        ELSE t.personal_identity
    END as residence_status,
    a.latitude,
    a.longitude
FROM movings m
INNER JOIN tenants t ON m.tenant_id = t.id
INNER JOIN apartments a ON m.apartment_id = a.id
INNER JOIN rooms r ON m.room_id = r.id
LEFT JOIN m_nationalities n ON t.m_nationality_id = n.id
WHERE m.movein_decided_date IS NOT NULL
  AND m.cancel_flag = 0
  AND DATE(m.movein_decided_date) >= '2018-01-01'
  AND a.latitude IS NOT NULL
  AND a.longitude IS NOT NULL
ORDER BY contract_date DESC
LIMIT 5;
EOSQL

echo ""

# Test 4: Moveouts
echo "4. Testing Moveouts model:"
mysql -h${DB_HOST} -P${DB_PORT} -u${DB_USER} -p${DB_PASSWORD} ${DB_NAME} <<'EOSQL'
USE staging;

SELECT 
    m.id as contract_id,
    a.unique_number as asset_id_hj,
    r.room_number as room_number,
    m.moveout_receipt_date as cancellation_notice_date,
    DATE(COALESCE(m.moveout_date_integrated, m.moveout_plans_date, m.moveout_date)) as moveout_date,
    CASE 
        WHEN m.moving_agreement_type IN (2, 3, 4) THEN 'corporate'
        ELSE 'individual'
    END as tenant_type,
    m.rent as monthly_rent,
    a.latitude,
    a.longitude
FROM movings m
INNER JOIN tenants t ON m.tenant_id = t.id
INNER JOIN apartments a ON m.apartment_id = a.id
INNER JOIN rooms r ON m.room_id = r.id
WHERE COALESCE(m.moveout_date_integrated, m.moveout_plans_date, m.moveout_date) IS NOT NULL
  AND m.is_moveout = 1
  AND DATE(COALESCE(m.moveout_date_integrated, m.moveout_plans_date, m.moveout_date)) >= '2018-01-01'
  AND a.latitude IS NOT NULL
  AND a.longitude IS NOT NULL
ORDER BY moveout_date DESC
LIMIT 5;
EOSQL

echo ""
echo "✅ All SQL queries executed successfully!"
echo ""
echo "These queries test the core logic of the dbt models."
echo "To run the actual dbt models, install dbt:"
echo "  pip install dbt-mysql"
echo "Then run: ./scripts/test_dbt_local.sh"
