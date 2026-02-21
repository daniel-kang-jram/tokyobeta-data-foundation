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

variable "artifact_release" {
  description = "Immutable release identifier for Glue/dbt artifacts in S3"
  type        = string
  default     = "legacy"

  validation {
    condition     = length(trimspace(var.artifact_release)) > 0
    error_message = "artifact_release must be non-empty."
  }
}

variable "alert_email" {
  description = "Email address for monitoring alerts"
  type        = string
}

variable "alert_emails" {
  description = "Additional email addresses for monitoring alerts"
  type        = list(string)
  default = [
    "daniel.kang@jram.jp"
  ]
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to access Aurora MySQL (external access)"
  type        = list(string)
  default = [
    "85.115.98.80/32",   # Current admin IP - update if your IP changes
    "13.112.83.65/32",   # EC2 dump host EIP
    "54.168.114.197/32", # V3 upstream sync source IP
  ]

  validation {
    condition     = contains(var.allowed_cidr_blocks, "13.112.83.65/32")
    error_message = "allowed_cidr_blocks must include 13.112.83.65/32 (EC2 dump host EIP)."
  }

  validation {
    condition     = contains(var.allowed_cidr_blocks, "54.168.114.197/32")
    error_message = "allowed_cidr_blocks must include 54.168.114.197/32 (V3 upstream sync source IP)."
  }
}

variable "create_rds_cron_secret" {
  description = "Whether to manage production dump-source cron secret in Terraform"
  type        = bool
  default     = false

  validation {
    condition     = var.create_rds_cron_secret == false
    error_message = "Production must keep create_rds_cron_secret=false to avoid cron secret drift."
  }
}

variable "manage_rds_cron_secret_value" {
  description = "Whether Terraform may rotate production dump-source secret value"
  type        = bool
  default     = false

  validation {
    condition     = var.manage_rds_cron_secret_value == false
    error_message = "Production must keep manage_rds_cron_secret_value=false to prevent dump source drift."
  }
}

variable "rds_cron_host" {
  description = "Dump source host for production cron secret"
  type        = string
  default     = ""
}

variable "rds_cron_username" {
  description = "Dump source username for production cron secret"
  type        = string
  default     = ""
}

variable "rds_cron_password" {
  description = "Optional explicit dump-source password. Leave blank to reuse Aurora admin password."
  type        = string
  default     = ""
  sensitive   = true
}

variable "rds_cron_database" {
  description = "Dump source database/schema for production cron secret"
  type        = string
  default     = ""
}

variable "rds_cron_port" {
  description = "Dump source port for production cron secret"
  type        = number
  default     = 3306
}

# Evidence hosting (CloudFront + S3 + Cognito)
variable "evidence_custom_domain" {
  description = "Custom domain for hosted Evidence app"
  type        = string
  default     = "evidence.jram.jp"
}

variable "evidence_enable_custom_domain" {
  description = "If true, attach evidence_custom_domain + ACM cert to CloudFront. Set true after DNS validation CNAME is in place."
  type        = bool
  default     = false
}

variable "evidence_auth_base_url" {
  description = "Base URL used for Cognito callbacks (CloudFront URL until custom domain is ready)"
  type        = string
  default     = "https://d2lnx09sw8wka0.cloudfront.net"
}

variable "evidence_enable_auth" {
  description = "Enable HTTP Basic Auth on CloudFront (set false to allow unauthenticated access)"
  type        = bool
  default     = true
}

variable "evidence_auth_users" {
  description = "Map of username to password for HTTP Basic Auth (keep this secure!)"
  type        = map(string)
  default     = {}
  sensitive   = true
}

variable "evidence_cognito_domain_prefix" {
  description = "Cognito hosted UI domain prefix (must be unique in region)"
  type        = string
  default     = "tokyobeta-prod-evidence"
}

variable "evidence_codestar_connection_arn" {
  description = "CodeStar connection ARN for scheduled CodeBuild refresh"
  type        = string
  default     = "arn:aws:codestar-connections:ap-northeast-1:343881458651:connection/c800e762-0967-4d1b-aa8f-2b5fd17bf97c"
}

variable "evidence_repo_full_name" {
  description = "GitHub repo full name (owner/repo) for CodeBuild source"
  type        = string
  default     = "daniel-kang-jram/tokyobeta-data-foundation"
}

variable "evidence_repo_branch" {
  description = "Branch to build Evidence from"
  type        = string
  default     = "main"
}

variable "evidence_snapshot_custom_domain" {
  description = "Custom domain for hosted snapshot Evidence app"
  type        = string
  default     = "evidence-snapshot.jram.jp"
}

variable "evidence_snapshot_enable_custom_domain" {
  description = "Attach snapshot custom domain + ACM cert"
  type        = bool
  default     = false
}

variable "evidence_snapshot_auth_base_url" {
  description = "Base URL used for snapshot app auth callbacks"
  type        = string
  default     = null
}

variable "evidence_snapshot_enable_auth" {
  description = "Enable HTTP Basic Auth for snapshot dashboard"
  type        = bool
  default     = true
}

variable "evidence_snapshot_auth_users" {
  description = "Map of username to password for snapshot Basic Auth"
  type        = map(string)
  default     = {}
  sensitive   = true
}

variable "evidence_snapshot_cognito_domain_prefix" {
  description = "Cognito domain prefix for snapshot Evidence app"
  type        = string
  default     = "tokyobeta-prod-evidence-snapshot"
}

variable "evidence_snapshot_codestar_connection_arn" {
  description = "CodeStar connection ARN for snapshot builds"
  type        = string
  default     = "arn:aws:codestar-connections:ap-northeast-1:343881458651:connection/c800e762-0967-4d1b-aa8f-2b5fd17bf97c"
}

variable "evidence_snapshot_repo_full_name" {
  description = "GitHub repo full name for snapshot dashboard build"
  type        = string
  default     = "daniel-kang-jram/tokyobeta-data-foundation"
}

variable "evidence_snapshot_repo_branch" {
  description = "Branch for snapshot dashboard build"
  type        = string
  default     = "main"
}
