# Terraform Plan Review - EC2 IAM Role Test

**Status:** ✅ Safe to Deploy  
**Risk Level:** None (test environment, no production impact)  
**Resources to Create:** 9

---

## Summary

This plan creates an isolated test of the EC2 IAM role module. It does NOT touch any production resources or your existing EC2 instance.

### What Will Be Created

| Resource | Name | Purpose |
|----------|------|---------|
| **IAM Role** | `tokyobeta-test-ec2-cron-role` | Role that EC2 instance will assume |
| **IAM Policy** | `tokyobeta-test-s3-dumps-access` | Allows uploads to s3://jram-gghouse |
| **IAM Policy** | `tokyobeta-test-secrets-manager-access` | Allows reading RDS credentials |
| **Policy Attachment** | SSM Managed Instance Core | Enables SSM Session Manager |
| **Instance Profile** | `tokyobeta-test-ec2-cron-profile` | Wrapper to attach role to EC2 |
| **Secret** | `tokyobeta/test/rds/cron-credentials` | Test RDS credentials |
| **Secret Version** | (placeholder credentials) | For testing purposes only |

---

## Security Review ✅

### IAM Role Permissions (Least Privilege)

**S3 Access:**
```json
{
  "Statement": [
    {
      "Sid": "ListDumpsBucket",
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::jram-gghouse"
    },
    {
      "Sid": "UploadDumps",
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:PutObjectAcl", "s3:GetObject"],
      "Resource": [
        "arn:aws:s3:::jram-gghouse/dumps/*",
        "arn:aws:s3:::jram-gghouse/contractstatus/*"
      ]
    }
  ]
}
```

✅ **Correct:** Only allows uploads to specific prefixes, not entire bucket  
✅ **Correct:** ListBucket on bucket, Put/Get on objects only  
✅ **Correct:** No DeleteObject permission (read + write only)

**Secrets Manager Access:**
```json
{
  "Effect": "Allow",
  "Action": [
    "secretsmanager:GetSecretValue",
    "secretsmanager:DescribeSecret"
  ],
  "Resource": "<test-secret-arn>"
}
```

✅ **Correct:** Read-only access to secrets  
✅ **Correct:** No write/update/delete permissions  
✅ **Correct:** Scoped to specific secret ARN

**SSM Session Manager:**
- Allows secure shell access without SSH keys
- AWS managed policy: `AmazonSSMManagedInstanceCore`

✅ **Correct:** Industry standard for EC2 management

---

## Cost Estimate

| Resource | Monthly Cost |
|----------|--------------|
| IAM Role & Policies | $0 (free) |
| Instance Profile | $0 (free) |
| Secrets Manager (1 secret) | $0.40 |
| **Total** | **~$0.40/month** |

**Note:** This is a test environment that can be destroyed after validation

---

## Safety Checks ✅

- [x] Tagged with `Environment=test` (not production)
- [x] Uses local Terraform state (not S3 backend)
- [x] Different naming convention (`test-` prefix)
- [x] Does NOT modify EC2 instance `i-00523f387117d497b`
- [x] Does NOT touch existing cron jobs
- [x] Does NOT interfere with production workflows
- [x] Can be deleted with `terraform destroy`

---

## What This Does NOT Do ❌

- ❌ Does NOT attach IAM role to EC2 instance (that's in a separate module)
- ❌ Does NOT modify existing infrastructure
- ❌ Does NOT change cron jobs
- ❌ Does NOT affect S3 bucket or objects
- ❌ Does NOT touch production Secrets Manager secrets
- ❌ Does NOT use production Terraform state

---

## After Deployment

You'll be able to test:

1. **Verify IAM role created:**
   ```bash
   aws iam get-role --role-name tokyobeta-test-ec2-cron-role --profile gghouse
   ```

2. **Check S3 policy:**
   ```bash
   aws iam list-role-policies --role-name tokyobeta-test-ec2-cron-role --profile gghouse
   ```

3. **Test secret access:**
   ```bash
   aws secretsmanager get-secret-value \
     --secret-id tokyobeta/test/rds/cron-credentials \
     --region ap-northeast-1 \
     --profile gghouse
   ```

4. **Validate least-privilege:**
   - Try accessing resources outside allowed scope (should fail)
   - Verify only required permissions granted

---

## Recommendation

✅ **Safe to deploy** - This is an isolated test with no production impact

Run:
```bash
terraform apply test.tfplan
```

---

## Cleanup

When testing is complete:

```bash
terraform destroy
```

This removes all test resources and costs you nothing beyond the test period.
