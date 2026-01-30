# Monitoring Module
# Creates CloudWatch alarms and SNS topics for alerts

variable "environment" {
  description = "Environment name (dev/prod)"
  type        = string
}

variable "glue_job_name" {
  description = "Name of the Glue job to monitor"
  type        = string
}

variable "aurora_cluster_id" {
  description = "ID of the Aurora cluster to monitor"
  type        = string
}

variable "alert_email" {
  description = "Email address for alert notifications"
  type        = string
}

# SNS Topic for alerts
resource "aws_sns_topic" "etl_alerts" {
  name = "tokyobeta-${var.environment}-dashboard-etl-alerts"

  tags = {
    Name        = "tokyobeta-${var.environment}-etl-alerts"
    Environment = var.environment
  }
}

# SNS Topic Subscription
resource "aws_sns_topic_subscription" "etl_alerts_email" {
  topic_arn = aws_sns_topic.etl_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# CloudWatch Alarm: Glue Job Failures
resource "aws_cloudwatch_metric_alarm" "glue_job_failures" {
  alarm_name          = "tokyobeta-${var.environment}-glue-job-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "glue.driver.aggregate.numFailedTasks"
  namespace           = "Glue"
  period              = "300"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "Alert when Glue ETL job fails"
  alarm_actions       = [aws_sns_topic.etl_alerts.arn]

  dimensions = {
    JobName = var.glue_job_name
  }

  tags = {
    Name        = "tokyobeta-${var.environment}-glue-failures"
    Environment = var.environment
  }
}

# CloudWatch Alarm: Glue Job Duration
resource "aws_cloudwatch_metric_alarm" "glue_job_duration" {
  alarm_name          = "tokyobeta-${var.environment}-glue-job-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "glue.driver.aggregate.elapsedTime"
  namespace           = "Glue"
  period              = "300"
  statistic           = "Maximum"
  threshold           = "1800000"  # 30 minutes in milliseconds
  alarm_description   = "Alert when Glue job takes longer than 30 minutes"
  alarm_actions       = [aws_sns_topic.etl_alerts.arn]

  dimensions = {
    JobName = var.glue_job_name
  }

  tags = {
    Name        = "tokyobeta-${var.environment}-glue-duration"
    Environment = var.environment
  }
}

# CloudWatch Alarm: Aurora CPU Utilization
resource "aws_cloudwatch_metric_alarm" "aurora_cpu" {
  alarm_name          = "tokyobeta-${var.environment}-aurora-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "Alert when Aurora CPU exceeds 80%"
  alarm_actions       = [aws_sns_topic.etl_alerts.arn]

  dimensions = {
    DBClusterIdentifier = var.aurora_cluster_id
  }

  tags = {
    Name        = "tokyobeta-${var.environment}-aurora-cpu"
    Environment = var.environment
  }
}

# CloudWatch Alarm: Aurora Storage
resource "aws_cloudwatch_metric_alarm" "aurora_storage" {
  alarm_name          = "tokyobeta-${var.environment}-aurora-low-storage"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "FreeLocalStorage"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "10737418240"  # 10 GB in bytes
  alarm_description   = "Alert when Aurora free storage < 10GB"
  alarm_actions       = [aws_sns_topic.etl_alerts.arn]

  dimensions = {
    DBClusterIdentifier = var.aurora_cluster_id
  }

  tags = {
    Name        = "tokyobeta-${var.environment}-aurora-storage"
    Environment = var.environment
  }
}

# Outputs
output "sns_topic_arn" {
  description = "ARN of the SNS alerts topic"
  value       = aws_sns_topic.etl_alerts.arn
}

output "alarm_names" {
  description = "Names of all CloudWatch alarms"
  value = [
    aws_cloudwatch_metric_alarm.glue_job_failures.alarm_name,
    aws_cloudwatch_metric_alarm.glue_job_duration.alarm_name,
    aws_cloudwatch_metric_alarm.aurora_cpu.alarm_name,
    aws_cloudwatch_metric_alarm.aurora_storage.alarm_name
  ]
}
