# Testing Guide - Validate New Secure Implementation

**Goal:** Test the new secure infrastructure before deploying to production

## What We Can Test Now

### ✅ Level 1: Local Validation (No AWS Required)
- Terraform syntax and validation
- Script syntax checking
- Configuration validation

### ✅ Level 2: AWS Infrastructure (Requires AWS Access)
- Deploy test infrastructure
- Verify IAM permissions
- Test Secrets Manager access

### ✅ Level 3: EC2 Integration (Requires EC2 Access)
- Test scripts on actual EC2 instance
- Verify database connectivity
- Compare outputs with existing crons

---

## Level 1: Local Validation (START HERE)

### Test 1: Terraform Validation

```bash
# Navigate to project root
cd /Users/danielkang/tokyobeta-data-consolidation

# Validate all new Terraform modules
echo "Testing: terraform/modules/ec2_iam_role/"
cd terraform/modules/ec2_iam_role
terraform init
terraform validate

echo "Testing: terraform/modules/ec2_management/"
cd ../ec2_management
terraform init
terraform validate

echo "Testing: terraform/modules/secrets/"
cd ../secrets
terraform init
terraform validate

echo "Testing: terraform/modules/quicksight/"
cd ../quicksight
terraform init
terraform validate

echo "✅ All Terraform modules validated"
```

### Test 2: Script Syntax Checking

```bash
cd /Users/danielkang/tokyobeta-data-consolidation

# Check bash script syntax
echo "Testing: ggh_datatransit.sh"
bash -n scripts/example_cron_scripts/ggh_datatransit.sh
if [ $? -eq 0 ]; then
    echo "✅ ggh_datatransit.sh syntax OK"
else
    echo "❌ ggh_datatransit.sh has syntax errors"
fi

echo "Testing: ggh_contractstatus.sh"
bash -n scripts/example_cron_scripts/ggh_contractstatus.sh
if [ $? -eq 0 ]; then
    echo "✅ ggh_contractstatus.sh syntax OK"
else
    echo "❌ ggh_contractstatus.sh has syntax errors"
fi

# Check Python script syntax
echo "Testing: deploy_dashboards.py"
python3 -m py_compile scripts/quicksight/deploy_dashboards.py
if [ $? -eq 0 ]; then
    echo "✅ deploy_dashboards.py syntax OK"
else
    echo "❌ deploy_dashboards.py has syntax errors"
fi

echo "Testing: spice_refresh.py"
python3 -m py_compile terraform/modules/quicksight/lambda/spice_refresh.py
if [ $? -eq 0 ]; then
    echo "✅ spice_refresh.py syntax OK"
else
    echo "❌ spice_refresh.py has syntax errors"
fi
```

### Test 3: Check Script Dependencies

```bash
# Check if required commands exist
echo "Checking dependencies..."

# For bash scripts
command -v aws >/dev/null 2>&1 && echo "✅ AWS CLI installed" || echo "❌ AWS CLI missing"
command -v jq >/dev/null 2>&1 && echo "✅ jq installed" || echo "❌ jq missing (required for scripts)"
command -v mysql >/dev/null 2>&1 && echo "✅ MySQL client installed" || echo "⚠️  MySQL client not found (needed on EC2)"
command -v mysqldump >/dev/null 2>&1 && echo "✅ mysqldump installed" || echo "⚠️  mysqldump not found (needed on EC2)"

# For Python scripts
python3 -c "import boto3" 2>/dev/null && echo "✅ boto3 installed" || echo "❌ boto3 missing (install: pip install boto3)"
python3 -c "import json" 2>/dev/null && echo "✅ json module available" || echo "❌ json missing"
```

---

## Level 2: AWS Infrastructure Testing

### Prerequisites

```bash
# 1. Ensure AWS credentials are configured
aws sts get-caller-identity --profile gghouse

# Expected output:
# {
#     "UserId": "...",
#     "Account": "343881458651",
#     "Arn": "arn:aws:iam::343881458651:user/..."
# }

# 2. Check current region
aws configure get region --profile gghouse
# Should be: ap-northeast-1
```

### Test 4: Terraform Plan (Dry Run)

```bash
cd /Users/danielkang/tokyobeta-data-consolidation/terraform/environments/prod

# Initialize Terraform
terraform init

# Create a plan (doesn't deploy, just shows what would happen)
terraform plan -out=test.tfplan

# Review the plan
terraform show test.tfplan

# Check what will be created:
# - IAM role: tokyobeta-prod-ec2-cron-role
# - IAM policies: S3 access, Secrets Manager access
# - Instance profile: tokyobeta-prod-ec2-cron-profile
# - Secrets Manager secret: tokyobeta/prod/rds/cron-credentials
# - QuickSight resources (if enabled)
```

**⚠️ Do NOT run `terraform apply` yet unless you're ready to deploy!**

### Test 5: IAM Policy Validation

```bash
# Validate IAM policies are correctly formatted
cd /Users/danielkang/tokyobeta-data-consolidation

# Check ec2_iam_role module policies
grep -A 50 "aws_iam_policy" terraform/modules/ec2_iam_role/main.tf

# Verify:
# ✅ S3 bucket name is correct: jram-gghouse
# ✅ Actions are least privilege (ListBucket, PutObject, GetObject)
# ✅ Secrets Manager ARN will be correct after deployment
```

### Test 6: Deploy Test Infrastructure (OPTIONAL - Safe to Deploy)

**This is safe because:**
- Only creates IAM role and Secrets Manager secret
- Doesn't modify existing EC2 instance
- Doesn't touch existing cron jobs
- Can be easily deleted with `terraform destroy`

```bash
cd /Users/danielkang/tokyobeta-data-consolidation/terraform/environments/prod

# Before deploying, review these variables in terraform.tfvars:
cat terraform.tfvars

# Deploy ONLY the infrastructure (no EC2 changes yet)
terraform apply -target=module.secrets -target=module.ec2_iam_role

# After deployment, verify:
aws iam get-role --role-name tokyobeta-prod-ec2-cron-role --profile gghouse
aws secretsmanager describe-secret --secret-id tokyobeta/prod/rds/cron-credentials --region ap-northeast-1 --profile gghouse
```

### Test 7: Store Test Credentials in Secrets Manager

```bash
# Store your CURRENT RDS credentials (the ones in your existing cron scripts)
aws secretsmanager put-secret-value \
  --secret-id tokyobeta/prod/rds/cron-credentials \
  --region ap-northeast-1 \
  --profile gghouse \
  --secret-string '{
    "host": "YOUR-RDS-ENDPOINT.rds.amazonaws.com",
    "username": "YOUR-CURRENT-USERNAME",
    "password": "YOUR-CURRENT-PASSWORD",
    "database": "gghouse",
    "port": 3306
  }'

# Verify it was stored correctly
aws secretsmanager get-secret-value \
  --secret-id tokyobeta/prod/rds/cron-credentials \
  --region ap-northeast-1 \
  --profile gghouse \
  --query SecretString \
  --output text | jq .

# Expected output: Your credentials in JSON format
```

---

## Level 3: EC2 Integration Testing

### Test 8: Test IAM Role on EC2 (Without Attaching Yet)

**Method 1: Using AWS CLI assume-role (simulate EC2 instance profile)**

```bash
# Get the IAM role ARN
ROLE_ARN=$(aws iam get-role \
  --role-name tokyobeta-prod-ec2-cron-role \
  --profile gghouse \
  --query 'Role.Arn' \
  --output text)

echo "Role ARN: $ROLE_ARN"

# Note: You can't actually assume an EC2 instance role from CLI
# But we can verify the policies are correct

# Check S3 access policy
aws iam list-role-policies --role-name tokyobeta-prod-ec2-cron-role --profile gghouse
aws iam list-attached-role-policies --role-name tokyobeta-prod-ec2-cron-role --profile gghouse
```

### Test 9: Copy Scripts to EC2 and Test (Without Changing Cron)

```bash
# SSH into EC2 instance
ssh ubuntu@<ec2-ip-address>

# On EC2: Create test directory
mkdir -p ~/cron_scripts_test
cd ~/cron_scripts_test

# Exit SSH and copy scripts from your local machine
scp /Users/danielkang/tokyobeta-data-consolidation/scripts/example_cron_scripts/ggh_datatransit.sh ubuntu@<ec2-ip>:~/cron_scripts_test/
scp /Users/danielkang/tokyobeta-data-consolidation/scripts/example_cron_scripts/ggh_contractstatus.sh ubuntu@<ec2-ip>:~/cron_scripts_test/

# SSH back in
ssh ubuntu@<ec2-ip>

# Make scripts executable
chmod +x ~/cron_scripts_test/*.sh

# IMPORTANT: Modify scripts to use test S3 prefix
cd ~/cron_scripts_test
sed -i 's/S3_PREFIX="dumps"/S3_PREFIX="dumps-test"/' ggh_datatransit.sh
sed -i 's/S3_PREFIX="contractstatus"/S3_PREFIX="contractstatus-test"/' ggh_contractstatus.sh

# Test if scripts can access Secrets Manager (using existing AWS credentials for now)
aws secretsmanager get-secret-value \
  --secret-id tokyobeta/prod/rds/cron-credentials \
  --region ap-northeast-1

# If that works, test the database connection extraction
SECRET_JSON=$(aws secretsmanager get-secret-value \
  --secret-id tokyobeta/prod/rds/cron-credentials \
  --region ap-northeast-1 \
  --query SecretString \
  --output text)

echo "$SECRET_JSON" | jq .

# Test database connectivity
DB_HOST=$(echo "$SECRET_JSON" | jq -r '.host')
DB_USER=$(echo "$SECRET_JSON" | jq -r '.username')
DB_PASS=$(echo "$SECRET_JSON" | jq -r '.password')
DB_NAME=$(echo "$SECRET_JSON" | jq -r '.database')

mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" -e "SELECT 'Connection successful!' AS status, NOW() AS timestamp;" "$DB_NAME"

# If connection works, test a small dump (just one table)
mysqldump -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" \
  --single-transaction "$DB_NAME" apartments | head -50

# SUCCESS? The new method can connect to the database!
```

### Test 10: Dry Run of New Script (No S3 Upload)

```bash
# On EC2: Modify script to skip S3 upload for testing
cd ~/cron_scripts_test
cp ggh_datatransit.sh ggh_datatransit_dryrun.sh

# Edit the dry run version to comment out S3 upload
vim ggh_datatransit_dryrun.sh
# Comment out the "aws s3 cp" line (add # at the beginning)

# Run the dry run
./ggh_datatransit_dryrun.sh

# Check the log
tail -50 /var/log/ggh_datatransit.log

# Verify:
# ✅ Secrets Manager access worked
# ✅ Database connection successful
# ✅ mysqldump executed
# ✅ Compression worked
# ✅ File created in /tmp/mysql_dumps/

# Check the dump file size
ls -lh /tmp/mysql_dumps/gghouse_*.sql.gz

# Compare with your existing dumps
aws s3 ls s3://jram-gghouse/dumps/ --human-readable | tail -5
```

---

## Quick Test Checklist

Run these commands to test everything at once:

```bash
#!/bin/bash
# Quick validation script

echo "=== TESTING NEW SECURE INFRASTRUCTURE ==="
echo ""

cd /Users/danielkang/tokyobeta-data-consolidation

echo "1. Testing bash script syntax..."
bash -n scripts/example_cron_scripts/ggh_datatransit.sh && echo "✅" || echo "❌"
bash -n scripts/example_cron_scripts/ggh_contractstatus.sh && echo "✅" || echo "❌"

echo ""
echo "2. Testing Python script syntax..."
python3 -m py_compile scripts/quicksight/deploy_dashboards.py && echo "✅" || echo "❌"

echo ""
echo "3. Checking dependencies..."
command -v aws >/dev/null 2>&1 && echo "✅ AWS CLI" || echo "❌ AWS CLI"
command -v jq >/dev/null 2>&1 && echo "✅ jq" || echo "❌ jq"
python3 -c "import boto3" 2>/dev/null && echo "✅ boto3" || echo "❌ boto3"

echo ""
echo "4. Testing AWS credentials..."
aws sts get-caller-identity --profile gghouse >/dev/null 2>&1 && echo "✅ AWS access" || echo "❌ AWS access"

echo ""
echo "5. Checking Terraform modules..."
cd terraform/modules/ec2_iam_role && terraform init >/dev/null 2>&1 && terraform validate >/dev/null 2>&1 && echo "✅ ec2_iam_role" || echo "❌ ec2_iam_role"
cd ../secrets && terraform init >/dev/null 2>&1 && terraform validate >/dev/null 2>&1 && echo "✅ secrets" || echo "❌ secrets"

echo ""
echo "=== TEST COMPLETE ==="
```

---

## What to Test When

### Now (No AWS changes)
- [x] Terraform syntax validation
- [x] Script syntax checking
- [x] Dependency checking

### After AWS login (Safe, no production impact)
- [ ] Terraform plan review
- [ ] Deploy test infrastructure (IAM + Secrets Manager only)
- [ ] Store credentials in Secrets Manager
- [ ] Verify IAM policies

### With EC2 access (Still safe, no cron changes)
- [ ] Copy scripts to EC2 test directory
- [ ] Test database connectivity
- [ ] Dry run dump creation
- [ ] Test S3 upload to test prefix

### During Phase 2 (Parallel testing)
- [ ] Add test cron jobs (alongside existing ones)
- [ ] Monitor for 7-14 days
- [ ] Compare outputs
- [ ] Validate Glue ETL compatibility

---

## Troubleshooting Common Issues

### "jq: command not found"
```bash
# On macOS
brew install jq

# On EC2 Ubuntu
sudo apt-get update && sudo apt-get install -y jq
```

### "boto3 module not found"
```bash
pip3 install boto3
```

### "AccessDeniedException" from Secrets Manager
```bash
# Check IAM permissions
aws iam get-role-policy --role-name tokyobeta-prod-ec2-cron-role --policy-name secrets-manager-access --profile gghouse

# Verify secret exists
aws secretsmanager list-secrets --region ap-northeast-1 --profile gghouse
```

### "Connection refused" from MySQL
```bash
# Check security group allows EC2 → RDS on port 3306
# Verify RDS endpoint is correct
# Check RDS is in same VPC or VPC peering configured
```

---

## Next Steps After Successful Tests

1. ✅ All local tests pass → Proceed to AWS infrastructure deployment
2. ✅ Infrastructure deployed → Copy scripts to EC2 and test
3. ✅ EC2 tests pass → Begin Phase 2 parallel testing
4. ✅ Parallel testing successful (7-14 days) → Schedule Phase 3 (IAM role attachment)
5. ✅ IAM role attached → Gradual cutover (Phase 4)

**Remember:** You can test everything without affecting your production cron jobs!
