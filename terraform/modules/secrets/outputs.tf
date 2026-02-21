# Secrets Module Outputs

output "aurora_secret_arn" {
  description = "ARN of the Aurora credentials secret"
  value       = aws_secretsmanager_secret.aurora_credentials.arn
}

output "aurora_username" {
  description = "Aurora master username"
  value       = var.db_username
}

output "aurora_password" {
  description = "Aurora master password (sensitive)"
  value       = random_password.aurora_password.result
  sensitive   = true
}

# RDS Cron Credentials Outputs
output "rds_cron_secret_arn" {
  description = "ARN of RDS cron credentials secret"
  value       = var.create_rds_cron_secret ? aws_secretsmanager_secret.rds_cron_credentials[0].arn : ""
}

output "rds_cron_secret_name" {
  description = "Name of RDS cron credentials secret"
  value       = var.create_rds_cron_secret ? aws_secretsmanager_secret.rds_cron_credentials[0].name : ""
}

output "rds_cron_username" {
  description = "RDS cron username"
  value       = var.rds_cron_username
}

output "rds_cron_password" {
  description = "RDS cron password (sensitive)"
  value       = var.create_rds_cron_secret ? (trimspace(var.rds_cron_password) != "" ? var.rds_cron_password : random_password.aurora_password.result) : ""
  sensitive   = true
}
