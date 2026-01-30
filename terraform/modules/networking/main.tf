# VPC and Networking Module
# Creates VPC, subnets, NAT gateway, and security groups for the data consolidation infrastructure

variable "environment" {
  description = "Environment name (dev/prod)"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones for subnet distribution"
  type        = list(string)
  default     = ["ap-northeast-1a", "ap-northeast-1c"]
}

# VPC
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "tokyobeta-${var.environment}-vpc"
    Environment = var.environment
  }
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name        = "tokyobeta-${var.environment}-igw"
    Environment = var.environment
  }
}

# Public Subnets (for NAT Gateway)
resource "aws_subnet" "public" {
  count                   = length(var.availability_zones)
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name        = "tokyobeta-${var.environment}-public-${var.availability_zones[count.index]}"
    Environment = var.environment
    Type        = "Public"
  }
}

# Private Subnets (for Aurora, Lambda)
resource "aws_subnet" "private" {
  count             = length(var.availability_zones)
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + 10)
  availability_zone = var.availability_zones[count.index]

  tags = {
    Name        = "tokyobeta-${var.environment}-private-${var.availability_zones[count.index]}"
    Environment = var.environment
    Type        = "Private"
  }
}

# Elastic IP for NAT Gateway
resource "aws_eip" "nat" {
  domain = "vpc"

  tags = {
    Name        = "tokyobeta-${var.environment}-nat-eip"
    Environment = var.environment
  }

  depends_on = [aws_internet_gateway.main]
}

# NAT Gateway (for Lambda to access S3)
resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id

  tags = {
    Name        = "tokyobeta-${var.environment}-nat"
    Environment = var.environment
  }

  depends_on = [aws_internet_gateway.main]
}

# Route Table for Public Subnets
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name        = "tokyobeta-${var.environment}-public-rt"
    Environment = var.environment
  }
}

# Route Table for Private Subnets
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main.id
  }

  tags = {
    Name        = "tokyobeta-${var.environment}-private-rt"
    Environment = var.environment
  }
}

# Route Table Associations - Public
resource "aws_route_table_association" "public" {
  count          = length(aws_subnet.public)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# Route Table Associations - Private
resource "aws_route_table_association" "private" {
  count          = length(aws_subnet.private)
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

# Security Group for Aurora
resource "aws_security_group" "aurora" {
  name        = "tokyobeta-${var.environment}-aurora-sg"
  description = "Security group for Aurora MySQL cluster"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 3306
    to_port     = 3306
    protocol    = "tcp"
    security_groups = [aws_security_group.lambda.id]
    description = "MySQL from Lambda"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }

  tags = {
    Name        = "tokyobeta-${var.environment}-aurora-sg"
    Environment = var.environment
  }
}

# Security Group for Lambda
resource "aws_security_group" "lambda" {
  name        = "tokyobeta-${var.environment}-lambda-sg"
  description = "Security group for Lambda ETL processor"
  vpc_id      = aws_vpc.main.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound (S3, Aurora, etc.)"
  }

  tags = {
    Name        = "tokyobeta-${var.environment}-lambda-sg"
    Environment = var.environment
  }
}

# Outputs
output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "private_subnet_ids" {
  description = "IDs of private subnets"
  value       = aws_subnet.private[*].id
}

output "public_subnet_ids" {
  description = "IDs of public subnets"
  value       = aws_subnet.public[*].id
}

output "aurora_security_group_id" {
  description = "ID of Aurora security group"
  value       = aws_security_group.aurora.id
}

output "lambda_security_group_id" {
  description = "ID of Lambda security group"
  value       = aws_security_group.lambda.id
}

output "nat_gateway_id" {
  description = "ID of NAT Gateway"
  value       = aws_nat_gateway.main.id
}
