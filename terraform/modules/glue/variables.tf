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

variable "daily_strict_dump_continuity" {
  description = "Whether daily_etl should fail on missing dump dates"
  type        = bool
  default     = false
}

variable "daily_skip_llm_enrichment" {
  description = "Whether daily_etl should skip LLM enrichment step"
  type        = bool
  default     = false
}

variable "daily_llm_nationality_max_batch" {
  description = "Max tenant records to enrich for nationality per run"
  type        = number
  default     = 300

  validation {
    condition     = var.daily_llm_nationality_max_batch >= 1
    error_message = "daily_llm_nationality_max_batch must be >= 1."
  }
}

variable "daily_llm_municipality_max_batch" {
  description = "Max property records to enrich for municipality per run"
  type        = number
  default     = 150

  validation {
    condition     = var.daily_llm_municipality_max_batch >= 0
    error_message = "daily_llm_municipality_max_batch must be >= 0."
  }
}

variable "daily_llm_requests_per_second" {
  description = "LLM request rate limit per second"
  type        = number
  default     = 3

  validation {
    condition     = var.daily_llm_requests_per_second >= 1
    error_message = "daily_llm_requests_per_second must be >= 1."
  }
}

variable "daily_llm_fail_on_error" {
  description = "Whether daily_etl should fail when LLM enrichment fails"
  type        = bool
  default     = false
}

variable "artifact_release" {
  description = "Immutable artifact release identifier used for Glue scripts and dbt project paths"
  type        = string
  default     = "legacy"
}
