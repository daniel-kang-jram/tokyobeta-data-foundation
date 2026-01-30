# Secrets Module Variables

variable "environment" {
  description = "Environment name (dev/prod)"
  type        = string
}

variable "db_username" {
  description = "Master username for Aurora"
  type        = string
  default     = "admin"
}

# RDS Cron Job Credentials Variables
variable "create_rds_cron_secret" {
  type        = bool
  description = "Whether to create RDS cron job credentials secret"
  default     = false
}

variable "rds_cron_host" {
  type        = string
  description = "RDS hostname for cron job database dumps"
  default     = ""
}

variable "rds_cron_username" {
  type        = string
  description = "RDS username for cron jobs"
  default     = "readonly_user"
}

variable "rds_cron_password" {
  type        = string
  description = "RDS password (leave empty to auto-generate)"
  default     = ""
  sensitive   = true
}

variable "rds_cron_database" {
  type        = string
  description = "RDS database name for dumps"
  default     = "gghouse"
}

variable "rds_cron_port" {
  type        = number
  description = "RDS port number"
  default     = 3306
}
