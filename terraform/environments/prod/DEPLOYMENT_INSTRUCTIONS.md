# Production Deployment Instructions - Phase 1

**Status:** Ready to deploy IAM role and Secrets Manager  
**Risk:** NONE - Does not modify existing EC2 instance or cron jobs  
**Duration:** ~10 seconds

---

## ⚠️ CRITICAL: Before Deploying

You MUST update the RDS credentials in `rds_cron_secret.tf` with your ACTUAL credentials.

### Step 1: Get Your Current RDS Credentials

Your existing cron scripts have the RDS credentials hardcoded. Find them:

```bash
# SSH into EC2
ssh ubuntu@<ec2-ip>

# Look at existing cron script
cat ~/cron_scripts/ggh_datatransit.sh | grep -E "DB_HOST|DB_USER|DB_PASS"

# Example output (your actual values):
# DB_HOST="your-rds-endpoint.rds.amazonaws.com"
# DB_USER="your_username"
# DB_PASS="your_password"
```

### Step 2: Update rds_cron_secret.tf

Edit the file and replace placeholders:

```hcl
secret_string = jsonencode({
  host     = "your-actual-rds-endpoint.rds.amazonaws.com"  # ← Replace
  username = "your_actual_username"                         # ← Replace
  password = "your_actual_password"                         # ← Replace
  database = "gghouse"                                      # Usually correct
  port     = 3306                                           # Usually correct
})
```

**Security Note:** These credentials are encrypted at rest in Secrets Manager and in Terraform state.

---

## Deployment Steps

### 1. Update Credentials (REQUIRED)

```bash
cd /Users/danielkang/tokyobeta-data-consolidation/terraform/environments/prod

# Edit rds_cron_secret.tf
vim rds_cron_secret.tf
# or
code rds_cron_secret.tf
```

### 2. Initialize Terraform

```bash
terraform init
```

### 3. Review Plan

```bash
terraform plan
```

**Expected resources to create:**
- IAM role: `tokyobeta-prod-ec2-cron-role`
- IAM policies: S3 access, Secrets Manager access
- Instance profile: `tokyobeta-prod-ec2-cron-profile`
- Secret: `tokyobeta/prod/rds/cron-credentials`

**Will NOT modify:**
- EC2 instance (no changes)
- Existing cron jobs (untouched)
- Any production workflows (unaffected)

### 4. Deploy

```bash
terraform apply
```

Review output and type `yes` when prompted.

### 5. Verify Deployment

```bash
# Check IAM role
aws iam get-role \
  --role-name tokyobeta-prod-ec2-cron-role \
  --profile gghouse

# Test secret access
aws secretsmanager get-secret-value \
  --secret-id tokyobeta/prod/rds/cron-credentials \
  --region ap-northeast-1 \
  --profile gghouse \
  --query SecretString \
  --output text | jq .
```

---

## What This Deploys (Phase 1)

✅ **Creates:**
- IAM role with least-privilege policies
- Instance profile (ready to attach later)
- RDS credentials in Secrets Manager (encrypted)
- S3 upload permissions
- Secrets Manager read permissions

❌ **Does NOT:**
- Attach IAM role to EC2 (Phase 3)
- Modify existing cron jobs
- Change any production workflows
- Require EC2 restart

---

## After Deployment - Phase 2 Begins

Once deployed, you can start Phase 2: Parallel Testing

See `docs/SECURITY_MIGRATION_PLAN.md` for complete Phase 2 instructions:

1. Copy example scripts to EC2
2. Add test cron jobs (alongside existing ones)
3. Monitor for 7-14 days
4. Compare outputs
5. Validate before cutover

---

## Rollback

If needed, you can remove these resources:

```bash
terraform destroy -target=module.ec2_iam_role \
                  -target=aws_secretsmanager_secret.rds_cron_credentials
```

Your existing cron jobs continue working unchanged.

---

## Cost

**New monthly costs:**
- IAM role & policies: $0 (free)
- Secrets Manager secret: $0.40/month
- **Total:** $0.40/month

**Security benefit:** Priceless (no more hardcoded credentials!)

---

## Troubleshooting

### "Secret already exists"

If you get this error, the secret was created in a previous test:

```bash
# Delete old test secret
aws secretsmanager delete-secret \
  --secret-id tokyobeta/prod/rds/cron-credentials \
  --force-delete-without-recovery \
  --profile gghouse \
  --region ap-northeast-1

# Then retry terraform apply
```

### "InvalidParameter" in secret string

Check JSON formatting in `rds_cron_secret.tf`:
- All values in quotes
- No trailing commas
- Valid JSON structure

### Can't find current RDS credentials

Check your existing cron scripts on EC2:
```bash
grep -r "DB_HOST\|DB_USER\|DB_PASS" ~/cron_scripts/
```

---

## Next Steps After Phase 1

1. ✅ Phase 1 complete: Infrastructure deployed
2. ⏭️ Phase 2: Begin parallel testing (see SECURITY_MIGRATION_PLAN.md)
3. ⏭️ Phase 3: Attach IAM role to EC2 (requires restart)
4. ⏭️ Phase 4: Gradual cutover
5. ⏭️ Phase 5: Cleanup

**Remember:** Old cron jobs keep running unchanged until Phase 4!
