# AWS Step Functions Module
# Orchestrates ETL workflow: Staging → Silver → Gold with granular retry logic

# IAM Role for Step Functions
resource "aws_iam_role" "step_functions_role" {
  name = "tokyobeta-${var.environment}-step-functions-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "states.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "tokyobeta-${var.environment}-step-functions-role"
    Environment = var.environment
  }
}

# IAM Policy for Step Functions
resource "aws_iam_role_policy" "step_functions_policy" {
  name = "tokyobeta-${var.environment}-step-functions-policy"
  role = aws_iam_role.step_functions_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "glue:StartJobRun",
          "glue:GetJobRun",
          "glue:GetJobRuns",
          "glue:BatchStopJobRun"
        ]
        Resource = [
          var.staging_loader_arn,
          var.silver_transformer_arn,
          var.gold_transformer_arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = [var.sns_topic_arn]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogDelivery",
          "logs:GetLogDelivery",
          "logs:UpdateLogDelivery",
          "logs:DeleteLogDelivery",
          "logs:ListLogDeliveries",
          "logs:PutLogEvents",
          "logs:PutResourcePolicy",
          "logs:DescribeResourcePolicies",
          "logs:DescribeLogGroups"
        ]
        Resource = ["*"]
      }
    ]
  })
}

# CloudWatch Log Group for Step Functions
resource "aws_cloudwatch_log_group" "step_functions_logs" {
  name              = "/aws/states/tokyobeta-${var.environment}-etl-orchestrator"
  retention_in_days = 7

  tags = {
    Name        = "tokyobeta-${var.environment}-step-functions-logs"
    Environment = var.environment
  }
}

# Step Functions State Machine
resource "aws_sfn_state_machine" "etl_orchestrator" {
  name     = "tokyobeta-${var.environment}-etl-orchestrator"
  role_arn = aws_iam_role.step_functions_role.arn

  definition = jsonencode({
    Comment = "ETL Orchestrator - Staging → Silver → Gold with granular retry and failure isolation"
    StartAt = "StagingLoader"
    States = {
      StagingLoader = {
        Type     = "Task"
        Resource = "arn:aws:states:::glue:startJobRun.sync"
        Parameters = {
          JobName = var.staging_loader_name
        }
        Retry = [
          {
            ErrorEquals     = ["States.TaskFailed"]
            IntervalSeconds = 300
            MaxAttempts     = 2
            BackoffRate     = 2.0
          }
        ]
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            ResultPath  = "$.error"
            Next        = "NotifyStagingFailure"
          }
        ]
        ResultPath = "$.staging"
        Next       = "SilverTransformer"
      }

      SilverTransformer = {
        Type     = "Task"
        Resource = "arn:aws:states:::glue:startJobRun.sync"
        Parameters = {
          JobName = var.silver_transformer_name
        }
        Retry = [
          {
            ErrorEquals     = ["States.TaskFailed"]
            IntervalSeconds = 60
            MaxAttempts     = 3
            BackoffRate     = 1.5
          }
        ]
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            ResultPath  = "$.error"
            Next        = "NotifySilverFailure"
          }
        ]
        ResultPath = "$.silver"
        Next       = "GoldTransformer"
      }

      GoldTransformer = {
        Type     = "Task"
        Resource = "arn:aws:states:::glue:startJobRun.sync"
        Parameters = {
          JobName = var.gold_transformer_name
        }
        Retry = [
          {
            ErrorEquals     = ["States.TaskFailed"]
            IntervalSeconds = 60
            MaxAttempts     = 3
            BackoffRate     = 1.5
          }
        ]
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            ResultPath  = "$.error"
            Next        = "NotifyGoldFailure"
          }
        ]
        ResultPath = "$.gold"
        Next       = "NotifySuccess"
      }

      NotifySuccess = {
        Type     = "Task"
        Resource = "arn:aws:states:::sns:publish"
        Parameters = {
          TopicArn = var.sns_topic_arn
          Subject  = "ETL Success - All Layers Completed"
          Message  = "ETL completed successfully. Check CloudWatch logs for details."
        }
        End = true
      }

      NotifyStagingFailure = {
        Type     = "Task"
        Resource = "arn:aws:states:::sns:publish"
        Parameters = {
          TopicArn = var.sns_topic_arn
          Subject  = "ETL Failed - Staging Layer"
          Message  = "Staging loader failed after 2 retries. Please check CloudWatch logs for details."
        }
        End = true
      }

      NotifySilverFailure = {
        Type     = "Task"
        Resource = "arn:aws:states:::sns:publish"
        Parameters = {
          TopicArn = var.sns_topic_arn
          Subject  = "ETL Failed - Silver Layer"
          Message  = "Silver transformer failed after 3 retries. Staging completed successfully. You can manually retry silver layer only."
        }
        End = true
      }

      NotifyGoldFailure = {
        Type     = "Task"
        Resource = "arn:aws:states:::sns:publish"
        Parameters = {
          TopicArn = var.sns_topic_arn
          Subject  = "ETL Failed - Gold Layer"
          Message  = "Gold transformer failed after 3 retries. Staging and Silver completed successfully. You can manually retry gold layer only."
        }
        End = true
      }
    }
  })

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.step_functions_logs.arn}:*"
    include_execution_data = true
    level                  = "ALL"
  }

  tags = {
    Name        = "tokyobeta-${var.environment}-etl-orchestrator"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
