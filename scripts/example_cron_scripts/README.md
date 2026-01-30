# Example Cron Scripts - Secrets Manager Migration

## ⚠️ IMPORTANT: These are EXAMPLE scripts, NOT production-ready replacements

**DO NOT immediately replace your existing cron jobs with these scripts!**

These scripts demonstrate how to use AWS Secrets Manager and IAM roles instead of hardcoded credentials. They must be thoroughly tested in parallel with your existing cron jobs before any cutover.

## Current Production Cron Jobs (DO NOT MODIFY YET)

Your existing cron jobs on EC2 instance `i-00523f387117d497b` are:

```bash
# ubuntu user crontab (KEEP THESE RUNNING)
30 5 * * * /path/to/original/ggh_datatransit.sh          # Full dump
 1 6 * * * /path/to/original/ggh_contractstatus.sh       # Contract status
 5 6 * * * /path/to/original/ggh_contractstatusALL.sh    # All contracts
10 6 * * * /path/to/original/TenantsALL.sh               # Tenants
12 6 * * * /path/to/original/MovingsALL.sh               # Movings
```

**These use:**
- Static AWS credentials in `~/.aws/credentials` → S3 uploads
- Hardcoded RDS username/password in scripts → Database access

## Safe Migration Strategy (4-Phase Approach)

### Phase 1: Infrastructure Setup (NO IMPACT on existing crons)

**Goal:** Deploy IAM role and Secrets Manager without touching existing cron jobs

**Steps:**
1. Deploy Terraform modules (IAM role, Secrets Manager)
2. Store current RDS credentials in Secrets Manager
3. **DO NOT attach IAM role to EC2 yet** (would require restart)
4. **DO NOT modify existing cron scripts**

**Validation:**
```bash
# On your local machine (not EC2)
aws secretsmanager get-secret-value \
  --secret-id tokyobeta/prod/rds/cron-credentials \
  --region ap-northeast-1

# Should return your current RDS credentials
```

### Phase 2: Parallel Testing (BOTH systems running)

**Goal:** Run new secure scripts alongside old ones, compare outputs

**Steps:**
1. Copy example scripts to EC2: `/home/ubuntu/cron_scripts_new/`
2. Keep originals in: `/home/ubuntu/cron_scripts/` (unchanged)
3. Add NEW cron jobs with different schedule (offset by 10 minutes)
4. Configure new scripts to upload to different S3 prefix for comparison

**New Crontab (ADDED, not replaced):**
```bash
# EXISTING CRONS (keep as-is)
30 5 * * * /home/ubuntu/cron_scripts/ggh_datatransit.sh

# NEW TEST CRONS (parallel validation)
40 5 * * * /home/ubuntu/cron_scripts_new/ggh_datatransit.sh  # 10 min offset
```

**New scripts upload to:** `s3://jram-gghouse/dumps-test/` (different prefix)

**Validation:**
```bash
# Compare dumps from both methods
aws s3 ls s3://jram-gghouse/dumps/gghouse_20260131.sql.gz
aws s3 ls s3://jram-gghouse/dumps-test/gghouse_20260131.sql.gz

# Download and compare (should be identical)
aws s3 cp s3://jram-gghouse/dumps/gghouse_20260131.sql.gz old.sql.gz
aws s3 cp s3://jram-gghouse/dumps-test/gghouse_20260131.sql.gz new.sql.gz

gunzip old.sql.gz new.sql.gz
diff old.sql new.sql  # Should show no differences (or only timestamp)
```

### Phase 3: Attach IAM Role (REQUIRES EC2 RESTART)

**Goal:** Remove dependency on `~/.aws/credentials` for S3 access

**⚠️ DOWNTIME WINDOW REQUIRED** (coordinate with stakeholders)

**Prerequisites:**
- [ ] Phase 2 validation successful (outputs match)
- [ ] Backup window scheduled (no critical operations)
- [ ] Stakeholders notified (brief cron job interruption)
- [ ] Rollback plan ready (detach IAM profile if issues)

**Steps:**
```bash
# 1. Stop EC2 instance
aws ec2 stop-instances --instance-ids i-00523f387117d497b
aws ec2 wait instance-stopped --instance-ids i-00523f387117d497b

# 2. Attach IAM instance profile
aws ec2 associate-iam-instance-profile \
  --instance-id i-00523f387117d497b \
  --iam-instance-profile Name=tokyobeta-prod-ec2-cron-profile

# 3. Start EC2 instance
aws ec2 start-instances --instance-ids i-00523f387117d497b
aws ec2 wait instance-running --instance-ids i-00523f387117d497b

# 4. SSH in and verify IAM role works
ssh ubuntu@<instance-ip>
aws sts get-caller-identity  # Should work WITHOUT ~/.aws/credentials
aws s3 ls s3://jram-gghouse/  # Should work
aws secretsmanager get-secret-value --secret-id tokyobeta/prod/rds/cron-credentials
```

**At this point:**
- ✅ Both old and new scripts can access S3 via IAM role
- ✅ Secrets Manager accessible via IAM role
- ⚠️ Old scripts still have hardcoded DB credentials (insecure but working)
- ⚠️ New scripts use Secrets Manager for DB credentials

### Phase 4: Gradual Cutover (ONE cron job at a time)

**Goal:** Replace old crons with new ones, one at a time with validation

**Approach:** Start with lowest-risk cron job first

**Week 1: Contract Status Query (lowest risk)**
```bash
# Disable old cron, enable new one at same time
# Edit crontab
1 6 * * * /home/ubuntu/cron_scripts_new/ggh_contractstatus.sh
# Comment out: # 1 6 * * * /home/ubuntu/cron_scripts/ggh_contractstatus.sh
```

**Validation after 3 days:**
- Check CloudWatch Logs for errors
- Verify S3 uploads successful
- Compare file sizes with historical data
- Check downstream consumers (Glue ETL) still work

**Week 2: Full Database Dump (highest risk)**
```bash
# Only after Week 1 is successful
30 5 * * * /home/ubuntu/cron_scripts_new/ggh_datatransit.sh
# Comment out: # 30 5 * * * /home/ubuntu/cron_scripts/ggh_datatransit.sh
```

**Week 3-4: Remaining cron jobs**
- Repeat for each remaining cron job
- Validate each for 2-3 days before next cutover

## Key Differences Between Old and New Scripts

### Authentication Changes

| Aspect | Old Method | New Method |
|--------|-----------|------------|
| **S3 Access** | Static AWS keys in `~/.aws/credentials` | IAM instance role |
| **RDS Access** | Hardcoded in scripts: `DB_USER="admin"` | Fetched from Secrets Manager |
| **Security** | ❌ Credentials in plaintext | ✅ No credentials in files |
| **Rotation** | ❌ Manual, requires script edits | ✅ Rotate in Secrets Manager only |

### Script Modifications Required

**Old script example:**
```bash
#!/bin/bash
DB_HOST="rds-instance.abc123.ap-northeast-1.rds.amazonaws.com"
DB_USER="gghouse_user"
DB_PASS="hardcoded_password_here"  # ❌ INSECURE
mysqldump -h $DB_HOST -u $DB_USER -p$DB_PASS ...
```

**New script example:**
```bash
#!/bin/bash
SECRET_JSON=$(aws secretsmanager get-secret-value --secret-id tokyobeta/prod/rds/cron-credentials --query SecretString --output text)
DB_HOST=$(echo "$SECRET_JSON" | jq -r '.host')
DB_USER=$(echo "$SECRET_JSON" | jq -r '.username')
DB_PASS=$(echo "$SECRET_JSON" | jq -r '.password')
mysqldump -h $DB_HOST -u $DB_USER -p$DB_PASS ...
unset DB_HOST DB_USER DB_PASS SECRET_JSON  # Clear from memory
```

## Validation Checklist

Before declaring Phase 2 successful:

- [ ] New scripts run without errors for 7+ days
- [ ] S3 file sizes match (within 1% difference acceptable)
- [ ] SQL dump content comparison shows only timestamp differences
- [ ] Glue ETL successfully processes dumps from new scripts
- [ ] No CloudWatch alarms triggered
- [ ] Log files show successful execution

## Rollback Procedures

### If Phase 2 Testing Fails
```bash
# Simply delete new cron jobs from crontab
crontab -e
# Remove lines with /cron_scripts_new/
# Old crons continue running unaffected
```

### If Phase 3 IAM Role Attachment Fails
```bash
# Detach IAM instance profile
aws ec2 disassociate-iam-instance-profile \
  --association-id $(aws ec2 describe-iam-instance-profile-associations \
    --filters Name=instance-id,Values=i-00523f387117d497b \
    --query 'IamInstanceProfileAssociations[0].AssociationId' \
    --output text)

# Scripts fall back to ~/.aws/credentials (still present)
```

### If Phase 4 Cutover Fails
```bash
# Re-enable old cron, disable new one
crontab -e
# Uncomment old cron line
# Comment out new cron line

# Old scripts with hardcoded credentials still work
```

## Security Benefits After Full Migration

✅ **No static AWS keys** - Can't be leaked, stolen, or committed to git  
✅ **No hardcoded DB passwords** - Not visible in `ps aux` output  
✅ **Centralized credential rotation** - Change once in Secrets Manager  
✅ **Audit trail** - CloudTrail logs who accessed secrets when  
✅ **Least privilege** - IAM role only has required permissions  
✅ **Session Manager access** - No SSH keys needed for instance access

## Final Cleanup (Only After 30 Days of Stable Operation)

```bash
# 1. Remove old cron scripts
rm -rf /home/ubuntu/cron_scripts/

# 2. Remove static AWS credentials
rm ~/.aws/credentials
# Keep ~/.aws/config for region settings

# 3. Remove test S3 prefix
aws s3 rm s3://jram-gghouse/dumps-test/ --recursive

# 4. Update documentation
```

## Questions Before Starting?

1. **What is the current RDS hostname/username?** (need for Secrets Manager)
2. **What is the acceptable downtime window for Phase 3?** (early morning? weekend?)
3. **Who should be notified before EC2 restart?** (stakeholders)
4. **What is the rollback approval process?** (who decides if we revert?)

## Monitoring During Migration

### CloudWatch Metrics to Watch
- EC2 instance status checks
- S3 PutObject API calls (should remain consistent)
- Secrets Manager GetSecretValue API calls (new)
- Glue job success/failure rate

### Log Files
```bash
# On EC2 instance
tail -f /var/log/ggh_*.log  # Your cron logs
tail -f /var/log/syslog | grep CRON  # Cron execution
```

### Success Criteria
- Zero failed cron executions
- 100% of dumps uploaded to S3
- Glue ETL continues processing without errors
- No manual intervention required for 14+ days

---

**Remember: Safety first! Never rush the migration. Each phase must be stable before proceeding to the next.**
