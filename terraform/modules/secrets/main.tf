# Secrets Manager Module
# Generates and stores Aurora MySQL credentials securely

# Generate random password for Aurora
resource "random_password" "aurora_password" {
  length           = 32
  special          = true
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

# RDS Credentials for EC2 Cron Jobs
# Separate secret for the legacy RDS instance accessed by cron scripts

# Generate random password for RDS cron access (if creating new credentials)
resource "random_password" "rds_cron_password" {
  count            = var.create_rds_cron_secret ? 1 : 0
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# Store RDS cron job credentials in Secrets Manager
resource "aws_secretsmanager_secret" "rds_cron_credentials" {
  count       = var.create_rds_cron_secret ? 1 : 0
  name        = "tokyobeta/${var.environment}/rds/cron-credentials"
  description = "RDS credentials for EC2 cron job database dumps"

  tags = {
    Name        = "tokyobeta-${var.environment}-rds-cron-creds"
    Environment = var.environment
    Purpose     = "EC2 Cron Jobs"
  }

  lifecycle {
    precondition {
      condition     = var.environment != "prod"
      error_message = "Production dump-source secret values must be managed outside Terraform."
    }
  }
}

resource "aws_secretsmanager_secret_version" "rds_cron_credentials" {
  count     = var.create_rds_cron_secret ? 1 : 0
  secret_id = aws_secretsmanager_secret.rds_cron_credentials[0].id
  secret_string = jsonencode({
    host     = var.rds_cron_host
    username = var.rds_cron_username
    password = var.rds_cron_password != "" ? var.rds_cron_password : random_password.rds_cron_password[0].result
    database = var.rds_cron_database
    port     = var.rds_cron_port
    engine   = "mysql"
  })

  lifecycle {
    precondition {
      condition     = var.environment != "prod"
      error_message = "Production dump-source secret values must be managed outside Terraform."
    }
  }
}
