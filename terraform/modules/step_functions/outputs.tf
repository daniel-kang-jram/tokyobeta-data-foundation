# Step Functions Module Outputs

output "state_machine_arn" {
  description = "ARN of the Step Functions state machine"
  value       = aws_sfn_state_machine.etl_orchestrator.arn
}

output "state_machine_name" {
  description = "Name of the Step Functions state machine"
  value       = aws_sfn_state_machine.etl_orchestrator.name
}

output "state_machine_role_arn" {
  description = "ARN of the Step Functions IAM role"
  value       = aws_iam_role.step_functions_role.arn
}

output "cloudwatch_log_group_name" {
  description = "Name of the CloudWatch log group for Step Functions"
  value       = aws_cloudwatch_log_group.step_functions_logs.name
}
