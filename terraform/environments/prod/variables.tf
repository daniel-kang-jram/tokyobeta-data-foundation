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
