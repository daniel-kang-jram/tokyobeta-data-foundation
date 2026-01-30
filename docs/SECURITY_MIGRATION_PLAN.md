# Security Migration Plan - EC2 Cron Job Hardening

**Date:** 2026-01-31  
**Status:** Infrastructure Ready, Awaiting Execution  
**Risk Level:** Medium (existing cron jobs continue working during migration)

## Executive Summary

This document outlines the complete plan to migrate the existing EC2 cron job from insecure static credentials to AWS best practices using IAM roles and Secrets Manager.

**Key Points:**
- ✅ All infrastructure code is ready (Terraform modules created)
- ✅ Safe migration strategy with rollback capability at each phase
- ✅ **Zero risk to existing operations** - old cron jobs remain untouched until validation complete
- ✅ Parallel testing approach ensures new method works before cutover

## Current State (Insecure but Functional)

### EC2 Instance
- **Instance ID:** `i-00523f387117d497b`
- **Name:** JRAM-GGH-EC2
- **Account:** gghouse (343881458651)
- **Location:** ap-northeast-1

### Security Issues
1. **Static AWS credentials** in `~/.aws/credentials` → Can be leaked, no audit trail
2. **Hardcoded RDS password** in cron scripts → Visible in `ps aux`, stored in plaintext
3. **No credential rotation** → Manual process, requires script edits
4. **No audit trail** → Can't track who accessed what

### Existing Cron Jobs (DO NOT MODIFY YET)
```bash
30 5 * * * ggh_datatransit.sh          # Full mysqldump
 1 6 * * * ggh_contractstatus.sh       # Contract status query
 5 6 * * * ggh_contractstatusALL.sh    # All contract statuses
10 6 * * * TenantsALL.sh               # Tenant data
12 6 * * * MovingsALL.sh               # Moving data
```

**Impact:** These upload 940MB daily dumps to `s3://jram-gghouse/dumps/` which feed the data pipeline

## Target State (Secure)

### After Migration
1. ✅ **IAM instance role** → EC2 gets AWS API access automatically
2. ✅ **Secrets Manager** → RDS credentials stored encrypted, rotatable
3. ✅ **No hardcoded credentials** → Nothing to leak or commit to git
4. ✅ **CloudTrail audit logs** → Track all secret access
5. ✅ **Centralized rotation** → Change password once, all scripts updated
6. ✅ **SSM Session Manager** → No SSH keys needed

## What Has Been Built

### 1. Terraform Modules Created

#### `terraform/modules/ec2_iam_role/`
- IAM role for EC2 with least-privilege permissions
- S3 access policy (upload to jram-gghouse bucket)
- Secrets Manager read policy
- SSM Session Manager access
- Instance profile for attaching to EC2

#### `terraform/modules/ec2_management/`
- Manages existing EC2 instance
- Safely attaches IAM instance profile
- Updates instance tags
- Includes rollback procedures

#### `terraform/modules/secrets/` (Extended)
- Aurora credentials secret (existing)
- **NEW:** RDS cron job credentials secret
- Auto-generated or user-provided passwords
- Proper encryption and tagging

#### `terraform/modules/quicksight/`
- VPC connection to Aurora
- Data source configuration
- SPICE refresh automation
- IAM roles for QuickSight

### 2. Example Cron Scripts Created

**Location:** `scripts/example_cron_scripts/`

- `ggh_datatransit.sh` - Full database dump using Secrets Manager
- `ggh_contractstatus.sh` - Contract status query using Secrets Manager
- `README.md` - Comprehensive migration guide with all phases
- `TESTING_GUIDE.md` - Detailed validation procedures

**Key Features:**
- Fetch credentials from Secrets Manager at runtime
- Clear sensitive variables from memory after use
- Comprehensive error handling and logging
- S3 upload with metadata tagging
- Compatible with existing cron schedule

### 3. QuickSight Automation

**Location:** `scripts/quicksight/`

- `deploy_dashboards.py` - Export and deploy dashboards as code
- `README.md` - Complete workflow documentation
- Lambda function for SPICE refresh automation

## Migration Timeline (4 Phases, ~3 Weeks)

### Phase 1: Infrastructure Deployment (Week 1, Days 1-2)
**Duration:** 2-3 hours  
**Risk:** None (no changes to existing crons)  
**Downtime:** None

**Steps:**
```bash
# 1. Deploy Terraform modules
cd terraform/environments/prod
terraform plan  # Review all changes
terraform apply  # Deploy IAM role, Secrets Manager

# 2. Store RDS credentials in Secrets Manager
aws secretsmanager put-secret-value \
  --secret-id tokyobeta/prod/rds/cron-credentials \
  --secret-string '{
    "host": "<your-rds-endpoint>",
    "username": "<current-username>",
    "password": "<current-password>",
    "database": "gghouse",
    "port": 3306
  }'

# 3. Verify secret stored correctly
aws secretsmanager get-secret-value \
  --secret-id tokyobeta/prod/rds/cron-credentials
```

**Validation:**
- [ ] IAM role created: `tokyobeta-prod-ec2-cron-role`
- [ ] Instance profile created: `tokyobeta-prod-ec2-cron-profile`
- [ ] Secret exists: `tokyobeta/prod/rds/cron-credentials`
- [ ] Old cron jobs still running successfully

### Phase 2: Parallel Testing (Week 1-2, Days 3-14)
**Duration:** 7-14 days (observation period)  
**Risk:** Low (both systems running independently)  
**Downtime:** None

**Steps:**
```bash
# 1. Copy example scripts to EC2
ssh ubuntu@<ec2-ip>
mkdir -p ~/cron_scripts_new
# Upload ggh_datatransit.sh, ggh_contractstatus.sh

# 2. Modify scripts to use test S3 prefix
vim ~/cron_scripts_new/ggh_datatransit.sh
# Change: S3_PREFIX="dumps-test"

# 3. Add test cron jobs (10 min offset from production)
crontab -e
# Add: 40 5 * * * /home/ubuntu/cron_scripts_new/ggh_datatransit.sh
# Keep existing: 30 5 * * * /home/ubuntu/cron_scripts/ggh_datatransit.sh

# 4. Monitor for 7-14 days
tail -f ~/logs_new/ggh_datatransit.log
```

**Validation (Daily):**
- [ ] Both old and new scripts execute successfully
- [ ] S3 uploads to both `dumps/` and `dumps-test/` succeed
- [ ] File sizes within 5% of each other
- [ ] Glue ETL processes both dumps successfully
- [ ] No errors in CloudWatch Logs

**Success Criteria:**
- 7+ consecutive days of successful parallel execution
- No manual intervention required
- Stakeholder approval to proceed

### Phase 3: IAM Role Attachment (Week 2, Day 15)
**Duration:** 30 minutes  
**Risk:** Medium (**requires EC2 restart**, cron jobs interrupted)  
**Downtime:** 5-10 minutes

**Prerequisites:**
- [ ] Phase 2 validation complete
- [ ] Maintenance window scheduled (e.g., Sunday 2 AM)
- [ ] Stakeholders notified
- [ ] Backup of current crontab saved
- [ ] Rollback plan reviewed

**Steps:**
```bash
# 1. Save current crontab
crontab -l > ~/crontab_backup_$(date +%Y%m%d).txt

# 2. Stop EC2 instance
aws ec2 stop-instances --instance-ids i-00523f387117d497b
aws ec2 wait instance-stopped --instance-ids i-00523f387117d497b

# 3. Attach IAM instance profile
aws ec2 associate-iam-instance-profile \
  --instance-id i-00523f387117d497b \
  --iam-instance-profile Name=tokyobeta-prod-ec2-cron-profile

# 4. Start EC2 instance
aws ec2 start-instances --instance-ids i-00523f387117d497b
aws ec2 wait instance-running --instance-ids i-00523f387117d497b

# 5. SSH and verify IAM role
ssh ubuntu@<ec2-ip>
aws sts get-caller-identity  # Should work without ~/.aws/credentials
aws s3 ls s3://jram-gghouse/
aws secretsmanager get-secret-value --secret-id tokyobeta/prod/rds/cron-credentials
```

**Validation:**
- [ ] EC2 restarted successfully
- [ ] IAM role attached
- [ ] AWS CLI works without credentials file
- [ ] Secrets Manager accessible
- [ ] Both old and new crons still running
- [ ] Next scheduled cron executes successfully

**Rollback (if issues):**
```bash
# Detach IAM profile, instance falls back to ~/.aws/credentials
aws ec2 disassociate-iam-instance-profile \
  --association-id $(aws ec2 describe-iam-instance-profile-associations \
    --filters Name=instance-id,Values=i-00523f387117d497b \
    --query 'IamInstanceProfileAssociations[0].AssociationId' --output text)
```

### Phase 4: Gradual Cutover (Week 2-3, Days 16-21)
**Duration:** 5-7 days (one cron per day)  
**Risk:** Low (incremental changes, easy rollback)  
**Downtime:** None

**Approach:** Replace one cron job at a time, validate for 24-48 hours before next

**Day 16: Contract Status (Lowest Risk)**
```bash
crontab -e
# Enable: 1 6 * * * /home/ubuntu/cron_scripts_new/ggh_contractstatus.sh
# Disable: # 1 6 * * * /home/ubuntu/cron_scripts/ggh_contractstatus.sh
```
- Monitor for 48 hours
- Verify S3 uploads to correct location (`dumps/` not `dumps-test/`)
- Check downstream consumers

**Day 18: Other Query Scripts**
```bash
# Repeat for: ggh_contractstatusALL.sh, TenantsALL.sh, MovingsALL.sh
```

**Day 20: Full Database Dump (Highest Risk)**
```bash
crontab -e
# Enable: 30 5 * * * /home/ubuntu/cron_scripts_new/ggh_datatransit.sh
# Disable: # 30 5 * * * /home/ubuntu/cron_scripts/ggh_datatransit.sh
```
- Critical: Monitor first 3 executions closely
- Verify Glue ETL success
- Check QuickSight dashboards populated

**Validation (After Each Cutover):**
- [ ] Cron executes at scheduled time
- [ ] S3 upload successful
- [ ] File size consistent with historical data
- [ ] No errors in logs
- [ ] Downstream pipeline unaffected

### Phase 5: Cleanup (Week 3, Day 22+)
**Duration:** 1 hour  
**Risk:** None  
**Downtime:** None

**Steps (only after 14+ days of stable operation):**
```bash
# 1. Remove old cron scripts
rm -rf ~/cron_scripts/

# 2. Remove static AWS credentials
rm ~/.aws/credentials
# Keep ~/.aws/config for region

# 3. Remove test S3 files
aws s3 rm s3://jram-gghouse/dumps-test/ --recursive

# 4. Update documentation
```

## Rollback Procedures (for Each Phase)

### Phase 1 Rollback
```bash
# Simply don't attach IAM role, don't update scripts
# Old crons continue working unchanged
terraform destroy  # Optional: remove created resources
```

### Phase 2 Rollback
```bash
# Delete test cron jobs from crontab
crontab -e
# Remove all /cron_scripts_new/ lines
# Old crons unaffected
```

### Phase 3 Rollback
```bash
# Detach IAM profile
aws ec2 disassociate-iam-instance-profile \
  --association-id <association-id>
# EC2 falls back to ~/.aws/credentials (still present)
```

### Phase 4 Rollback (per cron job)
```bash
# Re-enable old cron, disable new one
crontab -e
# Uncomment old cron line
# Comment out new cron line
```

## Success Metrics

### Technical Metrics
- ✅ Zero failed cron executions after cutover
- ✅ 100% of expected S3 uploads successful
- ✅ Glue ETL success rate unchanged (100%)
- ✅ No manual intervention required for 30+ days

### Security Metrics
- ✅ No static credentials in files
- ✅ CloudTrail logs showing secret access
- ✅ IAM least-privilege validated
- ✅ Credential rotation tested successfully

### Operational Metrics
- ✅ Time to rotate credentials: <5 minutes (vs 2+ hours before)
- ✅ Audit capability: 100% of access logged
- ✅ Recovery time: <10 minutes with clear rollback

## Communication Plan

### Stakeholders to Notify
1. Data engineering team
2. QuickSight dashboard users
3. BI analysts
4. Management (brief overview)

### Notification Timeline
- **7 days before Phase 3:** Announce EC2 restart maintenance window
- **1 day before Phase 3:** Reminder of downtime
- **Day of Phase 3:** Start notification, completion notification
- **After Phase 4 complete:** Migration success announcement

### Communication Template
```
Subject: [MAINTENANCE] EC2 Cron Job Security Upgrade

Timeline: Sunday, [DATE], 2:00-2:30 AM JST

Impact: 5-10 minutes interruption of data export cron jobs
        No impact to QuickSight dashboards (they use cached data)

Purpose: Upgrading EC2 cron job authentication from static credentials
         to IAM roles and AWS Secrets Manager for improved security

Rollback Plan: Can revert in <5 minutes if issues occur

Questions: Reply to this email or contact [CONTACT]
```

## Cost Impact

**New Resources:**
- IAM role: $0 (free)
- Secrets Manager: $0.40/month per secret × 1 = $0.40/month
- Secret API calls: $0.05 per 10,000 calls ≈ negligible
- **Total new cost:** ~$0.50/month

**Return on Investment:**
- Reduced security risk: High
- Operational efficiency: 90% faster credential rotation
- Compliance benefits: Audit trail, least privilege

## Monitoring & Alerting

### CloudWatch Alarms (Recommended)
```bash
# 1. Cron execution failure alarm
aws cloudwatch put-metric-alarm \
  --alarm-name tokyobeta-cron-failure \
  --alarm-description "Alert when cron jobs fail" \
  --metric-name "Errors" \
  --namespace "AWS/Logs" \
  --statistic Sum \
  --period 3600 \
  --threshold 1 \
  --comparison-operator GreaterThanThreshold

# 2. S3 upload failure alarm  
# 3. Secrets Manager access failure alarm
```

### Log Monitoring
- Cron logs: `/var/log/ggh_*.log`
- Syslog: `/var/log/syslog` (CRON entries)
- CloudTrail: Secrets Manager API calls
- S3 access logs: Upload verification

## Questions & Answers

**Q: What if the new scripts don't work?**  
A: Old scripts keep running during parallel testing. We only cutover after 7-14 days of successful validation.

**Q: Will this interrupt the data pipeline?**  
A: Phase 3 (EC2 restart) causes 5-10 minute interruption. Schedule during low-usage time (early morning weekend).

**Q: Can we rollback after cutover?**  
A: Yes, at any phase. Simply re-enable old cron jobs. Old scripts remain on instance for 30 days.

**Q: What if credentials need to be rotated?**  
A: Update once in Secrets Manager, all scripts automatically use new credentials. No script edits needed.

**Q: How do we know it's working?**  
A: Monitor logs, S3 uploads, and Glue ETL success rate. Automated comparison script validates dump consistency.

## Next Steps

1. **Review this plan** with stakeholders
2. **Get approval** for Phase 3 maintenance window
3. **Execute Phase 1** (infrastructure deployment)
4. **Begin Phase 2** (parallel testing)
5. **Schedule Phase 3** (EC2 restart)
6. **Complete Phase 4** (gradual cutover)
7. **Perform Phase 5** (cleanup)

## References

- Example scripts: `scripts/example_cron_scripts/`
- Testing guide: `scripts/example_cron_scripts/TESTING_GUIDE.md`
- Terraform modules: `terraform/modules/ec2_iam_role/`, `terraform/modules/ec2_management/`
- AWS Best Practices: [IAM Roles for EC2](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html)

---

**Document Owner:** Data Engineering Team  
**Last Updated:** 2026-01-31  
**Next Review:** After Phase 2 completion
