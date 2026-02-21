# Monitoring Module
# Creates CloudWatch alarms and SNS topics for alerts

locals {
  alert_recipients = toset(
    compact(
      distinct(
        concat(
          [var.alert_email],
          var.alert_emails
        )
      )
    )
  )
}

data "aws_caller_identity" "current" {}

# SNS Topic for alerts
resource "aws_sns_topic" "etl_alerts" {
  name = "tokyobeta-${var.environment}-dashboard-etl-alerts"

  tags = {
    Name        = "tokyobeta-${var.environment}-etl-alerts"
    Environment = var.environment
  }
}

data "aws_iam_policy_document" "etl_alerts_topic_policy" {
  statement {
    sid    = "AllowOwnerAccess"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = ["*"]
    }

    actions = [
      "SNS:GetTopicAttributes",
      "SNS:SetTopicAttributes",
      "SNS:AddPermission",
      "SNS:RemovePermission",
      "SNS:DeleteTopic",
      "SNS:Subscribe",
      "SNS:ListSubscriptionsByTopic",
      "SNS:Publish",
      "SNS:Receive",
    ]
    resources = [aws_sns_topic.etl_alerts.arn]

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceOwner"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }

  statement {
    sid    = "AllowCloudWatchPublish"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["cloudwatch.amazonaws.com"]
    }

    actions   = ["SNS:Publish"]
    resources = [aws_sns_topic.etl_alerts.arn]

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceOwner"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }

  statement {
    sid    = "AllowEventBridgeGlueFailurePublish"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }

    actions   = ["SNS:Publish"]
    resources = [aws_sns_topic.etl_alerts.arn]

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_cloudwatch_event_rule.glue_job_state_failures.arn]
    }
  }
}

resource "aws_sns_topic_policy" "etl_alerts" {
  arn    = aws_sns_topic.etl_alerts.arn
  policy = data.aws_iam_policy_document.etl_alerts_topic_policy.json
}

# SNS Topic Subscription
resource "aws_sns_topic_subscription" "etl_alerts_email" {
  for_each  = local.alert_recipients
  topic_arn = aws_sns_topic.etl_alerts.arn
  protocol  = "email"
  endpoint  = each.value
}

resource "aws_cloudwatch_event_rule" "glue_job_state_failures" {
  name        = "tokyobeta-${var.environment}-glue-job-state-failures"
  description = "Emit SNS alert when daily Glue job enters FAILED or TIMEOUT state"
  event_pattern = jsonencode({
    source      = ["aws.glue"]
    detail-type = ["Glue Job State Change"]
    detail = {
      jobName = [var.glue_job_name]
      state   = ["FAILED", "TIMEOUT"]
    }
  })

  tags = {
    Name        = "tokyobeta-${var.environment}-glue-failure-events"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_event_target" "glue_job_state_failures_sns" {
  rule      = aws_cloudwatch_event_rule.glue_job_state_failures.name
  target_id = "GlueFailureAlertsToSNS"
  arn       = aws_sns_topic.etl_alerts.arn
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
  treat_missing_data  = "notBreaching"

  dimensions = {
    JobName  = var.glue_job_name
    JobRunId = "ALL"
    Type     = "count"
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
  threshold           = "1800000" # 30 minutes in milliseconds
  alarm_description   = "Alert when Glue job takes longer than 30 minutes"
  alarm_actions       = [aws_sns_topic.etl_alerts.arn]
  treat_missing_data  = "notBreaching"

  dimensions = {
    JobName  = var.glue_job_name
    JobRunId = "ALL"
    Type     = "count"
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
  threshold           = "10737418240" # 10 GB in bytes
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
