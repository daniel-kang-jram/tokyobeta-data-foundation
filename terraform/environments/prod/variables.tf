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

variable "alert_emails" {
  description = "Additional email addresses for monitoring alerts"
  type        = list(string)
  default     = []
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to access Aurora MySQL (external access)"
  type        = list(string)
  default = [
    "85.115.98.80/32" # Current admin IP - update if your IP changes
  ]
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
