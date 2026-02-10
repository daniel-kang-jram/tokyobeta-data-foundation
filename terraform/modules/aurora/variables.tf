# Aurora Module Variables

variable "environment" {
  description = "Environment name (dev/prod)"
  type        = string
}

variable "vpc_id" {
  description = "ID of the VPC"
  type        = string
}

variable "subnet_ids" {
  description = "IDs of subnets for Aurora"
  type        = list(string)
}

variable "security_group_id" {
  description = "Security group ID for Aurora"
  type        = string
}

variable "db_username" {
  description = "Master username for Aurora"
  type        = string
}

variable "db_password" {
  description = "Master password for Aurora"
  type        = string
  sensitive   = true
}

variable "instance_class" {
  description = "Instance class for Aurora"
  type        = string
  default     = "db.t4g.medium"

  validation {
    condition     = can(regex("^db\\.", var.instance_class))
    error_message = "Instance class must start with 'db.'"
  }
}

variable "instance_count" {
  description = "Number of Aurora instances"
  type        = number
  default     = 2

  validation {
    condition     = var.instance_count >= 1 && var.instance_count <= 15
    error_message = "Instance count must be between 1 and 15"
  }
}

variable "publicly_accessible" {
  description = "Whether Aurora instances are publicly accessible"
  type        = bool
  default     = false
}

variable "backup_retention_period" {
  description = "Number of days to retain backups"
  type        = number
  default     = 7

  validation {
    condition     = var.backup_retention_period >= 1 && var.backup_retention_period <= 35
    error_message = "Backup retention must be between 1 and 35 days"
  }
}

variable "enable_deletion_protection" {
  description = "Enable deletion protection for production"
  type        = bool
  default     = false
}
