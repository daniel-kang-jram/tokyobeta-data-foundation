# Terraform Infrastructure

This directory contains all Terraform configurations for the Tokyo Beta Data Consolidation project.

## Directory Structure

```
terraform/
├── bootstrap/          # One-time backend setup (S3 + DynamoDB)
├── backend.tf          # Backend configuration (used by all environments)
├── environments/       # Environment-specific configurations
│   ├── dev/           # Development environment
│   └── prod/          # Production environment
└── modules/           # Reusable Terraform modules
    ├── networking/    # VPC, subnets, NAT, security groups
    ├── aurora/        # Aurora MySQL cluster
    ├── lambda/        # Lambda functions and IAM roles
    ├── eventbridge/   # EventBridge rules and targets
    ├── secrets/       # Secrets Manager
    ├── monitoring/    # CloudWatch alarms and SNS
    └── quicksight/    # QuickSight data sources
```

## Initial Setup

### 1. Bootstrap Backend (One-time)

```bash
cd bootstrap
terraform init
terraform apply
```

This creates:
- S3 bucket `tokyobeta-terraform-state` for state storage
- DynamoDB table `tokyobeta-terraform-locks` for state locking

### 2. Deploy Infrastructure

```bash
cd environments/prod
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

## Module Dependencies

Modules are applied in this order:

1. **networking** - VPC, subnets, NAT gateway, security groups
2. **secrets** - Aurora credentials in Secrets Manager
3. **aurora** - Aurora MySQL cluster (depends on networking + secrets)
4. **lambda** - ETL processor (depends on networking + secrets)
5. **eventbridge** - Daily trigger (depends on lambda)
6. **monitoring** - CloudWatch alarms (depends on lambda + aurora)
7. **quicksight** - Data source (depends on aurora)

## Common Commands

```bash
# Plan changes
terraform plan -out=tfplan

# Apply changes
terraform apply tfplan

# Show current state
terraform show

# List resources
terraform state list

# Destroy everything (careful!)
terraform destroy
```

## Environment Variables

Set these before running Terraform:

```bash
export AWS_PROFILE=gghouse
export AWS_REGION=ap-northeast-1
```

## State Management

- State files are stored in S3: `s3://tokyobeta-terraform-state/`
- State locking uses DynamoDB: `tokyobeta-terraform-locks`
- Each environment has its own state file path

## Security Notes

- Never commit `.tfvars` files with secrets
- Aurora credentials are generated and stored in Secrets Manager
- All resources use private subnets where possible
- Security groups follow least-privilege principle
