# Variables for QuickSight Module

variable "environment" {
  type        = string
  description = "Environment name (dev/prod)"
}

variable "aurora_endpoint" {
  type        = string
  description = "Aurora cluster endpoint"
}

variable "aurora_port" {
  type        = number
  description = "Aurora port"
  default     = 3306
}

variable "aurora_database" {
  type        = string
  description = "Aurora database name"
  default     = "tokyobeta"
}

variable "aurora_username" {
  type        = string
  description = "Aurora username for QuickSight"
}

variable "aurora_password" {
  type        = string
  description = "Aurora password for QuickSight"
  sensitive   = true
}

variable "security_group_ids" {
  type        = list(string)
  description = "Security group IDs for VPC connection"
}

variable "subnet_ids" {
  type        = list(string)
  description = "Subnet IDs for VPC connection (private subnets)"
}

variable "enable_spice_refresh" {
  type        = bool
  description = "Enable automatic SPICE dataset refresh"
  default     = false
}

variable "spice_refresh_schedule" {
  type        = string
  description = "CloudWatch Events schedule for SPICE refresh (cron format)"
  default     = "cron(0 23 * * ? *)"  # 8:00 AM JST = 23:00 UTC
}

variable "spice_dataset_ids" {
  type        = string
  description = "Comma-separated list of QuickSight dataset IDs to refresh"
  default     = ""
}
