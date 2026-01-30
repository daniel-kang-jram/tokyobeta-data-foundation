# Aurora MySQL Module
# Creates Aurora MySQL cluster for analytics data warehouse

variable "environment" {
  description = "Environment name (dev/prod)"
  type        = string
}

variable "vpc_id" {
  description = "ID of the VPC"
  type        = string
}

variable "private_subnet_ids" {
  description = "IDs of private subnets for Aurora"
  type        = list(string)
}

variable "security_group_id" {
  description = "Security group ID for Aurora"
  type        = string
}

variable "db_username" {
  description = "Master username for Aurora"
  type        = string
}

variable "db_password" {
  description = "Master password for Aurora"
  type        = string
  sensitive   = true
}

variable "instance_class" {
  description = "Instance class for Aurora"
  type        = string
  default     = "db.t4g.medium"
}

variable "instance_count" {
  description = "Number of Aurora instances"
  type        = number
  default     = 2
}

# DB Subnet Group
resource "aws_db_subnet_group" "aurora" {
  name       = "tokyobeta-${var.environment}-aurora-subnet-group"
  subnet_ids = var.private_subnet_ids

  tags = {
    Name        = "tokyobeta-${var.environment}-aurora-subnet-group"
    Environment = var.environment
  }
}

# Aurora Cluster Parameter Group
resource "aws_rds_cluster_parameter_group" "aurora" {
  name        = "tokyobeta-${var.environment}-aurora-cluster-params"
  family      = "aurora-mysql8.0"
  description = "Custom parameter group for Aurora MySQL 8.0"

  parameter {
    name  = "character_set_server"
    value = "utf8mb4"
  }

  parameter {
    name  = "collation_server"
    value = "utf8mb4_unicode_ci"
  }

  parameter {
    name  = "max_connections"
    value = "1000"
  }

  tags = {
    Name        = "tokyobeta-${var.environment}-aurora-cluster-params"
    Environment = var.environment
  }
}

# Aurora DB Parameter Group (for instances)
resource "aws_db_parameter_group" "aurora" {
  name        = "tokyobeta-${var.environment}-aurora-instance-params"
  family      = "aurora-mysql8.0"
  description = "Custom parameter group for Aurora MySQL 8.0 instances"

  parameter {
    name  = "slow_query_log"
    value = "1"
  }

  parameter {
    name  = "long_query_time"
    value = "2"
  }

  tags = {
    Name        = "tokyobeta-${var.environment}-aurora-instance-params"
    Environment = var.environment
  }
}

# Aurora Cluster
resource "aws_rds_cluster" "aurora" {
  cluster_identifier              = "tokyobeta-${var.environment}-aurora-cluster"
  engine                          = "aurora-mysql"
  engine_version                  = "8.0.mysql_aurora.3.05.2"
  database_name                   = "tokyobeta"
  master_username                 = var.db_username
  master_password                 = var.db_password
  db_subnet_group_name            = aws_db_subnet_group.aurora.name
  vpc_security_group_ids          = [var.security_group_id]
  db_cluster_parameter_group_name = aws_rds_cluster_parameter_group.aurora.name
  
  backup_retention_period      = 7
  preferred_backup_window      = "03:00-04:00"
  preferred_maintenance_window = "mon:04:00-mon:05:00"
  
  enabled_cloudwatch_logs_exports = ["error", "general", "slowquery"]
  
  skip_final_snapshot       = var.environment == "dev" ? true : false
  final_snapshot_identifier = var.environment == "dev" ? null : "tokyobeta-${var.environment}-final-snapshot-${formatdate("YYYY-MM-DD-hhmm", timestamp())}"
  
  deletion_protection = var.environment == "prod" ? true : false

  tags = {
    Name        = "tokyobeta-${var.environment}-aurora-cluster"
    Environment = var.environment
  }
}

# Aurora Cluster Instances
resource "aws_rds_cluster_instance" "aurora" {
  count              = var.instance_count
  identifier         = "tokyobeta-${var.environment}-aurora-instance-${count.index + 1}"
  cluster_identifier = aws_rds_cluster.aurora.id
  instance_class     = var.instance_class
  engine             = aws_rds_cluster.aurora.engine
  engine_version     = aws_rds_cluster.aurora.engine_version
  
  db_parameter_group_name = aws_db_parameter_group.aurora.name
  
  publicly_accessible = false
  
  performance_insights_enabled    = true
  performance_insights_retention_period = 7

  tags = {
    Name        = "tokyobeta-${var.environment}-aurora-instance-${count.index + 1}"
    Environment = var.environment
  }
}

# Outputs
output "cluster_endpoint" {
  description = "Writer endpoint for the Aurora cluster"
  value       = aws_rds_cluster.aurora.endpoint
}

output "reader_endpoint" {
  description = "Reader endpoint for the Aurora cluster"
  value       = aws_rds_cluster.aurora.reader_endpoint
}

output "cluster_id" {
  description = "ID of the Aurora cluster"
  value       = aws_rds_cluster.aurora.id
}

output "database_name" {
  description = "Name of the default database"
  value       = aws_rds_cluster.aurora.database_name
}

output "port" {
  description = "Port of the Aurora cluster"
  value       = aws_rds_cluster.aurora.port
}
