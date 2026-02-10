# EventBridge Module Variables

variable "environment" {
  description = "Environment name (dev/prod)"
  type        = string
}

variable "glue_job_name" {
  description = "Name of the Glue job to trigger"
  type        = string
}

variable "glue_job_arn" {
  description = "ARN of the Glue job"
  type        = string
}

variable "schedule_expression" {
  description = "Cron expression for daily trigger (JST 7:00 AM = UTC 22:00 previous day)"
  type        = string
  default     = "cron(0 22 * * ? *)" # 7:00 AM JST = 10:00 PM UTC (UTC+9)
}
