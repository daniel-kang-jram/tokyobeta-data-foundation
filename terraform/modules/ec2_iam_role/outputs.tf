# Outputs for EC2 IAM Role Module

output "role_arn" {
  description = "ARN of the IAM role for EC2"
  value       = aws_iam_role.ec2_cron_role.arn
}

output "role_name" {
  description = "Name of the IAM role for EC2"
  value       = aws_iam_role.ec2_cron_role.name
}

output "instance_profile_name" {
  description = "Name of the instance profile to attach to EC2"
  value       = aws_iam_instance_profile.ec2_cron_profile.name
}

output "instance_profile_arn" {
  description = "ARN of the instance profile"
  value       = aws_iam_instance_profile.ec2_cron_profile.arn
}
