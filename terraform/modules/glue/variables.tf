# Glue Module Variables

variable "environment" {
  description = "Environment name (dev/prod)"
  type        = string
}

variable "s3_source_bucket" {
  description = "S3 bucket containing SQL dumps"
  type        = string
  default     = "jram-gghouse"
}

variable "s3_source_prefix" {
  description = "S3 prefix for SQL dumps"
  type        = string
  default     = "dumps/"
}

variable "aurora_endpoint" {
  description = "Aurora cluster endpoint"
  type        = string
}

variable "aurora_database" {
  description = "Aurora database name"
  type        = string
}

variable "aurora_secret_arn" {
  description = "ARN of Aurora credentials in Secrets Manager"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID for Glue connection"
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for Glue"
  type        = list(string)
}

variable "security_group_id" {
  description = "Security group for Glue connection"
  type        = string
}

variable "worker_type" {
  description = "Glue worker type"
  type        = string
  default     = "G.1X"
  
  validation {
    condition     = contains(["G.1X", "G.2X", "G.4X", "G.8X"], var.worker_type)
    error_message = "Worker type must be one of: G.1X, G.2X, G.4X, G.8X"
  }
}

variable "number_of_workers" {
  description = "Number of Glue workers"
  type        = number
  default     = 2
  
  validation {
    condition     = var.number_of_workers >= 2 && var.number_of_workers <= 100
    error_message = "Number of workers must be between 2 and 100"
  }
}

variable "job_timeout" {
  description = "Glue job timeout in minutes"
  type        = number
  default     = 60
}
