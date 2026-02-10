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
  region = "ap-northeast-1"

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
  environment  = "prod"
  project_name = "tokyobeta"
  alert_email  = var.alert_email
}

# Module: Networking
module "networking" {
  source = "../../modules/networking"

  environment         = local.environment
  vpc_cidr            = "10.0.0.0/16"
  availability_zones  = ["ap-northeast-1a", "ap-northeast-1c"]
  allowed_cidr_blocks = var.allowed_cidr_blocks # External IPs allowed to access Aurora
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

  environment         = local.environment
  vpc_id              = module.networking.vpc_id
  subnet_ids          = module.networking.private_subnet_ids
  security_group_id   = module.networking.aurora_security_group_id
  db_username         = module.secrets.aurora_username
  db_password         = module.secrets.aurora_password
  instance_class      = "db.t4g.medium"
  instance_count      = 2
  publicly_accessible = true

  backup_retention_period    = 7
  enable_deletion_protection = true
}

# Module: Glue ETL
module "glue" {
  source = "../../modules/glue"

  environment      = local.environment
  s3_source_bucket = var.s3_source_bucket
  s3_source_prefix = var.s3_source_prefix
  # TEMPORARY: Hardcoded public Aurora endpoint until private cluster is fully removed
  aurora_endpoint    = "tokyobeta-prod-aurora-cluster-public.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com"
  aurora_database    = "tokyobeta"
  aurora_secret_arn  = module.secrets.aurora_secret_arn
  vpc_id             = module.networking.vpc_id
  private_subnet_ids = module.networking.private_subnet_ids
  security_group_id  = module.networking.lambda_security_group_id

  worker_type       = "G.1X"
  number_of_workers = 2
  job_timeout       = 60
}

# Module: Step Functions (NEW - Orchestrates ETL layers)
module "step_functions" {
  source = "../../modules/step_functions"

  environment             = local.environment
  staging_loader_name     = module.glue.staging_loader_name
  staging_loader_arn      = module.glue.staging_loader_arn
  silver_transformer_name = module.glue.silver_transformer_name
  silver_transformer_arn  = module.glue.silver_transformer_arn
  gold_transformer_name   = module.glue.gold_transformer_name
  gold_transformer_arn    = module.glue.gold_transformer_arn
  data_quality_test_name  = module.glue.data_quality_test_name
  data_quality_test_arn   = module.glue.data_quality_test_arn
  sns_topic_arn           = module.monitoring.sns_topic_arn
}

# Module: EventBridge
module "eventbridge" {
  source = "../../modules/eventbridge"

  environment         = local.environment
  glue_job_name       = module.glue.glue_job_name
  glue_job_arn        = module.glue.glue_job_arn
  schedule_expression = "cron(0 22 * * ? *)" # 7:00 AM JST = 22:00 UTC (OLD - Keep for rollback)

  # NEW: Trigger Step Functions instead (commented out for now - parallel run phase)
  # state_machine_arn    = module.step_functions.state_machine_arn
  # schedule_expression  = "cron(0 22 * * ? *)"  # 7:00 AM JST
}

# Module: Monitoring
module "monitoring" {
  source = "../../modules/monitoring"

  environment       = local.environment
  project_name      = local.project_name
  glue_job_name     = module.glue.glue_job_name
  aurora_cluster_id = module.aurora.cluster_id
  alert_email       = local.alert_email

  aurora_endpoint    = module.aurora.cluster_endpoint
  aurora_secret_arn  = module.secrets.aurora_secret_arn
  private_subnet_ids = module.networking.private_subnet_ids
  security_group_id  = module.networking.lambda_security_group_id
}
