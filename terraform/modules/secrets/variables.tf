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
