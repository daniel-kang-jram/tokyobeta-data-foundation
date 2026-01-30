# EventBridge Module Outputs

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
