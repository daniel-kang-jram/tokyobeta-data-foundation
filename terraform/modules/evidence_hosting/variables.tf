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
