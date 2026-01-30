# Secrets Manager Module
# Generates and stores Aurora MySQL credentials securely

variable "environment" {
  description = "Environment name (dev/prod)"
  type        = string
}

variable "db_username" {
  description = "Master username for Aurora"
  type        = string
  default     = "admin"
}

# Generate random password for Aurora
resource "random_password" "aurora_password" {
  length  = 32
  special = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# Store Aurora credentials in Secrets Manager
resource "aws_secretsmanager_secret" "aurora_credentials" {
  name        = "tokyobeta/${var.environment}/aurora/credentials"
  description = "Aurora MySQL master credentials for Tokyo Beta data consolidation"

  tags = {
    Name        = "tokyobeta-${var.environment}-aurora-creds"
    Environment = var.environment
  }
}

resource "aws_secretsmanager_secret_version" "aurora_credentials" {
  secret_id = aws_secretsmanager_secret.aurora_credentials.id
  secret_string = jsonencode({
    username = var.db_username
    password = random_password.aurora_password.result
    engine   = "mysql"
    port     = 3306
  })
}

# Outputs
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
