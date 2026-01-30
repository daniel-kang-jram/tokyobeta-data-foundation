# Networking Module Outputs

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

output "private_subnet_cidrs" {
  description = "CIDR blocks of private subnets"
  value       = aws_subnet.private[*].cidr_block
}
