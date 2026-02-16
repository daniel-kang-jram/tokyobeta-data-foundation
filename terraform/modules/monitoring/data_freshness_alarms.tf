# Data Freshness CloudWatch Alarms
# Monitors staging table freshness to prevent stale data issues

# Lambda function to check table freshness
resource "aws_lambda_function" "check_table_freshness" {
  filename         = data.archive_file.freshness_checker_zip.output_path
  function_name    = "${var.project_name}-${var.environment}-table-freshness-checker"
  role             = aws_iam_role.freshness_checker_role.arn
  handler          = "freshness_checker.lambda_handler"
  source_code_hash = data.archive_file.freshness_checker_zip.output_base64sha256
  runtime          = "python3.11"
  timeout          = 60

  environment {
    variables = {
      AURORA_ENDPOINT              = var.aurora_endpoint
      AURORA_SECRET_ARN            = var.aurora_secret_arn
      SNS_TOPIC_ARN                = aws_sns_topic.etl_alerts.arn
      S3_BUCKET                    = var.s3_bucket
      S3_DUMP_PREFIXES             = var.s3_dump_prefixes
      S3_DUMP_MIN_BYTES            = var.s3_dump_min_bytes
      S3_DUMP_ERROR_DAYS           = var.s3_dump_error_days
      S3_DUMP_REQUIRE_ALL_PREFIXES = var.s3_dump_require_all_prefixes ? "true" : "false"
    }
  }

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [var.security_group_id]
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-freshness-checker"
    Environment = var.environment
  }
}

# Archive Lambda function code
data "archive_file" "freshness_checker_zip" {
  type        = "zip"
  output_path = "${path.module}/freshness_checker.zip"

  source {
    content = templatefile("${path.module}/lambda/freshness_checker.py", {
      tables = ["movings", "tenants", "rooms", "inquiries", "apartments"]
    })
    filename = "freshness_checker.py"
  }
}

# IAM Role for Lambda
resource "aws_iam_role" "freshness_checker_role" {
  name = "${var.project_name}-${var.environment}-freshness-checker-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# IAM Policy for Lambda
resource "aws_iam_role_policy" "freshness_checker_policy" {
  name = "${var.project_name}-${var.environment}-freshness-checker-policy"
  role = aws_iam_role.freshness_checker_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [var.aurora_secret_arn]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetObject",
          "s3:HeadObject",
          "sns:Publish"
        ]
        Resource = [
          "arn:aws:s3:::${var.s3_bucket}",
          "arn:aws:s3:::${var.s3_bucket}/*",
          aws_sns_topic.etl_alerts.arn,
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = ["arn:aws:logs:*:*:*"]
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface"
        ]
        Resource = ["*"]
      }
    ]
  })
}

# EventBridge rule to trigger freshness check (daily at 9 AM JST = 00:00 UTC)
resource "aws_cloudwatch_event_rule" "check_freshness_daily" {
  name                = "${var.project_name}-${var.environment}-check-freshness-daily"
  description         = "Check staging table freshness daily"
  schedule_expression = "cron(0 0 * * ? *)" # 9 AM JST

  tags = {
    Name        = "${var.project_name}-${var.environment}-freshness-checker"
    Environment = var.environment
  }
}

# EventBridge rule to trigger post-dump check (daily at 6 AM JST = 21:00 UTC)
resource "aws_cloudwatch_event_rule" "check_freshness_post_dump" {
  name                = "${var.project_name}-${var.environment}-check-freshness-post-dump"
  description         = "Check dump availability shortly after dump schedule"
  schedule_expression = "cron(0 21 * * ? *)"

  tags = {
    Name        = "${var.project_name}-${var.environment}-freshness-post-dump"
    Environment = var.environment
  }
}

# EventBridge target
resource "aws_cloudwatch_event_target" "freshness_checker_lambda" {
  rule      = aws_cloudwatch_event_rule.check_freshness_daily.name
  target_id = "FreshnessCheckerLambda"
  arn       = aws_lambda_function.check_table_freshness.arn
}

resource "aws_cloudwatch_event_target" "freshness_checker_lambda_post_dump" {
  rule      = aws_cloudwatch_event_rule.check_freshness_post_dump.name
  target_id = "FreshnessCheckerLambdaPostDump"
  arn       = aws_lambda_function.check_table_freshness.arn
}

# Lambda permission for EventBridge
resource "aws_lambda_permission" "allow_eventbridge_freshness" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.check_table_freshness.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.check_freshness_daily.arn
}

resource "aws_lambda_permission" "allow_eventbridge_freshness_post_dump" {
  statement_id  = "AllowExecutionFromEventBridgePostDump"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.check_table_freshness.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.check_freshness_post_dump.arn
}

# CloudWatch Metric Alarm - Staging Movings Freshness
resource "aws_cloudwatch_metric_alarm" "staging_movings_stale" {
  alarm_name          = "${var.project_name}-${var.environment}-staging-movings-stale"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "StagingMovingsDaysOld"
  namespace           = "TokyoBeta/DataQuality"
  period              = 3600 # Check every hour
  statistic           = "Maximum"
  threshold           = 2 # Alert if > 2 days old
  alarm_description   = "Staging movings table is more than 2 days old"
  alarm_actions       = [aws_sns_topic.etl_alerts.arn]
  treat_missing_data  = "breaching" # Treat missing data as stale

  tags = {
    Name        = "${var.project_name}-${var.environment}-staging-freshness"
    Environment = var.environment
  }
}

# CloudWatch Metric Alarm - Staging Tenants Freshness
resource "aws_cloudwatch_metric_alarm" "staging_tenants_stale" {
  alarm_name          = "${var.project_name}-${var.environment}-staging-tenants-stale"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "StagingTenantsDaysOld"
  namespace           = "TokyoBeta/DataQuality"
  period              = 3600
  statistic           = "Maximum"
  threshold           = 2
  alarm_description   = "Staging tenants table is more than 2 days old"
  alarm_actions       = [aws_sns_topic.etl_alerts.arn]
  treat_missing_data  = "breaching"

  tags = {
    Name        = "${var.project_name}-${var.environment}-staging-freshness"
    Environment = var.environment
  }
}

# Output alarm ARNs
output "freshness_alarm_arns" {
  description = "ARNs of data freshness alarms"
  value = {
    movings = aws_cloudwatch_metric_alarm.staging_movings_stale.arn
    tenants = aws_cloudwatch_metric_alarm.staging_tenants_stale.arn
  }
}

output "freshness_checker_function_arn" {
  description = "ARN of freshness checker Lambda function"
  value       = aws_lambda_function.check_table_freshness.arn
}
