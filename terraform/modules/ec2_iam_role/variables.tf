# Variables for EC2 IAM Role Module

variable "environment" {
  type        = string
  description = "Environment name (e.g., prod, dev)"
}

variable "s3_dumps_bucket" {
  type        = string
  description = "S3 bucket name where SQL dumps are stored"
  default     = "jram-gghouse"
}

variable "rds_secret_arn" {
  type        = string
  description = "ARN of the Secrets Manager secret containing RDS credentials"
}
