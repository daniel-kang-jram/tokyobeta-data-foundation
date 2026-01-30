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
