# Variables for EC2 Management Module

variable "existing_instance_id" {
  type        = string
  description = "ID of the existing EC2 instance to manage"
  default     = "i-00523f387117d497b"
}

variable "instance_profile_name" {
  type        = string
  description = "Name of the IAM instance profile to attach"
}

variable "aws_region" {
  type        = string
  description = "AWS region where the EC2 instance is located"
  default     = "ap-northeast-1"
}

variable "attach_iam_profile" {
  type        = bool
  description = "Whether to attach the IAM instance profile"
  default     = false
}

variable "manage_instance_state" {
  type        = bool
  description = "Whether to manage the instance state (stop/start)"
  default     = false
}

variable "desired_state" {
  type        = string
  description = "Desired state of the instance (running, stopped)"
  default     = "running"

  validation {
    condition     = contains(["running", "stopped"], var.desired_state)
    error_message = "Desired state must be 'running' or 'stopped'"
  }
}

variable "update_tags" {
  type        = bool
  description = "Whether to update instance tags"
  default     = true
}

variable "instance_tags" {
  type        = map(string)
  description = "Tags to apply to the EC2 instance"
  default = {
    Name        = "JRAM-GGH-EC2-Cron"
    ManagedBy   = "Terraform"
    Purpose     = "Data Export Cron Jobs"
    Environment = "production"
  }
}

variable "environment" {
  type        = string
  description = "Environment name"
  default     = "prod"
}
