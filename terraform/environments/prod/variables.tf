# Production Environment Variables

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

variable "alert_email" {
  description = "Email address for monitoring alerts"
  type        = string
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to access Aurora MySQL (external access)"
  type        = list(string)
  default     = [
    "85.115.98.80/32"  # Current admin IP - update if your IP changes
  ]
}
