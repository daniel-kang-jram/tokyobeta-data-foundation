variable "environment" {
  description = "Environment name (e.g. prod)"
  type        = string
}

variable "project_name" {
  description = "Project name prefix for resources"
  type        = string
}

variable "custom_domain_name" {
  description = "Custom domain for the Evidence app (e.g. evidence.jram.jp)"
  type        = string
}

variable "auth_base_url" {
  description = "Base URL used for Cognito callback/logout (e.g. https://dxxxx.cloudfront.net or https://evidence.jram.jp)"
  type        = string
  default     = null
}

variable "enable_auth" {
  description = "If true, enable HTTP Basic Auth via CloudFront Functions"
  type        = bool
  default     = true
}

variable "auth_users" {
  description = "Map of username to password for HTTP Basic Auth. Store in tfvars, not in code!"
  type        = map(string)
  default     = {}
  sensitive   = true
}

variable "auth_ui_mode" {
  description = "Authentication UI mode: browser popup basic auth or branded login page"
  type        = string
  default     = "browser_basic"

  validation {
    condition     = contains(["browser_basic", "login_page"], var.auth_ui_mode)
    error_message = "auth_ui_mode must be one of: browser_basic, login_page."
  }
}

variable "auth_session_max_age_seconds" {
  description = "Session cookie TTL in seconds for login_page auth mode"
  type        = number
  default     = 28800

  validation {
    condition     = var.auth_session_max_age_seconds >= 300 && var.auth_session_max_age_seconds <= 86400
    error_message = "auth_session_max_age_seconds must be between 300 and 86400."
  }
}

variable "auth_login_copy_language" {
  description = "Copy language for branded login page"
  type        = string
  default     = "en"

  validation {
    condition     = contains(["en", "ja", "bilingual"], var.auth_login_copy_language)
    error_message = "auth_login_copy_language must be one of: en, ja, bilingual."
  }
}

variable "enable_custom_domain" {
  description = "If true, attach custom domain + ACM cert to CloudFront. Keep false until DNS validation completes."
  type        = bool
  default     = false
}

variable "cognito_domain_prefix" {
  description = "Cognito hosted UI domain prefix (must be globally unique per region)"
  type        = string
}

variable "evidence_repo_connection_arn" {
  description = "ARN of CodeStar Connections connection to the repo (manual approval required)"
  type        = string
  default     = null
}

variable "evidence_repo_full_name" {
  description = "Repo full name (e.g. owner/repo) used for CodeBuild source"
  type        = string
  default     = null
}

variable "evidence_repo_branch" {
  description = "Branch to build from"
  type        = string
  default     = "main"
}

variable "aurora_evidence_secret_id" {
  description = "Secrets Manager secret id for Evidence read-only Aurora credentials"
  type        = string
  default     = "tokyobeta/prod/aurora/evidence_ro"
}

variable "vpc_id" {
  description = "VPC id for CodeBuild VPC config"
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnet ids for CodeBuild VPC config"
  type        = list(string)
}

variable "codebuild_security_group_id" {
  description = "Security group id for CodeBuild to reach Aurora"
  type        = string
}

variable "schedule_expression" {
  description = "EventBridge schedule expression for daily refresh"
  type        = string
  default     = "cron(30 23 * * ? *)" # 08:30 JST = 23:30 UTC
}

variable "buildspec_path" {
  description = "Repository path to buildspec used by CodeBuild"
  type        = string
  default     = "evidence/buildspec.yml"
}

variable "enable_schedule" {
  description = "Enable EventBridge schedule for automatic refresh"
  type        = bool
  default     = true
}
