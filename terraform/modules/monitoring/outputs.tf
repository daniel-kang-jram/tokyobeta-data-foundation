# Monitoring Module Outputs

output "sns_topic_arn" {
  description = "ARN of the SNS alerts topic"
  value       = aws_sns_topic.etl_alerts.arn
}

output "sns_topic_name" {
  description = "Name of the SNS alerts topic"
  value       = aws_sns_topic.etl_alerts.name
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
