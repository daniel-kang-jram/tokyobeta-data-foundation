# IAM Role Module for EC2 Cron Job Instance
# Provides least-privilege access to S3 and Secrets Manager

# IAM Role for EC2 Instance
resource "aws_iam_role" "ec2_cron_role" {
  name        = "tokyobeta-${var.environment}-ec2-cron-role"
  description = "IAM role for EC2 instance running data export cron jobs"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "tokyobeta-${var.environment}-ec2-cron-role"
    Environment = var.environment
    Purpose     = "EC2 cron job execution"
  }
}

# IAM Policy for S3 Access (dumps bucket)
resource "aws_iam_policy" "s3_dumps_access" {
  name        = "tokyobeta-${var.environment}-s3-dumps-access"
  description = "Allow EC2 to upload SQL dumps to S3"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ListDumpsBucket"
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = "arn:aws:s3:::${var.s3_dumps_bucket}"
      },
      {
        Sid    = "UploadDumps"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:PutObjectAcl",
          "s3:GetObject"
        ]
        Resource = [
          "arn:aws:s3:::${var.s3_dumps_bucket}/dumps*/*",
          "arn:aws:s3:::${var.s3_dumps_bucket}/dumps*",
          "arn:aws:s3:::${var.s3_dumps_bucket}/contractstatus/*"
        ]
      }
    ]
  })

  tags = {
    Name        = "tokyobeta-${var.environment}-s3-dumps-policy"
    Environment = var.environment
  }
}

# IAM Policy for Secrets Manager Access (RDS credentials)
resource "aws_iam_policy" "secrets_manager_access" {
  name        = "tokyobeta-${var.environment}-secrets-manager-access"
  description = "Allow EC2 to read RDS credentials from Secrets Manager"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadRDSCredentials"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = var.rds_secret_arn
      }
    ]
  })

  tags = {
    Name        = "tokyobeta-${var.environment}-secrets-policy"
    Environment = var.environment
  }
}

# Attach S3 policy to role
resource "aws_iam_role_policy_attachment" "s3_access" {
  role       = aws_iam_role.ec2_cron_role.name
  policy_arn = aws_iam_policy.s3_dumps_access.arn
}

# Attach Secrets Manager policy to role
resource "aws_iam_role_policy_attachment" "secrets_access" {
  role       = aws_iam_role.ec2_cron_role.name
  policy_arn = aws_iam_policy.secrets_manager_access.arn
}

# Attach SSM Session Manager policy (for secure shell access)
resource "aws_iam_role_policy_attachment" "ssm_managed_instance" {
  role       = aws_iam_role.ec2_cron_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# Instance Profile to attach role to EC2
resource "aws_iam_instance_profile" "ec2_cron_profile" {
  name = "tokyobeta-${var.environment}-ec2-cron-profile"
  role = aws_iam_role.ec2_cron_role.name

  tags = {
    Name        = "tokyobeta-${var.environment}-ec2-cron-profile"
    Environment = var.environment
  }
}
