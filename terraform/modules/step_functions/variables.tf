# Step Functions Module Variables

variable "environment" {
  description = "Environment name (prod, dev)"
  type        = string
}

variable "staging_loader_name" {
  description = "Name of staging loader Glue job"
  type        = string
}

variable "staging_loader_arn" {
  description = "ARN of staging loader Glue job"
  type        = string
}

variable "silver_transformer_name" {
  description = "Name of silver transformer Glue job"
  type        = string
}

variable "silver_transformer_arn" {
  description = "ARN of silver transformer Glue job"
  type        = string
}

variable "gold_transformer_name" {
  description = "Name of gold transformer Glue job"
  type        = string
}

variable "gold_transformer_arn" {
  description = "ARN of gold transformer Glue job"
  type        = string
}

variable "data_quality_test_name" {
  description = "Name of data quality test Glue job"
  type        = string
}

variable "data_quality_test_arn" {
  description = "ARN of data quality test Glue job"
  type        = string
}

variable "sns_topic_arn" {
  description = "ARN of SNS topic for notifications"
  type        = string
}
