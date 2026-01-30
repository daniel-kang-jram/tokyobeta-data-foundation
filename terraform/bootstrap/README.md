# Terraform Backend Bootstrap

This directory contains the Terraform configuration to create the S3 bucket and DynamoDB table required for storing Terraform state.

## ⚠️ Important

This should be run **ONCE** before deploying the main infrastructure. The resources created here are used by all other Terraform configurations.

## Usage

```bash
# Initialize Terraform
terraform init

# Review the plan
terraform plan

# Create the backend resources
terraform apply

# Note the outputs
terraform output
```

## What Gets Created

1. **S3 Bucket** (`tokyobeta-terraform-state`)
   - Versioning enabled for state file recovery
   - Server-side encryption with AES256
   - Public access blocked
   
2. **DynamoDB Table** (`tokyobeta-terraform-locks`)
   - Used for state locking to prevent concurrent modifications
   - Pay-per-request billing mode

## After Bootstrap

Once these resources are created, you can use them in other Terraform configurations by adding a backend block:

```hcl
terraform {
  backend "s3" {
    bucket         = "tokyobeta-terraform-state"
    key            = "path/to/terraform.tfstate"
    region         = "ap-northeast-1"
    encrypt        = true
    dynamodb_table = "tokyobeta-terraform-locks"
    profile        = "gghouse"
  }
}
```

## State Management

This bootstrap configuration itself uses **local state** since the remote backend doesn't exist yet. After creation:

- Keep the `terraform.tfstate` file in this directory safe
- Consider storing it in a secure location
- Do not delete these resources unless you're tearing down the entire project
