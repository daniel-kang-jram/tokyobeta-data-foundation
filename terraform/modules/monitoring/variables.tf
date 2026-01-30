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
