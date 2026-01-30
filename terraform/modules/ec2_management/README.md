# EC2 Management Module

## Purpose
This module manages the existing EC2 instance (`i-00523f387117d497b`) that runs data export cron jobs. It allows attaching an IAM instance profile without recreating the instance.

## Important Notes

### IAM Profile Attachment
- Attaching an IAM instance profile to an existing instance **requires the instance to be stopped and restarted**
- Set `attach_iam_profile = true` only when you're ready to perform this operation
- The cron jobs will be interrupted during the restart

### Manual Steps Required

#### Step 1: Stop the Instance (if needed)
```bash
# Check current instance state
aws ec2 describe-instances --instance-ids i-00523f387117d497b --query 'Reservations[0].Instances[0].State.Name'

# Stop the instance (if running)
aws ec2 stop-instances --instance-ids i-00523f387117d497b

# Wait for it to stop
aws ec2 wait instance-stopped --instance-ids i-00523f387117d497b
```

#### Step 2: Attach IAM Instance Profile
```bash
# Attach the instance profile (created by ec2_iam_role module)
aws ec2 associate-iam-instance-profile \
  --instance-id i-00523f387117d497b \
  --iam-instance-profile Name=tokyobeta-prod-ec2-cron-profile
```

#### Step 3: Start the Instance
```bash
# Start the instance
aws ec2 start-instances --instance-ids i-00523f387117d497b

# Wait for it to start
aws ec2 wait instance-running --instance-ids i-00523f387117d497b
```

#### Step 4: Verify IAM Role
```bash
# SSH into the instance
ssh ubuntu@<instance-ip>

# Test the IAM role (should work without ~/.aws/credentials)
aws sts get-caller-identity
aws s3 ls s3://jram-gghouse/dumps/

# Test Secrets Manager access
aws secretsmanager get-secret-value \
  --secret-id tokyobeta/prod/rds/cron-credentials \
  --region ap-northeast-1
```

## Usage in Prod Environment

```hcl
# In terraform/environments/prod/main.tf

module "ec2_iam_role" {
  source = "../../modules/ec2_iam_role"
  
  environment     = local.environment
  s3_dumps_bucket = "jram-gghouse"
  rds_secret_arn  = module.rds_cron_secrets.rds_secret_arn
}

module "ec2_management" {
  source = "../../modules/ec2_management"
  
  environment           = local.environment
  existing_instance_id  = "i-00523f387117d497b"
  instance_profile_name = module.ec2_iam_role.instance_profile_name
  
  # Set to false initially to avoid disruption
  # Set to true when ready to attach IAM profile
  attach_iam_profile    = false
  manage_instance_state = false
  update_tags           = true
  
  instance_tags = {
    Name        = "JRAM-GGH-EC2-Cron"
    ManagedBy   = "Terraform"
    Purpose     = "Data Export Cron Jobs"
    Environment = "production"
    Project     = "TokyoBeta-DataConsolidation"
  }
}
```

## Variables

| Name | Description | Default | Required |
|------|-------------|---------|----------|
| `existing_instance_id` | EC2 instance ID | `i-00523f387117d497b` | No |
| `instance_profile_name` | IAM instance profile name | - | Yes |
| `attach_iam_profile` | Attach IAM profile (requires restart) | `false` | No |
| `manage_instance_state` | Manage instance state via Terraform | `false` | No |
| `update_tags` | Update instance tags | `true` | No |
| `instance_tags` | Tags for the instance | See variables.tf | No |

## Outputs

| Name | Description |
|------|-------------|
| `instance_id` | EC2 instance ID |
| `instance_public_ip` | Public IP address |
| `instance_private_ip` | Private IP address |
| `instance_state` | Current instance state |

## Security Considerations

### Before Applying
1. ✅ IAM role created with least privilege
2. ✅ Secrets Manager configured with RDS credentials
3. ✅ Cron scripts updated to use IAM role and Secrets Manager
4. ⚠️ Coordinate downtime window (cron jobs will be interrupted)

### After Applying
1. 🔒 Remove static AWS credentials from `~/.aws/credentials`
2. 🔒 Remove hardcoded RDS credentials from cron scripts
3. ✅ Test all cron jobs with new IAM role
4. ✅ Monitor CloudWatch Logs for any errors

## Rollback Plan

If issues occur after attaching the IAM profile:

```bash
# 1. Detach the IAM instance profile
aws ec2 disassociate-iam-instance-profile \
  --association-id $(aws ec2 describe-iam-instance-profile-associations \
    --filters Name=instance-id,Values=i-00523f387117d497b \
    --query 'IamInstanceProfileAssociations[0].AssociationId' \
    --output text)

# 2. Restore ~/.aws/credentials temporarily
# 3. Investigate and fix issues
# 4. Reattach when ready
```

## Maintenance

### Regular Updates
- Instance profile can be updated without restarting the instance
- IAM policy changes take effect immediately
- Secrets Manager credentials can be rotated without EC2 changes
