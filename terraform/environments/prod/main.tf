# Production Environment Configuration
# Orchestrates all Terraform modules for Tokyo Beta Data Consolidation

terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }

  backend "s3" {
    bucket         = "tokyobeta-terraform-state"
    key            = "prod/terraform.tfstate"
    region         = "ap-northeast-1"
    encrypt        = true
    dynamodb_table = "tokyobeta-terraform-locks"
  }
}

provider "aws" {
  region  = "ap-northeast-1"
  
  default_tags {
    tags = {
      Project     = "TokyoBeta-DataConsolidation"
      ManagedBy   = "Terraform"
      Environment = "production"
    }
  }
}

provider "random" {}

# Local variables
locals {
  environment = "prod"
  project_name = "tokyobeta"
  alert_email = var.alert_email
}

# Module: Networking
module "networking" {
  source = "../../modules/networking"
  
  environment        = local.environment
  vpc_cidr           = "10.0.0.0/16"
  availability_zones = ["ap-northeast-1a", "ap-northeast-1c"]
}

# Module: Secrets (Aurora credentials)
module "secrets" {
  source = "../../modules/secrets"
  
  environment = local.environment
  db_username = "admin"
}

# Module: Aurora MySQL
module "aurora" {
  source = "../../modules/aurora"
  
  environment        = local.environment
  vpc_id             = module.networking.vpc_id
  private_subnet_ids = module.networking.private_subnet_ids
  security_group_id  = module.networking.aurora_security_group_id
  db_username        = module.secrets.aurora_username
  db_password        = module.secrets.aurora_password
  instance_class     = "db.t4g.medium"
  instance_count     = 2
  
  backup_retention_period     = 7
  enable_deletion_protection  = true
}

# Module: Glue ETL
module "glue" {
  source = "../../modules/glue"
  
  environment         = local.environment
  s3_source_bucket    = var.s3_source_bucket
  s3_source_prefix    = var.s3_source_prefix
  aurora_endpoint     = module.aurora.cluster_endpoint
  aurora_database     = module.aurora.database_name
  aurora_secret_arn   = module.secrets.aurora_secret_arn
  vpc_id              = module.networking.vpc_id
  private_subnet_ids  = module.networking.private_subnet_ids
  security_group_id   = module.networking.lambda_security_group_id
  
  worker_type        = "G.1X"
  number_of_workers  = 2
  job_timeout        = 60
}

# Module: EventBridge
module "eventbridge" {
  source = "../../modules/eventbridge"
  
  environment          = local.environment
  glue_job_name        = module.glue.glue_job_name
  glue_job_arn         = module.glue.glue_job_arn
  schedule_expression  = "cron(0 22 * * ? *)"  # 7:00 AM JST = 22:00 UTC
}

# Module: Monitoring
module "monitoring" {
  source = "../../modules/monitoring"
  
  environment        = local.environment
  glue_job_name      = module.glue.glue_job_name
  aurora_cluster_id  = module.aurora.cluster_id
  alert_email        = local.alert_email
}
