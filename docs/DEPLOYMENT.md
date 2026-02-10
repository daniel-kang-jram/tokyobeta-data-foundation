# Deployment & Security

**Last Updated:** February 10, 2026

This document covers deployment procedures, verification checklists, and the security migration roadmap.

---

## 📚 Table of Contents
1. [Deployment Verification](#deployment-verification)
2. [Security Migration Plan](#security-migration-plan)

---

## Deployment Verification

### Pre-flight Checklist

- [ ] **S3 Sync**: All scripts uploaded to `s3://jram-gghouse/glue-scripts/`
- [ ] **dbt Models**: All models uploaded to `s3://jram-gghouse/dbt-project/`
- [ ] **Glue Params**: Job parameters configured correctly
- [ ] **IAM**: Permissions include Bedrock (if using enrichment)
- [ ] **Tests**: Integration tests pass (`python3 test_etl_integration.py`)
- [ ] **Timeouts**: Set to 60 minutes for all jobs

### Verification Steps

#### 1. Check S3 Files
```bash
aws s3 ls s3://jram-gghouse/glue-scripts/ --profile gghouse
# Verify timestamps match your local edits
```

#### 2. Run Integration Tests
```bash
python3 test_etl_integration.py
```
**Expected Output:**
- ✅ Staging loader script exists
- ✅ Enrichment function defined
- ✅ Silver/Gold dependencies check out
- ✅ ALL INTEGRATION TESTS PASSED

#### 3. Execute Pipeline
```bash
# Option A: Run staging loader only
aws glue start-job-run --job-name tokyobeta-prod-staging-loader --profile gghouse

# Option B: Run full pipeline via Step Functions
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:ap-northeast-1:343881458651:stateMachine:tokyobeta-prod-etl-orchestrator \
  --profile gghouse
```

#### 4. Monitor Execution
```bash
# Check status
aws glue get-job-run \
  --job-name tokyobeta-prod-staging-loader \
  --run-id <job-run-id> \
  --profile gghouse

# View logs
aws logs tail /aws-glue/jobs/output --log-stream-names <job-run-id> --follow
```

#### 5. Verify Data
```sql
-- Check if data updated
SELECT MAX(updated_at) FROM gold.daily_activity_summary;

-- Check enrichment results
SELECT COUNT(*) FROM staging.tenants WHERE llm_nationality IS NOT NULL;
```

---

## Security Migration Plan

**Status:** Infrastructure Ready, Awaiting Execution  
**Objective:** Migrate EC2 cron job from static credentials to IAM roles + Secrets Manager.

### Current State (Insecure)
- **Static AWS credentials** in `~/.aws/credentials`
- **Hardcoded RDS password** in scripts
- **No audit trail**

### Target State (Secure)
- ✅ **IAM instance role** (no static keys)
- ✅ **Secrets Manager** (encrypted RDS creds)
- ✅ **CloudTrail** audit logs

### Migration Phases

#### Phase 1: Infrastructure Deployment (Ready)
- Deploy Terraform modules: `ec2_iam_role`, `secrets`
- Store RDS credentials in Secrets Manager

#### Phase 2: Parallel Testing (1-2 Weeks)
- Deploy example scripts to `~/cron_scripts_new/`
- Run alongside existing crons (offset by 10 mins)
- Validate output consistency

#### Phase 3: IAM Role Attachment (Maintenance Window)
- Stop EC2 instance
- Attach `tokyobeta-prod-ec2-cron-profile`
- Start EC2 instance
- Verify `aws sts get-caller-identity` works without config

#### Phase 4: Gradual Cutover
- Replace one cron job at a time
- Monitor for 48 hours before next replacement

#### Phase 5: Cleanup
- Remove old scripts and static credentials

### Rollback Plan
- **Phase 1-2:** Stop new scripts, no impact.
- **Phase 3:** Detach IAM profile, instance falls back to `~/.aws/credentials`.
- **Phase 4:** Re-enable old cron lines in crontab.

### Cost Impact
- **New Cost:** ~$0.50/month (Secrets Manager)
- **Benefit:** High security improvement, compliance ready.
