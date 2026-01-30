# EC2 IAM Role Test Environment

## Purpose

This is a **standalone test environment** to validate the EC2 IAM role module before deploying to production.

**What this creates:**
- ✅ IAM role with least-privilege policies
- ✅ Instance profile (ready to attach to EC2)
- ✅ Test Secrets Manager secret
- ✅ Policies for S3 and Secrets Manager access

**What this does NOT do:**
- ❌ Does NOT modify existing EC2 instance
- ❌ Does NOT touch production infrastructure
- ❌ Does NOT affect existing cron jobs
- ❌ Does NOT use production Terraform state

## Usage

### 1. Deploy Test Infrastructure

```bash
cd /Users/danielkang/tokyobeta-data-consolidation/terraform/environments/test_ec2_role

# Initialize
terraform init

# Review plan
terraform plan

# Deploy (safe, isolated test)
terraform apply
```

### 2. Verify IAM Role

```bash
# Get role details
aws iam get-role \
  --role-name tokyobeta-test-ec2-cron-role \
  --profile gghouse

# Check S3 policy
aws iam get-role-policy \
  --role-name tokyobeta-test-ec2-cron-role \
  --policy-name tokyobeta-test-s3-dumps-access \
  --profile gghouse

# Check Secrets Manager policy
aws iam get-role-policy \
  --role-name tokyobeta-test-ec2-cron-role \
  --policy-name tokyobeta-test-secrets-manager-access \
  --profile gghouse

# List attached policies
aws iam list-attached-role-policies \
  --role-name tokyobeta-test-ec2-cron-role \
  --profile gghouse
```

### 3. Test Secret Access

```bash
# Get test secret
aws secretsmanager get-secret-value \
  --secret-id tokyobeta/test/rds/cron-credentials \
  --region ap-northeast-1 \
  --profile gghouse \
  --query SecretString \
  --output text | jq .
```

### 4. Clean Up

When testing is complete:

```bash
terraform destroy
```

## What Gets Created

| Resource | Name | Purpose |
|----------|------|---------|
| IAM Role | `tokyobeta-test-ec2-cron-role` | Assumed by EC2 instance |
| IAM Policy | `tokyobeta-test-s3-dumps-access` | Upload dumps to S3 |
| IAM Policy | `tokyobeta-test-secrets-manager-access` | Read RDS credentials |
| Instance Profile | `tokyobeta-test-ec2-cron-profile` | Attach to EC2 |
| Secret | `tokyobeta/test/rds/cron-credentials` | Test RDS credentials |

## Cost

**Estimated cost:** ~$0.40/month
- IAM role: $0 (free)
- Secrets Manager: $0.40/month per secret

## Safety

This test environment:
- ✅ Uses local Terraform state (not S3 backend)
- ✅ Tagged with `Environment=test`
- ✅ Completely isolated from production
- ✅ Can be destroyed without affecting production
- ✅ Does not modify any existing resources

## Next Steps After Successful Test

1. Review IAM policies are correct
2. Verify least-privilege access
3. Deploy to production environment
4. Attach instance profile to EC2
5. Test cron scripts with new IAM role

## Troubleshooting

### "AccessDenied" errors

Check AWS credentials:
```bash
aws sts get-caller-identity --profile gghouse
```

### Module not found

Run terraform init:
```bash
terraform init
```

### Secret already exists

If you get "ResourceExistsException", either:
1. Use a different secret name
2. Delete the existing test secret:
   ```bash
   aws secretsmanager delete-secret \
     --secret-id tokyobeta/test/rds/cron-credentials \
     --force-delete-without-recovery \
     --profile gghouse
   ```
