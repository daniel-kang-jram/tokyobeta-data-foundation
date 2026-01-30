# Testing Guide: Validating New Secure Cron Scripts

## Purpose
This guide helps you verify that the new Secrets Manager-based scripts produce **identical results** to your existing cron jobs before cutover.

## Prerequisites

- [ ] IAM role created but NOT attached to EC2 yet
- [ ] Secrets Manager secret created with current RDS credentials
- [ ] Example scripts copied to EC2 in separate directory
- [ ] Old cron jobs still running unchanged

## Test Environment Setup

### 1. Prepare Directories on EC2

```bash
# SSH into EC2 instance
ssh ubuntu@<ec2-ip>

# Keep existing scripts intact
ls -la ~/cron_scripts/  # Your current production scripts

# Create new directory for test scripts
mkdir -p ~/cron_scripts_new
mkdir -p ~/logs_new

# Copy example scripts
# (Upload from local machine first)
```

### 2. Modify Example Scripts for Testing

Edit the new scripts to use test S3 prefix:

```bash
cd ~/cron_scripts_new
vim ggh_datatransit.sh

# Change S3_PREFIX from "dumps" to "dumps-test"
S3_PREFIX="dumps-test"  # <-- ADD -test suffix

# Change LOG_FILE to separate location
LOG_FILE="/home/ubuntu/logs_new/ggh_datatransit.log"
```

### 3. Install Dependencies

```bash
# Check if jq is installed (required for JSON parsing)
which jq || sudo apt-get install -y jq

# Verify AWS CLI version (v2 recommended)
aws --version

# Test IAM role access (if Phase 3 completed)
aws sts get-caller-identity

# If no IAM role yet, ensure ~/.aws/credentials exists
cat ~/.aws/credentials  # Should show current keys
```

## Test 1: Secrets Manager Access

**Goal:** Verify new scripts can fetch RDS credentials

```bash
# Test fetching secret
aws secretsmanager get-secret-value \
  --secret-id tokyobeta/prod/rds/cron-credentials \
  --region ap-northeast-1 \
  --query SecretString \
  --output text

# Expected output: JSON with host, username, password, database
```

**If this fails:**
- Check IAM role has `secretsmanager:GetSecretValue` permission
- Verify secret name matches exactly
- Ensure EC2 is in same region as secret

## Test 2: Database Connectivity

**Goal:** Verify new scripts can connect to RDS using Secrets Manager credentials

```bash
cd ~/cron_scripts_new

# Run this test script
cat > test_db_connection.sh << 'EOF'
#!/bin/bash
SECRET_JSON=$(aws secretsmanager get-secret-value \
  --secret-id tokyobeta/prod/rds/cron-credentials \
  --region ap-northeast-1 \
  --query SecretString --output text)

DB_HOST=$(echo "$SECRET_JSON" | jq -r '.host')
DB_USER=$(echo "$SECRET_JSON" | jq -r '.username')
DB_PASS=$(echo "$SECRET_JSON" | jq -r '.password')
DB_NAME=$(echo "$SECRET_JSON" | jq -r '.database')
DB_PORT=$(echo "$SECRET_JSON" | jq -r '.port')

echo "Testing connection to: $DB_HOST:$DB_PORT"

mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" \
  -e "SELECT 'Connection successful!' AS status, NOW() AS timestamp;" "$DB_NAME"

if [[ $? -eq 0 ]]; then
  echo "✅ Database connection successful"
else
  echo "❌ Database connection failed"
fi

unset DB_HOST DB_USER DB_PASS DB_NAME DB_PORT SECRET_JSON
EOF

chmod +x test_db_connection.sh
./test_db_connection.sh
```

**Expected output:**
```
Testing connection to: rds-xxx.ap-northeast-1.rds.amazonaws.com:3306
Connection successful!
✅ Database connection successful
```

## Test 3: Parallel Dump Comparison

**Goal:** Run both old and new scripts, compare outputs byte-by-byte

### Step 3.1: Manual Test Run

```bash
# Run old script manually (with timestamp)
OLD_START=$(date +%s)
/home/ubuntu/cron_scripts/ggh_datatransit.sh
OLD_END=$(date +%s)
OLD_DURATION=$((OLD_END - OLD_START))
echo "Old script duration: ${OLD_DURATION}s"

# Run new script manually (with timestamp)
NEW_START=$(date +%s)
/home/ubuntu/cron_scripts_new/ggh_datatransit.sh
NEW_END=$(date +%s)
NEW_DURATION=$((NEW_END - NEW_START))
echo "New script duration: ${NEW_DURATION}s"
```

### Step 3.2: Compare S3 Uploads

```bash
# List files from both methods
TIMESTAMP=$(date +%Y%m%d)

aws s3 ls s3://jram-gghouse/dumps/gghouse_${TIMESTAMP}.sql.gz --human-readable
aws s3 ls s3://jram-gghouse/dumps-test/gghouse_${TIMESTAMP}.sql.gz --human-readable

# Expected: Similar file sizes (within 1-2% due to timestamps)
```

### Step 3.3: Content Comparison

```bash
# Download both dumps
mkdir -p /tmp/dump_comparison
cd /tmp/dump_comparison

aws s3 cp s3://jram-gghouse/dumps/gghouse_${TIMESTAMP}.sql.gz old.sql.gz
aws s3 cp s3://jram-gghouse/dumps-test/gghouse_${TIMESTAMP}.sql.gz new.sql.gz

# Decompress
gunzip old.sql.gz new.sql.gz

# Compare file sizes
ls -lh old.sql new.sql

# Calculate checksums (will differ due to timestamps in SQL comments)
md5sum old.sql new.sql

# Intelligent comparison (ignore timestamp comments)
# Extract just the schema and data, ignore dump metadata
grep -v "^-- Dump completed on" old.sql | \
grep -v "^-- MySQL dump" | \
grep -v "^-- Host:" | \
grep -v "^-- Server version" > old_normalized.sql

grep -v "^-- Dump completed on" new.sql | \
grep -v "^-- MySQL dump" | \
grep -v "^-- Host:" | \
grep -v "^-- Server version" > new_normalized.sql

# Compare normalized versions
diff old_normalized.sql new_normalized.sql

# Expected: Empty output (no differences) or minimal differences
```

**If differences found:**
- Check if it's only comments/timestamps → ACCEPTABLE
- Check if actual data differs → INVESTIGATE (likely script bug)
- Compare table counts, row counts

### Step 3.4: Detailed Analysis

```bash
# Count tables in each dump
grep -c "^CREATE TABLE" old_normalized.sql
grep -c "^CREATE TABLE" new_normalized.sql
# Should match: 81 tables

# Compare specific table (e.g., contracts)
awk '/CREATE TABLE `contracts`/,/CREATE TABLE/' old_normalized.sql > old_contracts.sql
awk '/CREATE TABLE `contracts`/,/CREATE TABLE/' new_normalized.sql > new_contracts.sql
diff old_contracts.sql new_contracts.sql
# Should be identical

# Row count comparison (spot check)
grep "INSERT INTO \`contracts\`" old_normalized.sql | wc -l
grep "INSERT INTO \`contracts\`" new_normalized.sql | wc -l
# Should match
```

## Test 4: Automated Parallel Testing

**Goal:** Run both scripts via cron for 7 days, automatically compare

### Step 4.1: Add Test Cron Jobs

```bash
crontab -e

# Add these lines (keep existing crons unchanged)
# OLD (existing) - DO NOT MODIFY
30 5 * * * /home/ubuntu/cron_scripts/ggh_datatransit.sh

# NEW (testing) - 10 minute offset
40 5 * * * /home/ubuntu/cron_scripts_new/ggh_datatransit.sh
```

### Step 4.2: Create Automated Comparison Script

```bash
cat > ~/compare_dumps.sh << 'EOF'
#!/bin/bash
# Automated comparison of old vs new dumps

DATE=$(date +%Y%m%d)
REPORT_FILE="/home/ubuntu/logs_new/comparison_${DATE}.txt"

echo "=== Dump Comparison Report: $(date) ===" > "$REPORT_FILE"

# Check both files exist
OLD_FILE="s3://jram-gghouse/dumps/gghouse_${DATE}.sql.gz"
NEW_FILE="s3://jram-gghouse/dumps-test/gghouse_${DATE}.sql.gz"

OLD_SIZE=$(aws s3 ls "$OLD_FILE" 2>/dev/null | awk '{print $3}')
NEW_SIZE=$(aws s3 ls "$NEW_FILE" 2>/dev/null | awk '{print $3}')

if [[ -z "$OLD_SIZE" ]]; then
  echo "❌ OLD file missing: $OLD_FILE" >> "$REPORT_FILE"
  exit 1
fi

if [[ -z "$NEW_SIZE" ]]; then
  echo "❌ NEW file missing: $NEW_FILE" >> "$REPORT_FILE"
  exit 1
fi

echo "✅ Both files exist" >> "$REPORT_FILE"
echo "Old size: $OLD_SIZE bytes" >> "$REPORT_FILE"
echo "New size: $NEW_SIZE bytes" >> "$REPORT_FILE"

# Calculate size difference percentage
DIFF=$(echo "scale=2; (($NEW_SIZE - $OLD_SIZE) / $OLD_SIZE) * 100" | bc)
echo "Size difference: ${DIFF}%" >> "$REPORT_FILE"

# Alert if size difference > 5%
if (( $(echo "$DIFF > 5 || $DIFF < -5" | bc -l) )); then
  echo "⚠️  WARNING: Size difference exceeds 5%" >> "$REPORT_FILE"
else
  echo "✅ Size difference acceptable (<5%)" >> "$REPORT_FILE"
fi

# Upload report to S3
aws s3 cp "$REPORT_FILE" "s3://jram-gghouse/dump-comparisons/comparison_${DATE}.txt"

cat "$REPORT_FILE"  # Print to stdout for cron email
EOF

chmod +x ~/compare_dumps.sh

# Add to crontab (run after both dumps complete)
# 0 6 * * * /home/ubuntu/compare_dumps.sh
```

## Test 5: Glue ETL Compatibility

**Goal:** Verify Glue can process dumps from new scripts

```bash
# Temporarily point Glue to test dumps
aws glue start-job-run \
  --job-name tokyobeta-prod-daily-etl \
  --arguments '{
    "--S3_SOURCE_BUCKET":"jram-gghouse",
    "--S3_SOURCE_PREFIX":"dumps-test",
    "--DB_SECRET_ARN":"tokyobeta/prod/aurora/credentials"
  }'

# Monitor job
aws glue get-job-run \
  --job-name tokyobeta-prod-daily-etl \
  --run-id <run-id-from-above>

# Check CloudWatch Logs for errors
```

## Success Criteria

Mark Phase 2 successful if ALL conditions met:

- [ ] ✅ Secrets Manager access works (Test 1)
- [ ] ✅ Database connection works (Test 2)
- [ ] ✅ Dumps uploaded to S3 successfully (Test 3.2)
- [ ] ✅ Dump size within 5% of old method (Test 3.2)
- [ ] ✅ Content differences only in timestamps (Test 3.3)
- [ ] ✅ Table count matches: 81 tables (Test 3.4)
- [ ] ✅ Automated parallel testing runs for 7+ days without errors (Test 4)
- [ ] ✅ Glue ETL processes new dumps successfully (Test 5)
- [ ] ✅ No manual intervention required
- [ ] ✅ Log files show clean execution (no errors)

## Failure Analysis

If any test fails:

### Test 1 Failure (Secrets Manager)
**Symptom:** Cannot fetch secret  
**Likely cause:** IAM permissions  
**Fix:** Check IAM role policy, verify secret exists

### Test 2 Failure (Database Connection)
**Symptom:** mysql command fails  
**Likely causes:**
- Wrong credentials in Secrets Manager
- Security group blocking EC2 → RDS
- RDS in different VPC
**Fix:** Verify secret contents match working credentials

### Test 3 Failure (Dump Differences)
**Symptom:** Files significantly different sizes or content  
**Likely causes:**
- Scripts running at different times (data changed between runs)
- mysqldump parameters differ
- Database user has different privileges
**Fix:** Run both scripts within 1 minute of each other, compare mysqldump flags

### Test 4 Failure (Cron Execution)
**Symptom:** New cron doesn't run  
**Likely causes:**
- Path issues in cron environment
- Missing execute permissions
- Environment variables not set in cron
**Fix:** Use absolute paths, add `source ~/.bashrc` to script, check cron logs

## Rollback Triggers

Immediately rollback (disable new crons, keep old ones) if:

- ❌ 3 consecutive failures of new script
- ❌ Dump size differs by >10% from old method
- ❌ Glue ETL fails to process new dumps
- ❌ Data integrity issues detected downstream
- ❌ Any production alert triggered related to data pipeline

## Next Steps After Successful Testing

Once all tests pass for 7+ days:

1. Schedule Phase 3 (IAM role attachment) during maintenance window
2. Notify stakeholders of brief EC2 restart
3. Follow Phase 3 and 4 procedures in main README
4. Monitor closely for first 48 hours after cutover

---

**Testing is not optional. Take your time with each phase. Production stability is more important than migration speed.**
