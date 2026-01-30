# Outputs for EC2 Management Module

output "instance_id" {
  description = "ID of the managed EC2 instance"
  value       = data.aws_instance.existing_cron_instance.id
}

output "instance_public_ip" {
  description = "Public IP address of the EC2 instance"
  value       = data.aws_instance.existing_cron_instance.public_ip
}

output "instance_private_ip" {
  description = "Private IP address of the EC2 instance"
  value       = data.aws_instance.existing_cron_instance.private_ip
}

output "instance_state" {
  description = "Current state of the EC2 instance"
  value       = data.aws_instance.existing_cron_instance.instance_state
}
