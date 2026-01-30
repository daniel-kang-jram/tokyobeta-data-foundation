# EventBridge Module
# Creates EventBridge rule to trigger Glue ETL job daily

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

