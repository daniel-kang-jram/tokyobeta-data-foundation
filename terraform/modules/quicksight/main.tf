# QuickSight Module
# Manages QuickSight data sources and dashboard deployments

# Data source: Get current AWS account ID
data "aws_caller_identity" "current" {}

# Data source: Get current AWS region
data "aws_region" "current" {}

# QuickSight Data Source for Aurora MySQL
resource "aws_quicksight_data_source" "aurora_analytics" {
  data_source_id = "${var.environment}-tokyobeta-analytics"
  name           = "Tokyo Beta Analytics (${upper(var.environment)})"
  type           = "AURORA"

  parameters {
    aurora {
      host     = var.aurora_endpoint
      port     = var.aurora_port
      database = var.aurora_database
    }
  }

  credentials {
    credential_pair {
      username = var.aurora_username
      password = var.aurora_password
    }
  }

  vpc_connection_properties {
    vpc_connection_arn = aws_quicksight_vpc_connection.aurora_vpc.arn
  }

  ssl_properties {
    disable_ssl = false
  }

  tags = {
    Name        = "tokyobeta-${var.environment}-aurora-datasource"
    Environment = var.environment
  }
}

# QuickSight VPC Connection to Aurora
resource "aws_quicksight_vpc_connection" "aurora_vpc" {
  vpc_connection_id = "${var.environment}-aurora-vpc-connection"
  name              = "Aurora VPC Connection (${upper(var.environment)})"
  role_arn          = aws_iam_role.quicksight_vpc_connection.arn

  security_group_ids = var.security_group_ids
  subnet_ids         = var.subnet_ids

  tags = {
    Name        = "tokyobeta-${var.environment}-vpc-connection"
    Environment = var.environment
  }
}

# IAM Role for QuickSight VPC Connection
resource "aws_iam_role" "quicksight_vpc_connection" {
  name = "tokyobeta-${var.environment}-quicksight-vpc-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "quicksight.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "tokyobeta-${var.environment}-quicksight-vpc-role"
    Environment = var.environment
  }
}

# IAM Policy for QuickSight VPC Access
resource "aws_iam_role_policy" "quicksight_vpc_policy" {
  name = "quicksight-vpc-access"
  role = aws_iam_role.quicksight_vpc_connection.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:ModifyNetworkInterfaceAttribute",
          "ec2:DeleteNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DescribeSecurityGroups",
          "ec2:DescribeSubnets",
          "ec2:DescribeVpcs"
        ]
        Resource = "*"
      }
    ]
  })
}

# QuickSight Data Sets (Managed separately via JSON templates)
# These are created via the aws_quicksight_data_set resource or CLI
# See quicksight/datasets/ directory for JSON definitions

# Dashboard resources are managed via JSON templates
# See quicksight/dashboards/ directory for definitions
# Use the automation script to deploy: scripts/deploy_quicksight_dashboards.py

# SPICE Refresh Schedule (daily at 8:00 AM JST = 23:00 UTC)
# Note: This requires datasets to be created first
resource "aws_cloudwatch_event_rule" "quicksight_refresh" {
  count               = var.enable_spice_refresh ? 1 : 0
  name                = "tokyobeta-${var.environment}-quicksight-refresh"
  description         = "Trigger QuickSight SPICE dataset refresh daily"
  schedule_expression = var.spice_refresh_schedule

  tags = {
    Name        = "tokyobeta-${var.environment}-quicksight-refresh"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_event_target" "quicksight_refresh_lambda" {
  count = var.enable_spice_refresh ? 1 : 0
  rule  = aws_cloudwatch_event_rule.quicksight_refresh[0].name
  arn   = aws_lambda_function.spice_refresh[0].arn
}

# Lambda function to refresh SPICE datasets
resource "aws_lambda_function" "spice_refresh" {
  count         = var.enable_spice_refresh ? 1 : 0
  filename      = "${path.module}/lambda/spice_refresh.zip"
  function_name = "tokyobeta-${var.environment}-spice-refresh"
  role          = aws_iam_role.spice_refresh_lambda[0].arn
  handler       = "index.handler"
  runtime       = "python3.11"
  timeout       = 300

  environment {
    variables = {
      QUICKSIGHT_AWS_ACCOUNT_ID = data.aws_caller_identity.current.account_id
      QUICKSIGHT_DATASET_IDS    = var.spice_dataset_ids
    }
  }

  tags = {
    Name        = "tokyobeta-${var.environment}-spice-refresh"
    Environment = var.environment
  }
}

# IAM Role for SPICE Refresh Lambda
resource "aws_iam_role" "spice_refresh_lambda" {
  count = var.enable_spice_refresh ? 1 : 0
  name  = "tokyobeta-${var.environment}-spice-refresh-lambda"

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

  tags = {
    Name        = "tokyobeta-${var.environment}-spice-refresh-lambda"
    Environment = var.environment
  }
}

# IAM Policy for SPICE Refresh Lambda
resource "aws_iam_role_policy" "spice_refresh_lambda_policy" {
  count = var.enable_spice_refresh ? 1 : 0
  name  = "spice-refresh-policy"
  role  = aws_iam_role.spice_refresh_lambda[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "quicksight:CreateIngestion",
          "quicksight:DescribeIngestion",
          "quicksight:ListDataSets"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# Lambda permission for CloudWatch Events
resource "aws_lambda_permission" "allow_cloudwatch" {
  count         = var.enable_spice_refresh ? 1 : 0
  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.spice_refresh[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.quicksight_refresh[0].arn
}
