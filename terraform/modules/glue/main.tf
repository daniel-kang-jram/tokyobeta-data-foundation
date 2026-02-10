# AWS Glue Module
# Creates Glue crawler, ETL jobs, and data quality rulesets

# IAM Role for Glue
resource "aws_iam_role" "glue_service_role" {
  name = "tokyobeta-${var.environment}-glue-service-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "glue.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "tokyobeta-${var.environment}-glue-role"
    Environment = var.environment
  }
}

# IAM Policy for Glue
resource "aws_iam_role_policy" "glue_service_policy" {
  name = "tokyobeta-${var.environment}-glue-policy"
  role = aws_iam_role.glue_service_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket",
          "s3:PutObject"
        ]
        Resource = [
          "arn:aws:s3:::${var.s3_source_bucket}",
          "arn:aws:s3:::${var.s3_source_bucket}/*"
        ]
      },
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
          "rds:DescribeDBClusterSnapshots",
          "rds:CreateDBClusterSnapshot",
          "rds:DeleteDBClusterSnapshot",
          "rds:DescribeDBClusters",
          "rds:ListTagsForResource"
        ]
        Resource = ["*"]
        Condition = {
          StringLike = {
            "rds:cluster-tag/ManagedBy" = "terraform"
          }
        }
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = ["arn:aws:logs:*:*:/aws-glue/*"]
      },
      {
        Effect = "Allow"
        Action = [
          "glue:*"
        ]
        Resource = ["*"]
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface",
          "ec2:DescribeVpcEndpoints",
          "ec2:DescribeSubnets",
          "ec2:DescribeVpcAttribute",
          "ec2:DescribeRouteTables",
          "ec2:DescribeSecurityGroups"
        ]
        Resource = ["*"]
      },
      {
        Effect = "Allow"
        Action = [
          "rds:CreateDBClusterSnapshot",
          "rds:DescribeDBClusterSnapshots",
          "rds:DeleteDBClusterSnapshot",
          "rds:ListTagsForResource"
        ]
        Resource = ["*"]
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = [
          "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-haiku-20240307-v1:0"
        ]
        Condition = {
          StringEquals = {
            "aws:RequestedRegion" = "us-east-1"
          }
        }
      }
    ]
  })
}

# Attach AWS managed policy for Glue
resource "aws_iam_role_policy_attachment" "glue_service_role_policy" {
  role       = aws_iam_role.glue_service_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

# Glue Connection to Aurora
resource "aws_glue_connection" "aurora" {
  name = "tokyobeta-${var.environment}-aurora-connection"

  connection_properties = {
    JDBC_CONNECTION_URL = "jdbc:mysql://${var.aurora_endpoint}:3306/${var.aurora_database}"
    SECRET_ID           = var.aurora_secret_arn
  }

  physical_connection_requirements {
    availability_zone      = data.aws_subnet.private[0].availability_zone
    security_group_id_list = [var.security_group_id]
    subnet_id              = var.private_subnet_ids[0]
  }
}

# Data source for subnet details
data "aws_subnet" "private" {
  count = length(var.private_subnet_ids)
  id    = var.private_subnet_ids[count.index]
}

# Glue Crawler for S3 Dumps
resource "aws_glue_crawler" "s3_dumps" {
  name          = "tokyobeta-${var.environment}-s3-dumps-crawler"
  role          = aws_iam_role.glue_service_role.arn
  database_name = aws_glue_catalog_database.source.name

  s3_target {
    path = "s3://${var.s3_source_bucket}/${var.s3_source_prefix}"
  }

  schedule = "cron(0 6 * * ? *)"  # Run at 6:00 AM JST daily

  schema_change_policy {
    delete_behavior = "LOG"
    update_behavior = "LOG"
  }

  tags = {
    Name        = "tokyobeta-${var.environment}-s3-crawler"
    Environment = var.environment
  }
}

# Glue Catalog Database
resource "aws_glue_catalog_database" "source" {
  name = "tokyobeta_${var.environment}_source"

  description = "Glue catalog for S3 SQL dumps"
}

resource "aws_glue_catalog_database" "staging" {
  name = "tokyobeta_${var.environment}_staging"

  description = "Staging schema metadata"
}

# Glue ETL Job
resource "aws_glue_job" "daily_etl" {
  name     = "tokyobeta-${var.environment}-daily-etl"
  role_arn = aws_iam_role.glue_service_role.arn

  command {
    name            = "glueetl"
    script_location = "s3://${var.s3_source_bucket}/glue-scripts/daily_etl.py"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--job-bookmark-option"              = "job-bookmark-enable"
    "--enable-metrics"                   = "true"
    "--enable-continuous-cloudwatch-log" = "true"
    "--enable-spark-ui"                  = "true"
    "--spark-event-logs-path"            = "s3://${var.s3_source_bucket}/glue-logs/"
    "--TempDir"                          = "s3://${var.s3_source_bucket}/glue-temp/"
    "--additional-python-modules"        = "protobuf==4.25.3,dbt-core==1.7.0,dbt-mysql==1.7.0,pymysql,boto3>=1.34.51,botocore>=1.34.51"
    
    # Custom parameters
    "--S3_SOURCE_BUCKET"     = var.s3_source_bucket
    "--S3_SOURCE_PREFIX"     = var.s3_source_prefix
    "--AURORA_ENDPOINT"      = var.aurora_endpoint
    "--AURORA_DATABASE"      = var.aurora_database
    "--AURORA_SECRET_ARN"    = var.aurora_secret_arn
    "--ENVIRONMENT"          = var.environment
    "--DBT_PROJECT_PATH"     = "s3://${var.s3_source_bucket}/dbt-project/"
  }

  glue_version      = "4.0"
  max_retries       = 0
  timeout           = 60
  worker_type       = "G.1X"
  number_of_workers = 2
  
  # VPC connection for Aurora access
  connections = [aws_glue_connection.aurora.name]

  execution_property {
    max_concurrent_runs = 1
  }

  tags = {
    Name        = "tokyobeta-${var.environment}-daily-etl"
    Environment = var.environment
  }
}

# Note: Glue Data Quality rulesets will be configured after first ETL run
# when staging.movings table exists in the Glue Data Catalog

# ============================================================================
# NEW RESILIENT ETL ARCHITECTURE (Three Independent Jobs)
# ============================================================================

# Job 1: Staging Loader
resource "aws_glue_job" "staging_loader" {
  name     = "tokyobeta-${var.environment}-staging-loader"
  role_arn = aws_iam_role.glue_service_role.arn

  command {
    name            = "glueetl"
    script_location = "s3://${var.s3_source_bucket}/glue-scripts/staging_loader.py"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--job-bookmark-option"              = "job-bookmark-disable"
    "--enable-metrics"                   = "true"
    "--enable-continuous-cloudwatch-log" = "true"
    "--enable-spark-ui"                  = "true"
    "--spark-event-logs-path"            = "s3://${var.s3_source_bucket}/glue-logs/staging/"
    "--TempDir"                          = "s3://${var.s3_source_bucket}/glue-temp/staging/"
    "--additional-python-modules"        = "pymysql"
    
    # Custom parameters
    "--S3_SOURCE_BUCKET"  = var.s3_source_bucket
    "--S3_SOURCE_PREFIX"  = var.s3_source_prefix
    "--AURORA_ENDPOINT"   = var.aurora_endpoint
    "--AURORA_DATABASE"   = var.aurora_database
    "--AURORA_SECRET_ARN" = var.aurora_secret_arn
    "--ENVIRONMENT"       = var.environment
  }

  glue_version      = "4.0"
  max_retries       = 0  # Retries handled by Step Functions
  timeout           = 30 # 30 minutes max
  worker_type       = "G.1X"
  number_of_workers = 2
  
  connections = [aws_glue_connection.aurora.name]

  execution_property {
    max_concurrent_runs = 1
  }

  tags = {
    Name        = "tokyobeta-${var.environment}-staging-loader"
    Environment = var.environment
    Layer       = "bronze"
    ManagedBy   = "terraform"
  }
}

# Job 2: Silver Transformer
resource "aws_glue_job" "silver_transformer" {
  name     = "tokyobeta-${var.environment}-silver-transformer"
  role_arn = aws_iam_role.glue_service_role.arn

  command {
    name            = "glueetl"
    script_location = "s3://${var.s3_source_bucket}/glue-scripts/silver_transformer.py"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--job-bookmark-option"              = "job-bookmark-disable"
    "--enable-metrics"                   = "true"
    "--enable-continuous-cloudwatch-log" = "true"
    "--enable-spark-ui"                  = "true"
    "--spark-event-logs-path"            = "s3://${var.s3_source_bucket}/glue-logs/silver/"
    "--TempDir"                          = "s3://${var.s3_source_bucket}/glue-temp/silver/"
    "--additional-python-modules"        = "protobuf==4.25.3,dbt-core==1.7.0,dbt-mysql==1.7.0,pymysql"
    
    # Custom parameters
    "--S3_SOURCE_BUCKET"  = var.s3_source_bucket
    "--DBT_PROJECT_PATH"  = "s3://${var.s3_source_bucket}/dbt-project/"
    "--AURORA_ENDPOINT"   = var.aurora_endpoint
    "--AURORA_DATABASE"   = var.aurora_database
    "--AURORA_SECRET_ARN" = var.aurora_secret_arn
    "--ENVIRONMENT"       = var.environment
  }

  glue_version      = "4.0"
  max_retries       = 0  # Retries handled by Step Functions
  timeout           = 60 # 60 minutes max (dbt deps + seed + models + tests + backups)
  worker_type       = "G.1X"
  number_of_workers = 2
  
  connections = [aws_glue_connection.aurora.name]

  execution_property {
    max_concurrent_runs = 1
  }

  tags = {
    Name        = "tokyobeta-${var.environment}-silver-transformer"
    Environment = var.environment
    Layer       = "silver"
    ManagedBy   = "terraform"
  }
}

# Job 3: Gold Transformer
resource "aws_glue_job" "gold_transformer" {
  name     = "tokyobeta-${var.environment}-gold-transformer"
  role_arn = aws_iam_role.glue_service_role.arn

  command {
    name            = "glueetl"
    script_location = "s3://${var.s3_source_bucket}/glue-scripts/gold_transformer.py"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--job-bookmark-option"              = "job-bookmark-disable"
    "--enable-metrics"                   = "true"
    "--enable-continuous-cloudwatch-log" = "true"
    "--enable-spark-ui"                  = "true"
    "--spark-event-logs-path"            = "s3://${var.s3_source_bucket}/glue-logs/gold/"
    "--TempDir"                          = "s3://${var.s3_source_bucket}/glue-temp/gold/"
    "--additional-python-modules"        = "protobuf==4.25.3,dbt-core==1.7.0,dbt-mysql==1.7.0,pymysql"
    
    # Custom parameters
    "--S3_SOURCE_BUCKET"  = var.s3_source_bucket
    "--DBT_PROJECT_PATH"  = "s3://${var.s3_source_bucket}/dbt-project/"
    "--AURORA_ENDPOINT"   = var.aurora_endpoint
    "--AURORA_DATABASE"   = var.aurora_database
    "--AURORA_SECRET_ARN" = var.aurora_secret_arn
    "--ENVIRONMENT"       = var.environment
    
    # Occupancy KPI parameters (integrated into gold job)
    "--LOOKBACK_DAYS"     = "3"
    "--FORWARD_DAYS"      = "90"
  }

  glue_version      = "4.0"
  max_retries       = 0  # Retries handled by Step Functions
  timeout           = 60 # 60 minutes max (dbt deps + seed + models + tests + backups)
  worker_type       = "G.1X"
  number_of_workers = 2
  
  connections = [aws_glue_connection.aurora.name]

  execution_property {
    max_concurrent_runs = 1
  }

  tags = {
    Name        = "tokyobeta-${var.environment}-gold-transformer"
    Environment = var.environment
    Layer       = "gold"
    ManagedBy   = "terraform"
  }
}

