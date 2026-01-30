# Outputs for QuickSight Module

output "data_source_id" {
  description = "QuickSight data source ID"
  value       = aws_quicksight_data_source.aurora_analytics.data_source_id
}

output "data_source_arn" {
  description = "QuickSight data source ARN"
  value       = aws_quicksight_data_source.aurora_analytics.arn
}

output "vpc_connection_arn" {
  description = "QuickSight VPC connection ARN"
  value       = aws_quicksight_vpc_connection.aurora_vpc.arn
}

output "quicksight_role_arn" {
  description = "IAM role ARN for QuickSight VPC access"
  value       = aws_iam_role.quicksight_vpc_connection.arn
}

output "spice_refresh_lambda_arn" {
  description = "Lambda function ARN for SPICE refresh"
  value       = var.enable_spice_refresh ? aws_lambda_function.spice_refresh[0].arn : ""
}
