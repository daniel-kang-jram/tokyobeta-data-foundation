# EventBridge Module
# Creates EventBridge rule to trigger Lambda (which starts Glue job)
# Note: EventBridge cannot directly trigger Glue jobs, only workflows

# Lambda function to trigger Glue
resource "aws_lambda_function" "glue_trigger" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "tokyobeta-${var.environment}-glue-trigger"
  role             = aws_iam_role.lambda_glue_trigger.arn
  handler          = "trigger_glue.handler"
  runtime          = "python3.11"
  timeout          = 60
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  environment {
    variables = {
      GLUE_JOB_NAME = var.glue_job_name
    }
  }

  tags = {
    Name        = "tokyobeta-${var.environment}-glue-trigger"
    Environment = var.environment
  }
}

# Package Lambda code
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/../../../glue/scripts/trigger_glue.py"
  output_path = "${path.module}/trigger_glue.zip"
}

# IAM Role for Lambda
resource "aws_iam_role" "lambda_glue_trigger" {
  name = "tokyobeta-${var.environment}-lambda-glue-trigger-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = {
    Name        = "tokyobeta-${var.environment}-lambda-glue-trigger"
    Environment = var.environment
  }
}

# Lambda policy to start Glue jobs
resource "aws_iam_role_policy" "lambda_glue_trigger" {
  name = "tokyobeta-${var.environment}-lambda-glue-policy"
  role = aws_iam_role.lambda_glue_trigger.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "glue:StartJobRun"
        ]
        Resource = [var.glue_job_arn]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = ["arn:aws:logs:*:*:*"]
      }
    ]
  })
}

# Lambda permission for EventBridge to invoke
resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.glue_trigger.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_etl_trigger.arn
}

# EventBridge Rule for daily trigger
resource "aws_cloudwatch_event_rule" "daily_etl_trigger" {
  name                = "tokyobeta-${var.environment}-daily-etl-trigger"
  description         = "Trigger Lambda to start Glue ETL job daily at 7:00 AM JST"
  schedule_expression = var.schedule_expression

  tags = {
    Name        = "tokyobeta-${var.environment}-daily-trigger"
    Environment = var.environment
  }
}

# EventBridge Target (Lambda function)
resource "aws_cloudwatch_event_target" "lambda_trigger" {
  rule      = aws_cloudwatch_event_rule.daily_etl_trigger.name
  target_id = "TriggerLambda"
  arn       = aws_lambda_function.glue_trigger.arn
}
