# Standalone Test: EC2 IAM Role for Cron Job Security
# This is a minimal, safe test that creates ONLY the IAM role and instance profile
# Does NOT modify existing EC2 instance or any production resources

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Local backend for testing (not production)
  backend "local" {
    path = "terraform.tfstate"
  }
}

provider "aws" {
  region  = "ap-northeast-1"
  profile = "gghouse"

  default_tags {
    tags = {
      Project     = "TokyoBeta-DataConsolidation"
      ManagedBy   = "Terraform"
      Environment = "test"
      Purpose     = "EC2-Security-Test"
    }
  }
}

locals {
  environment     = "test"
  s3_dumps_bucket = "jram-gghouse"
}

# Create a placeholder secret ARN for testing
# In production, this would come from the secrets module
resource "aws_secretsmanager_secret" "test_rds_cron" {
  name        = "tokyobeta/test/rds/cron-credentials"
  description = "TEST ONLY - RDS credentials for EC2 cron jobs"

  tags = {
    Name        = "tokyobeta-test-rds-cron-creds"
    Environment = "test"
    Purpose     = "Testing EC2 IAM role"
  }
}

resource "aws_secretsmanager_secret_version" "test_rds_cron" {
  secret_id = aws_secretsmanager_secret.test_rds_cron.id
  secret_string = jsonencode({
    host     = "test-rds-endpoint.rds.amazonaws.com"
    username = "test_user"
    password = "placeholder_password_change_in_production"
    database = "gghouse"
    port     = 3306
  })
}

# Module: EC2 IAM Role
module "ec2_iam_role" {
  source = "../../modules/ec2_iam_role"

  environment     = local.environment
  s3_dumps_bucket = local.s3_dumps_bucket
  rds_secret_arn  = aws_secretsmanager_secret.test_rds_cron.arn
}

# Outputs
output "iam_role_arn" {
  description = "IAM role ARN for EC2"
  value       = module.ec2_iam_role.role_arn
}

output "iam_role_name" {
  description = "IAM role name"
  value       = module.ec2_iam_role.role_name
}

output "instance_profile_name" {
  description = "Instance profile name (attach to EC2)"
  value       = module.ec2_iam_role.instance_profile_name
}

output "instance_profile_arn" {
  description = "Instance profile ARN"
  value       = module.ec2_iam_role.instance_profile_arn
}

output "test_secret_arn" {
  description = "Test secret ARN"
  value       = aws_secretsmanager_secret.test_rds_cron.arn
}

output "next_steps" {
  description = "What to do next"
  value       = <<-EOT
  
  ✅ TEST DEPLOYMENT SUCCESSFUL!
  
  Created resources:
  - IAM Role: ${module.ec2_iam_role.role_name}
  - Instance Profile: ${module.ec2_iam_role.instance_profile_name}
  - Test Secret: tokyobeta/test/rds/cron-credentials
  
  Next steps:
  1. Verify IAM policies:
     aws iam get-role --role-name ${module.ec2_iam_role.role_name} --profile gghouse
  
  2. Test S3 access policy:
     aws iam get-role-policy --role-name ${module.ec2_iam_role.role_name} --policy-name tokyobeta-test-s3-dumps-access --profile gghouse
  
  3. When ready for production:
     - Store REAL RDS credentials in Secrets Manager
     - Update production terraform to use this module
     - Attach instance profile to EC2: i-00523f387117d497b
  
  4. Clean up this test:
     terraform destroy
  
  EOT
}
