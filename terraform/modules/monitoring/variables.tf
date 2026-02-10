# Monitoring Module Variables

variable "environment" {
  description = "Environment name (dev/prod)"
  type        = string
}

variable "glue_job_name" {
  description = "Name of the Glue job to monitor"
  type        = string
}

variable "aurora_cluster_id" {
  description = "ID of the Aurora cluster to monitor"
  type        = string
}

variable "alert_email" {
  description = "Email address for alert notifications"
  type        = string
}

variable "cpu_threshold" {
  description = "CPU utilization threshold percentage"
  type        = number
  default     = 80
}

variable "storage_threshold_bytes" {
  description = "Free storage threshold in bytes"
  type        = number
  default     = 10737418240  # 10 GB
}

variable "job_duration_threshold_ms" {
  description = "Glue job duration threshold in milliseconds"
  type        = number
  default     = 1800000  # 30 minutes
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "tokyobeta"
}

variable "aurora_endpoint" {
  description = "Aurora cluster endpoint"
  type        = string
}

variable "aurora_secret_arn" {
  description = "ARN of the secret containing Aurora credentials"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for Lambda"
  type        = list(string)
}

variable "security_group_id" {
  description = "Security group ID for Lambda"
  type        = string
}
