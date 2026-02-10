# Terraform Backend Configuration
# This file defines the S3 backend for storing Terraform state files
# Run `terraform init` after creating this file to initialize the backend

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "tokyobeta-terraform-state"
    key            = "terraform.tfstate"
    region         = "ap-northeast-1"
    encrypt        = true
    dynamodb_table = "tokyobeta-terraform-locks"
  }
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile

  default_tags {
    tags = {
      Project     = "TokyoBeta-DataConsolidation"
      ManagedBy   = "Terraform"
      Environment = "production"
    }
  }
}
