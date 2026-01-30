# Secrets Manager Module
# Generates and stores Aurora MySQL credentials securely

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
