# EventBridge Module
# Creates EventBridge rule to trigger Glue ETL job daily

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
  default     = "cron(0 22 * * ? *)"  # 7:00 AM JST = 10:00 PM UTC (UTC+9)
}

# IAM Role for EventBridge to invoke Glue
resource "aws_iam_role" "eventbridge_glue" {
  name = "tokyobeta-${var.environment}-eventbridge-glue-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "tokyobeta-${var.environment}-eventbridge-role"
    Environment = var.environment
  }
}

# IAM Policy for EventBridge to start Glue jobs
resource "aws_iam_role_policy" "eventbridge_glue" {
  name = "tokyobeta-${var.environment}-eventbridge-glue-policy"
  role = aws_iam_role.eventbridge_glue.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "glue:StartJobRun"
        ]
        Resource = [var.glue_job_arn]
      }
    ]
  })
}

# EventBridge Rule for daily trigger
resource "aws_cloudwatch_event_rule" "daily_etl_trigger" {
  name                = "tokyobeta-${var.environment}-daily-etl-trigger"
  description         = "Trigger Glue ETL job daily at 7:00 AM JST"
  schedule_expression = var.schedule_expression
  
  tags = {
    Name        = "tokyobeta-${var.environment}-daily-trigger"
    Environment = var.environment
  }
}

# EventBridge Target (Glue job)
resource "aws_cloudwatch_event_target" "glue_job" {
  rule      = aws_cloudwatch_event_rule.daily_etl_trigger.name
  target_id = "TriggerGlueETL"
  arn       = var.glue_job_arn
  role_arn  = aws_iam_role.eventbridge_glue.arn
}

# Outputs
output "rule_name" {
  description = "Name of the EventBridge rule"
  value       = aws_cloudwatch_event_rule.daily_etl_trigger.name
}

output "rule_arn" {
  description = "ARN of the EventBridge rule"
  value       = aws_cloudwatch_event_rule.daily_etl_trigger.arn
}

output "schedule_expression" {
  description = "Schedule expression for the rule"
  value       = aws_cloudwatch_event_rule.daily_etl_trigger.schedule_expression
}
